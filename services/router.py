"""
services/router.py — Routeur hybride : décide QUI répond à la question.

Pourquoi ? Le RAG ne récupère que quelques lignes (8 sur 1000) : il ne peut pas
calculer un total ou une moyenne. On sépare donc :
    stat      -> pandas calcule (services/stats.py)
    text      -> RAG (recherche des lignes proches + LLM)
    graph     -> graphique (Phase 4)
    forecast / anomaly / churn -> modèles ML selon le domaine (Phase 5)
    export    -> export PDF

Étapes :
  1. Règles par mots-clés (fr / en / ar / derja traduite) pour les intents non
     ambigus (graphique, prévision, anomalie, churn, export) : instantané, sans LLM.
  2. Sinon, le LLM classe la question avec une SORTIE JSON CONTRAINTE (JSON schema
     passé à Ollama) : intent + opération choisie dans une liste fermée + colonnes.
  3. Validation du JSON en Python (colonnes existantes, opération autorisée, types).
     Le LLM ne calcule jamais et ne génère jamais de code (ni eval, ni exec).
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from services import stats
from services.llm import generer_json
from services.prompts import (PROMPT_SYSTEME_ROUTEUR, prompt_utilisateur_routeur,
                              schema_routeur)
from services.semantique import (colonne_pour_mot, concept_de, detecter_groupe,
                                 detecter_periode, normaliser)
from services.stats import Filtre, PlanStat

log = logging.getLogger("dataia.router")

INTENTS = ["stat", "graph", "text", "forecast", "anomaly", "churn", "export"]

# Mots-clés sans ambiguïté (appliqués à la question normalisée : minuscules, sans accents)
REGLES_INTENT = [
    ("export", [r"\bpdf\b", r"\bexport", r"telecharger (le |un )?rapport", r"تصدير", r"تقرير pdf"]),
    ("churn", [r"\bchurn", r"attrition", r"risque(nt)? de (partir|quitter)", r"(vont|va) (partir|quitter)",
               r"quitter la banque", r"depart des clients", r"clients? (a|qui) risque", r"\bleave the bank",
               r"likely to leave", r"مغادرة", r"يغادر", r"سيغادرون"]),
    ("anomaly", [r"anomal", r"aberran", r"\bfraud", r"outlier", r"suspect", r"شاذ", r"غير طبيعي", r"احتيال"]),
    ("forecast", [r"previs", r"\bprevoi", r"\bpredi(re|s|ction)\b.*(vente|chiffre|ca\b|mois|annee)",
                  r"\bforecast", r"\bpredict (the )?(sales|revenue)", r"mois prochain", r"next month",
                  r"توقع", r"تنبؤ", r"الشهر القادم"]),
    ("graph", [r"graphi", r"\bgraphe", r"diagramme", r"courbe", r"histogramme", r"camembert", r"\bchart",
               r"\bplot\b", r"\bgraph\b", r"visualis", r"dessine", r"رسم", r"مخطط", r"بياني"]),
]


@dataclass
class Routage:
    """Décision du routeur."""
    intent: str
    source: str                              # "regles" ou "llm"
    plan: Optional[PlanStat] = None          # plan de calcul (intent stat)
    brut: dict = field(default_factory=dict) # JSON brut du LLM (traçabilité / débogage)
    erreurs: List[str] = field(default_factory=list)   # problèmes de validation
    filtres_rejetes: List[str] = field(default_factory=list)  # filtres proposés par le LLM mais non ancrés
    precision: Optional[str] = None          # type de précision à demander (groupe, date, ...)


def intent_par_regles(question: str) -> Optional[str]:
    """Intent déterminé par mots-clés, ou None si la question n'est pas évidente."""
    q = normaliser(question)
    for intent, motifs in REGLES_INTENT:
        if any(re.search(m, q) for m in motifs):
            return intent
    return None


def _colonne_valide(df: pd.DataFrame, nom) -> Optional[str]:
    """Retrouve une colonne existante (tolère la casse) ; None sinon."""
    if not nom:
        return None
    if nom in df.columns:
        return nom
    par_nom = {str(c).lower(): c for c in df.columns}
    return par_nom.get(str(nom).lower())


def _nombre_dans_question(question: str) -> Optional[int]:
    """« top 3 », « les 5 meilleurs », « أفضل 3 » -> 3 / 5."""
    m = re.search(r"\b(?:top|les|the|first|premiers?)\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:premiers|meilleurs|plus|best|top)",
                  normaliser(question)) or re.search(r"(?:أفضل|أعلى|أكثر|أول)\s*(\d{1,2})(?!\d)", question)
    if not m:
        return None
    n = int(next(g for g in m.groups() if g))
    return n if 1 <= n <= 50 else None


# Noms de mois (fr / en / ar tunisien et oriental) -> numéro, pour ancrer les filtres « mois »
MOIS = {normaliser(m): str(i) for i, noms in enumerate([
    [], ["janvier", "january", "jan", "جانفي", "يناير"], ["fevrier", "february", "feb", "فيفري", "فبراير"],
    ["mars", "march", "مارس"], ["avril", "april", "apr", "أفريل", "أبريل"], ["mai", "may", "ماي", "مايو"],
    ["juin", "june", "جوان", "يونيو"], ["juillet", "july", "جويلية", "يوليو"], ["aout", "august", "aug", "أوت", "أغسطس"],
    ["septembre", "september", "sep", "سبتمبر"], ["octobre", "october", "oct", "أكتوبر"],
    ["novembre", "november", "nov", "نوفمبر"], ["decembre", "december", "dec", "ديسمبر"]]) for m in noms}


def _filtre_ancre(operateur: str, valeur: str, question: str) -> bool:
    """La valeur du filtre doit apparaître dans la question (pas de condition inventée)."""
    q = normaliser(question)
    if operateur == "mois":
        return valeur in re.findall(r"\d{1,2}", q) or any(MOIS[m] == valeur and re.search(rf"\b{re.escape(m)}\b", q)
                                                       for m in MOIS)
    v = normaliser(valeur).strip()
    if not v:
        return False
    if re.fullmatch(r"[\d.,]+", v):           # nombre : doit être écrit tel quel dans la question
        return v in re.findall(r"\d[\d.,]*", q) or v.rstrip("0").rstrip(".") in q
    return v in q


def valider_plan(df: pd.DataFrame, brut: dict, question: str) -> Routage:
    """
    Transforme le JSON du LLM en PlanStat validé.
    Les erreurs ne sont pas « réparées » en silence : elles déclenchent une demande
    de précision à l'utilisateur.
    """
    routage = Routage(intent="stat", source="llm", brut=brut)
    operation = brut.get("operation")
    if operation not in stats.OPERATIONS:
        routage.erreurs.append(f"opération non autorisée : {operation!r}")
        routage.precision = "operation"
        return routage

    plan = PlanStat(operation=operation)
    plan.colonne = _colonne_valide(df, brut.get("colonne"))
    plan.colonne_groupe = _colonne_valide(df, brut.get("colonne_groupe"))
    plan.colonne_date = _colonne_valide(df, brut.get("colonne_date"))
    agregation = brut.get("agregation") or "sum"
    plan.agregation = agregation if agregation in stats.AGREGATIONS else "sum"
    plan.ordre = "asc" if brut.get("ordre") == "asc" else "desc"
    plan.periode = brut.get("periode") if brut.get("periode") in stats.PERIODES else "mois"
    n = _nombre_dans_question(question) or brut.get("n") or 5
    plan.n = max(1, min(int(n), 50))

    # Filtres : colonne existante, opérateur autorisé, valeur non vide ET présente dans la question.
    # Cas mesuré : pour « CA par région », le LLM a ajouté « Status == Pending » (recopié d'un
    # exemple du prompt) -> 305 lignes sur 1000 et un résultat faux. Un filtre doit être ANCRÉ.
    for f in brut.get("filtres") or []:
        col = _colonne_valide(df, f.get("colonne"))
        op = f.get("operateur")
        val = str(f.get("valeur", "")).strip()
        if op == "mois":
            val = MOIS.get(normaliser(val), val)
        if col and op in stats.OPERATEURS_FILTRE and val and _filtre_ancre(op, val, question):
            plan.filtres.append(Filtre(col, op, val))
        else:
            routage.erreurs.append(f"filtre ignoré (non autorisé ou absent de la question) : {f}")
            if col and op and val:
                routage.filtres_rejetes.append(f"{col} {op} {val}")
            log.info("Filtre rejeté : %s", f)

    # Regroupement / période lus dans la question (règles déterministes, prioritaires sur le LLM).
    # Cas mesurés : le LLM ignorait « par région » (total global) et regroupait
    # « top 3 products » par Total_Price au lieu de Product.
    periode = detecter_periode(question)
    groupe = detecter_groupe(df, question)
    if periode and operation in ("sum", "mean", "median", "count", "min", "max", "trend"):
        plan.agregation = operation if operation in stats.AGREGATIONS else plan.agregation
        plan.operation = operation = "trend"
        plan.periode = periode
    elif groupe:
        plan.colonne_groupe = groupe
        if operation in ("sum", "mean", "median", "min", "max"):
            plan.agregation = operation
            plan.operation = operation = "groupby"
    elif plan.colonne_groupe and stats.est_numerique(df, plan.colonne_groupe) and df[plan.colonne_groupe].nunique() > 20:
        # Le LLM propose de regrouper par une mesure continue : non pertinent
        routage.erreurs.append(f"regroupement par une colonne numérique ignoré : {plan.colonne_groupe}")
        plan.colonne_groupe = None
    if plan.agregation == "count" and operation in ("groupby", "top"):
        plan.operation = operation = "count" if operation == "groupby" else operation

    # Contrôles propres à chaque opération
    # (le conflit « groupe = mesure » est vérifié dans assistant.py APRÈS la résolution
    #  déterministe de la mesure : le LLM met parfois la catégorie dans `colonne`)
    if operation in ("groupby", "percentage") and not plan.colonne_groupe:
        routage.precision = "groupe"
    if operation == "trend":
        if not plan.colonne_date or not stats.est_date(df, plan.colonne_date):
            dates = [c for c in df.columns if stats.est_date(df, c)]
            if dates:
                plan.colonne_date = dates[0]          # une seule colonne date : choix évident
            else:
                routage.precision = "date"
    if operation == "count" and plan.colonne_groupe == plan.colonne:
        plan.colonne = None

    routage.plan = plan
    return routage


# « Quelles sont les régions ? », « Which payment methods… », « ما هي المناطق » :
# lister les valeurs d'une colonne est une question EXACTE -> pandas (count par valeur).
# Mesuré : via le RAG, le modèle 3B ne citait que les valeurs des 8 lignes extraites
# (4 régions sur 5, 2 moyens de paiement sur 3).
MOTIFS_LISTE = [
    r"\b(?:quel(?:le)?s? sont les|quels|quelles|liste(?:r)?(?: des| les| de)?|enumere(?:r)? les)\s+(?:different(?:e)?s\s+)?([a-z]\w*)",
    r"\b(?:quel(?:le)?s?)\s+(?:le|la|les)\s+([a-z]\w*)",                # derja traduite : « quel le produits »
    r"\b(?:which|what|list(?: the| all)?)\s+(?:are the\s+|the\s+|different\s+)?([a-z]\w*)",
    r"(?:ما هي|ماهي|ما هى|اذكر|عدد)\s+(?:ال)?(\S+)",
    r"(?:^|\s)ما\s+(?:ال)?(\S+)",                                       # derja « شنوة » traduite en « ما »
]
MOTS_CALCUL = re.compile(
    r"total|somme|moyen|median|combien|plus|moins|maxi|mini|top|meilleur|pire|nombre|pourcent|part\b|evolution|"
    r"\bsum\b|average|mean|most|least|highest|lowest|how many|how much|count|percent|share|trend|"
    r"مجموع|متوسط|اكثر|اقل|اعلى|ادنى|كم|نسبة|تطور|\d")


def liste_par_regles(df: pd.DataFrame, question: str) -> Optional[str]:
    """Colonne dont l'utilisateur demande la liste des valeurs, ou None."""
    q = normaliser(question)
    if MOTS_CALCUL.search(q) or concept_de(question):
        return None
    # « Quels clients ont le statut Pending ? » : une valeur du fichier est citée -> il y a un
    # filtre, c'est au LLM de l'extraire (on ne répond pas par la liste complète)
    for c in df.columns:
        if not stats.est_numerique(df, c) and df[c].nunique() <= 200:
            if any(len(str(v)) >= 3 and re.search(rf"(?<!\w){re.escape(normaliser(v))}(?!\w)", q)
                   for v in df[c].dropna().unique()):
                return None
    for motif in MOTIFS_LISTE:
        for mot in re.findall(motif, q):
            colonne = colonne_pour_mot(df, mot)
            if colonne and not stats.est_numerique(df, colonne):
                return colonne
    return None


def router(df: pd.DataFrame, question: str) -> Routage:
    """Point d'entrée : règles d'abord, LLM (JSON contraint) ensuite."""
    intent = intent_par_regles(question)
    if intent:
        return Routage(intent=intent, source="regles")

    colonne_liste = liste_par_regles(df, question)
    if colonne_liste:
        return Routage(intent="stat", source="regles",
                       plan=PlanStat(operation="count", colonne_groupe=colonne_liste, liste=True))

    brut = generer_json(schema_routeur(df), PROMPT_SYSTEME_ROUTEUR,
                        prompt_utilisateur_routeur(df, question), etape="routage", max_tokens=160)
    log.info("Routeur LLM : %s", brut)
    intent = brut.get("intent")
    if intent not in INTENTS:
        intent = "text"                     # valeur imprévue : repli sur le RAG
    if intent != "stat":
        return Routage(intent=intent, source="llm", brut=brut)
    return valider_plan(df, brut, question)

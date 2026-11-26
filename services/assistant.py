"""
services/assistant.py — Parcours complet d'une question (appelé par la route /ask_ia).

    question
      -> langue (services/langue.py : détection + glossaire derja)
      -> routeur (services/router.py : règles puis JSON contraint du LLM)
      -> selon l'intent :
           stat      : résolution de la colonne (semantique.py) -> pandas (stats.py)
                       -> phrase + tableau + provenance (redaction.py)
           text      : RAG (rag.py) + LLM avec un prompt réduit
           graph     : (Phase 4) RAG + ancien format JSON de graphique
           forecast / anomaly / churn : vérification du domaine (ml/registry.py)
           export    : rappel du bouton Export PDF
      -> réponse + temps de chaque étape (pour mesurer les performances)
"""

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import pandas as pd

from config import REFORMULATION_LLM
from services import charts, rag, redaction, stats
from services.langue import AnalyseLangue
from services.llm import demarrer_trace, generer_reponse
from services.ml import registry
from services.prompts import (PROMPT_SYSTEME_REFORMULATION, prompt_systeme_rag,
                              prompt_utilisateur_rag, prompt_utilisateur_reformulation)
from services.router import Routage, router
from services.semantique import resoudre_mesure
from services.stats import ErreurCalcul, PlanStat

log = logging.getLogger("dataia.assistant")


@dataclass
class Reponse:
    texte: str
    intent: str
    source_routage: str = ""
    resultat: Optional[dict] = None              # résultat structuré (valeur, tableau...) pour l'UI / le PDF
    suggestions: List[str] = field(default_factory=list)
    demande_precision: bool = False
    temps: dict = field(default_factory=dict)
    graphique: Optional[dict] = None             # Phase 4 : {"figure", "spec", "tableau"} (calculé par pandas)
    _resultat_graphique: object = field(default=None, repr=False)   # pour l'enregistrement (PNG + base)

    def en_dict(self) -> dict:
        d = asdict(self)
        d.pop("_resultat_graphique", None)
        return d


MESSAGES_INTENT = {
    "export": {
        "fr": "Pour exporter l'analyse, cliquez sur le bouton **« Export PDF »** en haut de la page.",
        "en": "To export the analysis, click the **“Export PDF”** button at the top of the page.",
        "ar": "لتصدير التحليل، انقر على زر **«Export PDF»** في أعلى الصفحة.",
    },
    "modele_bientot": {
        "fr": "Le modèle **{nom}** est disponible pour votre domaine (**{domaine}**). Son exécution sera branchée "
              "à la prochaine étape du projet (Phase 5).",
        "en": "The **{nom}** model is available for your domain (**{domaine}**). It will be connected in the next "
              "project step (Phase 5).",
        "ar": "نموذج **{nom}** متاح لمجالك (**{domaine}**). سيتم تفعيله في المرحلة القادمة من المشروع (المرحلة 5).",
    },
    "modele_indisponible": {
        "fr": "Désolé, le modèle **{nom}** n'est pas proposé pour votre domaine d'activité (**{domaine}**). "
              "Il est réservé au(x) domaine(s) : {domaines}. Modèles disponibles pour vous : {dispo}. "
              "Vous pouvez changer de domaine dans votre profil si besoin.",
        "en": "Sorry, the **{nom}** model is not offered for your business domain (**{domaine}**). "
              "It is reserved for: {domaines}. Models available to you: {dispo}. "
              "You can change your domain in your profile if needed.",
        "ar": "عذرًا، نموذج **{nom}** غير متاح لمجال نشاطك (**{domaine}**). "
              "هو مخصص لمجال: {domaines}. النماذج المتاحة لك: {dispo}. يمكنك تغيير مجالك من ملفك الشخصي.",
    },
}


def _msg(cle: str, langue: str, **kwargs) -> str:
    textes = MESSAGES_INTENT[cle]
    return textes.get(langue, textes["fr"]).format(**kwargs)


def resume_categories(df: pd.DataFrame, max_valeurs: int = 20) -> str:
    """Valeurs distinctes des colonnes texte (aide le LLM pour les questions descriptives)."""
    lignes = []
    for c in df.select_dtypes(include=["object", "string", "category"]).columns:
        uniques = df[c].dropna().astype(str).unique()
        if len(uniques) > 50:      # identifiants (factures, noms de clients...) : peu utiles ici
            continue
        lignes.append(f"- {c} : {', '.join(uniques[:max_valeurs])}")
    return "\n".join(lignes) if lignes else "-"


# ---------------------------------------------------------------------------
# Intent « stat » : pandas calcule
# ---------------------------------------------------------------------------
def _repondre_stat(df: pd.DataFrame, routage: Routage, analyse: AnalyseLangue, question_originale: str,
                   temps: dict) -> Reponse:
    langue = analyse.langue_reponse
    plan: PlanStat = routage.plan

    # Précisions structurelles (pas de colonne de groupe, pas de date, opération inconnue)
    if routage.precision in ("groupe", "date", "operation"):
        if routage.precision == "groupe":
            candidates = [c for c in df.columns if not stats.est_numerique(df, c) and df[c].nunique() <= 50]
            texte = redaction.t("precision_groupe", langue, cols=", ".join(f"`{c}`" for c in candidates) or "-")
        else:
            texte = redaction.t(f"precision_{routage.precision}", langue)
        return Reponse(texte=texte, intent="stat", source_routage=routage.source, demande_precision=True)

    # Choix déterministe de la colonne mesurée (identique dans toutes les langues).
    # On analyse la question d'origine ET la version traduite (derja -> fr).
    resolution = None
    if plan.operation != "count":
        texte_analyse = f"{question_originale}\n{analyse.question_pour_llm}"
        resolution = resoudre_mesure(df, texte_analyse, plan.colonne)
        if resolution.ambigu:
            # On calcule chaque option avec pandas pour aider l'utilisateur à choisir
            options = []
            for o in resolution.options_precision:
                p = PlanStat(**{**plan.__dict__, "colonne": o["colonne"], "colonne_multiplicateur": o["multiplicateur"]})
                try:
                    r = stats.executer(df, p)
                    valeur = r.valeur
                except ErreurCalcul:
                    valeur = None
                options.append({"mesure": p.libelle_mesure(), "valeur": valeur})
            texte, suggestions = redaction.message_precision_colonne(resolution, plan, options, langue)
            return Reponse(texte=texte, intent="stat", source_routage=routage.source,
                           suggestions=suggestions, demande_precision=True,
                           resultat={"options": options, "concept": resolution.concept})
        plan.colonne, plan.colonne_multiplicateur = resolution.colonne, resolution.multiplicateur
        # Regrouper une mesure par elle-même n'a pas de sens (ex. top 3 « par Total_Price »)
        if plan.colonne_groupe and plan.colonne_groupe in (plan.colonne, plan.colonne_multiplicateur):
            if plan.operation in ("groupby", "percentage"):
                routage.precision = "groupe"
                return _repondre_stat(df, routage, analyse, question_originale, temps)
            plan.colonne_groupe = None

    # Exécution par pandas
    debut = time.time()
    try:
        res = stats.executer(df, plan)
    except ErreurCalcul as e:
        return Reponse(texte=f"⚠️ {e}", intent="stat", source_routage=routage.source, demande_precision=True)
    temps["calcul_pandas_s"] = round(time.time() - debut, 3)

    if res.nb_lignes_utilisees == 0 and plan.filtres:
        filtres = ", ".join(f"{f.colonne} {f.operateur} {f.valeur}" for f in plan.filtres)
        return Reponse(texte=redaction.t("aucune_ligne", langue, f=filtres), intent="stat",
                       source_routage=routage.source, demande_precision=True)

    phrase = redaction.phrase_modele(res, plan, langue)
    tableau = redaction.tableau_markdown(res.tableau, langue)
    provenance = redaction.ligne_provenance(res, plan, resolution, langue)
    if routage.filtres_rejetes:
        provenance += "\n>\n> ⚠️ " + redaction.t("filtres_rejetes", langue,
                                                 f=", ".join(f"`{x}`" for x in routage.filtres_rejetes))

    # Reformulation par le LLM (optionnelle), vérifiée nombre par nombre.
    # Uniquement pour un résultat à UNE valeur : pour un tableau (groupby, top, ...),
    # le LLM recopiait toutes les lignes (mesuré : 78 tokens, +15 s) alors que le
    # tableau est déjà affiché.
    intro = phrase
    resultat_scalaire = plan.operation in ("sum", "mean", "median", "min", "max") or \
        (plan.operation == "count" and not plan.colonne_groupe)
    if REFORMULATION_LLM and resultat_scalaire:
        debut = time.time()
        resume = phrase + ("\n" + redaction.tableau_markdown(res.tableau.head(5), langue)
                           if res.tableau is not None else "")
        try:
            proposition = generer_reponse(PROMPT_SYSTEME_REFORMULATION,
                                          prompt_utilisateur_reformulation(analyse.question_pour_llm, resume, langue),
                                          etape="reformulation", max_tokens=90)
            autorises = res.nombres() + [v for groupe in redaction.nombres_du_texte(question_originale) for v in groupe]
            if proposition and redaction.reformulation_valide(proposition, autorises):
                intro = proposition + "\n\n" + phrase
            else:
                log.warning("Reformulation rejetée (nombre non issu de pandas) : %r", proposition)
                temps["reformulation_rejetee"] = True
        except Exception as e:     # la reformulation est un bonus : jamais bloquante
            log.warning("Reformulation impossible : %s", e)
        temps["reformulation_s"] = round(time.time() - debut, 2)

    texte = "\n\n".join(x for x in (intro, tableau, provenance) if x)
    resultat = {
        "operation": plan.operation, "mesure": res.mesure, "valeur": res.valeur,
        "colonne_groupe": plan.colonne_groupe, "colonne_date": plan.colonne_date,
        "filtres": [f.__dict__ for f in plan.filtres],
        "nb_lignes_utilisees": res.nb_lignes_utilisees, "nb_lignes_total": res.nb_lignes_total,
        "tableau": res.tableau.to_dict(orient="records") if res.tableau is not None else None,
        "details": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in res.details.items()},
    }
    return Reponse(texte=texte, intent="stat", source_routage=routage.source, resultat=resultat)


# ---------------------------------------------------------------------------
# Intent « text » (et « graph » en attendant la Phase 4) : RAG
# ---------------------------------------------------------------------------
def _repondre_rag(df: pd.DataFrame, file_id: int, analyse: AnalyseLangue, intent: str, temps: dict) -> Reponse:
    debut = time.time()
    textes = rag.lignes_en_textes(df)
    index = rag.charger_ou_construire_index(int(file_id), textes)
    # Recherche hybride : mots-clés exacts (identifiants) + similarité vectorielle
    extraits = rag.recherche_hybride(index, df, textes, analyse.question_pour_llm)
    temps["recherche_rag_s"] = round(time.time() - debut, 2)
    texte = generer_reponse(
        prompt_systeme_rag(analyse.langue_reponse),
        prompt_utilisateur_rag(df, resume_categories(df), "\n".join(f"- {e}" for e in extraits),
                               analyse.question_pour_llm, analyse.langue_reponse),
        etape="rag")
    return Reponse(texte=texte, intent=intent)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def repondre(df: pd.DataFrame, file_id: int, question: str, analyse: AnalyseLangue, domaine: str) -> Reponse:
    debut_total = time.time()
    trace = demarrer_trace()
    temps: dict = {}
    langue = analyse.langue_reponse

    debut = time.time()
    routage = router(df, analyse.question_pour_llm)
    temps["routage_s"] = round(time.time() - debut, 2)

    intent = routage.intent
    if intent == "stat":
        reponse = _repondre_stat(df, routage, analyse, question, temps)
    elif intent == "graph":
        # Phase 4 : moteur de graphiques (données calculées par pandas, jamais par le LLM)
        rg = charts.generer(df, analyse.question_pour_llm, langue)
        temps.update({f"graphique_{k}": v for k, v in rg.temps.items()})
        reponse = Reponse(texte=rg.texte, intent=intent, suggestions=rg.suggestions,
                          demande_precision=rg.demande_precision,
                          graphique={"figure": rg.figure, "spec": rg.spec, "tableau": rg.tableau} if rg.figure else None,
                          _resultat_graphique=rg)
    elif intent == "text":
        reponse = _repondre_rag(df, file_id, analyse, intent, temps)
    elif intent == "export":
        reponse = Reponse(texte=_msg("export", langue), intent=intent)
    else:   # forecast, anomaly, churn : selon le domaine de l'utilisateur
        nom = registry.nom_modele(intent, langue)
        if registry.est_disponible(intent, domaine):
            texte = _msg("modele_bientot", langue, nom=nom, domaine=domaine)
        else:
            texte = _msg("modele_indisponible", langue, nom=nom, domaine=domaine,
                         domaines=", ".join(registry.domaines_du_modele(intent)),
                         dispo=", ".join(registry.nom_modele(m, langue) for m in registry.modeles_du_domaine(domaine)))
        reponse = Reponse(texte=texte, intent=intent)

    reponse.source_routage = reponse.source_routage or routage.source
    if analyse.avertissement:
        reponse.texte = f"{analyse.avertissement}\n\n{reponse.texte}"
    temps["total_s"] = round(time.time() - debut_total, 2)
    temps["appels_llm"] = trace
    temps["prompt_tokens_total"] = sum(a.get("prompt_tokens") or 0 for a in trace)
    reponse.temps = temps
    log.info("Question traitée : intent=%s (%s) en %.1f s, %d appel(s) LLM",
             intent, routage.source, temps["total_s"], len(trace))
    return reponse

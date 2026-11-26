"""
services/semantique.py — Lien entre les mots métier de la question et les colonnes.

Problème réel (produits_magasin.csv) : « total des ventes » alors que le fichier n'a
pas de colonne de ventes, seulement `price` et `stock_quantity`. Le LLM avait choisi
`price` (et, avant le routeur, inventé 105,00 puis 106,20 selon la langue).

Ce module est DÉTERMINISTE (règles, pas de LLM) : une même question donne la même
colonne en français, en anglais, en arabe ou en derja.
  1. la question cite explicitement une colonne        -> on respecte ce choix ;
  2. un concept métier est reconnu (ventes, quantité…) -> colonne correspondante
     (« calculé sur la colonne X » est indiqué dans la réponse) ;
  3. aucune colonne ne correspond                      -> on demande une précision,
     avec les options possibles (calculées par pandas).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from services.stats import est_numerique

# Concept -> mots qui l'expriment (fr / en / ar / derja traduite) et motifs de noms de colonnes.
# Les motifs sont classés par priorité : le premier qui correspond est le plus « logique ».
CONCEPTS = {
    "ventes": {
        "mots": [r"ventes?", r"chiffres? d'affaires?", r"revenus?", r"recettes?",
                 r"\bsales?\b", r"revenues?", r"turnover", r"مبيعات", r"المبيعات", r"رقم المعاملات",
                 r"رقم الأعمال", r"الإيرادات", r"إيرادات", r"مداخيل"],
        "colonnes": [r"(^|_)(sales?|ventes?)($|_)", r"revenue|turnover|chiffre|(^|_)ca($|_)",
                     r"total.?(price|amount|prix|montant|sales?)", r"montant|amount"],
    },
    "quantite": {
        "mots": [r"quantit[ée]s?", r"\bqty\b", r"\bqt[ée]\b", r"unit[ée]s vendues", r"\bquantity\b",
                 r"\bunits\b", r"كمية", r"الكمية", r"الكميات"],
        "colonnes": [r"quantit|(^|_)qty($|_)|(^|_)qte($|_)", r"units?", r"stock"],
    },
    "prix": {
        "mots": [r"\bprix\b", r"\bprice\b", r"tarifs?", r"co[uû]ts?", r"\bcost\b", r"سعر", r"السعر", r"ثمن", r"أسعار"],
        "colonnes": [r"unit.?price|prix.?unit", r"price|prix|tarif", r"cost|co[uû]t"],
    },
}


@dataclass
class Resolution:
    """Résultat de la résolution de la colonne mesurée."""
    colonne: Optional[str]
    multiplicateur: Optional[str] = None
    concept: Optional[str] = None           # concept reconnu dans la question
    note: str = ""                          # clé de note pour la réponse ("concept", "explicite"...)
    alternatives: List[str] = field(default_factory=list)
    options_precision: List[dict] = field(default_factory=list)  # si une précision est nécessaire

    @property
    def ambigu(self) -> bool:
        return bool(self.options_precision)


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, '_' et '-' remplacés par des espaces (arabe conservé)."""
    texte = unicodedata.normalize("NFKD", str(texte).lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[_\-]+", " ", texte)


def colonnes_citees(question: str, colonnes: List[str]) -> List[str]:
    """Colonnes dont le nom apparaît tel quel dans la question (ex. « stock_quantity »)."""
    q = " " + normaliser(question) + " "
    trouvees = []
    for c in sorted(colonnes, key=len, reverse=True):
        nom = normaliser(c).strip()
        if len(nom) >= 2 and re.search(r"(?<![\w])" + re.escape(nom) + r"(?![\w])", q):
            if not any(nom in normaliser(t) for t in trouvees):
                trouvees.append(c)
    return trouvees


def produit_cite(question: str, colonnes: List[str]) -> Optional[tuple]:
    """Détecte « colonneA × colonneB » (×, x, *, fois) dans la question."""
    noms = sorted(colonnes, key=len, reverse=True)
    motif_col = "|".join(re.escape(normaliser(c)) for c in noms)
    m = re.search(rf"({motif_col})\s*(?:×|\*|\bx\b|\bfois\b|\btimes\b)\s*({motif_col})", normaliser(question))
    if not m:
        return None
    par_nom = {normaliser(c): c for c in noms}
    return par_nom[m.group(1)], par_nom[m.group(2)]


def concept_de(question: str) -> Optional[str]:
    """Premier concept métier reconnu dans la question (ventes, quantité, prix)."""
    # « CA » seulement en majuscules : en minuscules, « ça » deviendrait « ca » après normalisation
    if re.search(r"\bCA\b", question):
        return "ventes"
    q = normaliser(question)
    for concept, regles in CONCEPTS.items():
        # motifs normalisés comme la question (sinon « الإيرادات » ne serait jamais reconnu)
        if any(re.search(normaliser(motif), q) for motif in regles["mots"]):
            return concept
    return None


def colonnes_du_concept(df: pd.DataFrame, concept: str) -> List[str]:
    """Colonnes numériques correspondant au concept, de la plus à la moins logique."""
    resultat = []
    for motif in CONCEPTS[concept]["colonnes"]:
        for c in df.columns:
            nom = normaliser(c).replace(" ", "_")
            # « Nombre de ventes » COMPTE des ventes : ce n'est pas un chiffre d'affaires (Phase 7, mesuré)
            if concept == "ventes" and re.match(r"(nombre|nb|count|quantit|qte|qty)", nom):
                continue
            if c not in resultat and re.search(motif, nom) and est_numerique(df, c):
                resultat.append(c)
    return resultat


# ---------------------------------------------------------------------------
# Regroupement (« par région », « by product », « حسب المنطقة », « top 3 produits »)
# ---------------------------------------------------------------------------
# Mot de la question (fr / en / ar) -> mots-clés possibles dans les NOMS de colonnes
SYNONYMES_COLONNES = {
    "produit": ["product", "produit", "item", "article"], "product": ["product", "produit", "item"],
    "article": ["article", "item", "product"], "categorie": ["category", "categorie", "cat"],
    "category": ["category", "categorie"], "client": ["client", "customer"], "customer": ["customer", "client"],
    "region": ["region", "zone", "gouvernorat"], "zone": ["zone", "region"], "ville": ["city", "ville"],
    "city": ["city", "ville"], "pays": ["country", "pays"], "country": ["country", "pays"],
    "vendeur": ["rep", "seller", "vendeur", "commercial"], "commercial": ["rep", "commercial", "seller"],
    "seller": ["seller", "rep"], "rep": ["rep"], "statut": ["status", "statut", "etat"], "etat": ["status", "etat"],
    "status": ["status", "statut"], "paiement": ["payment", "paiement"], "payment": ["payment", "paiement"],
    "genre": ["gender", "genre", "sexe"], "sexe": ["gender", "sexe"], "gender": ["gender"],
    "magasin": ["store", "shop", "magasin"], "store": ["store", "shop"], "type": ["type"],
    "المنطقة": ["region", "zone"], "المناطق": ["region", "zone"], "الجهة": ["region"], "الولاية": ["region", "gouvernorat"],
    "المنتج": ["product", "produit"], "المنتجات": ["product", "produit"], "المنتوج": ["product"],
    "الفئة": ["category", "categorie"], "الصنف": ["category"], "العميل": ["client", "customer"],
    "العملاء": ["client", "customer"], "الحريف": ["client"], "الحرفاء": ["client"], "المدينة": ["city", "ville"],
    "البلد": ["country"], "الدولة": ["country"], "الحالة": ["status"], "الدفع": ["payment"],
    "البائع": ["rep", "seller"], "الجنس": ["gender"],
}
# « par mois », « monthly », « شهريا » -> évolution dans le temps (trend)
PERIODES_QUESTION = [
    ("mois", r"par mois|mensuel|chaque mois|by month|per month|monthly|حسب الشهر|شهري"),
    ("annee", r"par an(nee)?\b|annuel|chaque annee|by year|per year|yearly|annual|حسب السنة|سنوي"),
    ("semaine", r"par semaine|hebdomadaire|by week|per week|weekly|أسبوعي"),
    ("jour", r"par jour|quotidien|by day|per day|daily|يومي"),
    ("trimestre", r"par trimestre|trimestriel|by quarter|quarterly|فصلي"),
]
MOTIFS_GROUPE = [
    r"\b(?:par|by|per|pour chaque|for each|selon|chaque|de chaque)\s+(?:(?:la|le|les|l'|the|each|type de)\s+)?([a-z][\w']*)",
    r"\btop\s*\d*\s+(?:des\s+|du\s+|de\s+|of\s+the\s+|of\s+|the\s+)?([a-z]\w*)",
    r"\b\d+\s+(?:meilleurs|premiers|plus grands|best|top|biggest|largest)\s+([a-z]\w*)",
    r"\b(?:les|the)\s+\d+\s+(?:meilleurs\s+|premiers\s+)?([a-z]\w*)",
    # Motifs appliqués au texte normalisé : NFKD retire les hamzas (أفضل -> افضل)
    r"(?:حسب|لكل|بحسب)\s+(\S+)",
    r"(?:افضل|اكثر|اعلى|اول)\s+\d+\s+(\S+)",
]


_SYNONYMES_NORMALISES = {normaliser(k): v for k, v in SYNONYMES_COLONNES.items()}
# Formes arabes sans article (« المنتجات » -> « منتجات ») et pluriels courants sans article
for _cle, _val in list(_SYNONYMES_NORMALISES.items()):
    if _cle.startswith("ال") and len(_cle) > 3:
        _SYNONYMES_NORMALISES.setdefault(_cle[2:], _val)
_SYNONYMES_NORMALISES.update({normaliser(k): v for k, v in {
    "منتجات": ["product", "produit"], "منتوجات": ["product"], "مناطق": ["region", "zone"],
    "عملاء": ["client", "customer"], "حرفاء": ["client"], "فئات": ["category"]}.items()})


def _jetons_colonne(colonne: str) -> List[str]:
    """« Client_Name » -> ['client', 'name'] ; « SalesRep » -> ['sales', 'rep']."""
    texte = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(colonne))
    return normaliser(texte).split()


def colonne_pour_mot(df: pd.DataFrame, mot: str) -> Optional[str]:
    """Colonne catégorielle désignée par un mot de la question (gère le pluriel et les synonymes)."""
    mot = normaliser(mot).strip("'?؟.,")
    singulier = re.sub(r"(s|x)$", "", mot) if len(mot) > 3 else mot
    cles = _SYNONYMES_NORMALISES.get(mot) or _SYNONYMES_NORMALISES.get(singulier) or [singulier]
    for c in df.columns:
        if est_numerique(df, c) and df[c].nunique() > 20:
            continue                          # une mesure continue n'est pas une catégorie
        jetons = _jetons_colonne(c)
        for cle in cles:
            if any(j == cle or (len(cle) >= 4 and (j.startswith(cle) or cle.startswith(j)) and len(j) >= 4)
                   for j in jetons):
                return c
    return None


def detecter_periode(question: str) -> Optional[str]:
    q = normaliser(question)
    for periode, motif in PERIODES_QUESTION:
        if re.search(motif, q):
            return periode
    return None


def detecter_groupe(df: pd.DataFrame, question: str) -> Optional[str]:
    """Colonne de regroupement citée dans la question, ou None."""
    q = normaliser(question)
    for motif in MOTIFS_GROUPE:
        for mot in re.findall(motif, q):
            colonne = colonne_pour_mot(df, mot)
            if colonne:
                return colonne
    return None


def mesure_par_defaut(df: pd.DataFrame, numeriques: List[str]) -> Optional[str]:
    """Colonne à mesurer quand la question n'en nomme aucune (voir resoudre_mesure, étape 5)."""
    sans_id = [c for c in numeriques
               if not re.search(r"(^|_)(id|code|num|numero|no|ref)($|_)", normaliser(c).replace(" ", "_"))]
    ventes = [c for c in colonnes_du_concept(df, "ventes") if c in sans_id]
    if ventes:
        return ventes[0]
    totaux = [c for c in sans_id if normaliser(c).strip() in ("total", "totaux", "montant total", "total general")]
    if totaux:
        return totaux[0]
    return sans_id[0] if len(sans_id) == 1 else None


def resoudre_mesure(df: pd.DataFrame, question: str, colonne_llm: Optional[str],
                    multiplicateur_llm: Optional[str] = None) -> Resolution:
    """
    Choisit la colonne à mesurer de façon reproductible.
    `colonne_llm` (proposée par le routeur) n'est retenue que si elle est cohérente
    avec la question ; sinon les règles ci-dessous décident.
    """
    colonnes = [str(c) for c in df.columns]
    numeriques = [c for c in colonnes if est_numerique(df, c)]

    # 1. Produit explicite : « price × stock_quantity »
    produit = produit_cite(question, numeriques)
    if produit:
        return Resolution(colonne=produit[0], multiplicateur=produit[1], note="explicite")

    # 2. Colonne(s) numérique(s) citée(s) explicitement par l'utilisateur
    citees = [c for c in colonnes_citees(question, colonnes) if c in numeriques]
    if citees:
        return Resolution(colonne=citees[0], note="explicite")

    concept = concept_de(question)

    # 3. Concept métier reconnu -> colonne correspondante
    if concept:
        candidates = colonnes_du_concept(df, concept)
        if candidates:
            choix = colonne_llm if colonne_llm in candidates else candidates[0]
            return Resolution(colonne=choix, concept=concept, note="concept",
                              alternatives=[c for c in candidates if c != choix])
        # Pas de colonne de ventes : proposer prix, quantité et prix × quantité
        options = []
        if concept == "ventes":
            prix = colonnes_du_concept(df, "prix")
            quantites = colonnes_du_concept(df, "quantite")
            for c in prix[:1] + quantites[:1]:
                options.append({"colonne": c, "multiplicateur": None})
            if prix and quantites:
                options.append({"colonne": prix[0], "multiplicateur": quantites[0]})
        if not options:
            options = [{"colonne": c, "multiplicateur": None} for c in numeriques[:5]]
        return Resolution(colonne=None, concept=concept, note="absent", options_precision=options)

    # 4. Pas de concept : on garde la proposition du LLM si elle est numérique
    if colonne_llm in numeriques:
        mult = multiplicateur_llm if multiplicateur_llm in numeriques else None
        return Resolution(colonne=colonne_llm, multiplicateur=mult, note="llm")

    # 5. Mesure par défaut (signalée dans la réponse) : colonne de CA, sinon colonne « Total »,
    #    sinon l'unique colonne numérique. Ex. « Quel est le mois le plus fort ? » sur un tableau
    #    Mois | Tunis | Sfax | ... | Total -> colonne Total.
    defaut = mesure_par_defaut(df, numeriques)
    if defaut:
        return Resolution(colonne=defaut, note="defaut")

    # 6. Rien d'exploitable : précision demandée
    return Resolution(colonne=None, note="inconnu",
                      options_precision=[{"colonne": c, "multiplicateur": None} for c in numeriques[:5]])

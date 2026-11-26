"""
services/charts.py — Moteur de graphiques Plotly (Phase 4).

Principe (identique à la Phase 3) : le LLM ne fournit JAMAIS les valeurs.
  1. On lit la question : type demandé (« en camembert »), colonnes, regroupement,
     période, agrégation, filtres -> règles déterministes (fr / en / ar / derja).
  2. Seulement si les colonnes restent inconnues, le LLM propose une SPEC JSON
     contrainte {type, x, y, agg, color} (noms de colonnes en `enum`).
  3. La spec est validée ; si le type demandé ne convient pas aux données, on
     l'explique et on trace un type adapté.
  4. pandas calcule les données (agrégation, corrélations...) et Plotly dessine.
  5. La figure est enregistrée (JSON tout de suite, PNG via kaleido en arrière-plan).

Types : bar, bar_groupe, bar_empile, line, area, pie, donut, scatter, histogram, box, heatmap.

Règles du choix automatique (cahier des charges) :
  date + nombre -> line ; catégorie + nombre -> bar (pie si ≤ 6 catégories) ;
  2 nombres -> scatter ; 1 nombre -> histogram (box si demandé) ; ≥ 3 nombres -> heatmap.
"""

import datetime
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import config
from services import stats
from services.llm import generer_json
from services.redaction import formater_nombre
from services.semantique import (colonne_pour_mot, colonnes_citees, concept_de, detecter_periode,
                                 normaliser, resoudre_mesure)

log = logging.getLogger("dataia.charts")

TYPES = ["bar", "bar_groupe", "bar_empile", "line", "area", "pie", "donut", "scatter", "histogram", "box", "heatmap"]

NOMS_TYPES = {
    "bar": {"fr": "barres", "en": "bar chart", "ar": "أعمدة"},
    "bar_groupe": {"fr": "barres groupées", "en": "grouped bar chart", "ar": "أعمدة مجمعة"},
    "bar_empile": {"fr": "barres empilées", "en": "stacked bar chart", "ar": "أعمدة مكدسة"},
    "line": {"fr": "courbe", "en": "line chart", "ar": "منحنى"},
    "area": {"fr": "aire", "en": "area chart", "ar": "مساحي"},
    "pie": {"fr": "camembert", "en": "pie chart", "ar": "دائري"},
    "donut": {"fr": "anneau (donut)", "en": "donut chart", "ar": "حلقي"},
    "scatter": {"fr": "nuage de points", "en": "scatter plot", "ar": "نقاط انتشار"},
    "histogram": {"fr": "histogramme", "en": "histogram", "ar": "مدرج تكراري"},
    "box": {"fr": "boîte à moustaches", "en": "box plot", "ar": "صندوقي"},
    "heatmap": {"fr": "carte de chaleur des corrélations", "en": "correlation heatmap", "ar": "خريطة حرارية للارتباط"},
}

# Type explicitement demandé (question normalisée : minuscules, sans accents ni hamza).
# L'ordre compte : « donut » avant « camembert », « barres groupées » avant « barres ».
MOTIFS_TYPES = [
    ("donut", r"donut|doughnut|anneau|حلقي"),
    ("pie", r"camembert|secteurs?\b|\bpie\b|circulaire|دائري|قطاعي"),
    ("bar_empile", r"empile|stacked|مكدس"),
    ("bar_groupe", r"(barres?|batons?|colonnes?|bars?)\s+group|grouped|cote a cote|side by side|مجمع"),
    ("heatmap", r"heatmap|carte de chaleur|correlation|matrice|حراري|ارتباط"),
    ("box", r"boite a moustache|box ?plot|\bboxplot|moustaches|صندوقي"),
    ("scatter", r"nuage|scatter|dispersion|انتشار"),
    ("area", r"\baire\b|area chart|\barea\b|surface|مساحي"),
    ("line", r"courbe|\blignes?\b|line chart|\bline\b|منحنى|خطي"),
    ("histogram", r"histogramme|histogram|distribution|توزيع|مدرج"),
    ("bar", r"\bbarres?\b|\bbar\b|bar chart|batons|colonnes|اعمدة|شريطي"),
]
MOTS_MOYENNE = r"moyen|average|mean|متوسط"
MOTS_COMPTE = r"nombre de|combien|count|how many|number of|عدد|كم"
MOTS_MEDIANE = r"median|وسيط"


# ---------------------------------------------------------------------------
# Spécification
# ---------------------------------------------------------------------------
@dataclass
class SpecGraphique:
    """Spécification validée d'un graphique (enregistrée dans graphiques.spec_json)."""
    type: str = ""
    x: Optional[str] = None                 # catégorie, date ou nombre (axe horizontal)
    y: Optional[str] = None                 # mesure numérique (None = nombre de lignes)
    multiplicateur: Optional[str] = None    # y × multiplicateur (ex. prix × quantité)
    agg: str = "sum"
    color: Optional[str] = None             # 2e catégorie (barres groupées / empilées, séries)
    periode: Optional[str] = None           # pour une date : jour, semaine, mois, trimestre, annee
    colonnes_numeriques: List[str] = field(default_factory=list)   # scatter / heatmap
    filtres: List[dict] = field(default_factory=list)
    type_demande: Optional[str] = None      # type écrit par l'utilisateur, s'il y en a un
    raison: str = ""                        # clé de l'explication du choix
    raison_params: dict = field(default_factory=dict)
    incompatibilite: str = ""               # clé du message si le type demandé ne convient pas
    source_colonnes: str = "regles"         # "regles" ou "llm"

    def libelle_mesure(self) -> str:
        if self.y and self.multiplicateur:
            return f"{self.y} × {self.multiplicateur}"
        return self.y or "lignes"


def type_demande(question: str) -> Optional[str]:
    q = normaliser(question)
    for type_, motif in MOTIFS_TYPES:
        if re.search(motif, q):
            return type_
    return None


def _agregation(question: str) -> str:
    q = normaliser(question)
    if re.search(MOTS_MOYENNE, q):
        return "mean"
    if re.search(MOTS_MEDIANE, q):
        return "median"
    if re.search(MOTS_COMPTE, q) and not concept_de(question):
        return "count"
    return "sum"


MOTS_EVOLUTION = r"evolution|tendance|au fil du temps|dans le temps|trend|over time|تطور|عبر الزمن"


def _est_identifiant(df: pd.DataFrame, c: str) -> bool:
    """`product_id`, `Invoice_ID`, `code_client` : des identifiants, jamais un axe de graphique."""
    nom = normaliser(c).replace(" ", "_")
    return bool(re.search(r"(^|_)(id|code|num|numero|no|ref)($|_)", nom)) or \
        (df[c].nunique() == len(df) and len(df) > 20 and not stats.est_date(df, c))


def _position(question: str, colonne: str) -> int:
    """Position de la colonne dans la question (pour respecter l'ordre « X et Y »)."""
    i = normaliser(question).find(normaliser(colonne).strip())
    return i if i >= 0 else 10 ** 6


def _colonnes_dates(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if stats.est_date(df, c)]


def _est_categorie(df: pd.DataFrame, c: Optional[str]) -> bool:
    return bool(c) and c in df.columns and not stats.est_date(df, c) and not _est_identifiant(df, c) and \
        (not stats.est_numerique(df, c) or df[c].nunique() <= 20)


def _groupes_cites(df: pd.DataFrame, question: str) -> List[str]:
    """Toutes les colonnes de regroupement citées (« par région et par catégorie »), dans l'ordre."""
    q = normaliser(question)
    motifs = [r"\b(?:par|by|per|pour chaque|for each|selon|et par|and by|et|and)\s+(?:(?:la|le|les|l'|the|each)\s+)?([a-z][\w']*)",
              r"\btop\s*\d*\s+(?:des\s+|of\s+the\s+|of\s+|the\s+)?([a-z]\w*)",
              r"(?:^|\s)(?:حسب|لكل|بحسب)\s+(\S+)",
              r"(?:^|\s)و(?:حسب\s+)?(\S+)"]          # « و » (et) seulement en début de mot
    trouvees: List[str] = []
    for motif in motifs:
        for m in re.finditer(motif, q):
            c = colonne_pour_mot(df, m.group(1))
            if c and c not in trouvees and _est_categorie(df, c):
                trouvees.append(c)
    # ordre d'apparition dans la question
    def position(c):
        noms = [normaliser(w) for w in re.split(r"[_\s]", str(c)) if len(w) >= 3]
        positions = [q.find(n[:5]) for n in noms if q.find(n[:5]) >= 0]
        return min(positions) if positions else 10 ** 6
    return sorted(trouvees, key=position)


def _filtres_ancres(df: pd.DataFrame, question: str, exclues: List[str]) -> List[dict]:
    """Filtres déduits de valeurs écrites dans la question : année (« en 2024 »), valeur d'une catégorie (« à Tunis »)."""
    q = normaliser(question)
    filtres = []
    annees = re.findall(r"\b(19\d{2}|20\d{2})\b", q)
    dates = _colonnes_dates(df)
    if annees and dates:
        filtres.append({"colonne": dates[0], "operateur": "annee", "valeur": annees[0]})
    for c in df.columns:
        if c in exclues or stats.est_numerique(df, c) or df[c].nunique() > 200:
            continue
        for v in df[c].dropna().unique():
            if len(str(v)) >= 3 and re.search(rf"(?<!\w){re.escape(normaliser(v))}(?!\w)", q):
                filtres.append({"colonne": c, "operateur": "==", "valeur": str(v)})
                break
    return filtres


# ---------------------------------------------------------------------------
# Spec proposée par le LLM (seulement si les règles ne suffisent pas)
# ---------------------------------------------------------------------------
PROMPT_SYSTEME_GRAPHIQUE = """Tu prépares un graphique pour la plateforme DataIA. Tu ne calcules rien : tu choisis seulement les colonnes.
Réponds avec le JSON demandé :
- x : colonne de l'axe horizontal (catégorie ou date) ;
- y : colonne numérique à mesurer (null s'il faut compter les lignes) ;
- color : deuxième catégorie éventuelle (sinon null) ;
- agg : sum (total), mean (moyenne), count (nombre de lignes), median, min ou max ;
- type : le type de graphique demandé, ou auto s'il n'est pas précisé.
Utilise uniquement des noms de colonnes de la liste."""


def _schema_graphique(df: pd.DataFrame) -> dict:
    colonnes = [str(c) for c in df.columns]
    col_ou_null = {"anyOf": [{"type": "string", "enum": colonnes}, {"type": "null"}]}
    return {"type": "object",
            "properties": {"type": {"type": "string", "enum": TYPES + ["auto"]},
                           "x": col_ou_null, "y": col_ou_null, "color": col_ou_null,
                           "agg": {"type": "string", "enum": stats.AGREGATIONS}},
            "required": ["type", "x", "y", "agg"]}


def _spec_llm(df: pd.DataFrame, question: str) -> dict:
    from services.prompts import contexte_fichier
    return generer_json(_schema_graphique(df), PROMPT_SYSTEME_GRAPHIQUE,
                        f"{contexte_fichier(df)}\n\nDEMANDE : {question}", etape="spec_graphique", max_tokens=80)


# ---------------------------------------------------------------------------
# Construction de la spec : règles -> (LLM) -> choix / compatibilité du type
# ---------------------------------------------------------------------------
def construire_spec(df: pd.DataFrame, question: str) -> SpecGraphique:
    spec = SpecGraphique(type_demande=type_demande(question), agg=_agregation(question))
    numeriques = [c for c in df.columns if stats.est_numerique(df, c) and not stats.est_date(df, c)
                  and not _est_identifiant(df, c)]
    dates = _colonnes_dates(df)

    # --- 1. Règles déterministes
    cites = colonnes_citees(question, [str(c) for c in df.columns])
    nums_cites = sorted([c for c in cites if c in numeriques], key=lambda c: _position(question, c))
    groupes = _groupes_cites(df, question)
    spec.periode = detecter_periode(question)
    evolution = re.search(MOTS_EVOLUTION, normaliser(question))
    if (spec.periode or evolution) and dates:
        spec.x = dates[0]
    elif groupes:
        spec.x = groupes[0]
    if groupes and spec.x != groupes[0]:
        spec.color = groupes[0]
    elif len(groupes) > 1:
        spec.color = groupes[1]

    if spec.agg != "count":
        resolution = resoudre_mesure(df, question, None)
        if resolution.colonne:
            spec.y, spec.multiplicateur = resolution.colonne, resolution.multiplicateur
        elif resolution.options_precision and concept_de(question):
            # « ventes » sans colonne de ventes : même logique que la Phase 3 (pas de choix inventé)
            spec.raison = "precision_mesure"
            spec.raison_params = {"options": resolution.options_precision}
            return spec
    spec.colonnes_numeriques = nums_cites

    # Types qui ont besoin de colonnes numériques citées
    if spec.type_demande == "heatmap" or len(nums_cites) >= 3:
        spec.colonnes_numeriques = nums_cites if len(nums_cites) >= 2 else numeriques[:12]
    if spec.type_demande == "scatter" or (len(nums_cites) == 2 and not spec.x):
        if len(nums_cites) >= 2:
            spec.x, spec.y = nums_cites[0], nums_cites[1]

    # --- 2. LLM seulement si l'axe X ou la mesure restent inconnus pour un type qui en a besoin
    # « courbe / aire des ventes » : avec une colonne de dates, l'axe X est évident (pas de LLM)
    if spec.type_demande in ("line", "area") and not spec.x and dates:
        spec.x = dates[0]

    # Une seule colonne numérique citée, sans regroupement ni période : la règle
    # « 1 nombre -> histogramme » s'applique, pas besoin de chercher un axe X.
    une_seule_colonne = len(nums_cites) == 1 and not groupes and not spec.periode and not evolution
    besoin_x = spec.type_demande not in ("histogram", "box", "heatmap", "scatter") and not spec.x \
        and not une_seule_colonne
    besoin_y = spec.agg != "count" and not spec.y and spec.type_demande != "heatmap"
    if besoin_x or besoin_y:
        brut = _spec_llm(df, question)
        log.info("Spec graphique du LLM : %s", brut)
        spec.source_colonnes = "llm"
        if besoin_x and brut.get("x") in df.columns and (_est_categorie(df, brut["x"]) or brut["x"] in dates
                                                         or brut["x"] in numeriques):
            spec.x = brut["x"]
        if besoin_y and brut.get("y") in numeriques and brut.get("y") != spec.x:
            spec.y = brut["y"]
        if not spec.color and brut.get("color") in df.columns and _est_categorie(df, brut["color"]) \
                and brut["color"] != spec.x:
            spec.color = brut["color"]
        if brut.get("agg") == "count" and not spec.y:
            spec.agg = "count"
        if not spec.type_demande and brut.get("type") in TYPES:
            pass   # le type du LLM n'est pas retenu : le choix automatique suit les règles du cahier des charges

    # Un graphique « nombre de lignes » n'a pas de mesure
    if not spec.y and spec.agg != "count" and spec.x and spec.type_demande not in ("histogram", "box", "heatmap", "scatter"):
        spec.agg = "count"

    spec.filtres = _filtres_ancres(df, question, exclues=[c for c in (spec.x, spec.color) if c])
    _choisir_type(df, spec, numeriques, dates)
    return spec


def _type_auto(df: pd.DataFrame, spec: SpecGraphique, numeriques: List[str], dates: List[str]):
    """Choix automatique selon les règles du cahier des charges. Retourne (type, raison, params)."""
    if len(spec.colonnes_numeriques) >= 3:
        return "heatmap", "auto_heatmap", {"n": len(spec.colonnes_numeriques)}
    # Deux colonnes numériques CITÉES -> nuage de points, même si l'une a peu de valeurs
    # distinctes (Quantity : 1 à 20) et pourrait aussi servir de catégorie.
    if spec.x and spec.y and spec.x in spec.colonnes_numeriques and spec.y in spec.colonnes_numeriques:
        return "scatter", "auto_scatter", {"x": spec.x}
    if spec.x and spec.x in dates:
        return "line", "auto_line", {"x": spec.x}
    if spec.x and _est_categorie(df, spec.x):
        n = int(df[spec.x].nunique())
        if spec.color:
            return "bar_groupe", "auto_bar_groupe", {"x": spec.x, "color": spec.color}
        if n <= config.GRAPH_MAX_PIE and spec.agg in ("sum", "count"):
            return "pie", "auto_pie", {"x": spec.x, "n": n}
        return "bar", "auto_bar", {"x": spec.x, "n": n}
    if spec.x and spec.y and spec.x in numeriques:
        return "scatter", "auto_scatter", {"x": spec.x}
    if spec.y:
        return "histogram", "auto_histogram", {}
    return "", "precision_colonnes", {}


def _choisir_type(df: pd.DataFrame, spec: SpecGraphique, numeriques: List[str], dates: List[str]):
    """Respecte le type demandé s'il convient aux données, sinon l'explique et choisit un type adapté."""
    demande = spec.type_demande
    if not demande:
        spec.type, spec.raison, spec.raison_params = _type_auto(df, spec, numeriques, dates)
        return

    x_date = bool(spec.x) and spec.x in dates
    x_cat = _est_categorie(df, spec.x)
    probleme = ""
    if demande in ("line", "area"):
        if not spec.x and dates:
            spec.x = dates[0]                      # « courbe des ventes » : la date est évidente
            x_date = True
        if not (x_date or (spec.x in numeriques and not _est_identifiant(df, spec.x))):
            probleme = "inc_ligne_sans_date" if dates else "inc_ligne_aucune_date"
    elif demande in ("pie", "donut"):
        if not x_cat:
            probleme = "inc_camembert_sans_categorie"
        elif spec.y and (stats.en_numerique(df[spec.y]) < 0).any():
            probleme = "inc_camembert_negatif"
    elif demande == "scatter":
        if not (spec.x in numeriques and spec.y in numeriques and spec.x != spec.y):
            probleme = "inc_nuage"
    elif demande in ("histogram", "box"):
        if not spec.y:
            probleme = "inc_distribution"
        elif demande == "histogram" and x_cat:
            probleme = "inc_histogramme_categories"     # « histogramme des ventes par région » -> barres
    elif demande == "heatmap":
        if len(spec.colonnes_numeriques) < 2:
            probleme = "inc_heatmap"
    elif demande in ("bar_groupe", "bar_empile"):
        if not spec.color or not (x_cat or x_date):
            probleme = "inc_barres_groupees"
    elif demande == "bar":
        if not (x_cat or x_date):
            probleme = "inc_barres"

    if not probleme:
        spec.type, spec.raison, spec.raison_params = demande, "demande", {}
        return
    spec.incompatibilite = probleme
    if demande in ("bar_groupe", "bar_empile") and (x_cat or x_date):
        spec.color = None
    spec.type, spec.raison, spec.raison_params = _type_auto(df, spec, numeriques, dates)
    # En remplacement d'une courbe / d'un histogramme, des barres (mêmes axes) sont plus proches
    # de la demande qu'un camembert ; le camembert ne remplace qu'un donut.
    if spec.type == "pie" and (demande not in ("pie", "donut") or probleme == "inc_camembert_negatif"):
        spec.type = "bar"     # (un donut refusé pour valeurs négatives ne devient pas un camembert : même problème)
    if spec.type == spec.type_demande:      # ne pas « remplacer » par le même type
        spec.type = "bar"
    if spec.type:
        spec.raison, spec.raison_params = "remplacement", {}


# ---------------------------------------------------------------------------
# Données (pandas) + figure (Plotly)
# ---------------------------------------------------------------------------
NOMS_AGG = {"sum": {"fr": "Total", "en": "Total", "ar": "مجموع"}, "mean": {"fr": "Moyenne", "en": "Average", "ar": "متوسط"},
            "median": {"fr": "Médiane", "en": "Median", "ar": "وسيط"}, "count": {"fr": "Nombre de lignes", "en": "Number of rows", "ar": "عدد الأسطر"},
            "min": {"fr": "Minimum", "en": "Minimum", "ar": "أدنى"}, "max": {"fr": "Maximum", "en": "Maximum", "ar": "أعلى"}}
COULEURS = ["#00a8b5", "#0a84e0", "#6c5ce7", "#f39c12", "#e74c3c", "#27ae60", "#8e44ad", "#16a085", "#d35400", "#2c3e50"]


def _periode_auto(dates: pd.Series) -> str:
    etendue = (dates.max() - dates.min()).days
    for limite, periode in ((45, "jour"), (180, "semaine"), (1100, "mois"), (3650, "trimestre")):
        if etendue <= limite:
            return periode
    return "annee"


def _agreger(df: pd.DataFrame, spec: SpecGraphique, cles: List) -> pd.Series:
    """Agrégation pandas de la mesure (ou nombre de lignes) selon les clés de regroupement."""
    if spec.agg == "count" or not spec.y:
        return df.groupby(cles, observed=True).size()
    mesure = stats.en_numerique(df[spec.y])
    if spec.multiplicateur:
        mesure = mesure * stats.en_numerique(df[spec.multiplicateur])
    return getattr(mesure.groupby([df[c] if isinstance(c, str) else c for c in cles], observed=True), spec.agg)()


def _limiter(serie: pd.Series, maximum: int, agg: str, autres: str) -> pd.Series:
    """Garde les `maximum` plus grandes catégories ; les autres sont regroupées si l'agrégat est additif."""
    serie = serie.sort_values(ascending=False)
    if len(serie) <= maximum:
        return serie
    tete = serie.head(maximum - 1)
    if agg in ("sum", "count"):
        tete = pd.concat([tete, pd.Series({autres: serie.iloc[maximum - 1:].sum()})])
    return tete


def construire_figure(df: pd.DataFrame, spec: SpecGraphique, langue: str) -> tuple:
    """Calcule les données avec pandas et construit la figure. Retourne (figure, tableau, infos)."""
    nb_total = len(df)
    plan_filtres = [stats.Filtre(f["colonne"], f["operateur"], f["valeur"]) for f in spec.filtres]
    df = stats.appliquer_filtres(df, plan_filtres)
    if df.empty:
        raise stats.ErreurCalcul("Aucune ligne ne correspond aux filtres.")
    infos = {"nb_lignes_total": nb_total, "nb_lignes_utilisees": len(df)}
    nom_agg = NOMS_AGG[spec.agg if spec.y or spec.agg == "count" else "count"][langue if langue in ("fr", "en", "ar") else "fr"]
    mesure = spec.libelle_mesure() if spec.agg != "count" else ""
    axe_y = f"{nom_agg} {mesure}".strip()
    autres = {"fr": "Autres", "en": "Others", "ar": "أخرى"}.get(langue, "Autres")
    fig = go.Figure()
    tableau = None
    t = spec.type

    if t in ("bar", "pie", "donut"):
        if spec.x in _colonnes_dates(df):         # barres par période
            dates = stats.en_dates(df[spec.x])
            spec.periode = spec.periode or _periode_auto(dates)
            cle = dates.dt.to_period(stats.PERIODES[spec.periode]).astype(str)
            serie = _agreger(df.assign(_p=cle), spec, ["_p"]).sort_index()
        else:
            serie = _agreger(df, spec, [spec.x])
            limite = config.GRAPH_MAX_CATEGORIES if t == "bar" else config.GRAPH_MAX_PIE + 2
            avant = len(serie)
            serie = _limiter(serie, limite, spec.agg, autres)
            infos["categories_regroupees"] = max(0, avant - len(serie) + (1 if len(serie) < avant else 0))
        etiquettes = [str(i) for i in serie.index]
        if t == "bar":
            fig.add_bar(x=etiquettes, y=serie.values, marker_color=COULEURS[0],
                        hovertemplate="%{x} : %{y:,.2f}<extra></extra>")
            fig.update_layout(xaxis_title=spec.x, yaxis_title=axe_y)
        else:
            fig.add_pie(labels=etiquettes, values=serie.values, hole=0.45 if t == "donut" else 0,
                        marker={"colors": COULEURS}, textinfo="label+percent", sort=False,
                        hovertemplate="%{label} : %{value:,.2f} (%{percent})<extra></extra>")
        tableau = pd.DataFrame({spec.x: etiquettes, axe_y: serie.values})

    elif t in ("bar_groupe", "bar_empile"):
        serie = _agreger(df, spec, [spec.x, spec.color])
        totaux = serie.groupby(level=0).sum().sort_values(ascending=False).head(config.GRAPH_MAX_CATEGORIES)
        pivot = serie.unstack(spec.color).reindex(totaux.index).fillna(0)
        pivot = pivot[pivot.sum().sort_values(ascending=False).index[:10]]
        for i, couleur in enumerate(pivot.columns):
            fig.add_bar(name=str(couleur), x=[str(v) for v in pivot.index], y=pivot[couleur].values,
                        marker_color=COULEURS[i % len(COULEURS)],
                        hovertemplate=f"{couleur} — %{{x}} : %{{y:,.2f}}<extra></extra>")
        fig.update_layout(barmode="group" if t == "bar_groupe" else "stack", xaxis_title=spec.x,
                          yaxis_title=axe_y, legend_title=spec.color)
        tableau = pivot.reset_index()

    elif t in ("line", "area"):
        if spec.x in _colonnes_dates(df):
            dates = stats.en_dates(df[spec.x])
            spec.periode = spec.periode or _periode_auto(dates)
            cle = dates.dt.to_period(stats.PERIODES[spec.periode]).dt.to_timestamp()
            base = df.assign(_p=cle)
            cles = ["_p"] + ([spec.color] if spec.color else [])
        else:                                       # axe X numérique ordonné (ex. ancienneté)
            base, cles = df, [spec.x] + ([spec.color] if spec.color else [])
        serie = _agreger(base, spec, cles).sort_index()
        series = serie.unstack(spec.color).fillna(0) if spec.color else serie.to_frame(axe_y)
        for i, nom in enumerate(series.columns):
            fig.add_scatter(x=series.index, y=series[nom].values, name=str(nom), mode="lines+markers",
                            line={"color": COULEURS[i % len(COULEURS)], "width": 2},
                            fill=("tonexty" if spec.color and i else "tozeroy") if t == "area" else None,
                            stackgroup="a" if (t == "area" and spec.color) else None,
                            hovertemplate="%{x} : %{y:,.2f}<extra>" + str(nom) + "</extra>")
        fig.update_layout(xaxis_title=spec.x, yaxis_title=axe_y, showlegend=bool(spec.color))
        tableau = series.reset_index().rename(columns={"_p": spec.x})
        infos["periode"] = spec.periode

    elif t == "scatter":
        donnees = pd.DataFrame({spec.x: stats.en_numerique(df[spec.x]), spec.y: stats.en_numerique(df[spec.y])})
        if spec.color:
            donnees[spec.color] = df[spec.color].astype(str)
        donnees = donnees.dropna()
        if len(donnees) > config.GRAPH_MAX_POINTS:
            infos["echantillon"] = config.GRAPH_MAX_POINTS
            donnees = donnees.sample(config.GRAPH_MAX_POINTS, random_state=0)
        groupes = donnees.groupby(spec.color) if spec.color else [(None, donnees)]
        for i, (nom, part) in enumerate(groupes):
            # scatter (SVG) et non scattergl (WebGL) : l'export PNG headless de WebGL peut être vide
            fig.add_scatter(x=part[spec.x], y=part[spec.y], mode="markers", name=str(nom) if nom else spec.y,
                              marker={"color": COULEURS[i % len(COULEURS)], "size": 6, "opacity": 0.7})
        fig.update_layout(xaxis_title=spec.x, yaxis_title=spec.y, showlegend=bool(spec.color))
        infos["correlation"] = round(float(donnees[spec.x].corr(donnees[spec.y])), 3)
        tableau = donnees.describe().T.reset_index()

    elif t in ("histogram", "box"):
        valeurs = stats.en_numerique(df[spec.y])
        if spec.multiplicateur:
            valeurs = valeurs * stats.en_numerique(df[spec.multiplicateur])
        donnees = pd.DataFrame({"v": valeurs})
        groupe = spec.x if (t == "box" and _est_categorie(df, spec.x)) else (spec.color if _est_categorie(df, spec.color) else None)
        if groupe:
            donnees["g"] = df[groupe].astype(str)
        donnees = donnees.dropna()
        parties = donnees.groupby("g") if groupe else [(spec.libelle_mesure(), donnees)]
        for i, (nom, part) in enumerate(parties):
            if t == "histogram":
                fig.add_histogram(x=part["v"], name=str(nom), marker_color=COULEURS[i % len(COULEURS)],
                                  opacity=0.75 if groupe else 1)
            else:
                fig.add_box(y=part["v"], name=str(nom), marker_color=COULEURS[i % len(COULEURS)], boxmean=True)
        fig.update_layout(barmode="overlay", xaxis_title=spec.libelle_mesure() if t == "histogram" else groupe,
                          yaxis_title={"fr": "Nombre de lignes", "en": "Number of rows", "ar": "عدد الأسطر"}.get(langue)
                          if t == "histogram" else spec.libelle_mesure(), showlegend=bool(groupe))
        tableau = donnees.groupby("g")["v"].describe().reset_index() if groupe else donnees["v"].describe().to_frame().T

    elif t == "heatmap":
        colonnes = spec.colonnes_numeriques
        matrice = pd.DataFrame({c: stats.en_numerique(df[c]) for c in colonnes}).corr()   # corrélation de Pearson
        fig.add_heatmap(z=matrice.values, x=colonnes, y=colonnes, zmin=-1, zmax=1, colorscale="RdBu",
                        texttemplate="%{z:.2f}",   # formaté par Plotly : respecte la virgule décimale (fr)
                        hovertemplate="%{x} / %{y} : %{z:.2f}<extra></extra>")
        fig.update_layout(yaxis_autorange="reversed")
        tableau = matrice.round(3).reset_index().rename(columns={"index": ""})

    fig.update_layout(template="plotly_white", title={"text": titre(spec, langue), "x": 0.02},
                      font={"family": "Inter, Arial, sans-serif", "size": 13},
                      separators=", " if langue == "fr" else ".,", margin={"l": 60, "r": 30, "t": 70, "b": 60},
                      paper_bgcolor="white", plot_bgcolor="white")
    return fig, tableau, infos


def titre(spec: SpecGraphique, langue: str) -> str:
    l = langue if langue in ("fr", "en", "ar") else "fr"
    nom_agg = NOMS_AGG[spec.agg][l]
    de = {"fr": "de", "en": "of", "ar": ""}[l]
    par = {"fr": "par", "en": "by", "ar": "حسب"}[l]
    mesure = spec.libelle_mesure()
    if spec.type == "heatmap":
        base = {"fr": "Corrélations entre colonnes numériques", "en": "Correlations between numeric columns",
                "ar": "الارتباط بين الأعمدة الرقمية"}[l]
    elif spec.type == "scatter":
        base = {"fr": f"{spec.y} en fonction de {spec.x}", "en": f"{spec.y} vs {spec.x}", "ar": f"{spec.y} حسب {spec.x}"}[l]
    elif spec.type in ("histogram", "box"):
        base = {"fr": f"Distribution de {mesure}", "en": f"Distribution of {mesure}", "ar": f"توزيع {mesure}"}[l]
        if spec.type == "box" and spec.x:
            base += f" {par} {spec.x}"
    else:
        base = nom_agg if spec.agg == "count" else f"{nom_agg} {de} {mesure}".replace("  ", " ")
        base += f" {par} {spec.x}" + (f" {({'fr': 'et', 'en': 'and', 'ar': 'و'})[l]} {spec.color}" if spec.color else "")
    filtres = ", ".join(f["valeur"] for f in spec.filtres)
    return base + (f" ({filtres})" if filtres else "")


# ---------------------------------------------------------------------------
# Explications (écrites à la main, en 3 langues)
# ---------------------------------------------------------------------------
TEXTES = {
    "demande": {"fr": "Type demandé : **{type}**.", "en": "Requested type: **{type}**.", "ar": "النوع المطلوب: **{type}**."},
    "auto_line": {"fr": "Type choisi automatiquement : **courbe**, car `{x}` est une date et la valeur est numérique (règle : date + nombre → courbe).",
                  "en": "Type chosen automatically: **line chart**, because `{x}` is a date and the value is numeric (rule: date + number → line).",
                  "ar": "تم اختيار النوع تلقائيًا: **منحنى**، لأن `{x}` تاريخ والقيمة رقمية (القاعدة: تاريخ + رقم ← منحنى)."},
    "auto_bar": {"fr": "Type choisi automatiquement : **barres**, car `{x}` est une catégorie ({n} valeurs) — au-delà de 6 catégories, un camembert devient illisible (règle : catégorie + nombre → barres).",
                 "en": "Type chosen automatically: **bar chart**, because `{x}` is a category ({n} values) — above 6 categories a pie chart becomes unreadable (rule: category + number → bars).",
                 "ar": "تم اختيار النوع تلقائيًا: **أعمدة**، لأن `{x}` فئة ({n} قيمة) — أكثر من 6 فئات يجعل الرسم الدائري غير مقروء (القاعدة: فئة + رقم ← أعمدة)."},
    "auto_pie": {"fr": "Type choisi automatiquement : **camembert**, car `{x}` n'a que {n} catégories (≤ 6) et les valeurs forment un total (règle : catégorie + nombre, ≤ 6 catégories → camembert).",
                 "en": "Type chosen automatically: **pie chart**, because `{x}` has only {n} categories (≤ 6) and the values add up to a total (rule: category + number, ≤ 6 categories → pie).",
                 "ar": "تم اختيار النوع تلقائيًا: **دائري**، لأن `{x}` يحتوي على {n} فئات فقط (≤ 6) والقيم تشكل مجموعًا (القاعدة: فئة + رقم، ≤ 6 فئات ← دائري)."},
    "auto_bar_groupe": {"fr": "Type choisi automatiquement : **barres groupées**, car il y a deux catégories (`{x}` et `{color}`) et une valeur numérique.",
                        "en": "Type chosen automatically: **grouped bar chart**, because there are two categories (`{x}` and `{color}`) and a numeric value.",
                        "ar": "تم اختيار النوع تلقائيًا: **أعمدة مجمعة**، لأن هناك فئتين (`{x}` و`{color}`) وقيمة رقمية."},
    "auto_scatter": {"fr": "Type choisi automatiquement : **nuage de points**, car les deux colonnes sont numériques (règle : 2 nombres → nuage de points).",
                     "en": "Type chosen automatically: **scatter plot**, because both columns are numeric (rule: 2 numbers → scatter).",
                     "ar": "تم اختيار النوع تلقائيًا: **نقاط انتشار**، لأن العمودين رقميان (القاعدة: رقمان ← نقاط انتشار)."},
    "auto_histogram": {"fr": "Type choisi automatiquement : **histogramme**, car une seule colonne numérique est concernée : il montre comment ses valeurs se répartissent (règle : 1 nombre → histogramme).",
                       "en": "Type chosen automatically: **histogram**, because only one numeric column is involved: it shows how its values are distributed (rule: 1 number → histogram).",
                       "ar": "تم اختيار النوع تلقائيًا: **مدرج تكراري**، لأن عمودًا رقميًا واحدًا فقط معني: يبين كيف تتوزع قيمه (القاعدة: رقم واحد ← مدرج تكراري)."},
    "auto_heatmap": {"fr": "Type choisi automatiquement : **carte de chaleur des corrélations**, car {n} colonnes numériques sont concernées (règle : ≥ 3 nombres → heatmap).",
                     "en": "Type chosen automatically: **correlation heatmap**, because {n} numeric columns are involved (rule: ≥ 3 numbers → heatmap).",
                     "ar": "تم اختيار النوع تلقائيًا: **خريطة حرارية للارتباط**، لأن {n} أعمدة رقمية معنية (القاعدة: ≥ 3 أرقام ← خريطة حرارية)."},
    "inc_ligne_sans_date": {"fr": "⚠️ Une **{demande}** sert à montrer une évolution : elle a besoin d'une colonne de dates (ou de nombres ordonnés) sur l'axe horizontal, or `{x}` est une catégorie.",
                            "en": "⚠️ A **{demande}** shows a trend: it needs a date (or ordered numeric) column on the horizontal axis, but `{x}` is a category.",
                            "ar": "⚠️ **{demande}** يُظهر التطور: يحتاج إلى عمود تواريخ (أو أرقام مرتبة) على المحور الأفقي، لكن `{x}` فئة."},
    "inc_ligne_aucune_date": {"fr": "⚠️ Une **{demande}** montre une évolution dans le temps, mais ce fichier ne contient aucune colonne de dates.",
                              "en": "⚠️ A **{demande}** shows a trend over time, but this file has no date column.",
                              "ar": "⚠️ **{demande}** يُظهر التطور عبر الزمن، لكن هذا الملف لا يحتوي على أي عمود تواريخ."},
    "inc_camembert_sans_categorie": {"fr": "⚠️ Un **{demande}** représente les parts d'un total entre des catégories ; aucune colonne de catégories n'a été trouvée dans la demande.",
                                     "en": "⚠️ A **{demande}** shows the shares of a total across categories; no category column was found in the request.",
                                     "ar": "⚠️ **{demande}** يمثل حصص مجموع بين فئات؛ لم يتم العثور على عمود فئات في الطلب."},
    "inc_camembert_negatif": {"fr": "⚠️ Un **{demande}** ne peut pas représenter des valeurs négatives (une part ne peut pas être négative).",
                              "en": "⚠️ A **{demande}** cannot represent negative values (a share cannot be negative).",
                              "ar": "⚠️ لا يمكن لـ **{demande}** تمثيل قيم سالبة."},
    "inc_nuage": {"fr": "⚠️ Un **{demande}** compare deux colonnes numériques ; il en faut deux, différentes (ex. « nuage de points entre Quantity et Total_Price »).",
                  "en": "⚠️ A **{demande}** compares two numeric columns; two different ones are needed (e.g. “scatter plot of Quantity and Total_Price”).",
                  "ar": "⚠️ **{demande}** يقارن عمودين رقميين مختلفين؛ يجب ذكرهما (مثال: «Quantity و Total_Price»)."},
    "inc_distribution": {"fr": "⚠️ Un **{demande}** montre la distribution d'une colonne numérique ; aucune n'a été trouvée dans la demande.",
                         "en": "⚠️ A **{demande}** shows the distribution of a numeric column; none was found in the request.",
                         "ar": "⚠️ **{demande}** يُظهر توزيع عمود رقمي؛ لم يتم العثور على أي عمود رقمي في الطلب."},
    "inc_histogramme_categories": {"fr": "⚠️ Un **histogramme** montre la distribution des valeurs d'une colonne numérique ; pour comparer des catégories (`{x}`), un graphique en barres est adapté.",
                                   "en": "⚠️ A **histogram** shows the distribution of one numeric column; to compare categories (`{x}`), a bar chart is appropriate.",
                                   "ar": "⚠️ **المدرج التكراري** يُظهر توزيع قيم عمود رقمي؛ لمقارنة الفئات (`{x}`) الأعمدة هي الأنسب."},
    "inc_heatmap": {"fr": "⚠️ Une **{demande}** a besoin d'au moins deux colonnes numériques.",
                    "en": "⚠️ A **{demande}** needs at least two numeric columns.", "ar": "⚠️ **{demande}** يحتاج إلى عمودين رقميين على الأقل."},
    "inc_barres_groupees": {"fr": "⚠️ Des **{demande}** ont besoin de deux catégories (ex. « par région et par catégorie ») ; une seule a été trouvée.",
                            "en": "⚠️ A **{demande}** needs two categories (e.g. “by region and by category”); only one was found.",
                            "ar": "⚠️ **{demande}** يحتاج إلى فئتين (مثال: «حسب المنطقة وحسب الفئة»)؛ تم العثور على فئة واحدة."},
    "inc_barres": {"fr": "⚠️ Des **{demande}** ont besoin d'une catégorie ou d'une date sur l'axe horizontal.",
                   "en": "⚠️ A **{demande}** needs a category or a date on the horizontal axis.", "ar": "⚠️ **{demande}** يحتاج إلى فئة أو تاريخ على المحور الأفقي."},
    "remplace": {"fr": "J'ai tracé un graphique en **{type}** à la place.", "en": "I drew a **{type}** instead.",
                 "ar": "قمت برسم **{type}** بدلًا من ذلك."},
    "remplacement": {"fr": "Ce type est adapté à ces données (même lecture : `{x}` sur l'axe horizontal, la valeur sur l'axe vertical).",
                     "en": "This type suits these data (same reading: `{x}` on the horizontal axis, the value on the vertical axis).",
                     "ar": "هذا النوع مناسب لهذه البيانات (نفس القراءة: `{x}` على المحور الأفقي والقيمة على المحور العمودي)."},
    "provenance": {"fr": "📊 *Données calculées par pandas — {detail} · {u} lignes utilisées sur {t}*",
                   "en": "📊 *Data computed by pandas — {detail} · {u} rows used out of {t}*",
                   "ar": "📊 *بيانات محسوبة بواسطة pandas — {detail} · {u} سطر مستعمل من {t}*"},
    "precision_colonnes": {"fr": "Précisez ce que vous voulez représenter. Exemples adaptés à ce fichier :",
                           "en": "Please specify what to plot. Examples for this file:",
                           "ar": "يرجى تحديد ما تريد تمثيله. أمثلة مناسبة لهذا الملف:"},
    "autres_types": {"fr": "Autres types possibles pour ces données :", "en": "Other possible types for these data:",
                     "ar": "أنواع أخرى ممكنة لهذه البيانات:"},
    "suggestion": {"fr": "Graphique en {type} : {quoi}", "en": "{type} of {quoi}", "ar": "رسم {type}: {quoi}"},
    "regroupees": {"fr": "{n} petites catégories regroupées dans « Autres »", "en": "{n} small categories grouped as “Others”",
                   "ar": "تم تجميع {n} فئات صغيرة في «أخرى»"},
    "echantillon": {"fr": "échantillon de {n} points", "en": "sample of {n} points", "ar": "عينة من {n} نقطة"},
    "correlation": {"fr": "corrélation de Pearson : {r}", "en": "Pearson correlation: {r}", "ar": "معامل ارتباط بيرسون: {r}"},
}


def _t(cle: str, langue: str, **kwargs) -> str:
    textes = TEXTES[cle]
    return textes.get(langue, textes["fr"]).format(**kwargs)


def nom_type(t: str, langue: str) -> str:
    return NOMS_TYPES.get(t, {}).get(langue, t)


def _types_compatibles(df: pd.DataFrame, spec: SpecGraphique) -> List[str]:
    """Types alternatifs pertinents pour les mêmes colonnes (proposés en suggestions)."""
    dates = _colonnes_dates(df)
    if spec.type in ("bar", "pie", "donut") and _est_categorie(df, spec.x):
        candidats = ["bar", "pie", "donut"] if df[spec.x].nunique() <= 12 else ["bar"]
        if spec.y:
            candidats.append("box")
    elif spec.type in ("line", "area", "bar") and spec.x in dates:
        candidats = ["line", "area", "bar"]
    elif spec.type in ("bar_groupe", "bar_empile"):
        candidats = ["bar_groupe", "bar_empile"]
    elif spec.type in ("histogram", "box"):
        candidats = ["histogram", "box"]
    else:
        candidats = []
    return [c for c in candidats if c != spec.type]


def _quoi(df: pd.DataFrame, spec: SpecGraphique, langue: str, type_cible: str) -> str:
    """Description re-routable par le moteur, adaptée au type CIBLE (colonnes écrites explicitement)."""
    l = langue if langue in ("fr", "en", "ar") else "fr"
    agg = NOMS_AGG[spec.agg][l].lower()
    par = {"fr": "par", "en": "by", "ar": "حسب"}[l]
    if type_cible == "histogram":                 # distribution d'une seule colonne
        return spec.libelle_mesure()
    if type_cible == "box":                       # distribution, éventuellement par catégorie
        return spec.libelle_mesure() + (f" {par} {spec.x}" if _est_categorie(df, spec.x) else "")
    mesure = "" if spec.agg == "count" else f" {spec.libelle_mesure()}"
    return f"{agg}{mesure} {par} {spec.x}" + (f" {par} {spec.color}" if spec.color else "")


def suggestions_pour_fichier(df: pd.DataFrame, langue: str) -> List[str]:
    """Exemples de graphiques possibles pour ce fichier (quand la demande est trop vague)."""
    l = langue if langue in ("fr", "en", "ar") else "fr"
    numeriques = [c for c in df.columns if stats.est_numerique(df, c) and df[c].nunique() > 20]
    dates = _colonnes_dates(df)
    categories = [c for c in df.columns if _est_categorie(df, c) and 2 <= df[c].nunique() <= 20]
    mesure = numeriques[-1] if numeriques else None
    sorties = []
    if mesure and dates:
        sorties.append(_t("suggestion", l, type=nom_type("line", l), quoi=f"{NOMS_AGG['sum'][l].lower()} {mesure} {({'fr': 'par mois', 'en': 'by month', 'ar': 'حسب الشهر'})[l]}"))
    if mesure and categories:
        sorties.append(_t("suggestion", l, type=nom_type("bar", l), quoi=f"{NOMS_AGG['sum'][l].lower()} {mesure} {({'fr': 'par', 'en': 'by', 'ar': 'حسب'})[l]} {categories[0]}"))
    if len(numeriques) >= 3:
        sorties.append(_t("suggestion", l, type=nom_type("heatmap", l), quoi=", ".join(numeriques[:4])))
    elif mesure:
        sorties.append(_t("suggestion", l, type=nom_type("histogram", l), quoi=mesure))
    return sorties


# ---------------------------------------------------------------------------
# Point d'entrée appelé par services/assistant.py
# ---------------------------------------------------------------------------
@dataclass
class ResultatGraphique:
    texte: str
    figure: Optional[dict] = None          # figure Plotly (dict JSON) à afficher dans le chat
    spec: Optional[dict] = None
    tableau: Optional[list] = None         # données calculées par pandas (pour le PDF)
    suggestions: List[str] = field(default_factory=list)
    demande_precision: bool = False
    temps: dict = field(default_factory=dict)


def generer(df: pd.DataFrame, question: str, langue: str) -> ResultatGraphique:
    t0 = time.time()
    spec = construire_spec(df, question)
    temps = {"spec_s": round(time.time() - t0, 3), "spec_par": spec.source_colonnes}

    if spec.raison == "precision_mesure":
        from services.redaction import message_precision_colonne
        from services.semantique import Resolution
        options = []
        for o in spec.raison_params["options"]:
            s = SpecGraphique(**{**asdict(spec), "y": o["colonne"], "multiplicateur": o["multiplicateur"]})
            options.append({"mesure": s.libelle_mesure(), "valeur": None})
        resolution = Resolution(colonne=None, concept=concept_de(question), note="absent",
                                options_precision=spec.raison_params["options"])
        texte, _ = message_precision_colonne(resolution, stats.PlanStat("sum"), options, langue)
        texte = texte.split("\n\n|")[0]           # pas de tableau de valeurs pour un graphique
        quoi_par = f" {({'fr': 'par', 'en': 'by', 'ar': 'حسب'}).get(langue, 'par')} {spec.x}" if spec.x else ""
        suggestions = [_t("suggestion", langue, type=nom_type(spec.type_demande or "bar", langue),
                          quoi=f"{NOMS_AGG['sum'].get(langue, NOMS_AGG['sum']['fr']).lower()} {o['mesure']}{quoi_par}")
                       for o in options]
        return ResultatGraphique(texte=texte, suggestions=suggestions, demande_precision=True, temps=temps)

    if not spec.type:
        return ResultatGraphique(texte=_t("precision_colonnes", langue), suggestions=suggestions_pour_fichier(df, langue),
                                 demande_precision=True, temps=temps)

    t1 = time.time()
    try:
        fig, tableau, infos = construire_figure(df, spec, langue)
    except stats.ErreurCalcul as e:
        return ResultatGraphique(texte=f"⚠️ {e}", demande_precision=True, temps=temps)
    temps["donnees_et_figure_s"] = round(time.time() - t1, 3)

    # Texte : explication du type + provenance des données
    lignes = []
    if spec.incompatibilite:
        lignes.append(_t(spec.incompatibilite, langue, demande=nom_type(spec.type_demande, langue), x=spec.x or "-")
                      + " " + _t("remplace", langue, type=nom_type(spec.type, langue)))
    if spec.raison == "demande":
        lignes.append(_t("demande", langue, type=nom_type(spec.type, langue)))
    elif spec.raison:
        lignes.append(_t(spec.raison, langue, **{"x": spec.x, "color": spec.color, "n": "-", **spec.raison_params}))
    detail = [titre(spec, langue)]
    if infos.get("categories_regroupees"):
        detail.append(_t("regroupees", langue, n=infos["categories_regroupees"]))
    if infos.get("echantillon"):
        detail.append(_t("echantillon", langue, n=infos["echantillon"]))
    if "correlation" in infos:
        detail.append(_t("correlation", langue, r=formater_nombre(infos["correlation"], langue)))
    lignes.append(_t("provenance", langue, detail=" · ".join(detail),
                     u=formater_nombre(infos["nb_lignes_utilisees"], langue), t=formater_nombre(infos["nb_lignes_total"], langue)))

    suggestions = [_t("suggestion", langue, type=nom_type(t, langue), quoi=_quoi(df, spec, langue, t))
                   for t in _types_compatibles(df, spec)]
    if suggestions:
        lignes.append(_t("autres_types", langue))

    temps["total_s"] = round(time.time() - t0, 3)
    figure = json.loads(pio.to_json(fig))
    temps["taille_json_ko"] = round(len(json.dumps(figure)) / 1024, 1)
    tableau_json = json.loads(tableau.to_json(orient="records", date_format="iso")) if tableau is not None else None
    return ResultatGraphique(texte="\n\n".join(lignes), figure=figure, spec=asdict(spec),
                             tableau=tableau_json, suggestions=suggestions, temps=temps)


# ---------------------------------------------------------------------------
# Historique : graphiques enregistrés et ancien format
# ---------------------------------------------------------------------------
# Ancien format (avant la Phase 4) : JSON écrit par le LLM dans le texte de la réponse,
# avec des valeurs inventées. Ex. {"type_graph": "pie", "data": {"x": ["Bizerte", "Sousse"], ...}}
_RE_ANCIEN_FORMAT = re.compile(r"(```(?:json)?\s*)?\{[^{}]*\"type_graph\"[\s\S]*?\}\s*\}(\s*```)?")


def nettoyer_ancien_format(texte: str) -> tuple:
    """Retire le JSON de graphique de l'ancien format. Retourne (texte nettoyé, True si présent)."""
    if '"type_graph"' not in texte:
        return texte, False
    return _RE_ANCIEN_FORMAT.sub("", texte).strip(), True


def figures_des_questions(ids_questions: List[int]) -> dict:
    """{id_question: [figure Plotly, ...]} pour réafficher les graphiques de l'historique."""
    if not ids_questions:
        return {}
    from services.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    marques = ", ".join(["%s"] * len(ids_questions))
    cur.execute(f"SELECT id_question, chemin_json FROM graphiques WHERE id_question IN ({marques}) "
                f"ORDER BY id_graphique", tuple(ids_questions))
    lignes = cur.fetchall()
    cur.close()
    conn.close()
    figures: dict = {}
    for l in lignes:
        chemin = os.path.join(config.BASE_DIR, l["chemin_json"])
        try:
            with open(chemin, encoding="utf-8") as f:
                figures.setdefault(l["id_question"], []).append(json.load(f))
        except OSError:
            log.warning("Figure introuvable : %s", chemin)
    return figures


# ---------------------------------------------------------------------------
# Enregistrement : JSON immédiat + PNG en arrière-plan (kaleido + Chrome installé)
# ---------------------------------------------------------------------------
_executeur = ThreadPoolExecutor(max_workers=1, thread_name_prefix="export-png")  # un seul Chrome, exports en file
_kaleido_pret = threading.Event()
TEMPS_PNG: list = []                       # durées mesurées (rapport de performances)


def _demarrer_kaleido():
    """Démarre UNE fois un Chrome persistant (1er export ~4,6 s, puis ~0,3 s au lieu de ~4 s chacun)."""
    if _kaleido_pret.is_set():
        return
    if config.CHROME_PATH:
        os.environ["BROWSER_PATH"] = config.CHROME_PATH      # Chrome de la machine, pas de téléchargement
    import kaleido
    kaleido.start_sync_server(silence_warnings=True)
    _kaleido_pret.set()


def prechauffer_export():
    """Lance Chrome en arrière-plan au démarrage de Flask (le 1er PNG ne paie pas le démarrage)."""
    def _tache():
        try:
            _demarrer_kaleido()
            exporter_png(go.Figure(go.Bar(x=["a"], y=[1])), None)
            log.info("Export PNG préchauffé (Chrome : %s)", config.CHROME_PATH or "détection automatique")
        except Exception as e:
            log.warning("Export PNG indisponible : %s", e)
    _executeur.submit(_tache)


def exporter_png(figure, chemin: Optional[str], largeur: int = 1000, hauteur: int = 560) -> Optional[bytes]:
    """Export PNG synchrone (utilisé par le thread d'arrière-plan et par le PDF en Phase 8)."""
    _demarrer_kaleido()
    fig = figure if isinstance(figure, go.Figure) else go.Figure(figure)
    debut = time.time()
    png = pio.to_image(fig, format="png", width=largeur, height=hauteur, scale=2)
    TEMPS_PNG.append(round(time.time() - debut, 3))
    if chemin:
        with open(chemin, "wb") as f:
            f.write(png)
    return png


def enregistrer(resultat: ResultatGraphique, id_utilisateur: int, id_fichier: Optional[int],
                id_question: Optional[int], source: str = "chat") -> Optional[int]:
    """Enregistre la figure (JSON tout de suite, PNG en arrière-plan) et la ligne `graphiques`."""
    if not resultat.figure:
        return None
    from services.db import get_db_connection
    dossier = os.path.join(config.GRAPH_FOLDER, f"U{id_utilisateur}")
    os.makedirs(dossier, exist_ok=True)
    base = f"{datetime.datetime.now():%Y%m%d_%H%M%S_%f}_{resultat.spec['type']}"
    chemin_json = os.path.join(dossier, base + ".json")
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(resultat.figure, f, ensure_ascii=False)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO graphiques (id_utilisateur, id_question, id_fichier, source, type_graphique, titre,
                   spec_json, chemin_json) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (id_utilisateur, id_question, id_fichier, source, resultat.spec["type"],
                 resultat.figure.get("layout", {}).get("title", {}).get("text", "")[:255],
                 json.dumps(resultat.spec, ensure_ascii=False, default=str),
                 os.path.relpath(chemin_json, config.BASE_DIR)))
    id_graphique = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()

    def _png():
        try:
            chemin_png = os.path.join(dossier, base + ".png")
            exporter_png(resultat.figure, chemin_png)
            c = get_db_connection()
            k = c.cursor()
            k.execute("UPDATE graphiques SET chemin_png = %s WHERE id_graphique = %s",
                      (os.path.relpath(chemin_png, config.BASE_DIR), id_graphique))
            c.commit()
            k.close()
            c.close()
        except Exception as e:      # le PNG pourra être régénéré depuis le JSON (Phase 8)
            log.warning("Export PNG du graphique %s impossible : %s", id_graphique, e)
    _executeur.submit(_png)
    return id_graphique

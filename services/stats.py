"""
services/stats.py — Calculs statistiques exécutés par pandas (jamais par le LLM).

Le LLM ne fait que CHOISIR une opération dans une liste fermée et les colonnes
concernées (le « plan »). Ce module exécute le plan avec pandas : le résultat est
exact, identique à chaque exécution et quelle que soit la langue de la question.

Aucune exécution de code généré (pas d'eval / exec) : chaque opération est une
fonction Python écrite à l'avance.

Opérations autorisées : sum, mean, median, count, min, max, top, groupby, trend, percentage.
"""

import re
import warnings
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

OPERATIONS = ["sum", "mean", "median", "count", "min", "max", "top", "groupby", "trend", "percentage"]
AGREGATIONS = ["sum", "mean", "median", "count", "min", "max"]
OPERATEURS_FILTRE = ["==", "!=", ">", ">=", "<", "<=", "contient", "annee", "mois"]
PERIODES = {"jour": "D", "semaine": "W", "mois": "M", "trimestre": "Q", "annee": "Y"}
MAX_LIGNES_TABLEAU = 20


class ErreurCalcul(ValueError):
    """Plan impossible à exécuter (colonne non numérique, date illisible, ...)."""


@dataclass
class Filtre:
    colonne: str
    operateur: str
    valeur: str


@dataclass
class PlanStat:
    """Plan de calcul validé (produit par services/router.py)."""
    operation: str
    colonne: Optional[str] = None                 # colonne mesurée (numérique)
    colonne_multiplicateur: Optional[str] = None  # si renseignée : colonne × colonne_multiplicateur
    colonne_groupe: Optional[str] = None          # regroupement (groupby, top, percentage)
    colonne_date: Optional[str] = None            # pour trend
    agregation: str = "sum"                       # agrégation pour groupby / top / trend
    n: int = 5                                    # pour top
    ordre: str = "desc"
    periode: str = "mois"
    filtres: List[Filtre] = field(default_factory=list)
    liste: bool = False                           # count par valeur demandé comme « liste des valeurs »

    def libelle_mesure(self) -> str:
        """Nom lisible de la mesure : `price` ou `price × stock_quantity`."""
        if self.colonne and self.colonne_multiplicateur:
            return f"{self.colonne} × {self.colonne_multiplicateur}"
        return self.colonne or "lignes"


@dataclass
class ResultatStat:
    """Résultat d'un calcul : valeur scalaire et/ou tableau + traçabilité."""
    operation: str
    mesure: str
    valeur: Optional[float] = None
    tableau: Optional[pd.DataFrame] = None
    nb_lignes_total: int = 0
    nb_lignes_utilisees: int = 0
    nb_valeurs_ignorees: int = 0                   # valeurs non numériques / manquantes écartées
    details: dict = field(default_factory=dict)    # infos spécifiques (ligne du min, variation...)

    def nombres(self) -> List[float]:
        """Tous les nombres du résultat (sert à vérifier la reformulation du LLM)."""
        valeurs = [self.valeur] if self.valeur is not None else []
        valeurs += [self.nb_lignes_total, self.nb_lignes_utilisees, self.nb_valeurs_ignorees]
        valeurs += [v for v in self.details.values() if isinstance(v, (int, float, np.number))]
        if self.tableau is not None:
            for col in self.tableau.select_dtypes(include="number").columns:
                valeurs += self.tableau[col].tolist()
        return [float(v) for v in valeurs if v is not None and not pd.isna(v)]


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def en_numerique(serie: pd.Series) -> pd.Series:
    """Convertit en nombres (gère '1 200,50', '1,200.50', '12%', '100 DT')."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float)
    texte = serie.astype(str).str.strip()
    # Seules les valeurs qui ont la FORME d'un nombre sont converties (unité/devise
    # facultative avant ou après) : « INV-10001 » ou « Rue 12 » ne sont pas des nombres.
    forme_nombre = texte.str.match(_RE_NOMBRE)
    texte = texte.where(forme_nombre, "").str.replace(r"[^\d,.\-]", "", regex=True)
    return pd.to_numeric(texte.map(_normaliser_separateurs), errors="coerce")


def _normaliser_separateurs(texte: str) -> str:
    """'1.234,56' / '1,234.56' / '1 234,5' / '12,5' -> notation Python '1234.56', '12.5'."""
    if "," in texte and "." in texte:
        # le DERNIER séparateur est le décimal, l'autre sépare les milliers
        if texte.rfind(",") > texte.rfind("."):
            return texte.replace(".", "").replace(",", ".")
        return texte.replace(",", "")
    if "," in texte:
        # « 1,200 » (milliers anglais) si exactement 3 chiffres après chaque virgule, sinon décimal
        return texte.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", texte) else texte.replace(",", ".")
    return texte


_RE_NOMBRE = re.compile(r"^\s*[€$£]?\s*[-+]?\d[\d\s.,]*\s*(%|[A-Za-z€$£.]{1,4}|دينار|د\.ت)?\s*$")
_RE_DATE = re.compile(r"^\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})([ T]\d{1,2}:\d{2}(:\d{2})?)?\s*$")


def _ressemble_a_des_dates(serie: pd.Series) -> bool:
    """Pré-filtre rapide : 80 % des valeurs ont-elles une forme de date (2024-11-07, 07/11/2024) ?"""
    echantillon = serie.dropna().astype(str).head(50)
    return len(echantillon) > 0 and echantillon.str.match(_RE_DATE).mean() >= 0.8


def en_dates(serie: pd.Series) -> pd.Series:
    """Convertit en dates ; lève ErreurCalcul si moins de 80 % des valeurs sont lisibles."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    with warnings.catch_warnings():          # avertissement pandas « format non déduit » sans intérêt ici
        warnings.simplefilter("ignore", UserWarning)
        dates = pd.to_datetime(serie, errors="coerce", dayfirst=False)
        if dates.notna().mean() < 0.8:
            dates = pd.to_datetime(serie, errors="coerce", dayfirst=True)
    if dates.notna().mean() < 0.8:
        raise ErreurCalcul(f"La colonne « {serie.name} » ne contient pas des dates lisibles.")
    return dates


def est_numerique(df: pd.DataFrame, colonne: str) -> bool:
    """Vrai si au moins 80 % des valeurs non vides se convertissent en nombre."""
    serie = df[colonne].dropna()
    return len(serie) > 0 and en_numerique(serie).notna().mean() >= 0.8


def est_date(df: pd.DataFrame, colonne: str) -> bool:
    if pd.api.types.is_datetime64_any_dtype(df[colonne]):
        return True
    if pd.api.types.is_numeric_dtype(df[colonne]) or not _ressemble_a_des_dates(df[colonne]):
        return False
    try:
        en_dates(df[colonne].dropna().head(200))
        return True
    except ErreurCalcul:
        return False


def appliquer_filtres(df: pd.DataFrame, filtres: List[Filtre]) -> pd.DataFrame:
    """Filtre les lignes (comparaisons insensibles à la casse pour le texte)."""
    for f in filtres:
        if f.operateur not in OPERATEURS_FILTRE:
            raise ErreurCalcul(f"Opérateur de filtre non autorisé : {f.operateur}")
        col = df[f.colonne]
        if f.operateur in ("annee", "mois"):
            dates = en_dates(col)
            partie = dates.dt.year if f.operateur == "annee" else dates.dt.month
            masque = partie == int(float(f.valeur))
        elif f.operateur == "contient":
            masque = col.astype(str).str.contains(str(f.valeur), case=False, regex=False, na=False)
        elif f.operateur in ("==", "!="):
            if est_numerique(df, f.colonne) and en_numerique(pd.Series([f.valeur])).notna().all():
                egal = en_numerique(col) == float(en_numerique(pd.Series([f.valeur]))[0])
            else:
                egal = col.astype(str).str.strip().str.casefold() == str(f.valeur).strip().casefold()
            masque = egal if f.operateur == "==" else ~egal
        else:
            valeur = en_numerique(pd.Series([f.valeur]))[0]
            if pd.isna(valeur):
                raise ErreurCalcul(f"Valeur numérique attendue pour le filtre {f.colonne} {f.operateur} {f.valeur}")
            num = en_numerique(col)
            masque = {">": num > valeur, ">=": num >= valeur, "<": num < valeur, "<=": num <= valeur}[f.operateur]
        df = df[masque.fillna(False)]
    return df


def _mesure(df: pd.DataFrame, plan: PlanStat) -> pd.Series:
    """Série mesurée : colonne, ou produit de deux colonnes (ex. prix × quantité)."""
    serie = en_numerique(df[plan.colonne])
    if plan.colonne_multiplicateur:
        serie = serie * en_numerique(df[plan.colonne_multiplicateur])
    return serie


def _agreger(groupes, agregation: str) -> pd.Series:
    if agregation not in AGREGATIONS:
        raise ErreurCalcul(f"Agrégation non autorisée : {agregation}")
    return getattr(groupes, agregation)()


# ---------------------------------------------------------------------------
# Exécution du plan
# ---------------------------------------------------------------------------
def executer(df: pd.DataFrame, plan: PlanStat) -> ResultatStat:
    """Exécute un plan validé. Toutes les valeurs du résultat viennent de pandas."""
    if plan.operation not in OPERATIONS:
        raise ErreurCalcul(f"Opération non autorisée : {plan.operation}")

    total = len(df)
    df = appliquer_filtres(df, plan.filtres)
    res = ResultatStat(operation=plan.operation, mesure=plan.libelle_mesure(),
                       nb_lignes_total=total, nb_lignes_utilisees=len(df))
    op = plan.operation

    # --- count : nombre de lignes (après filtres), éventuellement par groupe
    if op == "count":
        if plan.colonne_groupe:
            t = df[plan.colonne_groupe].value_counts(dropna=False).rename_axis(plan.colonne_groupe)
            res.tableau = t.reset_index(name="nombre").head(MAX_LIGNES_TABLEAU)
            res.details["nb_groupes"] = int(t.shape[0])
        res.valeur = float(len(df))
        res.mesure = "lignes"
        return res

    if not plan.colonne:
        raise ErreurCalcul("Aucune colonne numérique choisie pour le calcul.")
    mesure = _mesure(df, plan)
    res.nb_valeurs_ignorees = int(mesure.isna().sum())
    valides = mesure.dropna()

    # --- agrégats simples
    if op in ("sum", "mean", "median", "min", "max"):
        if valides.empty:
            raise ErreurCalcul("Aucune valeur numérique exploitable après filtrage.")
        res.valeur = float(getattr(valides, op)())
        if op in ("min", "max"):
            # Ligne correspondante (ex. le produit le plus cher)
            ligne = df.loc[valides.idxmin() if op == "min" else valides.idxmax()]
            res.tableau = ligne.to_frame().T.reset_index(drop=True)
        return res

    # --- groupby / top / percentage : regroupement par une colonne catégorielle
    if op in ("groupby", "top", "percentage"):
        if not plan.colonne_groupe:
            if op == "top":   # top N lignes selon la mesure
                ordre = valides.sort_values(ascending=(plan.ordre == "asc")).head(plan.n)
                t = df.loc[ordre.index].copy()
                t[res.mesure] = ordre
                res.tableau = t.reset_index(drop=True)
                return res
            raise ErreurCalcul("Une colonne de regroupement est nécessaire.")
        agg = "sum" if op == "percentage" else plan.agregation
        t = _agreger(valides.groupby(df.loc[valides.index, plan.colonne_groupe]), agg)
        t = t.sort_values(ascending=(plan.ordre == "asc"))
        res.details["nb_groupes"] = int(t.shape[0])
        if op == "percentage":
            somme = t.sum()
            res.valeur = float(somme)
            tableau = pd.DataFrame({plan.colonne_groupe: t.index, res.mesure: t.values,
                                    "pourcentage": (t.values / somme * 100) if somme else np.nan})
        else:
            if op == "top":
                t = t.head(plan.n)
            tableau = pd.DataFrame({plan.colonne_groupe: t.index, f"{agg}({res.mesure})": t.values})
        res.tableau = tableau.head(MAX_LIGNES_TABLEAU).reset_index(drop=True)
        return res

    # --- trend : évolution dans le temps
    if op == "trend":
        if not plan.colonne_date:
            raise ErreurCalcul("Aucune colonne de date pour calculer une évolution.")
        dates = en_dates(df[plan.colonne_date])
        serie = pd.Series(mesure.values, index=dates.values).dropna()
        serie = serie[serie.index.notna()]
        if serie.empty:
            raise ErreurCalcul("Aucune valeur datée exploitable.")
        freq = PERIODES.get(plan.periode, "M")
        alias = {"M": "ME", "Q": "QE", "Y": "YE"}.get(freq, freq)   # alias pandas ≥ 2.2
        t = _agreger(serie.resample(alias), plan.agregation)
        etiquettes = t.index.to_period(freq).astype(str)
        res.tableau = pd.DataFrame({"période": etiquettes, f"{plan.agregation}({res.mesure})": t.values})
        premiere, derniere = float(t.iloc[0]), float(t.iloc[-1])
        res.details.update({"premiere_valeur": premiere, "derniere_valeur": derniere,
                            "nb_periodes": int(len(t))})
        if premiere:
            res.details["variation_pct"] = (derniere - premiere) / abs(premiere) * 100
        res.details["premiere_periode"] = etiquettes[0]
        res.details["derniere_periode"] = etiquettes[-1]
        res.valeur = float(t.sum()) if plan.agregation == "sum" else None
        if len(res.tableau) > MAX_LIGNES_TABLEAU:
            res.tableau = res.tableau.tail(MAX_LIGNES_TABLEAU).reset_index(drop=True)
            res.details["periodes_tronquees"] = True
        return res

    raise ErreurCalcul(f"Opération non gérée : {op}")

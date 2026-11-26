"""
services/apercu.py — Aperçu d'un fichier après l'upload (Phase 7).

Après l'upload : AUCUN graphique ni prédiction automatique. On montre seulement :
  - les premières lignes, les colonnes détectées et leur type (nombre / date / texte) ;
  - 3 à 4 questions suggérées CLIQUABLES, adaptées au fichier ET au domaine de
    l'utilisateur (un modèle n'est suggéré que s'il est disponible pour son domaine
    et que le fichier contient les colonnes nécessaires).
"""

import math
from typing import List

import pandas as pd

from services import stats
from services.fichiers import chemin_absolu
from services.ml import registry
from services.parsers import analyser_fichier
from services.semantique import colonnes_du_concept


def _type(df: pd.DataFrame, c: str) -> str:
    if stats.est_date(df, c):
        return "date"
    if stats.est_numerique(df, c):
        return "nombre"
    return "texte"


def _json(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    if hasattr(v, "item"):
        return v.item()
    return v


def questions_suggerees(df: pd.DataFrame, domaine: str) -> List[str]:
    from services.charts import _est_identifiant
    types = {c: _type(df, c) for c in df.columns}
    dates = [c for c, t in types.items() if t == "date"]
    categories = [c for c, t in types.items() if t == "texte" and 2 <= df[c].nunique() <= 30 and not _est_identifiant(df, c)]
    ventes = colonnes_du_concept(df, "ventes")
    numeriques = [c for c, t in types.items() if t == "nombre" and not _est_identifiant(df, c)]
    mesure = ventes[0] if ventes else (numeriques[-1] if numeriques else None)
    q: List[str] = []
    if ventes:
        q.append("Quel est le chiffre d'affaires total ?")
    elif mesure:
        q.append(f"Quel est le total de {mesure} ?")
    if mesure and categories:
        q.append(f"Affiche un graphique de {mesure} par {categories[0]}")
    if mesure and dates and registry.est_disponible("forecast", domaine):
        q.append("Affiche l'évolution du chiffre d'affaires par mois" if ventes else f"Affiche l'évolution de {mesure} par mois")
        q.append("Prévois le chiffre d'affaires des 6 prochains mois" if ventes else f"Prévois {mesure} des 6 prochains mois")
    if registry.est_disponible("churn", domaine):
        from services.ml.churn_banque import ModeleChurnIndisponible, charger, correspondance_colonnes
        try:
            _, meta = charger()
            if not correspondance_colonnes(df, meta["features_entree"])[1]:
                q.insert(0, "Quels clients risquent de partir ?")
        except ModeleChurnIndisponible:
            pass
    if len(numeriques) >= 2 and registry.est_disponible("anomaly", domaine):
        q.append("Détecte les anomalies")
    if mesure and categories and len(q) < 4:
        q.append(f"Quels sont les 3 {categories[0]} avec le plus de {mesure} ?")
    vus, resultat = set(), []
    for x in q:
        if x not in vus:
            vus.add(x)
            resultat.append(x)
    return resultat[:4]


def apercu_fichier(fichier: dict, domaine: str, nb_lignes: int = 5) -> dict:
    res = analyser_fichier(chemin_absolu(fichier["chemin_fichier"]))
    df = res.principal
    remarques = list(res.remarques)
    if len(res.tables) > 1:
        remarques.append("Tableaux détectés : " + ", ".join(f"{n} ({len(d)} lignes)" for n, d in res.tables)
                         + ". Le tableau le plus pertinent est choisi selon chaque question.")
    return {
        "nb_lignes": int(len(df)), "nb_colonnes": int(df.shape[1]),
        "colonnes": [{"nom": str(c), "type": _type(df, c)} for c in df.columns],
        "lignes": [{str(k): _json(v) for k, v in l.items()} for l in df.head(nb_lignes).to_dict(orient="records")],
        "questions_suggerees": questions_suggerees(df, domaine),
        "source": res.source, "remarques": remarques, "duree_analyse_s": res.duree_s,
        "tables": [{"nom": n, "lignes": int(len(d)), "colonnes": [str(c) for c in d.columns]} for n, d in res.tables],
    }

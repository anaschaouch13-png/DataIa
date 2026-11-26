"""
services/ml/simulateur.py — Simulateur « what-if » (Phase 6).

Pour chaque modèle du registre, deux fonctions :
  - champs_<modele>(df)  : description du formulaire (généré automatiquement) ;
  - simuler_<modele>(...) : exécution sur les valeurs saisies.

Les modèles d'anomalies entraînés sur un fichier sont gardés en mémoire (cache limité)
pour qu'une simulation prenne quelques millisecondes au lieu de réentraîner à chaque clic.
Chaque simulation est enregistrée dans la table `simulations` (services/ml/simulateur.enregistrer).
"""

import json
import threading
from collections import OrderedDict
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from services import stats
from services.ml import anomalies, churn_banque, forecast
from services.semantique import colonnes_du_concept

_cache_anomalies: "OrderedDict[str, anomalies.ModeleAnomalies]" = OrderedDict()
_verrou = threading.Lock()
TAILLE_CACHE = 8


def _numeriques(df: pd.DataFrame) -> list:
    from services.charts import _est_identifiant
    return [c for c in df.columns if stats.est_numerique(df, c) and not stats.est_date(df, c) and not _est_identifiant(df, c)]


# ---------------------------------------------------------------------------
# Prévision du CA : choix de la colonne et de l'horizon (1 à 12)
# ---------------------------------------------------------------------------
def champs_prevision(df: Optional[pd.DataFrame]) -> list:
    if df is None:
        return []
    numeriques = _numeriques(df)
    if not any(stats.est_date(df, c) for c in df.columns) or not numeriques:
        return []
    defaut = next(iter(colonnes_du_concept(df, "ventes")), numeriques[0])
    return [{"nom": "colonne", "type": "liste", "options": numeriques, "defaut": defaut,
             "libelle": "Colonne à prévoir"},
            {"nom": "horizon", "type": "curseur", "min": 1, "max": 12, "pas": 1, "defaut": 6,
             "libelle": "Horizon (périodes)"}]


def simuler_prevision(df: pd.DataFrame, entrees: dict, **_) -> dict:
    horizon = int(max(1, min(12, int(entrees.get("horizon", 6)))))
    res = forecast.prevoir(df, horizon=horizon, colonne_cible=entrees.get("colonne"))
    m = res.metriques
    fig = forecast.figure(res)
    fig.update_layout(height=260, margin={"l": 40, "r": 10, "t": 40, "b": 30}, showlegend=False,
                      title={"text": f"{res.colonne_cible} — {res.modele_retenu}", "font": {"size": 12}})
    p = res.previsions
    return {"modele": res.modele_retenu, "frequence": res.frequence, "critere": res.critere,
            "mape": round(m["mape"], 2), "precision": round(max(0.0, 100 - m[res.critere]), 2),
            "valeur_prevue": round(float(p["prevision"].iloc[0]), 2),
            "periode_prevue": p["periode"].iloc[0].strftime("%Y-%m-%d"),
            "total_horizon": round(float(p["prevision"].sum()), 2),
            "previsions": [{"periode": d.strftime("%Y-%m-%d"), "prevision": round(float(v), 2),
                            "basse": round(float(b), 2), "haute": round(float(h), 2)}
                           for d, v, b, h in zip(p["periode"], p["prevision"], p["borne_basse"], p["borne_haute"])],
            "figure": json.loads(pio.to_json(fig))}


# ---------------------------------------------------------------------------
# Anomalies : saisie d'une transaction
# ---------------------------------------------------------------------------
def _modele_anomalies(cle_fichier: str, df: pd.DataFrame) -> anomalies.ModeleAnomalies:
    with _verrou:
        if cle_fichier in _cache_anomalies:
            _cache_anomalies.move_to_end(cle_fichier)
            return _cache_anomalies[cle_fichier]
    colonnes, coherence = anomalies.choisir_colonnes(df)
    propre = df.copy()
    for c in colonnes:
        propre[c] = stats.en_numerique(propre[c])
    modele = anomalies.entrainer(propre, colonnes, coherence)
    with _verrou:
        _cache_anomalies[cle_fichier] = modele
        while len(_cache_anomalies) > TAILLE_CACHE:
            _cache_anomalies.popitem(last=False)
    return modele


def champs_anomalie(df: Optional[pd.DataFrame], cle_fichier: str = "") -> list:
    if df is None:
        return []
    try:
        modele = _modele_anomalies(cle_fichier, df)
    except ValueError:
        return []
    champs = [{"nom": c, "type": "nombre", "defaut": round(float(modele.medianes[c]), 2), "pas": 0.01,
               "libelle": c} for c in modele.colonnes]
    if modele.coherence and modele.coherence.get("remise"):
        champs.append({"nom": modele.coherence["remise"], "type": "nombre", "defaut": 0, "pas": 1,
                       "libelle": modele.coherence["remise"]})
    return champs


def simuler_anomalie(df: pd.DataFrame, entrees: dict, cle_fichier: str = "", **_) -> dict:
    modele = _modele_anomalies(cle_fichier, df)
    valeurs = {k: float(v) for k, v in entrees.items() if v not in (None, "")}
    r = anomalies.evaluer_transaction(modele, valeurs)
    r["anomalie"] = bool(r["anomalie"])
    r["verdict"] = "Anormale" if r["anomalie"] else "Normale"
    # Position du score parmi les transactions du fichier (lecture intuitive)
    scores = modele.scores(df)
    r["percentile"] = round(float((scores < r["score"]).mean() * 100), 1)
    return r


# ---------------------------------------------------------------------------
# Churn (Banque) : formulaire généré à partir des features du modèle
# ---------------------------------------------------------------------------
def champs_churn(df: Optional[pd.DataFrame] = None, **_) -> list:
    try:
        return churn_banque.champs_formulaire()
    except churn_banque.ModeleChurnIndisponible:
        return []


def simuler_churn(df: Optional[pd.DataFrame], entrees: dict, **_) -> dict:
    r = churn_banque.predire_client(entrees)
    r["pourcentage"] = round(r["probabilite_depart"] * 100, 1)
    return r


CHAMPS = {"forecast": champs_prevision, "anomaly": champs_anomalie, "churn": champs_churn}
BESOIN_FICHIER = {"forecast": True, "anomaly": True, "churn": False}


def enregistrer(id_utilisateur: int, type_modele: str, entrees: dict, resultat: dict) -> int:
    from services.db import get_db_connection
    stockable = {k: v for k, v in resultat.items() if k != "figure"}          # la figure se régénère
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO simulations (id_utilisateur, type_modele, entrees_json, resultat_json) VALUES (%s,%s,%s,%s)",
                (id_utilisateur, type_modele, json.dumps(entrees, ensure_ascii=False, default=str),
                 json.dumps(stockable, ensure_ascii=False, default=lambda o: o.item() if isinstance(o, np.generic) else str(o))))
    id_simulation = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return id_simulation

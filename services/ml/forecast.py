"""
services/ml/forecast.py — Prévision du chiffre d'affaires (Phase 5.2).

Étapes :
  1. Colonnes : date détectée automatiquement ; cible = concept « ventes / CA » (même
     résolution que la Phase 3 : chiffre_affaires, Total_Price...). La question peut
     corriger (« prévision de la colonne marge »).
  2. Nettoyage traçable (dates, nombres, manquants, doublons) -> export CSV/Excel.
  3. Agrégation : somme par période. Fréquence automatique selon l'historique
     (≥ 2 ans -> mois, ≥ 6 mois -> semaine, sinon jour) ou précisée dans la question.
  4. SPLIT TEMPOREL : les dernières périodes servent de test (jamais de split aléatoire :
     on ne prédit pas le passé avec le futur).
  5. Deux modèles candidats :
       - Prophet (tendance + saisonnalité, intervalle de confiance natif) ;
       - LightGBM (arbres boostés) avec features : retards (lags), moyenne mobile,
         mois / jour de semaine, indice de temps. Prévision RÉCURSIVE (chaque valeur
         prévue sert de retard pour la suivante), sur le test comme sur le futur.
     + une référence naïve (« même valeur qu'il y a un an / la période précédente »).
  6. Métriques sur le test : MAE, RMSE, MAPE (+ sMAPE si des valeurs proches de 0).
     Le modèle au MAPE le plus faible est retenu, puis réentraîné sur tout l'historique.
  7. Sortie : courbe historique + prévision + intervalle, « Précision : X % (MAPE = Y %) ».
"""

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import config
from services import stats
from services.ml import nettoyage
from services.semantique import colonnes_citees, colonnes_du_concept, normaliser, resoudre_mesure

log = logging.getLogger("dataia.ml.prevision")
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

# Semaine étiquetée par son DIMANCHE (fin de semaine) : permet de savoir si elle est complète
FREQUENCES = {"mois": ("MS", "mois"), "semaine": ("W-SUN", "semaines"), "jour": ("D", "jours")}
NIVEAU_CONFIANCE = 0.95


class HistoriqueInsuffisant(ValueError):
    pass


@dataclass
class ResultatPrevision:
    colonne_date: str
    colonne_cible: str
    frequence: str
    nb_periodes: int
    nb_test: int
    comparaison: List[dict]                 # métriques de chaque modèle sur le test
    modele_retenu: str
    critere: str                            # MAPE ou sMAPE
    previsions: pd.DataFrame                # periode, prevision, borne_basse, borne_haute
    historique: pd.Series
    test_predictions: dict = field(default_factory=dict)
    df_nettoye: Optional[pd.DataFrame] = None
    rapport: Optional[nettoyage.RapportNettoyage] = None
    temps: dict = field(default_factory=dict)

    @property
    def metriques(self) -> dict:
        return next(m for m in self.comparaison if m["modele"] == self.modele_retenu)


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------
def calculer_metriques(reel: np.ndarray, prevu: np.ndarray) -> dict:
    reel, prevu = np.asarray(reel, float), np.asarray(prevu, float)
    erreur = prevu - reel
    non_nuls = np.abs(reel) > 1e-9
    mape = float(np.mean(np.abs(erreur[non_nuls] / reel[non_nuls])) * 100) if non_nuls.any() else math.inf
    denom = (np.abs(reel) + np.abs(prevu)) / 2
    smape = float(np.mean(np.where(denom > 0, np.abs(erreur) / denom, 0)) * 100)
    return {"mae": float(np.mean(np.abs(erreur))), "rmse": float(np.sqrt(np.mean(erreur ** 2))),
            "mape": mape, "smape": smape}


# ---------------------------------------------------------------------------
# Préparation
# ---------------------------------------------------------------------------
def choisir_colonnes(df: pd.DataFrame, question: str) -> tuple:
    dates = [c for c in df.columns if stats.est_date(df, c)]
    citees = colonnes_citees(question, [str(c) for c in df.columns])
    date = next((c for c in citees if c in dates), dates[0] if dates else None)
    if not date:
        raise HistoriqueInsuffisant("Aucune colonne de dates dans ce fichier : une prévision dans le temps est impossible.")
    resolution = resoudre_mesure(df, question, None)
    cible = resolution.colonne
    if not cible:
        candidates = colonnes_du_concept(df, "ventes")
        cible = candidates[0] if candidates else None
    if not cible:
        raise HistoriqueInsuffisant("Je n'ai pas trouvé de colonne de chiffre d'affaires ; précisez la colonne à prévoir "
                                    "(ex. « prévision de la colonne montant »).")
    return date, cible


def frequence_demandee(question: str) -> Optional[str]:
    q = normaliser(question)
    for freq, motif in (("mois", r"mensuel|par mois|mois prochains?|monthly|months?|شهر"),
                        ("semaine", r"hebdo|par semaine|semaines?|weekly|weeks?|أسبوع"),
                        ("jour", r"quotidien|par jour|jours?|daily|days?|يوم")):
        if re.search(motif, q):
            return freq
    return None


def horizon_demande(question: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,2})\s*(?:prochains?|derniers?|next)?\s*(?:mois|semaines?|jours?|months?|weeks?|days?|periodes?)",
                  normaliser(question))
    return max(1, min(int(m.group(1)), 24)) if m else None


def preparer(df: pd.DataFrame, date: str, cible: str, source: str):
    rapport = nettoyage.commencer(df, "prévision du chiffre d'affaires", source)
    propre = df[[date, cible]].copy()
    rapport.ajouter(f"Colonnes utilisées : date = « {date} », cible = « {cible} » ({df.shape[1] - 2} autres colonnes ignorées).")
    propre = nettoyage.convertir_date(propre, date, rapport)
    propre = nettoyage.convertir_numeriques(propre, [cible], rapport)
    propre = nettoyage.traiter_manquants(propre, rapport, numeriques=[], obligatoires=[date, cible])
    if config.PREVISION_EXCLURE_ABERRANTS:
        # Une vente isolée énorme (ex. 106 549 alors que le maximum normal est 9 898) ferait croire
        # au modèle à un pic de CA qui ne se reproduira pas. Seuil prudent : Q3 + 5 × IQR (une
        # « valeur extrême » classique est Q3 + 1,5 × IQR) -> seules les valeurs vraiment aberrantes.
        q1, q3 = propre[cible].quantile([0.25, 0.75])
        seuil = q3 + 5 * (q3 - q1)
        masque = (propre[cible] < 0) | (propre[cible] > seuil)
        if masque.any():
            exclues = propre[masque]
            rapport.ajouter(
                f"{int(masque.sum())} ligne(s) exclue(s) de l'apprentissage : {int((exclues[cible] < 0).sum())} "
                f"valeur(s) négative(s) et {int((exclues[cible] > seuil).sum())} valeur(s) > {seuil:,.0f} "
                f"(Q3 + 5×IQR) — valeurs : {sorted(round(v, 2) for v in exclues[cible])}. Elles restent visibles "
                "avec la détection d'anomalies.".replace(",", " "))
            propre = propre[~masque]
        else:
            rapport.ajouter(f"Aucune valeur négative ni aberrante (> Q3 + 5×IQR = {seuil:,.0f}).".replace(",", " "))
    return propre.sort_values(date).reset_index(drop=True), rapport


def agreger(propre: pd.DataFrame, date: str, cible: str, freq: str, rapport) -> pd.Series:
    code = FREQUENCES[freq][0]
    serie = propre.set_index(date)[cible].resample(code).sum()
    # Périodes INCOMPLÈTES aux extrémités (ex. semaine du 29/12 au 04/01 alors que les données
    # s'arrêtent le 31/12) : leur somme est artificiellement basse et fausserait le test.
    debut_donnees, fin_donnees = propre[date].min(), propre[date].max()
    if freq == "mois":
        debut_p, fin_p = serie.index, serie.index + pd.offsets.MonthEnd(0)
    elif freq == "semaine":
        debut_p, fin_p = serie.index - pd.Timedelta(days=6), serie.index
    else:
        debut_p, fin_p = serie.index, serie.index
    completes = (debut_p >= debut_donnees.normalize()) & (fin_p <= fin_donnees.normalize())
    if (~completes).any():
        rapport.ajouter(f"{int((~completes).sum())} période(s) incomplète(s) au début ou à la fin retirée(s) : "
                        f"{[str(d.date()) for d in serie.index[~completes]]}.")
        serie = serie[completes]
    rapport.ajouter(f"Agrégation : somme de « {cible} » par {freq} ({len(serie)} périodes, "
                    f"du {serie.index.min():%Y-%m-%d} au {serie.index.max():%Y-%m-%d}) ; "
                    "une période sans vente vaut 0.")
    return serie


def choisir_frequence(propre: pd.DataFrame, date: str, demandee: Optional[str]) -> str:
    """
    Fréquence la plus GROSSIÈRE qui donne assez de périodes (mois > semaine > jour) :
    un CA mensuel est moins bruité qu'un CA hebdomadaire (mesuré sur sales_data :
    MAPE 13 % par mois contre 64 % par semaine) et c'est l'horizon utile en gestion.
    """
    # Jamais plus fin que la granularité réelle des données : 5 dates MENSUELLES agrégées
    # par semaine donneraient 17 « semaines » presque toutes à 0 (périodes inventées).
    ecart_median = propre[date].drop_duplicates().sort_values().diff().dt.days.median()
    ecart_median = 0 if pd.isna(ecart_median) else ecart_median
    if demandee:
        return demandee
    etendue_jours = (propre[date].max() - propre[date].min()).days
    if etendue_jours / 30.44 >= config.PREVISION_MIN_PERIODES + 1 or ecart_median >= 25:
        return "mois"
    if etendue_jours / 7 >= config.PREVISION_MIN_PERIODES + 1 or ecart_median >= 6:
        return "semaine"
    return "jour"


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------
def _prophet(train: pd.Series, horizon: int, freq: str):
    from prophet import Prophet
    etendue_jours = (train.index.max() - train.index.min()).days
    modele = Prophet(yearly_seasonality=etendue_jours >= 700, weekly_seasonality=(freq == "jour"),
                     daily_seasonality=False, interval_width=NIVEAU_CONFIANCE)
    modele.fit(pd.DataFrame({"ds": train.index, "y": train.values}))
    futur = modele.make_future_dataframe(periods=horizon, freq=FREQUENCES[freq][0], include_history=False)
    p = modele.predict(futur)
    return p["yhat"].values, p["yhat_lower"].values, p["yhat_upper"].values


def _features(index: pd.DatetimeIndex, valeurs: list, t0: int, freq: str) -> dict:
    """Features d'UNE période à partir des valeurs connues (ou prévues) jusqu'à la période précédente."""
    return {"t": t0, "mois": index.month if freq != "jour" else index.month,
            "jour_semaine": index.dayofweek if freq == "jour" else 0,
            "lag_1": valeurs[-1], "lag_2": valeurs[-2], "lag_3": valeurs[-3],
            "moyenne_mobile_3": float(np.mean(valeurs[-3:]))}


def _lightgbm(train: pd.Series, horizon: int, freq: str, residus_std: Optional[float] = None):
    import lightgbm as lgb
    valeurs = list(train.values.astype(float))
    lignes, y = [], []
    for i in range(3, len(valeurs)):
        lignes.append(_features(train.index[i], valeurs[:i], i, freq))
        y.append(valeurs[i])
    X = pd.DataFrame(lignes)
    # Petits jeux (24 mois) : arbres peu profonds, feuilles d'au moins 3 périodes, sinon sur-apprentissage
    modele = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=7, min_child_samples=3,
                               subsample=0.9, subsample_freq=1, random_state=42, verbose=-1)
    modele.fit(X, y)
    pas = pd.tseries.frequencies.to_offset(FREQUENCES[freq][0])
    dates = pd.date_range(train.index[-1] + pas, periods=horizon, freq=FREQUENCES[freq][0])
    historique = valeurs.copy()
    prevues = []
    for k, d in enumerate(dates):                        # prévision récursive
        x = pd.DataFrame([_features(d, historique, len(historique), freq)])
        v = float(modele.predict(x)[0])
        prevues.append(v)
        historique.append(v)
    prevues = np.array(prevues)
    ecart = residus_std if residus_std is not None else float(np.std(np.array(y) - modele.predict(X)))
    z = 1.96                                             # intervalle à 95 % (hypothèse d'erreurs gaussiennes)
    return prevues, prevues - z * ecart, prevues + z * ecart


def _naif(train: pd.Series, horizon: int, freq: str):
    """Référence : la valeur de la même période l'an dernier (mois), sinon la dernière valeur."""
    saison = {"mois": 12, "semaine": 52, "jour": 7}[freq]
    if len(train) >= saison:
        base = [train.values[-saison + (k % saison)] for k in range(horizon)]
    else:
        base = [train.values[-1]] * horizon
    base = np.array(base, float)
    return base, base, base


MODELES = {"Prophet": _prophet, "LightGBM": _lightgbm}


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def prevoir(df: pd.DataFrame, question: str = "", horizon: Optional[int] = None, source: str = "",
            colonne_cible: Optional[str] = None, frequence: Optional[str] = None) -> ResultatPrevision:
    t0 = time.time()
    if colonne_cible:
        dates = [c for c in df.columns if stats.est_date(df, c)]
        if not dates:
            raise HistoriqueInsuffisant("Aucune colonne de dates dans ce fichier.")
        date, cible = dates[0], colonne_cible
    else:
        date, cible = choisir_colonnes(df, question)
    horizon = horizon or horizon_demande(question) or config.PREVISION_HORIZON_DEFAUT
    propre, rapport = preparer(df, date, cible, source)
    freq = choisir_frequence(propre, date, frequence or frequence_demandee(question))
    serie = agreger(propre, date, cible, freq, rapport)
    if len(serie) < config.PREVISION_MIN_PERIODES:
        raise HistoriqueInsuffisant(
            f"Historique insuffisant : {len(serie)} période(s) de {freq} après agrégation, il en faut au moins "
            f"{config.PREVISION_MIN_PERIODES} pour entraîner et tester un modèle de façon fiable.")

    nb_test = max(3, min(12, round(len(serie) * 0.2)))
    train, test = serie.iloc[:-nb_test], serie.iloc[-nb_test:]
    rapport.ajouter(f"Split temporel : {len(train)} premières périodes pour l'entraînement, "
                    f"{nb_test} dernières pour le test (jamais de mélange aléatoire).")
    t_prep = time.time()

    proches_zero = bool((np.abs(test.values) < 0.01 * max(1e-9, np.abs(serie.values).mean())).any())
    critere = "smape" if proches_zero else "mape"
    comparaison, predictions_test = [], {}
    for nom, fonction in list(MODELES.items()) + [("Référence naïve", _naif)]:
        debut = time.time()
        try:
            prevu, _, _ = fonction(train, nb_test, freq)
        except Exception as e:                        # un modèle qui échoue ne bloque pas l'autre
            log.warning("Modèle %s en échec : %s", nom, e)
            continue
        m = calculer_metriques(test.values, prevu)
        m.update({"modele": nom, "duree_s": round(time.time() - debut, 2), "candidat": nom in MODELES})
        comparaison.append(m)
        predictions_test[nom] = prevu
    candidats = [m for m in comparaison if m["candidat"]]
    if not candidats:
        raise HistoriqueInsuffisant("Aucun modèle n'a pu être entraîné sur cet historique.")
    retenu = min(candidats, key=lambda m: m[critere])["modele"]
    t_eval = time.time()

    # Modèle retenu réentraîné sur TOUT l'historique pour la prévision du futur
    residus = np.std(test.values - predictions_test[retenu]) if retenu == "LightGBM" else None
    prevu, bas, haut = (_lightgbm(serie, horizon, freq, residus) if retenu == "LightGBM"
                        else MODELES[retenu](serie, horizon, freq))
    pas = pd.tseries.frequencies.to_offset(FREQUENCES[freq][0])
    periodes = pd.date_range(serie.index[-1] + pas, periods=horizon, freq=FREQUENCES[freq][0])
    previsions = pd.DataFrame({"periode": periodes, "prevision": prevu, "borne_basse": bas, "borne_haute": haut})
    rapport.ajouter(f"Modèle retenu : {retenu} ({critere.upper()} le plus faible sur le test), réentraîné sur les "
                    f"{len(serie)} périodes ; prévision de {horizon} période(s).")

    donnees = serie.rename(cible).reset_index().rename(columns={date: "periode"})
    donnees["jeu"] = ["entrainement"] * len(train) + ["test"] * nb_test
    for nom, valeurs in predictions_test.items():
        donnees[f"prevision_test_{nom}"] = [None] * len(train) + list(np.round(valeurs, 2))
    return ResultatPrevision(
        colonne_date=date, colonne_cible=cible, frequence=freq, nb_periodes=len(serie), nb_test=nb_test,
        comparaison=comparaison, modele_retenu=retenu, critere=critere, previsions=previsions,
        historique=serie, test_predictions={k: list(v) for k, v in predictions_test.items()},
        df_nettoye=donnees, rapport=rapport,
        temps={"preparation_s": round(t_prep - t0, 2), "entrainement_evaluation_s": round(t_eval - t_prep, 2),
               "prevision_finale_s": round(time.time() - t_eval, 2), "total_s": round(time.time() - t0, 2)})


def figure(res: ResultatPrevision, langue: str = "fr") -> go.Figure:
    l = langue if langue in ("fr", "en", "ar") else "fr"
    noms = {"hist": {"fr": "Historique", "en": "History", "ar": "التاريخ"},
            "prev": {"fr": "Prévision", "en": "Forecast", "ar": "التوقع"},
            "ic": {"fr": "Intervalle de confiance 95 %", "en": "95% confidence interval", "ar": "مجال الثقة 95٪"},
            "titre": {"fr": f"Prévision de {res.colonne_cible} par {res.frequence} ({res.modele_retenu})",
                      "en": f"{res.colonne_cible} forecast ({res.modele_retenu})",
                      "ar": f"توقع {res.colonne_cible} ({res.modele_retenu})"}}
    fig = go.Figure()
    p = res.previsions
    fig.add_scatter(x=list(p["periode"]) + list(p["periode"][::-1]),
                    y=list(p["borne_haute"]) + list(p["borne_basse"][::-1]), fill="toself",
                    fillcolor="rgba(10,132,224,0.15)", line={"width": 0}, name=noms["ic"][l], hoverinfo="skip")
    fig.add_scatter(x=res.historique.index, y=res.historique.values, mode="lines+markers", name=noms["hist"][l],
                    line={"color": "#2c3e50", "width": 2})
    fig.add_scatter(x=[res.historique.index[-1]] + list(p["periode"]),
                    y=[res.historique.values[-1]] + list(p["prevision"]), mode="lines+markers",
                    name=noms["prev"][l], line={"color": "#0a84e0", "width": 3, "dash": "dash"})
    fig.update_layout(template="plotly_white", title={"text": noms["titre"][l], "x": 0.02},
                      xaxis_title=res.colonne_date, yaxis_title=res.colonne_cible,
                      separators=", " if l == "fr" else ".,", paper_bgcolor="white", plot_bgcolor="white",
                      legend={"orientation": "h", "y": -0.2}, margin={"l": 60, "r": 30, "t": 70, "b": 80})
    return fig

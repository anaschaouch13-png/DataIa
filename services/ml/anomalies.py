"""
services/ml/anomalies.py — Détection d'anomalies par Isolation Forest (Phase 5.3).

Idée d'Isolation Forest : on construit des arbres qui coupent les données au hasard.
Une ligne ANORMALE est isolée en peu de coupes (elle est loin des autres) ; une ligne
normale demande beaucoup de coupes. Le score d'anomalie = rapidité d'isolement.

Choix (mesurés sur ventes_demo_dataia.xlsx, 8 anomalies volontaires) :
  - Colonnes TRANSACTIONNELLES (quantité, prix, montant) plutôt que toutes les colonnes :
    l'âge ou la satisfaction « diluent » la recherche (rangs des anomalies 1 à 360).
  - Feature de COHÉRENCE quand quantité, prix et montant existent :
      écart = (montant − quantité × prix × (1 − remise)) / |quantité × prix|, borné à [−5, 5]
    -> un montant négatif ou un prix de 0,01 deviennent flagrants.
  - Normalisation (StandardScaler) : Isolation Forest est peu sensible à l'échelle, mais les
    scores et l'explication par colonne sont ainsi comparables.
  - Seuil AUTOMATIQUE robuste : score > Q3 + 3 × IQR des scores (pas de « contamination »
    à deviner). Les lignes juste sous le seuil sont listées « à surveiller ».
  - Explication de chaque anomalie : colonnes les plus éloignées de la médiane (z-score robuste).
"""

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from services import stats
from services.redaction import formater_nombre
from services.ml import nettoyage
from services.semantique import colonnes_citees, colonnes_du_concept, normaliser

ECART = "ecart_coherence"
GRAINE = 42


@dataclass
class ModeleAnomalies:
    """Modèle entraîné sur un fichier (réutilisé par le simulateur pour une transaction saisie)."""
    pipeline: Pipeline
    colonnes: List[str]                    # colonnes du fichier utilisées
    coherence: Optional[dict]              # {"quantite", "prix", "montant", "remise"} si la feature existe
    seuil: float
    medianes: dict
    dispersions: dict

    def matrice(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame({c: stats.en_numerique(df[c]) for c in self.colonnes}, index=df.index)
        X = X.fillna(pd.Series(self.medianes))
        if self.coherence:
            c = self.coherence
            remise = (stats.en_numerique(df[c["remise"]]).fillna(0) / 100) if c.get("remise") and c["remise"] in df \
                else 0
            attendu = X[c["quantite"]] * X[c["prix"]] * (1 - remise)
            X[ECART] = ((X[c["montant"]] - attendu) / attendu.abs().clip(lower=1)).clip(-5, 5)
        return X

    def scores(self, df: pd.DataFrame) -> np.ndarray:
        return -self.pipeline.score_samples(self.matrice(df))      # plus grand = plus anormal


@dataclass
class ResultatAnomalies:
    modele: ModeleAnomalies
    anomalies: pd.DataFrame                # lignes anormales + score + raison
    a_surveiller: pd.DataFrame             # lignes suivantes, sous le seuil
    nb_lignes: int
    df_nettoye: pd.DataFrame
    rapport: nettoyage.RapportNettoyage
    axes: tuple                            # colonnes du nuage de points
    temps: dict = field(default_factory=dict)


def _colonne_remise(df: pd.DataFrame) -> Optional[str]:
    return next((c for c in df.columns if re.search(r"remise|discount|rabais", normaliser(c))
                 and stats.est_numerique(df, c)), None)


def choisir_colonnes(df: pd.DataFrame, question: str = "") -> tuple:
    from services.charts import _est_identifiant
    numeriques = [c for c in df.columns if stats.est_numerique(df, c) and not stats.est_date(df, c)
                  and not _est_identifiant(df, c)]
    citees = [c for c in colonnes_citees(question, [str(c) for c in df.columns]) if c in numeriques]
    prix = next(iter(colonnes_du_concept(df, "prix")), None)
    quantite = next(iter(colonnes_du_concept(df, "quantite")), None)
    montant = next(iter(colonnes_du_concept(df, "ventes")), None)
    coherence = None
    if prix and quantite and montant and len({prix, quantite, montant}) == 3:
        coherence = {"quantite": quantite, "prix": prix, "montant": montant, "remise": _colonne_remise(df)}
    if len(citees) >= 2:
        colonnes = citees
    else:
        transactionnelles = [c for c in (quantite, prix, montant) if c]
        colonnes = list(dict.fromkeys(transactionnelles)) if len(set(transactionnelles)) >= 2 else numeriques[:10]
    # (la remise ne sert qu'au calcul de la cohérence : comme colonne à part entière, elle
    #  diluait la recherche — mesuré : 0 anomalie trouvée au lieu de 7)
    if not colonnes:
        raise ValueError("Aucune colonne numérique exploitable pour détecter des anomalies.")
    return colonnes, coherence


def entrainer(df: pd.DataFrame, colonnes: List[str], coherence: Optional[dict]) -> ModeleAnomalies:
    X = pd.DataFrame({c: stats.en_numerique(df[c]) for c in colonnes})
    medianes = X.median().to_dict()
    dispersions = {}
    for c in colonnes:
        mad = float((X[c] - medianes[c]).abs().median()) * 1.4826       # écart absolu médian (robuste)
        dispersions[c] = mad if mad > 0 else float(X[c].std() or 1.0)
    modele = ModeleAnomalies(Pipeline([("normalisation", StandardScaler()),
                                       ("isolation_forest", IsolationForest(n_estimators=300, random_state=GRAINE))]),
                             colonnes, coherence, 0.0, medianes, dispersions)
    M = modele.matrice(df)
    modele.pipeline.fit(M)
    s = modele.scores(df)
    q1, q3 = np.percentile(s, [25, 75])
    modele.seuil = float(q3 + 3 * (q3 - q1))
    return modele


def expliquer(modele: ModeleAnomalies, ligne: pd.Series, langue: str = "fr") -> str:
    """Raison lisible : colonnes les plus éloignées de la médiane, et incohérence éventuelle."""
    langue = langue if langue in ("fr", "en", "ar") else "fr"
    raisons = []
    if modele.coherence:
        c = modele.coherence
        q, p, m = (float(stats.en_numerique(pd.Series([ligne[c[k]]]))[0]) for k in ("quantite", "prix", "montant"))
        r = float(stats.en_numerique(pd.Series([ligne[c["remise"]]]))[0]) / 100 if c.get("remise") else 0
        attendu = q * p * (1 - r)
        if abs(m - attendu) > max(1.0, 0.01 * abs(attendu)):
            fm, fa = formater_nombre(m, langue), formater_nombre(attendu, langue)
            raisons.append({"fr": f"{c['montant']} = {fm} au lieu de {fa} ({c['quantite']} × {c['prix']})",
                            "en": f"{c['montant']} = {fm} instead of {fa} ({c['quantite']} × {c['prix']})",
                            "ar": f"{c['montant']} = {fm} بدل {fa} ({c['quantite']} × {c['prix']})"}[langue])
    ecarts = {}
    for col in modele.colonnes:
        v = float(stats.en_numerique(pd.Series([ligne[col]]))[0])
        ecarts[col] = (v - modele.medianes[col]) / modele.dispersions[col]
    for col, z in sorted(ecarts.items(), key=lambda kv: -abs(kv[1]))[:2]:
        if abs(z) >= 3:
            sens = {"fr": ("très élevé", "très bas"), "en": ("very high", "very low"), "ar": ("مرتفع جدًا", "منخفض جدًا")}[langue]
            mediane = {"fr": "médiane", "en": "median", "ar": "الوسيط"}[langue]
            raisons.append(f"{col} {sens[0] if z > 0 else sens[1]} ({formater_nombre(float(ligne[col]), langue)} ; "
                           f"{mediane} {formater_nombre(modele.medianes[col], langue)})")
    return " ; ".join(raisons) or {"fr": "combinaison de valeurs inhabituelle", "en": "unusual combination of values",
                                   "ar": "تركيبة قيم غير معتادة"}[langue]


def detecter(df: pd.DataFrame, question: str = "", source: str = "", langue: str = "fr",
             nb_a_surveiller: int = 15) -> ResultatAnomalies:
    t0 = time.time()
    colonnes, coherence = choisir_colonnes(df, question)
    rapport = nettoyage.commencer(df, "détection d'anomalies (Isolation Forest)", source)
    rapport.ajouter(f"Colonnes analysées : {colonnes}" + (f" + feature de cohérence « {ECART} » = (montant − quantité × prix"
                                                          f"{' × (1 − remise)' if coherence and coherence['remise'] else ''}) / "
                                                          "|quantité × prix|, bornée à [−5 ; 5]" if coherence else "") + ".")
    propre = nettoyage.convertir_numeriques(df.copy(), colonnes, rapport)
    manquants = int(propre[colonnes].isna().sum().sum())
    rapport.ajouter(f"{manquants} valeur(s) manquante(s) remplacée(s) par la médiane de leur colonne (aucune ligne supprimée : "
                    "une transaction incomplète peut elle-même être une anomalie)." if manquants
                    else "Aucune valeur manquante dans les colonnes analysées.")
    rapport.ajouter("Doublons conservés : deux transactions identiques peuvent être légitimes.")
    rapport.ajouter("Normalisation StandardScaler (moyenne 0, écart-type 1) dans le pipeline, avant Isolation Forest "
                    "(300 arbres, graine 42).")

    modele = entrainer(propre, colonnes, coherence)
    scores = modele.scores(propre)
    rapport.ajouter(f"Seuil automatique : score > Q3 + 3 × IQR des scores = {modele.seuil:.4f}.")
    resultat = df.copy()
    resultat["score_anomalie"] = np.round(scores, 4)
    resultat["anomalie"] = scores > modele.seuil
    ordre = resultat.sort_values("score_anomalie", ascending=False)
    anomalies = ordre[ordre["anomalie"]].copy()
    surveiller = ordre[~ordre["anomalie"]].head(nb_a_surveiller).copy()
    for t in (anomalies, surveiller):
        t["raison"] = [expliquer(modele, l, langue) for _, l in t.iterrows()]
    rapport.ajouter(f"{len(anomalies)} anomalie(s) détectée(s) sur {len(df)} lignes ; "
                    f"{len(surveiller)} ligne(s) « à surveiller » juste sous le seuil.")

    exporte = modele.matrice(propre)
    exporte.columns = [f"{c} (utilisé)" if c != ECART else ECART for c in exporte.columns]
    donnees = pd.concat([df.reset_index(drop=True), exporte.reset_index(drop=True),
                         resultat[["score_anomalie", "anomalie"]].reset_index(drop=True)], axis=1)
    axes = (coherence["quantite"], coherence["montant"]) if coherence else tuple(colonnes[:2]) if len(colonnes) >= 2 \
        else (colonnes[0], colonnes[0])
    return ResultatAnomalies(modele, anomalies, surveiller, len(df), donnees, rapport, axes,
                             {"total_s": round(time.time() - t0, 2)})


def figure(res: ResultatAnomalies, df: pd.DataFrame, langue: str = "fr") -> go.Figure:
    x, y = res.axes
    l = langue if langue in ("fr", "en", "ar") else "fr"
    scores = res.modele.scores(df)
    normal = scores <= res.modele.seuil
    noms = {"n": {"fr": "Normale", "en": "Normal", "ar": "عادية"}, "a": {"fr": "Anomalie", "en": "Anomaly", "ar": "شاذة"},
            "t": {"fr": f"Anomalies détectées (Isolation Forest) : {int((~normal).sum())} sur {len(df)}",
                  "en": f"Detected anomalies (Isolation Forest): {int((~normal).sum())} of {len(df)}",
                  "ar": f"الحالات الشاذة (Isolation Forest): {int((~normal).sum())} من {len(df)}"}}
    vx, vy = stats.en_numerique(df[x]), stats.en_numerique(df[y])
    fig = go.Figure()
    fig.add_scatter(x=vx[normal], y=vy[normal], mode="markers", name=noms["n"][l],
                    marker={"color": "#95a5a6", "size": 6, "opacity": 0.5})
    fig.add_scatter(x=vx[~normal], y=vy[~normal], mode="markers", name=noms["a"][l],
                    marker={"color": "#e74c3c", "size": 11, "line": {"color": "#7f1d1d", "width": 1}},
                    text=[f"score {s:.3f}" for s in scores[~normal]], hovertemplate="%{x} / %{y}<br>%{text}<extra></extra>")
    fig.update_layout(template="plotly_white", title={"text": noms["t"][l], "x": 0.02}, xaxis_title=x, yaxis_title=y,
                      separators=", " if l == "fr" else ".,", paper_bgcolor="white", plot_bgcolor="white",
                      margin={"l": 60, "r": 30, "t": 70, "b": 60})
    return fig


def evaluer_transaction(modele: ModeleAnomalies, valeurs: dict) -> dict:
    """Simulateur : une transaction saisie -> normale / anormale + score."""
    donnees = {c: valeurs.get(c, modele.medianes[c]) for c in modele.colonnes}
    if modele.coherence and modele.coherence.get("remise"):         # remise facultative (0 par défaut)
        donnees[modele.coherence["remise"]] = valeurs.get(modele.coherence["remise"], 0)
    ligne = pd.DataFrame([donnees])
    score = float(modele.scores(ligne)[0])
    return {"anomalie": score > modele.seuil, "score": round(score, 4), "seuil": round(modele.seuil, 4),
            "raison": expliquer(modele, ligne.iloc[0])}

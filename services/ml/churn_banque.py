"""
services/ml/churn_banque.py — Prédiction du départ des clients (churn), domaine Banque (Phase 5.4).

- Le Pipeline scikit-learn (OneHotEncoder + arbre de décision) entraîné par
  entrainer_churn.py est chargé UNE SEULE FOIS (au premier usage, puis gardé en mémoire).
- Aucun réentraînement : le modèle est utilisé tel quel.
- Le prétraitement d'entraînement (encodage one-hot) est DANS le pipeline : il est donc
  appliqué exactement à l'identique à la prédiction.
- Sur un fichier : les colonnes attendues sont vérifiées (noms tolérants : « Geography »
  = country, « NumOfProducts » = products_number...) ; s'il en manque, on renvoie la
  liste des colonnes manquantes au lieu de planter.
"""

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import config
from services import stats
from services.ml import nettoyage

SEUIL = 0.5
# Noms alternatifs reconnus pour chaque colonne attendue (comparaison sans casse ni « _ »)
ALIAS = {
    "credit_score": ["creditscore", "score", "scorecredit", "score_credit"],
    "country": ["geography", "pays", "region", "countryname"],
    "gender": ["sexe", "genre", "sex"],
    "age": ["ageclient", "age_client"],
    "tenure": ["anciennete", "seniority", "years"],
    "balance": ["solde", "balanceaccount"],
    "products_number": ["numofproducts", "nbproduits", "nombreproduits", "productsnumber", "nb_produits"],
    "credit_card": ["hascrcard", "carte", "cartecredit", "hascreditcard"],
    "active_member": ["isactivemember", "actif", "membreactif"],
    "estimated_salary": ["estimatedsalary", "salaire", "salary", "salaireestime"],
}

_verrou = threading.Lock()
_modele = None
_meta: Optional[dict] = None


class ModeleChurnIndisponible(RuntimeError):
    pass


def charger() -> tuple:
    """Charge le pipeline et ses métadonnées une seule fois (thread-safe)."""
    global _modele, _meta
    if _modele is None:
        with _verrou:
            if _modele is None:
                if not os.path.isfile(config.CHURN_MODEL_PATH):
                    raise ModeleChurnIndisponible(
                        f"Modèle churn introuvable ({config.CHURN_MODEL_PATH}). Lancez : python entrainer_churn.py")
                chemin_meta = os.path.splitext(config.CHURN_MODEL_PATH)[0] + "_metadonnees.json"
                with open(chemin_meta, encoding="utf-8") as f:
                    _meta = json.load(f)
                _modele = joblib.load(config.CHURN_MODEL_PATH)
    return _modele, _meta


def _cle(nom: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(nom).lower())


def correspondance_colonnes(df: pd.DataFrame, attendues: List[str]) -> tuple:
    """{colonne attendue: colonne du fichier} et liste des colonnes manquantes."""
    par_cle = {_cle(c): c for c in df.columns}
    trouve, manquantes = {}, []
    for a in attendues:
        candidats = [a] + ALIAS.get(a, [])
        colonne = next((par_cle[_cle(c)] for c in candidats if _cle(c) in par_cle), None)
        if colonne is None:
            manquantes.append(a)
        else:
            trouve[a] = colonne
    return trouve, manquantes


class ColonnesManquantes(ValueError):
    def __init__(self, manquantes: List[str], presentes: Dict[str, str]):
        super().__init__(f"Colonnes manquantes : {manquantes}")
        self.manquantes, self.presentes = manquantes, presentes


@dataclass
class ResultatChurn:
    clients: pd.DataFrame                  # fichier + probabilité + prédiction, trié par risque
    nb_clients: int
    nb_risque: int
    importances: Dict[str, float]
    colonnes: Dict[str, str]
    categories_inconnues: Dict[str, List[str]]
    df_nettoye: pd.DataFrame
    rapport: nettoyage.RapportNettoyage
    meta: dict
    temps: dict = field(default_factory=dict)

    @property
    def pourcentage(self) -> float:
        return 100 * self.nb_risque / max(1, self.nb_clients)


def preparer(df: pd.DataFrame, source: str = "") -> tuple:
    modele, meta = charger()
    attendues = meta["features_entree"]
    colonnes, manquantes = correspondance_colonnes(df, attendues)
    if manquantes:
        raise ColonnesManquantes(manquantes, colonnes)
    rapport = nettoyage.commencer(df, "churn (prédiction)", source)
    renommees = {v: k for k, v in colonnes.items() if v != k}
    if renommees:
        rapport.ajouter(f"Colonnes renommées vers les noms du modèle : {renommees}.")
    X = df[[colonnes[a] for a in attendues]].copy()
    X.columns = attendues
    numeriques = [c for c in attendues if c in meta["bornes_numeriques"]]
    categorielles = [c for c in attendues if c in meta["categories"]]
    X = nettoyage.convertir_numeriques(X, numeriques, rapport)
    for c in numeriques:                          # médiane de l'ENTRAÎNEMENT (pas celle du fichier)
        n = int(X[c].isna().sum())
        if n:
            X[c] = X[c].fillna(meta["bornes_numeriques"][c]["mediane"])
            rapport.ajouter(f"« {c} » : {n} valeur(s) manquante(s) -> médiane de l'entraînement "
                            f"({meta['bornes_numeriques'][c]['mediane']}).")
    inconnues = {}
    for c in categorielles:
        X[c] = X[c].astype(str).str.strip()
        autres = sorted(set(X[c].unique()) - set(meta["categories"][c]))
        if autres:
            inconnues[c] = autres
            rapport.ajouter(f"« {c} » : valeur(s) inconnue(s) du modèle {autres} -> encodées en 0 sur toutes les "
                            f"colonnes one-hot (handle_unknown='ignore'). Valeurs connues : {meta['categories'][c]}.")
    rapport.ajouter("Encodage one-hot de country et gender fait PAR LE PIPELINE (identique à l'entraînement).")
    return X, colonnes, inconnues, rapport


def predire_fichier(df: pd.DataFrame, source: str = "") -> ResultatChurn:
    t0 = time.time()
    modele, meta = charger()
    X, colonnes, inconnues, rapport = preparer(df, source)
    proba = modele.predict_proba(X)[:, 1]
    clients = df.copy()
    clients["probabilite_depart"] = np.round(proba, 4)
    clients["prediction"] = np.where(proba >= SEUIL, "Risque de départ", "Reste")
    clients = clients.sort_values("probabilite_depart", ascending=False)
    rapport.ajouter(f"Prédiction : probabilité de départ (classe 1) ; seuil {SEUIL} -> « Risque de départ ».")
    donnees = pd.concat([X.reset_index(drop=True),
                         pd.DataFrame({"probabilite_depart": np.round(proba, 4),
                                       "prediction": np.where(proba >= SEUIL, 1, 0)})], axis=1)
    return ResultatChurn(clients, len(df), int((proba >= SEUIL).sum()), meta["importance_variables"], colonnes,
                         inconnues, donnees, rapport, meta, {"total_s": round(time.time() - t0, 3)})


def predire_client(valeurs: dict) -> dict:
    """Simulateur : un client saisi -> « Reste » / « Risque de départ » + probabilité."""
    modele, meta = charger()
    ligne = {}
    for c in meta["features_entree"]:
        v = valeurs.get(c)
        if c in meta["bornes_numeriques"]:
            v = float(v) if v not in (None, "") else meta["bornes_numeriques"][c]["mediane"]
        else:
            v = str(v) if v not in (None, "") else meta["categories"][c][0]
        ligne[c] = v
    proba = float(modele.predict_proba(pd.DataFrame([ligne]))[0, 1])
    return {"probabilite_depart": round(proba, 4), "prediction": "Risque de départ" if proba >= SEUIL else "Reste",
            "seuil": SEUIL, "entrees": ligne}


def champs_formulaire() -> List[dict]:
    """Formulaire du simulateur généré à partir des features du modèle (Phase 6)."""
    _, meta = charger()
    champs = []
    for c in meta["features_entree"]:
        if c in meta["categories"]:
            champs.append({"nom": c, "type": "liste", "options": meta["categories"][c],
                           "defaut": meta["categories"][c][0]})
        else:
            b = meta["bornes_numeriques"][c]
            binaire = b["entier"] and b["min"] == 0 and b["max"] == 1
            champs.append({"nom": c, "type": "booleen" if binaire else "nombre", "min": b["min"], "max": b["max"],
                           "pas": 1 if b["entier"] else 0.01, "defaut": b["mediane"]})
    return champs


def figures(res: ResultatChurn, langue: str = "fr") -> List[go.Figure]:
    l = langue if langue in ("fr", "en", "ar") else "fr"
    t = {"reste": {"fr": "Reste", "en": "Stays", "ar": "يبقى"},
         "part": {"fr": "Risque de départ", "en": "Churn risk", "ar": "خطر المغادرة"},
         "titre1": {"fr": f"Répartition des {res.nb_clients} clients", "en": f"Breakdown of {res.nb_clients} customers",
                    "ar": f"توزيع {res.nb_clients} عميل"},
         "titre2": {"fr": "Importance des variables (arbre de décision)", "en": "Feature importance (decision tree)",
                    "ar": "أهمية المتغيرات (شجرة القرار)"}}
    commun = dict(template="plotly_white", separators=", " if l == "fr" else ".,", paper_bgcolor="white",
                  plot_bgcolor="white", margin={"l": 60, "r": 30, "t": 70, "b": 60})
    f1 = go.Figure(go.Pie(labels=[t["reste"][l], t["part"][l]], values=[res.nb_clients - res.nb_risque, res.nb_risque],
                          hole=0.45, marker={"colors": ["#27ae60", "#e74c3c"]}, textinfo="label+value+percent", sort=False))
    f1.update_layout(title={"text": t["titre1"][l], "x": 0.02}, **commun)
    imp = dict(sorted(res.importances.items(), key=lambda kv: kv[1]))
    f2 = go.Figure(go.Bar(x=list(imp.values()), y=list(imp.keys()), orientation="h", marker_color="#0a84e0",
                          text=[f"{v:.1%}" for v in imp.values()], textposition="outside"))
    f2.update_layout(title={"text": t["titre2"][l], "x": 0.02}, xaxis_tickformat=".0%", **commun)
    return [f1, f2]

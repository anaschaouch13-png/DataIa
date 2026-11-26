"""
services/ml/registry.py — Registre des modèles de Machine Learning par domaine.

Une seule source de vérité : quels modèles sont proposés à quel domaine.
Ajouter un modèle (ex. recommandation pour l'e-commerce) = ajouter une entrée
dans MODELES et son nom dans MODELES_PAR_DOMAINE, sans toucher au reste du code.

Chaque entrée indique, sous forme de texte « module:fonction », la fonction qui exécute
le modèle dans le chat et celle du simulateur what-if : elles sont importées au moment de
l'appel (pas d'import circulaire, et un modèle lourd n'est chargé que s'il est utilisé).

Exemple d'ajout pour l'e-commerce :
    MODELES["reco"] = DescriptionModele("reco", "recommandation", {...},
                                        "services.ml.executeur:lancer_reco", "services.ml.simulateur:simuler_reco")
    MODELES_SPECIFIQUES["E-commerce"] = ["reco"]
(+ la valeur « recommandation » dans l'ENUM modeles_ml.type, par une migration.)
"""

import importlib
from dataclasses import dataclass
from typing import Callable, Dict, List

from services.domaines import DOMAINES


@dataclass(frozen=True)
class DescriptionModele:
    cle: str                 # identifiant = intent du routeur (forecast, anomaly, churn)
    type_bdd: str            # valeur de modeles_ml.type / simulations.type_modele
    noms: Dict[str, str]     # nom affiché par langue
    lanceur: str = ""        # « module:fonction » exécutée quand l'utilisateur le demande dans le chat
    simulateur: str = ""     # « module:fonction » du simulateur what-if (Phase 6)


MODELES: Dict[str, DescriptionModele] = {
    "forecast": DescriptionModele("forecast", "prevision", {
        "fr": "Prévision du chiffre d'affaires", "en": "Revenue forecast", "ar": "توقع رقم المعاملات"},
        "services.ml.executeur:lancer_prevision", "services.ml.simulateur:simuler_prevision"),
    "anomaly": DescriptionModele("anomaly", "anomalie", {
        "fr": "Détection d'anomalies", "en": "Anomaly detection", "ar": "كشف الحالات الشاذة"},
        "services.ml.executeur:lancer_anomalies", "services.ml.simulateur:simuler_anomalie"),
    "churn": DescriptionModele("churn", "churn", {
        "fr": "Prédiction du départ des clients (churn)", "en": "Customer churn prediction",
        "ar": "توقع مغادرة العملاء"},
        "services.ml.executeur:lancer_churn", "services.ml.simulateur:simuler_churn"),
}


def _importer(reference: str) -> Callable:
    module, fonction = reference.split(":")
    return getattr(importlib.import_module(module), fonction)


def lanceur(cle_modele: str) -> Callable:
    return _importer(MODELES[cle_modele].lanceur)


def simulateur(cle_modele: str) -> Callable:
    return _importer(MODELES[cle_modele].simulateur)

# Modèles communs à tous les domaines + modèles spécifiques
MODELES_COMMUNS = ["forecast", "anomaly"]
MODELES_SPECIFIQUES: Dict[str, List[str]] = {
    "Banque": ["churn"],
}
MODELES_PAR_DOMAINE: Dict[str, List[str]] = {
    d: MODELES_COMMUNS + MODELES_SPECIFIQUES.get(d, []) for d in DOMAINES
}


def modeles_du_domaine(domaine: str) -> List[str]:
    """Clés des modèles disponibles pour un domaine (Autre si domaine inconnu)."""
    return MODELES_PAR_DOMAINE.get(domaine, MODELES_COMMUNS)


def est_disponible(cle_modele: str, domaine: str) -> bool:
    return cle_modele in modeles_du_domaine(domaine)


def domaines_du_modele(cle_modele: str) -> List[str]:
    """Domaines qui ont accès à un modèle (pour l'expliquer à l'utilisateur)."""
    return [d for d, modeles in MODELES_PAR_DOMAINE.items() if cle_modele in modeles]


def nom_modele(cle_modele: str, langue: str) -> str:
    noms = MODELES[cle_modele].noms
    return noms.get(langue, noms["fr"])

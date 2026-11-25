"""
services/ml/registry.py — Registre des modèles de Machine Learning par domaine.

Une seule source de vérité : quels modèles sont proposés à quel domaine.
Ajouter un modèle (ex. recommandation pour l'e-commerce) = ajouter une entrée
dans MODELES et son nom dans MODELES_PAR_DOMAINE, sans toucher au reste du code.

Phase 3 : seules les métadonnées sont utilisées (le routeur vérifie que le modèle
demandé existe pour le domaine de l'utilisateur).
Phase 5 : chaque entrée recevra la fonction qui exécute le modèle.
"""

from dataclasses import dataclass
from typing import Dict, List

from services.domaines import DOMAINES


@dataclass(frozen=True)
class DescriptionModele:
    cle: str                 # identifiant = intent du routeur (forecast, anomaly, churn)
    type_bdd: str            # valeur de modeles_ml.type / simulations.type_modele
    noms: Dict[str, str]     # nom affiché par langue


MODELES: Dict[str, DescriptionModele] = {
    "forecast": DescriptionModele("forecast", "prevision", {
        "fr": "Prévision du chiffre d'affaires", "en": "Revenue forecast", "ar": "توقع رقم المعاملات"}),
    "anomaly": DescriptionModele("anomaly", "anomalie", {
        "fr": "Détection d'anomalies", "en": "Anomaly detection", "ar": "كشف الحالات الشاذة"}),
    "churn": DescriptionModele("churn", "churn", {
        "fr": "Prédiction du départ des clients (churn)", "en": "Customer churn prediction",
        "ar": "توقع مغادرة العملاء"}),
}

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

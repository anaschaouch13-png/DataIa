"""
services/domaines.py — Domaines d'activité des utilisateurs.

La liste doit rester identique à l'ENUM de la colonne `utilisateurs.domaine`
(migrations/001_phase2_innodb_domaine_ml.sql). Le registre des modèles ML
(services/ml/registry.py, Phase 5) associera à chaque domaine ses modèles.
"""

DOMAINES = ["Banque", "E-commerce", "Finance", "Poste", "Assurance", "Télécom", "Industrie", "Autre"]
DOMAINE_PAR_DEFAUT = "Autre"


def domaine_valide(domaine: str) -> bool:
    """Vrai si la valeur reçue du formulaire fait partie de la liste autorisée."""
    return domaine in DOMAINES

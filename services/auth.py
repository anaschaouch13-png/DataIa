"""
services/auth.py — Utilisateur connecté (Flask-Login) et contrôle du rôle administrateur.

Partagé par app.py (pages Jinja) et api.py (API JSON du frontend React).
"""

from functools import wraps

from flask import jsonify, request
from flask_login import UserMixin, current_user

from services.domaines import DOMAINE_PAR_DEFAUT


class User(UserMixin):
    def __init__(self, id_user, nom, email, password, role, bloque, domaine=DOMAINE_PAR_DEFAUT):
        self.id = id_user
        self.nom = nom
        self.email = email
        self.password = password
        self.role = role
        self.bloque = bloque
        self.domaine = domaine   # Phase 2 : détermine les modèles ML disponibles (Phase 5)

    @classmethod
    def depuis_ligne(cls, ligne: dict) -> "User":
        """Construit l'utilisateur à partir d'une ligne de la table `utilisateurs`."""
        return cls(ligne['id_utilisateur'], ligne['nom_utilisateur'], ligne['email'],
                   ligne['mot_de_passe'], ligne['role'], ligne['est_bloque'],
                   ligne.get('domaine') or DOMAINE_PAR_DEFAUT)

    def en_dict(self) -> dict:
        """Représentation envoyée au frontend (jamais le hash du mot de passe)."""
        return {"id": self.id, "nom": self.nom, "email": self.email, "role": self.role,
                "est_bloque": int(self.bloque or 0), "domaine": self.domaine}


def est_requete_api() -> bool:
    return request.path.startswith("/api/") or request.is_json


def admin_required(f):
    """Réservé au rôle administrateur : 403 (JSON pour l'API, texte pour les pages)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'administrateur':
            if est_requete_api():
                return jsonify({"status": "error", "message": "Accès réservé à l'administrateur."}), 403
            return "Accès interdit : Vous n'êtes pas administrateur", 403
        return f(*args, **kwargs)
    return decorated_function

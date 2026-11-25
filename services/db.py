"""
services/db.py — Accès à la base MySQL (WampServer).

Les paramètres de connexion viennent de `config.DB_CONFIG` (fichier .env).
"""

import mysql.connector

from config import DB_CONFIG


def get_db_connection():
    """Ouvre une nouvelle connexion MySQL (à fermer par l'appelant)."""
    return mysql.connector.connect(**DB_CONFIG)

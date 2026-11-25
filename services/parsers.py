"""
services/parsers.py — Lecture des fichiers uploadés en DataFrame pandas.

Phase 1 : CSV et Excel (logique reprise de l'ancien app.py, partagée avec reindex.py).
La Phase 7 ajoutera : détection d'encodage, toutes les feuilles Excel, PDF et images (OCR).
"""

import pandas as pd


def charger_dataframe(chemin: str) -> pd.DataFrame:
    """Charge un fichier CSV (séparateur détecté automatiquement) ou Excel."""
    if chemin.lower().endswith('.csv'):
        try:
            return pd.read_csv(chemin, sep=None, engine='python', encoding='utf-8-sig')
        except Exception:
            try:
                return pd.read_csv(chemin, sep=';', encoding='utf-8-sig')
            except Exception:
                return pd.read_csv(chemin)
    return pd.read_excel(chemin)

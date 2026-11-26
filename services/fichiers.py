"""
services/fichiers.py — Fichiers uploadés : chemins, enregistrement, contrôle de propriété.

Partagé par les routes Jinja (app.py) et l'API JSON du frontend React (api.py).
"""

import datetime
import os
from typing import Optional

from werkzeug.utils import secure_filename

import config
from services.db import get_db_connection

# Extensions acceptées (Phase 7 : + PDF et images) -> valeur de fichiers.type_fichier (migration 003)
EXTENSIONS = {".csv": "CSV", ".xls": "Excel", ".xlsx": "Excel", ".pdf": "PDF", ".png": "Image", ".jpg": "Image", ".jpeg": "Image"}


def chemin_absolu(chemin: str) -> str:
    """Les chemins sont stockés en base relativement au dossier du backend (ex. uploads\\x.csv)."""
    chemin = chemin.replace('\\', os.sep)
    return chemin if os.path.isabs(chemin) else os.path.join(config.BASE_DIR, chemin)


def chemin_relatif(chemin: str) -> str:
    """Chemin à enregistrer en base (relatif au backend : le projet reste déplaçable)."""
    return os.path.relpath(chemin, config.BASE_DIR)


def type_de_fichier(nom: str) -> Optional[str]:
    return EXTENSIONS.get(os.path.splitext(nom.lower())[1])


def enregistrer_upload(fichier_upload, id_utilisateur: int) -> tuple:
    """
    Sauvegarde le fichier sous un nom unique et l'enregistre en base.
    Retourne (ligne de la table fichiers, None) ou (None, message d'erreur).
    """
    nom = secure_filename(fichier_upload.filename or "")
    type_fichier = type_de_fichier(nom)
    if not nom or not type_fichier:
        return None, f"Format non supporté. Formats acceptés : {', '.join(sorted(EXTENSIONS))}."
    # Nom unique sur le disque : deux utilisateurs envoyant « ventes.csv » ne s'écrasent plus
    horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = os.path.join(config.UPLOAD_FOLDER, f"U{id_utilisateur}_{horodatage}_{nom}")
    fichier_upload.save(chemin)
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) VALUES (%s, %s, %s, %s)",
                (id_utilisateur, nom, chemin_relatif(chemin), type_fichier))
    conn.commit()
    cur.execute("SELECT * FROM fichiers WHERE id_fichier = %s", (cur.lastrowid,))
    ligne = cur.fetchone()
    cur.close()
    conn.close()
    return ligne, None


def fichier_de_utilisateur(id_fichier, id_utilisateur: int) -> Optional[dict]:
    """La ligne `fichiers` si elle appartient à l'utilisateur, sinon None (protection IDOR)."""
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s", (id_fichier, id_utilisateur))
    ligne = cur.fetchone()
    cur.close()
    conn.close()
    return ligne


def supprimer_fichier(id_fichier: int, id_utilisateur: int) -> bool:
    """Supprime la ligne (l'historique des questions est conservé grâce à ON DELETE SET NULL)."""
    from services import rag
    fichier = fichier_de_utilisateur(id_fichier, id_utilisateur)
    if not fichier:
        return False
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    # Anciennes lignes : plusieurs fichiers peuvent pointer vers le même chemin disque
    cur.execute("SELECT COUNT(*) AS n FROM fichiers WHERE chemin_fichier = %s AND id_fichier <> %s",
                (fichier['chemin_fichier'], id_fichier))
    partage = cur.fetchone()['n'] > 0
    chemin = chemin_absolu(fichier['chemin_fichier'])
    if not partage and os.path.isfile(chemin):
        os.remove(chemin)
    rag.supprimer_index(id_fichier)
    cur.execute("DELETE FROM fichiers WHERE id_fichier = %s", (id_fichier,))
    conn.commit()
    cur.close()
    conn.close()
    return True

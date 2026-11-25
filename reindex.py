#!/usr/bin/env python3
"""
reindex.py
Script de réindexation du Vector Store pour le projet DataIA.
- Supprime les anciens index vectoriels incompatibles (dimension != 768)
- Réindexe les fichiers (CSV / Excel) avec Ollama (nomic-embed-text)
- Applique le préfixe requis 'search_document: '
- Sauvegarde les index FAISS avec dimension 768
"""

import os
import sys
import argparse
import pandas as pd
import mysql.connector

from config_ia import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, RAG_TOP_K
from ollama_rag import (
    OllamaNomicEmbeddings,
    load_or_build_vector_store,
    get_vector_store_dir,
    EXPECTED_EMBEDDING_DIM
)


def get_db_connection():
    """Connexion optionnelle à la base de données DataIA."""
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="dataia"
        )
    except Exception:
        return None


def get_files_to_index(upload_folder="uploads"):
    """
    Récupère la liste des fichiers à indexer.
    Tente la base de données en premier, sinon parcourt le dossier uploads.
    """
    files = []
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id_fichier, nom_fichier, chemin_fichier FROM fichiers")
            rows = cursor.fetchall()
            for r in rows:
                if os.path.exists(r['chemin_fichier']):
                    files.append(r)
            cursor.close()
            conn.close()
            if files:
                print(f"[Info] {len(files)} fichier(s) trouvé(s) depuis la base de données.")
                return files
        except Exception as e:
            print(f"[Avertissement] Erreur lecture DB ({e}), bascule sur le dossier uploads.")

    # Fallback : scan direct du dossier uploads
    if os.path.exists(upload_folder):
        file_id = 1
        for fname in os.listdir(upload_folder):
            fpath = os.path.join(upload_folder, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(('.csv', '.xlsx', '.xls')):
                files.append({
                    "id_fichier": file_id,
                    "nom_fichier": fname,
                    "chemin_fichier": fpath
                })
                file_id += 1
        print(f"[Info] {len(files)} fichier(s) trouvé(s) dans le dossier {upload_folder}.")

    return files


def reindex_all(upload_folder="uploads", force=True):
    print("=" * 60)
    print("        RÉINDEXATION DU VECTOR STORE DATAIA (OLLAMA)")
    print("=" * 60)
    print(f"URL Ollama       : {OLLAMA_BASE_URL}")
    print(f"Modèle Embedding : {OLLAMA_EMBED_MODEL}")
    print(f"Dimension cible  : {EXPECTED_EMBEDDING_DIM}")
    print("=" * 60)

    # 1. Vérification de l'accès à Ollama
    embed_model = OllamaNomicEmbeddings()
    print("\n[1/3] Verification de la connexion a Ollama...")
    try:
        test_vec = embed_model.embed_query("test de connexion")
        dim = len(test_vec)
        print(f"[OK] Connexion reussie a Ollama ! Dimension retournee : {dim}")
        if dim != EXPECTED_EMBEDDING_DIM:
            print(f"[!] Attention : La dimension recue ({dim}) differe de {EXPECTED_EMBEDDING_DIM}.")
    except Exception as e:
        print(f"[ERREUR] Impossible de contacter Ollama sur {OLLAMA_BASE_URL} : {e}")
        print("Assurez-vous qu'Ollama est demarre ('ollama serve') et que le modele 'nomic-embed-text' est installe :")
        print("  ollama pull nomic-embed-text")
        sys.exit(1)

    # 2. Récupération des fichiers
    print("\n[2/3] Recherche des fichiers a indexer...")
    files = get_files_to_index(upload_folder)
    if not files:
        print("Aucun fichier de donnees (CSV ou Excel) trouve a indexer.")
        return

    # 3. Réindexation fichier par fichier
    print(f"\n[3/3] Reindexation de {len(files)} fichier(s)...")
    success_count = 0
    for f in files:
        file_id = f["id_fichier"]
        name = f["nom_fichier"]
        path = f["chemin_fichier"]
        print(f"\n- Traitement de [ID {file_id}] '{name}'...")

        try:
            # Lecture du fichier avec détection automatique du séparateur (; ou ,)
            if path.endswith('.csv'):
                try:
                    df = pd.read_csv(path, sep=None, engine='python', encoding='utf-8-sig')
                except Exception:
                    df = pd.read_csv(path, sep=';', encoding='utf-8-sig')
            else:
                df = pd.read_excel(path)
            texts = df.astype(str).apply(
                lambda x: " | ".join(f"{col}: {val}" for col, val in x.items()),
                axis=1
            ).tolist()

            if not texts:
                print(f"  [!] Fichier vide ou sans lignes, ignore.")
                continue

            print(f"  Generation des embeddings pour {len(texts)} lignes (prefixe 'search_document: ')...")
            vs = load_or_build_vector_store(
                file_id=file_id,
                texts=texts,
                embed_model=embed_model,
                upload_folder=upload_folder,
                force_rebuild=force
            )
            print(f"  [OK] Index FAISS cree et sauvegarde avec succes dans '{get_vector_store_dir(upload_folder, file_id)}'.")
            success_count += 1
        except Exception as e:
            print(f"  [ERREUR] Erreur lors de l'indexation de {name} : {e}")

    print("\n" + "=" * 60)
    print(f"REINDEXATION TERMINEE : {success_count}/{len(files)} fichier(s) reindexe(s) avec succes.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Réindexation des fichiers pour DataIA avec Ollama (nomic-embed-text)")
    parser.add_argument("--folder", default="uploads", help="Dossier contenant les fichiers et index")
    parser.add_argument("--no-force", action="store_true", help="Ne pas forcer la suppression des index déjà existants")
    args = parser.parse_args()

    reindex_all(upload_folder=args.folder, force=not args.no_force)

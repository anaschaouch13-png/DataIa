#!/usr/bin/env python3
"""
reindex.py — Réindexation FAISS de tous les fichiers existants.

Pourquoi ? Le passage à nomic-embed-text change la dimension des vecteurs (768).
Un index construit avec un autre modèle d'embeddings est incompatible : il faut
recalculer les vecteurs de toutes les lignes avec le préfixe "search_document: ".

Usage (depuis le dossier DataIa, venv activé) :
    python reindex.py              # reconstruit tous les index
    python reindex.py --no-force   # ne reconstruit que les index absents ou invalides

Les fichiers référencés en base mais absents du disque sont signalés (pas supprimés).
"""

import argparse
import os
import sys
import time

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from services import rag
from services.db import get_db_connection
from services.llm import OllamaIndisponibleError, get_embeddings
from services.parsers import charger_dataframe


def chemin_absolu(chemin: str) -> str:
    chemin = chemin.replace('\\', os.sep)
    return chemin if os.path.isabs(chemin) else os.path.join(config.BASE_DIR, chemin)


def reindexer_tout(forcer: bool = True) -> int:
    print("=" * 64)
    print("  RÉINDEXATION FAISS — DataIA")
    print(f"  Ollama : {config.OLLAMA_BASE_URL} | embeddings : {config.OLLAMA_EMBED_MODEL} "
          f"| dimension attendue : {config.EMBEDDING_DIM}")
    print("=" * 64)

    # 1. Ollama joignable et dimension correcte ?
    try:
        dim = len(get_embeddings().embed_query("test"))
    except OllamaIndisponibleError as e:
        print(f"[ERREUR] {e}\n  -> Lancez Ollama ('ollama serve') puis 'ollama pull {config.OLLAMA_EMBED_MODEL}'.")
        return 1
    print(f"[OK] Ollama répond, dimension des vecteurs = {dim}")
    if dim != config.EMBEDDING_DIM:
        print(f"[ERREUR] Dimension {dim} différente de EMBEDDING_DIM={config.EMBEDDING_DIM} (.env).")
        return 1

    # 2. Fichiers enregistrés en base
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id_fichier, id_utilisateur, nom_fichier, chemin_fichier FROM fichiers ORDER BY id_fichier")
    fichiers = cur.fetchall()
    cur.close()
    conn.close()

    ok, absents, erreurs = 0, [], []
    for f in fichiers:
        chemin = chemin_absolu(f["chemin_fichier"])
        etiquette = f"[ID {f['id_fichier']}] {f['nom_fichier']} (utilisateur {f['id_utilisateur']})"
        if not os.path.isfile(chemin):
            absents.append(etiquette)
            print(f"  [ABSENT] {etiquette} -> {f['chemin_fichier']} introuvable sur le disque")
            continue
        try:
            debut = time.time()
            textes = rag.lignes_en_textes(charger_dataframe(chemin))
            rag.charger_ou_construire_index(f["id_fichier"], textes, forcer=forcer)
            print(f"  [OK] {etiquette} : {len(textes)} lignes indexées en {time.time() - debut:.0f} s")
            ok += 1
        except Exception as e:
            erreurs.append(etiquette)
            print(f"  [ERREUR] {etiquette} : {e}")

    print("=" * 64)
    print(f"  Résultat : {ok} réindexé(s), {len(absents)} absent(s) du disque, {len(erreurs)} erreur(s)")
    if absents:
        print("  Fichiers perdus (lignes conservées en base, à réimporter par l'utilisateur) :")
        for a in absents:
            print(f"    - {a}")
    print("=" * 64)
    return 0 if not erreurs else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Réindexation FAISS (nomic-embed-text, 768 dim.)")
    parser.add_argument("--no-force", action="store_true",
                        help="ne reconstruit que les index absents ou de mauvaise dimension")
    args = parser.parse_args()
    sys.exit(reindexer_tout(forcer=not args.no_force))

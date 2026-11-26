"""
services/rag.py — Index vectoriel FAISS (RAG) par fichier uploadé.

Chaque ligne du tableau devient un texte "colonne: valeur | colonne: valeur ...",
transformé en vecteur de 768 dimensions par nomic-embed-text, puis stocké dans
un index FAISS sauvegardé sur disque (un dossier par fichier).

Si un ancien index a une autre dimension (ex. 1024 avec l'ancien embedding
Mistral), il est supprimé puis reconstruit automatiquement.
"""

import logging
import os
import re
import shutil
from typing import List

import pandas as pd
from langchain_community.vectorstores import FAISS

from config import EMBEDDING_DIM, RAG_TOP_K, VECTOR_FOLDER
from services.llm import get_embeddings

log = logging.getLogger("dataia.rag")


def dossier_index(file_id: int) -> str:
    """Dossier de l'index FAISS d'un fichier."""
    return os.path.join(VECTOR_FOLDER, f"file_{file_id}")


def lignes_en_textes(df: pd.DataFrame) -> List[str]:
    """Transforme chaque ligne du DataFrame en texte indexable."""
    return df.astype(str).apply(
        lambda ligne: " | ".join(f"{col}: {val}" for col, val in ligne.items()), axis=1
    ).tolist()


def charger_ou_construire_index(file_id: int, textes: List[str], forcer: bool = False) -> FAISS:
    """
    Charge l'index existant s'il est valide (dimension 768), sinon le (re)construit.
    `allow_dangerous_deserialization=True` : l'index est créé par notre propre
    serveur dans un dossier non exposé, il n'a donc pas d'origine externe.
    """
    embeddings = get_embeddings()
    dossier = dossier_index(file_id)

    if not forcer and os.path.isdir(dossier):
        try:
            index = FAISS.load_local(dossier, embeddings, allow_dangerous_deserialization=True)
            if index.index.d == EMBEDDING_DIM:
                return index
            log.warning("Index %s : dimension %s != %s, reconstruction.", dossier, index.index.d, EMBEDDING_DIM)
        except Exception as e:
            log.warning("Index %s illisible (%s), reconstruction.", dossier, e)
        shutil.rmtree(dossier, ignore_errors=True)

    if not textes:
        raise ValueError("Aucune ligne à indexer.")
    index = FAISS.from_texts(textes, embeddings)
    os.makedirs(dossier, exist_ok=True)
    index.save_local(dossier)
    log.info("Index FAISS construit : %s (%d lignes, dim %d)", dossier, len(textes), index.index.d)
    return index


def rechercher(index: FAISS, question: str, nb_lignes: int, k: int = RAG_TOP_K) -> List[str]:
    """Renvoie les k extraits les plus proches de la question (similarité vectorielle)."""
    k = max(1, min(nb_lignes, k))
    return [doc.page_content for doc in index.similarity_search(question, k=k)]


def lignes_exactes(df: pd.DataFrame, question: str, maximum: int = 5) -> List[int]:
    """
    Recherche par mot-clé : lignes dont une cellule est EXACTEMENT un mot/identifiant de
    la question (« INV-10002 », « Gamma Store »). Les embeddings sont mauvais sur les
    identifiants : testé, la ligne INV-10002 n'était pas dans les 8 extraits vectoriels.
    """
    q = " " + re.sub(r"\s+", " ", question.lower()) + " "
    trouvees: List[int] = []
    for colonne in df.columns:
        valeurs = df[colonne].dropna().astype(str).str.strip().str.lower()
        valeurs = valeurs[valeurs.str.len() >= 4]                   # évite « 1 », « IT »…
        if valeurs.nunique() < 0.5 * len(df):                       # seulement les colonnes très variées
            continue                                                # (identifiants, noms), pas les catégories
        for i, v in valeurs.items():
            if re.search(r"(?<![\w-])" + re.escape(v) + r"(?![\w-])", q):
                trouvees.append(i)
                if len(trouvees) >= maximum:
                    return trouvees
    return trouvees


def recherche_hybride(index: FAISS, df: pd.DataFrame, textes: List[str], question: str,
                      k: int = RAG_TOP_K) -> List[str]:
    """Lignes trouvées par mot-clé exact d'abord, puis complétées par la similarité vectorielle."""
    # Texte reconstruit depuis la ligne du tableau (les textes indexés peuvent contenir d'autres
    # tableaux ou du texte libre : leurs positions ne correspondent pas aux lignes de df)
    exactes = [" | ".join(f"{c}: {v}" for c, v in df.astype(str).iloc[i].items()) for i in lignes_exactes(df, question)]
    vectorielles = [t for t in rechercher(index, question, len(textes), k) if t not in exactes]
    return (exactes + vectorielles)[:k]


def supprimer_index(file_id: int):
    """Supprime l'index vectoriel d'un fichier (appelé à la suppression du fichier)."""
    shutil.rmtree(dossier_index(file_id), ignore_errors=True)

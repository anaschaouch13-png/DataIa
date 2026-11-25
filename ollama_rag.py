"""
ollama_rag.py
Module fournissant :
- OllamaNomicEmbeddings : embeddings avec préfixes nomic-embed-text ("search_document: " et "search_query: ")
- Gestion et persistance du vector store FAISS (dimension 768)
- Génération de chat via l'endpoint OpenAI-compatible d'Ollama
"""

import os
import shutil
import requests
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from config_ia import (
    OLLAMA_BASE_URL,
    OLLAMA_GEN_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_API_KEY,
    OLLAMA_CONFIG,
    SYSTEM_PROMPT,
    RAG_TOP_K
)

EXPECTED_EMBEDDING_DIM = 768  # nomic-embed-text dimension


class OllamaNomicEmbeddings(Embeddings):
    """
    Embeddings personnalisés pour nomic-embed-text via Ollama.
    Ajoute impérativement les préfixes Nomic :
    - 'search_document: ' pour les documents/lignes indexés
    - 'search_query: ' pour la question utilisateur
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120
    ):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self.model = model or OLLAMA_EMBED_MODEL
        self.timeout = timeout

    def _call_embed_api(self, inputs: List[str]) -> List[List[float]]:
        """
        Appelle l'endpoint /api/embed d'Ollama (ou /v1/embeddings / /api/embeddings en fallback).
        """
        # 1. Tentative avec l'endpoint natif /api/embed (batch)
        embed_url = f"{self.base_url}/api/embed"
        try:
            resp = requests.post(
                embed_url,
                json={"model": self.model, "input": inputs},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                if "embeddings" in data and len(data["embeddings"]) == len(inputs):
                    return data["embeddings"]
        except Exception:
            pass

        # 2. Fallback avec l'endpoint OpenAI-compatible /v1/embeddings
        v1_url = f"{self.base_url}/v1/embeddings"
        try:
            headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
            resp = requests.post(
                v1_url,
                json={"model": self.model, "input": inputs},
                headers=headers,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    return [item["embedding"] for item in data["data"]]
        except Exception:
            pass

        # 3. Fallback unitaire /api/embeddings
        single_url = f"{self.base_url}/api/embeddings"
        results = []
        for text in inputs:
            resp = requests.post(
                single_url,
                json={"model": self.model, "prompt": text},
                timeout=self.timeout
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Indexation de documents avec le préfixe search_document: """
        if not texts:
            return []
        prefixed = [f"search_document: {t}" for t in texts]

        # Traitement par lots (batch) de 32 pour éviter les surcharges mémoires
        batch_size = 32
        all_embeddings: List[List[float]] = []
        for i in range(0, len(prefixed), batch_size):
            chunk = prefixed[i:i + batch_size]
            embeddings = self._call_embed_api(chunk)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Requête utilisateur avec le préfixe search_query: """
        prefixed = f"search_query: {text}"
        res = self._call_embed_api([prefixed])
        return res[0]


def get_vector_store_dir(upload_folder: str, file_id: int) -> str:
    """Retourne le répertoire de stockage de l'index FAISS pour un fichier donné."""
    return os.path.join(upload_folder, "vector_indices", f"file_{file_id}")


def load_or_build_vector_store(
    file_id: int,
    texts: List[str],
    embed_model: OllamaNomicEmbeddings,
    upload_folder: str = "uploads",
    force_rebuild: bool = False
) -> FAISS:
    """
    Charge l'index vectoriel existant ou le reconstruit.
    Si un ancien index n'a pas la bonne dimension (768 pour nomic-embed-text),
    il est automatiquement supprimé et reconstruit.
    """
    index_dir = get_vector_store_dir(upload_folder, file_id)

    if not force_rebuild and os.path.exists(index_dir):
        try:
            vs = FAISS.load_local(index_dir, embed_model, allow_dangerous_deserialization=True)
            # Vérification de la dimension du modèle nomic-embed-text (768)
            current_dim = vs.index.d
            if current_dim == EXPECTED_EMBEDDING_DIM:
                return vs
            else:
                print(f"[RAG] Dimension invalide détectée ({current_dim} != {EXPECTED_EMBEDDING_DIM}). Suppression de l'ancien index.")
                shutil.rmtree(index_dir, ignore_errors=True)
        except Exception as e:
            print(f"[RAG] Impossible de charger l'index existant ({e}). Reconstruction en cours...")
            shutil.rmtree(index_dir, ignore_errors=True)

    # Construction d'un nouvel index avec nomic-embed-text (dimension 768)
    os.makedirs(os.path.dirname(index_dir), exist_ok=True)
    vector_store = FAISS.from_texts(texts, embed_model)
    vector_store.save_local(index_dir)
    return vector_store


def delete_vector_store(upload_folder: str, file_id: int):
    """Supprime l'index vectoriel d'un fichier."""
    index_dir = get_vector_store_dir(upload_folder, file_id)
    if os.path.exists(index_dir):
        shutil.rmtree(index_dir, ignore_errors=True)


def call_ollama_chat(prompt_final: str) -> str:
    """
    Envoie la requête de chat à Ollama via l'endpoint compatible OpenAI.
    Utilise le modèle configuré (qwen2.5:3b).
    """
    import time
    base_url = OLLAMA_BASE_URL.rstrip("/")
    v1_url = f"{base_url}/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OLLAMA_API_KEY}"
    }

    payload = {
        "model": OLLAMA_GEN_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_final}
        ],
        "temperature": OLLAMA_CONFIG.get("temperature", 0.2),
        "top_p": OLLAMA_CONFIG.get("top_p", 0.9),
        "max_tokens": OLLAMA_CONFIG.get("max_tokens", 1000)
    }

    print(f"\n>>> [OLLAMA LOCAL] Envoi de la requete au modele local '{OLLAMA_GEN_MODEL}' ({v1_url})...")
    start_time = time.time()

    try:
        # Appel vers l'endpoint OpenAI-compatible
        resp = requests.post(v1_url, json=payload, headers=headers, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            elapsed = time.time() - start_time
            print(f">>> [OLLAMA LOCAL] Reponse generee par '{OLLAMA_GEN_MODEL}' en {elapsed:.2f}s (100% hors ligne).\n")
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Ollama] Echec /v1/chat/completions : {e}, tentative /api/chat...")

    # Fallback vers l'endpoint natif /api/chat d'Ollama
    native_url = f"{base_url}/api/chat"
    native_payload = {
        "model": OLLAMA_GEN_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_final}
        ],
        "stream": False,
        "options": {
            "temperature": OLLAMA_CONFIG.get("temperature", 0.2),
            "top_p": OLLAMA_CONFIG.get("top_p", 0.9),
            "num_predict": OLLAMA_CONFIG.get("max_tokens", 1000)
        }
    }

    resp = requests.post(native_url, json=native_payload, timeout=120)
    resp.raise_for_status()
    elapsed = time.time() - start_time
    print(f">>> [OLLAMA LOCAL] Reponse generee par '{OLLAMA_GEN_MODEL}' via /api/chat en {elapsed:.2f}s (100% hors ligne).\n")
    return resp.json()["message"]["content"]

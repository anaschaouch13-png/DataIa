"""
services/llm.py — Accès au LLM local et aux embeddings via Ollama (langchain-ollama).

- ChatOllama(qwen2.5:3b, temperature=0, num_ctx=4096) pour générer les réponses ;
- OllamaEmbeddings(nomic-embed-text) pour le RAG, avec les préfixes imposés par
  nomic : "search_document: " pour les chunks indexés, "search_query: " pour les questions ;
- vérification qu'Ollama est joignable : si Ollama est arrêté, on lève
  `OllamaIndisponibleError` (message clair côté utilisateur, pas de crash).

Aucune clé API : tout tourne en local sur la machine.
"""

import logging
import time
from typing import List, Optional

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from config import (OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL,
                    OLLAMA_NUM_CTX, OLLAMA_NUM_PREDICT, OLLAMA_TEMPERATURE,
                    OLLAMA_TIMEOUT)

log = logging.getLogger("dataia.llm")


class OllamaIndisponibleError(RuntimeError):
    """Ollama ne répond pas, ou le modèle demandé n'est pas installé."""

    def __init__(self, message: str, cle_message: str = "ollama_indisponible", modele: str = ""):
        super().__init__(message)
        self.cle_message = cle_message  # clé du message traduit (services/langue.py)
        self.modele = modele


# ---------------------------------------------------------------------------
# Vérification de l'état d'Ollama
# ---------------------------------------------------------------------------
def verifier_ollama(modeles_requis: Optional[List[str]] = None) -> dict:
    """
    Interroge /api/tags (réponse rapide, ne charge aucun modèle).
    Retourne {"ok": bool, "modeles": [...], "manquants": [...], "erreur": str}.
    """
    modeles_requis = modeles_requis or [OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL]
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        installes = [m["name"] for m in resp.json().get("models", [])]
    except Exception as e:  # serveur arrêté, port fermé, timeout...
        return {"ok": False, "modeles": [], "manquants": modeles_requis, "erreur": str(e)}

    def _present(nom: str) -> bool:
        # "nomic-embed-text" correspond à "nomic-embed-text:latest"
        return any(i == nom or i.split(":")[0] == nom or i == f"{nom}:latest" for i in installes)

    manquants = [m for m in modeles_requis if not _present(m)]
    return {"ok": not manquants, "modeles": installes, "manquants": manquants, "erreur": ""}


def _assurer_ollama(modele: str):
    """Lève OllamaIndisponibleError si Ollama est arrêté ou si le modèle manque."""
    etat = verifier_ollama([modele])
    if etat["erreur"]:
        raise OllamaIndisponibleError(f"Ollama injoignable sur {OLLAMA_BASE_URL} : {etat['erreur']}")
    if etat["manquants"]:
        raise OllamaIndisponibleError(f"Modèle '{modele}' absent d'Ollama",
                                      cle_message="modele_absent", modele=modele)


def _est_erreur_connexion(exc: Exception) -> bool:
    """Reconnaît les erreurs réseau (Ollama arrêté pendant un appel)."""
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, ConnectionError))


# ---------------------------------------------------------------------------
# LLM de chat
# ---------------------------------------------------------------------------
_chat_llm: Optional[ChatOllama] = None


def get_chat_llm() -> ChatOllama:
    """Instance unique (créée au premier appel) du modèle de chat."""
    global _chat_llm
    if _chat_llm is None:
        _chat_llm = ChatOllama(
            model=OLLAMA_CHAT_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=OLLAMA_TEMPERATURE,   # 0 : même question -> même réponse
            num_ctx=OLLAMA_NUM_CTX,           # 4096 tokens : compromis RAM (8 Go) / contexte
            num_predict=OLLAMA_NUM_PREDICT,
            client_kwargs={"timeout": OLLAMA_TIMEOUT},
        )
    return _chat_llm


def generer_reponse(prompt_systeme: str, prompt_utilisateur: str) -> str:
    """
    Envoie un message système + un message utilisateur au LLM et renvoie le texte.
    Lève OllamaIndisponibleError si Ollama ne répond pas.
    """
    _assurer_ollama(OLLAMA_CHAT_MODEL)
    debut = time.time()
    try:
        reponse = get_chat_llm().invoke([
            SystemMessage(content=prompt_systeme),
            HumanMessage(content=prompt_utilisateur),
        ])
    except Exception as e:
        if _est_erreur_connexion(e):
            raise OllamaIndisponibleError(f"Ollama a cessé de répondre : {e}") from e
        raise
    log.info("Réponse de %s générée en %.1f s", OLLAMA_CHAT_MODEL, time.time() - debut)
    return (reponse.content or "").strip()


# ---------------------------------------------------------------------------
# Embeddings nomic-embed-text avec préfixes
# ---------------------------------------------------------------------------
class NomicEmbeddings(OllamaEmbeddings):
    """
    OllamaEmbeddings + préfixes de tâche requis par nomic-embed-text.
    Sans ces préfixes, la qualité de la recherche baisse (le modèle a été entraîné avec).
    """

    PREFIXE_DOCUMENT: str = "search_document: "
    PREFIXE_REQUETE: str = "search_query: "
    # Envoi par lots : envoyer 1000 lignes en une seule requête fait planter le
    # processus interne d'Ollama sur une machine 8 Go (constaté pendant la réindexation).
    TAILLE_LOT: int = 32

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vecteurs: List[List[float]] = []
        for i in range(0, len(texts), self.TAILLE_LOT):
            lot = [self.PREFIXE_DOCUMENT + t for t in texts[i:i + self.TAILLE_LOT]]
            vecteurs.extend(super().embed_documents(lot))
        return vecteurs

    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(self.PREFIXE_REQUETE + text)


_embeddings: Optional[NomicEmbeddings] = None


def get_embeddings() -> NomicEmbeddings:
    """Instance unique du modèle d'embeddings (vérifie Ollama avant usage)."""
    global _embeddings
    _assurer_ollama(OLLAMA_EMBED_MODEL)
    if _embeddings is None:
        _embeddings = NomicEmbeddings(
            model=OLLAMA_EMBED_MODEL,
            base_url=OLLAMA_BASE_URL,
            client_kwargs={"timeout": OLLAMA_TIMEOUT},
        )
    return _embeddings

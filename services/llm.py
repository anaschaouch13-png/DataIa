"""
services/llm.py — Accès au LLM local et aux embeddings via Ollama (langchain-ollama).

- ChatOllama(qwen2.5:3b, temperature=0, num_ctx=4096) pour générer les réponses ;
- OllamaEmbeddings(nomic-embed-text) pour le RAG, avec les préfixes imposés par
  nomic : "search_document: " pour les chunks indexés, "search_query: " pour les questions ;
- vérification qu'Ollama est joignable : si Ollama est arrêté, on lève
  `OllamaIndisponibleError` (message clair côté utilisateur, pas de crash).

Aucune clé API : tout tourne en local sur la machine.
"""

import contextvars
import json
import logging
import threading
import time
from typing import List, Optional

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings

from config import (OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL,
                    OLLAMA_KEEP_ALIVE, OLLAMA_NUM_CTX, OLLAMA_NUM_GPU,
                    OLLAMA_NUM_PREDICT, OLLAMA_TEMPERATURE, OLLAMA_TIMEOUT)

log = logging.getLogger("dataia.llm")

# Trace des appels LLM de la requête en cours (tokens, durées) : sert à mesurer
# les performances et à les renvoyer au frontend. Une liste par requête.
TRACE_APPELS: contextvars.ContextVar = contextvars.ContextVar("trace_appels", default=None)


def demarrer_trace() -> list:
    trace: list = []
    TRACE_APPELS.set(trace)
    return trace


def _tracer(etape: str, reponse, debut: float):
    trace = TRACE_APPELS.get()
    meta = getattr(reponse, "response_metadata", None) or {}
    entree = {
        "etape": etape,
        "duree_s": round(time.time() - debut, 2),
        "prompt_tokens": meta.get("prompt_eval_count"),
        "sortie_tokens": meta.get("eval_count"),
    }
    log.info("LLM %s : %.1f s, %s tokens en entrée, %s en sortie", etape, entree["duree_s"],
             entree["prompt_tokens"], entree["sortie_tokens"])
    if trace is not None:
        trace.append(entree)


def keep_alive_secondes(valeur: str) -> int:
    """« 30m » -> 1800, « 2h » -> 7200, « 90 » -> 90, « -1 » -> -1 (toujours chargé)."""
    valeur = str(valeur).strip().lower()
    unites = {"s": 1, "m": 60, "h": 3600}
    if valeur and valeur[-1] in unites:
        return int(float(valeur[:-1]) * unites[valeur[-1]])
    return int(valeur)


def _options_communes() -> dict:
    """
    Options identiques pour TOUS les appels au modèle de chat. Important : si num_ctx
    ou num_gpu changent d'un appel à l'autre, Ollama recharge le modèle (~10 s).
    """
    options = {"model": OLLAMA_CHAT_MODEL, "base_url": OLLAMA_BASE_URL,
               "temperature": OLLAMA_TEMPERATURE, "num_ctx": OLLAMA_NUM_CTX,
               "keep_alive": OLLAMA_KEEP_ALIVE, "client_kwargs": {"timeout": OLLAMA_TIMEOUT}}
    if OLLAMA_NUM_GPU != "":
        options["num_gpu"] = int(OLLAMA_NUM_GPU)
    return options


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


_DERNIERE_VERIF_OK: dict = {}   # modèle -> horodatage de la dernière vérification réussie
DUREE_CACHE_VERIF_S = 30


def _assurer_ollama(modele: str):
    """
    Lève OllamaIndisponibleError si Ollama est arrêté ou si le modèle manque.
    Une vérification réussie est gardée 30 s (une question = 2 à 3 appels LLM) ;
    si Ollama tombe entre-temps, l'appel lui-même échoue et l'erreur est convertie.
    """
    if time.time() - _DERNIERE_VERIF_OK.get(modele, 0) < DUREE_CACHE_VERIF_S:
        return
    etat = verifier_ollama([modele])
    if etat["erreur"]:
        raise OllamaIndisponibleError(f"Ollama injoignable sur {OLLAMA_BASE_URL} : {etat['erreur']}")
    if etat["manquants"]:
        raise OllamaIndisponibleError(f"Modèle '{modele}' absent d'Ollama",
                                      cle_message="modele_absent", modele=modele)
    _DERNIERE_VERIF_OK[modele] = time.time()


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
        # temperature 0 : même question -> même réponse ; num_ctx 4096 : compromis RAM / contexte
        _chat_llm = ChatOllama(num_predict=OLLAMA_NUM_PREDICT, **_options_communes())
    return _chat_llm


def _invoquer(llm: ChatOllama, prompt_systeme: str, prompt_utilisateur: str, etape: str):
    """Appel commun : vérification d'Ollama, gestion des pannes, trace des tokens."""
    _assurer_ollama(OLLAMA_CHAT_MODEL)
    debut = time.time()
    try:
        reponse = llm.invoke([SystemMessage(content=prompt_systeme),
                              HumanMessage(content=prompt_utilisateur)])
    except Exception as e:
        if _est_erreur_connexion(e):
            raise OllamaIndisponibleError(f"Ollama a cessé de répondre : {e}") from e
        raise
    _tracer(etape, reponse, debut)
    return reponse


def generer_reponse(prompt_systeme: str, prompt_utilisateur: str, etape: str = "redaction",
                    max_tokens: Optional[int] = None) -> str:
    """
    Envoie un message système + un message utilisateur au LLM et renvoie le texte.
    Lève OllamaIndisponibleError si Ollama ne répond pas.
    """
    llm = get_chat_llm() if max_tokens is None else ChatOllama(num_predict=max_tokens, **_options_communes())
    return (_invoquer(llm, prompt_systeme, prompt_utilisateur, etape).content or "").strip()


def generer_json(schema: dict, prompt_systeme: str, prompt_utilisateur: str,
                 etape: str = "routage", max_tokens: int = 200) -> dict:
    """
    Sortie JSON CONTRAINTE : le paramètre `format` d'Ollama reçoit un JSON schema.
    Ollama restreint la génération token par token (grammaire) : le modèle ne peut
    produire qu'un JSON conforme (ex. un nom de colonne pris dans un `enum`).
    """
    llm = ChatOllama(format=schema, num_predict=max_tokens, **_options_communes())
    texte = _invoquer(llm, prompt_systeme, prompt_utilisateur, etape).content or "{}"
    return json.loads(texte)


def prechauffer():
    """
    Charge les modèles en mémoire au démarrage de Flask (dans un thread) pour que la
    première question de l'utilisateur ne paie pas le chargement (~10-20 s).
    """
    def _charger():
        try:
            if not verifier_ollama()["ok"]:
                return
            debut = time.time()
            get_chat_llm().invoke("OK")
            get_embeddings().embed_query("OK")
            log.info("Modèles préchauffés en %.1f s (keep_alive=%s, num_gpu=%s)",
                     time.time() - debut, OLLAMA_KEEP_ALIVE, OLLAMA_NUM_GPU or "auto")
        except Exception as e:  # le préchauffage ne doit jamais empêcher le démarrage
            log.warning("Préchauffage impossible : %s", e)
    threading.Thread(target=_charger, daemon=True, name="prechauffage-ollama").start()


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
        # OllamaEmbeddings attend keep_alive en SECONDES (entier), ChatOllama accepte "30m"
        options = {"model": OLLAMA_EMBED_MODEL, "base_url": OLLAMA_BASE_URL,
                   "keep_alive": keep_alive_secondes(OLLAMA_KEEP_ALIVE),
                   "client_kwargs": {"timeout": OLLAMA_TIMEOUT}}
        if OLLAMA_NUM_GPU != "":
            options["num_gpu"] = int(OLLAMA_NUM_GPU)
        _embeddings = NomicEmbeddings(**options)
    return _embeddings

"""
config.py — Configuration centrale de DataIA.

Toutes les valeurs qui dépendent de la machine (URL d'Ollama, noms des modèles,
connexion MySQL, chemins, clé secrète Flask) sont lues depuis le fichier `.env`.
Aucune de ces valeurs ne doit être écrite en dur ailleurs dans le code :
les autres modules importent ce fichier.

Voir `.env.example` pour la liste complète des variables.
"""

import os
import secrets
import sys

from dotenv import load_dotenv

# Dossier racine du backend (là où se trouve ce fichier)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Chargement du .env situé à côté de ce fichier (indépendant du dossier de lancement)
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env_int(nom: str, defaut: int) -> int:
    """Lit une variable d'environnement entière avec une valeur par défaut."""
    try:
        return int(os.getenv(nom, str(defaut)))
    except ValueError:
        return defaut


def _env_float(nom: str, defaut: float) -> float:
    """Lit une variable d'environnement décimale avec une valeur par défaut."""
    try:
        return float(os.getenv(nom, str(defaut)))
    except ValueError:
        return defaut


def _chemin(nom: str, defaut: str) -> str:
    """Retourne un chemin absolu ; un chemin relatif est résolu depuis BASE_DIR."""
    valeur = os.getenv(nom, defaut)
    return os.path.normpath(valeur if os.path.isabs(valeur) else os.path.join(BASE_DIR, valeur))


# ================== Flask ==================
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    # Pas de clé en dur : on génère une clé aléatoire pour cette exécution.
    # Conséquence : les sessions sont perdues à chaque redémarrage -> à définir dans .env.
    SECRET_KEY = secrets.token_hex(32)
    print("[Config] ATTENTION : SECRET_KEY absente du .env, clé temporaire générée.", file=sys.stderr)

FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 20)

# ================== MySQL ==================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": _env_int("DB_PORT", 3306),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "dataia"),
    "charset": "utf8mb4",
}

# ================== Ollama (LLM local) ==================
# 127.0.0.1 plutôt que localhost : sous Windows, « localhost » tente d'abord IPv6 (::1),
# or Ollama n'écoute qu'en IPv4 -> 2,3 s perdues à chaque connexion (mesuré en Phase 3).
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TEMPERATURE = _env_float("OLLAMA_TEMPERATURE", 0.0)   # 0 = réponses déterministes
OLLAMA_NUM_CTX = _env_int("OLLAMA_NUM_CTX", 4096)            # fenêtre de contexte (tokens)
OLLAMA_NUM_PREDICT = _env_int("OLLAMA_NUM_PREDICT", 800)     # longueur max de la réponse
OLLAMA_TIMEOUT = _env_int("OLLAMA_TIMEOUT", 180)             # secondes (CPU lent au 1er appel)
# Nombre de couches envoyées au GPU. Mesuré sur la MX130 (2 Go) : le découpage
# CPU/GPU automatique donne 3,2 tokens/s, le 100 % CPU (0) donne 8,7 tokens/s.
# Chaîne vide = laisser Ollama décider.
OLLAMA_NUM_GPU = os.getenv("OLLAMA_NUM_GPU", "0")
# Durée pendant laquelle Ollama garde le modèle en RAM après un appel
# (évite ~10 s de rechargement à chaque question).
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# Reformulation de la réponse chiffrée par le LLM (1) ou phrase modèle seule (0)
REFORMULATION_LLM = os.getenv("REFORMULATION_LLM", "1") == "1"

# ================== RAG / FAISS ==================
RAG_TOP_K = _env_int("RAG_TOP_K", 5)
EMBEDDING_DIM = _env_int("EMBEDDING_DIM", 768)  # dimension des vecteurs nomic-embed-text

# ================== Chemins ==================
UPLOAD_FOLDER = _chemin("UPLOAD_FOLDER", "uploads")
VECTOR_FOLDER = _chemin("VECTOR_FOLDER", os.path.join("uploads", "vector_indices"))
REPORT_FOLDER = _chemin("REPORT_FOLDER", os.path.join("uploads", "rapports"))

GRAPH_FOLDER = _chemin("GRAPH_FOLDER", os.path.join("uploads", "graphiques"))  # PNG + JSON Plotly
# Données nettoyées passées aux modèles ML (CSV + Excel + rapport), une sous-dossier par utilisateur
EXPORT_FOLDER = _chemin("EXPORT_FOLDER", os.path.join("exports", "donnees_nettoyees"))
# Modèle churn (Pipeline scikit-learn) et ses métadonnées, entraînés par entrainer_churn.py
CHURN_MODEL_PATH = _chemin("CHURN_MODEL_PATH", os.path.join("..", "a_integrer", "modele_banque", "modele_churn_pipeline.joblib"))
CHURN_DATA_PATH = _chemin("CHURN_DATA_PATH", os.path.join("..", "a_integrer", "modele_banque", "Bank-Customer-Churn-Prediction.csv"))
BACKUP_FOLDER = _chemin("BACKUP_FOLDER", "backups")          # sauvegardes mysqldump
MIGRATIONS_FOLDER = _chemin("MIGRATIONS_FOLDER", "migrations")  # scripts SQL de migration
# Chemin de mysqldump (WampServer ne l'ajoute pas au PATH)
MYSQLDUMP_PATH = os.getenv("MYSQLDUMP_PATH", "mysqldump")

# ================== Graphiques (Phase 4) ==================
# Chrome déjà installé sur la machine, utilisé par kaleido pour exporter les PNG
# (aucune copie de Chrome téléchargée). Vide = détection automatique.
CHROME_PATH = os.getenv("CHROME_PATH", "")
GRAPH_MAX_CATEGORIES = _env_int("GRAPH_MAX_CATEGORIES", 20)  # barres : au-delà -> top N + « Autres »
GRAPH_MAX_PIE = _env_int("GRAPH_MAX_PIE", 6)                 # règle auto : ≤ 6 catégories -> camembert
GRAPH_MAX_POINTS = _env_int("GRAPH_MAX_POINTS", 5000)        # nuage de points : échantillon au-delà

# ================== Frontend React (Phase 6) ==================
FRONTEND_DIST = _chemin("FRONTEND_DIST", os.path.join("frontend", "dist"))   # build Vite servi sous /app/
UI_PRINCIPALE = os.getenv("UI_PRINCIPALE", "react")    # "react" : / -> /app/ ; "jinja" : anciennes pages

# ================== Machine Learning (Phase 5) ==================
PREVISION_MIN_PERIODES = _env_int("PREVISION_MIN_PERIODES", 12)    # historique minimum après agrégation
PREVISION_HORIZON_DEFAUT = _env_int("PREVISION_HORIZON_DEFAUT", 6)
# Exclure de l'apprentissage les valeurs négatives et aberrantes (> Q3 + 5×IQR) de la cible
PREVISION_EXCLURE_ABERRANTS = os.getenv("PREVISION_EXCLURE_ABERRANTS", "1") == "1"
ANOMALIE_CONTAMINATION = os.getenv("ANOMALIE_CONTAMINATION", "auto")  # part d'anomalies attendue ou « auto »

for _dossier in (UPLOAD_FOLDER, VECTOR_FOLDER, REPORT_FOLDER, BACKUP_FOLDER, GRAPH_FOLDER, EXPORT_FOLDER):
    os.makedirs(_dossier, exist_ok=True)

# ================== Multilingue ==================
# Langue de réponse quand l'utilisateur écrit en derja (le modèle 3B ne génère
# pas la derja de façon fiable, cf. JUSTIFICATIONS.md) :
#   derja en lettres latines -> DERJA_LATIN_REPONSE (fr par défaut)
#   derja en lettres arabes  -> DERJA_ARABE_REPONSE (ar = arabe standard par défaut)
DERJA_LATIN_REPONSE = os.getenv("DERJA_LATIN_REPONSE", "fr")
DERJA_ARABE_REPONSE = os.getenv("DERJA_ARABE_REPONSE", "ar")

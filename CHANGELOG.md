# CHANGELOG — DataIA v2

Branche Git : `dataia-v2` (un commit par phase).

---

## Phase 1 — LLM local, multilingue, configuration et sécurité

### Fichiers ajoutés
| Fichier | Rôle |
|---|---|
| `config.py` | Configuration centrale lue depuis `.env` (Flask, MySQL, Ollama, RAG, chemins, langue derja). Crée les dossiers `uploads/`, `uploads/vector_indices/` et `uploads/rapports/`. |
| `services/__init__.py` | Paquet des services métier. |
| `services/db.py` | `get_db_connection()` : connexion MySQL à partir de `config.DB_CONFIG`. |
| `services/llm.py` | `ChatOllama` (qwen2.5:3b, temperature 0, num_ctx 4096), `NomicEmbeddings` (préfixes `search_document:` / `search_query:`, lots de 32), `verifier_ollama()`, exception `OllamaIndisponibleError`. |
| `services/rag.py` | Index FAISS par fichier : construction, chargement avec contrôle de la dimension (768), recherche, suppression. |
| `services/langue.py` | Détection fr / en / ar / derja (lettres arabes ou latines), glossaires derja, consignes de langue, messages d'erreur traduits. |
| `services/prompts.py` | Prompts du RAG (système et utilisateur) avec la consigne de langue. |
| `services/parsers.py` | `charger_dataframe()` (CSV / Excel), partagé entre `app.py` et `reindex.py`. |
| `requirements-lock.txt` | `pip freeze` complet de l'environnement testé (reproductibilité). |
| `JUSTIFICATIONS.md`, `CHANGELOG.md` | Documentation. |
| `.env` (non versionné) | Configuration locale avec une `SECRET_KEY` aléatoire. |

### Fichiers supprimés
| Fichier | Remplacé par |
|---|---|
| `config_ia.py` | `config.py` |
| `ollama_rag.py` | `services/llm.py` + `services/rag.py` + `services/prompts.py` |

### Fichiers modifiés
- **`app.py`**
  - Imports : plus de `config_ia`, `ollama_rag` ni `requests` ; utilise `config` et `services.*`.
  - `SECRET_KEY` et `UPLOAD_FOLDER` lus depuis `config` ; `MAX_CONTENT_LENGTH` (20 Mo).
  - Sorties console en UTF-8 + `logging` (corrige le crash sur l'arabe dans la console Windows).
  - `load_user` : un compte bloqué perd sa session immédiatement.
  - **`/ask_ia` réécrite** : détection de langue → contrôle de propriété du fichier → RAG → `generer_reponse()` dans la langue de l'utilisateur → historique. 503 + message traduit si Ollama est indisponible, 410 si le fichier n'est plus sur le disque. La réponse JSON contient aussi `langue` et `langue_reponse`.
  - Nouvelle route **`/api/sante`** (état d'Ollama, des modèles et de MySQL).
  - `/export_pdf` : dossier des rapports lu depuis la config, chemin relatif en base.
  - `/upload` : extensions contrôlées, nom unique sur le disque, chemin relatif en base.
  - `/delete_file` : n'efface le fichier physique que s'il n'est plus référencé ; utilise `rag.supprimer_index`.
  - **`/view_report`** sécurisée (rapport enregistré en base, propriétaire ou admin, dossier des rapports).
  - `/admin/toggle_user` et `/admin/delete_user` : `@admin_required`.
  - `app.run(debug=config.FLASK_DEBUG)` + avertissement au démarrage si Ollama est indisponible.
- **`reindex.py`** réécrit : utilise les services ; signale les fichiers absents du disque ; code de sortie 0/1/2.
- **`requirements.txt`** : remplace l'ancien `pip freeze` Python 3.10 win32 (pandas 1.4, Django, PyQt…, incompatible avec le venv) par les **dépendances directes** épinglées sur les versions du venv. Ajoute `langchain-ollama==1.0.1` et `ollama==0.6.3`. Retire `openai` (plus utilisé). `langchain-mistralai` reste installé dans le venv mais n'est plus importé nulle part ni requis.
- **`.env.example`** : toutes les variables documentées (MySQL, Flask, Ollama, chemins, derja).
- **`.gitignore`** : remplace le modèle Expo/React Native par des règles adaptées (`.env`, `uploads/`, `exports/`, `backups/`, `venv/`…).
- **`demarrer.bat`** : utilise `..\venv` (l'ancien `venv_dataia` n'existait pas), console UTF-8, vérifie la présence de `.env`.

### Packages installés
- `langchain-ollama==1.0.1`, `ollama==0.6.3` (aucun package existant mis à jour).

### Données
- Copie de `sales_data_1000_rows.xlsx` et `Loan_AI_RAG_Dataset_200_rows.xlsx` depuis `DataIA\app\DataIA\uploads\` vers `DataIa/uploads/`.
- Réindexation FAISS : **5 / 5 fichiers présents réindexés** (768 dimensions).
- **Fichiers perdus** (lignes conservées en base) :
  - `fichiers.id_fichier = 1` : `produits_magasin.csv` (utilisateur 1) est absent du disque.
  - 8 rapports PDF (`rapports.id_rapport` 1 à 8) sont absents du disque ; `/view_report` renvoie maintenant une 404 propre.

### Tests Phase 1 (20 / 20 OK)
| Test | Résultat |
|---|---|
| Détection de langue (13 phrases fr / en / ar / derja) | ✅ 13/13 |
| Réindexation FAISS | ✅ 5/5 (1000 lignes ≈ 110 s) |
| Démarrage du serveur, `/`, `/login`, `/signup`, `/api/sante` | ✅ 200 ; `/dashboard` non connecté → 302 |
| Question fr / en / ar / derja latine / derja arabe | ✅ bonne langue de réponse (34 à 88 s par réponse sur CPU) |
| Ollama arrêté (simulé) | ✅ 503 + message clair fr / ar |
| IDOR `/ask_ia`, *path traversal* `/view_report`, rapport d'un autre utilisateur | ✅ 404 / 404 / 403 |
| `toggle_user` / `delete_user` par un non-admin | ✅ 403 |
| Déconnexion puis page protégée | ✅ redirection vers `/login` |

**Limite constatée (corrigée en Phase 3).** Une réponse anglaise ne citait qu'un seul moyen de paiement : le RAG ne voit que 8 lignes sur 1000. C'est le problème que le routeur hybride doit résoudre.

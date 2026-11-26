# CHANGELOG — DataIA v2

Branche Git : `dataia-v2` (un commit par phase).

---

## Phase 4 — Graphiques à la demande (tous types, calculés par pandas)

### Base de données (migration `002`)
- Sauvegarde : `backups/dataia_20261126_011349_avant_migration_002.sql` (vérifiée).
- Nouvelle table **`graphiques`** : utilisateur, question, fichier, source, type, titre, `spec_json`, `chemin_json`, `chemin_png`, avec 3 clés étrangères.
- Aucune ligne existante modifiée (8 / 7 / 70 / 8 lignes avant = après).

### Package installé (accord donné)
- `kaleido==1.5.2`, qui installe aussi `choreographer`, `logistro`, `simplejson` et `platformdirs`. Ce sont uniquement de nouveaux packages ; aucun package existant n'a été mis à jour.
- **Aucune copie de Chrome téléchargée** : kaleido utilise le Chrome installé (`CHROME_PATH` dans `.env`).

### Fichiers ajoutés
| Fichier | Rôle |
|---|---|
| `services/charts.py` | Moteur de graphiques : type demandé et colonnes par règles, spec LLM contrainte seulement si une colonne manque, validation et incompatibilités, données pandas, figure Plotly (11 variantes), titre et explications en 3 langues, suggestions de types, export PNG persistant en arrière-plan, nettoyage de l'ancien format, rechargement de l'historique. |
| `migrations/002_phase4_graphiques.sql` | Table `graphiques`. |
| `tests/test_graphiques.py` | **17 tests** : valeurs de chaque figure comparées à pandas, 11 variantes, règles automatiques, incompatibilités, suggestions, 4 langues, ancien format, export PNG. |
| `tests/benchmark_graphiques.py`, `mesures/phase4_graphiques.json` | Mesure du temps de génération. |

### Fichiers modifiés
- **`services/assistant.py`** : l'intent `graph` passe par `charts.generer` (fini le RAG pour les graphiques) ; `Reponse.graphique`.
- **`services/prompts.py`** : suppression de la règle « produis un JSON `type_graph` » ; le RAG n'a plus le droit de produire un graphique.
- **`services/router.py`** : règles de l'intent `graph` complétées (barres, aire, donut, anneau, nuage de points, boîte à moustaches, heatmap, corrélation, pie, arabe : منحنى / دائري / خريطة حرارية).
- **`app.py`** :
  - `/ask_ia` enregistre le graphique (JSON + ligne en base, PNG en arrière-plan) et renvoie `graphique` et `id_question` ;
  - `/chat/<id>` recharge les figures de l'historique et nettoie l'ancien format ; l'historique est aussi filtré par utilisateur ;
  - nouvelle route `/vendor/plotly.min.js` ;
  - Chrome préchauffé au démarrage.
- **`templates/chat.html`** :
  - plotly.js local ;
  - historique rendu en Markdown, avec ses graphiques ;
  - ancien format remplacé par un avertissement et un bouton « Régénérer avec le nouveau moteur » ;
  - `afficherGraphique()` remplace l'ancien `renderPlotlyGraph()` (qui dessinait les valeurs écrites par le LLM).
- **`templates/base.html`** : retrait du CDN `plotly-latest` (version 1.58.5, chargé sur toutes les pages).
- **`config.py`, `.env`, `.env.example`** : `GRAPH_FOLDER`, `CHROME_PATH`, `GRAPH_MAX_CATEGORIES`, `GRAPH_MAX_PIE`, `GRAPH_MAX_POINTS`.
- **`requirements.txt`, `requirements-lock.txt`** : kaleido.

### Problèmes trouvés et corrigés pendant la phase
| Problème | Correction |
|---|---|
| CDN `plotly-latest` figé en 1.58.5 (2021) | plotly.js 3.3.1 servi en local |
| « Nuage de points entre Quantity et Total_Price » : axes inversés | Ordre des colonnes = ordre dans la question |
| Deux colonnes numériques citées → barres (Quantity a 20 valeurs) | La règle « 2 nombres → nuage de points » est prioritaire |
| « graphique de Total_Price » → courbe (via le LLM) | La règle « 1 nombre → histogramme » est appliquée sans LLM |
| « Courbe des prix » le long de `product_id` | Identifiants exclus des axes et des corrélations |
| Courbe impossible remplacée par un camembert | Remplacée par des barres (mêmes axes) |
| Heatmap : « 0.03 » au lieu de « 0,03 » | Texte formaté par Plotly (séparateurs selon la langue) |
| « Barres groupées » et « courbe des ventes » passaient par le LLM (9 à 15 s) | Règles complétées : 0,35 à 0,46 s |

### Mesures
- Graphique **sans LLM** : **0,47 s en moyenne** (14 demandes sur 15).
- Graphique **avec LLM** (axe non précisé) : ~9 s.
- PNG : ~4 s pour le premier (démarrage de Chrome, au lancement de Flask), puis **~0,4 s**, en arrière-plan.
- Avant / après sur « CA par région » : **65 à 75 s, valeurs fausses → 0,39 s, valeurs exactes**.

### Tests Phase 4
| Suite | Résultat |
|---|---|
| `tests/test_graphiques.py` (17 tests) | ✅ |
| Test de bout en bout `/ask_ia` → ligne `graphiques` → PNG → historique | ✅ (1,28 s, 0 appel LLM) |
| Non-régression Phase 3 (`tests/test_routeur_hybride.py`, 16 tests) | ✅ |
| Non-régression Phases 1 et 2 (scripts de test) | ✅ 21/21 et 33/33 |

---

## Phase 3 — Routeur hybride (le LLM comprend, pandas calcule)

### Corrections préalables demandées
- **venv** :
  - `Scripts/activate` pointait encore vers `C:\stage-perfectionnemnt\DataIA\venv`. Il utilise maintenant `/e/stage-perfectionnemnt/DataIA_Loal/venv` (la forme `E:\…` cassait le PATH sous Git Bash).
  - `activate.bat` (corrigé par l'utilisatrice) et `Activate.ps1` (chemin calculé automatiquement) ont été vérifiés.
  - **Les 24 lanceurs `.exe`** (`pip.exe`, `flask.exe`…) lançaient le Python de **l'ancien venv**, qui existe encore sur `C:` : un `pip install` aurait installé dans le mauvais environnement. Leur ligne `#!` a été réécrite (sauvegarde faite avant) et vérifiée : `pip --version` affiche `E:\…\DataIA_Loal\venv`.
  - `pyvenv.cfg` : ligne `command` mise à jour.
  - Vérifié dans cmd, PowerShell et Git Bash.
- **`demarrer.bat`** (double-clic), qui exécute dans l'ordre :
  1. vérification du venv et du `.env` ;
  2. MySQL (attend que WampServer soit lancé) ;
  3. Ollama (lance `ollama serve` s'il est arrêté) ;
  4. alerte si des migrations sont en attente ;
  5. ouverture du navigateur dès que Flask répond ;
  6. fins de ligne CRLF.

  Testé : toutes les vérifications passent et Flask répond 200.

### Fichiers ajoutés
| Fichier | Rôle |
|---|---|
| `services/router.py` | Routeur : règles par mots-clés (intents évidents, liste des valeurs d'une colonne), puis LLM avec **JSON contraint**, puis **validation** (opération autorisée, colonnes, filtres **ancrés dans la question**, regroupement et période détectés par règles). |
| `services/stats.py` | Moteur pandas : 10 opérations en liste fermée, filtres, produit de deux colonnes, conversion robuste des nombres et des dates. Aucun `eval`/`exec`. |
| `services/semantique.py` | Résolution **déterministe** de la colonne mesurée (colonne citée, concept « ventes / quantité / prix » en fr / en / ar) et du regroupement (« par X », « top N X », « حسب X »), avec synonymes fr / en / ar. |
| `services/redaction.py` | Phrases modèles en 3 langues, tableaux Markdown, ligne de provenance « Calculé par pandas », demande de précision avec options calculées, **garde-fou** sur les nombres écrits par le LLM. |
| `services/assistant.py` | Orchestration d'une question (langue → routeur → pandas / RAG / registre ML → réponse) et mesure des temps par étape. |
| `services/ml/__init__.py`, `services/ml/registry.py` | Registre des modèles par domaine (métadonnées ; l'exécution arrive en Phase 5). |
| `tests/test_routeur_hybride.py` | **15 tests** `unittest`, dont le cas réel `produits_magasin.csv` dans 4 langues. |
| `tests/benchmark_routeur.py` | Banc de mesure avant / après (temps, tokens, réponses). |
| `tests/donnees/produits_magasin.csv`, `tests/donnees/sales_data_1000_rows.xlsx` | Données de test. |
| `mesures/phase3_avant.json`, `mesures/phase3_apres.json` | Résultats bruts du banc de mesure. |

### Fichiers modifiés
- **`app.py`** :
  - `/ask_ia` délègue à `services.assistant.repondre`. La réponse JSON contient en plus `intent`, `routage`, `resultat` (structuré), `suggestions`, `demande_precision` et `temps`.
  - `resume_categories` est déplacé dans `assistant.py`.
  - Préchauffage d'Ollama au démarrage.
- **`services/llm.py`** :
  - options communes à tous les appels (`num_gpu`, `keep_alive`, `num_ctx`), sans quoi Ollama recharge le modèle ;
  - `generer_json()` (paramètre `format`) ;
  - trace des tokens et durées par requête ;
  - `prechauffer()` ;
  - vérification d'Ollama gardée 30 s ;
  - correction : `keep_alive` en secondes pour les embeddings.
- **`services/prompts.py`** : prompt du routeur et son schéma JSON (colonnes en `enum`), contexte réduit (**colonnes + types + 3 lignes**, plus de `describe()`), RAG allégé, prompt de reformulation.
- **`services/rag.py`** : `lignes_exactes()` et `recherche_hybride()`.
- **`templates/chat.html`** : suggestions affichées en boutons cliquables.
- **`config.py`, `.env`, `.env.example`** : `OLLAMA_NUM_GPU=0`, `OLLAMA_KEEP_ALIVE=30m`, `REFORMULATION_LLM=1`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`.
- **venv** (hors dépôt) : `Scripts/activate`, 24 `Scripts/*.exe`, `pyvenv.cfg`.
- **`demarrer.bat`**.

### Problèmes trouvés et corrigés pendant la phase (tous couverts par un test)
| Problème | Correction |
|---|---|
| « ventes » sans colonne de ventes → chiffres inventés (105 / 106,20) | Demande de précision avec les options calculées |
| Le LLM ignorait « par région » | Détection du regroupement par règles |
| « top 3 products » regroupé par `Total_Price` | Regroupement par une colonne catégorielle uniquement |
| Filtre `Status == Pending` inventé (recopié du prompt) | Filtres ancrés dans la question, filtres rejetés signalés |
| « Quelles régions ? » : 4 sur 5 via le RAG | Liste exacte par pandas (sans LLM) |
| `INV-10001` pris pour un nombre ; « 1,200.50 » illisible | Conversion selon la forme du nombre et le dernier séparateur décimal |
| Hamzas retirés par la normalisation (« الإيرادات » non reconnu) | Motifs arabes normalisés |
| `localhost` = 2,3 s par connexion sous Windows | `127.0.0.1` |
| GPU MX130 plus lent que le CPU | `OLLAMA_NUM_GPU=0` |
| Avertissements pandas à chaque question | Pré-filtre des dates par expression régulière |
| RAG : la ligne « INV-10002 » absente des extraits vectoriels | **Recherche hybride** (`rag.recherche_hybride`) : mot-clé exact puis vecteurs ; `RAG_TOP_K` passe de 8 à 5 |

### Mesures (6 questions identiques, avant → après)
- Temps moyen : **61,3 s → 11,2 s** (÷ 5,5).
- Réponses exactes : **0 / 6 → 6 / 6**.
- Tokens du prompt : **~2 080 → ~680**.
- Détail : `JUSTIFICATIONS.md` §28.

### Tests Phase 3
| Suite | Résultat |
|---|---|
| `tests/test_routeur_hybride.py` (16 tests, dont le cas réel en 4 langues) | ✅ |
| Non-régression Phase 1 (script de test, chat 4 langues + derja, sécurité, Ollama arrêté) | ✅ 21/21 |
| Non-régression Phase 2 (inscription, profil, admin, déconnexion, clés étrangères) | ✅ 33/33 |
| `demarrer.bat` en double-clic | ✅ |

### Limites connues
- **Questions texte (RAG)** : ~20 s avec le cache chaud, 50 à 80 s à froid.
- **Graphiques** : encore l'ancien format, avec des données parfois fausses. Ils sont remplacés en Phase 4 par des graphiques calculés par pandas.

### Packages
Aucun package installé.

---

## Phase 2 — Domaine d'activité, déconnexion et base de données

### Base de données (migration `001`)
- **Sauvegardes** (dossier `backups/`, non versionné) :
  - `dataia_20261125_225632_manuel.sql` : état d'origine, **restauration testée** dans une base temporaire.
  - `dataia_20261125_225728_avant_migration_001.sql` : sauvegarde automatique juste avant la migration.
- **Répétée sur une copie** (`dataia_test`) avant l'application réelle.
- Modifications :
  - 4 tables MyISAM → **InnoDB**.
  - `utilisateurs.domaine` : ENUM des 8 domaines, `NOT NULL DEFAULT 'Autre'` (les 7 comptes existants sont en `Autre`).
  - `questions.id_fichier` et `rapports.id_question` deviennent **NULL autorisé**.
  - **39 questions orphelines** : `id_fichier` passe à NULL, l'ancienne valeur est conservée dans la nouvelle table `migration_orphelins`.
  - **7 clés étrangères** (CASCADE pour le propriétaire, SET NULL pour conserver l'historique).
  - `rapports.type_graphique` (`chemin_graphique` existait déjà).
  - Nouvelles tables **`modeles_ml`**, **`simulations`**, **`migration_orphelins`**, **`schema_migrations`**.
- **Vérification après migration** :
  - nombre de lignes identique (utilisateurs 7, fichiers 6, questions 64, rapports 8) ;
  - **comparaison ligne par ligne et colonne par colonne** avec la sauvegarde : 0 différence inattendue ;
  - 39/39 orphelins tracés avec leur valeur exacte.

### Fichiers ajoutés
| Fichier | Rôle |
|---|---|
| `migrate.py` | Applique `migrations/*.sql` dans l'ordre : sauvegarde `mysqldump` vérifiée, puis migration, puis contrôle du nombre de lignes. Options `--statut` et `--sauvegarde-seule`. |
| `migrations/001_phase2_innodb_domaine_ml.sql` | Migration de la Phase 2 (commentée). |
| `services/domaines.py` | Liste des 8 domaines + validation. |
| `templates/profil.html` | Page profil (nom et domaine). |

### Fichiers modifiés
- **`app.py`**
  - `User` : attribut `domaine` et constructeur `User.depuis_ligne()`.
  - `after_request` : `Cache-Control: no-store` pour les pages connectées.
  - `context_processor` : `DOMAINES` disponible dans les templates.
  - **`/signup`** : domaine obligatoire validé côté serveur, champs conservés en cas d'erreur, message clair pour un email en double (au lieu de l'erreur SQL), email en minuscules.
  - `/login` : `session.clear()` avant `login_user`.
  - **`/profil`** (nouvelle) : GET et POST.
  - **`/admin/set_domaine/<id>`** (nouvelle, `@admin_required`).
  - `/admin/dashboard` : `LEFT JOIN` pour que les rapports sans question restent visibles.
  - **`/logout`** : `session.clear()`, message, accepte GET et POST, sans `@login_required`.
- **`templates/signup.html`** : liste déroulante « Domaine d'activité ».
- **`templates/base.html`** : lien « Mon profil », nom et badge du domaine, bouton déconnexion identifié.
- **`templates/admin_dashboard.html`** : boutons **Profil** et **Déconnexion** (absents avant), colonne Domaine modifiable, email affiché, messages flash.
- **`database.sql`** : réécrit pour correspondre au **schéma v1 réel**. Une installation neuve suit `database.sql` puis `migrate.py` (testé).
- **`config.py`**, **`.env`**, **`.env.example`** : `BACKUP_FOLDER`, `MIGRATIONS_FOLDER`, `MYSQLDUMP_PATH`.

### Tests Phase 2 : 33 / 33 OK
| Domaine | Résultat |
|---|---|
| Inscription : domaine valide, hors liste, absent ; email en double | ✅ |
| Connexion réelle par mot de passe ; domaine affiché | ✅ |
| Profil : affichage, modification, valeur invalide refusée | ✅ |
| Admin : voir et modifier le domaine (avec accent : Télécom) ; non-admin → 403 | ✅ |
| Bouton déconnexion sur dashboard, mes_fichiers, profil, admin | ✅ |
| Après déconnexion : session vide ; 5 pages protégées + `/ask_ia` refusées | ✅ |
| `Cache-Control: no-store` | ✅ |
| FK : suppression de fichier → question conservée (NULL) ; utilisateur inexistant → erreur 1452 | ✅ |
| Compte bloqué pendant sa session → déconnecté ; connexion refusée | ✅ |
| Non-régression : utilisateur existant (dashboard, chat, historique) | ✅ |
| Données existantes identiques après les tests | ✅ |
| Installation neuve (`database.sql` + `migrate.py`) | ✅ |
| Non-régression : tests de la Phase 1 relancés (chat 4 langues + derja, sécurité, Ollama arrêté) | ✅ 20/20 |

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

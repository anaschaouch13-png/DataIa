# DataIA — Explication détaillée du code

Ce document se lit avec le code ouvert à côté. Il décrit **chaque fichier** : ce qu'il fait, ses fonctions principales et qui l'appelle. Pour la vision d'ensemble, voir `ARCHITECTURE.md` ; pour les raisons des choix, `JUSTIFICATIONS.md` ; pour un cours pas à pas, `GUIDE_COMPRENDRE_DATAIA.md`.

---

## 1. Points d'entrée

### `app.py` — le serveur Flask
- **Configuration** : `SECRET_KEY`, taille maximale d'upload, cookie HttpOnly + SameSite=Lax ; enregistrement des Blueprints `api` et `spa` (de `api.py`) ; `login_manager` avec `unauthorized_handler` (401 JSON pour l'API, redirection vers `/login` pour les pages).
- **`load_user`** : recharge l'utilisatrice depuis la base à chaque requête. Un compte bloqué perd sa session immédiatement.
- **`after_request`** : `Cache-Control: no-store` sur les pages connectées.
- **Pages Jinja (secours)** : `/accueil`, `/signup`, `/login`, `/dashboard`, `/profil`, `/chat/<id>`, `/mes_fichiers`, `/mes_donnees_nettoyees`, `/admin/dashboard`, `/logout`.
- **`/ask_ia` (POST)** : le cœur du chat. Elle vérifie la propriété du fichier, appelle `analyser_fichier` et `table_pour_question`, puis `assistant.repondre`, enregistre la question et les graphiques, et renvoie le JSON. Elle gère `OllamaIndisponibleError` (503).
- **`/export_pdf`** : avec `file_id`, appelle `pdf_export.generer_rapport` ; sinon, ancien format en secours.
- **`/telecharger/nettoyees/<id>/<format>`** : données nettoyées (propriétaire ou admin, liste fermée de formats, dossier contrôlé par `commonpath`).
- **`/view_report/<fichier>`** : rapport PDF ; il doit être enregistré dans `rapports` et appartenir à l'utilisatrice.
- **`/vendor/plotly.min.js`** : plotly.js servi en local.
- **`/api/sante`** : état d'Ollama et de MySQL.
- **Au démarrage** (`__main__`) : vérification d'Ollama, préchauffage du LLM, démarrage de Chrome pour les PNG, `app.run(debug=config.FLASK_DEBUG)`.

### `api.py` — l'API JSON et la SPA
- **`exiger_json_pour_modifier`** (`before_request`) : protection CSRF. Un POST / PUT / DELETE doit être en JSON, sauf l'upload multipart.
- **Auth** : `signup` (domaine validé, email en minuscules, 409 si doublon), `login` (`session.clear()` puis `login_user`), `logout` (POST), `me`, `domaines`.
- **`profil`** (GET / PUT) : nom, domaine, modèles disponibles.
- **Fichiers** : `dashboard`, `fichiers`, `upload` (avec aperçu), `supprimer`, `apercu`, `historique` (avec les figures).
- **Simulateur** : `simulateur_modeles` (formulaires du domaine), `simuler` (403 hors domaine), `simulations`.
- **`rapport_pdf`** : `POST /api/rapport/<id_fichier>/pdf`.
- **`donnees_nettoyees`** : liste des exports avec leurs liens.
- **Admin** : `admin_data`, bloquer / débloquer, changer le domaine, supprimer.
- **`application`** (Blueprint `spa`) : sert `frontend/dist`. Une adresse inconnue renvoie `index.html` (routage côté React) ; il y a un contrôle de chemin, et un cache long sur `/assets/`.

### `config.py`
Il lit `.env` une seule fois. `_env_int` et `_env_float` donnent une valeur par défaut si la variable est invalide ; `_chemin` rend les chemins absolus par rapport au projet. Il crée les dossiers nécessaires. **Aucun autre fichier ne lit `os.getenv`.**

### `migrate.py`
`python migrate.py [--statut | --sauvegarde-seule]` :
1. `mysqldump` vers `backups/`, avec vérification que le fichier n'est pas vide ;
2. application, dans l'ordre, des `migrations/NNN_*.sql` absents de `schema_migrations` ;
3. comptage des lignes de chaque table avant / après, et erreur en cas de différence.

### `entrainer_churn.py`
Réentraînement du churn : lecture, nettoyage tracé, split stratifié 80 / 20, validation croisée (5 plis, 20 combinaisons de `max_depth` × `class_weight`), Pipeline final, métriques de test, sauvegarde du `.joblib` + des métadonnées JSON + des données nettoyées.

### `demarrer.bat`
Lancement en un double-clic (venv, `.env`, MySQL, Ollama, migrations en attente, build React, Flask, navigateur).

---

## 2. Services (`services/`)

### Accès et fichiers
| Fichier | Contenu |
|---|---|
| `db.py` | `get_db_connection()` à partir de `config.DB_CONFIG` |
| `auth.py` | `User` (`depuis_ligne`, `en_dict` sans mot de passe), `admin_required` (403 JSON pour l'API), `est_requete_api` |
| `domaines.py` | `DOMAINES` (les 8), `domaine_valide` |
| `fichiers.py` | `enregistrer_upload` (extension contrôlée, nom unique `U<id>_<date>_<nom>`, chemin relatif), `fichier_de_utilisateur` (**contrôle IDOR**), `supprimer_fichier` (fichier physique effacé seulement s'il n'est plus référencé), `chemin_absolu`, `type_de_fichier` |

### Lecture des fichiers
**`parsers.py`**
- `analyser_fichier(chemin)` → `ResultatParsing` (tables, textes, source, remarques, durée). Il y a un cache par chemin et date de modification.
- `lire_csv` : encodage (charset-normalizer), séparateur (`csv.Sniffer`), virgule décimale.
- `lire_excel` : toutes les feuilles.
- `lire_pdf` : pdfplumber, tableaux et texte découpé en phrases.
- `lire_image` + `reconstruire_tableau` : RapidOCR, fusion des zones proches d'une même ligne, alignement sur l'en-tête.
- `normaliser` : nombres écrits en texte (« 1 234,56 », « 12 % »), retrait des lignes de total.
- `table_pour_question` : choisit le tableau dont les colonnes sont citées dans la question.
- `ResultatParsing.textes_rag()` : tout le contenu, pour l'index FAISS.
- `charger_dataframe` : compatibilité avec l'ancien code.

**`apercu.py`** : `apercu_fichier` (colonnes, types, 5 lignes, remarques, tableaux) et `questions_suggerees` (selon les colonnes trouvées et le domaine).

### Langue
**`langue.py`**
- `detecter_langue` : alphabet, mots-outils fr / en, marqueurs derja et arabizi.
- `analyser_question` → `AnalyseLangue` (langue, langue de réponse, `question_pour_llm` traduite par le glossaire, avertissement derja, noms propres arabes translittérés).
- `consigne_langue` : consigne ajoutée aux prompts.
- `message(cle, langue)` : messages d'erreur écrits à la main en 3 langues.

### LLM et RAG
**`llm.py`**
- `get_chat_llm` : ChatOllama, avec les options communes `num_gpu`, `keep_alive` et `num_ctx`.
- `generer_reponse` : texte libre (RAG, reformulation).
- `generer_json(prompt, schema)` : sortie contrainte (paramètre `format` d'Ollama).
- `verifier_ollama` (résultat gardé 30 s), `OllamaIndisponibleError`, `prechauffer`.
- `NomicEmbeddings` (préfixes `search_document:` / `search_query:`, lots de 32), `demarrer_trace` (tokens et durées de chaque appel).

**`rag.py`** : `charger_ou_construire_index` (FAISS par fichier, avec contrôle de la dimension 768), `rechercher`, `lignes_exactes` (mots-clés exacts), `recherche_hybride` (exact puis vecteurs, `RAG_TOP_K=5`), `supprimer_index`.

**`prompts.py`** : `contexte_fichier` (colonnes + types + 3 lignes), `schema_routeur` (JSON schema dont les colonnes sont en `enum`), `prompt_utilisateur_routeur`, prompts du RAG et de la reformulation.

### Routage et calcul
**`router.py`** → `router(df, question, analyse)` renvoie un `Routage` (intent, plan, source, durée) :
1. `intent_par_regles` : graph, forecast, anomaly, churn, export, lecture → text ;
2. `liste_par_regles` : « quelles sont les X ? » → count par X ;
3. `superlatif_par_regles` : « la plus forte / le plus vendu » → top 1 ;
4. sinon, `generer_json` avec `schema_routeur` ;
5. `valider_plan` : opération autorisée, colonnes, filtres ancrés, `n` borné, regroupement et période donnés par `semantique`.

**`semantique.py`** : `resoudre_mesure` (colonne citée > concept > demande de précision), `concept_de` et `colonnes_du_concept` (ventes / quantité / prix en fr / en / ar), `detecter_groupe` (« par X », « top N X », « حسب X »), `detecter_periode`, `mesure_par_defaut` (tableau de document avec une colonne Total), `produit_cite` (« prix × quantité »).

**`stats.py`** : `PlanStat` → `executer` → `ResultatStat`. Il y a 10 opérations et des filtres (`==, !=, >, >=, <, <=, contient, annee, mois`) ; `en_numerique` et `en_dates` sont robustes. **Aucun `eval` / `exec`.**

**`redaction.py`** : `phrase_modele` (3 langues), `tableau_markdown`, `ligne_provenance`, `message_precision_colonne` (options calculées), `formater_nombre` (fr : espaces, en / ar : virgules), `reformulation_valide` (**garde-fou** : chaque nombre doit exister dans le résultat, à 0,5 % près ; chiffres arabes-indiens gérés).

**`assistant.py`** → `repondre(df, id_fichier, question, analyse, domaine, ...)` renvoie une `Reponse` (texte, intent, résultat, suggestions, graphiques, id_modele, temps). Il orchestre router → stats / charts / RAG / ML → rédaction, et produit le refus poli hors domaine.

### Graphiques
**`charts.py`**
- `generer(df, question, langue)` → `ResultatGraphique` (figure, spec, texte, suggestions, demande de précision).
- `type_demande` (mots-clés → l'une des 11 variantes) ; `construire_spec` (colonnes par règles, `_spec_llm` seulement si un axe manque).
- `_choisir_type` (incompatibilités : courbe sans date, camembert avec des valeurs négatives ou trop de parts, nuage avec une seule colonne numérique, histogramme sur des catégories) ; `_type_auto` (choix automatique expliqué).
- `construire_figure` (pandas → Plotly ; « Autres » au-delà de `GRAPH_MAX_CATEGORIES`, échantillon au-delà de `GRAPH_MAX_POINTS`).
- `exporter_png` (kaleido + Chrome installé, serveur persistant) ; `enregistrer` (table `graphiques` ; JSON tout de suite, PNG en arrière-plan) ; `figures_des_questions` (historique) ; `nettoyer_ancien_format`.

### Rapport PDF
**`pdf_export.py`**
- `texte_pdf` : emojis retirés, arabe mis en forme (arabic-reshaper + python-bidi).
- `RapportPDF` (fpdf2) : police Arial (normal, gras, italique), pied de page « Page X / N », `titre_section` (entrée du sommaire), `paragraphe`, `tableau`, `markdown` (tableaux, titres, listes, provenance).
- `generer_rapport(id_utilisateur, id_fichier)` : titre, sommaire, fichier, questions et réponses, graphiques (PNG régénéré si absent), modèles ML, simulations ; enregistrement dans `uploads/rapports/` et dans la table `rapports`.

---

## 3. Machine Learning (`services/ml/`)

| Fichier | Contenu |
|---|---|
| `registry.py` | `MODELES` (clé → `DescriptionModele` : noms en 3 langues, type en base, `"module:fonction"` du lanceur et du simulateur), `MODELES_COMMUNS = [forecast, anomaly]`, `MODELES_SPECIFIQUES = {"Banque": [churn]}` ; `modeles_du_domaine`, `est_disponible`, `lanceur`, `simulateur` (import à la demande) |
| `nettoyage.py` | `RapportNettoyage` : `commencer`, `supprimer_doublons`, `convertir_numeriques`, `convertir_date`, `traiter_manquants` (médiane / mode / suppression), chaque opération étant tracée ; `exporter` (CSV UTF-8 BOM + Excel 2 feuilles + rapport texte dans `exports/donnees_nettoyees/U<id>/`) |
| `forecast.py` | `choisir_colonnes`, `preparer` (nettoyage + aberrants), `choisir_frequence` (≥ 12 périodes, pas plus fine que les données), `agreger` (périodes incomplètes retirées), `prevoir` (split temporel, Prophet / LightGBM / naïve, `calculer_metriques`, choix, réentraînement, intervalle), `figure` ; `HistoriqueInsuffisant` |
| `anomalies.py` | `choisir_colonnes` (transactionnelles + cohérence), `entrainer` (Isolation Forest, 300 arbres, seuil Q3 + 3 × IQR), `detecter`, `expliquer` (écart à la médiane, incohérence), `figure`, `evaluer_transaction` (simulateur) |
| `churn_banque.py` | `charger` (pipeline gardé en mémoire), `correspondance_colonnes` (alias : « Age » → `age`…), `preparer` (médianes de l'entraînement), `predire_fichier`, `predire_client`, `champs_formulaire` (générés depuis les métadonnées), `figures` ; `ColonnesManquantes`, `ModeleChurnIndisponible` |
| `executeur.py` | `lancer_prevision`, `lancer_anomalies`, `lancer_churn` : nettoyage + export + ligne `modeles_ml` + réponse en 3 langues (tableaux, liens de téléchargement) + figures |
| `simulateur.py` | `champs_*` et `simuler_*` pour chaque modèle, cache des modèles d'anomalies par fichier, `enregistrer` (table `simulations`) |

---

## 4. Frontend (`frontend/src/`)

| Fichier | Rôle |
|---|---|
| `main.tsx`, `App.tsx` | Routeur React (`basename="/app"`), routes protégées, Toaster |
| `lib/api.ts` | **Tous** les appels au serveur (`/api/*`, `/ask_ia`) ; la déconnexion est un POST |
| `hooks/useAuth.tsx` | État de connexion (`/api/me`), inscription avec le domaine |
| `pages/LoginPage`, `SignupPage` | Connexion ; inscription (liste des domaines) |
| `pages/DashboardPage`, `MyFilesPage` | Statistiques, upload (`FileUploadZone`), aperçu (`FilePreview`), fichiers |
| `pages/ChatPage` | Chat : historique, Markdown (`ChatBubble`), figures (`PlotlyChart`), suggestions, panneau `SimulatorPanel` repliable, export PDF |
| `pages/SimulatorPage` | Choix du fichier + simulateur |
| `pages/ProfilePage`, `CleanedDataPage` | Profil et modèles disponibles ; données nettoyées |
| `pages/AdminPage` | Comptes (bloquer, changer le domaine, supprimer), rapports |
| `tailwind.config.js` | Palette `slate` inversée → fond blanc |
| `vite.config.ts` | `base: '/app/'`, proxy vers Flask en développement |

---

## 5. Base de données et migrations

| Fichier | Contenu |
|---|---|
| `database.sql` | Schéma v1 réel (installation neuve), complété ensuite par `migrate.py` |
| `migrations/001_phase2_innodb_domaine_ml.sql` | InnoDB, `domaine`, orphelins → `migration_orphelins`, 7 clés étrangères, `modeles_ml`, `simulations`, `rapports.type_graphique` |
| `migrations/002_phase4_graphiques.sql` | Table `graphiques` + 3 clés étrangères |
| `migrations/003_phase7_types_fichiers.sql` | `type_fichier` ENUM('CSV','Excel','PDF','Image') |

Le schéma complet (diagramme) est dans `ARCHITECTURE.md` §5.

---

## 6. Tests (`tests/`)

| Fichier | Ce qu'il vérifie | Nombre |
|---|---|---|
| `integration_phase1.py` | Langues, chat en 4 langues + derja, IDOR, path traversal, droits admin, Ollama arrêté, déconnexion | 21 |
| `integration_phase2.py` | Inscription / domaine, profil, admin, déconnexion, no-store, clés étrangères, compte bloqué, données intactes, installation neuve | 33 |
| `test_routeur_hybride.py` | Cas 105 / 106,20 dans 4 langues, ventes = Total_Price, filtres ancrés, listes, garde-fou, nombres, évolution → graphique, termes arabes | 18 |
| `test_graphiques.py` | Valeurs = pandas, 11 variantes, choix automatique, incompatibilités, 4 langues, PNG | 17 |
| `test_ml.py` | Métriques, prévision, anomalies injectées, churn, registre, refus hors domaine, base + téléchargement | 15 |
| `test_frontend_api.py` | API : auth, CSRF, profil, upload, IDOR, simulateur, admin, SPA | 7 |
| `test_parsers.py` | CSV difficiles, Excel multi-feuilles, PDF, OCR, suggestions, réponses attendues | 9 |
| `test_pdf.py` | Arabe, contenu du PDF, ligne `rapports`, IDOR | 4 |
| `tout_lancer.py` | Lance tout et affiche un bilan | — |
| `e2e_final.py` | Parcours complet par HTTP sur le serveur lancé → `mesures/E2E_RESULTATS.md` | 60 étapes |
| `benchmark_*.py` | Mesures de temps → `mesures/*.json` | — |

---

## 7. Données et résultats

| Dossier / fichier | Contenu |
|---|---|
| `donnees_demo/` | Générateur + 3 jeux synthétiques (ventes, transactions avec 10 anomalies, clients banque) + corrigé des anomalies + README |
| `uploads/ventes_demo_dataia.xlsx` / `.csv` | 1 793 ventes 2024-2025 avec 8 anomalies volontaires |
| `uploads/rapport_ventes_2025.pdf`, `tableau_ventes_2025.png` | Tests PDF et OCR |
| `mesures/` | Mesures brutes (JSON), métriques du churn, résultats E2E |
| `exports/donnees_nettoyees/U<id>/` | Données nettoyées de chaque exécution de modèle |
| `../a_integrer/modele_banque/` | Modèle churn, métadonnées, données d'entraînement nettoyées |

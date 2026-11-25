# DataIA — Justification des choix techniques

> Document mis à jour à chaque phase. Pour chaque choix : **ce qui a été choisi**,
> **pourquoi**, **alternatives écartées**, et **question probable du jury** avec une réponse courte.
>
> Machine cible : Intel i5-10210U, **8 Go de RAM**, GPU MX130 2 Go (trop petit : l'inférence se fait sur CPU), Windows 10.

---

## Sommaire

- **Phase 1 — LLM local et multilingue**
  1. [LLM local plutôt qu'une API (Mistral)](#1-llm-local-plutôt-quune-api-mistral)
  2. [Ollama comme serveur de modèles](#2-ollama-comme-serveur-de-modèles)
  3. [Qwen2.5 3B comme modèle de chat](#3-qwen25-3b-comme-modèle-de-chat)
  4. [Paramètres : temperature 0, num_ctx 4096](#4-paramètres-du-llm--temperature0-num_ctx4096)
  5. [nomic-embed-text + préfixes](#5-nomic-embed-text-et-ses-préfixes)
  6. [FAISS comme base vectorielle](#6-faiss-comme-base-vectorielle)
  7. [langchain-ollama (version 1.0.1)](#7-langchain-ollama-version-101)
  8. [Réindexation et envoi par lots](#8-réindexation-faiss-et-envoi-par-lots)
  9. [Multilinguisme et limite de la derja](#9-multilinguisme-et-limite-de-la-derja)
  10. [Ollama indisponible : pas de crash](#10-ollama-indisponible--message-clair-pas-de-crash)
  11. [Configuration dans `.env` + `config.py`](#11-configuration-dans-env--configpy)
  12. [Corrections de sécurité](#12-corrections-de-sécurité)
- **Phase 2 — Domaine, déconnexion, base de données**
  13. [Sauvegarde et migrations versionnées](#13-sauvegarde-et-migrations-versionnées)
  14. [MyISAM vers InnoDB](#14-myisam-vers-innodb)
  15. [Clés étrangères : CASCADE ou SET NULL](#15-clés-étrangères--cascade-ou-set-null)
  16. [Les 39 questions orphelines](#16-les-39-questions-orphelines-sans-perte-de-données)
  17. [Colonne `domaine` en ENUM](#17-colonne-domaine-en-enum)
  18. [Tables `modeles_ml` et `simulations`](#18-tables-modeles_ml-et-simulations)
  19. [Déconnexion fiable](#19-déconnexion-fiable)
  20. [Profil et administration du domaine](#20-profil-et-administration-du-domaine)
- **Phase 3 — Routeur hybride**
  21. [Pourquoi le RAG seul ne suffit pas](#21-pourquoi-le-rag-seul-ne-suffit-pas-pour-les-données-tabulaires)
  22. [Exemple réel avant / après](#22-exemple-réel-avant--après--produits_magasincsv)
  23. [Routeur hybride : règles puis LLM](#23-routeur-hybride--règles-puis-llm)
  24. [Sortie JSON contrainte plutôt que génération de code](#24-sortie-json-contrainte-plutôt-que-génération-de-code)
  25. [Liste fermée d'opérations et validation](#25-liste-fermée-dopérations-et-validation)
  26. [Résolution déterministe des colonnes et ambiguïté](#26-résolution-déterministe-des-colonnes-et-ambiguïté)
  27. [Reformulation par le LLM sous contrôle](#27-reformulation-par-le-llm-sous-contrôle)
  28. [Temps de réponse : mesures avant / après](#28-temps-de-réponse--mesures-avant--après)
  29. [Modèle demandé hors domaine](#29-modèle-demandé-hors-domaine)

---

# Phase 1 — LLM local et multilingue

## 1. LLM local plutôt qu'une API (Mistral)

**Choix.** Le chatbot n'utilise plus l'API Mistral : le modèle tourne sur la machine via Ollama. Plus aucune clé API.

**Pourquoi.**
- **Confidentialité** : les utilisateurs envoient des fichiers métier (clients bancaires, ventes, prêts). Avec une API, chaque question envoie des lignes de ces fichiers à un serveur externe. En local, aucune donnée ne quitte la machine.
- **Coût et quotas** : pas de facturation par token, pas de limite de requêtes.
- **Disponibilité** : fonctionne sans Internet (démonstration en salle sans réseau).
- **Sécurité** : plus de clé secrète à protéger (l'ancienne clé était écrite en dur dans le code).

**Alternatives écartées.**
| Alternative | Pourquoi écartée |
|---|---|
| Garder l'API Mistral | Données envoyées à un tiers, coût, dépendance réseau |
| OpenAI / Gemini | Mêmes inconvénients, plus une question de souveraineté des données |
| Modèle via `transformers` (Python pur) | Pas de quantification simple, beaucoup plus de RAM, plus lent sur CPU |

**Contrepartie assumée.** Un modèle local de 3B est **moins bon et plus lent** qu'une API (mesuré : 30 à 90 s par réponse sur ce CPU, contre ~2 s pour l'API). C'est pour cela que les phases suivantes confient les **calculs** à pandas (Phase 3) : le LLM ne sert qu'à comprendre la question et à rédiger la réponse.

> **Jury :** *« Pourquoi ne pas garder l'API, qui est plus performante ? »*
> **Réponse :** Parce que la plateforme traite des données confidentielles d'entreprise ; en local, rien ne sort de la machine, il n'y a ni coût ni clé à protéger. La perte de qualité est compensée par l'architecture : le LLM ne calcule pas, il oriente et reformule.

## 2. Ollama comme serveur de modèles

**Choix.** Ollama (v0.34) sert le LLM et le modèle d'embeddings sur `http://localhost:11434`.

**Pourquoi.**
- Installation Windows en un clic, modèles téléchargés avec `ollama pull`.
- Modèles **quantifiés** (GGUF Q4) : ils tiennent dans 8 Go de RAM.
- API HTTP simple, avec **sortie JSON contrainte** (`format` + JSON schema), indispensable au routeur de la Phase 3.
- Charge/décharge les modèles automatiquement et gère le CPU et le GPU.

**Alternatives écartées.** *llama.cpp* seul (même moteur, mais à compiler et sans gestion des modèles) ; *LM Studio* (interface graphique, moins adapté à un serveur) ; *vLLM* (exige un GPU NVIDIA puissant, pas de Windows natif).

> **Jury :** *« Ollama, c'est quoi exactement ? »*
> **Réponse :** Un serveur local qui exécute des modèles de langage quantifiés (moteur llama.cpp) et les expose par une API HTTP, comme une API cloud, mais sur ma machine.

## 3. Qwen2.5 3B comme modèle de chat

**Choix.** `qwen2.5:3b` (3,1 milliards de paramètres, quantifié Q4_K_M, **1,9 Go**).

**Pourquoi.**
- **Mémoire** : 1,9 Go plus le contexte, cela laisse de la place pour Windows, MySQL, Flask et le modèle d'embeddings dans 8 Go. Un 7B (~4,7 Go) ferait saturer la RAM et basculer sur le disque (swap).
- **Multilingue** : Qwen2.5 est entraîné sur plus de 29 langues, dont le **français, l'anglais et l'arabe** (vérifié : réponse correcte en arabe standard).
- **Sortie structurée** : bon suivi des formats JSON, indispensable pour le routeur (Phase 3).
- Contexte jusqu'à 32k tokens (on en utilise 4096).

**Alternatives écartées.**
| Modèle | Raison |
|---|---|
| Llama 3.2 3B | Arabe nettement plus faible |
| Phi-3.5 mini (3,8B) | Plus lourd, arabe faible |
| Mistral 7B / Qwen2.5 7B | Meilleurs, mais trop gros pour 8 Go avec le reste de la plateforme |
| Gemma 2 2B | Plus léger mais moins fiable sur le JSON |

> **Jury :** *« Pourquoi pas un modèle plus gros ? »*
> **Réponse :** 8 Go de RAM : un 7B quantifié occupe ~4,7 Go à lui seul ; avec Windows, MySQL et les embeddings, la machine swappe et une réponse prend plusieurs minutes. Le 3B est le plus gros modèle utilisable confortablement. Le nom du modèle est dans `.env` : passer au 7B sur une machine plus puissante ne demande aucune modification du code.

## 4. Paramètres du LLM : `temperature=0`, `num_ctx=4096`

- **temperature = 0** : le modèle choisit toujours le mot le plus probable, donc la même question donne la même réponse. Pour de l'analyse de données on veut de la **reproductibilité**, pas de la créativité. C'est aussi indispensable pour un JSON de routage stable.
- **num_ctx = 4096 tokens** : assez pour la liste des colonnes, les statistiques, 8 extraits et la question. Chaque doublement du contexte augmente la RAM (cache KV) et le temps de calcul ; 4096 est le compromis pour 8 Go.
- **num_predict = 800** : limite la longueur des réponses (et donc le temps de génération sur CPU).

> **Jury :** *« Que se passe-t-il si le prompt dépasse 4096 tokens ? »*
> **Réponse :** Ollama tronque le début du prompt. C'est une raison de plus pour la Phase 3 : au lieu d'envoyer `describe()` complet, on enverra au LLM seulement les colonnes, leurs types et 3 lignes, ce qui est beaucoup plus court.

## 5. nomic-embed-text et ses préfixes

**Choix.** `nomic-embed-text` (137M paramètres, 274 Mo, **vecteurs de 768 dimensions**) pour transformer les lignes du fichier et les questions en vecteurs.

**Pourquoi.**
- Très léger (tourne vite sur CPU), disponible directement dans Ollama.
- Bonnes performances de recherche (benchmark MTEB), meilleures que d'anciens modèles comme `text-embedding-ada-002` d'OpenAI.
- **Préfixes de tâche** : le modèle a été entraîné avec `search_document: ` devant les textes indexés et `search_query: ` devant les questions. Les omettre dégrade la qualité de la recherche. On les ajoute automatiquement dans `services/llm.py` (classe `NomicEmbeddings`).

**Alternatives écartées.** `mxbai-embed-large` (1024 dim., 670 Mo : plus lourd) ; `bge-m3` (excellent en multilingue mais 1,2 Go) ; embeddings HuggingFace via `sentence-transformers` (charge PyTorch en mémoire en plus d'Ollama).

> **Jury :** *« À quoi servent les préfixes ? »*
> **Réponse :** Le modèle encode différemment une question et un document ; le préfixe lui dit lequel des deux il reçoit. C'est la façon dont il a été entraîné, donc la recherche est plus précise.

## 6. FAISS comme base vectorielle

**Choix.** FAISS (déjà utilisé dans le projet), un index par fichier, sauvegardé dans `uploads/vector_indices/file_<id>/`.

**Pourquoi.** Bibliothèque (pas de serveur à installer), très rapide sur CPU, et largement suffisante pour quelques milliers de lignes par fichier. Elle était déjà en place : on la garde.

**Alternatives.** ChromaDB (plus de dépendances, base SQLite en plus) ; pgvector (demande PostgreSQL alors qu'on est sur MySQL) ; Milvus/Qdrant (serveurs dédiés, disproportionnés ici).

> **Jury :** *« Pourquoi une base vectorielle séparée de MySQL ? »*
> **Réponse :** MySQL 9 a un type VECTOR mais pas de recherche de plus proches voisins efficace ; FAISS est conçu pour cela et ne demande aucun serveur.

## 7. langchain-ollama (version 1.0.1)

**Choix.** `ChatOllama` et `OllamaEmbeddings` du package officiel `langchain-ollama`, à la place de l'ancien code `requests` écrit à la main (trois points d'accès de secours différents).

**Pourquoi.** Code plus court et maintenu par LangChain ; il s'intègre directement avec FAISS (`langchain-community`) ; il gère le paramètre `format` (sortie JSON) pour la Phase 3.

**Pourquoi la version 1.0.1 et pas la dernière (1.2.0).** La 1.2.0 imposait de passer `langchain-core` de 1.2.7 à 1.8.4, au risque de casser `langchain-community` 0.4.1 (FAISS). La 1.0.1 n'ajoute que 2 packages (`langchain-ollama`, `ollama`) **sans rien mettre à jour** (vérifié avec `pip install --dry-run`).

## 8. Réindexation FAISS et envoi par lots

**Pourquoi réindexer.** La dimension des vecteurs dépend du modèle d'embeddings (768 pour nomic). Un ancien index construit avec un autre modèle est incompatible. `reindex.py` recalcule les vecteurs de tous les fichiers en base. De plus, `rag.py` vérifie la dimension à chaque chargement et reconstruit l'index si elle est fausse.

**Envoi par lots de 32.** Problème constaté : envoyer les 1000 lignes d'un fichier en une seule requête faisait planter le processus interne d'Ollama (erreur `/tokenize`, connexion refusée). Avec des lots de 32 lignes, les 1000 lignes sont indexées en ~110 s sans erreur.

**Fichiers perdus.** Le script signale les fichiers référencés en base mais absents du disque (ici `produits_magasin.csv`, id 1), sans supprimer leurs lignes : l'historique des questions est conservé.

## 9. Multilinguisme et limite de la derja

**Choix.**
1. **Détection de la langue par règles** (`services/langue.py`) : alphabet (arabe ou latin), mots-outils français ou anglais, marqueurs derja (`شنوة`, `برشا`, `قداش`…) et **arabizi** (chiffres utilisés comme lettres : `a3tini`, `9addech`, `wa7da`).
2. Langue de réponse :
   | Langue détectée | Réponse |
   |---|---|
   | français | français |
   | anglais | anglais |
   | arabe standard | arabe standard |
   | derja en lettres latines | **français** + avertissement |
   | derja en lettres arabes | **arabe standard** + avertissement |
3. **Glossaire derja → français / arabe** (environ 150 mots courants) appliqué à la question avant l'envoi au LLM. La question originale est jointe au prompt.

**Pourquoi la détection par règles et pas par le LLM.** Elle est instantanée (le LLM prend plusieurs secondes sur CPU), déterministe et testable. Surtout, **le modèle 3B ne reconnaît pas la derja**, donc il ne peut pas la détecter lui-même.

**Limite de la derja : test réalisé (Phase 1).**
| Entrée | Réponse de qwen2.5:3b sans glossaire |
|---|---|
| `a3tini 9addech el ventes fil chhar elli fet` (« donne-moi combien de ventes le mois dernier ») | « Le prix des ventes dans la chaîne est élevé » ❌ |
| `شنوة أكثر منتوج تباع برشا؟` (« quel produit s'est le plus vendu ? ») | « Quelle est la valeur du cacao vendu à Résia ? » ❌ |
| Demande de répondre en derja | Le modèle a pris la derja pour du **wolof** ❌ |
| Après glossaire : `donne-moi combien le ventes dans le mois dernier` | « Pourriez-vous me dire combien ont été les ventes du mois dernier ? » ✅ |

Conclusion : le modèle **ne comprend pas** la derja et **ne sait pas l'écrire**. On ne répond donc jamais en derja : on traduit la question par glossaire, on répond en français ou en arabe standard, et on affiche un avertissement écrit à la main (pas généré par le LLM).

**Limites restantes (à dire honnêtement).** Le glossaire est mot à mot : une phrase derja avec beaucoup de mots absents du glossaire, ou des préfixes collés (`w`, `el`, `bel` attachés au mot en lettres arabes), sera mal traduite. Pistes d'amélioration : un modèle plus gros (Qwen2.5 7B comprend mieux le dialecte), ou un modèle spécialisé dialectes maghrébins.

> **Jury :** *« Votre plateforme parle derja ? »*
> **Réponse :** Elle **comprend** les questions en derja courantes grâce à un glossaire, mais répond en français ou en arabe standard, parce que nos tests montrent qu'un modèle 3B ne génère pas la derja de façon fiable (il l'a confondue avec du wolof). Le système le signale à l'utilisateur au lieu de produire une réponse fausse.

## 10. Ollama indisponible : message clair, pas de crash

**Choix.** Avant chaque appel, `services/llm.py` interroge `/api/tags` (réponse en quelques millisecondes, aucun modèle n'est chargé). Si Ollama est arrêté ou si le modèle n'est pas installé, une exception dédiée `OllamaIndisponibleError` est levée. La route renvoie alors un **code HTTP 503** avec un message **dans la langue de l'utilisateur** (« Vérifiez qu'Ollama est lancé : `ollama serve` »). Une route `/api/sante` donne l'état d'Ollama et de MySQL.

**Pourquoi.** Avant, une erreur Ollama remontait en erreur 500 avec la trace technique affichée à l'utilisateur. Les messages d'erreur sont écrits à la main dans les 3 langues, car le LLM ne peut pas les traduire puisqu'il est justement indisponible.

**Autre problème corrigé.** La console Windows est en cp1252 : un `print` contenant de l'arabe faisait **planter la requête** (`UnicodeEncodeError`, constaté pendant les tests). Les sorties sont maintenant en UTF-8 et les `print` de debug sont remplacés par le module `logging`.

## 11. Configuration dans `.env` + `config.py`

**Choix.** Toutes les valeurs qui dépendent de l'environnement (URL d'Ollama, noms des modèles, connexion MySQL, chemins, `SECRET_KEY`, debug) sont dans `.env`, lues **une seule fois** par `config.py`. `.env` est dans `.gitignore` ; `.env.example` documente chaque variable.

**Pourquoi.** Les secrets ne sont plus dans le code ni dans Git. On peut changer de modèle ou de base sans toucher au code. Il y a une seule source de vérité : avant, la connexion MySQL était copiée dans `app.py` **et** dans `reindex.py`.

## 12. Corrections de sécurité

| # | Problème | Risque concret | Correction |
|---|---|---|---|
| 1 | `/ask_ia` acceptait n'importe quel `file_id` | Un utilisateur pouvait interroger le fichier d'un autre en changeant l'id (faille **IDOR**) | Requête SQL avec `AND id_utilisateur = %s` : 404 sinon |
| 2 | `/view_report/<path>` faisait `send_file(chemin)` | Téléchargement de **n'importe quel fichier** du serveur (`../.env`, `C:/Windows/...`) : *path traversal* | Le chemin doit exister dans `rapports`, appartenir à l'utilisateur (ou admin) et être dans le dossier des rapports |
| 3 | `/admin/toggle_user` sans contrôle de rôle | Un utilisateur simple pouvait **bloquer l'administrateur** | Décorateur `@admin_required` (aussi sur `delete_user`) |
| 4 | `SECRET_KEY = 'ma_cle_secrete_123'` dans le code | Clé publique sur GitHub : n'importe qui peut **forger un cookie de session** et se connecter comme admin | Clé aléatoire de 64 caractères hexadécimaux dans `.env` |
| 5 | Mot de passe MySQL dans le code | Fuite si le dépôt est public | `.env` |
| 6 | `app.run(debug=True)` | Le débogueur Werkzeug permet **d'exécuter du code** depuis le navigateur | `FLASK_DEBUG=0` par défaut |
| 7 | Upload : même nom de fichier, donc écrasement | L'utilisateur A écrase le fichier de B (cas réel : fichiers 29 et 30) ; supprimer l'un effaçait l'autre | Nom disque unique `U<id>_<date>_<nom>` ; suppression physique seulement si plus aucune ligne ne pointe dessus |
| 8 | Utilisateur bloqué gardait sa session | Le blocage n'avait d'effet qu'à la connexion suivante | `load_user` refuse les comptes bloqués : déconnexion immédiate |

Toutes ces corrections sont testées automatiquement (voir CHANGELOG, « Tests Phase 1 »).

> **Jury :** *« Qu'est-ce qu'une faille IDOR ? »*
> **Réponse :** *Insecure Direct Object Reference* : l'application fait confiance à un identifiant envoyé par le client sans vérifier que l'objet appartient à l'utilisateur. Il suffisait de changer `file_id` dans la requête pour lire les données d'un autre client.

---

# Phase 2 — Domaine d'activité, déconnexion et base de données

## 13. Sauvegarde et migrations versionnées

**Choix.**
- `migrate.py` applique les scripts `migrations/NNN_nom.sql` dans l'ordre.
- Il fait **toujours un `mysqldump` vérifié avant** de modifier la base (fichier non vide, marqueur « Dump completed »). Si la sauvegarde échoue, rien n'est modifié.
- Il note chaque migration appliquée dans la table `schema_migrations`, pour ne jamais l'appliquer deux fois.
- Il compare le **nombre de lignes avant et après** et signale toute différence comme une erreur.

**Démarche suivie en Phase 2 (prudence maximale).**
1. Sauvegarde manuelle de l'état d'origine : `backups/dataia_20261125_225632_manuel.sql`.
2. **Test de restauration** : la sauvegarde a été rejouée dans une base temporaire et les 4 tables ont été retrouvées identiques (7 / 6 / 64 / 8 lignes). Une sauvegarde qu'on n'a jamais restaurée n'est pas une sauvegarde prouvée.
3. **Répétition** de la migration sur une copie (`dataia_test`), puis vérification des moteurs, des clés et des orphelins.
4. Migration réelle (nouvelle sauvegarde automatique : `backups/dataia_20261125_225728_avant_migration_001.sql`).
5. **Comparaison ligne par ligne et colonne par colonne** avec la sauvegarde d'avant migration : aucune différence inattendue. Les seules différences sont les 39 `id_fichier` orphelins passés à NULL, tous tracés (point 16).
6. Test d'une **installation neuve** : `database.sql` (schéma v1) puis `migrate.py`, ce qui donne le même schéma final.

**Pourquoi des scripts SQL versionnés plutôt que des modifications dans phpMyAdmin.** C'est reproductible (même résultat sur la machine du jury), traçable dans Git, relisible, et on sait toujours quelle version du schéma est installée. C'est le principe de Flyway ou Liquibase, appliqué ici en ~150 lignes de Python.

**Alternatives.** *Alembic* (outil de migration de SQLAlchemy) : le projet n'utilise pas l'ORM SQLAlchemy mais `mysql-connector` avec du SQL direct, il faudrait donc décrire tout le schéma en Python. *Flyway* : nécessite Java. Pour 4 tables et un projet académique, des fichiers SQL lisibles sont plus pédagogiques.

> **Jury :** *« Et si la migration plante au milieu ? »*
> **Réponse :** Les `ALTER TABLE` de MySQL ne sont pas annulables par une transaction ; c'est justement pour cela que `migrate.py` fait une sauvegarde **avant**, s'arrête à la première erreur et affiche la commande de restauration. J'ai aussi répété la migration sur une copie avant de l'appliquer.

## 14. MyISAM vers InnoDB

**Constat.** Les 4 tables étaient en **MyISAM**. Ce moteur **ignore les clés étrangères** (on peut les écrire, elles ne sont pas vérifiées) et n'a **pas de transactions**. Conséquence visible : 39 questions pointaient vers des fichiers supprimés.

**Choix.** Conversion en **InnoDB** (moteur par défaut de MySQL depuis la version 5.5).

| | MyISAM | InnoDB |
|---|---|---|
| Clés étrangères | ignorées | **vérifiées** |
| Transactions (COMMIT/ROLLBACK) | non | **oui** |
| Verrouillage | table entière | **par ligne** (plusieurs utilisateurs en même temps) |
| Résistance aux crashs | réparation manuelle | **journal de reprise automatique** |

> **Jury :** *« Pourquoi vos tables étaient-elles en MyISAM ? »*
> **Réponse :** Elles avaient probablement été créées depuis phpMyAdmin avec ce moteur. Le fichier `database.sql` du dépôt indiquait InnoDB mais ne correspondait pas à la base réelle : j'ai vérifié la base elle-même (`SHOW CREATE TABLE`) avant de migrer.

## 15. Clés étrangères : CASCADE ou SET NULL

| Clé | Règle | Raison |
|---|---|---|
| `fichiers.id_utilisateur` | CASCADE | Les fichiers d'un utilisateur supprimé n'ont plus de propriétaire |
| `questions.id_utilisateur` | CASCADE | Idem |
| `questions.id_fichier` | **SET NULL** | Supprimer un fichier **ne doit pas effacer l'historique des questions** (contrainte du cahier des charges) |
| `rapports.id_question` | **SET NULL** | Un rapport PDF reste consultable par l'admin |
| `modeles_ml.id_utilisateur` / `simulations.id_utilisateur` | CASCADE | Données personnelles de l'utilisateur |
| `modeles_ml.id_fichier` | SET NULL | On garde la trace des métriques d'un modèle même si le fichier est supprimé |

Testé : supprimer un fichier laisse la question en base avec `id_fichier = NULL`, et insérer un fichier pour un utilisateur inexistant est refusé (erreur MySQL 1452).

## 16. Les 39 questions orphelines (sans perte de données)

**Problème.** Créer la clé `questions → fichiers` est impossible tant que des questions pointent vers des fichiers qui n'existent plus. Ces orphelins venaient de l'ancienne route `delete_file`, qui supprimait le fichier sans s'occuper des questions liées (MyISAM ne l'empêchait pas).

**Options étudiées.**
| Option | Verdict |
|---|---|
| Supprimer les 39 questions | ❌ perte de données et d'historique |
| Créer de faux fichiers « fantômes » | ❌ fausse donnée dans la base |
| Ne pas créer la clé étrangère | ❌ le problème continue |
| **Mettre `id_fichier` à NULL et garder l'ancienne valeur dans `migration_orphelins`** | ✅ retenue |

La table `migration_orphelins` garde pour chaque ligne : la table, l'id de la ligne, la colonne et l'**ancienne valeur**. La migration est donc **sans perte d'information** (vérifié : 39 / 39 valeurs retrouvées). Les questions restent comptées dans les statistiques de l'admin.

## 17. Colonne `domaine` en ENUM

**Choix.** `domaine ENUM('Banque','E-commerce','Finance','Poste','Assurance','Télécom','Industrie','Autre') NOT NULL DEFAULT 'Autre'`. Les 7 comptes existants ont reçu `Autre`.

**Pourquoi.** La base refuse toute valeur hors liste (intégrité garantie même si l'application avait un bug). La colonne est lisible directement dans phpMyAdmin et stockée sur 1 octet. Le formulaire valide **aussi côté serveur** (`services/domaines.py`), car un `<select>` HTML peut être contourné en envoyant une requête à la main (testé : le domaine « Pirate » est refusé).

**Alternative : une table `domaines` avec une clé étrangère.** Plus souple si les domaines changent souvent ou s'ils ont des attributs (description, icône). Écartée : la liste est fixe dans le cahier des charges, et un ENUM évite une jointure. Ajouter un domaine = une migration `ALTER TABLE` + une ligne dans `services/domaines.py`.

> **Jury :** *« À quoi sert le domaine ? »*
> **Réponse :** Il détermine les modèles de Machine Learning proposés à l'utilisateur (Phase 5) : tous les domaines ont la prévision du CA et la détection d'anomalies, et la Banque a en plus le modèle de churn.

## 18. Tables `modeles_ml` et `simulations`

- **`modeles_ml`** : une ligne par **exécution** d'un modèle (qui, sur quel fichier, quel type, quel algorithme, quelles métriques, où sont les données nettoyées). Elle permet d'afficher l'historique et de justifier chaque résultat.
- **`simulations`** : une ligne par simulation « what-if » du simulateur (entrées saisies et résultat).
- **Colonnes JSON** (`parametres_json`, `entrees_json`, `resultat_json`) : les entrées varient selon le modèle (horizon et colonne pour la prévision, 10 variables pour le churn…). Une colonne JSON évite une table par modèle ; MySQL vérifie que le JSON est valide.
- **Métriques en colonnes séparées** (`metrique_mape`, `metrique_mae`, `metrique_accuracy`) plutôt que dans le JSON : on peut trier et filtrer en SQL (« meilleur MAPE »).
- **Nommage** : clés primaires `id_modele` et `id_simulation`, sur le modèle des tables existantes (`id_utilisateur`, `id_fichier`…), plutôt que `id`. Noms de tables en minuscules, comme les tables existantes (et MySQL sous Windows les met de toute façon en minuscules).
- **Index** `(id_utilisateur, type)` et `(id_utilisateur, date_simulation)` : ce sont les filtres de l'historique.
- `rapports.chemin_graphique` **existait déjà** dans la base réelle ; seule `type_graphique` a été ajoutée.

## 19. Déconnexion fiable

**Constats (Phase 0).** La déconnexion appelait seulement `logout_user()`. La page admin, qui n'hérite pas de `base.html`, **n'avait aucun bouton de déconnexion**.

**Corrections.**
1. `logout_user()` **et** `session.clear()` : toute la session est détruite, pas seulement l'identifiant.
2. **`Cache-Control: no-store`** sur toutes les pages vues par un utilisateur connecté : après déconnexion, le bouton « Précédent » du navigateur ne réaffiche pas une page protégée depuis le cache.
3. Bouton **Déconnexion** sur toutes les pages connectées, page admin comprise, avec un identifiant `btn-deconnexion` vérifié par les tests.
4. `/logout` sans `@login_required` : un utilisateur dont la session a expiré est simplement renvoyé vers `/login` au lieu de recevoir une erreur.
5. `session.clear()` aussi à la connexion : aucune donnée d'une session précédente n'est conservée.

**Testé** : après déconnexion, `/dashboard`, `/profil`, `/mes_fichiers`, `/chat/<id>`, `/admin/dashboard` et `/ask_ia` sont tous refusés (redirection vers `/login`).

**Limite connue.** La déconnexion se fait par un lien (GET). Un site malveillant pourrait déconnecter l'utilisateur en lui faisant charger ce lien (CSRF de déconnexion). Le risque est faible, car l'attaquant ne peut que déconnecter. Le frontend React (Phase 6) utilisera `POST /api/logout`.

## 20. Profil et administration du domaine

- **Profil** (`/profil`) : l'utilisateur modifie son nom et son domaine. L'email n'est pas modifiable ici, car c'est l'identifiant de connexion.
- **Admin** : une colonne « Domaine » avec une liste déroulante envoyée automatiquement au changement (`POST /admin/set_domaine/<id>`, protégée par `@admin_required` ; testé : 403 pour un non-admin).
- **Inscription** : un email déjà utilisé affiche « Un compte existe déjà avec cet email ». Avant, l'**erreur SQL brute** était montrée, ce qui révélait la structure de la base. Les emails sont enregistrés en minuscules.

---

# Phase 3 — Routeur hybride : le LLM comprend, pandas calcule

## 21. Pourquoi le RAG seul ne suffit pas pour les données tabulaires

Le RAG (*Retrieval-Augmented Generation*) cherche les **quelques lignes** les plus proches de la question (8 sur 1000 dans DataIA), puis demande au LLM de répondre avec ces lignes.

- Un **total**, une **moyenne** ou un **comptage** portent sur **toutes** les lignes. Avec 8 lignes sur 1000, le LLM ne peut pas les calculer : il **invente** un chiffre plausible.
- Un LLM ne sait pas faire de calcul exact : il prédit des mots. Même avec toutes les lignes dans le prompt, additionner 1000 nombres « de tête » donne une valeur fausse. De toute façon, 1000 lignes ne tiennent pas dans 4096 tokens.
- La recherche par similarité convient au **texte** (« quel client s'appelle Alpha ? »), pas à l'**agrégation** (« combien… au total ? »).

Conclusion : il faut **séparer la compréhension** de la question (le LLM) et **le calcul** (pandas, exact et déterministe).

## 22. Exemple réel avant / après : produits_magasin.csv

**Le fichier** : 5 produits, colonnes `product_id, product_name, category, price, stock_quantity`. **Il n'y a aucune colonne de ventes.**

| | « Quel est le total des ventes ? » | « ما هو مجموع المبيعات؟ » |
|---|---|---|
| **Avant** (observé par l'utilisatrice) | `105.00` | `106.20 دينار` |
| **Avant** (relancé pour le banc de mesure) | `Le total des ventes est de 150.` | `مجموع المبيعات هو 100.30 دينار.` |
| **Après (Phase 3)** | Demande de précision | **La même** demande de précision, en arabe |

Aucune des valeurs « avant » ne correspond à un calcul possible : ce sont des chiffres **inventés**, et différents à chaque langue et à chaque exécution.

**Réponse après la Phase 3** (identique en français, anglais, arabe et derja) :

> Ce fichier ne contient pas de colonne correspondant à « ventes ». Sur quelle colonne voulez-vous calculer ce total ? Voici les options possibles, calculées par pandas :
>
> | Option | Résultat (Total) |
> |---|---|
> | `price` | 10,7 |
> | `stock_quantity` | 275 |
> | `price × stock_quantity` | 424 |
>
> *(3 boutons cliquables ; « Quel est le total de price × stock_quantity ? » donne **424**, la valeur du stock)*

**Test automatique** : `tests/test_routeur_hybride.py` vérifie que, pour les 4 langues, les options et leurs valeurs (10,7 / 275 / 424) sont **exactement les mêmes**, qu'aucune valeur inventée (105, 106,2, 150, 100,3) n'apparaît, et que la suggestion cliquée donne 424.

**Quand une colonne de ventes existe** (`sales_data_1000_rows.xlsx`) : « ventes » est résolu en `Total_Price`. La réponse vaut **16 037 348** dans toutes les langues et l'indique : « ℹ️ « ventes » a été interprété comme la colonne `Total_Price`. » L'ancien pipeline répondait `16037.35`.

> **Jury :** *« Pourquoi ne pas choisir automatiquement price × quantité ? »*
> **Réponse :** Parce que ce serait une supposition : « ventes » pourrait être le chiffre d'affaires, le nombre d'articles ou la valeur du stock. Quand le fichier contient une colonne de ventes, le système la choisit et le dit ; sinon il demande, en montrant le résultat exact de chaque option. Une question en plus vaut mieux qu'un chiffre faux présenté comme vrai.

## 23. Routeur hybride : règles puis LLM

**Choix.** Chaque question est classée dans un *intent* : `stat`, `text`, `graph`, `forecast`, `anomaly`, `churn` ou `export`.

1. **Règles par mots-clés** (`services/router.py`), en français, anglais, arabe et derja traduite, pour les intents **sans ambiguïté** : « graphique / chart / رسم », « anomalie / fraude / شاذ », « prévision / forecast / توقع », « churn / quitter la banque / مغادرة », « PDF / exporter ». C'est instantané et ne demande aucun appel au LLM.
2. Sinon, le **LLM classe la question** avec une sortie JSON contrainte (point 24) : `stat` ou `text`, et pour `stat`, l'opération, la colonne et les filtres.
3. Selon l'intent :
   - `stat` → **pandas** ;
   - `text` → RAG ;
   - `graph` → ancien format en attendant la Phase 4 ;
   - `forecast`, `anomaly`, `churn` → registre des modèles selon le domaine ;
   - `export` → bouton PDF.

**Pourquoi des règles avant le LLM.** Un mot comme « graphique » ne laisse aucun doute. Payer 5 s de LLM pour le reconnaître serait du gaspillage, et les règles ne se trompent pas de langue.

**Pièges évités dans les règles.** « rapport » seul n'est pas un mot-clé d'export (« par rapport au mois dernier ») ; testé.

**« Quelles sont les valeurs de X ? » aussi par pandas.** Mesuré pendant les tests de non-régression : via le RAG, le modèle 3B ne citait que les valeurs présentes dans les 8 lignes extraites (« Quelles régions ? » → 4 régions sur 5 ; en arabe → 2 sur 5), alors que la liste complète figurait dans le prompt. Lister les valeurs d'une colonne est une question **exacte** : une règle (« quels sont les X », « which X », « ما هي X », derja « chnowa el X ») la transforme en `count` regroupé par X. Le résultat est la liste complète avec le nombre de lignes de chaque valeur, **sans appel au LLM** (0,04 s). Deux garde-fous :
- pas de règle s'il y a un mot de calcul (« Quel produit a le **plus** de ventes ? ») ;
- pas de règle si une valeur du fichier est citée (« Quels clients ont le statut **Pending** ? » est un filtre, laissé au LLM).

## 24. Sortie JSON contrainte plutôt que génération de code

**Choix.** Le paramètre `format` d'Ollama reçoit un **JSON schema** (`services/prompts.py`, `schema_routeur`). Ollama le transforme en **grammaire** et, à chaque token, n'autorise que les tokens qui gardent le JSON valide. En particulier, les noms de colonnes sont des `enum` construits à partir du fichier : le modèle **ne peut physiquement pas** écrire une colonne qui n'existe pas.

Exemple de sortie réelle : `{"intent": "stat", "operation": "count", "colonne": null, "filtres": [{"colonne": "Status", "operateur": "==", "valeur": "Pending"}]}`

**Alternatives écartées.**
| Approche | Problème |
|---|---|
| Le LLM écrit du code pandas exécuté par `eval`/`exec` (ex. *PandasAI*, agent pandas de LangChain) | **Faille de sécurité** : un fichier piégé ou une question malveillante peut faire exécuter n'importe quel code sur le serveur (« supprime le disque »). Et un modèle 3B écrit souvent du code faux. Interdit par le cahier des charges. |
| Le LLM écrit du SQL | Même risque (injection), et les données sont dans des fichiers, pas en base. |
| JSON demandé « dans le prompt », sans contrainte | Un 3B ajoute du texte autour, oublie une accolade, invente des colonnes : il faut le réparer, et ça échoue de temps en temps. |
| Fonctions (*tool calling*) | Possible avec Qwen2.5, mais moins fiable en 3B que la grammaire et sans `enum` dynamique aussi strict. |

> **Jury :** *« Qu'est-ce qui empêche le LLM de faire n'importe quoi ? »*
> **Réponse :** Trois barrières. 1) La grammaire d'Ollama : la sortie est forcément un JSON du bon format, avec des colonnes qui existent. 2) La validation Python : opération dans une liste fermée, colonnes vérifiées, types vérifiés. 3) Aucune exécution de code : chaque opération est une fonction écrite à l'avance.

## 25. Liste fermée d'opérations et validation

**Opérations** (`services/stats.py`) : `sum`, `mean`, `median`, `count`, `min`, `max`, `top`, `groupby`, `trend`, `percentage`. **Filtres** : `==`, `!=`, `>`, `>=`, `<`, `<=`, `contient`, `annee`, `mois`. On peut aussi mesurer un **produit de deux colonnes** (prix × quantité).

**Validation** (`router.valider_plan`) : opération autorisée ; colonnes existantes (tolère la casse) ; mesure numérique ; filtre valide (sinon il est ignoré et tracé) ; colonne de date lisible pour `trend` ; `n` borné entre 1 et 50. **En cas de problème, le système demande une précision** au lieu de deviner.

**Filtres ancrés dans la question (hallucination réelle corrigée).** Pendant les mesures, pour « Quel est le chiffre d'affaires par région ? », le LLM a ajouté le filtre `Status == Pending`, recopié d'un exemple de mon prompt. Le résultat portait donc sur 305 lignes au lieu de 1000 (Nabeul 1 109 536 au lieu de Sousse 3 607 262). La ligne de provenance l'a rendu visible, puis deux corrections ont suivi :
1. plus d'exemples concrets de valeurs dans le prompt système ;
2. **un filtre n'est conservé que si sa valeur est écrite dans la question** (« Pending », « 2023 », « mars » → 3). Un filtre rejeté est **signalé** dans la réponse au lieu d'être ignoré en silence. Testé automatiquement.

*Limite* : une valeur écrite dans une autre langue que celle du fichier (« تونس » pour `Tunis`) n'est pas reconnue comme ancrée. Le filtre est alors signalé comme non appliqué, et l'utilisateur doit écrire la valeur telle qu'elle apparaît dans le fichier.

**Prompt réduit** : le LLM reçoit seulement les colonnes, leur type (dérivé de `df.dtypes` : nombre / date / texte) et **3 lignes d'exemple**. Plus de `describe()` complet.

**Robustesse des types (problèmes trouvés en testant).**
- `INV-10001` était pris pour un nombre (on retirait les lettres). On ne convertit maintenant que les valeurs qui ont la **forme** d'un nombre, éventuellement avec une unité : « 100 DT », « 12 % », « € 45 ».
- « 1,200.50 » (format anglais) et « 1.234,56 » (format français) sont tous deux lus correctement : le dernier séparateur est le séparateur décimal.

## 26. Résolution déterministe des colonnes et ambiguïté

**Constat (mesuré).** Le LLM 3B choisissait la mauvaise colonne : `price` pour « ventes », `Total_Price` comme regroupement pour « top 3 products », et il ignorait « par région ». Ces choix pouvaient en plus varier selon la langue.

**Choix.** `services/semantique.py` décide **par règles**, de façon identique dans toutes les langues :

1. **Colonne citée** explicitement (« moyenne de stock_quantity », « price × stock_quantity ») : elle est respectée.
2. **Concept métier** reconnu (ventes / chiffre d'affaires / sales / مبيعات / الإيرادات ; quantité ; prix) : on prend la colonne correspondante, par ordre de priorité (`Sales`, puis `Total_Price`, puis `Montant`…). La réponse l'indique : « « ventes » a été interprété comme la colonne `Total_Price` ».
3. **Concept sans colonne** : **demande de précision** avec les options calculées par pandas (cas réel du point 22).
4. **Regroupement** : « par X », « by X », « pour chaque X », « top N X », « حسب X ». Le mot est relié à une colonne catégorielle grâce aux pluriels, à un dictionnaire de synonymes français / anglais / arabe (produit = product = منتج) et à l'article arabe « ال ».
5. **Période** : « par mois », « monthly », « شهري » donnent une évolution (`trend`).

**Ce que garde le LLM.** Le type de calcul et les filtres (« statut Pending », « en 2023 »), qu'il comprend bien.

**Détail technique.** La normalisation Unicode retire les hamzas de l'arabe (« أفضل » devient « افضل ») : les dictionnaires et les motifs arabes sont donc normalisés de la même façon (sinon « الإيرادات » n'était jamais reconnu ; trouvé par les tests).

## 27. Reformulation par le LLM sous contrôle

**Règle : la valeur affichée est toujours celle de pandas.**

1. Une **phrase modèle** est construite en Python, dans la langue de l'utilisateur, avec les nombres formatés : « **Total de `Total_Price`** : **16 037 348** » (fr), « 16,037,348 » (en, ar).
2. Pour un résultat **à une seule valeur**, le LLM peut écrire une phrase plus naturelle. Elle passe par un **garde-fou** : chaque nombre qu'elle contient doit correspondre (à 0,5 % près) à une valeur du résultat pandas ou de la question, sinon elle est **rejetée**. Le garde-fou gère les chiffres arabes-indiens (٤٢٤) et les formats français et anglais. Testé : « 105,00 » est rejeté, « ٤٢٤ » est accepté.
3. Une **ligne de provenance** est toujours ajoutée : « 🔢 *Calculé par pandas — opération : `sum` · colonne : `Total_Price` · 1 000 lignes utilisées sur 1 000* », avec les filtres et les valeurs ignorées.

**Pas de reformulation des tableaux.** Mesuré : pour « CA par région », le LLM recopiait les 5 lignes (78 tokens, +15 s) alors que le tableau est déjà affiché. La reformulation est réservée aux résultats à une valeur. `REFORMULATION_LLM=0` dans `.env` la désactive complètement.

## 28. Temps de réponse : mesures avant / après

**Protocole.** Les 6 mêmes questions, dans le même ordre, sur la même machine, avec un appel de préchauffage non mesuré. Le temps est mesuré de bout en bout sur `/ask_ia`, et les tokens sont relevés dans les métadonnées d'Ollama.

| # | Question (fichier) | Avant : temps | Avant : tokens du prompt | Avant : réponse | Après : temps | Après : tokens (routeur + reformulation) | Après : réponse |
|---|---|---|---|---|---|---|---|
| 1 | Total des ventes ? (produits_magasin) | 40,3 s | 929 | « 150 » ❌ | **11,3 s** | 547 | précision : 10,7 / 275 / 424 ✅ |
| 2 | مجموع المبيعات؟ (produits_magasin) | 41,7 s | 957 | « 100,30 دينار » ❌ | **5,4 s** | 546 | même précision ✅ |
| 3 | Total des ventes ? (sales_data) | 50,8 s | 2 642 | « 16037.35 » ❌ | **24,8 s** | 746 + 168 | **16 037 348** ✅ |
| 4 | CA par région ? | 65,5 s | 2 644 | camembert, 2 régions sur 5 ❌ | **5,9 s** | 749 | 5 régions, valeurs exactes ✅ |
| 5 | Factures au statut Pending ? | 45,9 s | 2 651 | « 141 » ❌ | **12,7 s** | 748 + 161 | **305** ✅ |
| 6 | Top 3 products by total sales? | 123,6 s | 2 632 | Printer / Chair / Keyboard ❌ | **6,9 s** | 748 | **Mouse / Laptop / Keyboard** ✅ |
| | **Moyenne** | **61,3 s** | **~2 080** | **0 / 6 exactes** | **11,2 s** (÷ 5,5) | **~680** | **6 / 6 exactes** |

*Résultats bruts : `mesures/phase3_avant.json` et `mesures/phase3_apres.json` (script : `tests/benchmark_routeur.py`).*

**Autres chemins (mesurés à part) :**
- **Liste des valeurs** (« Quelles sont les régions ? ») : **0,04 s**, sans appel au LLM (avant : 42 à 69 s et 4 régions sur 5).
- **Question texte (RAG)** (« Qui est le client de la facture INV-10002 ? ») : **environ 20 s** quand le cache de préfixe d'Ollama est chaud, **50 à 80 s** à froid (prompt de ~950 tokens). C'est le chemin le plus lent qui reste ; il ne sert plus qu'aux vraies questions descriptives.

**Pourquoi la question 3 reste à ~25 s.** C'est la première question sur un **nouveau fichier** : Ollama doit lire tout le prompt du routeur (~750 tokens), sans cache. Sur le même fichier, les questions 4 à 6 ne prennent que 5 à 7 s.

**Les 5 optimisations, par ordre d'effet :**

| # | Optimisation | Effet mesuré |
|---|---|---|
| 1 | **Pas de `describe()` complet** : colonnes, types et 3 lignes | Prompt de **~2 640 à ~730 tokens** (sales_data) |
| 2 | **100 % CPU** (`OLLAMA_NUM_GPU=0`) | Génération **3,2 → 8,7 tokens/s**. Sur la MX130 (2 Go), Ollama mettait 42 % du modèle sur le GPU ; les échanges CPU ↔ GPU à chaque token coûtaient plus que le calcul gagné. |
| 3 | **`127.0.0.1` au lieu de `localhost`** | **2,3 s → 0,3 s par connexion**. Sous Windows, `localhost` essaie d'abord IPv6 (`::1`) alors qu'Ollama n'écoute qu'en IPv4 ; il y avait 2 à 3 connexions par question. |
| 4 | **Pas d'appel LLM inutile** | Intents évidents par règles (0 appel), pas de reformulation des tableaux, vérification d'Ollama gardée 30 s |
| 5 | **`keep_alive=30m` + préchauffage** au démarrage de Flask | Le modèle reste en RAM : pas de rechargement (~10 s) à la première question ni après 5 min d'inactivité |

| 6 | **Recherche hybride** dans le RAG (mot-clé exact puis vecteurs) + **5 extraits au lieu de 8** | Prompt RAG de ~1 420 à ~950 tokens ; « facture INV-10002 » retrouvée à coup sûr (les embeddings ne la trouvaient pas) |

**Limite restante.** Le premier appel sur un **nouveau fichier** reste plus lent : Ollama doit lire tout le prompt (~750 tokens à environ 40 tokens/s sur ce CPU). Les questions suivantes sur le même fichier profitent du **cache de préfixe** d'Ollama : l'appel au routeur passe d'environ 19 s à 5 s.

> **Jury :** *« Pourquoi ne pas utiliser le GPU ? »*
> **Réponse :** Je l'ai mesuré : la MX130 n'a que 2 Go et Ollama n'y met qu'une partie du modèle ; les allers-retours CPU ↔ GPU à chaque token rendent la génération 2,7 fois plus lente (3,2 contre 8,7 tokens/s). Le réglage est dans `.env` : sur une machine avec un vrai GPU, il suffit de vider `OLLAMA_NUM_GPU`.

## 29. Modèle demandé hors domaine

**Choix.** `services/ml/registry.py` décrit les modèles disponibles par domaine : tous les domaines ont la prévision du CA et la détection d'anomalies ; la Banque a en plus le churn. Si un utilisateur E-commerce demande « quels clients risquent de partir ? », le système répond poliment que ce modèle est réservé au domaine **Banque**, liste les modèles disponibles pour lui et rappelle qu'on peut changer de domaine dans le profil (testé).

Le registre est créé dès la Phase 3 pour que le routeur l'utilise. La Phase 5 y branchera l'exécution des modèles, sans changer le routeur.

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

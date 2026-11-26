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
- **Phase 4 — Graphiques à la demande**
  30. [Graphiques calculés par pandas, jamais par le LLM](#30-graphiques-calculés-par-pandas-jamais-par-le-llm)
  31. [Règles de choix du type de graphique](#31-règles-de-choix-du-type-de-graphique)
  32. [Type demandé mais inadapté](#32-type-demandé-mais-inadapté)
  33. [Plotly, et plotly.js servi en local](#33-plotly-et-plotlyjs-servi-en-local)
  34. [Export PNG : kaleido + Chrome déjà installé](#34-export-png--kaleido--chrome-déjà-installé)
  35. [Table `graphiques` (migration 002)](#35-table-graphiques-migration-002)
  36. [Graphiques de l'ancien format](#36-graphiques-de-lancien-format)
  37. [Tout à la demande, rien d'automatique à l'upload](#37-tout-à-la-demande-rien-dautomatique-à-lupload)
  38. [Temps de génération d'un graphique](#38-temps-de-génération-dun-graphique)
- **Phase 5 — Modèles de Machine Learning selon le domaine**
  39. [Registre des modèles par domaine](#39-registre-des-modèles-par-domaine)
  40. [Prévision : Prophet vs LightGBM vs ARIMA](#40-prévision--prophet-vs-lightgbm-vs-arima)
  41. [Split temporel](#41-split-temporel)
  42. [MAPE, MAE, RMSE : exemple chiffré](#42-mape-mae-rmse--exemple-chiffré)
  43. [Préparer une série pour la prévision](#43-préparer-une-série-pour-la-prévision)
  44. [Isolation Forest vs K-Means, DBSCAN, Z-score](#44-isolation-forest-vs-k-means-dbscan-z-score)
  45. [Arbre de décision pour le churn (et ses limites)](#45-arbre-de-décision-pour-le-churn-et-ses-limites)
  46. [Nettoyage des données et exports téléchargeables](#46-nettoyage-des-données-et-exports-téléchargeables)
  47. [Packages ML installés](#47-packages-ml-installés)
- **Phase 6 — Nouveau frontend et simulateur what-if**
  48. [Architecture : SPA React + API REST JSON](#48-architecture--spa-react--api-rest-json)
  49. [Sécurité de l'API](#49-sécurité-de-lapi)
  50. [Fond blanc : inversion de la palette](#50-fond-blanc--inversion-de-la-palette)
  51. [Simulateur what-if](#51-simulateur-what-if)
  52. [Graphiques dans React : Plotly plutôt que Recharts](#52-graphiques-dans-react--plotly-plutôt-que-recharts)
  53. [Où vit le frontend ?](#53-où-vit-le-frontend-)
- **Phase 7 — Support multi-formats**
  54. [Parser unifié](#54-parser-unifié)
  55. [OCR : RapidOCR ou Tesseract](#55-ocr--rapidocr-ou-tesseract)
  56. [Pièges des tableaux de documents](#56-pièges-des-tableaux-de-documents)
  57. [Réponses attendues sur le PDF et l'image](#57-réponses-attendues-sur-le-pdf-et-limage)
  58. [Aperçu et questions suggérées (rien d'automatique)](#58-aperçu-et-questions-suggérées-rien-dautomatique)

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

---

# Phase 4 — Graphiques à la demande

## 30. Graphiques calculés par pandas, jamais par le LLM

**Avant.** Le LLM écrivait lui-même un JSON `{"type_graph": "pie", "data": {"x": [...], "y": [...]}}` avec les valeurs du graphique. Mesuré : pour « CA par région », il dessinait **2 régions sur 5**, avec des valeurs inventées, en 65 à 75 s.

**Maintenant** (`services/charts.py`), en 4 étapes :
1. **Règles** : le type demandé (« en camembert », « courbe », « nuage de points », « رسم دائري »…), les colonnes (citées, ou concept « ventes » → `Total_Price`), le regroupement (« par région »), la période (« par mois »), l'agrégation (« moyenne », « nombre de ») et les filtres **ancrés** (« en 2024 », « à Tunis »). Ce sont les mêmes règles qu'en Phase 3, valables dans les 4 langues.
2. **LLM seulement si une colonne reste inconnue** (ex. « courbe des ventes » : quel axe X ?). Il produit une **spec JSON contrainte** `{type, x, y, agg, color}`, avec les noms de colonnes en `enum`. Il choisit des **colonnes**, jamais des **valeurs**. Sur le banc de mesure, 13 demandes sur 14 n'ont eu besoin d'**aucun** appel au LLM.
3. **pandas calcule** les données : `groupby`, ré-échantillonnage par période, `corr()`, valeurs brutes pour le nuage de points, l'histogramme et la boîte à moustaches.
4. **Plotly dessine.** Le titre est construit en Python (« Total de Total_Price par Region ») et non par le LLM, qui pourrait y glisser un chiffre.

**Vérifié par les tests** (`tests/test_graphiques.py`) : pour chaque type, les valeurs de la figure sont **recalculées avec pandas et comparées** (camembert = `groupby().sum()`, barres groupées = `pivot_table`, courbe = somme mensuelle, heatmap = `df.corr()`, filtre « Tunis »…).

> **Jury :** *« D'où viennent les chiffres du graphique ? »*
> **Réponse :** De pandas, comme pour les calculs : le LLM ne fait au plus que choisir les colonnes, dans une liste fermée. Sous chaque graphique, une ligne de provenance indique le calcul (« Total de Total_Price par Region · 1 000 lignes utilisées sur 1 000 »), et les tests comparent chaque valeur dessinée à pandas.

## 31. Règles de choix du type de graphique

Quand l'utilisateur ne précise pas le type, le choix suit les règles du cahier des charges, et **la raison est écrite dans la réponse** (ex. « Type choisi automatiquement : **courbe**, car `Date` est une date et la valeur est numérique »).

| Données concernées | Type choisi | Pourquoi |
|---|---|---|
| ≥ 3 colonnes numériques | **Carte de chaleur des corrélations** | Montre d'un coup les liens entre toutes les paires de colonnes |
| 2 colonnes numériques | **Nuage de points** (+ corrélation de Pearson) | Montre la relation entre deux mesures |
| Date + nombre | **Courbe** | L'axe du temps est continu et ordonné ; la courbe montre la tendance |
| Catégorie + nombre, **≤ 6 catégories** | **Camembert** | Parts d'un total, encore lisibles |
| Catégorie + nombre, > 6 catégories | **Barres** | Au-delà de 6 parts, un camembert devient illisible ; les barres se comparent facilement |
| 2 catégories + nombre | **Barres groupées** | Compare une 2e dimension dans chaque catégorie |
| 1 seule colonne numérique | **Histogramme** | Montre la distribution des valeurs |

**Détails.**
- La période de la courbe est choisie selon l'étendue des dates (≤ 45 jours → jour, ≤ 6 mois → semaine, ≤ 3 ans → mois…), sauf si l'utilisateur la précise.
- Le camembert n'est proposé automatiquement que pour une **somme** ou un **comptage** : une moyenne n'a pas de sens en « parts ».
- Au-delà de 20 barres (ou 8 parts de camembert), les petites catégories sont regroupées dans « Autres », et c'est signalé.
- Les **identifiants** (`product_id`, `Invoice_ID`) ne sont jamais utilisés comme axe ni dans une corrélation (trouvé en test : une « courbe des prix » le long de `product_id` n'avait aucun sens).

## 32. Type demandé mais inadapté

**Choix.** Le type demandé est respecté **s'il convient aux données**. Sinon, le système :
1. **explique** pourquoi : « ⚠️ Une **courbe** sert à montrer une évolution : elle a besoin d'une colonne de dates sur l'axe horizontal, or `Region` est une catégorie » ;
2. trace un **type adapté**, en restant proche de la demande (une courbe impossible devient des barres, avec les mêmes axes, plutôt qu'un camembert) ;
3. propose les **autres types possibles** pour ces données, en boutons cliquables. Chaque suggestion est réécrite pour être comprise par le moteur, et un test vérifie qu'elle produit bien le type annoncé.

| Demande | Problème | Remplacement |
|---|---|---|
| Courbe / aire sur une catégorie | Pas de date sur l'axe X | Barres |
| Courbe dans un fichier sans date | Aucune évolution possible | Explication seule |
| Camembert sans catégorie, ou avec des valeurs négatives | Pas de « parts » | Type automatique |
| Nuage de points avec une seule colonne numérique | Il en faut deux | Histogramme |
| Histogramme « par catégorie » | Un histogramme montre une distribution | Barres |
| Barres groupées avec une seule catégorie | Il en faut deux | Barres simples |
| Heatmap avec moins de 2 colonnes numériques | Pas de corrélation possible | Type automatique |

## 33. Plotly, et plotly.js servi en local

**Plotly** était déjà dans le projet. Il produit des graphiques **interactifs** (survol, zoom) dans le navigateur **et** des images statiques pour le PDF, avec une seule bibliothèque. Les 9 types demandés sont natifs.

**Alternatives.** *Matplotlib / Seaborn* : images statiques uniquement, pas d'interactivité dans le chat. *Recharts* (utilisé par le frontend React fourni) : uniquement dans le navigateur, donc impossible de générer le même graphique côté serveur pour le PDF. Le frontend devra afficher la figure Plotly (Phase 6).

**plotly.js servi en local** (route `/vendor/plotly.min.js`). L'ancien lien CDN `plotly-latest` est figé depuis 2021 en **version 1.58.5**, alors que plotly 6.5.2 produit des figures pour plotly.js **3.3.1** (encodage binaire des tableaux, nouveaux attributs). On sert donc le fichier fourni avec le paquet Python : versions assorties, et **aucun besoin d'Internet**, ce qui va dans le même sens que le LLM local.

## 34. Export PNG : kaleido + Chrome déjà installé

**Pourquoi un PNG ?** Le PDF (Phase 8) ne peut pas contenir un graphique interactif : il faut une image.

**kaleido 1.5.2** est la bibliothèque officielle d'export de Plotly. Depuis la version 1.0, elle **pilote un navigateur Chrome** au lieu d'embarquer son propre moteur (~80 Mo). Comme demandé, on utilise **le Chrome déjà installé** (`C:\Users\Lenovo\AppData\Local\Google\Chrome\Application\chrome.exe`, indiqué dans `.env` par `CHROME_PATH`) : aucune copie de Chrome n'est téléchargée.

**Mesuré.**
| Mode | 1er PNG | PNG suivants |
|---|---|---|
| Chrome relancé à chaque export (défaut) | ~4 s | ~4 s |
| **Chrome persistant** (`kaleido.start_sync_server`, lancé au démarrage de Flask) | ~2 à 4,6 s | **~0,2 s** |

**L'export se fait en arrière-plan** : la réponse du chat part tout de suite avec la figure interactive. Le PNG est écrit quelques dixièmes de seconde après, par un fil d'exécution unique (un seul Chrome, exports en file), puis son chemin est enregistré en base. Si l'export échoue, le PNG pourra être régénéré depuis le JSON au moment du PDF.

**Alternatives.** *kaleido 0.2* (ancien, moteur embarqué) : non compatible avec plotly 6. *Orca* : abandonné. *Matplotlib* pour le PDF : il faudrait dessiner chaque graphique deux fois, avec deux rendus différents.

**Arabe dans les images.** Vérifié visuellement : les titres arabes (« مجموع Total_Price حسب Region ») sont correctement liés et ordonnés de droite à gauche, car Chrome gère nativement le texte bidirectionnel.

## 35. Table `graphiques` (migration 002)

**Choix.** Une table dédiée : utilisateur, question, fichier, source (`chat` / `ml` / `simulation`), type, titre, **spec JSON**, chemin de la **figure JSON** et du **PNG**. Sauvegarde `mysqldump` vérifiée faite avant la migration, aucune ligne existante modifiée.

**Pourquoi pas les colonnes `rapports.chemin_graphique` / `type_graphique` ?** Un rapport PDF regroupe **plusieurs** graphiques, une question peut en produire un, et les modèles ML de la Phase 5 en produiront aussi : c'est une relation 1-n, qu'une colonne ne peut pas représenter. Les colonnes de `rapports` restent disponibles pour le graphique principal d'un rapport.

**Ce que la table permet.**
- **Réafficher les graphiques dans l'historique** du chat (avant, l'historique n'affichait que du texte brut).
- Retrouver **tous** les graphiques d'une conversation pour le PDF.
- **Justifier** chaque graphique : la spec indique le type, les colonnes, l'agrégation, les filtres et la raison du choix.

## 36. Graphiques de l'ancien format

16 réponses de l'historique contenaient l'ancien JSON écrit par le LLM, dont 9 portaient sur des fichiers déjà supprimés.

**Choix.** Les lignes en base **ne sont pas modifiées** : l'historique reste fidèle à ce qui a été répondu. À l'affichage :
- le JSON est **retiré du texte**, et le texte explicatif autour est conservé (16 réponses sur 16 nettoyées) ;
- un avertissement indique que ce graphique « avait été écrit par l'IA, sans calcul vérifié » ;
- un bouton **« Régénérer avec le nouveau moteur »** renvoie la question d'origine, qui passe alors par pandas.

**Pourquoi ne pas redessiner automatiquement les anciens JSON ?** Leurs valeurs étaient inventées : les afficher avec le nouveau moteur leur donnerait une fausse crédibilité. Les régénérer depuis la question d'origine produit, lui, des valeurs exactes.

Le prompt du RAG interdit maintenant de produire un graphique ou du JSON : toutes les demandes de graphique passent par le moteur.

## 37. Tout à la demande, rien d'automatique à l'upload

**Choix.** Aucun graphique n'est produit à l'upload : uniquement quand l'utilisateur le demande dans le chat.

**Pourquoi.**
1. **Pertinence** : on ne sait pas, à l'upload, ce que l'utilisateur veut voir. Un graphique automatique choisirait des colonnes au hasard.
2. **Ressources** : sur une machine de 8 Go, générer des graphiques (ou des prédictions) que personne ne regarde consomme du CPU pour rien.
3. **Traçabilité** : chaque graphique est lié à la question qui l'a demandé (table `graphiques`).

La Phase 7 affichera seulement un **aperçu** du fichier et des **questions suggérées** cliquables, qui mènent à des graphiques précis.

## 38. Temps de génération d'un graphique

**Protocole.** `tests/benchmark_graphiques.py` : 15 demandes (les 11 variantes, un type incompatible, l'arabe, deux demandes sans axe précisé), parcours complet `/ask_ia` sans le réseau, sur `sales_data` (1000 lignes), avec un préchauffage du LLM non mesuré. Résultats bruts : `mesures/phase4_graphiques.json`.

**Avant / après** (« graphique du chiffre d'affaires par région ») :
| | Avant (LLM + RAG) | Après (règles + pandas + Plotly) |
|---|---|---|
| Temps | **65 à 75 s** (prompt ~1 500 tokens) | **0,39 s** |
| Données | 2 régions sur 5, valeurs inventées ❌ | 5 régions, sommes exactes ✅ |
| Appels au LLM | 1 (génération du JSON) | **0** |

**Détail par étape (moyenne sur les 14 demandes sans LLM) :**
| Étape | Temps |
|---|---|
| Routage par règles | ~0 s |
| Construction de la spec (règles) | 0,16 à 0,51 s |
| Calcul pandas + figure Plotly | 0,06 à 0,48 s |
| **Total de la réponse dans le chat** | **0,47 s en moyenne** (0,35 à 0,67 s) |
| Taille de la figure envoyée au navigateur | 7,7 à 28,5 Ko |
| Export PNG, 1er (Chrome démarre) | ~4 s (fait en arrière-plan, au démarrage de Flask) |
| Export PNG, suivants | **~0,4 s** (en arrière-plan, n'allonge pas la réponse) |

**Avec le LLM** (« graphique des ventes » : aucun axe précisé) : **~9 s**, dont ~9 s pour la spec du LLM, qui choisit seulement les colonnes. C'est le seul cas où le LLM intervient.

**Optimisations trouvées grâce aux mesures.**
- « Barres groupées / empilées » passaient par le routeur LLM (15 s), car la règle ne reconnaissait que « en barres » : tous les mots de type ont été ajoutés aux règles. Résultat : 0,46 s.
- « Courbe des ventes » appelait le LLM (9 s) pour trouver l'axe X, alors qu'avec une colonne de dates il est évident : règle ajoutée. Résultat : 0,35 s.

---

# Phase 5 — Modèles de Machine Learning selon le domaine

## 39. Registre des modèles par domaine

**Choix.** `services/ml/registry.py` est la **seule** source qui dit quel modèle est proposé à quel domaine :
- **tous les domaines** : prévision du CA et détection d'anomalies ;
- **Banque** : en plus, le churn.

Chaque entrée indique, sous forme de texte `"module:fonction"`, la fonction qui exécute le modèle dans le chat et celle du simulateur. Elles sont importées **au moment de l'appel** : pas d'import circulaire, et un modèle lourd (Prophet) n'est chargé que s'il sert.

**Ajouter un modèle** (ex. une recommandation pour l'e-commerce) = une entrée dans `MODELES`, son nom dans `MODELES_SPECIFIQUES["E-commerce"]`, la fonction elle-même, et la valeur dans l'ENUM `modeles_ml.type` (par une migration). Le routeur, l'assistant, le chat et le simulateur n'ont pas à changer.

**Hors domaine** : un utilisateur E-commerce qui demande le churn reçoit une explication polie (modèle réservé à la Banque, modèles disponibles pour lui, possibilité de changer de domaine). Testé.

> **Jury :** *« Pourquoi pas un `if domaine == 'Banque'` dans le code ? »*
> **Réponse :** Ce test se répéterait dans le routeur, le chat et le simulateur ; à chaque nouveau modèle il faudrait modifier tous ces endroits. Avec le registre, la règle métier est écrite à un seul endroit : c'est le principe « ouvert à l'extension, fermé à la modification ».

## 40. Prévision : Prophet vs LightGBM vs ARIMA

**Choix.** Deux modèles candidats **entraînés à chaque demande**, et le meilleur (MAPE le plus faible sur le test) est retenu automatiquement, avec un tableau comparatif dans la réponse. Une **référence naïve** (« même valeur qu'il y a un an ») est affichée pour juger si un modèle apporte vraiment quelque chose.

| Modèle | Principe | Forces | Faiblesses |
|---|---|---|---|
| **Prophet** (Meta) | Somme d'une tendance, de saisonnalités et de jours fériés | Fonctionne avec peu de réglages ; intervalle de confiance natif ; robuste aux trous | Moins bon si la série est très bruitée ou sans saisonnalité nette |
| **LightGBM** | Arbres de décision boostés sur des features : retards (lag 1-2-3), moyenne mobile, mois, jour de semaine, indice de temps | Capte des relations non linéaires ; très rapide | Ne sait pas extrapoler une tendance seul ; demande des features ; intervalle de confiance approximatif (±1,96 × écart-type des erreurs du test) |
| ARIMA / SARIMA (écarté) | Modèle statistique autorégressif | Référence académique, interprétable | Demande une série stationnaire et le choix des ordres (p, d, q)(P, D, Q) : sur 24 mois, ces réglages sont instables. Prophet fournit la même famille de résultats sans réglage manuel. statsmodels est installé et pourrait servir de 3ᵉ candidat. |

**Résultats mesurés (les deux cas montrent l'intérêt de la sélection automatique) :**
| Fichier | Prophet | LightGBM | Référence naïve | Retenu |
|---|---|---|---|---|
| `ventes_demo_dataia.xlsx` (24 mois, ventes irrégulières) | MAPE 17,9 % | **9,7 %** | 22,5 % | LightGBM |
| `demo_ventes_synthetique.csv` (36 mois, saisonnalité nette) | **11,6 %** | 26,1 % | 13,7 % | Prophet |
| `sales_data_1000_rows.xlsx` (23 mois, données aléatoires) | 21,1 % | **13,2 %** | 22,7 % | LightGBM |

**Prophet sous Windows** : installé sans problème (prophet 1.5.0, cmdstan inclus), compatible avec pandas 3.0. Le premier entraînement prend ~4 s (démarrage de cmdstan), puis moins d'une seconde.

> **Jury :** *« Pourquoi entraîner deux modèles au lieu d'un ? »*
> **Réponse :** Aucun modèle n'est le meilleur partout : sur mes trois fichiers, Prophet gagne une fois et LightGBM deux fois. On les compare sur les mêmes périodes de test et on garde le meilleur. C'est rapide (moins de 5 s), et le tableau comparatif montre le choix à l'utilisateur.

## 41. Split temporel

**Choix.** Les **dernières périodes** servent de test (20 % de la série, entre 3 et 12 périodes) ; le modèle est entraîné sur les périodes précédentes. **Jamais de mélange aléatoire.**

**Pourquoi.** Avec un split aléatoire, le modèle verrait par exemple mars et mai pour « prédire » avril : il utiliserait le futur pour prédire le passé, et le score serait trop optimiste. En réalité, on prédit toujours après la dernière date connue. Le test reproduit cette situation.

**Prévision récursive pour LightGBM** : sur le test comme sur le futur, chaque valeur prévue sert de « retard » pour la suivante. On n'utilise jamais les vraies valeurs du test pour prédire le test.

Après l'évaluation, le modèle retenu est **réentraîné sur toute la série** pour prévoir le futur (les dernières périodes sont les plus informatives).

> **Jury :** *« Pourquoi pas une validation croisée classique (k-fold) ? »*
> **Réponse :** Le k-fold mélange les périodes, ce qui fait apprendre le futur au modèle. Pour une série temporelle, on utilise un split chronologique (ou un « walk-forward »). Avec 24 mois, un seul découpage (19 / 5) reste lisible pour l'utilisateur.

## 42. MAPE, MAE, RMSE : exemple chiffré

Prenons deux mois réels **100 000** et **200 000**, prévus **110 000** et **180 000**.

| Métrique | Calcul | Résultat | Lecture |
|---|---|---|---|
| **MAE** (erreur absolue moyenne) | (10 000 + 20 000) / 2 | **15 000** | « en moyenne, on se trompe de 15 000 dinars » |
| **RMSE** (racine de l'erreur quadratique moyenne) | √((10 000² + 20 000²) / 2) | **15 811** | pénalise davantage les grosses erreurs (RMSE ≥ MAE) |
| **MAPE** (erreur absolue moyenne en %) | (10 % + 10 %) / 2 | **10 %** | indépendante de l'échelle : « on se trompe de 10 % » → précision affichée 90 % |
| sMAPE (MAPE symétrique) | moyenne de \|erreur\| / ((\|réel\| + \|prévu\|) / 2) | 10,0 % | utilisée quand des valeurs réelles sont proches de 0 (la MAPE exploserait : division par ~0) |

Ce calcul est vérifié par un test automatique (`tests/test_ml.py`, `test_metriques`).

**Pourquoi choisir le modèle sur la MAPE ?** Elle est compréhensible par un non-spécialiste (« 9,7 % d'erreur ») et comparable d'un fichier à l'autre. La MAE et la RMSE sont affichées aussi : elles donnent l'erreur dans l'unité de la donnée.

> **Jury :** *« Que veut dire “Précision : 90,3 %” ? »*
> **Réponse :** 100 % moins la MAPE mesurée sur les 5 derniers mois, que le modèle n'avait pas vus : en moyenne, la prévision mensuelle s'écarte de 9,7 % du chiffre d'affaires réel.

## 43. Préparer une série pour la prévision

Trois problèmes réels ont été trouvés en testant sur `ventes_demo_dataia.xlsx`, et chacun a été corrigé :

1. **Valeurs aberrantes.** Une seule vente de 106 549 (anomalie volontaire) faisait passer avril 2025 de 166 916 à 273 465. Les valeurs **négatives** et **supérieures à Q3 + 5 × IQR** (seuil volontairement prudent : la règle classique des valeurs extrêmes est 1,5 × IQR) sont **exclues de l'apprentissage**, listées dans le rapport de nettoyage, et restent visibles avec la détection d'anomalies. Sur ce fichier, exactement 5 lignes sont exclues (les 3 énormes et les 2 négatives) ; la plus grande vente normale est 9 898 ; sur `sales_data`, aucune ligne n'est exclue. **Effet : MAPE de LightGBM 24,5 % → 9,7 %.** Réglable par `PREVISION_EXCLURE_ABERRANTS` dans `.env`.
2. **Périodes incomplètes.** La dernière semaine (29/12 → 04/01) ne contenait que 3 jours de ventes : sa somme, artificiellement basse, faussait le test. Les périodes incomplètes aux deux extrémités sont retirées (et signalées).
3. **Fréquence d'agrégation.** La fréquence choisie automatiquement est la **plus grossière qui donne au moins 12 périodes** (mois, sinon semaine, sinon jour), et **jamais plus fine que la granularité réelle** des données. Un CA mensuel est moins bruité : sur `sales_data`, MAPE 13 % par mois contre 64 % par semaine. Sans cette limite, 5 dates mensuelles auraient donné 17 « semaines » presque toutes à 0 (trouvé par le test « historique insuffisant »). L'utilisateur peut imposer la fréquence (« prévision hebdomadaire »).

**Historique insuffisant** : en dessous de 12 périodes après agrégation, le système l'explique au lieu de produire une prévision sans valeur.

## 44. Isolation Forest vs K-Means, DBSCAN, Z-score

**Principe d'Isolation Forest.** On construit 300 arbres qui coupent les données **au hasard**. Une ligne anormale est **isolée en peu de coupes**, car elle est loin des autres ; une ligne normale en demande beaucoup. Le score d'anomalie mesure cette facilité d'isolement.

| Méthode | Pourquoi écartée |
|---|---|
| **Z-score** (\|x − moyenne\| / écart-type > 3) | Une seule colonne à la fois ; la moyenne et l'écart-type sont eux-mêmes faussés par les anomalies (un prix de 99 999 gonfle l'écart-type) ; suppose une distribution normale, alors que les montants sont très asymétriques |
| **K-Means** | Fait des groupes, pas de la détection : il faut choisir k, et une anomalie finit dans un groupe comme les autres |
| **DBSCAN** | Repère les points isolés, mais demande deux réglages sensibles (eps, min_samples), coûte plus cher en calcul, et marche mal quand la densité varie |
| **Isolation Forest** ✅ | Plusieurs colonnes à la fois, aucune hypothèse de distribution, peu de réglages, rapide (~1 s sur 1 800 lignes), score continu pour classer les lignes |

**Réglages trouvés par l'expérience** (`ventes_demo_dataia.xlsx`, 8 anomalies volontaires ; détail dans le CHANGELOG) :
| Configuration | Rangs des 8 anomalies parmi 1 793 lignes |
|---|---|
| Toutes les colonnes numériques | 1, 2, 4, 26, 51, 52, 290, 360 |
| Toutes + logarithme | 2, 3, 7, 29, 46, 80, 137, 237 |
| **Quantité, prix, montant + écart de cohérence** ✅ | **1, 2, 3, 4, 5, 6, 7, 19** |

1. **Colonnes transactionnelles uniquement** : l'âge du client ou la satisfaction « diluent » la recherche, puisque chaque coupe porte sur une colonne tirée au hasard.
2. **Écart de cohérence** = (montant − quantité × prix × (1 − remise)) / |quantité × prix|, borné à [−5 ; 5]. Il fait ressortir un CA négatif, un prix de 0,01 ou un montant qui ne correspond pas à quantité × prix. Il est calculé automatiquement quand les trois colonnes sont reconnues.
3. **Seuil automatique** : score > Q3 + 3 × IQR des scores. Il n'y a pas de « pourcentage d'anomalies » à deviner (avec `contamination="auto"`, 573 lignes étaient signalées).
4. **Explication de chaque anomalie** : colonnes les plus éloignées de la médiane (écart absolu médian, robuste) et incohérence éventuelle, par exemple « chiffre_affaires = −350,00 au lieu de 1 608,30 (quantite × prix_unitaire) ».

**Résultat** : sur `ventes_demo_dataia.xlsx`, **7 anomalies sur 8 détectées, 0 faux positif**. La 8ᵉ (quantité 120 à 46,37 €, montant cohérent) est 19ᵉ et figure en tête de la liste **« à surveiller »**. Sur `demo_transactions_anomalies_synthetique.csv`, 6 sur 10 sont détectées (1 faux positif) et les 4 autres sont dans « à surveiller ». Sur `sales_data` (aléatoire), 1 ligne sur 1 000 est signalée.

**Limite (à dire honnêtement) — l'effet de masquage.** Quand plusieurs anomalies se ressemblent (4 quantités énormes : 60, 75, 90, 120), elles forment un petit groupe et s'isolent moins vite. C'est pour cela que la liste « à surveiller » est affichée. Une piste d'amélioration : un contrôle univarié robuste par colonne, en complément.

> **Jury :** *« Une anomalie, c'est forcément une erreur ? »*
> **Réponse :** Non : c'est une ligne **inhabituelle**. Elle peut être une erreur de saisie (prix de 0,01) ou une vraie vente exceptionnelle. Le modèle signale, explique pourquoi, et l'humain décide. C'est aussi pour cela que la prévision exclut ces lignes de l'apprentissage sans les supprimer du fichier.

## 45. Arbre de décision pour le churn (et ses limites)

**Réentraînement** (`entrainer_churn.py`, à partir de `train_churn.py`).

1. **Pipeline scikit-learn** : `ColumnTransformer` (OneHotEncoder sur `country` et `gender`, autres colonnes telles quelles), puis `DecisionTreeClassifier`.
   - *Avant* : `pd.get_dummies` **hors** du modèle. Au moment de prédire, il fallait refaire exactement le même encodage à la main ; or un fichier contenant seulement des clients français ne produit pas la colonne `country_Germany`, ce qui donne une erreur ou un décalage silencieux des colonnes.
   - *Maintenant* : l'encodage fait partie du modèle sauvegardé, il est appliqué à l'identique.
   - `handle_unknown="ignore"` : un pays inconnu (« Italy ») ne fait pas planter le modèle ; c'est signalé dans la réponse.
2. **Pas de normalisation** : un arbre compare des seuils (« âge > 42,5 ? »), l'échelle des colonnes ne change rien.
3. **`customer_id` retiré** : un identifiant n'a pas de valeur prédictive, et un arbre pourrait apprendre des numéros par cœur.

**Choix de `max_depth`** par validation croisée stratifiée (5 plis), **sur le jeu d'entraînement seulement** :
| max_depth | F1 entraînement | F1 validation | Lecture |
|---|---|---|---|
| 2 | 0,51 | 0,51 | trop simple (sous-apprentissage) |
| 4 (modèle d'origine) | 0,51 | 0,50 | |
| **5, poids équilibrés** ✅ | **0,58** | **0,56** | meilleur compromis |
| 8 | 0,65 | 0,55 | l'écart se creuse |
| illimité | **1,00** | 0,50 | **sur-apprentissage** : l'arbre apprend le jeu d'entraînement par cœur |

**`class_weight="balanced"`** : seuls 20,4 % des clients partent. Sans pondération, l'arbre favorise la classe majoritaire. Les poids équilibrés donnent autant d'importance aux départs, ce qui améliore le F1 en validation (0,562 contre 0,553).

**Résultats sur le jeu de test** (2 000 clients jamais vus) :
| Métrique | Valeur | Lecture |
|---|---|---|
| **Rappel** | **76,7 %** | 312 des 407 clients partis ont été détectés |
| Précision | 46,2 % | Sur 676 alertes, 312 sont de vrais départs |
| F1 | 0,576 | Moyenne harmonique précision / rappel |
| ROC-AUC | 0,840 | Bonne capacité à classer les clients du plus au moins risqué |
| Accuracy | 77,1 % | **Inférieure au modèle naïf « tout le monde reste » (79,65 %)** |
| Matrice de confusion | VN 1 229, FP 364, FN 95, VP 312 | |

**Pourquoi l'accuracy est trompeuse ici.** Le modèle naïf qui dit « tout le monde reste » obtient 79,65 % d'accuracy… et ne détecte **aucun** départ. Pour une banque, rater un client qui part (faux négatif) coûte plus cher qu'appeler un client qui serait resté (faux positif). On privilégie donc le **rappel** et le **F1**.

**Variables les plus importantes** : âge (46,9 %), nombre de produits (34,6 %), membre actif (7,2 %), solde (6,6 %), pays (3,8 %).

**Limites de l'arbre de décision (à dire au jury).**
- Instable : de petites variations des données peuvent changer l'arbre. Une forêt aléatoire ou un gradient boosting seraient plus robustes et un peu plus précis (AUC souvent ~0,86), mais moins lisibles.
- Probabilités grossières : un arbre de profondeur 5 n'a que 32 feuilles, donc 32 probabilités possibles au maximum.
- Avec des poids équilibrés, les probabilités sont **décalées vers le haut** : sur l'échantillon de démo, 32 % de clients « à risque » pour un taux réel de 20 %. Il faut les lire comme un **classement** des clients à contacter en priorité, pas comme des probabilités calibrées.
- Modèle entraîné sur un seul jeu public (10 000 clients européens) : à réentraîner sur les données de la banque cible avant tout usage réel.

**Sauvegarde.**
- `a_integrer/modele_banque/modele_churn_pipeline.joblib` : le pipeline complet.
- `modele_churn_pipeline_metadonnees.json` : features, catégories, bornes, version de scikit-learn (1.8.0), paramètres, tableau de validation croisée, métriques, importances, date, empreinte SHA-256 des données.
- Données nettoyées (CSV + Excel) et rapport de nettoyage.
- Le modèle est chargé **une seule fois** (au premier usage, puis gardé en mémoire), sans réentraînement.

> **Jury :** *« Pourquoi un arbre de décision et pas un réseau de neurones ? »*
> **Réponse :** Sur 10 000 lignes tabulaires, les réseaux de neurones ne font pas mieux que les arbres, et l'arbre est **explicable** : on peut montrer à un conseiller pourquoi un client est à risque (âge, nombre de produits). C'était aussi le modèle fourni ; je l'ai amélioré (Pipeline, profondeur choisie par validation croisée) sans changer de famille.

## 46. Nettoyage des données et exports téléchargeables

**Choix.** Chaque modèle passe par `services/ml/nettoyage.py`, qui **enregistre chaque opération** :
- lignes avant / après ;
- doublons supprimés ;
- valeurs manquantes et méthode de traitement (**médiane** pour les nombres, plus robuste que la moyenne face aux valeurs extrêmes ; **valeur la plus fréquente** pour les catégories ; **suppression** si la cible ou la date manque, car on n'invente pas une cible) ;
- conversions de types ;
- encodages ;
- agrégation ;
- exclusions.

**Exports** (à chaque exécution) dans `exports/donnees_nettoyees/U<utilisateur>/<modele>_<date>` :
- `.csv` (UTF-8 avec BOM, pour que les accents s'affichent correctement dans Excel) ;
- `.xlsx` (feuille `donnees` + feuille `rapport_nettoyage`) ;
- `_rapport.txt`.

Le chemin est enregistré dans `modeles_ml.chemin_donnees_nettoyees`. Dans le chat, chaque résultat de modèle propose les liens **CSV · Excel · rapport de nettoyage**, et la page **« Mes données nettoyées »** liste toutes les exécutions.

**Sécurité du téléchargement** (`/telecharger/nettoyees/<id>/<format>`) : l'exécution doit appartenir à l'utilisateur (l'admin voit tout), le format est pris dans une liste fermée, et le fichier doit se trouver dans le dossier des exports. Testé : un autre utilisateur reçoit 403, et `../../.env` donne 404.

**Choix propres à chaque modèle (justifiés dans le rapport de nettoyage lui-même).**
- *Anomalies* : **aucune ligne supprimée** (une transaction incomplète ou en double peut elle-même être l'anomalie) ; manquants remplacés par la médiane.
- *Churn (prédiction)* : manquants remplacés par la **médiane de l'entraînement**, pas celle du fichier (le modèle doit voir les mêmes repères qu'à l'apprentissage).
- *Prévision* : exclusion documentée des valeurs aberrantes (§43).

> **Jury :** *« Comment savez-vous ce que le modèle a vraiment reçu ? »*
> **Réponse :** Pour chaque exécution, le jeu de données exact passé au modèle est téléchargeable en CSV et Excel, avec le rapport de nettoyage (lignes avant / après, méthode utilisée pour chaque valeur manquante, conversions, exclusions). Tout est reproductible et vérifiable.

## 47. Packages ML installés

`prophet 1.5.0`, `lightgbm 4.7.0`, `statsmodels 0.15.0`, `xlsxwriter 3.3.4` (et leurs dépendances : cmdstanpy, holidays, matplotlib, patsy…). Les dépendances ont été vérifiées par `pip install --dry-run` avant l'installation : ce sont uniquement de **nouveaux** packages, et aucun package existant n'a été mis à jour.

`xlsxwriter` écrit les fichiers Excel à plusieurs feuilles (données + rapport) ; openpyxl, déjà présent, continue de servir à la lecture.

---

# Phase 6 — Nouveau frontend et simulateur what-if

## 48. Architecture : SPA React + API REST JSON

**Choix (option 1, validée).** Le frontend fourni (React 18 + Vite + TypeScript + Tailwind) est une **SPA** (*Single Page Application*) :
- le navigateur charge une seule page HTML ;
- React affiche les écrans ;
- toutes les données passent par une **API JSON** (`api.py`, routes `/api/*`).

Flask sert le build compilé sous **`/app/`** (`frontend/dist`) ; `/` redirige vers `/app/` (réglable avec `UI_PRINCIPALE` dans `.env`). Les pages **Jinja** restent accessibles en secours (`/login`, `/dashboard`, `/chat/<id>`, `/accueil`…), et tous leurs tests de non-régression passent.

**Pourquoi.**
- **Séparation** : l'interface et le serveur évoluent indépendamment. La même API pourrait servir une application mobile.
- **Réutilisation** : le frontend fourni attendait déjà ces routes ; il a été adapté (fond blanc, simulateur, domaine, profil, données nettoyées, graphiques Plotly), pas réécrit.
- **Pas de serveur Node en production** : `npm run build` produit des fichiers statiques servis par Flask ; une seule commande lance tout. `demarrer.bat` compile au premier lancement.

**Alternative écartée — tout réécrire en Jinja (option 2).** Plus simple à déployer, mais cela jetait le travail fourni, et chaque interaction (chat, simulateur) aurait demandé du JavaScript écrit à la main dans les templates.

**Routes ajoutées.** `/api/me`, `login`, `signup`, `logout` (POST), `domaines`, `profil` (GET/PUT), `dashboard`, `files`, `upload`, `files/<id>` (DELETE), `files/<id>/apercu`, `chat/<id>/history`, `simulateur/modeles`, `simulateur/<modele>`, `simulations`, `donnees_nettoyees`, `admin/data`, `admin/users/<id>/toggle`, `admin/users/<id>/domaine`, `admin/users/<id>` (DELETE). `/ask_ia` est commune aux deux interfaces.

> **Jury :** *« C'est quoi une API REST ? »*
> **Réponse :** Une interface où chaque ressource a une adresse (`/api/files/12`) et où le verbe HTTP dit l'action : GET pour lire, POST pour créer, PUT pour modifier, DELETE pour supprimer. Les réponses sont en JSON, que React affiche.

## 49. Sécurité de l'API

| Risque | Protection |
|---|---|
| Session volée par du JavaScript (XSS) | Cookie de session **HttpOnly** : le JavaScript ne peut pas le lire |
| **CSRF** : un autre site fait agir le navigateur de l'utilisateur connecté | 1) Cookie **SameSite=Lax** : il n'est pas envoyé par les requêtes POST venant d'autres sites. 2) Les requêtes qui modifient des données doivent être en **JSON** (un formulaire HTML d'un autre site ne peut pas en envoyer ; testé : 415). 3) **Déconnexion en POST** : une simple image `<img src="/logout">` sur un autre site ne déconnecte plus. |
| Accès aux données d'un autre (IDOR) | Chaque fichier ou exécution est filtré par `id_utilisateur` (testé : 404 pour un autre compte) |
| Écrans protégés sans session | 401 en **JSON** (`unauthorized_handler`) : React affiche « session expirée » au lieu de recevoir une page HTML de connexion |
| Fichiers du build (`/app/...`) | Le chemin doit rester dans `frontend/dist` (testé : `../../.env` donne 404) |
| Admin | `admin_required` ; l'admin ne peut ni se bloquer ni se supprimer lui-même |

Le décorateur `admin_required` et la classe `User` sont dans `services/auth.py`, partagés par les deux interfaces (plus de copie du contrôle).

## 50. Fond blanc : inversion de la palette

**Constat.** Le frontend fourni était entièrement sombre : environ 300 classes Tailwind de la palette `slate` (`bg-slate-950`, `text-slate-100`…).

**Choix.** Dans `tailwind.config.js`, l'échelle `slate` est **inversée** : `slate-950` donne blanc et `slate-50` donne presque noir. Toutes les classes du design gardent leur **contraste relatif** sur fond clair, sans réécrire chaque composant. Les quelques `text-white` posés sur un fond neutre ont été remplacés (16 lignes) ; ceux posés sur un dégradé coloré (boutons, avatars) restent blancs. La bascule « mode sombre » a été retirée, et les pages Jinja ont aussi été passées en fond blanc.

**Alternative.** Réécrire chaque classe à la main : plus « propre », mais environ 300 modifications et un fort risque d'oubli. Le choix fait tient en un seul fichier, et il est réversible.

**Vérification visuelle.** Captures d'écran prises dans Chrome (headless) après connexion : chat, tableau de bord, simulateur, profil, données nettoyées, à 1 440 px et à 760 px de large (mobile).

## 51. Simulateur what-if

**Choix.** Un **panneau à droite du chat** (et une page dédiée) qui n'affiche **que les modèles du domaine** de l'utilisateur : la liste vient de `services/ml/registry.py`, comme dans le chat.

| Modèle | Formulaire (généré par le serveur) | Résultat |
|---|---|---|
| Prévision CA | Colonne à prévoir (liste des colonnes numériques du fichier), horizon (curseur 1 à 12) | Valeur prévue pour la prochaine période, modèle retenu, précision (MAPE), mini-graphique |
| Anomalies | Un champ par colonne utilisée par le modèle (prérempli avec la médiane) | « Normale » / « Anormale », score, seuil, position parmi les transactions du fichier, raison |
| Churn (Banque) | **Généré depuis les features du modèle** (`meta["features_entree"]`) : listes déroulantes pour `country` / `gender` (catégories apprises), Oui/Non pour les colonnes 0/1, nombres pour le reste (bornes et médianes de l'entraînement) | « Reste » / « Risque de départ » et probabilité en % |

**Pourquoi générer les formulaires côté serveur ?** Si le modèle est réentraîné avec d'autres variables, le formulaire suit **automatiquement** ; aucune liste de champs n'est écrite en dur dans React. Le frontend fourni avait un formulaire churn codé à la main, qui aurait été faux dès le premier changement.

**Performance.** Le modèle d'anomalies entraîné sur un fichier est gardé en mémoire (cache de 8 fichiers, invalidé si le fichier change). Une simulation prend quelques millisecondes au lieu de réentraîner à chaque clic.

**Traçabilité.** Chaque simulation est enregistrée dans la table **`simulations`** (entrées et résultat en JSON). Testé : 3 simulations donnent 3 lignes.

**Responsive.** Le panneau est ouvert sur grand écran (≥ 1 280 px) ; sur petit écran il est replié, et un bouton flottant l'ouvre en tiroir.

> **Jury :** *« À quoi sert un simulateur what-if ? »*
> **Réponse :** À répondre à « que se passerait-il si… ? » sans fichier à préparer : « si ce client a 55 ans, 3 produits et n'est pas actif, risque-t-il de partir ? ». Le modèle est le même que celui du chat ; seule l'entrée change (une ligne saisie au lieu d'un fichier).

## 52. Graphiques dans React : Plotly plutôt que Recharts

Le frontend fourni dessinait avec **Recharts** les valeurs du JSON écrit par le LLM (l'ancien format). Désormais, le composant `PlotlyChart` affiche **la figure Plotly construite par le serveur** à partir de pandas (Phase 4) : un seul moteur pour le chat, l'historique, le simulateur et le PDF, donc des graphiques identiques partout. `plotly.js` est chargé depuis Flask (`/vendor/plotly.min.js`), sans package npm supplémentaire et sans Internet. Le bundle JavaScript passe de 950 Ko à 528 Ko.

## 53. Où vit le frontend ?

Le frontend fourni était dans `DataIA_Loal/frontend`, **hors du dépôt Git** : ses modifications n'auraient pas été versionnées. Ses sources ont été copiées dans **`DataIa/frontend/`**, qui est désormais la version de référence (commitée avec la Phase 6). L'original n'a pas été modifié. Les dépendances (`node_modules`) sont partagées par une jonction Windows ; pour une installation neuve : `npm install` puis `npm run build` dans `DataIa/frontend` (ou simplement `demarrer.bat`).

---

# Phase 7 — Support multi-formats

## 54. Parser unifié

**Choix.** `services/parsers.py` transforme **tout fichier** en un `ResultatParsing` : un ou plusieurs tableaux pandas, le texte du document pour le RAG, une description de la source et des remarques. Le reste de la plateforme (routeur, pandas, graphiques, ML) ne sait pas d'où viennent les données : un PDF se traite comme un CSV.

| Format | Outil | Détail |
|---|---|---|
| CSV | pandas + `charset-normalizer` + `csv.Sniffer` | Encodage détecté (UTF-8 essayé d'abord, sinon détection : un CSV Excel français est souvent en latin-1) ; séparateur détecté (`,` `;` tabulation `\|`) |
| Excel | pandas | **Toutes les feuilles** : fusionnées si elles ont les mêmes colonnes (colonne `feuille` ajoutée), sinon conservées séparément |
| PDF | `pdfplumber` | Tableaux de toutes les pages (un tableau coupé sur deux pages est recollé) et texte |
| Image | RapidOCR | Texte, puis tableau reconstruit à partir des positions des mots (point 55) |

Commun à tous les formats : les nombres écrits en texte sont convertis (« 18 521 », « 1 234,56 »), et les en-têtes sont nettoyés. Le résultat est **mis en cache** (fichier + date de modification) : un PDF ou une image n'est analysé qu'une fois.

**Installation prudente.** La dernière version de `pdfplumber` (0.11.11) imposait de passer **Pillow 12.1 → 13.0**, un package déjà utilisé par matplotlib et kaleido. La version 0.11.9, compatible avec Pillow 12.1, a été choisie (vérifié par `pip install --dry-run`) : aucun package existant n'a été modifié. C'est la même prudence qu'avec `langchain-ollama`.

> **Jury :** *« Pourquoi pdfplumber et pas PyPDF2 ? »*
> **Réponse :** PyPDF2 n'extrait que du texte brut ; pdfplumber reconnaît les **tableaux** (lignes et colonnes) à partir de la mise en page, ce qui permet à pandas de calculer dessus.

## 55. OCR : RapidOCR ou Tesseract

Deux options compatibles avec 8 Go de RAM :

| | **RapidOCR** (`rapidocr-onnxruntime`) ✅ | **Tesseract** (`pytesseract`) |
|---|---|---|
| Installation | `pip` seulement : les modèles ONNX (~15 Mo) sont inclus | Programme Windows à installer à part, plus les langues (`fra`, `ara`), plus le PATH |
| Moteur | Réseaux de neurones (détection + reconnaissance PaddleOCR, convertis en ONNX), CPU | Moteur LSTM classique |
| Précision sur le tableau de test | **31 zones, confiance moyenne 99 %, 8 lignes sur 8 exactes** | Bonne sur du texte propre ; plus sensible aux tableaux et aux polices |
| Position des mots | Oui (boîtes) : permet de reconstruire le tableau | Oui (`image_to_data`) |
| Arabe | **Limité** (modèles chinois / latin par défaut) | **Bon** avec le pack `ara` |
| Temps (image 1 300 × 760) | ~4 s la première fois (chargement du modèle), puis mis en cache | ~1 à 2 s |

**Choix : RapidOCR**, parce qu'il ne demande aucune installation système (un seul `pip install`, reproductible sur la machine du jury) et qu'il a été parfait sur le tableau de test.

**Alternative documentée pour l'arabe** : Tesseract avec la langue `ara`. Il suffirait d'ajouter une branche dans `lire_image` si l'utilisateur doit numériser des documents en arabe.

**Reconstruction du tableau.** L'OCR rend des mots avec leur position. On regroupe les mots d'une même **ligne** (même hauteur), on **fusionne** les morceaux très proches (l'OCR coupe « 157 737 » en « 157 » et « 737 » : écart de −3 à +2 px, alors que deux colonnes sont séparées de plus de 280 px), puis on aligne chaque cellule sur les **colonnes de l'en-tête**. Une remarque rappelle à l'utilisateur de vérifier les valeurs importantes, car une erreur de lecture reste possible.

> **Jury :** *« Pourquoi pas un LLM multimodal pour lire l'image ? »*
> **Réponse :** Un modèle vision local (LLaVA, Qwen-VL) demande plusieurs Go de RAM en plus et peut « inventer » des chiffres. L'OCR lit exactement ce qui est écrit, avec un score de confiance, et pandas calcule ensuite.

## 56. Pièges des tableaux de documents

Trois problèmes rencontrés sur `rapport_ventes_2025.pdf`, et leurs corrections :

1. **La ligne « Total ».** Le tableau mensuel se termine par `Total | 602 532 | …`. La garder **doublerait toutes les sommes** : le CA de Tunis deviendrait 1 205 064. Les lignes dont la première cellule est « Total », « Somme », « المجموع »… sont retirées, et c'est signalé dans l'aperçu.
2. **Plusieurs tableaux** (CA par mois et par région ; synthèse par catégorie). `table_pour_question` choisit, pour **chaque question**, le tableau dont les colonnes ou les valeurs sont citées : « catégorie la plus forte » donne le tableau des catégories, « CA de Tunis » le tableau mensuel. Le RAG indexe **tous** les tableaux et le texte.
3. **Le texte libre.** Le texte du PDF est découpé en **phrases**, en écartant les lignes de tableau déjà indexées. Avant cela, la phrase sur les mois de fin d'année n'était pas retrouvée par la recherche.

**Règles ajoutées au routeur (découvertes avec ces fichiers).**
- **Superlatifs** (« la catégorie la plus forte », « le produit le plus vendu », « which category has the highest… », « أعلى ») : opération `top` avec n = 1, groupée par la colonne citée, **sans appel au LLM** (0,03 s). Avant, « catégorie la plus forte » partait au RAG, qui répondait **Électroménager** (faux).
- **Mesure par défaut**, signalée dans la réponse, quand aucune n'est nommée : colonne de CA, sinon colonne « Total », sinon l'unique colonne numérique. Une colonne qui **compte** des ventes (« Nombre de ventes ») n'est pas un chiffre d'affaires : elle est exclue du concept « ventes ».
- **Questions de lecture** (« que dit », « résume », « explique », « what does », « لخص ») : envoyées au RAG.
- **Noms propres arabes** (تونس → Tunis, صفاقس → Sfax…) : ajoutés à la question pour retrouver les colonnes et les valeurs écrites en lettres latines.

## 57. Réponses attendues sur le PDF et l'image

| Question | Réponse attendue (utilisatrice) | Réponse de DataIA | Comment |
|---|---|---|---|
| CA total de Tunis | 602 532 | **602 532** ✅ | Somme de la colonne `Tunis` (ligne Total exclue) |
| Mois le plus fort | Juillet (197 381) | **Mai (237 858)** ⚠️ | Voir ci-dessous |
| Catégorie la plus forte | Informatique (1 037 167) | **Informatique (1 037 167)** ✅ | top 1 sur `Chiffre d'affaires (TND)` |
| Produit le plus vendu en CA | Ordinateur portable (594 715) | **Ordinateur portable (594 715)** ✅ | Image → OCR → top 1 |
| Quantité de télévisions | 441 | **441** ✅ | Image → filtre `Produit == Télévision` |
| ما هو رقم المعاملات الإجمالي لتونس؟ | — | **602,532** ✅ | تونس → Tunis |
| Que dit le rapport sur la fin d'année ? | — | « novembre et décembre sont les plus forts » ✅ | RAG (texte) |

**À propos du mois le plus fort.** Dans le tableau du PDF, la colonne Total vaut **237 858 en mai**, 216 636 en septembre et 197 381 en juillet. Juillet est le mois le plus fort **pour Tunis** (77 784), et sa ligne totalise 197 381 : la réponse attendue vient probablement de cette confusion. Le **texte** du même PDF affirme par ailleurs que « novembre et décembre sont les plus forts », ce qui contredit son propre tableau (187 231 et 187 990). DataIA restitue fidèlement les deux selon la question : le **calcul** sur le tableau (mai) et la **lecture** du texte (novembre / décembre). Il ne force pas une valeur attendue qui ne correspond pas aux données. Tout cela est vérifié par `tests/test_parsers.py`.

## 58. Aperçu et questions suggérées (rien d'automatique)

**Après l'upload**, l'utilisateur voit seulement :
- un **aperçu** : nombre de lignes et de colonnes, colonnes et types détectés (nombre / date / texte), 5 premières lignes, source (« PDF : 2 tableaux, 1 page »), remarques (ligne Total retirée, confiance de l'OCR…) ;
- **3 à 4 questions suggérées cliquables**, adaptées au fichier **et au domaine**. La prévision n'est suggérée que s'il y a une date et une mesure ; « Quels clients risquent de partir ? » seulement pour le domaine Banque **et** si les colonnes du modèle sont présentes ; les anomalies s'il y a au moins deux colonnes numériques.

**Aucun graphique ni aucune prédiction n'est calculé à l'upload** (§37) : l'utilisateur clique sur une suggestion ou pose sa question.

Dans React, l'upload ouvre directement le chat du fichier avec cet aperçu. L'API `/api/upload` renvoie l'aperçu, et `/api/files/<id>/apercu` le recalcule (il est mis en cache).

> **Jury :** *« Pourquoi ne pas afficher un tableau de bord automatique à l'upload ? »*
> **Réponse :** Parce qu'on ne sait pas encore ce qui intéresse l'utilisateur ; on lui montre ce que contient le fichier et des questions pertinentes, et chaque calcul reste à sa demande. Cela évite aussi des calculs inutiles sur une machine de 8 Go.

# DataIA — Guide de démarrage

Ce guide sert à installer, lancer et tester DataIA sur un PC Windows. Il ne faut aucune connexion Internet une fois l'installation faite.

## 1. Prérequis

| Logiciel | Version testée | Rôle |
|---|---|---|
| Windows 10 | 19045 | — |
| Python | 3.11.9 (venv `..\venv`) | serveur Flask, pandas, ML |
| WampServer | MySQL 9.1.0 | base de données `dataia` |
| Ollama | 0.34 | LLM local |
| Google Chrome | installé | export PNG des graphiques (kaleido) |
| Node.js + npm | (seulement pour recompiler le frontend) | build React |

Modèles Ollama, à télécharger une seule fois :
```
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Dossiers attendus :
```
DataIA_Loal/
├── venv/                     environnement Python
├── a_integrer/modele_banque/ modèle churn (.joblib + métadonnées) et données d'entraînement
└── DataIa/                   le projet (ce dossier)
```

## 2. Première installation

1. **Dépendances Python** (venv activé) :
   ```
   ..\venv\Scripts\activate
   pip install -r requirements.txt
   ```
   `requirements-lock.txt` contient l'environnement exact testé (`pip freeze`).
2. **Configuration** : copier `.env.example` en `.env`, puis remplir au minimum :
   - `SECRET_KEY`, avec une valeur aléatoire : `python -c "import secrets; print(secrets.token_hex(32))"` ;
   - `DB_PASSWORD` si MySQL a un mot de passe ;
   - `CHROME_PATH` si Chrome n'est pas à l'emplacement standard ;
   - `MYSQLDUMP_PATH`.
3. **Base de données** (WampServer lancé, icône verte) :
   - base existante : `python migrate.py` applique les migrations en attente, avec une sauvegarde automatique dans `backups/` ;
   - installation neuve : `mysql -uroot < database.sql`, puis `python migrate.py`.
   - `python migrate.py --statut` affiche les migrations appliquées ou en attente.
4. **Modèle churn** : il est déjà entraîné dans `a_integrer/modele_banque/`. Pour le réentraîner : `python entrainer_churn.py`.
5. **Frontend** : `frontend/dist` est déjà compilé. Pour le recompiler après une modification : `cd frontend && npm install && npm run build`.

## 3. Lancer l'application

**Double-cliquer sur `demarrer.bat`.** Le script :
1. vérifie le venv, `.env`, MySQL et Ollama (et lance `ollama serve` si besoin) ;
2. signale les migrations en attente ;
3. compile le frontend s'il ne l'est pas ;
4. lance Flask et ouvre le navigateur sur **http://127.0.0.1:5000** (qui redirige vers `/app/`).

Lancement manuel : `..\venv\Scripts\python.exe app.py`.

Pour arrêter : fermer la fenêtre « DataIA » (ou Ctrl+C).

> Utiliser **127.0.0.1** plutôt que `localhost` : sous Windows, `localhost` essaie d'abord IPv6 et perd environ 2 s par connexion.

Le premier démarrage prend environ 10 à 20 s : chargement du modèle dans Ollama et démarrage de Chrome pour les PNG.

## 4. Premier test (5 minutes)

1. **Créer un compte** du domaine **Banque** (le domaine choisit les modèles ML disponibles).
2. **Déposer** `uploads/ventes_demo_dataia.xlsx`. L'aperçu affiche les colonnes et 4 questions suggérées.
3. Poser des questions :
   - « Quel est le chiffre d'affaires total à Tunis ? » (calcul pandas) ;
   - « Montre les ventes par région en camembert » (graphique) ;
   - « Prévois le chiffre d'affaires des 6 prochains mois » (Prophet / LightGBM) ;
   - « Détecte les anomalies » (Isolation Forest) ;
   - « ما هو مجموع رقم المعاملات في تونس؟ » (arabe, même chiffre).
4. Ouvrir le **simulateur** (panneau à droite du chat) et changer une valeur.
5. Déposer `donnees_demo/demo_clients_banque_synthetique.csv` et demander « Quels clients risquent de partir ? » (churn).
6. Cliquer sur **Exporter PDF** pour obtenir le rapport complet.
7. Menu **Données nettoyées** : télécharger CSV, Excel et le rapport de nettoyage.
8. **Se déconnecter**, puis essayer de revenir en arrière : l'accès est refusé.

Comptes de démonstration créés par le test de bout en bout (mot de passe `Demo2026!`) :
- `e2e.banque@dataia.local` (Banque) ;
- `e2e.ecommerce@dataia.local` (E-commerce).

## 5. Lancer les tests

```
cd DataIa
..\venv\Scripts\python.exe -W ignore tests\tout_lancer.py
```
Ce script lance toutes les suites, Phases 1 à 8 (environ 15 à 25 min, à cause des appels au LLM sur CPU). Chaque suite crée ses comptes temporaires puis les supprime.

Test de bout en bout (avec le serveur lancé) : `..\venv\Scripts\python.exe tests\e2e_final.py`. Il écrit le tableau dans `mesures/E2E_RESULTATS.md`.

## 6. Problèmes fréquents

| Symptôme | Cause | Solution |
|---|---|---|
| « Le service d'IA est indisponible » (503) | Ollama arrêté ou modèle absent | `ollama serve`, puis `ollama list` pour vérifier les 2 modèles |
| Page de connexion MySQL en erreur | WampServer arrêté | Lancer WampServer, attendre l'icône verte |
| Graphiques sans PNG dans le PDF | Chrome introuvable | Renseigner `CHROME_PATH` dans `.env` (le PDF régénère les PNG manquants) |
| Réponses texte lentes (20 à 60 s) | LLM sur CPU | Normal sur cette machine ; les calculs et graphiques ne passent pas par le LLM |
| `/app/` affiche « Frontend non compilé » (503) | Frontend non compilé | `cd frontend && npm install && npm run build` |
| Migration en attente | Nouvelle version du code | `python migrate.py` (sauvegarde automatique) |
| Arabe en carrés dans le PDF | Police sans arabe | `PDF_POLICE` doit pointer vers une police qui contient l'arabe (Arial) |

## 7. Restaurer une sauvegarde

```
"C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe" -uroot dataia < backups\dataia_AAAAMMJJ_HHMMSS_....sql
```

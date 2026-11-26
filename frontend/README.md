# DataIA — Modern React SaaS Frontend

Frontend moderne pour la plateforme d'analyse intelligente de données **DataIA**, développé avec **React 18**, **Vite**, **TypeScript**, **Tailwind CSS**, **Recharts**, **Lucide Icons** et **Framer Motion**.

---

## 🚀 Guide de Démarrage Rapide sous Windows

Pour lancer l'application en développement, suivez ces 3 étapes simples :

### 1. Démarrer la Base de Données et MySQL
* Lancez **WampServer** ou **XAMPP** (assurez-vous que le service **MySQL** est en vert / actif sur le port `3306`).
* La base de données `dataia` doit être accessible sans mot de passe sur `root@localhost`.

### 2. Démarrer le Serveur Backend Flask
Ouvrez un premier terminal dans le dossier du projet :
```powershell
# 1. Se placer dans le dossier backend
cd app\DataIA

# 2. Activer l'environnement virtuel Python
.\venv\Scripts\Activate.ps1

# 3. Lancer Flask (il démarrera sur http://127.0.0.1:5000)
python app.py
```

### 3. Démarrer le Serveur de Développement Frontend React
Ouvrez un second terminal à la racine du projet :
```powershell
# 1. Se placer dans le dossier frontend
cd frontend

# 2. Installer les dépendances (déjà fait si le dossier node_modules existe)
npm install

# 3. Lancer Vite
npm run dev
```
* Ouvrez votre navigateur sur **[http://localhost:5173](http://localhost:5173)**.
* Le proxy Vite redirige automatiquement toutes les requêtes (`/api/*`, `/ask_ia`, `/upload`, etc.) vers votre serveur Flask sur `http://127.0.0.1:5000` avec transmission transparente des cookies de session.

---

## 🛠️ Architecture Technique & Fonctionnalités

### 1. Authentification & Sécurité (`src/hooks/useAuth.tsx`, `src/lib/api.ts`)
* Utilise les sessions et cookies HttpOnly de Flask-Login.
* Détection automatique des comptes bloqués : si un utilisateur a `est_bloque = 1`, l'accès est immédiatement verrouillé avec notification claire *"Votre compte est bloqué par l'administrateur."*.
* Routes protégées par `AppLayout` et déconnexion propre.

### 2. Dashboard (`src/pages/DashboardPage.tsx`)
* Cartes KPI interactives : total des fichiers importés et questions posées.
* Zone d'upload moderne par **glisser-déposer (Drag & Drop)** avec validation stricte du format (`.csv`, `.xlsx`, `.xls`) et de la taille maximale (10 Mo).
* Tableau des fichiers récents avec badges de formats et accès direct à l'analyse.

### 3. Chat IA & RAG Haute Précision (`src/pages/ChatPage.tsx`)
* Interface type ChatGPT / Notion : bulles utilisateur à droite, réponses IA stylées à gauche.
* Rendu **Markdown riche** (`react-markdown` + `remark-gfm`) : titres Cyan, listes, code et tableaux formatés.
* **Moteur Graphique Recharts** (`src/components/chat/ChartRenderer.tsx`) : détecte automatiquement le JSON renvoyé par l'IA et affiche instantanément un graphique interactif (Histogramme, Courbe ou Camembert) avec infobulles au survol.
* Bouton **Copier la réponse** et suggestions de questions métiers en un clic.
* Bouton **Export PDF** : génère et télécharge le rapport officiel formaté.

### 4. Bibliothèque de Fichiers (`src/pages/MyFilesPage.tsx`)
* Exploration de tous les fichiers importés avec barre de recherche en temps réel et filtres par format (CSV / Excel).
* Suppression sécurisée avec boîte de dialogue de confirmation modale.

### 5. Console Administrateur (`src/pages/AdminPage.tsx`)
* Accessible uniquement aux utilisateurs ayant le rôle `administrateur`.
* Compteurs globaux : Utilisateurs, Rapports PDF, Analyses totales.
* Tableau de gestion des utilisateurs :
  * Filtrage rapide des analyses en cliquant sur le badge d'activité d'un utilisateur.
  * Bouton **Bloquer / Débloquer** instantané.
  * Bouton **Supprimer définitivement** avec boîte de confirmation.
* Tableau d'audit des analyses avec lien direct de téléchargement des rapports PDF.

---

## 📦 Scripts Disponibles

* `npm run dev` : Lance le serveur Vite en local avec rechargement à chaud (HMR).
* `npm run build` : Compile le projet avec TypeScript (`tsc`) et génère les fichiers de production optimisés dans `dist/`.
* `npm run preview` : Prévisualise le build de production en local.

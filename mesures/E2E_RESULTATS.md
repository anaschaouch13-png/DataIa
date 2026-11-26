# Test de bout en bout — 2026-11-26 08:10

**60/60 OK**

| # | Étape | Attendu | Obtenu | OK/KO | Remarque |
|---|---|---|---|---|---|
| 1 | 1. Inscription + connexion Banque | 201 (ou 409 si déjà créé), domaine Banque | signup 409, login 200, domaine Banque | OK |  |
| 2 | 1. Inscription + connexion E-commerce | 201 (ou 409 si déjà créé), domaine E-commerce | signup 409, login 200, domaine E-commerce | OK |  |
| 3 | 1. Inscription avec un domaine hors liste | 400 refusé | 400 | OK |  |
| 4 | 2. Upload XLSX (Banque) | 201, aperçu + questions suggérées | 201, type Excel, 4 suggestions | OK |  (1.13 s) |
| 5 | 2. Upload CSV (Banque) | 201, aperçu + questions suggérées | 201, type CSV, 4 suggestions | OK |  (0.58 s) |
| 6 | 2. Upload PDF (Banque) | 201, aperçu + questions suggérées | 201, type PDF, 4 suggestions | OK |  (0.56 s) |
| 7 | 2. Upload PNG (Banque) | 201, aperçu + questions suggérées | 201, type Image, 4 suggestions | OK |  (4.96 s) |
| 8 | 2. Upload CLIENTS (Banque) | 201, aperçu + questions suggérées | 201, type CSV, 4 suggestions | OK |  (0.13 s) |
| 9 | 2. Upload XLSX (E-commerce) | 201, aperçu + questions suggérées | 201, type Excel, 4 suggestions | OK |  (0.75 s) |
| 10 | 2. Upload CLIENTS (E-commerce) | 201, aperçu + questions suggérées | 201, type CSV, 4 suggestions | OK |  (0.1 s) |
| 11 | 3. Calcul fr (xlsx) | CA Tunis = 1 107 535 (pandas) | Le chiffre d'affaires total à Tunis est de 1 107 535,92. **Total de `chiffre_affaires`** : **1 107 535,92** > 🔢 *Calculé par pandas — opération : `sum` · colo | OK | intent stat (14.84 s) |
| 12 | 3. Calcul en (xlsx) | CA Tunis = 1 107 535 (pandas) | The total revenue in Tunis is $1,107,535.92. **Total of `chiffre_affaires`** : **1,107,535.92** > 🔢 *Computed by pandas — operation : `sum` · column : `chiffr | OK | intent stat (14.36 s) |
| 13 | 3. Calcul ar (xlsx) | CA Tunis = 1 107 535 (pandas) | مجموع رقم المعاملات في تونس هو **1,107,535.92**. **مجموع لـ `chiffre_affaires`** : **1,107,535.92** > 🔢 *محسوب بواسطة pandas — العملية : `sum` · العمود : `chi | OK | intent stat (16.23 s) |
| 14 | 3. Calcul derja (xlsx) | CA Tunis = 1 107 535 (pandas) | ℹ️ *Réponse en français : le modèle local (3B) ne maîtrise pas la derja, votre question a été traduite automatiquement.* Le total du chiffre d'affaires dans Tu | OK | intent stat (18.51 s) |
| 15 | 3. Superlatif (xlsx) | Informatique 1 891 204 | **`categorie`** — total de `chiffre_affaires` la plus élevée : **Informatique** (1 891 204,59) / categorie / sum(chiffre_affaires) / /---/---/ / Informatique / | OK |  (0.21 s) |
| 16 | 3. Calcul PDF : Quel est le CA total de Tunis ? | 602 532 | Le CA total de Tunis est de 602 532. **Total de `Tunis`** : **602 532** > 🔢 *Calculé par pandas — opération : `sum` · colonne : `Tunis` · 12 lignes utilisées  | OK |  (23.37 s) |
| 17 | 3. Calcul PDF : Quelle est la catégorie la plus forte ? | Informatique 1 037 167 | **`Catégorie`** — total de `Chiffre d'affaires (TND)` la plus élevée : **Informatique** (1 037 167) / Catégorie / sum(Chiffre d'affaires (TND)) / /---/---/ / I | OK |  (0.06 s) |
| 18 | 3. Calcul PDF : Quel est le mois le plus fort ? | Mai 237 858 | Le mois le plus fort est Mai avec un total de 237 858. **Maximum de `Total`** : **237 858** / Mois / Tunis / Sfax / Sousse / Nabeul / Bizerte / Total / /---/- | OK | Le tableau du PDF donne Mai (Juillet 197 381 = meilleur mois de Tunis), voir JUSTIFICATIONS §57 (12.42 s) |
| 19 | 3. Calcul PNG : Quel est le produit le plus vendu en CA ? | Ordinateur portable 594 715 | **`Produit`** — total de `Chiffre d'affaires (TND)` la plus élevée : **Ordinateur portable** (594 715) / Produit / sum(Chiffre d'affaires (TND)) / /---/---/ /  | OK | image OCR (0.05 s) |
| 20 | 3. Calcul PNG : Quelle est la quantité de télévisions ? | 441 | La quantité de télévisions vendues est 441. **Total de `Quantité vendue`** : **441** > 🔢 *Calculé par pandas — opération : `sum` · colonne : `Quantité vendue` | OK | image OCR (18.29 s) |
| 21 | 3. Graphique pie | pie | pie | OK |  (0.87 s) |
| 22 | 3. Graphique bar | bar | bar | OK |  (0.38 s) |
| 23 | 3. Graphique bar_groupe | bar_groupe | bar_groupe | OK |  (0.41 s) |
| 24 | 3. Graphique bar_empile | bar_empile | bar_empile | OK |  (0.46 s) |
| 25 | 3. Graphique line | line | line | OK |  (0.36 s) |
| 26 | 3. Graphique area | area | area | OK |  (0.67 s) |
| 27 | 3. Graphique donut | donut | donut | OK |  (0.34 s) |
| 28 | 3. Graphique scatter | scatter | scatter | OK |  (0.4 s) |
| 29 | 3. Graphique histogram | histogram | histogram | OK |  (0.32 s) |
| 30 | 3. Graphique box | box | box | OK |  (0.34 s) |
| 31 | 3. Graphique heatmap | heatmap | heatmap | OK |  (0.35 s) |
| 32 | 3. Graphique en | graphique ventes par région | pie | OK |  (0.38 s) |
| 33 | 3. Graphique ar | graphique ventes par région | pie | OK |  (0.32 s) |
| 34 | 3. Graphique derja | graphique ventes par région | pie | OK |  (0.38 s) |
| 35 | 3. Question texte fr (PDF) | novembre / décembre | Le rapport indique que les mois de novembre et décembre sont les plus forts de l'année, grâce aux achats de fin d'année. | OK | intent text (9.66 s) |
| 36 | 3. Question texte en (PDF) | november / december | The report indicates that November and December are the strongest months of the year, with the highest sales figures. | OK | intent text (3.17 s) |
| 37 | 3. Question texte ar (PDF) | نوفمبر / ديسمبر / 11 / 12 | التقرير يشير إلى أن شهر نوفمبر هو الشهر الذي حقق فيه أكبر رقم إجمالي للعائد من الأعمال مقارنة بالأشهر الأخرى. كما أنه يشير إلى أن ديسمبر هو الشهر الثاني الذي حق | OK | intent text (13.03 s) |
| 38 | 4. forecast (Banque) | intent forecast, modèle enregistré | 📈 **Prévision de `chiffre_affaires`** par mois — modèle retenu : **LightGBM** **Précision : 90,27 % (MAPE = 9,73 %)** s | OK |  (3.79 s) |
| 39 | 4. anomaly (Banque) | intent anomaly, modèle enregistré | 🔎 **7 anomalie(s)** détectée(s) sur 1 793 lignes (Isolation Forest, colonnes : `quantite`, `prix_unitaire`, `chiffre_aff | OK |  (1.56 s) |
| 40 | 4. forecast (E-commerce) | intent forecast, modèle enregistré | 📈 **Prévision de `chiffre_affaires`** par mois — modèle retenu : **LightGBM** **Précision : 90,27 % (MAPE = 9,73 %)** s | OK |  (0.69 s) |
| 41 | 4. anomaly (E-commerce) | intent anomaly, modèle enregistré | 🔎 **7 anomalie(s)** détectée(s) sur 1 793 lignes (Isolation Forest, colonnes : `quantite`, `prix_unitaire`, `chiffre_aff | OK |  (1.97 s) |
| 42 | 4. Churn (Banque) | scores + 2 graphiques | 👥 **125 client(s) sur 300 (41,7 %) présentent un risque de départ** (probabilité ≥ 50 %). Modèle : arbre de décision (p | OK |  (0.29 s) |
| 43 | 4. Churn (E-commerce) | refus poli (réservé Banque) | Désolé, le modèle **Prédiction du départ des clients (churn)** n'est pas proposé pour votre domaine d'activité (**E-commerce**). Il est réservé au(x) domaine(s) | OK |  (0.06 s) |
| 44 | 5. Simulateur forecast (Banque) | 200 + résultat | 200 {'critere': 'mape', 'figure': {'data': [{'fill': 'toself', 'fillcolor': 'rgba(10,132,224,0 | OK |  |
| 45 | 5. Simulateur anomaly (Banque) | 200 + résultat | 200 {'anomalie': False, 'percentile': 98.3, 'raison': 'chiffre_affaires = 1 445,62 au lieu de  | OK |  |
| 46 | 5. Simulateur churn (Banque) | 200 + résultat | 200 {'entrees': {'active_member': 1.0, 'age': 37.0, 'balance': 97198.54000000001, 'country': ' | OK |  |
| 47 | 5. Simulateur forecast (E-commerce) | 200 + résultat | 200 {'critere': 'mape', 'figure': {'data': [{'fill': 'toself', 'fillcolor': 'rgba(10,132,224,0 | OK |  |
| 48 | 5. Simulateur anomaly (E-commerce) | 200 + résultat | 200 {'anomalie': False, 'percentile': 98.3, 'raison': 'chiffre_affaires = 1 445,62 au lieu de  | OK |  |
| 49 | 5. Simulateur churn (E-commerce) | 403 refusé | 403 | OK |  |
| 50 | 6. Données nettoyées (csv, xlsx, rapport) | 200 pour chaque lien | types ['anomalie', 'churn', 'prevision'], 9/9 OK | OK |  |
| 51 | 6. Téléchargement d'un autre compte | 403 | 403 | OK |  |
| 52 | 7. Rapport PDF complet | sections + graphiques + ML + arabe | 17 pages, 17 images, 1497 Ko, sections True, arabe True | OK |  (7.63 s) |
| 53 | 8. Modifier le profil | nom mis à jour | 200 E2E Banque (modifié) | OK |  |
| 54 | 8. Admin par une utilisatrice | 403 | 403 | OK |  |
| 55 | 8. Tableau de bord admin | liste des comptes (dont E2E) + page Jinja 200 | 10 comptes, E2E présents True, page 200 | OK | session admin du client de test Flask |
| 56 | 8. Fichier d'un autre compte (IDOR) | 404 | pdf 404, ask 404 | OK |  |
| 57 | 8. Déconnexion (POST) puis accès refusé | 401 sur l'API, /dashboard redirige vers /login | avant 200; après : API [401, 401, 401], /ask_ia 401, /dashboard 302 | OK |  |
| 58 | 9. Tables InnoDB + clés étrangères | toutes InnoDB, FK présentes | 9 tables, InnoDB : True, 10 FK | OK |  |
| 59 | 9. Lignes enregistrées (comptes E2E) | chaque table remplie | {'fichiers': 14, 'questions': 66, 'graphiques': 39, 'modeles_ml': 10, 'simulations': 10, 'rapports': 2} | OK |  |
| 60 | 9. Migrations appliquées | 001, 002, 003 | ['001', '002', '003'] | OK |  |

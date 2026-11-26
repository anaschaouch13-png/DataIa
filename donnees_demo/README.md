# Données de démonstration — ⚠️ DONNÉES SYNTHÉTIQUES DE TEST

**Tous les fichiers de ce dossier sont fictifs.** Ils ont été générés aléatoirement par
`generer_donnees_demo.py` (graines fixes : on obtient toujours les mêmes fichiers) pour
tester les trois modèles de DataIA. Ils ne décrivent aucune entreprise ni aucun client réel.
Le mot « synthetique » figure dans le nom de chaque fichier.

| Fichier | Modèle testé | Contenu |
|---|---|---|
| `demo_ventes_synthetique.csv` | **Prévision du CA** | 5 707 ventes, du 01/01/2023 au 31/12/2025. Tendance +15 %/an, pics en été et en décembre, bruit modéré. Colonnes : `date, region, produit, categorie, quantite, prix_unitaire, chiffre_affaires`. |
| `demo_transactions_anomalies_synthetique.csv` | **Détection d'anomalies** | 1 500 transactions, dont **10 anomalies injectées volontairement**. Colonnes : `id_transaction, date, client, canal, produit, quantite, prix_unitaire, montant`. |
| `demo_transactions_anomalies_REPONSES.csv` | (corrigé) | La liste des 10 anomalies injectées et leur nature, pour vérifier le résultat du modèle. |
| `demo_clients_banque_synthetique.csv` | **Churn bancaire** | 300 clients fictifs avec **exactement les colonnes attendues par le modèle** : `customer_id, credit_score, country, gender, age, tenure, balance, products_number, credit_card, active_member, estimated_salary` (sans la colonne `churn`, qui est à prédire). |

## Anomalies injectées (corrigé)

| Transaction | Anomalie |
|---|---|
| T00101, T00251, T00401 | Quantité énorme (150, 95, 80) — montant cohérent |
| T00521, T00691, T00831 | Montant négatif |
| T00976 | Prix absurde (0,05) |
| T01111 | Prix absurde (250 000) |
| T01241 | Montant (30 000) incohérent avec quantité × prix |
| T01381 | Montant (5) incohérent avec quantité × prix |

## Résultats obtenus avec ces fichiers (Phase 5)

- **Prévision** : agrégation mensuelle (36 mois), test sur les 7 derniers mois. Prophet est retenu (MAPE 11,6 %), contre LightGBM (26,1 %) et la référence naïve (13,7 %).
- **Anomalies** : 7 lignes signalées, dont 6 anomalies injectées (1 faux positif). Les 4 autres anomalies injectées figurent dans la liste « à surveiller » (les plus inhabituelles juste sous le seuil). Les quantités énormes mais cohérentes sont les plus difficiles (effet de masquage, voir `JUSTIFICATIONS.md`).
- **Churn** : 300 clients scorés ; la proportion « à risque » est élevée, car les profils sont tirés au hasard et le modèle privilégie le rappel (`class_weight="balanced"`).

## Autres fichiers de test (fournis par l'utilisatrice, dans `uploads/`)

- `ventes_demo_dataia.xlsx` / `.csv` : 1 793 ventes 2024–2025 avec 8 anomalies volontaires.
- `rapport_ventes_2025.pdf`, `tableau_ventes_2025.png` : tests de la Phase 7 (PDF et OCR).

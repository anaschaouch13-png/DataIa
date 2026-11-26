#!/usr/bin/env python3
"""
generer_donnees_demo.py — Génère les jeux de données de DÉMONSTRATION (synthétiques).

⚠️ Ces données sont FICTIVES, créées aléatoirement pour tester la plateforme.
Elles ne décrivent aucune entreprise ni aucun client réel.

Usage (dossier DataIa, venv activé) :  python donnees_demo/generer_donnees_demo.py
Graines aléatoires fixes : le script produit toujours exactement les mêmes fichiers.
"""

import os

import numpy as np
import pandas as pd

DOSSIER = os.path.dirname(os.path.abspath(__file__))
REGIONS = ["Tunis", "Sfax", "Sousse", "Nabeul", "Bizerte"]
PRODUITS = {"Ordinateur portable": ("Informatique", 1900), "Imprimante": ("Informatique", 420),
            "Smartphone": ("Téléphonie", 950), "Écouteurs": ("Accessoires", 85), "Télévision": ("Électroménager", 1300),
            "Montre connectée": ("Accessoires", 340)}


def ventes_pour_prevision():
    """3 ans de ventes : tendance +15 %/an, pics en été et en décembre, bruit modéré."""
    rng = np.random.default_rng(2024)
    lignes = []
    for jour in pd.date_range("2023-01-01", "2025-12-31", freq="D"):
        annee = (jour - pd.Timestamp("2023-01-01")).days / 365
        saison = 1 + 0.25 * np.sin(2 * np.pi * (jour.dayofyear - 100) / 365) + (0.35 if jour.month == 12 else 0)
        for _ in range(rng.poisson(4 * (1.15 ** annee) * saison)):
            produit = rng.choice(list(PRODUITS))
            categorie, prix = PRODUITS[produit]
            prix_reel = round(prix * rng.uniform(0.9, 1.1), 2)
            quantite = int(rng.integers(1, 5))
            lignes.append({"date": jour.date().isoformat(), "region": rng.choice(REGIONS), "produit": produit,
                           "categorie": categorie, "quantite": quantite, "prix_unitaire": prix_reel,
                           "chiffre_affaires": round(quantite * prix_reel, 2)})
    return pd.DataFrame(lignes)


def transactions_avec_anomalies():
    """1 500 transactions normales + 10 anomalies injectées (liste dans le README)."""
    rng = np.random.default_rng(7)
    lignes = []
    for i in range(1500):
        produit = rng.choice(list(PRODUITS))
        prix = round(PRODUITS[produit][1] * rng.uniform(0.85, 1.15), 2)
        quantite = int(rng.integers(1, 6))
        lignes.append({"id_transaction": f"T{i + 1:05d}", "date": (pd.Timestamp("2025-01-01")
                       + pd.Timedelta(days=int(rng.integers(0, 365)))).date().isoformat(),
                       "client": f"C{int(rng.integers(1, 400)):04d}", "canal": rng.choice(["Magasin", "En ligne"]),
                       "produit": produit, "quantite": quantite, "prix_unitaire": prix,
                       "montant": round(quantite * prix, 2)})
    df = pd.DataFrame(lignes)
    anomalies = {  # index -> (modification, description)
        100: ({"quantite": 150}, "quantité énorme (150)"), 250: ({"quantite": 95}, "quantité énorme (95)"),
        400: ({"quantite": 80}, "quantité énorme (80)"),
        520: ({"montant": -900.0}, "montant négatif"), 690: ({"montant": -2500.0}, "montant négatif"),
        830: ({"montant": -120.0}, "montant négatif"),
        975: ({"prix_unitaire": 0.05}, "prix absurde (0,05)"), 1110: ({"prix_unitaire": 250000.0}, "prix absurde (250 000)"),
        1240: ({"montant": 30000.0}, "montant incohérent avec quantité × prix"),
        1380: ({"montant": 5.0}, "montant incohérent avec quantité × prix"),
    }
    for i, (modif, _) in anomalies.items():
        for col, val in modif.items():
            df.loc[i, col] = val
        if "quantite" in modif:                      # montant cohérent avec la quantité énorme
            df.loc[i, "montant"] = round(df.loc[i, "quantite"] * df.loc[i, "prix_unitaire"], 2)
    reference = pd.DataFrame([{"id_transaction": df.loc[i, "id_transaction"], "anomalie_injectee": d}
                              for i, (_, d) in anomalies.items()])
    return df, reference


def clients_banque():
    """300 clients fictifs avec EXACTEMENT les colonnes attendues par le modèle de churn."""
    rng = np.random.default_rng(42)
    n = 300
    solde = np.where(rng.random(n) < 0.36, 0.0, np.round(rng.normal(120000, 30000, n).clip(1000), 2))
    return pd.DataFrame({
        "customer_id": np.arange(90000001, 90000001 + n),
        "credit_score": rng.normal(650, 96, n).clip(350, 850).round().astype(int),
        "country": rng.choice(["France", "Germany", "Spain"], n, p=[0.5, 0.25, 0.25]),
        "gender": rng.choice(["Male", "Female"], n, p=[0.55, 0.45]),
        "age": rng.normal(39, 10, n).clip(18, 92).round().astype(int),
        "tenure": rng.integers(0, 11, n),
        "balance": solde,
        "products_number": rng.choice([1, 2, 3, 4], n, p=[0.5, 0.46, 0.03, 0.01]),
        "credit_card": rng.choice([0, 1], n, p=[0.3, 0.7]),
        "active_member": rng.choice([0, 1], n, p=[0.48, 0.52]),
        "estimated_salary": rng.uniform(11000, 200000, n).round(2),
    })


if __name__ == "__main__":
    ventes = ventes_pour_prevision()
    ventes.to_csv(os.path.join(DOSSIER, "demo_ventes_synthetique.csv"), index=False, encoding="utf-8-sig")
    transactions, reference = transactions_avec_anomalies()
    transactions.to_csv(os.path.join(DOSSIER, "demo_transactions_anomalies_synthetique.csv"), index=False,
                        encoding="utf-8-sig")
    reference.to_csv(os.path.join(DOSSIER, "demo_transactions_anomalies_REPONSES.csv"), index=False, encoding="utf-8-sig")
    clients = clients_banque()
    clients.to_csv(os.path.join(DOSSIER, "demo_clients_banque_synthetique.csv"), index=False, encoding="utf-8-sig")
    print(f"ventes : {len(ventes)} lignes | transactions : {len(transactions)} (dont {len(reference)} anomalies) | "
          f"clients : {len(clients)}")

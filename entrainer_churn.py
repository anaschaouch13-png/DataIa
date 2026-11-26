#!/usr/bin/env python3
"""
entrainer_churn.py — Réentraînement du modèle de churn bancaire (Phase 5).

Base : train_churn.py (version initiale, get_dummies HORS du modèle, max_depth=4 fixé).
Changements :
  1. Pipeline scikit-learn : ColumnTransformer (OneHotEncoder sur country et gender,
     autres colonnes telles quelles) + DecisionTreeClassifier. L'encodage fait partie
     du modèle sauvegardé : impossible d'oublier ou de mal refaire le prétraitement
     au moment de la prédiction.
  2. max_depth choisi par validation croisée stratifiée (5 plis) sur le jeu
     d'entraînement uniquement, en comparant score d'entraînement et de validation
     (sur-apprentissage visible) ; critère : F1 de la classe « part » (1).
  3. Métriques complètes sur le jeu de test (jamais vu) : accuracy, précision, rappel,
     F1, matrice de confusion, ROC-AUC, comparaison avec un modèle naïf.
  4. Sauvegarde : pipeline .joblib + métadonnées .json + données nettoyées (CSV, Excel)
     + rapport de nettoyage, dans a_integrer/modele_banque/.

Usage (dossier DataIa, venv activé) :  python entrainer_churn.py
"""

import datetime
import hashlib
import json
import os
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier

import config
from services.ml import nettoyage

CIBLE = "churn"
CATEGORIELLES = ["country", "gender"]
NUMERIQUES = ["credit_score", "age", "tenure", "balance", "products_number", "credit_card",
              "active_member", "estimated_salary"]
IDENTIFIANT = "customer_id"
GRAINE = 42
PROFONDEURS = [2, 3, 4, 5, 6, 7, 8, 10, 12, None]


def construire_pipeline(max_depth, class_weight=None) -> Pipeline:
    pretraitement = ColumnTransformer([
        # handle_unknown="ignore" : un pays inconnu (ex. « Italy ») donne un vecteur nul au lieu d'une erreur
        ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORIELLES),
        ("nombres", "passthrough", NUMERIQUES),       # un arbre n'a pas besoin de normalisation
    ])
    return Pipeline([("pretraitement", pretraitement),
                     ("arbre", DecisionTreeClassifier(max_depth=max_depth, class_weight=class_weight,
                                                      random_state=GRAINE))])


def main():
    dossier = os.path.dirname(config.CHURN_MODEL_PATH)
    print("=" * 70 + "\n  RÉENTRAÎNEMENT DU MODÈLE CHURN (Pipeline + arbre de décision)\n" + "=" * 70)
    brut = pd.read_csv(config.CHURN_DATA_PATH)
    empreinte = hashlib.sha256(open(config.CHURN_DATA_PATH, "rb").read()).hexdigest()[:16]
    print(f"[1] Données : {brut.shape[0]} lignes, {brut.shape[1]} colonnes (sha256 {empreinte})")

    # ---------- Nettoyage traçable ----------
    rapport = nettoyage.commencer(brut, "churn (entraînement)", os.path.basename(config.CHURN_DATA_PATH))
    df = nettoyage.supprimer_doublons(brut, rapport)
    df = nettoyage.supprimer_doublons(df, rapport, colonnes=[IDENTIFIANT])     # un client = une ligne
    df = df.drop(columns=[IDENTIFIANT])
    rapport.ajouter(f"Colonne « {IDENTIFIANT} » retirée : identifiant sans valeur prédictive "
                    "(un arbre pourrait apprendre des numéros par cœur).")
    df = nettoyage.convertir_numeriques(df, NUMERIQUES + [CIBLE], rapport)
    df = nettoyage.traiter_manquants(df, rapport, numeriques=NUMERIQUES, categorielles=CATEGORIELLES,
                                     obligatoires=[CIBLE])
    for c in CATEGORIELLES:
        df[c] = df[c].astype(str).str.strip()
        rapport.ajouter(f"« {c} » : valeurs {sorted(df[c].unique())} -> encodage one-hot DANS le pipeline "
                        f"(une colonne 0/1 par valeur).")
    valeurs_cible = sorted(df[CIBLE].unique().tolist())
    if valeurs_cible != [0, 1]:
        raise SystemExit(f"Cible inattendue : {valeurs_cible}")
    rapport.ajouter(f"Cible « {CIBLE} » : 0 = reste, 1 = quitte la banque ; taux de départ {df[CIBLE].mean():.2%}.")
    rapport.ajouter("Aucune normalisation : un arbre de décision compare des seuils, l'échelle des colonnes ne change rien.")
    rapport.ajouter("Pas de suppression des valeurs extrêmes : un arbre y est peu sensible et ce sont des clients réels.")

    X, y = df[CATEGORIELLES + NUMERIQUES], df[CIBLE]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=GRAINE)
    rapport.ajouter(f"Séparation stratifiée 80 / 20 (graine {GRAINE}) : {len(X_train)} lignes d'entraînement, "
                    f"{len(X_test)} de test ; taux de départ {y_train.mean():.2%} / {y_test.mean():.2%}.")
    print(f"[2] Entraînement {len(X_train)} / test {len(X_test)} (stratifié)")

    # ---------- Choix de max_depth (et de class_weight) par validation croisée ----------
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=GRAINE)
    tableau = []
    for poids in (None, "balanced"):
        for profondeur in PROFONDEURS:
            res = cross_validate(construire_pipeline(profondeur, poids), X_train, y_train, cv=cv,
                                 scoring=["f1", "accuracy", "roc_auc"], return_train_score=True)
            tableau.append({"max_depth": profondeur, "class_weight": poids,
                            "f1_entrainement": round(res["train_f1"].mean(), 4),
                            "f1_validation": round(res["test_f1"].mean(), 4),
                            "accuracy_validation": round(res["test_accuracy"].mean(), 4),
                            "roc_auc_validation": round(res["test_roc_auc"].mean(), 4)})
    choix = max(tableau, key=lambda r: (r["f1_validation"], -(r["max_depth"] or 99)))
    print("[3] Validation croisée (F1 classe 1) :")
    for r in tableau:
        marque = "  <== retenu" if r is choix else ""
        print(f"    depth={str(r['max_depth']):>4} poids={str(r['class_weight']):>8} | F1 entr. {r['f1_entrainement']:.3f} "
              f"| F1 valid. {r['f1_validation']:.3f} | AUC {r['roc_auc_validation']:.3f}{marque}")

    # ---------- Modèle final + évaluation sur le test ----------
    modele = construire_pipeline(choix["max_depth"], choix["class_weight"]).fit(X_train, y_train)
    proba = modele.predict_proba(X_test)[:, 1]
    pred = modele.predict(X_test)
    naif = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
    cm = confusion_matrix(y_test, pred)
    metriques = {
        "accuracy": round(accuracy_score(y_test, pred), 4),
        "precision": round(precision_score(y_test, pred), 4),
        "rappel": round(recall_score(y_test, pred), 4),
        "f1": round(f1_score(y_test, pred), 4),
        "roc_auc": round(roc_auc_score(y_test, proba), 4),
        "accuracy_modele_naif": round(accuracy_score(y_test, naif.predict(X_test)), 4),
        "matrice_confusion": {"vrais_negatifs": int(cm[0, 0]), "faux_positifs": int(cm[0, 1]),
                              "faux_negatifs": int(cm[1, 0]), "vrais_positifs": int(cm[1, 1])},
        "accuracy_entrainement": round(accuracy_score(y_train, modele.predict(X_train)), 4),
    }
    noms = modele.named_steps["pretraitement"].get_feature_names_out()
    importances = modele.named_steps["arbre"].feature_importances_
    imp_encodees = {n.split("__", 1)[1]: round(float(v), 4) for n, v in zip(noms, importances)}
    imp_variables = {}
    for n, v in imp_encodees.items():
        base = next((c for c in CATEGORIELLES if n.startswith(c + "_")), n)
        imp_variables[base] = round(imp_variables.get(base, 0) + v, 4)
    imp_variables = dict(sorted(imp_variables.items(), key=lambda kv: -kv[1]))

    print(f"[4] Test : accuracy {metriques['accuracy']:.2%} (modèle naïf « tous restent » : "
          f"{metriques['accuracy_modele_naif']:.2%}) | précision {metriques['precision']:.2%} | rappel "
          f"{metriques['rappel']:.2%} | F1 {metriques['f1']:.3f} | AUC {metriques['roc_auc']:.3f}")
    print(f"    Matrice de confusion [[VN FP] [FN VP]] = {cm.tolist()}")
    print(classification_report(y_test, pred, target_names=["Reste (0)", "Part (1)"]))
    print("    Importance des variables :", imp_variables)

    # ---------- Sauvegardes ----------
    chemin_modele = config.CHURN_MODEL_PATH
    joblib.dump(modele, chemin_modele)
    categories = {c: list(map(str, cats)) for c, cats in
                  zip(CATEGORIELLES, modele.named_steps["pretraitement"].named_transformers_["categories"].categories_)}
    bornes = {c: {"min": float(X[c].min()), "max": float(X[c].max()), "mediane": float(X[c].median()),
                  "entier": bool((X[c] % 1 == 0).all())} for c in NUMERIQUES}
    meta = {
        "date_entrainement": datetime.datetime.now().isoformat(timespec="seconds"),
        "version_sklearn": sklearn.__version__, "version_python": sys.version.split()[0],
        "fichier_donnees": os.path.basename(config.CHURN_DATA_PATH), "sha256_donnees": empreinte,
        "type": "Pipeline(ColumnTransformer[OneHotEncoder(country, gender) + passthrough] -> DecisionTreeClassifier)",
        "features_entree": CATEGORIELLES + NUMERIQUES, "categories": categories, "bornes_numeriques": bornes,
        "features_encodees": [n.split("__", 1)[1] for n in noms],
        "classes": {"0": "Reste", "1": "Quitte la banque"}, "cible": CIBLE,
        "parametres": {"max_depth": choix["max_depth"], "class_weight": choix["class_weight"],
                       "random_state": GRAINE, "seuil_decision": 0.5},
        "validation_croisee": tableau, "metriques_test": metriques,
        "importance_variables": imp_variables, "importance_features_encodees": imp_encodees,
        "taille": {"entrainement": len(X_train), "test": len(X_test)},
    }
    chemin_meta = os.path.splitext(chemin_modele)[0] + "_metadonnees.json"
    with open(chemin_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    exports = nettoyage.exporter(df, rapport, dossier, "churn_donnees_nettoyees")
    os.makedirs("mesures", exist_ok=True)
    with open(os.path.join("mesures", "phase5_churn_metriques.json"), "w", encoding="utf-8") as f:
        json.dump({k: meta[k] for k in ("date_entrainement", "version_sklearn", "parametres", "metriques_test",
                                        "importance_variables", "validation_croisee")}, f, ensure_ascii=False, indent=2)
    print(f"[5] Modèle : {chemin_modele}\n    Métadonnées : {chemin_meta}\n    Données nettoyées : {exports}")


if __name__ == "__main__":
    main()

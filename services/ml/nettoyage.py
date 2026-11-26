"""
services/ml/nettoyage.py — Nettoyage traçable des données avant un modèle ML.

Chaque opération est enregistrée dans un `RapportNettoyage` : lignes avant/après,
doublons supprimés, valeurs manquantes traitées (et méthode), conversions de types,
encodages, agrégation. Le jeu de données EXACTEMENT passé au modèle est exporté en
CSV + Excel (avec le rapport dans une feuille séparée) + un rapport .txt, dans :
    exports/donnees_nettoyees/<utilisateur>/<modele>_<date>.csv | .xlsx | _rapport.txt

Objectif (cahier des charges §5.5) : le professeur peut ouvrir le fichier et vérifier
ce que le modèle a réellement reçu.
"""

import datetime
import os
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

import config
from services import stats


@dataclass
class RapportNettoyage:
    modele: str
    source: str = ""
    lignes_avant: int = 0
    colonnes_avant: int = 0
    lignes_apres: int = 0
    colonnes_apres: int = 0
    etapes: List[str] = field(default_factory=list)       # description lisible de chaque étape

    def ajouter(self, texte: str):
        self.etapes.append(texte)

    def en_texte(self) -> str:
        lignes = [f"RAPPORT DE NETTOYAGE — modèle : {self.modele}",
                  f"Date : {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
                  f"Source : {self.source}",
                  f"Lignes : {self.lignes_avant} -> {self.lignes_apres}",
                  f"Colonnes : {self.colonnes_avant} -> {self.colonnes_apres}", "", "ÉTAPES :"]
        lignes += [f"{i}. {e}" for i, e in enumerate(self.etapes, 1)]
        return "\n".join(lignes)

    def en_dict(self) -> dict:
        return {"modele": self.modele, "source": self.source, "lignes_avant": self.lignes_avant,
                "lignes_apres": self.lignes_apres, "colonnes_avant": self.colonnes_avant,
                "colonnes_apres": self.colonnes_apres, "etapes": self.etapes}


def commencer(df: pd.DataFrame, modele: str, source: str) -> RapportNettoyage:
    return RapportNettoyage(modele=modele, source=source, lignes_avant=len(df), colonnes_avant=df.shape[1])


def supprimer_doublons(df: pd.DataFrame, rapport: RapportNettoyage, colonnes: Optional[List[str]] = None) -> pd.DataFrame:
    avant = len(df)
    df = df.drop_duplicates(subset=colonnes).reset_index(drop=True)
    n = avant - len(df)
    rapport.ajouter(f"Doublons supprimés : {n} ligne(s) identique(s)"
                    + (f" sur les colonnes {colonnes}" if colonnes else "") + ".")
    return df


def convertir_numeriques(df: pd.DataFrame, colonnes: List[str], rapport: RapportNettoyage) -> pd.DataFrame:
    """Conversion en nombres (« 1 200,50 », « 12 % », « 100 DT ») ; valeurs illisibles -> manquantes."""
    df = df.copy()
    for c in colonnes:
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        avant = df[c].isna().sum()
        df[c] = stats.en_numerique(df[c])
        illisibles = df[c].isna().sum() - avant
        rapport.ajouter(f"Conversion de « {c} » en nombre" + (f" ({illisibles} valeur(s) illisible(s) devenues manquantes)" if illisibles else "") + ".")
    return df


def convertir_date(df: pd.DataFrame, colonne: str, rapport: RapportNettoyage) -> pd.DataFrame:
    df = df.copy()
    avant = df[colonne].isna().sum()
    df[colonne] = stats.en_dates(df[colonne])
    illisibles = int(df[colonne].isna().sum() - avant)
    rapport.ajouter(f"Conversion de « {colonne} » en date" + (f" ({illisibles} date(s) illisible(s))" if illisibles else "") + ".")
    return df


def traiter_manquants(df: pd.DataFrame, rapport: RapportNettoyage, numeriques: List[str],
                      categorielles: List[str] = (), obligatoires: List[str] = ()) -> pd.DataFrame:
    """
    - colonnes obligatoires (date, cible) : lignes supprimées si vides (on n'invente pas une cible) ;
    - numériques : médiane (robuste aux valeurs extrêmes, contrairement à la moyenne) ;
    - catégorielles : valeur la plus fréquente (mode).
    """
    df = df.copy()
    for c in obligatoires:
        n = int(df[c].isna().sum())
        if n:
            df = df[df[c].notna()]
        rapport.ajouter(f"« {c} » (obligatoire) : {n} ligne(s) sans valeur supprimée(s).")
    for c in numeriques:
        n = int(df[c].isna().sum())
        if n:
            mediane = df[c].median()
            df[c] = df[c].fillna(mediane)
            rapport.ajouter(f"« {c} » : {n} valeur(s) manquante(s) remplacée(s) par la médiane ({mediane:.4g}).")
    for c in categorielles:
        n = int(df[c].isna().sum())
        if n:
            mode = df[c].mode().iloc[0]
            df[c] = df[c].fillna(mode)
            rapport.ajouter(f"« {c} » : {n} valeur(s) manquante(s) remplacée(s) par la valeur la plus fréquente ({mode}).")
    if not any(df[c].isna().any() for c in list(numeriques) + list(categorielles)):
        rapport.ajouter("Aucune valeur manquante restante dans les colonnes utilisées.")
    return df.reset_index(drop=True)


def dossier_utilisateur(id_utilisateur) -> str:
    dossier = os.path.join(config.EXPORT_FOLDER, f"U{id_utilisateur}")
    os.makedirs(dossier, exist_ok=True)
    return dossier


def exporter(df: pd.DataFrame, rapport: RapportNettoyage, dossier: str, nom: str) -> dict:
    """Écrit <nom>.csv, <nom>.xlsx (feuilles « donnees » + « rapport_nettoyage ») et <nom>_rapport.txt."""
    os.makedirs(dossier, exist_ok=True)
    rapport.lignes_apres, rapport.colonnes_apres = len(df), df.shape[1]
    base = os.path.join(dossier, nom)
    df.to_csv(base + ".csv", index=False, encoding="utf-8-sig")       # utf-8-sig : accents corrects dans Excel
    with pd.ExcelWriter(base + ".xlsx", engine="xlsxwriter") as ecrivain:
        df.to_excel(ecrivain, sheet_name="donnees", index=False)
        pd.DataFrame({"rapport de nettoyage": rapport.en_texte().splitlines()}).to_excel(
            ecrivain, sheet_name="rapport_nettoyage", index=False)
    with open(base + "_rapport.txt", "w", encoding="utf-8") as f:
        f.write(rapport.en_texte())
    return {"csv": base + ".csv", "xlsx": base + ".xlsx", "rapport": base + "_rapport.txt"}

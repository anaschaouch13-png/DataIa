"""
services/parsers.py — Parser unifié (Phase 7) : tout fichier -> DataFrame(s) pandas + texte pour le RAG.

| Format | Outil | Ce qui est extrait |
|---|---|---|
| CSV   | pandas + charset-normalizer + csv.Sniffer | encodage et séparateur détectés automatiquement |
| Excel | pandas (openpyxl / xlrd) | TOUTES les feuilles (fusionnées si mêmes colonnes) |
| PDF   | pdfplumber | tous les tableaux de toutes les pages + le texte |
| Image | RapidOCR (onnxruntime, sans installation système) | texte + tableau reconstruit à partir des positions |

Traitements communs :
  - les nombres écrits en texte (« 18 521 », « 1 234,56 », « 12 % ») sont convertis ;
  - les lignes de TOTAL d'un tableau (« Total », « المجموع ») sont retirées : les garder
    doublerait toutes les sommes calculées par pandas (signalé dans les remarques) ;
  - plusieurs tableaux (ex. un PDF avec « CA par mois » et « CA par catégorie ») sont conservés ;
    `table_pour_question` choisit celui qui correspond le mieux à la question.
Le résultat est mis en cache (fichier + date de modification) : un PDF ou une image n'est
analysé qu'une fois.
"""

import csv
import io
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

log = logging.getLogger("dataia.parsers")

EXTENSIONS_TABLEUR = (".csv", ".xls", ".xlsx")
EXTENSIONS_PDF = (".pdf",)
EXTENSIONS_IMAGE = (".png", ".jpg", ".jpeg")
MOTS_TOTAL = {"total", "totaux", "total general", "total général", "somme", "sum", "grand total",
              "المجموع", "المجموع العام", "الإجمالي", "الاجمالي"}


@dataclass
class ResultatParsing:
    tables: List[tuple]                     # [(nom, DataFrame), ...] — au moins une table
    texte: str = ""                         # texte libre du document (PDF / image) pour le RAG
    source: str = ""                        # description lisible (« PDF : 2 tableaux, 1 page »)
    remarques: List[str] = field(default_factory=list)
    duree_s: float = 0.0

    @property
    def principal(self) -> pd.DataFrame:
        return max(self.tables, key=lambda t: t[1].size)[1]

    def textes_rag(self) -> List[str]:
        """Lignes de TOUS les tableaux + paragraphes du texte : ce que le RAG indexe."""
        textes = []
        for nom, df in self.tables:
            prefixe = f"[{nom}] " if len(self.tables) > 1 else ""
            textes += [prefixe + " | ".join(f"{c}: {v}" for c, v in ligne.items())
                       for ligne in df.astype(str).to_dict(orient="records")]
        # Texte libre découpé en PHRASES (sans les lignes de tableau, déjà indexées ci-dessus) :
        # un gros bloc mêlant texte et chiffres « dilue » la recherche (mesuré : la phrase sur les
        # mois de fin d'année n'était pas retrouvée).
        lignes_texte = [l for l in self.texte.splitlines()
                        if len(re.findall(r"\d[\d\s.,]*", l)) < 3 and l.strip()]
        phrases = re.split(r"(?<=[.!?])\s+", " ".join(lignes_texte))
        textes += [p.strip() for p in phrases if len(p.strip()) > 20]
        return textes or ["(document vide)"]


# ---------------------------------------------------------------------------
# Normalisation commune
# ---------------------------------------------------------------------------
def _nettoyer_entetes(df: pd.DataFrame) -> pd.DataFrame:
    noms, vus = [], {}
    for i, c in enumerate(df.columns):
        nom = re.sub(r"\s+", " ", str(c)).strip() or f"colonne_{i + 1}"
        if nom.lower().startswith("unnamed"):
            nom = f"colonne_{i + 1}"
        if nom in vus:
            vus[nom] += 1
            nom = f"{nom}_{vus[nom]}"
        vus[nom] = vus.get(nom, 0)
        noms.append(nom)
    df.columns = noms
    return df


def normaliser(df: pd.DataFrame, nom: str, remarques: List[str]) -> pd.DataFrame:
    """En-têtes propres, lignes vides retirées, lignes de total retirées, nombres en texte convertis."""
    from services.stats import en_numerique
    df = _nettoyer_entetes(df.copy())
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = df[~df.astype(str).apply(lambda l: all(v.strip() in ("", "None", "nan") for v in l), axis=1)]
    if len(df.columns):
        premiere = df.iloc[:, 0].astype(str).str.strip().str.lower()
        totaux = premiere.isin(MOTS_TOTAL)
        if totaux.any():
            remarques.append(f"{nom} : {int(totaux.sum())} ligne(s) de total retirée(s) "
                             "(sinon chaque somme calculée serait comptée deux fois).")
            df = df[~totaux]
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype) in ("str", "string"):
            valeurs = df[c].dropna().astype(str).str.strip()
            valeurs = valeurs[valeurs != ""]
            if len(valeurs) and en_numerique(valeurs).notna().mean() >= 0.9:
                df[c] = en_numerique(df[c].astype(str))
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# CSV et Excel
# ---------------------------------------------------------------------------
def lire_csv(chemin: str) -> ResultatParsing:
    brut = open(chemin, "rb").read()
    encodage = "utf-8-sig"
    try:
        brut.decode("utf-8")
    except UnicodeDecodeError:
        from charset_normalizer import from_bytes
        meilleur = from_bytes(brut).best()
        encodage = meilleur.encoding if meilleur else "latin-1"
    texte = brut.decode(encodage, errors="replace")
    try:
        separateur = csv.Sniffer().sniff(texte[:20000], delimiters=",;\t|").delimiter
    except csv.Error:
        separateur = ","
    remarques = [] if encodage in ("utf-8", "utf-8-sig") else [f"Encodage détecté : {encodage}."]
    if separateur != ",":
        remarques.append(f"Séparateur détecté : « {separateur if separateur != chr(9) else 'tabulation'} ».")
    df = pd.read_csv(io.StringIO(texte), sep=separateur, engine="python")
    return ResultatParsing([("donnees", normaliser(df, "donnees", remarques))],
                           source=f"CSV ({encodage}, séparateur « {separateur if separateur != chr(9) else 'tab'} »)",
                           remarques=remarques)


def lire_excel(chemin: str) -> ResultatParsing:
    feuilles = pd.read_excel(chemin, sheet_name=None)
    remarques: List[str] = []
    tables = [(nom, normaliser(df, nom, remarques)) for nom, df in feuilles.items()]
    tables = [(n, d) for n, d in tables if not d.empty]
    if not tables:
        raise ValueError("Le classeur Excel ne contient aucune donnée.")
    colonnes = {tuple(d.columns) for _, d in tables}
    if len(tables) > 1 and len(colonnes) == 1:
        # Mêmes colonnes sur chaque feuille (ex. une feuille par année) : une seule table
        fusion = pd.concat([d.assign(feuille=n) for n, d in tables], ignore_index=True)
        remarques.append(f"{len(tables)} feuilles de même structure fusionnées (colonne « feuille » ajoutée).")
        tables = [("donnees", fusion)]
    elif len(tables) > 1:
        remarques.append(f"{len(tables)} feuilles de structures différentes : chacune est conservée, "
                         "la plus pertinente est choisie selon la question.")
    return ResultatParsing(tables, source=f"Excel ({len(feuilles)} feuille(s))", remarques=remarques)


# ---------------------------------------------------------------------------
# PDF (pdfplumber)
# ---------------------------------------------------------------------------
def lire_pdf(chemin: str) -> ResultatParsing:
    import pdfplumber
    remarques: List[str] = []
    tables, textes = [], []
    with pdfplumber.open(chemin) as pdf:
        nb_pages = len(pdf.pages)
        for num, page in enumerate(pdf.pages, 1):
            textes.append(page.extract_text() or "")
            for t in page.extract_tables():
                lignes = [[(c or "").strip() for c in l] for l in t if any(c for c in l)]
                if len(lignes) >= 2 and len(lignes[0]) >= 2:
                    df = pd.DataFrame(lignes[1:], columns=lignes[0])
                    # Un tableau coupé sur deux pages (mêmes en-têtes) est recollé
                    precedent = next((i for i, (_, d) in enumerate(tables) if list(d.columns) == list(df.columns)), None)
                    if precedent is not None:
                        tables[precedent] = (tables[precedent][0], pd.concat([tables[precedent][1], df], ignore_index=True))
                    else:
                        tables.append((f"tableau_{len(tables) + 1} (page {num})", df))
    texte = "\n\n".join(textes).strip()
    tables = [(n, normaliser(d, n, remarques)) for n, d in tables]
    tables = [(n, d) for n, d in tables if not d.empty]
    if not tables:
        if not texte:
            raise ValueError("Aucun texte ni tableau lisible dans ce PDF (PDF scanné ? essayez une image).")
        tables = [("texte", pd.DataFrame({"texte": [l for l in texte.splitlines() if l.strip()]}))]
        remarques.append("Aucun tableau détecté : le texte est analysé par l'IA (questions descriptives).")
    return ResultatParsing(tables, texte=texte, remarques=remarques,
                           source=f"PDF : {len(tables)} tableau(x), {nb_pages} page(s)")


# ---------------------------------------------------------------------------
# Image (RapidOCR) : texte + reconstruction du tableau par positions
# ---------------------------------------------------------------------------
_ocr = None
_verrou_ocr = threading.Lock()


def _moteur_ocr():
    global _ocr
    with _verrou_ocr:
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr = RapidOCR()               # modèles ONNX embarqués (~15 Mo), CPU uniquement
    return _ocr


def reconstruire_tableau(boites: list) -> tuple:
    """
    boites = [(x1, y1, x2, y2, texte), ...]. Regroupe en LIGNES (même hauteur), puis aligne les
    cellules sur les COLONNES de la ligne d'en-tête (la plus longue). Retourne (DataFrame | None, titres).
    """
    if not boites:
        return None, []
    hauteur = sorted(b[3] - b[1] for b in boites)[len(boites) // 2]
    boites = sorted(boites, key=lambda b: (b[1] + b[3]) / 2)
    lignes, courante, y_courant = [], [], None
    for b in boites:
        y = (b[1] + b[3]) / 2
        if y_courant is None or abs(y - y_courant) <= hauteur * 0.6:
            courante.append(b)
            y_courant = y if y_courant is None else (y_courant + y) / 2
        else:
            lignes.append(sorted(courante, key=lambda b: b[0]))
            courante, y_courant = [b], y
    lignes.append(sorted(courante, key=lambda b: b[0]))

    # Fusion des zones très proches d'une même ligne : l'OCR coupe souvent un nombre au
    # séparateur de milliers (« 157 » + « 737 », écart de -3 à +2 px, alors que deux colonnes
    # sont séparées de plus de 280 px) -> une seule cellule « 157 737 ».
    def fusionner(ligne):
        fusion = [list(ligne[0])]
        for b in ligne[1:]:
            precedente = fusion[-1]
            if b[0] - precedente[2] < hauteur * 0.5:
                precedente[2] = max(precedente[2], b[2])
                precedente[4] = f"{precedente[4]} {b[4]}"
            else:
                fusion.append(list(b))
        return [tuple(b) for b in fusion]
    lignes = [fusionner(l) for l in lignes]

    nb_max = max(len(l) for l in lignes)
    if nb_max < 2:
        return None, [" ".join(b[4] for b in l) for l in lignes]
    i_entete = next(i for i, l in enumerate(lignes) if len(l) == nb_max)
    titres = [" ".join(b[4] for b in l) for l in lignes[:i_entete]]
    entete = lignes[i_entete]
    # Frontières des colonnes : milieu entre deux cellules d'en-tête consécutives
    frontieres = [(entete[k][2] + entete[k + 1][0]) / 2 for k in range(len(entete) - 1)]

    def colonne(b):
        centre = (b[0] + b[2]) / 2
        return sum(centre > f for f in frontieres)

    donnees = []
    for l in lignes[i_entete + 1:]:
        cellules = [""] * len(entete)
        for b in l:
            k = colonne(b)
            cellules[k] = (cellules[k] + " " + b[4]).strip()      # « 594 » + « 715 » -> « 594 715 »
        if sum(bool(c) for c in cellules) >= max(2, len(entete) // 2):
            donnees.append(cellules)
    if not donnees:
        return None, titres
    return pd.DataFrame(donnees, columns=[b[4] for b in entete]), titres


def lire_image(chemin: str) -> ResultatParsing:
    moteur = _moteur_ocr()
    resultat, _ = moteur(chemin)
    if not resultat:
        raise ValueError("Aucun texte reconnu dans l'image.")
    boites = []
    for polygone, texte, confiance in resultat:
        xs, ys = [p[0] for p in polygone], [p[1] for p in polygone]
        boites.append((min(xs), min(ys), max(xs), max(ys), str(texte).strip()))
    confiance_moy = sum(float(r[2]) for r in resultat) / len(resultat)
    df, titres = reconstruire_tableau(boites)
    texte = "\n".join(t for t in titres) + "\n" + "\n".join(b[4] for b in boites)
    remarques = [f"Texte reconnu par OCR (RapidOCR) : {len(boites)} zones, confiance moyenne {confiance_moy:.0%}. "
                 "Vérifiez les valeurs importantes : une erreur de lecture reste possible."]
    if df is None:
        df = pd.DataFrame({"texte": [b[4] for b in boites]})
        remarques.append("Aucun tableau reconnu : le texte est analysé par l'IA.")
        nom = "texte"
    else:
        nom = titres[0] if titres else "tableau_image"
    return ResultatParsing([(nom, normaliser(df, nom, remarques))], texte=texte, remarques=remarques,
                           source=f"Image (OCR) : tableau de {len(df)} ligne(s)" if nom != "texte" else "Image (OCR) : texte")


# ---------------------------------------------------------------------------
# Point d'entrée + cache
# ---------------------------------------------------------------------------
_cache: "OrderedDict[tuple, ResultatParsing]" = OrderedDict()
_verrou_cache = threading.Lock()
TAILLE_CACHE = 16


def analyser_fichier(chemin: str) -> ResultatParsing:
    cle = (os.path.abspath(chemin), os.path.getmtime(chemin))
    with _verrou_cache:
        if cle in _cache:
            _cache.move_to_end(cle)
            return _cache[cle]
    debut = time.time()
    ext = os.path.splitext(chemin.lower())[1]
    if ext == ".csv":
        res = lire_csv(chemin)
    elif ext in (".xls", ".xlsx"):
        res = lire_excel(chemin)
    elif ext in EXTENSIONS_PDF:
        res = lire_pdf(chemin)
    elif ext in EXTENSIONS_IMAGE:
        res = lire_image(chemin)
    else:
        raise ValueError(f"Format non supporté : {ext}")
    res.duree_s = round(time.time() - debut, 2)
    log.info("Fichier analysé (%s) en %.2f s : %s", ext, res.duree_s, res.source)
    with _verrou_cache:
        _cache[cle] = res
        while len(_cache) > TAILLE_CACHE:
            _cache.popitem(last=False)
    return res


def table_pour_question(res: ResultatParsing, question: str) -> pd.DataFrame:
    """
    Plusieurs tableaux : on garde celui dont les COLONNES (ou les valeurs) sont citées dans la
    question. Ex. « catégorie la plus forte » -> tableau des catégories ; « CA de Tunis » ->
    tableau mensuel (colonne « Tunis »). À égalité : le plus grand tableau.
    """
    if len(res.tables) == 1:
        return res.tables[0][1]
    from services.semantique import normaliser as norm
    q = " " + norm(question) + " "

    def score(df):
        s = 0
        for c in df.columns:
            nom = norm(c).strip()
            racine = nom[:6] if len(nom) > 6 else nom
            if nom and (f" {nom} " in q or (len(racine) >= 4 and racine in q)):
                s += 3
        for c in df.columns[:2]:                     # valeurs des premières colonnes (catégories, mois...)
            for v in df[c].astype(str).head(40):
                v = norm(v).strip()
                if len(v) >= 4 and f" {v} " in q:
                    s += 2
        return s
    return max(res.tables, key=lambda t: (score(t[1]), t[1].size))[1]


def charger_dataframe(chemin: str) -> pd.DataFrame:
    """Compatibilité (Phases 1-6) : la table principale du fichier."""
    return analyser_fichier(chemin).principal

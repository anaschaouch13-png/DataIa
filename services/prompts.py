"""
services/prompts.py — Prompts envoyés au LLM.

Regroupés ici pour pouvoir les relire, les justifier et les modifier sans toucher
à la logique. Deux principes (Phase 3) :
  1. Prompts COURTS : seulement les colonnes, leurs types et 3 lignes d'exemple
     (plus de describe() complet) -> moins de tokens à lire, réponse plus rapide.
  2. Partie FIXE en premier (message système identique d'un appel à l'autre) :
     Ollama réutilise alors le début déjà calculé (cache du préfixe).
"""

import pandas as pd

from services.langue import consigne_langue
from services.stats import est_date, est_numerique

# ---------------------------------------------------------------------------
# Contexte réduit d'un fichier : colonnes + types + 3 lignes
# ---------------------------------------------------------------------------
def type_lisible(df: pd.DataFrame, colonne: str) -> str:
    """Type simplifié compréhensible par le LLM : nombre, date ou texte."""
    if est_numerique(df, colonne):
        return "nombre"
    if est_date(df, colonne):
        return "date"
    return "texte"


def contexte_fichier(df: pd.DataFrame, nb_lignes: int = 3) -> str:
    """Colonnes, types (df.dtypes simplifiés) et quelques lignes d'exemple."""
    lignes_types = [f"- {c} : {type_lisible(df, c)} (dtype {df[c].dtype})" for c in df.columns]
    texte = (f"FICHIER : {len(df)} lignes, {len(df.columns)} colonnes\n"
             f"COLONNES (nom : type) :\n" + "\n".join(lignes_types))
    if nb_lignes:
        texte += f"\n{nb_lignes} LIGNES D'EXEMPLE (CSV) :\n" + df.head(nb_lignes).to_csv(index=False).strip()
    return texte


# ---------------------------------------------------------------------------
# 1. Routeur (sortie JSON contrainte)
# ---------------------------------------------------------------------------
PROMPT_SYSTEME_ROUTEUR = """Tu es le routeur de la plateforme DataIA. Tu reçois la description d'un tableau de données et une question. Tu ne réponds PAS à la question : tu la classes et tu remplis le JSON demandé.

INTENT :
- stat : un calcul sur les données (total, somme, moyenne, médiane, nombre de lignes, minimum, maximum, classement / top N, valeur par catégorie, évolution dans le temps, pourcentage / part).
- text : une question descriptive ou une recherche d'information (quelles valeurs existent, description d'une ligne, explication).
- graph : un graphique est demandé.
- forecast : une prévision du futur. anomaly : des anomalies ou fraudes. churn : des clients qui risquent de partir. export : un export PDF.

OPERATION (si intent = stat, sinon none) :
- sum (total), mean (moyenne), median, count (combien de lignes), min, max
- top : les N plus grands (ou plus petits avec ordre asc), n = N
- groupby : une valeur par catégorie (« par région », « pour chaque produit ») -> colonne_groupe
- trend : évolution dans le temps -> colonne_date et periode
- percentage : part de chaque catégorie dans le total -> colonne_groupe
colonne = colonne numérique mesurée. agregation = sum par défaut (mean si « moyenne par »).
filtres : seulement si la question impose EXPLICITEMENT une condition sur une valeur citée dans la question (colonne == valeur, annee = année citée). La valeur doit être écrite dans la question. Sinon filtres = [].
Choisis uniquement des noms de colonnes de la liste fournie."""


def schema_routeur(df: pd.DataFrame) -> dict:
    """
    JSON schema passé au paramètre `format` d'Ollama. Les noms de colonnes sont des
    `enum` : le modèle ne PEUT PAS produire une colonne qui n'existe pas.
    """
    colonnes = [str(c) for c in df.columns]
    col_ou_null = {"anyOf": [{"type": "string", "enum": colonnes}, {"type": "null"}]}
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["stat", "text", "graph", "forecast", "anomaly", "churn", "export"]},
            "operation": {"type": "string", "enum": ["sum", "mean", "median", "count", "min", "max", "top",
                                                      "groupby", "trend", "percentage", "none"]},
            "colonne": col_ou_null,
            "colonne_groupe": col_ou_null,
            "colonne_date": col_ou_null,
            "agregation": {"type": "string", "enum": ["sum", "mean", "median", "count", "min", "max"]},
            "n": {"type": "integer"},
            "ordre": {"type": "string", "enum": ["desc", "asc"]},
            "periode": {"type": "string", "enum": ["jour", "semaine", "mois", "trimestre", "annee"]},
            "filtres": {
                "type": "array", "maxItems": 3,
                "items": {"type": "object", "properties": {
                    "colonne": {"type": "string", "enum": colonnes},
                    "operateur": {"type": "string", "enum": ["==", "!=", ">", ">=", "<", "<=", "contient", "annee", "mois"]},
                    "valeur": {"type": "string"}},
                    "required": ["colonne", "operateur", "valeur"]},
            },
        },
        # Champs obligatoires réduits au minimum : chaque champ généré coûte ~0,1 s sur CPU.
        # Le regroupement et la période sont aussi détectés par règles (semantique.py).
        "required": ["intent", "operation", "colonne", "filtres"],
    }


def prompt_utilisateur_routeur(df: pd.DataFrame, question: str) -> str:
    return f"{contexte_fichier(df)}\n\nQUESTION : {question}"


# ---------------------------------------------------------------------------
# 2. RAG (questions « text »)
# ---------------------------------------------------------------------------
PROMPT_SYSTEME_RAG = """Tu es l'assistant d'analyse de données de la plateforme DataIA.
Tu réponds à partir de la description du fichier et des EXTRAITS (lignes les plus proches de la question).

RÈGLES :
1. Ne cite que des valeurs, noms et chiffres présents dans les données fournies. N'invente rien.
2. Les extraits ne sont qu'une partie du fichier : ne calcule JAMAIS de total, moyenne ou nombre sur l'ensemble du fichier.
3. Si l'information n'est pas dans les données, dis-le simplement.
4. Sois clair et concis ; utilise des listes à puces pour énumérer.
5. Ne produis jamais de graphique ni de JSON : les graphiques sont générés par un autre module.

LANGUE : {consigne_langue}"""


def prompt_systeme_rag(langue_reponse: str) -> str:
    # Phase 4 : l'ancienne règle « produis un JSON {"type_graph": ...} » est supprimée ;
    # le LLM inventait les valeurs du graphique (ex. 2 régions sur 5, valeurs fausses).
    return PROMPT_SYSTEME_RAG.format(consigne_langue=consigne_langue(langue_reponse))


def prompt_utilisateur_rag(df: pd.DataFrame, valeurs_categories: str, extraits: str,
                           question: str, langue_reponse: str) -> str:
    # Pas de lignes d'exemple ici : les EXTRAITS montrent déjà des lignes réelles (-~150 tokens)
    return f"""{contexte_fichier(df, nb_lignes=0)}

VALEURS PRÉSENTES DANS LES COLONNES TEXTE :
{valeurs_categories}

EXTRAITS DU FICHIER :
{extraits}

QUESTION : {question}

{consigne_langue(langue_reponse)}"""


# ---------------------------------------------------------------------------
# 3. Reformulation d'un résultat calculé par pandas
# ---------------------------------------------------------------------------
PROMPT_SYSTEME_REFORMULATION = """Tu rédiges la réponse finale de la plateforme DataIA.
On te donne une question et le RÉSULTAT EXACT calculé par le logiciel pandas.
- Écris 1 ou 2 phrases simples qui répondent à la question avec ce résultat.
- Recopie les nombres EXACTEMENT comme ils sont écrits dans le résultat.
- N'ajoute AUCUN autre nombre, ne fais aucun calcul, pas de liste, pas de tableau.
- Respecte la langue demandée."""


def prompt_utilisateur_reformulation(question: str, resultat_texte: str, langue_reponse: str) -> str:
    return f"QUESTION : {question}\nRÉSULTAT EXACT : {resultat_texte}\n{consigne_langue(langue_reponse)}"

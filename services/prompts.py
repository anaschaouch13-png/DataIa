"""
services/prompts.py — Prompts envoyés au LLM.

Regroupés ici pour pouvoir les relire, les justifier et les modifier
sans toucher à la logique de l'application.
"""

from services.langue import consigne_langue

# Prompt système du RAG (questions "texte"). Court et explicite : un modèle 3B
# suit mieux quelques règles claires qu'un long prompt.
PROMPT_SYSTEME_RAG = """Tu es l'assistant d'analyse de données de la plateforme DataIA.
Tu réponds à partir des COLONNES, STATISTIQUES et EXTRAITS fournis pour un fichier CSV/Excel.

RÈGLES :
1. Ne cite que des valeurs, noms et chiffres présents dans les données fournies. N'invente rien.
2. Si l'information n'est pas dans les données, dis-le simplement.
3. Les EXTRAITS ne sont qu'une partie du fichier : pour un total ou une moyenne sur tout le fichier,
   utilise les STATISTIQUES GLOBALES, pas les extraits.
4. Sois clair et concis ; utilise des listes à puces pour énumérer.
5. Si l'utilisateur demande explicitement un graphique, ajoute ce JSON strict avec les données :
   {{"type_graph": "bar", "title": "Titre", "data": {{"x": ["A", "B"], "y": [10, 20]}}}}
   (types possibles : "bar", "line", "pie").
6. Pour un export PDF, indique le bouton « Export PDF » en haut de la page.

LANGUE : {consigne_langue}"""


def prompt_systeme_rag(langue_reponse: str) -> str:
    """Prompt système complété avec la consigne de langue de réponse."""
    return PROMPT_SYSTEME_RAG.format(consigne_langue=consigne_langue(langue_reponse))


def prompt_utilisateur_rag(colonnes, valeurs_categories: str, stats: str,
                           extraits: str, question: str, langue_reponse: str) -> str:
    """Message utilisateur : contexte du fichier + question (éventuellement traduite)."""
    return f"""COLONNES DISPONIBLES :
{colonnes}

VALEURS PRÉSENTES PAR COLONNE (catégories) :
{valeurs_categories}

STATISTIQUES GLOBALES (calculées sur tout le fichier) :
{stats}

EXTRAITS DU FICHIER (lignes les plus proches de la question) :
{extraits}

QUESTION : {question}

{consigne_langue(langue_reponse)}"""

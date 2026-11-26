"""
services/langue.py — Détection de langue et prise en charge de la derja tunisienne.

Langues reconnues :
    fr          français
    en          anglais
    ar          arabe standard (lettres arabes)
    derja_ar    derja tunisienne en lettres arabes      ("شنوة أكثر منتوج تباع برشا؟")
    derja_latin derja tunisienne en lettres latines     ("a3tini 9addech el ventes")

Pourquoi des règles et pas le LLM pour détecter la langue ?
    - c'est instantané (le LLM met plusieurs secondes sur CPU) et déterministe ;
    - nos tests montrent que qwen2.5:3b ne reconnaît pas la derja (il l'a prise
      pour du wolof), il ne peut donc pas la détecter lui-même.

Limite du modèle 3B (testée, voir JUSTIFICATIONS.md) : il ne comprend pas la derja.
On traduit donc les mots derja courants via un glossaire AVANT d'envoyer la
question au LLM, puis on répond en français (derja latine) ou en arabe standard
(derja en lettres arabes), avec un avertissement visible.
"""

import re
from dataclasses import dataclass

from config import DERJA_ARABE_REPONSE, DERJA_LATIN_REPONSE

# ---------------------------------------------------------------------------
# 1. Glossaires derja (approximatifs, mot à mot). Les expressions de plusieurs
#    mots sont placées en premier pour être remplacées avant les mots seuls.
# ---------------------------------------------------------------------------
GLOSSAIRE_DERJA_LATIN = {
    # expressions
    "elli fet": "dernier", "li fet": "dernier", "eli fet": "dernier",
    "elli jey": "prochain", "li jey": "prochain",
    # mots interrogatifs
    "chnowa": "quel", "chnoua": "quel", "chnouwa": "quel", "chnou": "quel",
    "chnia": "quel", "chniya": "quel", "chneya": "quel",
    "9addech": "combien", "9adech": "combien", "qaddech": "combien", "kaddech": "combien",
    "kifech": "comment", "kifach": "comment", "kifeh": "comment",
    "3lech": "pourquoi", "aalech": "pourquoi", "3lach": "pourquoi",
    "wa9tech": "quand", "waktech": "quand",
    "chkoun": "qui", "chkon": "qui",
    "win": "où", "wen": "où",
    # verbes / demandes
    "a3tini": "donne-moi", "a3tina": "donne-nous", "aatini": "donne-moi",
    "warini": "montre-moi", "werini": "montre-moi", "warrini": "montre-moi",
    "orsom": "dessine", "ersem": "dessine", "orsomli": "dessine-moi",
    "nheb": "je veux", "n7eb": "je veux", "nhab": "je veux", "n7ib": "je veux",
    "nchouf": "voir", "chouf": "regarde",
    "e7seb": "calcule", "ahseb": "calcule", "a7seb": "calcule",
    "tba3": "vendu", "tbe3": "vendu", "bie3": "vente", "bi3": "vente",
    "yokhrjou": "partir", "ykharjou": "partir", "yemchiw": "partent", "mechi": "partir",
    # quantités / comparaisons
    "barcha": "beaucoup", "barsha": "beaucoup", "yesser": "beaucoup",
    "akther": "le plus", "ekther": "le plus", "aktar": "le plus",
    "a9al": "le moins", "a9el": "le moins", "akal": "le moins",
    "jemla": "total", "jomla": "total", "majmou3": "somme", "mejmou3": "somme",
    "kol": "chaque",
    # temps
    "chhar": "mois", "ech-chhar": "le mois", "3am": "année", "aam": "année",
    "jom3a": "semaine", "nhar": "jour", "lyoum": "aujourd'hui", "elyoum": "aujourd'hui",
    "tawa": "maintenant", "taw": "maintenant", "fet": "passé", "jey": "prochain",
    # métier
    "ma7soul": "chiffre d'affaires", "dakhl": "revenus", "dakhla": "revenus",
    "flous": "argent", "sel3a": "produit", "mantouj": "produit",
    "7rif": "client", "7rafa": "clients", "kliyen": "client",
    # mots outils
    "mta3": "de", "mte3": "de", "mtaa": "de", "mte3hom": "leur",
    "fil": "dans le", "fel": "dans le", "fi": "dans", "mel": "du", "mil": "du",
    "m3a": "avec", "wala": "ou", "ken": "si", "khater": "parce que", "5ater": "parce que",
    "zeda": "aussi", "zada": "aussi", "famma": "il y a", "fama": "il y a",
    "mouch": "pas", "mech": "pas", "mich": "pas", "behi": "bien", "bahi": "bien",
    "el": "le", "w": "et",
}

GLOSSAIRE_DERJA_ARABE = {
    # expressions
    "اللي فات": "الماضي", "إلي فات": "الماضي", "اللي جاي": "القادم",
    # interrogatifs
    "شنوة": "ما", "شنية": "ما", "شنو": "ما", "شنوا": "ما",
    "قداش": "كم", "كيفاش": "كيف", "علاش": "لماذا", "وقتاش": "متى",
    "وين": "أين", "شكون": "من",
    # verbes
    "عطيني": "أعطني", "وريني": "أرني", "ورّيني": "أرني", "ارسملي": "ارسم لي",
    "نحب": "أريد", "نحبّ": "أريد", "نشوف": "أرى", "احسبلي": "احسب لي",
    "تباع": "بيع", "تبيع": "بيع", "يخرجو": "يغادرون", "يمشيو": "يغادرون",
    # quantités
    "برشا": "كثيرا", "ياسر": "كثيرا", "أكثر": "أكثر",
    # temps
    "توا": "الآن", "تو": "الآن", "فات": "الماضي",
    # métier
    "منتوج": "منتج", "حريف": "عميل", "حرفاء": "عملاء", "فلوس": "مال",
    # mots outils
    "متاع": "الخاص بـ", "متع": "الخاص بـ", "اللي": "الذي", "فما": "هناك",
    "موش": "ليس", "مش": "ليس", "زادة": "أيضا", "خاطر": "لأن", "باش": "لكي",
}

# Mots qui signalent la derja en lettres arabes (absents de l'arabe standard)
MARQUEURS_DERJA_ARABE = {
    "شنوة", "شنية", "شنو", "شنوا", "برشا", "توا", "قداش", "عطيني", "وريني", "ورّيني",
    "كيفاش", "علاش", "وقتاش", "شكون", "متاع", "متع", "فما", "موش", "مش", "زادة",
    "خاطر", "باش", "ياسر", "نحب", "نحبّ", "حرفاء", "حريف", "منتوج", "اللي", "ارسملي",
}

# Mots-outils fréquents pour départager français / anglais
MOTS_FR = {"le", "la", "les", "des", "du", "de", "un", "une", "est", "et", "quel", "quelle",
           "quels", "combien", "moyenne", "affiche", "donne", "moi", "par", "pour", "dans",
           "sur", "mois", "qui", "que", "quoi", "total", "montre", "chiffre", "ventes"}
MOTS_EN = {"the", "what", "which", "is", "are", "of", "and", "show", "give", "me", "how",
           "many", "much", "average", "per", "by", "for", "in", "on", "month", "who",
           "total", "sales", "top", "plot", "chart", "revenue", "customers"}

# Arabizi : chiffre utilisé comme lettre arabe à l'intérieur d'un mot (a3tini, wa7da, 9addech)
_RE_ARABIZI = re.compile(r"[a-z][23579][a-z]|^[23579][a-z]{2,}")
_RE_ARABE = re.compile(r"[؀-ۿ]")
_RE_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_RE_MOTS = re.compile(r"[\w'-]+", re.UNICODE)


@dataclass
class AnalyseLangue:
    """Résultat de l'analyse de la question de l'utilisateur."""
    langue: str              # langue détectée (fr, en, ar, derja_ar, derja_latin)
    langue_reponse: str      # langue dans laquelle le système répondra (fr, en, ar)
    question_pour_llm: str   # question éventuellement traduite par le glossaire
    avertissement: str       # message à afficher avant la réponse ("" si aucun)


def _tokens(texte: str) -> list:
    return [t.lower() for t in _RE_MOTS.findall(texte)]


def detecter_langue(texte: str) -> str:
    """Détecte la langue d'un texte par règles simples (alphabet + mots-outils)."""
    texte = (texte or "").strip()
    if not texte:
        return "fr"

    nb_arabe = len(_RE_ARABE.findall(texte))
    nb_latin = len(_RE_LATIN.findall(texte))

    # --- Lettres arabes majoritaires : arabe standard ou derja ---
    if nb_arabe > nb_latin:
        mots = set(_tokens(texte))
        return "derja_ar" if mots & MARQUEURS_DERJA_ARABE else "ar"

    # --- Lettres latines : derja (arabizi), français ou anglais ---
    mots = _tokens(texte)
    score_derja = sum(1 for m in mots if _RE_ARABIZI.search(m))
    score_derja += sum(1 for m in mots if m in GLOSSAIRE_DERJA_LATIN and m not in ("el", "w", "fi", "win"))
    score_fr = sum(1 for m in mots if m in MOTS_FR)
    score_en = sum(1 for m in mots if m in MOTS_EN)
    if re.search(r"[éèêàùçôî]", texte.lower()):
        score_fr += 2  # les accents sont un indice fort du français

    if score_derja >= 1 and score_derja >= score_en:
        return "derja_latin"
    if score_en > score_fr:
        return "en"
    return "fr"


def _appliquer_glossaire(texte: str, glossaire: dict) -> str:
    """Remplace les mots/expressions derja par leur équivalent (mot entier uniquement)."""
    resultat = texte
    # Les expressions les plus longues d'abord ("elli fet" avant "fet")
    for derja in sorted(glossaire, key=len, reverse=True):
        motif = r"(?<![\w])" + re.escape(derja) + r"(?![\w])"
        resultat = re.sub(motif, glossaire[derja], resultat, flags=re.IGNORECASE)
    return resultat


# Noms propres fréquents écrits en arabe alors que le fichier les contient en lettres latines
# (Phase 7, mesuré : « رقم المعاملات لتونس » ne trouvait pas la colonne « Tunis »).
NOMS_PROPRES_ARABE = {
    "تونس": "Tunis", "صفاقس": "Sfax", "سوسة": "Sousse", "نابل": "Nabeul", "بنزرت": "Bizerte",
    "المنستير": "Monastir", "قابس": "Gabès", "القيروان": "Kairouan", "أريانة": "Ariana", "بن عروس": "Ben Arous",
    "فرنسا": "France", "ألمانيا": "Germany", "إسبانيا": "Spain",
}


def _noms_latins(question: str) -> str:
    trouves = [latin for arabe, latin in NOMS_PROPRES_ARABE.items() if re.search(rf"(?:^|\s|ل|ب|و|في)?{arabe}", question)]
    return f" ({', '.join(trouves)})" if trouves else ""


def analyser_question(question: str) -> AnalyseLangue:
    """
    Détecte la langue, traduit la derja si besoin et choisit la langue de réponse.
    C'est le point d'entrée utilisé par la route /ask_ia.
    """
    langue = detecter_langue(question)
    if langue == "ar":
        return AnalyseLangue(langue=langue, langue_reponse="ar",
                             question_pour_llm=question + _noms_latins(question), avertissement="")

    if langue == "derja_latin":
        traduite = _appliquer_glossaire(question, GLOSSAIRE_DERJA_LATIN)
        return AnalyseLangue(
            langue=langue,
            langue_reponse=DERJA_LATIN_REPONSE,
            question_pour_llm=(f"{traduite}\n(Question originale en derja tunisienne : « {question} »)"),
            avertissement=MESSAGES["avertissement_derja"][DERJA_LATIN_REPONSE],
        )

    if langue == "derja_ar":
        traduite = _appliquer_glossaire(question, GLOSSAIRE_DERJA_ARABE)
        return AnalyseLangue(
            langue=langue,
            langue_reponse=DERJA_ARABE_REPONSE,
            question_pour_llm=f"{traduite}{_noms_latins(question)}\n(السؤال الأصلي بالدارجة التونسية: « {question} »)",
            avertissement=MESSAGES["avertissement_derja"][DERJA_ARABE_REPONSE],
        )

    return AnalyseLangue(langue=langue, langue_reponse=langue,
                         question_pour_llm=question, avertissement="")


# ---------------------------------------------------------------------------
# 2. Consignes de langue injectées dans le prompt système
# ---------------------------------------------------------------------------
CONSIGNE_LANGUE = {
    "fr": "Réponds UNIQUEMENT en français.",
    "en": "Answer ONLY in English.",
    "ar": "أجب باللغة العربية الفصحى فقط. (Réponds uniquement en arabe standard.)",
}


def consigne_langue(langue_reponse: str) -> str:
    return CONSIGNE_LANGUE.get(langue_reponse, CONSIGNE_LANGUE["fr"])


# ---------------------------------------------------------------------------
# 3. Messages de l'application traduits (erreurs, avertissements)
#    Écrits à la main : ils ne dépendent pas du LLM et restent donc fiables,
#    même quand Ollama est arrêté.
# ---------------------------------------------------------------------------
MESSAGES = {
    "ollama_indisponible": {
        "fr": "Le moteur d'IA local (Ollama) ne répond pas. Vérifiez qu'Ollama est lancé "
              "(commande `ollama serve`) puis réessayez.",
        "en": "The local AI engine (Ollama) is not responding. Make sure Ollama is running "
              "(`ollama serve`) and try again.",
        "ar": "محرك الذكاء الاصطناعي المحلي (Ollama) لا يستجيب. تأكد من تشغيل Ollama "
              "(الأمر `ollama serve`) ثم أعد المحاولة.",
    },
    "modele_absent": {
        "fr": "Le modèle d'IA requis n'est pas installé dans Ollama. Exécutez `ollama pull {modele}`.",
        "en": "The required AI model is not installed in Ollama. Run `ollama pull {modele}`.",
        "ar": "نموذج الذكاء الاصطناعي المطلوب غير مثبت في Ollama. نفّذ الأمر `ollama pull {modele}`.",
    },
    "fichier_introuvable": {
        "fr": "Fichier introuvable ou accès non autorisé.",
        "en": "File not found or access denied.",
        "ar": "الملف غير موجود أو غير مسموح بالوصول إليه.",
    },
    "fichier_absent_disque": {
        "fr": "Le fichier « {nom} » est référencé mais n'existe plus sur le serveur. Merci de le réimporter.",
        "en": "The file “{nom}” is registered but no longer exists on the server. Please upload it again.",
        "ar": "الملف «{nom}» مسجّل لكنه لم يعد موجودًا على الخادم. يرجى رفعه من جديد.",
    },
    "erreur_interne": {
        "fr": "Une erreur interne est survenue pendant l'analyse.",
        "en": "An internal error occurred during the analysis.",
        "ar": "حدث خطأ داخلي أثناء التحليل.",
    },
    "avertissement_derja": {
        "fr": "ℹ️ *Réponse en français : le modèle local (3B) ne maîtrise pas la derja, "
              "votre question a été traduite automatiquement.*",
        "en": "ℹ️ *Answer in English: the local 3B model does not handle Tunisian derja reliably.*",
        "ar": "ℹ️ *ملاحظة: تمت الإجابة بالعربية الفصحى لأن النموذج المحلي لا يتقن الدارجة التونسية، "
              "وتمت ترجمة سؤالك تلقائيًا.*",
    },
}


def message(cle: str, langue: str = "fr", **kwargs) -> str:
    """Renvoie un message traduit ; derja -> langue de réponse correspondante."""
    if langue == "derja_latin":
        langue = DERJA_LATIN_REPONSE
    elif langue == "derja_ar":
        langue = DERJA_ARABE_REPONSE
    textes = MESSAGES.get(cle, {})
    texte = textes.get(langue) or textes.get("fr", cle)
    return texte.format(**kwargs) if kwargs else texte

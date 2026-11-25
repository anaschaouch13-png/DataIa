"""
services/redaction.py — Rédaction des réponses à partir des résultats pandas.

Règle d'or : la valeur affichée est TOUJOURS celle calculée par pandas.
  - Une phrase modèle (template) est construite en Python dans la langue de
    l'utilisateur, avec les nombres formatés : elle ne dépend pas du LLM.
  - Si REFORMULATION_LLM=1, le LLM peut reformuler cette phrase plus naturellement,
    MAIS sa phrase est rejetée si elle contient un seul nombre qui n'est pas dans le
    résultat (garde-fou anti-hallucination). On revient alors à la phrase modèle.
  - Une ligne de provenance (« Calculé par pandas : opération, colonne, lignes »)
    est toujours ajoutée : l'utilisateur voit d'où vient le chiffre.
"""

import math
import re
from typing import Iterable, List, Optional

import pandas as pd

from services.semantique import Resolution
from services.stats import PlanStat, ResultatStat

# ---------------------------------------------------------------------------
# Nombres
# ---------------------------------------------------------------------------
def formater_nombre(x, langue: str = "fr") -> str:
    """10700.5 -> « 10 700,5 » (fr) / « 10,700.5 » (en, ar). Entiers sans décimales."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    x = float(x)
    decimales = 0 if abs(x - round(x)) < 1e-9 else 2
    texte = f"{x:,.{decimales}f}"
    if decimales:
        texte = texte.rstrip("0").rstrip(".")
    if langue == "fr":
        texte = texte.replace(",", " ").replace(".", ",")
    return texte


_CHIFFRES_ARABES = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def nombres_du_texte(texte: str) -> List[float]:
    """Extrait les nombres d'un texte (formats fr, en, chiffres arabes-indiens)."""
    texte = texte.translate(_CHIFFRES_ARABES).replace(" ", " ").replace("\xa0", " ")
    nombres = []
    for brut in re.findall(r"\d+(?:[ .,]\d+)*", texte):
        brut = brut.strip()
        candidats = set()
        sans_espace = brut.replace(" ", "")
        if "," in sans_espace and "." in sans_espace:   # séparateur décimal = le dernier
            if sans_espace.rfind(",") > sans_espace.rfind("."):
                candidats.add(sans_espace.replace(".", "").replace(",", "."))
            else:
                candidats.add(sans_espace.replace(",", ""))
        elif "," in sans_espace:
            candidats.add(sans_espace.replace(",", "."))      # 10,7 (décimal fr)
            candidats.add(sans_espace.replace(",", ""))       # 10,700 (milliers en)
        elif "." in sans_espace:
            candidats.add(sans_espace)                        # 10.7
            candidats.add(sans_espace.replace(".", ""))       # 10.700 (milliers)
        else:
            candidats.add(sans_espace)
        for p in brut.split(" "):                             # « 2023 5 » : nombres séparés
            if p:
                candidats.add(p.replace(",", "."))
        valeurs = []
        for c in candidats:
            try:
                valeurs.append(float(c))
            except ValueError:
                pass
        if valeurs:
            nombres.append(valeurs)
    return nombres


def reformulation_valide(texte: str, autorises: Iterable[float]) -> bool:
    """
    Vrai si CHAQUE nombre de `texte` correspond (à l'arrondi près) à un nombre autorisé :
    valeurs du résultat pandas, nombres de la question, ou petits entiers (1 à 12).
    """
    autorises = [float(a) for a in autorises]
    for interpretations in nombres_du_texte(texte):
        ok = False
        for v in interpretations:
            if v.is_integer() and 1 <= v <= 12:
                ok = True        # « 3 produits », « 2 phrases »…
            elif any(abs(v - a) <= max(0.011, abs(a) * 0.005) for a in autorises):
                ok = True        # tolérance d'arrondi : 0,5 % ou 1 centime
            if ok:
                break
        if not ok:
            return False
    return True


# ---------------------------------------------------------------------------
# Textes traduits (écrits à la main : fiables et instantanés)
# ---------------------------------------------------------------------------
NOMS_OPERATIONS = {
    "sum": {"fr": "Total", "en": "Total", "ar": "مجموع"},
    "mean": {"fr": "Moyenne", "en": "Average", "ar": "متوسط"},
    "median": {"fr": "Médiane", "en": "Median", "ar": "وسيط"},
    "min": {"fr": "Minimum", "en": "Minimum", "ar": "أدنى قيمة"},
    "max": {"fr": "Maximum", "en": "Maximum", "ar": "أعلى قيمة"},
    "count": {"fr": "Nombre de lignes", "en": "Number of rows", "ar": "عدد الأسطر"},
}
NOMS_CONCEPTS = {
    "ventes": {"fr": "ventes", "en": "sales", "ar": "المبيعات"},
    "quantite": {"fr": "quantité", "en": "quantity", "ar": "الكمية"},
    "prix": {"fr": "prix", "en": "price", "ar": "السعر"},
}
TEXTES = {
    "de": {"fr": "de", "en": "of", "ar": "لـ"},
    "par": {"fr": "par", "en": "by", "ar": "حسب"},
    "groupes": {"fr": "groupes", "en": "groups", "ar": "مجموعات"},
    "selon": {"fr": "selon", "en": "by", "ar": "حسب"},
    "repartition": {"fr": "Répartition", "en": "Breakdown", "ar": "توزيع"},
    "evolution": {"fr": "Évolution", "en": "Trend", "ar": "تطور"},
    "de_a": {"fr": "de {a} ({pa}) à {b} ({pb})", "en": "from {a} ({pa}) to {b} ({pb})",
             "ar": "من {a} ({pa}) إلى {b} ({pb})"},
    "soit": {"fr": "soit", "en": "i.e.", "ar": "أي"},
    "periodes": {"fr": "périodes", "en": "periods", "ar": "فترات"},
    "ligne_concernee": {"fr": "Ligne concernée", "en": "Matching row", "ar": "السطر المعني"},
    "provenance": {"fr": "Calculé par pandas", "en": "Computed by pandas", "ar": "محسوب بواسطة pandas"},
    "operation": {"fr": "opération", "en": "operation", "ar": "العملية"},
    "colonne": {"fr": "colonne", "en": "column", "ar": "العمود"},
    "lignes_sur": {"fr": "{u} lignes utilisées sur {t}", "en": "{u} rows used out of {t}",
                   "ar": "{u} سطر مستعمل من {t}"},
    "filtres": {"fr": "filtres", "en": "filters", "ar": "المرشحات"},
    "ignorees": {"fr": "{n} valeur(s) vide(s) ou non numérique(s) ignorée(s)",
                 "en": "{n} empty or non-numeric value(s) ignored",
                 "ar": "تم تجاهل {n} قيمة فارغة أو غير رقمية"},
    "concept": {"fr": "« {c} » a été interprété comme la colonne `{col}`.",
                "en": "“{c}” was interpreted as the column `{col}`.",
                "ar": "تم اعتبار «{c}» هو العمود `{col}`."},
    "alternatives": {"fr": "Autres colonnes possibles : {cols}.", "en": "Other possible columns: {cols}.",
                     "ar": "أعمدة أخرى ممكنة: {cols}."},
    "precision_absent": {
        "fr": "Ce fichier ne contient pas de colonne correspondant à « {c} ». "
              "Sur quelle colonne voulez-vous calculer ce {op} ? Voici les options possibles, calculées par pandas :",
        "en": "This file has no column matching “{c}”. Which column should the {op} be computed on? "
              "Here are the possible options, computed by pandas:",
        "ar": "هذا الملف لا يحتوي على عمود يطابق «{c}». على أي عمود تريد حساب {op}؟ "
              "إليك الخيارات الممكنة، محسوبة بواسطة pandas:"},
    "precision_inconnu": {
        "fr": "Je n'ai pas pu déterminer la colonne à utiliser. Précisez-la parmi les colonnes numériques suivantes :",
        "en": "I could not determine which column to use. Please choose one of these numeric columns:",
        "ar": "لم أتمكن من تحديد العمود المطلوب. يرجى اختيار أحد الأعمدة الرقمية التالية:"},
    "precision_groupe": {
        "fr": "Par quelle colonne voulez-vous regrouper le résultat ? Colonnes possibles : {cols}.",
        "en": "Which column should the result be grouped by? Possible columns: {cols}.",
        "ar": "حسب أي عمود تريد تجميع النتيجة؟ الأعمدة الممكنة: {cols}."},
    "precision_date": {
        "fr": "Aucune colonne de dates n'a été trouvée dans ce fichier : impossible de calculer une évolution dans le temps.",
        "en": "No date column was found in this file: a trend over time cannot be computed.",
        "ar": "لم يتم العثور على عمود تواريخ في هذا الملف: لا يمكن حساب التطور عبر الزمن."},
    "precision_operation": {
        "fr": "Je n'ai pas compris le calcul demandé. Exemples : « total de X », « moyenne de X par Y », « top 5 des Y selon X ».",
        "en": "I did not understand the requested calculation. Examples: “total of X”, “average X by Y”, “top 5 Y by X”.",
        "ar": "لم أفهم الحساب المطلوب. أمثلة: «مجموع X»، «متوسط X حسب Y»، «أفضل 5 Y حسب X»."},
    "option": {"fr": "Option", "en": "Option", "ar": "الخيار"},
    "resultat": {"fr": "Résultat", "en": "Result", "ar": "النتيجة"},
    "cliquez": {"fr": "Cliquez sur une suggestion ou reformulez votre question.",
                "en": "Click a suggestion or rephrase your question.",
                "ar": "انقر على أحد الاقتراحات أو أعد صياغة سؤالك."},
    "suggestion_total": {"fr": "Quel est le {op} de {mesure} ?", "en": "What is the {op} of {mesure}?",
                         "ar": "ما هو {op} {mesure}؟"},
    "valeurs_distinctes": {"fr": "Valeurs distinctes de", "en": "Distinct values of", "ar": "القيم المختلفة في"},
    "avec_nombre": {"fr": "avec le nombre de lignes de chacune", "en": "with the number of rows for each",
                    "ar": "مع عدد الأسطر لكل قيمة"},
    "filtres_rejetes": {
        "fr": "Filtre(s) non appliqué(s) car absent(s) de votre question : {f}. Si vous vouliez filtrer, "
              "écrivez la valeur exacte telle qu'elle apparaît dans le fichier.",
        "en": "Filter(s) not applied because not present in your question: {f}. To filter, "
              "write the exact value as it appears in the file.",
        "ar": "مرشح(ات) غير مطبقة لأنها غير موجودة في سؤالك: {f}. للتصفية، اكتب القيمة كما تظهر في الملف."},
    "aucune_ligne": {"fr": "Aucune ligne ne correspond aux filtres ({f}).",
                     "en": "No row matches the filters ({f}).", "ar": "لا يوجد سطر يطابق المرشحات ({f})."},
}


# En-têtes produits par services/stats.py (en français) traduits pour l'affichage
ENTETES = {
    "en": {"nombre": "count", "pourcentage": "percentage", "période": "period"},
    "ar": {"nombre": "العدد", "pourcentage": "النسبة", "période": "الفترة"},
}


def t(cle: str, langue: str, **kwargs) -> str:
    textes = TEXTES[cle]
    texte = textes.get(langue, textes["fr"])
    return texte.format(**kwargs) if kwargs else texte


def nom_operation(op: str, langue: str) -> str:
    return NOMS_OPERATIONS.get(op, {}).get(langue, op)


# ---------------------------------------------------------------------------
# Tableaux et phrases
# ---------------------------------------------------------------------------
def tableau_markdown(df: Optional[pd.DataFrame], langue: str) -> str:
    """DataFrame -> tableau Markdown avec nombres formatés selon la langue."""
    if df is None or df.empty:
        return ""
    traduction = ENTETES.get(langue, {})
    entetes = [traduction.get(str(c), str(c)) for c in df.columns]
    lignes = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    for _, ligne in df.iterrows():
        cellules = []
        for c in df.columns:
            v = ligne[c]
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                txt = formater_nombre(v, langue)
                cellules.append(txt + (" %" if c == "pourcentage" else ""))
            else:
                cellules.append(str(v).replace("|", "/"))
        lignes.append("| " + " | ".join(cellules) + " |")
    return "\n".join(lignes)


def phrase_modele(res: ResultatStat, plan: PlanStat, langue: str) -> str:
    """Phrase factuelle construite en Python (aucun LLM) avec la valeur pandas."""
    mesure = f"`{res.mesure}`"
    op = plan.operation
    fmt = lambda x: formater_nombre(x, langue)

    if op in ("sum", "mean", "median", "min", "max"):
        return f"**{nom_operation(op, langue)} {t('de', langue)} {mesure}** : **{fmt(res.valeur)}**"
    if op == "count" and plan.liste:
        return (f"**{t('valeurs_distinctes', langue)} `{plan.colonne_groupe}`** : "
                f"**{res.details.get('nb_groupes', 0)}** ({t('avec_nombre', langue)}) :")
    if op == "count":
        base = f"**{nom_operation('count', langue)}** : **{fmt(res.valeur)}**"
        if plan.colonne_groupe:
            base += f" ({t('par', langue)} `{plan.colonne_groupe}`)"
        return base
    if op == "groupby":
        return (f"**{nom_operation(plan.agregation, langue)} {t('de', langue)} {mesure} {t('par', langue)} "
                f"`{plan.colonne_groupe}`** ({res.details.get('nb_groupes', 0)} {t('groupes', langue)}) :")
    if op == "top":
        cible = f"`{plan.colonne_groupe}`" if plan.colonne_groupe else ""
        return (f"**Top {plan.n} {cible} {t('selon', langue)} {nom_operation(plan.agregation, langue).lower()} "
                f"{t('de', langue)} {mesure}** :")
    if op == "percentage":
        return (f"**{t('repartition', langue)} {t('de', langue)} {mesure} {t('par', langue)} `{plan.colonne_groupe}`** "
                f"({nom_operation('sum', langue)} : **{fmt(res.valeur)}**) :")
    if op == "trend":
        d = res.details
        phrase = (f"**{t('evolution', langue)} {t('de', langue)} {mesure} ({plan.periode})** : "
                  + t("de_a", langue, a=f"**{fmt(d['premiere_valeur'])}**", pa=d["premiere_periode"],
                      b=f"**{fmt(d['derniere_valeur'])}**", pb=d["derniere_periode"]))
        if "variation_pct" in d:
            signe = "+" if d["variation_pct"] >= 0 else ""
            phrase += f", {t('soit', langue)} **{signe}{fmt(round(d['variation_pct'], 1))} %**"
        return phrase + f" ({d['nb_periodes']} {t('periodes', langue)})."
    return ""


def ligne_provenance(res: ResultatStat, plan: PlanStat, resolution: Optional[Resolution], langue: str) -> str:
    """« 🔢 Calculé par pandas — opération : sum · colonne : Total_Price · 1000 lignes… »"""
    morceaux = [f"{t('operation', langue)} : `{plan.operation}`"]
    if res.mesure != "lignes":
        morceaux.append(f"{t('colonne', langue)} : `{res.mesure}`")
    morceaux.append(t("lignes_sur", langue, u=formater_nombre(res.nb_lignes_utilisees, langue),
                      t=formater_nombre(res.nb_lignes_total, langue)))
    if plan.filtres:
        morceaux.append(f"{t('filtres', langue)} : " + ", ".join(f"`{f.colonne} {f.operateur} {f.valeur}`"
                                                                for f in plan.filtres))
    if res.nb_valeurs_ignorees:
        morceaux.append(t("ignorees", langue, n=res.nb_valeurs_ignorees))
    texte = f"> 🔢 *{t('provenance', langue)} — " + " · ".join(morceaux) + "*"
    if resolution and resolution.note == "concept":
        nom_c = NOMS_CONCEPTS[resolution.concept].get(langue, resolution.concept)
        texte += "\n>\n> ℹ️ " + t("concept", langue, c=nom_c, col=resolution.colonne)
        if resolution.alternatives:
            texte += " " + t("alternatives", langue, cols=", ".join(f"`{c}`" for c in resolution.alternatives))
    return texte


def message_precision_colonne(resolution: Resolution, plan: PlanStat, options_calculees: List[dict],
                              langue: str) -> tuple:
    """
    Message « quelle colonne ? » avec, pour chaque option, la valeur calculée par pandas,
    et la liste des questions suggérées (cliquables).
    """
    op_nom = nom_operation(plan.operation, langue).lower()
    if resolution.note == "absent":
        nom_c = NOMS_CONCEPTS.get(resolution.concept, {}).get(langue, resolution.concept)
        intro = t("precision_absent", langue, c=nom_c, op=op_nom)
    else:
        intro = t("precision_inconnu", langue)
    lignes = [f"| {t('option', langue)} | {t('resultat', langue)} ({nom_operation(plan.operation, langue)}) |", "|---|---|"]
    suggestions = []
    for o in options_calculees:
        lignes.append(f"| `{o['mesure']}` | {formater_nombre(o['valeur'], langue) if o['valeur'] is not None else '-'} |")
        suggestions.append(t("suggestion_total", langue, op=op_nom, mesure=o["mesure"]))
    texte = intro + "\n\n" + "\n".join(lignes) + "\n\n" + t("cliquez", langue)
    return texte, suggestions

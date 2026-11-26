"""
services/pdf_export.py — Rapport PDF complet d'une analyse (Phase 8).

Contenu (pour un fichier analysé par l'utilisateur) :
  1. page de titre : titre, fichier, date, utilisateur, domaine ;
  2. sommaire (numéros de page) ;
  3. informations du fichier : format, taille, colonnes et types, remarques du parser ;
  4. questions et réponses (avec les tableaux de résultats calculés par pandas) ;
  5. tous les graphiques générés (PNG enregistrés en Phase 4, régénérés si absents) ;
  6. résultats des modèles ML (métriques, paramètres, données nettoyées) ;
  7. simulations what-if ;
  8. pied de page « Page X / N ».

Arabe : police Arial du système (contient les lettres arabes et leurs formes liées) +
arabic-reshaper (choisit la forme de chaque lettre : initiale, médiane, finale, isolée)
+ python-bidi (remet le texte de droite à gauche pour l'affichage). Sans ces deux
étapes, fpdf2 écrit les lettres isolées et dans le mauvais sens.
"""

import datetime
import json
import logging
import os
import re
from typing import List, Optional

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

import config
from services.db import get_db_connection
from services.fichiers import chemin_absolu

log = logging.getLogger("dataia.pdf")
_RE_ARABE = re.compile(r"[؀-ۿ]")
# Emojis des réponses du chat -> texte (la police ne contient pas d'emojis)
EMOJIS = {"🔢": "", "ℹ️": "Info :", "ℹ": "Info :", "⚠️": "Attention :", "⚠": "Attention :", "📊": "", "📈": "",
          "🔎": "", "👥": "", "📥": "", "🧹": "", "✅": "(retenu)", "❌": "", "️": ""}
COULEUR = (8, 145, 178)
# Raison du type de graphique (services/charts.py) en phrase lisible
RAISONS = {"demande": "type demandé par l'utilisateur",
           "remplacement": "type demandé inadapté aux données, remplacé par un type adapté",
           "auto_line": "automatique — date + nombre -> courbe", "auto_bar": "automatique — catégorie + nombre -> barres",
           "auto_pie": "automatique — 6 catégories ou moins -> camembert",
           "auto_bar_groupe": "automatique — deux catégories -> barres groupées",
           "auto_scatter": "automatique — deux nombres -> nuage de points",
           "auto_histogram": "automatique — un seul nombre -> histogramme",
           "auto_heatmap": "automatique — trois nombres ou plus -> carte de chaleur"}


def texte_pdf(texte) -> str:
    """Prépare un texte pour fpdf2 : emojis retirés, arabe mis en forme et réordonné."""
    texte = "" if texte is None else str(texte)
    for e, r in EMOJIS.items():
        texte = texte.replace(e, r)
    texte = re.sub(r"[\U00010000-\U0010FFFF]", "", texte)            # autres caractères hors police
    if _RE_ARABE.search(texte):
        return "\n".join(get_display(arabic_reshaper.reshape(l)) for l in texte.split("\n"))
    return texte


class RapportPDF(FPDF):
    def __init__(self, titre: str):
        super().__init__(format="A4")
        self.titre_rapport = titre
        self.set_auto_page_break(True, margin=18)
        self.add_font("Arial", "", config.PDF_POLICE)
        self.add_font("Arial", "B", config.PDF_POLICE_GRAS)
        self.add_font("Arial", "I", config.PDF_POLICE_ITALIQUE)
        self.set_font("Arial", size=10)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("Arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, texte_pdf(f"{self.titre_rapport} — Page {self.page_no()} / {{nb}}"), align="C")
        self.set_text_color(0, 0, 0)

    # ---------- blocs ----------
    def titre_section(self, texte: str, niveau: int = 0):
        if niveau == 0 and self.get_y() > 60:
            self.add_page()
        self.start_section(texte_pdf(texte), level=niveau)
        self.set_font("Arial", "B", 15 if niveau == 0 else 11)
        self.set_text_color(*COULEUR)
        self.multi_cell(0, 8 if niveau == 0 else 6, texte_pdf(texte), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)
        self.set_font("Arial", size=10)
        self.ln(1)

    def paragraphe(self, texte: str, taille: int = 10, style: str = ""):
        arabe = bool(_RE_ARABE.search(texte or ""))
        if arabe and "I" in style:
            style = style.replace("I", "")   # Arial Italique ne contient pas les lettres arabes
        if arabe:                            # le Markdown de fpdf2 n'est pas appliqué au texte arabe
            texte = texte.replace("**", "").replace("__", "")
        self.set_font("Arial", style, taille)
        self.multi_cell(0, 5.5, texte_pdf(texte), markdown=not arabe, align="R" if arabe else "L",
                        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Arial", size=10)

    def tableau(self, lignes: List[List[str]], entete: bool = True, taille: int = 8):
        if not lignes:
            return
        nb = max(len(l) for l in lignes)
        lignes = [list(l) + [""] * (nb - len(l)) for l in lignes][:40]
        self.set_font("Arial", size=taille)
        style = FontFace(emphasis="BOLD", fill_color=(241, 245, 249))
        with self.table(first_row_as_headings=entete, text_align="LEFT", line_height=4.6,
                        headings_style=style) as t:
            for l in lignes:
                r = t.row()
                for c in l:
                    r.cell(texte_pdf(str(c))[:80])
        self.set_font("Arial", size=10)
        self.ln(2)

    def markdown(self, texte: str):
        """Réponse du chat (Markdown simple) : paragraphes, citations, tableaux, détails du nettoyage."""
        texte = re.sub(r"</?details>|</?summary>", "\n", texte or "")
        texte = re.sub(r"\[([^\]]+)\]\(/telecharger[^)]*\)", r"\1", texte)            # liens -> texte
        bloc_tableau: List[List[str]] = []

        def vider():
            if bloc_tableau:
                self.tableau(bloc_tableau)
                bloc_tableau.clear()
        for ligne in texte.split("\n"):
            l = ligne.strip()
            if l.startswith("|") and l.endswith("|"):
                if re.fullmatch(r"\|[\s\-:|]+\|", l):
                    continue                                                         # |---|---|
                bloc_tableau.append([c.strip().replace("`", "") for c in l.strip("|").split("|")])
                continue
            vider()
            if not l or l == ">":
                continue
            if l.startswith(">"):
                self.set_text_color(90, 90, 90)
                self.paragraphe(l.lstrip("> ").replace("`", "").replace("*", ""), 8, "I")
                self.set_text_color(0, 0, 0)
            elif l.startswith("- "):
                self.paragraphe("• " + l[2:].replace("`", ""), 9)
            else:
                self.paragraphe(l.replace("`", "").replace("*** ", "** "), 10)
        vider()


def _requete(sql, params=()):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    lignes = cur.fetchall()
    cur.close()
    conn.close()
    return lignes


def _png(graphique: dict) -> Optional[str]:
    """PNG du graphique ; régénéré depuis le JSON s'il manque (export en arrière-plan non terminé)."""
    if graphique.get("chemin_png") and os.path.isfile(chemin_absolu(graphique["chemin_png"])):
        return chemin_absolu(graphique["chemin_png"])
    chemin_json = chemin_absolu(graphique["chemin_json"])
    if not os.path.isfile(chemin_json):
        return None
    from services.charts import exporter_png
    chemin_png = os.path.splitext(chemin_json)[0] + ".png"
    with open(chemin_json, encoding="utf-8") as f:
        exporter_png(json.load(f), chemin_png)
    return chemin_png


def generer_rapport(id_utilisateur: int, id_fichier: int) -> dict:
    """Construit le PDF, l'enregistre (dossier des rapports + table `rapports`) et renvoie ses infos."""
    utilisateur = _requete("SELECT nom_utilisateur, email, domaine FROM utilisateurs WHERE id_utilisateur = %s",
                           (id_utilisateur,))[0]
    fichier = _requete("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s",
                       (id_fichier, id_utilisateur))
    if not fichier:
        raise ValueError("Fichier introuvable.")
    fichier = fichier[0]
    questions = _requete("SELECT id_question, question_texte, reponse_texte, date_question FROM questions "
                         "WHERE id_fichier = %s AND id_utilisateur = %s ORDER BY date_question", (id_fichier, id_utilisateur))
    graphiques = _requete("SELECT * FROM graphiques WHERE id_fichier = %s AND id_utilisateur = %s ORDER BY id_graphique",
                          (id_fichier, id_utilisateur))
    modeles = _requete("SELECT * FROM modeles_ml WHERE id_fichier = %s AND id_utilisateur = %s ORDER BY id_modele",
                       (id_fichier, id_utilisateur))
    simulations = [s for s in _requete("SELECT * FROM simulations WHERE id_utilisateur = %s ORDER BY id_simulation DESC "
                                       "LIMIT 50", (id_utilisateur,))
                   if json.loads(s["entrees_json"]).get("file_id") in (id_fichier, None)][:15]

    maintenant = datetime.datetime.now()
    pdf = RapportPDF(f"Rapport DataIA — {fichier['nom_fichier']}")
    pdf.alias_nb_pages()

    # ---------- 1. Page de titre ----------
    pdf.add_page()
    logo = os.path.join(config.BASE_DIR, "static", "logo.png")
    if os.path.isfile(logo):
        pdf.image(logo, x=85, y=30, w=40)
    pdf.set_y(85)
    pdf.set_font("Arial", "B", 24)
    pdf.set_text_color(*COULEUR)
    pdf.multi_cell(0, 12, "Rapport d'analyse DataIA", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 13)
    pdf.ln(4)
    for ligne in (f"Fichier analysé : {fichier['nom_fichier']}",
                  f"Date du rapport : {maintenant:%d/%m/%Y à %H:%M}",
                  f"Utilisateur : {utilisateur['nom_utilisateur']}",
                  f"Domaine d'activité : {utilisateur['domaine']}"):
        pdf.multi_cell(0, 8, texte_pdf(ligne), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "Les chiffres de ce rapport sont calculés par pandas et par les modèles de Machine Learning "
                         "de la plateforme ; l'IA locale (Ollama) sert à comprendre les questions et à rédiger.",
                   align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # ---------- 2. Sommaire ----------
    pdf.add_page()
    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(*COULEUR)
    pdf.cell(0, 10, "Sommaire", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    def sommaire(p, sections):
        p.set_font("Arial", size=10)
        for s in sections:
            p.set_x(p.l_margin + 6 * s.level)
            p.cell(150 - 6 * s.level, 7, s.name, new_x=XPos.RIGHT, new_y=YPos.TOP)
            p.cell(0, 7, str(s.page_number), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.insert_toc_placeholder(sommaire, pages=1)

    # ---------- 3. Informations du fichier ----------
    pdf.titre_section("1. Informations du fichier")
    infos = [["Nom", fichier["nom_fichier"]], ["Format", fichier["type_fichier"]],
             ["Importé le", f"{fichier['date_upload']:%d/%m/%Y %H:%M}" if fichier.get("date_upload") else "-"]]
    chemin = chemin_absolu(fichier["chemin_fichier"])
    if os.path.isfile(chemin):
        from services.apercu import _type
        from services.parsers import analyser_fichier
        doc = analyser_fichier(chemin)
        df = doc.principal
        infos += [["Contenu", doc.source], ["Lignes × colonnes", f"{len(df)} × {df.shape[1]}"]]
        pdf.tableau([["Élément", "Valeur"]] + infos)
        pdf.titre_section("Colonnes détectées", 1)
        pdf.tableau([["Colonne", "Type"]] + [[str(c), _type(df, c)] for c in df.columns])
        for r in doc.remarques:
            pdf.paragraphe(f"• {r}", 9)
    else:
        pdf.tableau([["Élément", "Valeur"]] + infos)
        pdf.paragraphe("Le fichier n'est plus présent sur le serveur.", 9, "I")

    # ---------- 4. Questions et réponses ----------
    pdf.titre_section(f"2. Questions et réponses ({len(questions)})")
    if not questions:
        pdf.paragraphe("Aucune question posée sur ce fichier.", 9, "I")
    for i, q in enumerate(questions, 1):
        from services.charts import nettoyer_ancien_format
        reponse, ancien = nettoyer_ancien_format(q["reponse_texte"] or "")
        pdf.set_fill_color(236, 254, 255)
        pdf.set_font("Arial", "B", 10)
        pdf.multi_cell(0, 6, texte_pdf(f"Q{i}. {q['question_texte']}"), fill=True,
                       align="R" if _RE_ARABE.search(q["question_texte"]) else "L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Arial", size=10)
        pdf.markdown(reponse)
        if ancien:
            pdf.paragraphe("(Graphique de l'ancienne version non repris : ses valeurs n'étaient pas calculées.)", 8, "I")
        pdf.ln(3)

    # ---------- 5. Graphiques ----------
    pdf.titre_section(f"3. Graphiques ({len(graphiques)})")
    if not graphiques:
        pdf.paragraphe("Aucun graphique n'a été demandé pour ce fichier.", 9, "I")
    for g in graphiques:
        try:
            png = _png(g)
        except Exception as e:
            log.warning("PNG impossible pour le graphique %s : %s", g["id_graphique"], e)
            png = None
        spec = json.loads(g["spec_json"]) if g.get("spec_json") else {}
        if pdf.get_y() > 170:                # titre et image sur la même page
            pdf.add_page()
        pdf.titre_section(f"{g['titre']} — {g['type_graphique']}", 1)
        if png:
            pdf.image(png, w=175)
        raison = RAISONS.get(spec.get("raison", ""), "")
        if raison:
            pdf.paragraphe(f"Choix du type : {raison}" + (f" (type demandé : {spec['type_demande']})"
                                                           if spec.get("type_demande") else ""), 8, "I")
        pdf.ln(2)

    # ---------- 6. Modèles ML ----------
    pdf.titre_section(f"4. Modèles de Machine Learning ({len(modeles)})")
    if not modeles:
        pdf.paragraphe("Aucun modèle n'a été exécuté sur ce fichier.", 9, "I")
    noms = {"prevision": "Prévision du chiffre d'affaires", "anomalie": "Détection d'anomalies", "churn": "Churn bancaire"}
    for m in modeles:
        params = json.loads(m["parametres_json"] or "{}")
        pdf.titre_section(f"{noms.get(m['type'], m['type'])} — {m['algorithme']} ({m['date_execution']:%d/%m/%Y %H:%M})", 1)
        lignes = [["Métrique", "Valeur"]]
        for cle, valeur in (params.get("metriques") or {}).items():
            lignes.append([cle, f"{valeur:.4g}" if isinstance(valeur, float) else str(valeur)])
        pdf.tableau(lignes)
        if m["type"] == "prevision" and params.get("comparaison"):
            pdf.paragraphe("Comparaison des modèles sur la période de test :", 9, "B")
            pdf.tableau([["Modèle", "MAPE %", "sMAPE %", "MAE", "RMSE"]] +
                        [[c["modele"], f"{c['mape']:.2f}", f"{c['smape']:.2f}", f"{c['mae']:.0f}", f"{c['rmse']:.0f}"]
                         for c in params["comparaison"]])
            pdf.paragraphe(f"Colonne prévue : {params.get('colonne_cible')} ; fréquence : {params.get('frequence')} ; "
                           f"{params.get('nb_periodes')} périodes, dont {params.get('nb_test')} de test.", 9)
        if m["type"] == "anomalie":
            pdf.paragraphe(f"Colonnes analysées : {', '.join(params.get('colonnes', []))} ; seuil automatique "
                           f"{params.get('seuil', 0):.4f}.", 9)
        if m["type"] == "churn":
            mt = params.get("metriques_test", {})
            pdf.paragraphe(f"{params.get('nb_risque')} client(s) à risque sur {params.get('nb_clients')}. Modèle évalué sur "
                           f"un jeu de test : rappel {mt.get('rappel', 0):.1%}, précision {mt.get('precision', 0):.1%}, "
                           f"F1 {mt.get('f1', 0):.3f}, AUC {mt.get('roc_auc', 0):.3f}.", 9)
        if m.get("chemin_donnees_nettoyees"):
            pdf.paragraphe(f"Données nettoyées : {os.path.basename(m['chemin_donnees_nettoyees'])} (CSV, Excel, rapport de "
                           "nettoyage, téléchargeables dans « Mes données nettoyées »).", 8, "I")

    # ---------- 7. Simulations ----------
    pdf.titre_section(f"5. Simulations what-if ({len(simulations)})")
    if not simulations:
        pdf.paragraphe("Aucune simulation enregistrée pour ce fichier.", 9, "I")
    for s in simulations:
        entrees = {k: v for k, v in json.loads(s["entrees_json"]).items() if k != "file_id"}
        resultat = json.loads(s["resultat_json"])
        resume = resultat.get("prediction") or resultat.get("verdict") or \
            (f"{resultat.get('valeur_prevue')} ({resultat.get('modele')}, précision {resultat.get('precision')} %)"
             if "valeur_prevue" in resultat else "")
        if "pourcentage" in resultat:
            resume += f" — probabilité de départ {resultat['pourcentage']} %"
        if "score" in resultat:
            resume += f" — score {resultat['score']}"
        pdf.paragraphe(f"**{s['type_modele']}** ({s['date_simulation']:%d/%m/%Y %H:%M}) : {resume}", 9)
        pdf.paragraphe("Entrées : " + ", ".join(f"{k} = {v}" for k, v in entrees.items()), 8, "I")

    # ---------- Enregistrement ----------
    nom = f"Rapport_U{id_utilisateur}_F{id_fichier}_{maintenant:%Y%m%d_%H%M%S}.pdf"
    chemin_pdf = os.path.join(config.REPORT_FOLDER, nom)
    pdf.output(chemin_pdf)
    premier_png = next((g.get("chemin_png") for g in graphiques if g.get("chemin_png")), None)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO rapports (id_question, rapport_texte, chemin_graphique, type_graphique, chemin_resume) "
                "VALUES (%s, %s, %s, %s, %s)",
                (questions[-1]["id_question"] if questions else None,
                 f"Rapport complet : {len(questions)} question(s), {len(graphiques)} graphique(s), "
                 f"{len(modeles)} modèle(s), {len(simulations)} simulation(s) — {fichier['nom_fichier']}",
                 premier_png, graphiques[0]["type_graphique"] if graphiques else None,
                 os.path.relpath(chemin_pdf, config.BASE_DIR)))
    conn.commit()
    cur.close()
    conn.close()
    return {"chemin": chemin_pdf, "nom": nom, "pages": pdf.page_no(), "questions": len(questions),
            "graphiques": len(graphiques), "modeles": len(modeles), "simulations": len(simulations)}

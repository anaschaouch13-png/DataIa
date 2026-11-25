import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def create_report():
    doc = Document()

    # Définition des marges (2 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Couleurs du thème
    PRIMARY = RGBColor(27, 54, 93)     # Bleu nuit / Navy
    SECONDARY = RGBColor(0, 150, 166)  # Turquoise / Cyan
    DARK_TEXT = RGBColor(40, 40, 40)
    GRAY_TEXT = RGBColor(100, 100, 100)

    # 1. En-tête / Titre du document
    p_badge = doc.add_paragraph()
    r_badge = p_badge.add_run("PROJET DATAIA  |  RAPPORT TECHNIQUE D'INGÉNIERIE IA")
    r_badge.font.name = "Arial"
    r_badge.font.size = Pt(9)
    r_badge.font.bold = True
    r_badge.font.color.rgb = SECONDARY
    p_badge.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_title = doc.add_paragraph()
    r_title = p_title.add_run("Migration RAG : De l'API Mistral vers Ollama Local (Qwen 2.5)")
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = PRIMARY
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_after = Pt(4)

    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run("Rapport complet des transformations architecturales, configuration des dépendances et optimisation du pipeline RAG")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(11)
    r_sub.font.italic = True
    r_sub.font.color.rgb = GRAY_TEXT
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(24)

    # Ligne de séparation
    p_sep = doc.add_paragraph()
    p_sep_run = p_sep.add_run("_________________________________________________________________________________")
    p_sep_run.font.color.rgb = SECONDARY
    p_sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sep.paragraph_format.space_after = Pt(20)

    # 2. Section Contexte et Dernier Prompt Utilisateur
    h1 = doc.add_heading(level=1)
    h1_run = h1.add_run("1. Contexte et Demande de l'Utilisateur")
    h1_run.font.name = "Calibri"
    h1_run.font.color.rgb = PRIMARY
    h1_run.font.bold = True

    p_desc = doc.add_paragraph("Ce rapport documente la réponse et les actions techniques menées suite au prompt suivant formulé par l'utilisateur :")
    p_desc.paragraph_format.space_after = Pt(8)

    # Boîte Callout pour le Prompt
    tbl_prompt = doc.add_table(rows=1, cols=1)
    tbl_prompt.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_p = tbl_prompt.cell(0, 0)
    set_cell_background(cell_p, "F0F4F8")
    set_cell_margins(cell_p, top=140, bottom=140, left=200, right=200)
    
    p_box = cell_p.paragraphs[0]
    r_box_title = p_box.add_run("Dernier prompt reçu :\n")
    r_box_title.font.bold = True
    r_box_title.font.color.rgb = PRIMARY
    r_box_txt = p_box.add_run("« quels sont les changements que tu as apporté sur le fichier requirements.txt après l'intégration du ai local ?? et qu'est tu as vraiement changé pour faire la transformation de l'api mistral vers l'utilisation de l'ai local qwen 2.5 de ollama ? »")
    r_box_txt.font.italic = True
    r_box_txt.font.color.rgb = DARK_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # 3. Section Changements apportés à requirements.txt
    h2 = doc.add_heading(level=1)
    h2_run = h2.add_run("2. Modifications apportées à requirements.txt")
    h2_run.font.name = "Calibri"
    h2_run.font.color.rgb = PRIMARY
    h2_run.font.bold = True

    p_req = doc.add_paragraph(
        "Dans le cadre de l'autonomisation du projet, les dépendances externes ont été assainies afin de supprimer tout intermédiaire tiers propriétaire et d'installer les connecteurs vers l'infrastructure locale Ollama :"
    )

    # Tableau des dépendances
    tbl_req = doc.add_table(rows=4, cols=4)
    tbl_req.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Package", "Version", "Action", "Raison / Rôle technique"]
    for i, h in enumerate(headers):
        cell = tbl_req.cell(0, i)
        cell.paragraphs[0].add_run(h).font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)

    rows_data = [
        ("mistralai", "2.4.5", "SUPPRIMÉ", "Suppression de la dépendance à l'API Cloud propriétaire Mistral."),
        ("ollama", ">=0.3.0", "AJOUTÉ", "Bibliothèque client officielle pour interagir avec le serveur local Ollama."),
        ("openai", ">=1.0.0", "AJOUTÉ", "Client OpenAI-compatible permettant d'attaquer l'endpoint http://localhost:11434/v1."),
    ]

    for row_idx, r_data in enumerate(rows_data, start=1):
        for col_idx, text in enumerate(r_data):
            cell = tbl_req.cell(row_idx, col_idx)
            run = cell.paragraphs[0].add_run(text)
            if col_idx == 2:
                run.font.bold = True
                if text == "SUPPRIMÉ":
                    run.font.color.rgb = RGBColor(180, 40, 40)
                else:
                    run.font.color.rgb = RGBColor(20, 140, 40)
            set_cell_background(cell, "FFFFFF" if row_idx % 2 == 1 else "F9FBFD")
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # 4. Section Détail de la Transformation Technique (Mistral -> Ollama)
    h3 = doc.add_heading(level=1)
    h3_run = h3.add_run("3. Détail de la Transformation Mistral ➔ Ollama Local")
    h3_run.font.name = "Calibri"
    h3_run.font.color.rgb = PRIMARY
    h3_run.font.bold = True

    p_intro_trans = doc.add_paragraph(
        "La migration a été menée sur l'ensemble de la chaîne de traitement (Ingestion, Indexation, Vectorisation, Prompt Engineering et Génération) :"
    )

    # Sous-sections techniques
    sections_tech = [
        ("A. Suppression de la dépendance API Cloud & Sécurisation", [
            "Retrait de la clé secrète codée en dur dans le code (MISTRAL_API_KEY).",
            "Suppression de l'endpoint distant https://api.mistral.ai/v1/chat/completions.",
            "Toutes les données de l'entreprise restent désormais confinées sur la machine locale sans aucune fuite vers l'extérieur."
        ]),
        ("B. Intégration du Modèle de Génération Local (Qwen 2.5)", [
            "Implémentation de l'endpoint compatible OpenAI http://localhost:11434/v1/chat/completions avec fallback sur /api/chat.",
            "Modèle déployé : qwen2.5:3b (optimisé pour la rapidité et faible empreinte mémoire VRAM).",
            "Possibilité d'évoluer vers qwen2.5:7b ou mistral:7b par simple modification du fichier .env."
        ]),
        ("C. Refonte Complète du Moteur d'Embeddings (nomic-embed-text)", [
            "Remplacement de l'ancien modèle HuggingFace all-MiniLM-L6-v2 (dimension 384).",
            "Adoption de nomic-embed-text sous Ollama générant des représentations vectorielles de dimension 768.",
            "Implémentation stricte des préfixes asymétriques exigés par Nomic :",
            "   • 'search_document: ' injecté avant chaque ligne/enregistrement indexé.",
            "   • 'search_query: ' injecté avant la question posée par l'utilisateur."
        ]),
        ("D. Mise en Cache & Gestion du Vector Store FAISS", [
            "Avant la migration : l'index vectoriel était recalculé intégralement à chaque requête utilisateur, provoquant des lenteurs critiques.",
            "Après la migration : les index FAISS sont sauvegardés et persistés sur disque dans uploads/vector_indices/file_<id>.",
            "Détection d'intégrité : vérification automatique de la dimension vectorielle (index.d == 768). Si un ancien index 384 subsiste, il est invalidé et recalculé automatiquement.",
            "Création du script CLI reindex.py permettant de réindexer en masse tous les fichiers du dossier uploads/ ou de la base MySQL."
        ]),
        ("E. Détection Automatique du Format des Fichiers CSV", [
            "Découverte d'un bug bloquant : les fichiers CSV européens/français (séparateur point-virgule ';') étaient interprétés en une seule colonne brute.",
            "Création de la fonction load_dataset() avec détection automatique du délimiteur (',', ';', '\\t') et encodage UTF-8 avec BOM (utf-8-sig).",
            "Les colonnes (ClientID, NomClient, Ville, PaysID, etc.) sont désormais fidèlement extraites et isolées."
        ]),
        ("F. Optimisation du Prompt RAG & Contexte Catégoriel pour Modèle 3B", [
            "Calibrage du nombre d'extraits RAG (top-k ramené de 100 à 8 extraits) pour respecter la fenêtre d'attention d'un modèle 3B.",
            "Génération dynamique d'un aperçu des valeurs catégorielles uniques (liste exhaustive des villes, segments, modes de paiement).",
            "Ajustement des instructions : autorisation formelle de la déduction géographique (Toulouse/Lyon = France, Milan/Turin = Italie, Tunis = Tunisie), résolvant le problème des réponses 'Je ne sais pas'."
        ])
    ]

    for title, points in sections_tech:
        h_sub = doc.add_heading(level=2)
        h_sub_run = h_sub.add_run(title)
        h_sub_run.font.name = "Calibri"
        h_sub_run.font.color.rgb = SECONDARY
        h_sub_run.font.bold = True

        for pt in points:
            p_pt = doc.add_paragraph(pt, style='List Bullet')
            p_pt.paragraph_format.space_after = Pt(2)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # 5. Tableau Comparatif Avant / Après
    h4 = doc.add_heading(level=1)
    h4_run = h4.add_run("4. Synthèse Comparative Avant / Après")
    h4_run.font.name = "Calibri"
    h4_run.font.color.rgb = PRIMARY
    h4_run.font.bold = True

    tbl_comp = doc.add_table(rows=8, cols=3)
    tbl_comp.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers_comp = ["Composant / Caractéristique", "Architecture Initiale (Mistral Cloud)", "Nouvelle Architecture (Ollama Local)"]
    for i, h in enumerate(headers_comp):
        cell = tbl_comp.cell(0, i)
        cell.paragraphs[0].add_run(h).font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=100, bottom=100, left=150, right=150)

    comparisons = [
        ("Fournisseur IA", "Mistral AI (API Cloud propriétaire)", "Ollama (Serveur local open-source)"),
        ("Modèle de Chat", "open-mistral-7b (Distant)", "qwen2.5:3b (Local sur GPU/CPU)"),
        ("Modèle d'Embeddings", "HuggingFace all-MiniLM-L6-v2", "nomic-embed-text (Ollama local)"),
        ("Dimension Vectorielle", "384 dimensions", "768 dimensions (Préfixes search_*)"),
        ("Confidentialité / Réseau", "Requiert Internet, données envoyées au Cloud", "100% Hors-ligne, aucune fuite de données"),
        ("Gestion Vector Store", "Recalcul complet à chaque question", "Persistance sur disque FAISS + Script reindex.py"),
        ("Coût d'exploitation", "Facturation aux tokens consommés", "Totalement gratuit et illimité"),
    ]

    for row_idx, (comp_item, before, after) in enumerate(comparisons, start=1):
        cell_0 = tbl_comp.cell(row_idx, 0)
        cell_0.paragraphs[0].add_run(comp_item).font.bold = True
        set_cell_background(cell_0, "F0F4F8")
        set_cell_margins(cell_0, top=80, bottom=80, left=120, right=120)

        cell_1 = tbl_comp.cell(row_idx, 1)
        cell_1.paragraphs[0].add_run(before)
        set_cell_background(cell_1, "FFFFFF" if row_idx % 2 == 1 else "F9FBFD")
        set_cell_margins(cell_1, top=80, bottom=80, left=120, right=120)

        cell_2 = tbl_comp.cell(row_idx, 2)
        cell_2.paragraphs[0].add_run(after)
        set_cell_background(cell_2, "E8F8F5" if row_idx % 2 == 1 else "DEF5F0")
        set_cell_margins(cell_2, top=80, bottom=80, left=120, right=120)

    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    # 6. Conclusion
    h5 = doc.add_heading(level=1)
    h5_run = h5.add_run("5. Conclusion et Bénéfices Obtenus")
    h5_run.font.name = "Calibri"
    h5_run.font.color.rgb = PRIMARY
    h5_run.font.bold = True

    p_conclusion = doc.add_paragraph(
        "Grâce à cette transformation, la plateforme DataIA est désormais totalement autonome, souveraine et opérationnelle sans dépendance à Internet ni coûts récurrents. "
        "Les données confidentielles de l'entreprise sont traitées localement en quelques secondes, avec un contrôle total sur l'indexation, la dimension vectorielle (768) et les paramètres du modèle."
    )
    p_conclusion.paragraph_format.space_after = Pt(24)

    # Pied de page discret
    p_footer = doc.add_paragraph()
    r_foot = p_footer.add_run("Document généré automatiquement - Projet DataIA (Python / Flask / Ollama / FAISS)")
    r_foot.font.size = Pt(8.5)
    r_foot.font.italic = True
    r_foot.font.color.rgb = GRAY_TEXT
    p_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    output_path = os.path.join(os.getcwd(), "Rapport_Migration_Ollama_DataIA.docx")
    doc.save(output_path)
    print(f"Document Word généré avec succès : {output_path}")
    return output_path

if __name__ == "__main__":
    create_report()

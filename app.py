# ================== 1. Imports ==================
import datetime
import logging
import os
import sys
from functools import wraps

import pandas as pd
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from fpdf import FPDF
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
from services import rag
from services.db import get_db_connection
from services.domaines import DOMAINE_PAR_DEFAUT, DOMAINES, domaine_valide
from services.langue import analyser_question, message
from services.llm import (OllamaIndisponibleError, generer_reponse,
                          verifier_ollama)
from services.parsers import charger_dataframe
from services.prompts import prompt_systeme_rag, prompt_utilisateur_rag

# ================== 2. Config ==================
# Console Windows en cp1252 : sans cela, un print/log contenant de l'arabe
# fait planter la requête (UnicodeEncodeError constaté pendant les tests).
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("dataia")

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY          # lu depuis .env (plus de clé en dur)
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_MB * 1024 * 1024


def chemin_absolu(chemin: str) -> str:
    """Les chemins sont stockés en base relativement au dossier du backend (ex. uploads\\x.csv)."""
    chemin = chemin.replace('\\', os.sep)
    return chemin if os.path.isabs(chemin) else os.path.join(config.BASE_DIR, chemin)


def chemin_relatif(chemin: str) -> str:
    """Chemin à enregistrer en base (relatif au backend : le projet reste déplaçable)."""
    return os.path.relpath(chemin, config.BASE_DIR)


load_dataset = charger_dataframe  # alias conservé pour le code existant


# ================== 3. Login Manager & User Class ==================
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id_user, nom, email, password, role, bloque, domaine=DOMAINE_PAR_DEFAUT):
        self.id = id_user
        self.nom = nom
        self.email = email
        self.password = password
        self.role = role
        self.bloque = bloque
        self.domaine = domaine   # Phase 2 : détermine les modèles ML disponibles (Phase 5)

    @classmethod
    def depuis_ligne(cls, ligne: dict) -> "User":
        """Construit l'utilisateur à partir d'une ligne de la table `utilisateurs`."""
        return cls(ligne['id_utilisateur'], ligne['nom_utilisateur'], ligne['email'],
                   ligne['mot_de_passe'], ligne['role'], ligne['est_bloque'],
                   ligne.get('domaine') or DOMAINE_PAR_DEFAUT)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    # Un compte bloqué par l'admin perd immédiatement sa session (avant : il restait connecté)
    if user_data and not user_data.get('est_bloque'):
        return User.depuis_ligne(user_data)
    return None


@app.after_request
def interdire_cache_pages_connectees(reponse):
    """
    Après déconnexion, le bouton « Précédent » du navigateur ne doit pas réafficher
    une page protégée depuis le cache : les pages vues par un utilisateur connecté
    sont marquées « no-store ».
    """
    if current_user.is_authenticated:
        reponse.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        reponse.headers['Pragma'] = 'no-cache'
    return reponse


@app.context_processor
def injecter_domaines():
    """Rend la liste des domaines disponible dans tous les templates Jinja."""
    return {"DOMAINES": DOMAINES}

# ================== 4. Routes ==================


@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    formulaire = {}
    if request.method == 'POST':
        nom = (request.form.get('nom_utilisateur') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        mot_de_passe = request.form.get('password') or ''
        domaine = request.form.get('domaine') or ''
        formulaire = {'nom_utilisateur': nom, 'email': email, 'domaine': domaine}

        # Validation côté serveur (le <select> HTML peut être contourné)
        if not nom or not email or not mot_de_passe:
            flash("Tous les champs sont obligatoires.", "danger")
        elif not domaine_valide(domaine):
            flash("Veuillez choisir un domaine d'activité dans la liste.", "danger")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe, domaine) "
                               "VALUES (%s, %s, %s, %s)",
                               (nom, email, generate_password_hash(mot_de_passe), domaine))
                conn.commit()
                flash('Compte créé ! Connectez-vous.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                # Avant : le message SQL brut était affiché à l'utilisateur
                if getattr(e, 'errno', None) == 1062:   # ER_DUP_ENTRY : email déjà utilisé
                    flash("Un compte existe déjà avec cet email.", "danger")
                else:
                    log.exception("Erreur à l'inscription")
                    flash("Erreur lors de la création du compte.", "danger")
            finally:
                cursor.close()
                conn.close()
    return render_template('signup.html', formulaire=formulaire)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM utilisateurs WHERE email = %s", ((email or '').strip().lower(),))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()

        # 1. التثبت من صحة الإيميل و كلمة السر
        if user_data and check_password_hash(user_data['mot_de_passe'], password):

            # 2. التثبت إذا كان المستخدم مبلك (est_bloque == 1)
            if user_data.get('est_bloque') == 1:
                flash('Votre compte est bloqué par l\'administrateur.', 'danger')
                return render_template('login.html')

            # 3. صنع الـ Object User (تأكدي أن الكلاس User فيها الـ role و est_bloque)
            user = User.depuis_ligne(user_data)

            session.clear()          # pas de données d'une session précédente
            login_user(user)

            # 4. التوجيه حسب الـ Role (Admin يمشي للـ admin_dashboard والـ User يمشي للـ dashboard العادية)
            if user_data['role'] == 'administrateur':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))

        flash('Email ou mot de passe incorrect', 'danger')

    return render_template('login.html')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # نثبتوا هل المستخدم admin وموش متبلوكي
        if not current_user.is_authenticated or current_user.role != 'administrateur':
            return "Accès interdit : Vous n'êtes pas administrateur", 403
        return f(*args, **kwargs)
    return decorated_function


@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_utilisateur = %s ORDER BY id_fichier DESC LIMIT 5", (current_user.id,))
    fichiers = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as count FROM questions WHERE id_utilisateur = %s", (current_user.id,))
    q_count = cursor.fetchone()['count']
    cursor.close()
    conn.close()
    return render_template('dashboard.html', fichiers=fichiers, questions_count=q_count)


@app.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    """Profil : l'utilisateur peut modifier son nom et son domaine d'activité."""
    if request.method == 'POST':
        nom = (request.form.get('nom_utilisateur') or '').strip()
        domaine = request.form.get('domaine') or ''
        if not nom:
            flash("Le nom d'utilisateur est obligatoire.", "danger")
        elif not domaine_valide(domaine):
            flash("Domaine d'activité invalide.", "danger")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE utilisateurs SET nom_utilisateur = %s, domaine = %s WHERE id_utilisateur = %s",
                           (nom, domaine, current_user.id))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Profil mis à jour.", "success")
            return redirect(url_for('profil'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nom_utilisateur, email, role, domaine, date_inscription "
                   "FROM utilisateurs WHERE id_utilisateur = %s", (current_user.id,))
    infos = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('profil.html', infos=infos)


@app.route('/chat/<int:file_id>')
@login_required
def chat(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s", (file_id, current_user.id))
    fichier = cursor.fetchone()
    cursor.execute(
        "SELECT question_texte, reponse_texte FROM questions WHERE id_fichier = %s ORDER BY date_question ASC", (file_id,))
    historique = cursor.fetchall()
    cursor.close()
    conn.close()
    if not fichier:
        return redirect(url_for('dashboard'))
    return render_template('chat.html', fichier=fichier, historique=historique)

# ================== Route ask_ia (Version Finale Complète) ==================


def resume_categories(df: pd.DataFrame, max_valeurs: int = 35) -> str:
    """Valeurs distinctes des colonnes texte (aide le LLM sur les catégories / villes)."""
    lignes = []
    for c in df.select_dtypes(include=['object', 'string', 'category']).columns:
        uniques = [str(v) for v in df[c].dropna().unique()[:max_valeurs]]
        lignes.append(f"- {c} : {', '.join(uniques)}")
    return "\n".join(lignes) if lignes else "Aucune colonne catégorielle"


@app.route('/ask_ia', methods=['POST'])
@login_required
def ask_ia():
    data = request.get_json(silent=True) or {}
    file_id = data.get('file_id')
    question = (data.get('question') or '').strip()

    # 1. Langue : détection + traduction de la derja (services/langue.py)
    analyse = analyser_question(question)
    langue = analyse.langue_reponse

    if not question:
        return jsonify({"status": "error", "message": "Question vide."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 2. Sécurité : le fichier doit appartenir à l'utilisateur connecté
        #    (avant : n'importe quel id_fichier était accepté -> fuite de données)
        cursor.execute("SELECT * FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s",
                       (file_id, current_user.id))
        fichier = cursor.fetchone()
        if not fichier:
            return jsonify({"status": "error", "message": message("fichier_introuvable", langue)}), 404

        chemin = chemin_absolu(fichier['chemin_fichier'])
        if not os.path.isfile(chemin):
            return jsonify({"status": "error",
                            "message": message("fichier_absent_disque", langue, nom=fichier['nom_fichier'])}), 410

        df = load_dataset(chemin)

        # 3. RAG : recherche des lignes les plus proches de la question
        textes = rag.lignes_en_textes(df)
        index = rag.charger_ou_construire_index(int(file_id), textes)
        extraits = rag.rechercher(index, analyse.question_pour_llm, nb_lignes=len(textes))

        # 4. Génération de la réponse par le LLM local, dans la langue de l'utilisateur
        prompt_user = prompt_utilisateur_rag(
            colonnes=df.columns.tolist(),
            valeurs_categories=resume_categories(df),
            stats=df.describe(include='all').to_string(),
            extraits="\n".join(f"- {e}" for e in extraits),
            question=analyse.question_pour_llm,
            langue_reponse=langue,
        )
        reponse = generer_reponse(prompt_systeme_rag(langue), prompt_user)
        if analyse.avertissement:
            reponse = f"{analyse.avertissement}\n\n{reponse}"

        # 5. Historique : on enregistre la question telle que l'utilisateur l'a écrite
        cursor.execute("INSERT INTO questions (id_utilisateur, id_fichier, question_texte, reponse_texte, date_question) "
                       "VALUES (%s, %s, %s, %s, NOW())",
                       (current_user.id, file_id, question, reponse))
        conn.commit()
        return jsonify({"status": "success", "answer": reponse,
                        "langue": analyse.langue, "langue_reponse": langue})

    except OllamaIndisponibleError as e:
        # Ollama arrêté ou modèle absent : message clair, code 503, pas de crash
        log.warning("Ollama indisponible : %s", e)
        return jsonify({"status": "error", "code": "ollama_indisponible",
                        "message": message(e.cle_message, langue, modele=e.modele)}), 503
    except Exception:
        log.exception("Erreur dans /ask_ia")
        return jsonify({"status": "error", "message": message("erreur_interne", langue)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/sante')
def api_sante():
    """État des services (Ollama + modèles, MySQL) : utile pour le diagnostic et le frontend."""
    etat_ollama = verifier_ollama()
    try:
        conn = get_db_connection()
        conn.close()
        mysql_ok = True
    except Exception:
        mysql_ok = False
    return jsonify({"ollama": etat_ollama["ok"], "modeles_manquants": etat_ollama["manquants"],
                    "mysql": mysql_ok}), (200 if etat_ollama["ok"] and mysql_ok else 503)

# ================== Route export_pdf ==================


@app.route('/export_pdf', methods=['POST'])
@login_required
def export_pdf():
    try:
        # Récupération des données envoyées par le Frontend
        data = request.get_json()
        history = data.get('history', '')
        conseil = data.get('conseil', 'Aucun conseil généré.')

        # Connexion à la base de données pour récupérer l'ID de la dernière question
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # On récupère le dernier id_question de l'utilisateur pour lier le rapport (selon ta structure DB)
        cursor.execute(
            "SELECT id_question FROM questions WHERE id_utilisateur = %s ORDER BY id_question DESC LIMIT 1", (current_user.id,))
        result = cursor.fetchone()
        question_id = result['id_question'] if result else None

        # 1. Configuration et génération du document PDF
        pdf = FPDF()
        pdf.add_page()

        # Titre du rapport
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(0, 15, "Rapport d'Analyse Automatique", ln=True, align='C')
        pdf.ln(5)

        # Fonction interne pour nettoyer le texte et éviter les erreurs d'encodage (Latin-1)
        def clean_text(t):
            return str(t).encode('latin-1', 'ignore').decode('latin-1')

        # Section : Historique des échanges
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Historique des echanges :", ln=True)
        pdf.set_font("helvetica", size=10)
        pdf.multi_cell(0, 8, txt=clean_text(history))

        pdf.ln(10)

        # Section : Conseil Stratégique (avec mise en forme visuelle)
        pdf.set_fill_color(230, 240, 250)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 10, "Conseil Strategique :", ln=True, fill=True)
        pdf.set_font("helvetica", "I", 11)
        pdf.multi_cell(0, 10, txt=clean_text(conseil), border=1)

        # 2. Gestion du stockage physique sur le serveur (dossier défini dans config.py)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Rapport_U{current_user.id}_{timestamp}.pdf"
        report_path = os.path.join(config.REPORT_FOLDER, filename)
        pdf.output(report_path)

        # 3. Enregistrement des métadonnées dans la table 'rapports' (selon ton image)
        # Colonnes cibles : id_question, rapport_texte, chemin_resume, date_generation
        query = """
            INSERT INTO rapports 
            (id_question, rapport_texte, chemin_resume, date_generation) 
            VALUES (%s, %s, %s, NOW())
        """
        # On insère un extrait du texte et le chemin physique du fichier
        cursor.execute(query, (question_id, clean_text(history[:500]), chemin_relatif(report_path)))

        conn.commit()
        cursor.close()
        conn.close()

        # 4. Envoi du fichier généré au navigateur pour téléchargement
        return send_file(report_path, as_attachment=True, download_name="Rapport_DataIA.pdf")

    except Exception as e:
        # En cas d'erreur, on affiche le log dans la console et on renvoie un JSON d'erreur
        print(f"DEBUG EXPORT PDF: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ================== Mes Fichiers & Upload & Delete ==================


@app.route('/mes_fichiers')
@login_required
def mes_fichiers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM fichiers WHERE id_utilisateur = %s ORDER BY id_fichier DESC", (current_user.id,))
    tous_les_fichiers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('mes_fichiers.html', fichiers=tous_les_fichiers)


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('dashboard'))
    if file:
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(('.csv', '.xls', '.xlsx')):
            flash('Format non supporté (CSV ou Excel uniquement).', 'danger')
            return redirect(url_for('dashboard'))
        # Nom unique sur le disque : avant, deux utilisateurs envoyant "ventes.csv"
        # écrasaient le fichier l'un de l'autre (cas réel : fichiers 29 et 30).
        horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_disque = f"U{current_user.id}_{horodatage}_{filename}"
        path = os.path.join(config.UPLOAD_FOLDER, nom_disque)
        file.save(path)
        file_type = 'Excel' if filename.lower().endswith(('.xls', '.xlsx')) else 'CSV'
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) VALUES (%s, %s, %s, %s)",
                       (current_user.id, filename, chemin_relatif(path), file_type))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Fichier uploadé avec succès!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_file/<int:file_id>')
@login_required
def delete_file(file_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT chemin_fichier FROM fichiers WHERE id_fichier = %s AND id_utilisateur = %s",
                   (file_id, current_user.id))
    fichier = cursor.fetchone()
    if fichier:
        # Anciennes lignes : plusieurs fichiers peuvent pointer vers le même chemin disque.
        # On ne supprime le fichier physique que s'il n'est plus référencé ailleurs.
        cursor.execute("SELECT COUNT(*) AS n FROM fichiers WHERE chemin_fichier = %s AND id_fichier <> %s",
                       (fichier['chemin_fichier'], file_id))
        partage = cursor.fetchone()['n'] > 0
        chemin = chemin_absolu(fichier['chemin_fichier'])
        if not partage and os.path.isfile(chemin):
            os.remove(chemin)
        rag.supprimer_index(file_id)
        cursor.execute("DELETE FROM fichiers WHERE id_fichier = %s", (file_id,))
        conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. إحصائيات
        cursor.execute("SELECT COUNT(*) as total FROM utilisateurs")
        users_count = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM rapports")
        reports_count = cursor.fetchone()['total']

        # 2.م
        # استعملنا GROUP_CONCAT باش نجمعوا روابط الـ PDF في سطر واحد لكل مستخدم
        cursor.execute("""
            SELECT u.*, 
                   COUNT(q.id_question) as nb_questions,
                   (SELECT COUNT(*) FROM rapports r 
                    JOIN questions q2 ON r.id_question = q2.id_question 
                    WHERE q2.id_utilisateur = u.id_utilisateur) as nb_rapports
            FROM utilisateurs u 
            LEFT JOIN questions q ON u.id_utilisateur = q.id_utilisateur 
            GROUP BY u.id_utilisateur
        """)
        all_users = cursor.fetchall()

        # 3
        # LEFT JOIN : un rapport dont la question a été supprimée (id_question NULL)
        # reste visible pour l'admin au lieu de disparaître de la liste.
        query = """
            SELECT r.id_rapport, COALESCE(q.question_texte, '(question supprimée)') AS question_texte,
                   COALESCE(u.nom_utilisateur, '-') AS user_name,
                   r.date_generation, r.chemin_resume
            FROM rapports r
            LEFT JOIN questions q ON r.id_question = q.id_question
            LEFT JOIN utilisateurs u ON q.id_utilisateur = u.id_utilisateur
            ORDER BY r.date_generation DESC
        """
        cursor.execute(query)
        reports_list = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin_dashboard.html',
                               users=users_count,
                               reports=reports_count,
                               list=reports_list,
                               all_users=all_users)
    except Exception as e:
        return f"Erreur Admin: {str(e)}"


@app.route('/view_report/<path:filename>')
@login_required
def view_report(filename):
    """
    Envoie un rapport PDF.
    Sécurité (avant : send_file(filename) envoyait N'IMPORTE QUEL fichier du disque,
    ex. /view_report/C:/Windows/win.ini ou ../.env) :
      1. le chemin doit être enregistré dans la table `rapports` ;
      2. un utilisateur ne voit que ses rapports (l'admin voit tout) ;
      3. le fichier doit se trouver dans le dossier des rapports.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.chemin_resume, q.id_utilisateur
        FROM rapports r LEFT JOIN questions q ON r.id_question = q.id_question
        WHERE r.chemin_resume = %s
    """, (filename,))
    rapport = cursor.fetchone()
    cursor.close()
    conn.close()

    if not rapport:
        abort(404)
    if current_user.role != 'administrateur' and rapport['id_utilisateur'] != current_user.id:
        abort(403)

    chemin = os.path.realpath(chemin_absolu(rapport['chemin_resume']))
    dossier = os.path.realpath(config.REPORT_FOLDER)
    if os.path.commonpath([chemin, dossier]) != dossier or not os.path.isfile(chemin):
        abort(404)
    return send_file(chemin, mimetype='application/pdf')

# 1. Route pour supprimer un utilisateur


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM rapports WHERE id_question IN (SELECT id_question FROM questions WHERE id_utilisateur = %s)", (user_id,))
        cursor.execute("DELETE FROM questions WHERE id_utilisateur = %s", (user_id,))
        cursor.execute("DELETE FROM fichiers WHERE id_utilisateur = %s", (user_id,))
        cursor.execute("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return str(e)

# 2. Route pour bloquer/débloquer


@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required   # avant : n'importe quel utilisateur connecté pouvait bloquer un compte (même l'admin)
def toggle_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT est_bloque FROM utilisateurs WHERE id_utilisateur = %s", (user_id,))
        user = cursor.fetchone()

        nouvel_etat = 1 if user['est_bloque'] == 0 else 0

        cursor.execute("UPDATE utilisateurs SET est_bloque = %s WHERE id_utilisateur = %s", (nouvel_etat, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        return f"Erreur: {str(e)}"


@app.route('/admin/set_domaine/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def set_domaine(user_id):
    """L'administrateur modifie le domaine d'activité d'un utilisateur."""
    domaine = request.form.get('domaine') or ''
    if not domaine_valide(domaine):
        flash("Domaine invalide.", "danger")
        return redirect(url_for('admin_dashboard'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE utilisateurs SET domaine = %s WHERE id_utilisateur = %s", (domaine, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Déconnexion : supprime l'utilisateur de la session (logout_user) PUIS vide
    toute la session (session.clear) et redirige vers la page de connexion.
    Pas de @login_required : un utilisateur déjà déconnecté (session expirée)
    est simplement renvoyé vers /login au lieu d'obtenir une erreur.
    """
    logout_user()
    session.clear()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for('login'))


if __name__ == '__main__':
    # debug lu depuis .env (FLASK_DEBUG=1) : le débogueur Werkzeug permet d'exécuter
    # du code à distance, il ne doit pas être activé par défaut.
    etat = verifier_ollama()
    if not etat["ok"]:
        log.warning("Ollama indisponible ou modèles manquants %s : le chat affichera un message d'erreur.",
                    etat["manquants"])
    app.run(debug=config.FLASK_DEBUG)

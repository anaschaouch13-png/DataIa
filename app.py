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
from services import charts, rag
from services.auth import User, admin_required, est_requete_api
from services.db import get_db_connection
from services.domaines import DOMAINE_PAR_DEFAUT, DOMAINES, domaine_valide
from services.langue import analyser_question, message
from services.assistant import repondre
from services.llm import OllamaIndisponibleError, prechauffer, verifier_ollama
from services.parsers import charger_dataframe
from services.fichiers import (chemin_absolu, chemin_relatif, enregistrer_upload,
                               supprimer_fichier)

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
# Cookie de session : non lisible en JavaScript (HttpOnly, défaut Flask) et non envoyé par
# les requêtes provenant d'autres sites (SameSite=Lax) -> protection CSRF de base.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Phase 6 : API JSON du frontend React (/api/*) + frontend compilé servi sous /app/
from api import api as api_blueprint, spa as spa_blueprint   # noqa: E402
app.register_blueprint(api_blueprint)
app.register_blueprint(spa_blueprint)


# chemin_absolu / chemin_relatif : déplacés dans services/fichiers.py (partagés avec api.py)
load_dataset = charger_dataframe  # alias conservé pour le code existant


# ================== 3. Login Manager & User Class ==================
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.unauthorized_handler
def non_connecte():
    """API : 401 JSON (le frontend React affiche « session expirée ») ; pages : redirection /login."""
    if est_requete_api():
        return jsonify({"status": "error", "message": "Session expirée ou non connecté."}), 401
    return redirect(url_for('login', next=request.path))


# User : déplacé dans services/auth.py (partagé avec l'API JSON)


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
    statique = request.path.startswith(('/app/assets/', '/vendor/', '/static/'))
    if current_user.is_authenticated and not statique:
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
    # Phase 6 : interface principale = frontend React (/app/) s'il est compilé ;
    # les pages Jinja restent accessibles en secours (/accueil, /login, /dashboard...).
    if config.UI_PRINCIPALE == 'react' and os.path.isfile(os.path.join(config.FRONTEND_DIST, 'index.html')):
        return redirect('/app/')
    return render_template('landing.html')


@app.route('/accueil')
def landing_jinja():
    """Page d'accueil Jinja (interface de secours)."""
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


# admin_required : déplacé dans services/auth.py (réponse JSON pour l'API)


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
    if not fichier:
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
    cursor.execute("SELECT id_question, question_texte, reponse_texte FROM questions "
                   "WHERE id_fichier = %s AND id_utilisateur = %s ORDER BY date_question ASC",
                   (file_id, current_user.id))
    historique = cursor.fetchall()
    cursor.close()
    conn.close()
    # Phase 4 : graphiques de l'historique rechargés depuis leur JSON ; ancien format
    # (JSON inventé par le LLM) retiré du texte et signalé, avec un bouton « Régénérer »
    figures = charts.figures_des_questions([h['id_question'] for h in historique])
    for h in historique:
        h['reponse_texte'], h['ancien_graphique'] = charts.nettoyer_ancien_format(h['reponse_texte'] or '')
        h['figures'] = figures.get(h['id_question'], [])
    return render_template('chat.html', fichier=fichier, historique=historique)


def donnees_nettoyees_utilisateur(id_utilisateur: int) -> list:
    """Exécutions de modèles ML de l'utilisateur, avec leurs fichiers de données nettoyées."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT m.id_modele, m.type, m.algorithme, m.metrique_mape, m.metrique_mae, m.metrique_accuracy,
                             m.chemin_donnees_nettoyees, m.date_execution, f.nom_fichier
                      FROM modeles_ml m LEFT JOIN fichiers f ON f.id_fichier = m.id_fichier
                      WHERE m.id_utilisateur = %s ORDER BY m.date_execution DESC""", (id_utilisateur,))
    lignes = cursor.fetchall()
    cursor.close()
    conn.close()
    for l in lignes:
        l['disponible'] = bool(l['chemin_donnees_nettoyees']) and os.path.isfile(chemin_absolu(l['chemin_donnees_nettoyees']))
    return lignes


@app.route('/mes_donnees_nettoyees')
@login_required
def mes_donnees_nettoyees():
    """Phase 5.5 : liste de tous les jeux de données nettoyés passés aux modèles ML."""
    return render_template('mes_donnees.html', executions=donnees_nettoyees_utilisateur(current_user.id))


@app.route('/telecharger/nettoyees/<int:id_modele>/<format_fichier>')
@login_required
def telecharger_nettoyees(id_modele, format_fichier):
    """
    Téléchargement des données nettoyées d'une exécution ML (CSV, Excel ou rapport .txt).
    Sécurité : la ligne doit appartenir à l'utilisateur (l'admin voit tout), le format est pris
    dans une liste fermée et le fichier doit être dans le dossier des exports (pas de path traversal).
    """
    extensions = {"csv": (".csv", "text/csv"), "xlsx": (".xlsx", None), "rapport": ("_rapport.txt", "text/plain")}
    if format_fichier not in extensions:
        abort(404)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_utilisateur, type, chemin_donnees_nettoyees FROM modeles_ml WHERE id_modele = %s",
                   (id_modele,))
    ligne = cursor.fetchone()
    cursor.close()
    conn.close()
    if not ligne or not ligne['chemin_donnees_nettoyees']:
        abort(404)
    if ligne['id_utilisateur'] != current_user.id and current_user.role != 'administrateur':
        abort(403)
    base = os.path.splitext(chemin_absolu(ligne['chemin_donnees_nettoyees']))[0]
    suffixe, mimetype = extensions[format_fichier]
    chemin = os.path.realpath(base + suffixe)
    if os.path.commonpath([chemin, os.path.realpath(config.EXPORT_FOLDER)]) != os.path.realpath(config.EXPORT_FOLDER) \
            or not os.path.isfile(chemin):
        abort(404)
    return send_file(chemin, as_attachment=True, download_name=os.path.basename(chemin), mimetype=mimetype)


@app.route('/vendor/plotly.min.js')
def plotly_js():
    """
    plotly.js servi depuis le paquet Python installé (version 3.3.1, assortie à plotly 6.5.2).
    Avant : CDN « plotly-latest » figé en 1.58.5 (2021), incompatible avec les figures
    produites par plotly 6, et dépendant d'Internet.
    """
    import plotly
    chemin = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
    return send_file(chemin, mimetype='application/javascript', max_age=7 * 24 * 3600)

# ================== Route ask_ia (Version Finale Complète) ==================


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

        # 3. Routeur hybride : pandas (calculs) | RAG (texte) | graphique | ML selon le domaine
        #    (services/assistant.py)
        reponse = repondre(df, int(file_id), question, analyse, current_user.domaine,
                           id_utilisateur=current_user.id, source=fichier['nom_fichier'])

        # 4. Historique : on enregistre la question telle que l'utilisateur l'a écrite
        cursor.execute("INSERT INTO questions (id_utilisateur, id_fichier, question_texte, reponse_texte, date_question) "
                       "VALUES (%s, %s, %s, %s, NOW())",
                       (current_user.id, file_id, question, reponse.texte))
        conn.commit()
        id_question = cursor.lastrowid

        # 5. Graphiques : JSON enregistré tout de suite, PNG généré en arrière-plan (Phase 8 : PDF)
        graphiques = []
        for rg in reponse.resultats_graphiques:
            id_graphique = charts.enregistrer(rg, current_user.id, int(file_id), id_question,
                                              source=reponse.source_graphiques)
            graphiques.append({"id_graphique": id_graphique, "figure": rg.figure, "type": rg.spec["type"]})
        return jsonify({"status": "success", "answer": reponse.texte,
                        "langue": analyse.langue, "langue_reponse": langue,
                        "intent": reponse.intent, "routage": reponse.source_routage,
                        "resultat": reponse.resultat, "suggestions": reponse.suggestions,
                        "demande_precision": reponse.demande_precision, "temps": reponse.temps,
                        "graphique": graphiques[0] if graphiques else None, "graphiques": graphiques,
                        "id_modele": reponse.id_modele, "id_question": id_question})

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
    # Nom unique sur le disque, extension contrôlée (services/fichiers.py)
    _, erreur = enregistrer_upload(file, current_user.id)
    flash(erreur, 'danger') if erreur else flash('Fichier uploadé avec succès!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_file/<int:file_id>')
@login_required
def delete_file(file_id):
    supprimer_fichier(file_id, current_user.id)      # services/fichiers.py (contrôle du propriétaire)
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
    else:
        prechauffer()   # charge les modèles en RAM en arrière-plan (1re question plus rapide)
    charts.prechauffer_export()   # lance Chrome (kaleido) une fois : PNG en ~0,2 s au lieu de ~4 s
    app.run(debug=config.FLASK_DEBUG)

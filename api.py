"""
api.py — API JSON (/api/*) utilisée par le frontend React (Phase 6, option 1 validée).

Le frontend React (dossier frontend/, compilé dans frontend/dist) est servi par Flask
sous /app/. Il dialogue avec le serveur uniquement par ces routes JSON. Les pages Jinja
(/login, /dashboard, /chat/<id>...) restent disponibles en secours.

Sécurité :
  - session Flask-Login (cookie HttpOnly, SameSite=Lax : envoyé seulement par notre site) ;
  - réponses 401 / 403 en JSON (pas de redirection HTML) ;
  - requêtes qui modifient des données : JSON obligatoire (un formulaire d'un autre site ne
    peut pas envoyer de JSON sans autorisation CORS) -> protection CSRF ; l'upload
    (multipart) est protégé par SameSite=Lax ;
  - chaque fichier / exécution est vérifié comme appartenant à l'utilisateur (IDOR).
"""

import logging
import os

from flask import Blueprint, abort, jsonify, request, send_file, session
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

import config
from services import charts
from services.auth import User, admin_required
from services.db import get_db_connection
from services.domaines import DOMAINES, domaine_valide
from services.fichiers import (chemin_absolu, enregistrer_upload, fichier_de_utilisateur,
                               supprimer_fichier)
from services.ml import registry, simulateur
from services.parsers import charger_dataframe

log = logging.getLogger("dataia.api")
api = Blueprint("api", __name__, url_prefix="/api")


def erreur(message: str, code: int = 400):
    return jsonify({"status": "error", "message": message}), code


@api.before_request
def exiger_json_pour_modifier():
    """Protection CSRF : POST / PUT / DELETE en JSON (sauf l'upload multipart, protégé par SameSite)."""
    if request.method in ("POST", "PUT", "DELETE") and request.endpoint not in ("api.upload",) \
            and request.content_length and not request.is_json:
        return erreur("Requête JSON attendue.", 415)


def _requete_sql(sql: str, params=(), une=False):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    lignes = cur.fetchall() if cur.with_rows else None
    conn.commit()
    dernier_id = cur.lastrowid
    cur.close()
    conn.close()
    if une:
        return lignes[0] if lignes else None
    return lignes if lignes is not None else dernier_id


def _serialiser(ligne: dict) -> dict:
    """Dates -> ISO, pour le JSON."""
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in ligne.items()}


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
@api.get("/me")
@login_required
def me():
    return jsonify({"status": "success", "user": current_user.en_dict()})


@api.get("/domaines")
def domaines():
    return jsonify({"domaines": DOMAINES})


@api.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    ligne = _requete_sql("SELECT * FROM utilisateurs WHERE email = %s", (email,), une=True)
    if not ligne or not check_password_hash(ligne["mot_de_passe"], data.get("password") or ""):
        return erreur("Email ou mot de passe incorrect.", 401)
    if ligne.get("est_bloque"):
        return erreur("Votre compte est bloqué par l'administrateur.", 403)
    session.clear()
    utilisateur = User.depuis_ligne(ligne)
    login_user(utilisateur)
    return jsonify({"status": "success", "user": utilisateur.en_dict(), "message": "Connexion réussie."})


@api.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom_utilisateur") or "").strip()
    email = (data.get("email") or "").strip().lower()
    mot_de_passe = data.get("password") or ""
    domaine = data.get("domaine") or ""
    if not nom or not email or not mot_de_passe:
        return erreur("Tous les champs sont obligatoires.")
    if len(mot_de_passe) < 6:
        return erreur("Le mot de passe doit contenir au moins 6 caractères.")
    if not domaine_valide(domaine):
        return erreur("Veuillez choisir un domaine d'activité dans la liste.")
    try:
        _requete_sql("INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe, domaine) VALUES (%s, %s, %s, %s)",
                     (nom, email, generate_password_hash(mot_de_passe), domaine))
    except Exception as e:
        if getattr(e, "errno", None) == 1062:
            return erreur("Un compte existe déjà avec cet email.", 409)
        log.exception("Erreur à l'inscription")
        return erreur("Erreur lors de la création du compte.", 500)
    return jsonify({"status": "success", "message": "Compte créé ! Connectez-vous."}), 201


@api.post("/logout")
def logout():
    """Déconnexion en POST (un simple lien ou une image d'un autre site ne peut pas la déclencher)."""
    logout_user()
    session.clear()
    return jsonify({"status": "success", "message": "Vous êtes déconnecté."})


@api.route("/profil", methods=["GET", "PUT"])
@login_required
def profil():
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        nom = (data.get("nom_utilisateur") or "").strip()
        domaine = data.get("domaine") or ""
        if not nom or not domaine_valide(domaine):
            return erreur("Nom obligatoire et domaine valide requis.")
        _requete_sql("UPDATE utilisateurs SET nom_utilisateur = %s, domaine = %s WHERE id_utilisateur = %s",
                     (nom, domaine, current_user.id))
    infos = _requete_sql("SELECT id_utilisateur, nom_utilisateur, email, role, domaine, date_inscription "
                         "FROM utilisateurs WHERE id_utilisateur = %s", (current_user.id,), une=True)
    infos = _serialiser(infos)
    infos["modeles"] = [{"cle": m, "nom": registry.nom_modele(m, "fr")} for m in registry.modeles_du_domaine(infos["domaine"])]
    return jsonify({"status": "success", "profil": infos})


# ---------------------------------------------------------------------------
# Dashboard et fichiers
# ---------------------------------------------------------------------------
@api.get("/dashboard")
@login_required
def dashboard():
    uid = current_user.id
    stats = {
        "files_count": _requete_sql("SELECT COUNT(*) n FROM fichiers WHERE id_utilisateur = %s", (uid,), une=True)["n"],
        "questions_count": _requete_sql("SELECT COUNT(*) n FROM questions WHERE id_utilisateur = %s", (uid,), une=True)["n"],
        "modeles_count": _requete_sql("SELECT COUNT(*) n FROM modeles_ml WHERE id_utilisateur = %s", (uid,), une=True)["n"],
        "graphiques_count": _requete_sql("SELECT COUNT(*) n FROM graphiques WHERE id_utilisateur = %s", (uid,), une=True)["n"],
    }
    recents = _requete_sql("SELECT id_fichier, nom_fichier, type_fichier, date_upload FROM fichiers WHERE id_utilisateur = %s "
                           "ORDER BY id_fichier DESC LIMIT 5", (uid,))
    return jsonify({"stats": stats, "recent_files": [_serialiser(f) for f in recents]})


@api.get("/files")
@login_required
def fichiers():
    lignes = _requete_sql("SELECT id_fichier, nom_fichier, type_fichier, date_upload, chemin_fichier FROM fichiers "
                          "WHERE id_utilisateur = %s ORDER BY id_fichier DESC", (current_user.id,))
    resultat = []
    for f in lignes:
        disponible = os.path.isfile(chemin_absolu(f.pop("chemin_fichier")))
        resultat.append({**_serialiser(f), "disponible": disponible})
    return jsonify({"fichiers": resultat})


@api.post("/upload")
@login_required
def upload():
    if "file" not in request.files or not request.files["file"].filename:
        return erreur("Aucun fichier reçu.")
    ligne, message = enregistrer_upload(request.files["file"], current_user.id)
    if message:
        return erreur(message, 415)
    reponse = {"status": "success", "fichier": _serialiser(ligne)}
    try:                                 # Phase 7 : aperçu + questions suggérées
        from services.apercu import apercu_fichier
        reponse["apercu"] = apercu_fichier(ligne, current_user.domaine)
    except ImportError:
        pass
    except Exception as e:
        log.warning("Aperçu impossible : %s", e)
    return jsonify(reponse), 201


@api.delete("/files/<int:id_fichier>")
@login_required
def supprimer(id_fichier):
    if not supprimer_fichier(id_fichier, current_user.id):
        return erreur("Fichier introuvable.", 404)
    return jsonify({"status": "success"})


@api.get("/files/<int:id_fichier>/apercu")
@login_required
def apercu(id_fichier):
    fichier = fichier_de_utilisateur(id_fichier, current_user.id)
    if not fichier:
        return erreur("Fichier introuvable.", 404)
    try:
        from services.apercu import apercu_fichier
        return jsonify({"status": "success", "apercu": apercu_fichier(fichier, current_user.domaine)})
    except ImportError:
        return erreur("Aperçu non disponible.", 501)


# ---------------------------------------------------------------------------
# Chat : historique (questions, réponses, graphiques enregistrés)
# ---------------------------------------------------------------------------
@api.get("/chat/<int:id_fichier>/history")
@login_required
def historique(id_fichier):
    fichier = fichier_de_utilisateur(id_fichier, current_user.id)
    if not fichier:
        return erreur("Fichier introuvable.", 404)
    lignes = _requete_sql("SELECT id_question, question_texte, reponse_texte, date_question FROM questions "
                          "WHERE id_fichier = %s AND id_utilisateur = %s ORDER BY date_question ASC",
                          (id_fichier, current_user.id))
    figures = charts.figures_des_questions([l["id_question"] for l in lignes])
    historique_json = []
    for l in lignes:
        texte, ancien = charts.nettoyer_ancien_format(l["reponse_texte"] or "")
        historique_json.append({**_serialiser(l), "reponse_texte": texte, "ancien_graphique": ancien,
                                "figures": figures.get(l["id_question"], [])})
    f = {k: fichier[k] for k in ("id_fichier", "nom_fichier", "type_fichier", "date_upload")}
    return jsonify({"fichier": _serialiser(f), "historique": historique_json,
                    "disponible": os.path.isfile(chemin_absolu(fichier["chemin_fichier"]))})


# ---------------------------------------------------------------------------
# Simulateur what-if (panneau à droite du chat) : modèles du domaine de l'utilisateur
# ---------------------------------------------------------------------------
def _df_du_fichier(id_fichier):
    if not id_fichier:
        return None, None
    fichier = fichier_de_utilisateur(id_fichier, current_user.id)
    if not fichier or not os.path.isfile(chemin_absolu(fichier["chemin_fichier"])):
        return None, None
    chemin = chemin_absolu(fichier["chemin_fichier"])
    return charger_dataframe(chemin), f"{id_fichier}:{os.path.getmtime(chemin)}"


@api.get("/simulateur/modeles")
@login_required
def simulateur_modeles():
    df, cle = _df_du_fichier(request.args.get("file_id", type=int))
    modeles = []
    for m in registry.modeles_du_domaine(current_user.domaine):
        besoin = simulateur.BESOIN_FICHIER[m]
        try:
            champs = simulateur.CHAMPS[m](df, cle_fichier=cle) if m == "anomaly" else simulateur.CHAMPS[m](df)
        except Exception as e:
            log.warning("Formulaire %s indisponible : %s", m, e)
            champs = []
        modeles.append({"cle": m, "nom": registry.nom_modele(m, "fr"), "besoin_fichier": besoin, "champs": champs,
                        "disponible": bool(champs),
                        "raison": "" if champs else ("Ouvrez un fichier avec une colonne de dates et une valeur numérique."
                                                     if m == "forecast" else
                                                     "Ouvrez un fichier avec des colonnes numériques." if m == "anomaly"
                                                     else "Modèle indisponible.")})
    return jsonify({"domaine": current_user.domaine, "modeles": modeles})


@api.post("/simulateur/<cle>")
@login_required
def simuler(cle):
    if not registry.est_disponible(cle, current_user.domaine):
        return erreur(f"Le modèle « {cle} » n'est pas proposé pour votre domaine ({current_user.domaine}).", 403)
    data = request.get_json(silent=True) or {}
    df, cle_fichier = _df_du_fichier(data.get("file_id"))
    if simulateur.BESOIN_FICHIER[cle] and df is None:
        return erreur("Ce simulateur a besoin d'un fichier ouvert.", 400)
    entrees = data.get("entrees") or {}
    try:
        resultat = registry.simulateur(cle)(df, entrees, cle_fichier=cle_fichier)
    except Exception as e:
        log.exception("Simulation %s impossible", cle)
        return erreur(f"Simulation impossible : {e}", 422)
    id_simulation = simulateur.enregistrer(current_user.id, registry.MODELES[cle].type_bdd,
                                           {**entrees, "file_id": data.get("file_id")}, resultat)
    return jsonify({"status": "success", "id_simulation": id_simulation, "resultat": resultat})


@api.get("/simulations")
@login_required
def simulations():
    lignes = _requete_sql("SELECT id_simulation, type_modele, entrees_json, resultat_json, date_simulation FROM simulations "
                          "WHERE id_utilisateur = %s ORDER BY id_simulation DESC LIMIT 50", (current_user.id,))
    return jsonify({"simulations": [_serialiser(l) for l in lignes]})


# ---------------------------------------------------------------------------
# Données nettoyées (Phase 5.5)
# ---------------------------------------------------------------------------
@api.get("/donnees_nettoyees")
@login_required
def donnees_nettoyees():
    lignes = _requete_sql("""SELECT m.id_modele, m.type, m.algorithme, m.metrique_mape, m.metrique_mae, m.metrique_accuracy,
                                    m.chemin_donnees_nettoyees, m.date_execution, f.nom_fichier
                             FROM modeles_ml m LEFT JOIN fichiers f ON f.id_fichier = m.id_fichier
                             WHERE m.id_utilisateur = %s ORDER BY m.date_execution DESC""", (current_user.id,))
    resultat = []
    for l in lignes:
        disponible = bool(l["chemin_donnees_nettoyees"]) and os.path.isfile(chemin_absolu(l.pop("chemin_donnees_nettoyees")))
        base = f"/telecharger/nettoyees/{l['id_modele']}"
        resultat.append({**_serialiser(l), "disponible": disponible,
                         "liens": {"csv": f"{base}/csv", "xlsx": f"{base}/xlsx", "rapport": f"{base}/rapport"}})
    return jsonify({"executions": resultat})


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------
@api.get("/admin/data")
@login_required
@admin_required
def admin_data():
    utilisateurs = _requete_sql("""
        SELECT u.id_utilisateur, u.nom_utilisateur, u.email, u.role, u.domaine, u.est_bloque, u.date_inscription,
               (SELECT COUNT(*) FROM questions q WHERE q.id_utilisateur = u.id_utilisateur) AS nb_questions,
               (SELECT COUNT(*) FROM rapports r JOIN questions q2 ON r.id_question = q2.id_question
                 WHERE q2.id_utilisateur = u.id_utilisateur) AS nb_rapports,
               (SELECT COUNT(*) FROM modeles_ml m WHERE m.id_utilisateur = u.id_utilisateur) AS nb_modeles
        FROM utilisateurs u ORDER BY u.id_utilisateur""")
    rapports = _requete_sql("""
        SELECT r.id_rapport, r.id_question, COALESCE(q.question_texte, '(question supprimée)') AS question_texte,
               COALESCE(u.nom_utilisateur, '-') AS user_name, r.date_generation, r.chemin_resume
        FROM rapports r LEFT JOIN questions q ON r.id_question = q.id_question
        LEFT JOIN utilisateurs u ON q.id_utilisateur = u.id_utilisateur ORDER BY r.date_generation DESC""")
    stats = {"users_count": len(utilisateurs), "reports_count": len(rapports),
             "questions_count": sum(u["nb_questions"] for u in utilisateurs),
             "modeles_count": sum(u["nb_modeles"] for u in utilisateurs)}
    return jsonify({"stats": stats, "users": [_serialiser(u) for u in utilisateurs],
                    "reports": [_serialiser(r) for r in rapports], "domaines": DOMAINES})


@api.post("/admin/users/<int:id_utilisateur>/toggle")
@login_required
@admin_required
def admin_bloquer(id_utilisateur):
    if id_utilisateur == current_user.id:
        return erreur("Vous ne pouvez pas bloquer votre propre compte.")
    _requete_sql("UPDATE utilisateurs SET est_bloque = 1 - est_bloque WHERE id_utilisateur = %s", (id_utilisateur,))
    return jsonify({"status": "success"})


@api.put("/admin/users/<int:id_utilisateur>/domaine")
@login_required
@admin_required
def admin_domaine(id_utilisateur):
    domaine = (request.get_json(silent=True) or {}).get("domaine") or ""
    if not domaine_valide(domaine):
        return erreur("Domaine invalide.")
    _requete_sql("UPDATE utilisateurs SET domaine = %s WHERE id_utilisateur = %s", (domaine, id_utilisateur))
    return jsonify({"status": "success"})


@api.delete("/admin/users/<int:id_utilisateur>")
@login_required
@admin_required
def admin_supprimer(id_utilisateur):
    if id_utilisateur == current_user.id:
        return erreur("Vous ne pouvez pas supprimer votre propre compte.")
    # Les clés étrangères (ON DELETE CASCADE) suppriment fichiers, questions, modèles et simulations
    _requete_sql("DELETE FROM rapports WHERE id_question IN (SELECT id_question FROM questions WHERE id_utilisateur = %s)",
                 (id_utilisateur,))
    _requete_sql("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (id_utilisateur,))
    return jsonify({"status": "success"})


# ---------------------------------------------------------------------------
# Frontend React compilé, servi sous /app/ (Blueprint séparé, sans préfixe /api)
# ---------------------------------------------------------------------------
spa = Blueprint("spa", __name__)


@spa.route("/app/", defaults={"chemin": ""})
@spa.route("/app/<path:chemin>")
def application(chemin):
    """Fichiers de frontend/dist ; toute autre adresse renvoie index.html (routage côté React)."""
    dist = config.FRONTEND_DIST
    if not os.path.isfile(os.path.join(dist, "index.html")):
        return ("Frontend non compilé : lancez « npm run build » dans le dossier frontend "
                "(les pages Jinja restent disponibles sur /login).", 503)
    cible = os.path.realpath(os.path.join(dist, chemin))
    if chemin and os.path.commonpath([cible, os.path.realpath(dist)]) == os.path.realpath(dist) and os.path.isfile(cible):
        return send_file(cible, max_age=31536000 if "/assets/" in cible.replace("\\", "/") else 0)
    if "." in os.path.basename(chemin):          # fichier statique absent
        abort(404)
    return send_file(os.path.join(dist, "index.html"), max_age=0)

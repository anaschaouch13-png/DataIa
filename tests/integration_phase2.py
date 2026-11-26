"""
tests/integration_phase2.py — tests d'intégration de la Phase 2 (base MySQL réelle, client de test Flask).
Lancer depuis le dossier DataIa : python tests/integration_phase2.py
Les questions / comptes créés pendant le test sont supprimés à la fin.
"""
import os, sys, time
sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
import logging; logging.disable(logging.INFO)
import app as appmod
from services.db import get_db_connection

app = appmod.app
app.config["TESTING"] = True
res = []
def check(nom, ok, detail=""):
    res.append((nom, bool(ok))); print(("OK   " if ok else "ECHEC"), nom, ("| " + str(detail)) if detail else "")

def sql(q, p=(), one=False):
    c = get_db_connection(); cur = c.cursor(dictionary=True); cur.execute(q, p)
    r = cur.fetchall() if cur.with_rows else None; c.commit(); cur.close(); c.close()
    return (r[0] if r else None) if one else r

avant = {t: sql(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in ["utilisateurs", "fichiers", "questions", "rapports"]}
email = f"test_phase2_{int(time.time())}@test.local"
c = app.test_client()

# ---------- Inscription
r = c.post("/signup", data={"nom_utilisateur": "Test P2", "email": email, "password": "Secret123!", "domaine": "Pirate"})
check("inscription domaine hors liste refusée", "domaine" in r.get_data(as_text=True).lower() and sql("SELECT 1 FROM utilisateurs WHERE email=%s", (email,)) == [])
r = c.post("/signup", data={"nom_utilisateur": "Test P2", "email": email, "password": "Secret123!"})
check("inscription sans domaine refusée", sql("SELECT 1 FROM utilisateurs WHERE email=%s", (email,)) == [])
html = c.get("/signup").get_data(as_text=True)
check("formulaire : liste déroulante des 8 domaines", all(f'value="{d}"' in html for d in appmod.DOMAINES))
r = c.post("/signup", data={"nom_utilisateur": "Test P2", "email": email.upper(), "password": "Secret123!", "domaine": "Banque"})
u = sql("SELECT * FROM utilisateurs WHERE email=%s", (email,), one=True)
check("inscription domaine Banque", r.status_code == 302 and u and u["domaine"] == "Banque", u and u["domaine"])
r = c.post("/signup", data={"nom_utilisateur": "X", "email": email, "password": "x", "domaine": "Autre"})
t = r.get_data(as_text=True)
check("email déjà utilisé : message clair (pas d'erreur SQL)", "existe déjà" in t and "1062" not in t)

# ---------- Connexion réelle (mot de passe)
r = c.post("/login", data={"email": email, "password": "Secret123!"})
check("connexion par mot de passe", r.status_code == 302 and "/dashboard" in r.headers["Location"])
r = c.get("/dashboard"); t = r.get_data(as_text=True)
check("dashboard : domaine affiché + bouton déconnexion", "Banque" in t and 'id="btn-deconnexion"' in t)
check("pages connectées non mises en cache (no-store)", "no-store" in r.headers.get("Cache-Control", ""))
for page in ["/mes_fichiers", "/profil"]:
    check(f"bouton déconnexion visible sur {page}", 'id="btn-deconnexion"' in c.get(page).get_data(as_text=True))

# ---------- Profil
check("profil affiche le domaine actuel", 'value="Banque" selected' in c.get("/profil").get_data(as_text=True))
c.post("/profil", data={"nom_utilisateur": "Test P2 modifié", "domaine": "Finance"})
u = sql("SELECT * FROM utilisateurs WHERE email=%s", (email,), one=True)
check("profil : modification nom + domaine", u["domaine"] == "Finance" and u["nom_utilisateur"] == "Test P2 modifié")
c.post("/profil", data={"nom_utilisateur": "Test P2", "domaine": "Inconnu"})
check("profil : domaine invalide refusé", sql("SELECT domaine FROM utilisateurs WHERE email=%s", (email,), one=True)["domaine"] == "Finance")
check("non-admin ne peut pas modifier un domaine", c.post(f"/admin/set_domaine/{u['id_utilisateur']}", data={"domaine": "Banque"}).status_code == 403)

# ---------- Clés étrangères : supprimer un fichier conserve l'historique
uid = u["id_utilisateur"]
sql("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) VALUES (%s,'fk_test.csv','uploads/inexistant_fk_test.csv','CSV')", (uid,))
fid = sql("SELECT MAX(id_fichier) m FROM fichiers WHERE id_utilisateur=%s", (uid,), one=True)["m"]
sql("INSERT INTO questions (id_utilisateur, id_fichier, question_texte, reponse_texte) VALUES (%s,%s,'q test','r test')", (uid, fid))
c.get(f"/delete_file/{fid}")
q = sql("SELECT id_fichier FROM questions WHERE id_utilisateur=%s", (uid,), one=True)
check("FK : suppression du fichier -> question conservée, id_fichier NULL", q is not None and q["id_fichier"] is None)
try:
    sql("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) VALUES (999999,'x','x','CSV')")
    check("FK : fichier pour un utilisateur inexistant refusé", False)
except Exception as e:
    check("FK : fichier pour un utilisateur inexistant refusé", "foreign key" in str(e).lower(), getattr(e, "errno", ""))

# ---------- Déconnexion
r = c.get("/logout")
check("logout -> redirection /login", r.status_code == 302 and "/login" in r.headers["Location"])
with c.session_transaction() as s:
    check("session détruite (plus de _user_id)", "_user_id" not in s)
for page in ["/dashboard", "/profil", "/mes_fichiers", "/chat/31", "/admin/dashboard"]:
    r = c.get(page)
    check(f"après logout {page} -> login", r.status_code == 302 and "/login" in r.headers["Location"])
r = c.post("/ask_ia", json={"file_id": 31, "question": "x"})
check("après logout /ask_ia refusé", r.status_code in (302, 401))
check("logout sans être connecté -> /login (pas d'erreur)", "/login" in c.get("/logout").headers.get("Location", ""))

# ---------- Admin
adm = app.test_client()
with adm.session_transaction() as s:
    s["_user_id"] = "6"; s["_fresh"] = True
t = adm.get("/admin/dashboard").get_data(as_text=True)
check("admin : colonne domaine + bouton déconnexion", "set_domaine" in t and 'id="btn-deconnexion"' in t)
adm.post(f"/admin/set_domaine/{uid}", data={"domaine": "Télécom"})
check("admin modifie le domaine (Télécom, accent)", sql("SELECT domaine FROM utilisateurs WHERE id_utilisateur=%s", (uid,), one=True)["domaine"] == "Télécom")

# ---------- Compte bloqué : session invalidée immédiatement
c2 = app.test_client(); c2.post("/login", data={"email": email, "password": "Secret123!"})
adm.post(f"/admin/toggle_user/{uid}")
r = c2.get("/dashboard")
check("compte bloqué pendant la session -> renvoyé vers login", r.status_code == 302 and "/login" in r.headers["Location"])
r = c2.post("/login", data={"email": email, "password": "Secret123!"})
check("compte bloqué : connexion refusée", "bloqué" in r.get_data(as_text=True))

# ---------- Non-régression : utilisateur existant
u1 = app.test_client()
with u1.session_transaction() as s:
    s["_user_id"] = "1"; s["_fresh"] = True
check("utilisateur existant : dashboard + domaine 'Autre'", "Autre" in u1.get("/dashboard").get_data(as_text=True))
t = u1.get("/chat/31").get_data(as_text=True)
check("utilisateur existant : chat et historique", u1.get("/chat/31").status_code == 200)

# ---------- Nettoyage : suppression du compte de test (cascade)
adm.post(f"/admin/delete_user/{uid}")
check("suppression du compte de test (cascade)", sql("SELECT 1 FROM utilisateurs WHERE id_utilisateur=%s", (uid,)) == []
      and sql("SELECT 1 FROM questions WHERE id_utilisateur=%s", (uid,)) == [])
apres = {t: sql(f"SELECT COUNT(*) n FROM {t}", one=True)["n"] for t in avant}
check("données existantes intactes après les tests", avant == apres, apres)
print(f"\nBILAN : {sum(o for _, o in res)}/{len(res)} tests OK")

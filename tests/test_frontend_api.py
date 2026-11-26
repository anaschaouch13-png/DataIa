"""
tests/test_frontend_api.py — Tests de la Phase 6 : API JSON du frontend React + simulateur + SPA.

Lancer depuis le dossier DataIa (MySQL lancé) :  python -m unittest tests.test_frontend_api -v
Deux comptes temporaires (Banque et E-commerce) sont créés puis supprimés (cascade).
"""

import io
import logging
import os
import sys
import time
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
logging.disable(logging.INFO)

import app as appmod                          # noqa: E402
import config                                 # noqa: E402
from services.db import get_db_connection     # noqa: E402

app = appmod.app
app.config["TESTING"] = True
SUFFIXE = str(int(time.time()))
COMPTES = {"Banque": f"test_banque_{SUFFIXE}@test.local", "E-commerce": f"test_ecom_{SUFFIXE}@test.local"}
MDP = "Secret123!"


def sql(requete, params=(), une=False):
    c = get_db_connection()
    cur = c.cursor(dictionary=True)
    cur.execute(requete, params)
    r = cur.fetchall() if cur.with_rows else None
    c.commit()
    cur.close()
    c.close()
    return (r[0] if r else None) if une else r


def client_connecte(email):
    c = app.test_client()
    r = c.post("/api/login", json={"email": email, "password": MDP})
    assert r.status_code == 200, r.get_json()
    return c


class TestApiFrontend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        c = app.test_client()
        for domaine, email in COMPTES.items():
            r = c.post("/api/signup", json={"nom_utilisateur": f"Test {domaine}", "email": email,
                                            "password": MDP, "domaine": domaine})
            assert r.status_code == 201, r.get_json()

    @classmethod
    def tearDownClass(cls):
        for email in COMPTES.values():
            u = sql("SELECT id_utilisateur FROM utilisateurs WHERE email = %s", (email,), une=True)
            if u:
                for f in sql("SELECT chemin_fichier FROM fichiers WHERE id_utilisateur = %s", (u["id_utilisateur"],)):
                    chemin = os.path.join(RACINE, f["chemin_fichier"])
                    if os.path.isfile(chemin):
                        os.remove(chemin)
                sql("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (u["id_utilisateur"],))   # cascade

    # ---------- Authentification ----------
    def test_authentification(self):
        c = app.test_client()
        r = c.get("/api/me")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["status"], "error")                      # JSON, pas de redirection HTML
        self.assertEqual(c.post("/api/login", json={"email": COMPTES["Banque"], "password": "faux"}).status_code, 401)
        c = client_connecte(COMPTES["Banque"])
        moi = c.get("/api/me").get_json()["user"]
        self.assertEqual(moi["domaine"], "Banque")
        self.assertNotIn("password", moi)
        self.assertEqual(c.post("/api/logout").status_code, 200)                # déconnexion en POST
        self.assertEqual(c.get("/api/me").status_code, 401)

    def test_inscription_validation(self):
        c = app.test_client()
        r = c.post("/api/signup", json={"nom_utilisateur": "x", "email": f"x{SUFFIXE}@t.l", "password": MDP, "domaine": "Pirate"})
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/signup", json={"nom_utilisateur": "x", "email": COMPTES["Banque"], "password": MDP, "domaine": "Autre"})
        self.assertEqual(r.status_code, 409)

    def test_csrf_json_obligatoire(self):
        c = client_connecte(COMPTES["Banque"])
        r = c.put("/api/profil", data={"nom_utilisateur": "pirate", "domaine": "Autre"})   # formulaire HTML
        self.assertEqual(r.status_code, 415)

    def test_profil(self):
        c = client_connecte(COMPTES["E-commerce"])
        p = c.get("/api/profil").get_json()["profil"]
        self.assertEqual([m["cle"] for m in p["modeles"]], ["forecast", "anomaly"])
        r = c.put("/api/profil", json={"nom_utilisateur": "Test E-commerce", "domaine": "E-commerce"})
        self.assertEqual(r.status_code, 200)

    # ---------- Fichiers, chat, simulateur ----------
    def test_parcours_fichier_et_simulateur(self):
        c = client_connecte(COMPTES["Banque"])
        with open(os.path.join(RACINE, "uploads", "ventes_demo_dataia.xlsx"), "rb") as f:
            r = c.post("/api/upload", data={"file": (io.BytesIO(f.read()), "ventes_demo.xlsx")},
                       content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201, r.get_json())
        fid = r.get_json()["fichier"]["id_fichier"]
        r = c.post("/api/upload", data={"file": (io.BytesIO(b"x"), "virus.exe")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 415)
        self.assertEqual(len(c.get("/api/files").get_json()["fichiers"]), 1)
        self.assertEqual(c.get(f"/api/chat/{fid}/history").get_json()["historique"], [])

        modeles = c.get(f"/api/simulateur/modeles?file_id={fid}").get_json()["modeles"]
        self.assertEqual([m["cle"] for m in modeles], ["forecast", "anomaly", "churn"])
        self.assertTrue(all(m["disponible"] for m in modeles))
        avant = sql("SELECT COUNT(*) n FROM simulations s JOIN utilisateurs u USING(id_utilisateur) WHERE u.email = %s",
                    (COMPTES["Banque"],), une=True)["n"]
        r = c.post("/api/simulateur/forecast", json={"file_id": fid, "entrees": {"colonne": "chiffre_affaires", "horizon": 3}})
        self.assertEqual(len(r.get_json()["resultat"]["previsions"]), 3)
        r = c.post("/api/simulateur/anomaly", json={"file_id": fid, "entrees": {"quantite": 4, "prix_unitaire": 0.01,
                                                                                "chiffre_affaires": 3856}})
        self.assertEqual(r.get_json()["resultat"]["verdict"], "Anormale")
        r = c.post("/api/simulateur/churn", json={"entrees": {"age": 55, "products_number": 3, "active_member": 0}})
        self.assertEqual(r.get_json()["resultat"]["prediction"], "Risque de départ")
        apres = sql("SELECT COUNT(*) n FROM simulations s JOIN utilisateurs u USING(id_utilisateur) WHERE u.email = %s",
                    (COMPTES["Banque"],), une=True)["n"]
        self.assertEqual(apres - avant, 3)                                      # chaque simulation est enregistrée

        autre = client_connecte(COMPTES["E-commerce"])
        self.assertEqual(autre.get(f"/api/chat/{fid}/history").status_code, 404)  # IDOR
        self.assertEqual(autre.post("/api/simulateur/churn", json={"entrees": {}}).status_code, 403)
        self.assertNotIn("churn", [m["cle"] for m in autre.get("/api/simulateur/modeles").get_json()["modeles"]])
        self.assertEqual(c.delete(f"/api/files/{fid}").status_code, 200)

    # ---------- Admin ----------
    def test_admin_reserve(self):
        c = client_connecte(COMPTES["Banque"])
        self.assertEqual(c.get("/api/admin/data").status_code, 403)
        self.assertEqual(c.post("/api/admin/users/1/toggle").status_code, 403)
        admin = app.test_client()
        ident = sql("SELECT id_utilisateur FROM utilisateurs WHERE role = 'administrateur' LIMIT 1", une=True)
        with admin.session_transaction() as s:
            s["_user_id"], s["_fresh"] = str(ident["id_utilisateur"]), True
        d = admin.get("/api/admin/data").get_json()
        self.assertIn("domaine", d["users"][0])
        cible = sql("SELECT id_utilisateur FROM utilisateurs WHERE email = %s", (COMPTES["E-commerce"],), une=True)["id_utilisateur"]
        self.assertEqual(admin.put(f"/api/admin/users/{cible}/domaine", json={"domaine": "Télécom"}).status_code, 200)
        self.assertEqual(sql("SELECT domaine FROM utilisateurs WHERE id_utilisateur = %s", (cible,), une=True)["domaine"], "Télécom")
        admin.put(f"/api/admin/users/{cible}/domaine", json={"domaine": "E-commerce"})

    # ---------- Frontend servi par Flask ----------
    def test_spa_et_secours_jinja(self):
        c = app.test_client()
        if not os.path.isfile(os.path.join(config.FRONTEND_DIST, "index.html")):
            self.skipTest("frontend non compilé")
        self.assertEqual(c.get("/").headers["Location"], "/app/")
        self.assertIn(b'<div id="root">', c.get("/app/").data)
        self.assertIn(b'<div id="root">', c.get("/app/chat/12").data)            # routage côté React
        self.assertEqual(c.get("/app/assets/inexistant.js").status_code, 404)
        self.assertEqual(c.get("/app/..%2F..%2F.env").status_code, 404)
        self.assertEqual(c.get("/login").status_code, 200)                       # Jinja en secours
        self.assertEqual(c.get("/accueil").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

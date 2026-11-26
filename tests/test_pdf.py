"""
tests/test_pdf.py — Tests de la Phase 8 (rapport PDF complet, arabe).

Lancer depuis le dossier DataIa (MySQL lancé) :  python -m unittest tests.test_pdf -v
Un compte temporaire est créé ; questions, graphique, prévision ML et simulation sont produits
par l'API, puis le PDF est téléchargé et son CONTENU est vérifié avec pdfplumber.
"""

import io
import json
import logging
import os
import sys
import time
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
logging.disable(logging.INFO)

import pdfplumber                                      # noqa: E402

import app as appmod                                   # noqa: E402
from services.db import get_db_connection              # noqa: E402
from services.pdf_export import texte_pdf              # noqa: E402

app = appmod.app
app.config["TESTING"] = True
EMAIL = f"test_pdf_{int(time.time())}@test.local"


def sql(requete, params=(), une=False):
    c = get_db_connection()
    cur = c.cursor(dictionary=True)
    cur.execute(requete, params)
    r = cur.fetchall() if cur.with_rows else None
    c.commit()
    cur.close()
    c.close()
    return (r[0] if r else None) if une else r


class TestArabe(unittest.TestCase):

    def test_mise_en_forme_arabe(self):
        sortie = texte_pdf("مجموع المبيعات")
        self.assertTrue(any(0xFE70 <= ord(c) <= 0xFEFF for c in sortie))      # formes liées (reshaper)
        self.assertNotEqual(sortie, "مجموع المبيعات")                         # ordre d'affichage (bidi)
        self.assertEqual(texte_pdf("Total 🔢 : 12"), "Total  : 12")            # emojis retirés
        self.assertEqual(texte_pdf("Bonjour"), "Bonjour")


class TestRapportComplet(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        c = app.test_client()
        assert c.post("/api/signup", json={"nom_utilisateur": "Test PDF", "email": EMAIL, "password": "Secret123!",
                                           "domaine": "Banque"}).status_code == 201
        c.post("/api/login", json={"email": EMAIL, "password": "Secret123!"})
        with open(os.path.join(RACINE, "uploads", "ventes_demo_dataia.xlsx"), "rb") as f:
            r = c.post("/api/upload", data={"file": (io.BytesIO(f.read()), "ventes_pdf.xlsx")},
                       content_type="multipart/form-data")
        cls.fid = r.get_json()["fichier"]["id_fichier"]
        cls.client = c
        # Questions routées par les règles (pas d'appel au LLM) : graphique, arabe, superlatif, prévision ML
        for q in ("Montre les ventes par région en camembert", "ارسم مخطط المبيعات حسب المنطقة",
                  "Quelle est la région la plus forte ?", "Prévois le chiffre d'affaires des 6 prochains mois"):
            assert c.post("/ask_ia", json={"file_id": cls.fid, "question": q}).status_code == 200
        c.post("/api/simulateur/churn", json={"file_id": cls.fid, "entrees": {"age": 55, "products_number": 3}})
        time.sleep(3)                                     # export PNG en arrière-plan
        debut = time.time()
        cls.reponse = c.post(f"/api/rapport/{cls.fid}/pdf", json={})
        cls.duree = round(time.time() - debut, 2)
        cls.pdf = cls.reponse.data
        cls.reponse.close()                               # libère le fichier (sinon Windows le verrouille)

    @classmethod
    def tearDownClass(cls):
        u = sql("SELECT id_utilisateur FROM utilisateurs WHERE email = %s", (EMAIL,), une=True)
        if not u:
            return
        uid = u["id_utilisateur"]
        for r in sql("SELECT r.id_rapport, r.chemin_resume FROM rapports r JOIN questions q USING(id_question) "
                     "WHERE q.id_utilisateur = %s", (uid,)):
            p = os.path.join(RACINE, r["chemin_resume"])
            try:
                os.remove(p)
            except OSError:
                pass
            sql("DELETE FROM rapports WHERE id_rapport = %s", (r["id_rapport"],))
        for f in sql("SELECT chemin_fichier FROM fichiers WHERE id_utilisateur = %s", (uid,)):
            p = os.path.join(RACINE, f["chemin_fichier"])
            if os.path.isfile(p):
                os.remove(p)
        sql("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (uid,))       # cascade
        import shutil
        import config
        for dossier in (config.GRAPH_FOLDER, config.EXPORT_FOLDER):            # graphiques et exports du compte
            shutil.rmtree(os.path.join(dossier, f"U{uid}"), ignore_errors=True)
        os.makedirs(os.path.join(RACINE, "mesures"), exist_ok=True)
        with open(os.path.join(RACINE, "mesures", "phase8_pdf.json"), "w", encoding="utf-8") as f:
            json.dump({"generation_pdf_s": cls.duree, "taille_ko": round(len(cls.pdf) / 1024, 1)}, f, indent=2)

    def test_pdf_telecharge(self):
        self.assertEqual(self.reponse.status_code, 200)
        self.assertEqual(self.reponse.mimetype, "application/pdf")
        self.assertTrue(self.pdf.startswith(b"%PDF"))

    def test_contenu(self):
        with pdfplumber.open(io.BytesIO(self.pdf)) as doc:
            texte = "\n".join(p.extract_text() or "" for p in doc.pages)
            nb_images = sum(len(p.images) for p in doc.pages)
            self.assertGreaterEqual(len(doc.pages), 5)
        for attendu in ("Rapport d'analyse DataIA", "Domaine d'activité : Banque", "Sommaire", "Informations du fichier",
                        "Questions et réponses", "Montre les ventes par région en camembert", "Graphiques",
                        "Modèles de Machine Learning", "Prévision du chiffre d'affaires", "Simulations what-if",
                        "Calculé par pandas"):
            self.assertIn(attendu, texte, attendu)
        self.assertTrue(any(0xFE70 <= ord(c) <= 0xFEFF for c in texte), "texte arabe mis en forme absent")
        self.assertGreaterEqual(nb_images, 4)          # logo + 3 graphiques (camembert/barres, arabe, prévision)

    def test_enregistrement_et_securite(self):
        u = sql("SELECT id_utilisateur FROM utilisateurs WHERE email = %s", (EMAIL,), une=True)
        rapport = sql("SELECT r.* FROM rapports r JOIN questions q USING(id_question) WHERE q.id_utilisateur = %s",
                      (u["id_utilisateur"],), une=True)
        self.assertIsNotNone(rapport)
        self.assertIsNotNone(rapport["type_graphique"])
        autre = app.test_client()
        admin = sql("SELECT id_utilisateur FROM utilisateurs WHERE role = 'administrateur' LIMIT 1", une=True)
        with autre.session_transaction() as s:
            s["_user_id"], s["_fresh"] = str(admin["id_utilisateur"]), True
        self.assertEqual(autre.post(f"/api/rapport/{self.fid}/pdf", json={}).status_code, 404)   # pas le sien


if __name__ == "__main__":
    unittest.main(verbosity=2)

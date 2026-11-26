"""
tests/test_parsers.py — Tests de la Phase 7 (multi-formats, aperçu, questions suggérées).

Lancer depuis le dossier DataIa :  python -m unittest tests.test_parsers -v
Les réponses attendues sur rapport_ventes_2025.pdf et tableau_ventes_2025.png viennent de
l'utilisatrice (sauf le « mois le plus fort » : le tableau du PDF donne Mai, voir JUSTIFICATIONS).
"""

import io
import json
import logging
import os
import sys
import tempfile
import time
import unittest

import pandas as pd

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
logging.disable(logging.INFO)

from services import parsers                                  # noqa: E402
from services.apercu import questions_suggerees               # noqa: E402
from services.assistant import repondre                       # noqa: E402
from services.langue import analyser_question                 # noqa: E402
from services.llm import verifier_ollama                      # noqa: E402

PDF = os.path.join(RACINE, "uploads", "rapport_ventes_2025.pdf")
PNG = os.path.join(RACINE, "uploads", "tableau_ventes_2025.png")
MESURES = {}


def poser(chemin, question, domaine="Autre", id_index=990100):
    doc = parsers.analyser_fichier(chemin)
    analyse = analyser_question(question)
    df = parsers.table_pour_question(doc, f"{question} {analyse.question_pour_llm}")
    return repondre(df, id_index, question, analyse, domaine, textes_rag=doc.textes_rag())


class TestFormats(unittest.TestCase):

    def test_csv_separateur_encodage_virgule(self):
        contenu = "Région;Ventes;Date\nTunis;1 200,50;2025-01-01\nSfax;800,25;2025-01-02\nTotal;2 000,75;\n"
        with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
            f.write(contenu.encode("latin-1"))
        try:
            res = parsers.analyser_fichier(f.name)
            df = res.principal
            self.assertEqual(list(df.columns), ["Région", "Ventes", "Date"])          # accents relus (latin-1)
            self.assertEqual(df["Ventes"].tolist(), [1200.5, 800.25])                 # « 1 200,50 » -> 1200.5
            self.assertTrue(any("total" in r for r in res.remarques))                 # ligne Total retirée
            self.assertTrue(any("Séparateur" in r for r in res.remarques))
        finally:
            os.remove(f.name)

    def test_excel_toutes_les_feuilles(self):
        with tempfile.TemporaryDirectory() as d:
            meme = os.path.join(d, "meme.xlsx")
            with pd.ExcelWriter(meme) as w:
                pd.DataFrame({"mois": ["jan", "fev"], "ca": [1, 2]}).to_excel(w, sheet_name="2024", index=False)
                pd.DataFrame({"mois": ["jan", "fev"], "ca": [3, 4]}).to_excel(w, sheet_name="2025", index=False)
            res = parsers.analyser_fichier(meme)
            self.assertEqual(len(res.tables), 1)
            self.assertEqual(res.principal["ca"].sum(), 10)
            self.assertIn("feuille", res.principal.columns)
            differentes = os.path.join(d, "diff.xlsx")
            with pd.ExcelWriter(differentes) as w:
                pd.DataFrame({"produit": ["a", "b"], "prix": [1, 2]}).to_excel(w, sheet_name="produits", index=False)
                pd.DataFrame({"client": ["x"], "ville": ["Tunis"]}).to_excel(w, sheet_name="clients", index=False)
            self.assertEqual(len(parsers.analyser_fichier(differentes).tables), 2)

    def test_pdf_tableaux_et_texte(self):
        debut = time.time()
        res = parsers.analyser_fichier(PDF)
        MESURES["pdf_analyse_s"] = round(time.time() - debut, 2)
        self.assertEqual(len(res.tables), 2)
        mensuel = res.tables[0][1]
        self.assertEqual(len(mensuel), 12)                                           # ligne Total retirée
        self.assertEqual(mensuel["Tunis"].sum(), 602532)
        self.assertIn("fin d'année", res.texte)
        self.assertEqual(list(parsers.table_pour_question(res, "catégorie la plus forte").columns)[0], "Catégorie")
        self.assertEqual(list(parsers.table_pour_question(res, "CA de Tunis").columns)[0], "Mois")

    def test_image_ocr(self):
        parsers._cache.clear()
        debut = time.time()
        res = parsers.analyser_fichier(PNG)
        MESURES["image_ocr_s"] = round(time.time() - debut, 2)
        df = res.principal
        self.assertEqual(len(df), 8)
        produits = dict(zip(df["Produit"], df["Chiffre d'affaires (TND)"]))
        self.assertEqual(produits["Ordinateur portable"], 594715)
        quantites = dict(zip(df["Produit"], df["Quantité vendue"]))
        self.assertEqual(quantites["Télévision"], 441)


class TestQuestionsSuggerees(unittest.TestCase):

    def test_selon_domaine(self):
        clients = pd.read_csv(os.path.join(RACINE, "donnees_demo", "demo_clients_banque_synthetique.csv"))
        self.assertIn("Quels clients risquent de partir ?", questions_suggerees(clients, "Banque"))
        self.assertNotIn("Quels clients risquent de partir ?", questions_suggerees(clients, "E-commerce"))
        ventes = parsers.charger_dataframe(os.path.join(RACINE, "uploads", "ventes_demo_dataia.xlsx"))
        q = questions_suggerees(ventes, "Autre")
        self.assertTrue(3 <= len(q) <= 4)
        self.assertIn("Prévois le chiffre d'affaires des 6 prochains mois", q)


class TestUploadApi(unittest.TestCase):
    """Upload PDF et PNG par l'API : type enregistré (migration 003) et aperçu sans calcul automatique."""

    def test_upload_pdf_et_image(self):
        import app as appmod
        from services.db import get_db_connection
        app = appmod.app
        app.config["TESTING"] = True
        email = f"test_formats_{int(time.time())}@test.local"
        c = app.test_client()
        self.assertEqual(c.post("/api/signup", json={"nom_utilisateur": "Test formats", "email": email,
                                                     "password": "Secret123!", "domaine": "Autre"}).status_code, 201)
        c.post("/api/login", json={"email": email, "password": "Secret123!"})
        try:
            for chemin, type_attendu, nb_lignes in ((PDF, "PDF", 12), (PNG, "Image", 8)):
                with open(chemin, "rb") as f:
                    r = c.post("/api/upload", data={"file": (io.BytesIO(f.read()), os.path.basename(chemin))},
                               content_type="multipart/form-data")
                self.assertEqual(r.status_code, 201, r.get_json())
                d = r.get_json()
                self.assertEqual(d["fichier"]["type_fichier"], type_attendu)
                self.assertEqual(d["apercu"]["nb_lignes"], nb_lignes)
                self.assertTrue(3 <= len(d["apercu"]["questions_suggerees"]) <= 4)
                self.assertNotIn("graphique", d)                       # aucun graphique automatique
        finally:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id_utilisateur FROM utilisateurs WHERE email = %s", (email,))
            uid = cur.fetchone()["id_utilisateur"]
            cur.execute("SELECT chemin_fichier FROM fichiers WHERE id_utilisateur = %s", (uid,))
            for f in cur.fetchall():
                p = os.path.join(RACINE, f["chemin_fichier"])
                if os.path.isfile(p):
                    os.remove(p)
            cur.execute("DELETE FROM utilisateurs WHERE id_utilisateur = %s", (uid,))
            conn.commit()
            cur.close()
            conn.close()


@unittest.skipUnless(verifier_ollama()["ok"], "Ollama arrêté")
class TestReponsesAttendues(unittest.TestCase):
    """Les réponses attendues sur le PDF et l'image (calculées par pandas)."""

    @classmethod
    def tearDownClass(cls):
        from services.rag import supprimer_index
        supprimer_index(990100)
        os.makedirs(os.path.join(RACINE, "mesures"), exist_ok=True)
        with open(os.path.join(RACINE, "mesures", "phase7_formats.json"), "w", encoding="utf-8") as f:
            json.dump(MESURES, f, ensure_ascii=False, indent=2)

    def _verifier(self, chemin, question, attendus):
        debut = time.time()
        r = poser(chemin, question)
        MESURES[question] = round(time.time() - debut, 2)
        for a in attendus:
            self.assertIn(a, r.texte, f"{question} -> {r.texte[:300]}")

    def test_pdf(self):
        self._verifier(PDF, "Quel est le CA total de Tunis ?", ["602 532"])
        self._verifier(PDF, "Quel est le mois le plus fort ?", ["Mai", "237 858"])
        self._verifier(PDF, "Quelle est la catégorie la plus forte ?", ["Informatique", "1 037 167"])
        self._verifier(PDF, "ما هو رقم المعاملات الإجمالي لتونس؟", ["602,532"])

    def test_image(self):
        self._verifier(PNG, "Quel est le produit le plus vendu en CA ?", ["Ordinateur portable", "594 715"])
        self._verifier(PNG, "Quelle est la quantité de télévisions ?", ["441"])

    def test_question_texte_rag(self):
        self._verifier(PDF, "Que dit le rapport sur les mois de fin d'année ?", ["novembre", "décembre"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

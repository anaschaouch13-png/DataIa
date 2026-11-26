"""
tests/test_ml.py — Tests automatiques de la Phase 5 (modèles ML par domaine).

Lancer depuis le dossier DataIa (venv activé ; MySQL lancé pour le test d'intégration) :
    python -m unittest tests.test_ml -v
"""

import logging
import os
import sys
import unittest

import numpy as np
import pandas as pd

DOSSIER = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(DOSSIER)
sys.path.insert(0, RACINE)
logging.disable(logging.INFO)

from services.assistant import repondre                                  # noqa: E402
from services.langue import analyser_question                            # noqa: E402
from services.ml import anomalies, churn_banque, forecast, registry      # noqa: E402
from services.parsers import charger_dataframe                           # noqa: E402

DEMO = os.path.join(RACINE, "donnees_demo")
VENTES_DEMO = os.path.join(RACINE, "uploads", "ventes_demo_dataia.xlsx")
ANOMALIES_PLANTEES = {"V00357", "V00403", "V00480", "V00592", "V00788", "V01006", "V01538", "V01743"}


class TestChurn(unittest.TestCase):

    def test_charge_une_seule_fois(self):
        m1, _ = churn_banque.charger()
        m2, _ = churn_banque.charger()
        self.assertIs(m1, m2)
        self.assertEqual(type(m1).__name__, "Pipeline")

    def test_metriques_et_metadonnees(self):
        _, meta = churn_banque.charger()
        for cle in ("features_entree", "categories", "version_sklearn", "metriques_test", "date_entrainement"):
            self.assertIn(cle, meta)
        mt = meta["metriques_test"]
        self.assertGreaterEqual(mt["rappel"], 0.70)          # la majorité des départs sont détectés
        self.assertGreaterEqual(mt["roc_auc"], 0.80)
        self.assertEqual(set(meta["categories"]["country"]), {"France", "Germany", "Spain"})

    def test_fichier_demo_et_colonnes_manquantes(self):
        df = charger_dataframe(os.path.join(DEMO, "demo_clients_banque_synthetique.csv"))
        r = churn_banque.predire_fichier(df)
        self.assertEqual(r.nb_clients, 300)
        self.assertTrue(((r.clients["probabilite_depart"] >= 0) & (r.clients["probabilite_depart"] <= 1)).all())
        with self.assertRaises(churn_banque.ColonnesManquantes) as ctx:
            churn_banque.predire_fichier(df.drop(columns=["age", "balance"]))
        self.assertEqual(ctx.exception.manquantes, ["age", "balance"])
        alias = df.rename(columns={"country": "Geography", "products_number": "NumOfProducts"})
        self.assertEqual(churn_banque.predire_fichier(alias).nb_risque, r.nb_risque)

    def test_client_simule(self):
        risque = churn_banque.predire_client({"age": 55, "products_number": 3, "active_member": 0,
                                              "country": "Germany", "gender": "Female", "balance": 120000})
        sur = churn_banque.predire_client({"age": 30, "products_number": 2, "active_member": 1, "country": "France"})
        self.assertEqual(risque["prediction"], "Risque de départ")
        self.assertEqual(sur["prediction"], "Reste")
        self.assertEqual(len(churn_banque.champs_formulaire()), 10)


class TestPrevision(unittest.TestCase):

    def test_metriques(self):
        m = forecast.calculer_metriques(np.array([100, 200]), np.array([110, 180]))
        self.assertAlmostEqual(m["mae"], 15)                         # (10 + 20) / 2
        self.assertAlmostEqual(m["mape"], 10)                        # (10 % + 10 %) / 2
        self.assertAlmostEqual(m["rmse"], np.sqrt((100 + 400) / 2))

    def test_demo_selection_et_split_temporel(self):
        r = forecast.prevoir(charger_dataframe(os.path.join(DEMO, "demo_ventes_synthetique.csv")), "prévision du CA")
        self.assertEqual((r.frequence, r.nb_periodes), ("mois", 36))
        candidats = [m for m in r.comparaison if m["candidat"]]
        self.assertEqual(r.modele_retenu, min(candidats, key=lambda m: m["mape"])["modele"])
        jeux = r.df_nettoye["jeu"].tolist()
        self.assertEqual(jeux, ["entrainement"] * (36 - r.nb_test) + ["test"] * r.nb_test)   # test = fin de série
        self.assertTrue(r.df_nettoye["periode"].is_monotonic_increasing)
        self.assertTrue((r.previsions["borne_basse"] <= r.previsions["prevision"]).all())

    def test_aberrants_exclus_et_bon_mape(self):
        r = forecast.prevoir(charger_dataframe(VENTES_DEMO), "prévision du chiffre d'affaires")
        self.assertEqual(r.colonne_cible, "chiffre_affaires")
        self.assertTrue(any("5 ligne(s) exclue(s)" in e for e in r.rapport.etapes))
        self.assertLess(r.metriques["mape"], 15)

    def test_historique_insuffisant(self):
        petit = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=5, freq="MS"), "ventes": [1, 2, 3, 4, 5]})
        with self.assertRaises(forecast.HistoriqueInsuffisant):
            forecast.prevoir(petit, "prévision des ventes")


class TestAnomalies(unittest.TestCase):

    def test_ventes_demo_8_anomalies(self):
        r = anomalies.detecter(charger_dataframe(VENTES_DEMO), "anomalies")
        trouvees = set(r.anomalies["id_vente"])
        self.assertEqual(len(trouvees & ANOMALIES_PLANTEES), 7)
        self.assertEqual(len(trouvees - ANOMALIES_PLANTEES), 0)                  # aucun faux positif
        self.assertIn("V00592", set(r.a_surveiller["id_vente"]))                 # la 8e : « à surveiller »

    def test_transactions_demo(self):
        df = charger_dataframe(os.path.join(DEMO, "demo_transactions_anomalies_synthetique.csv"))
        ref = set(pd.read_csv(os.path.join(DEMO, "demo_transactions_anomalies_REPONSES.csv"))["id_transaction"])
        r = anomalies.detecter(df, "anomalies")
        self.assertGreaterEqual(len(ref & set(r.anomalies["id_transaction"])), 6)
        self.assertEqual(ref, ref & (set(r.anomalies["id_transaction"]) | set(r.a_surveiller["id_transaction"])))

    def test_transaction_simulee(self):
        r = anomalies.detecter(charger_dataframe(VENTES_DEMO), "anomalies")
        normale = anomalies.evaluer_transaction(r.modele, {"quantite": 3, "prix_unitaire": 500, "chiffre_affaires": 1500})
        absurde = anomalies.evaluer_transaction(r.modele, {"quantite": 4, "prix_unitaire": 0.01, "chiffre_affaires": 3856})
        self.assertFalse(normale["anomalie"])
        self.assertTrue(absurde["anomalie"])


class TestRegistreEtRoutage(unittest.TestCase):

    def test_registre(self):
        self.assertEqual(registry.modeles_du_domaine("Banque"), ["forecast", "anomaly", "churn"])
        self.assertEqual(registry.modeles_du_domaine("E-commerce"), ["forecast", "anomaly"])
        for cle in registry.MODELES:
            self.assertTrue(callable(registry.lanceur(cle)))

    def test_churn_refuse_hors_banque(self):
        df = charger_dataframe(os.path.join(DEMO, "demo_clients_banque_synthetique.csv"))
        q = "Quels clients risquent de partir ?"
        r = repondre(df, 0, q, analyser_question(q), "E-commerce")
        self.assertEqual(r.intent, "churn")
        self.assertIn("Banque", r.texte)
        self.assertFalse(r.resultats_graphiques)
        r = repondre(df, 0, q, analyser_question(q), "Banque")
        self.assertIn("risque de départ", r.texte)
        self.assertEqual(len(r.resultats_graphiques), 2)

    def test_prevision_et_anomalies_via_chat(self):
        df = charger_dataframe(VENTES_DEMO)
        for q, intent, attendu in [("Prévois le chiffre d'affaires des 6 prochains mois", "forecast", "Précision"),
                                   ("Détecte les anomalies", "anomaly", "anomalie"),
                                   ("توقع رقم المعاملات", "forecast", "الدقة")]:
            with self.subTest(question=q):
                r = repondre(df, 0, q, analyser_question(q), "Autre")
                self.assertEqual(r.intent, intent)
                self.assertIn(attendu, r.texte)


class TestIntegrationBase(unittest.TestCase):
    """/ask_ia -> modeles_ml -> téléchargement sécurisé (les lignes créées sont supprimées à la fin)."""

    def test_parcours_complet(self):
        import app as appmod
        from services.db import get_db_connection
        app = appmod.app
        app.config["TESTING"] = True
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id_utilisateur FROM utilisateurs WHERE domaine = 'Banque' LIMIT 1")
        banque = cur.fetchone()
        if not banque:
            self.skipTest("aucun utilisateur du domaine Banque")
        uid = banque["id_utilisateur"]
        chemin = os.path.relpath(os.path.join(DEMO, "demo_clients_banque_synthetique.csv"), RACINE)
        cur.execute("INSERT INTO fichiers (id_utilisateur, nom_fichier, chemin_fichier, type_fichier) "
                    "VALUES (%s, 'clients_test_ml.csv', %s, 'CSV')", (uid, chemin))
        fid = cur.lastrowid
        conn.commit()
        crees = {"questions": [], "modeles": []}
        try:
            c = app.test_client()
            with c.session_transaction() as s:
                s["_user_id"], s["_fresh"] = str(uid), True
            d = c.post("/ask_ia", json={"file_id": fid, "question": "Quels clients risquent de partir ?"}).get_json()
            crees["questions"].append(d["id_question"])
            crees["modeles"].append(d["id_modele"])
            self.assertEqual(d["intent"], "churn")
            self.assertEqual(len(d["graphiques"]), 2)
            cur.execute("SELECT type, chemin_donnees_nettoyees FROM modeles_ml WHERE id_modele = %s", (d["id_modele"],))
            ligne = cur.fetchone()
            self.assertEqual(ligne["type"], "churn")
            for fmt in ("csv", "xlsx", "rapport"):
                r = c.get(f"/telecharger/nettoyees/{d['id_modele']}/{fmt}")
                self.assertEqual(r.status_code, 200, fmt)
                r.close()
            self.assertEqual(c.get(f"/telecharger/nettoyees/{d['id_modele']}/..%2F..%2F.env").status_code, 404)
            self.assertIn("clients_test_ml.csv", c.get("/mes_donnees_nettoyees").get_data(as_text=True))
            autre = app.test_client()
            cur.execute("SELECT id_utilisateur FROM utilisateurs WHERE id_utilisateur <> %s AND role = 'utilisateur' "
                        "LIMIT 1", (uid,))
            with autre.session_transaction() as s:
                s["_user_id"], s["_fresh"] = str(cur.fetchone()["id_utilisateur"]), True
            self.assertEqual(autre.get(f"/telecharger/nettoyees/{d['id_modele']}/csv").status_code, 403)
        finally:
            base = None
            for idm in filter(None, crees["modeles"]):
                cur.execute("SELECT chemin_donnees_nettoyees FROM modeles_ml WHERE id_modele = %s", (idm,))
                ligne = cur.fetchone()
                if ligne:
                    base = os.path.splitext(os.path.join(RACINE, ligne["chemin_donnees_nettoyees"]))[0]
                cur.execute("DELETE FROM modeles_ml WHERE id_modele = %s", (idm,))
            for idq in filter(None, crees["questions"]):
                cur.execute("DELETE FROM graphiques WHERE id_question = %s", (idq,))
                cur.execute("DELETE FROM questions WHERE id_question = %s", (idq,))
            cur.execute("DELETE FROM fichiers WHERE id_fichier = %s", (fid,))
            conn.commit()
            cur.close()
            conn.close()
            if base:
                for suffixe in (".csv", ".xlsx", "_rapport.txt"):
                    if os.path.isfile(base + suffixe):
                        os.remove(base + suffixe)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""
tests/test_routeur_hybride.py — Tests automatiques de la Phase 3 (routeur hybride).

Lancer depuis le dossier DataIa (venv activé) :
    python -m unittest tests.test_routeur_hybride -v

Deux groupes :
  * TestCalculsDeterministes : pandas + résolution des colonnes + garde-fou,
    sans LLM (rapide, toujours exécuté).
  * TestCasReelProduitsMagasin / TestVentesSalesData : parcours complet avec le LLM
    (routeur JSON contraint). Ignorés automatiquement si Ollama est arrêté.

CAS RÉEL (observé avant la Phase 3) sur produits_magasin.csv :
    « Quel est le total des ventes ? »   -> le LLM répondait 105.00
    « ما هو مجموع المبيعات؟ »             -> le LLM répondait 106.20 دينار
  Or le fichier n'a PAS de colonne de ventes (price, stock_quantity).
  Valeurs exactes (pandas) : somme(price) = 10,7 ; somme(stock_quantity) = 275 ;
  somme(price × stock_quantity) = 424.
  Attendu : même demande de précision, mêmes valeurs, quelle que soit la langue.
"""

import logging
import os
import sys
import unittest

DOSSIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(DOSSIER))
logging.disable(logging.INFO)

from services import redaction, stats                     # noqa: E402
from services.assistant import repondre                   # noqa: E402
from services.langue import analyser_question             # noqa: E402
from services.llm import verifier_ollama                  # noqa: E402
from services.parsers import charger_dataframe            # noqa: E402
from services.router import liste_par_regles, valider_plan  # noqa: E402
from services.semantique import detecter_groupe, resoudre_mesure  # noqa: E402

import pandas as pd                                        # noqa: E402
from services.stats import Filtre, PlanStat               # noqa: E402

PRODUITS = charger_dataframe(os.path.join(DOSSIER, "donnees", "produits_magasin.csv"))
VENTES = charger_dataframe(os.path.join(DOSSIER, "donnees", "sales_data_1000_rows.xlsx"))

QUESTIONS_VENTES = {
    "fr": "Quel est le total des ventes ?",
    "ar": "ما هو مجموع المبيعات؟",
    "en": "What is the total of sales?",
    "derja_latin": "a3tini el total mta3 el ventes",
}
VALEURS_ATTENDUES = [10.7, 275.0, 424.0]            # price, stock_quantity, price × stock_quantity
VALEURS_INVENTEES = ["105", "106,2", "106.2", "150", "100,3", "100.3"]

OLLAMA_OK = verifier_ollama()["ok"]


class TestCalculsDeterministes(unittest.TestCase):
    """Sans LLM : ce sont ces fonctions qui garantissent l'exactitude."""

    def test_valeurs_exactes_produits(self):
        self.assertAlmostEqual(stats.executer(PRODUITS, PlanStat("sum", "price")).valeur, 10.7)
        self.assertEqual(stats.executer(PRODUITS, PlanStat("sum", "stock_quantity")).valeur, 275)
        self.assertEqual(stats.executer(PRODUITS, PlanStat("sum", "price", "stock_quantity")).valeur, 424)

    def test_ventes_ambigu_identique_dans_toutes_les_langues(self):
        for langue, question in QUESTIONS_VENTES.items():
            analyse = analyser_question(question)
            r = resoudre_mesure(PRODUITS, f"{question}\n{analyse.question_pour_llm}", "price")
            with self.subTest(langue=langue):
                self.assertTrue(r.ambigu, "« ventes » sans colonne de ventes doit demander une précision")
                self.assertEqual([(o["colonne"], o["multiplicateur"]) for o in r.options_precision],
                                 [("price", None), ("stock_quantity", None), ("price", "stock_quantity")])

    def test_ventes_resolu_sur_total_price(self):
        for langue, question in QUESTIONS_VENTES.items():
            analyse = analyser_question(question)
            r = resoudre_mesure(VENTES, f"{question}\n{analyse.question_pour_llm}", "Unit_Price")
            with self.subTest(langue=langue):
                self.assertEqual(r.colonne, "Total_Price")
                self.assertEqual(r.note, "concept")

    def test_colonne_explicite_et_produit(self):
        r = resoudre_mesure(PRODUITS, "Quel est le total de price × stock_quantity ?", None)
        self.assertEqual((r.colonne, r.multiplicateur), ("price", "stock_quantity"))
        r = resoudre_mesure(PRODUITS, "moyenne de stock_quantity", "price")
        self.assertEqual(r.colonne, "stock_quantity")

    def test_operations_pandas(self):
        self.assertEqual(stats.executer(VENTES, PlanStat("sum", "Total_Price")).valeur, VENTES["Total_Price"].sum())
        r = stats.executer(VENTES, PlanStat("count", filtres=[Filtre("Status", "==", "pending")]))
        self.assertEqual(r.valeur, (VENTES["Status"] == "Pending").sum())
        r = stats.executer(VENTES, PlanStat("groupby", "Total_Price", colonne_groupe="Region"))
        attendu = VENTES.groupby("Region")["Total_Price"].sum().sort_values(ascending=False)
        self.assertEqual(r.tableau.iloc[:, 1].tolist(), attendu.tolist())
        r = stats.executer(VENTES, PlanStat("top", "Total_Price", colonne_groupe="Product", n=3))
        self.assertEqual(r.tableau["Product"].tolist(),
                         VENTES.groupby("Product")["Total_Price"].sum().nlargest(3).index.tolist())

    def test_filtres_ancres_dans_la_question(self):
        """Un filtre proposé par le LLM n'est gardé que si sa valeur est écrite dans la question."""
        filtre_invente = {"intent": "stat", "operation": "sum", "colonne": "Total_Price",
                          "filtres": [{"colonne": "Status", "operateur": "==", "valeur": "Pending"}]}
        r = valider_plan(VENTES, filtre_invente, "Quel est le chiffre d'affaires par région ?")
        self.assertEqual(r.plan.filtres, [])
        self.assertEqual(r.filtres_rejetes, ["Status == Pending"])
        self.assertEqual((r.plan.operation, r.plan.colonne_groupe), ("groupby", "Region"))
        r = valider_plan(VENTES, filtre_invente, "Combien de factures ont le statut Pending ?")
        self.assertEqual(len(r.plan.filtres), 1)
        annee = {"operation": "sum", "colonne": "Total_Price",
                 "filtres": [{"colonne": "Date", "operateur": "annee", "valeur": "2023"}]}
        self.assertEqual(len(valider_plan(VENTES, annee, "total des ventes en 2023").plan.filtres), 1)
        self.assertEqual(len(valider_plan(VENTES, annee, "total des ventes").plan.filtres), 0)
        mois = {"operation": "sum", "colonne": "Total_Price",
                "filtres": [{"colonne": "Date", "operateur": "mois", "valeur": "mars"}]}
        r = valider_plan(VENTES, mois, "total des ventes en mars")
        self.assertEqual([(f.operateur, f.valeur) for f in r.plan.filtres], [("mois", "3")])

    def test_regroupement_detecte_dans_toutes_les_langues(self):
        for question, attendu in [("Quel est le chiffre d'affaires par région ?", "Region"),
                                  ("ما هو رقم المعاملات حسب المنطقة؟", "Region"),
                                  ("What are the top 3 products by total sales?", "Product"),
                                  ("أفضل 3 منتجات حسب المبيعات", "Product"),
                                  ("Combien de factures par statut ?", "Status")]:
            with self.subTest(question=question):
                self.assertEqual(detecter_groupe(VENTES, question), attendu)

    def test_liste_des_valeurs_par_pandas(self):
        """« Quelles sont les régions ? » : liste exacte (avant : 4 régions sur 5 via le RAG)."""
        for question, attendu in [("Quelles sont les régions présentes dans le fichier ?", "Region"),
                                  ("Which payment methods are used in this file?", "Payment_Method"),
                                  ("ما هي المناطق الموجودة في الملف؟", "Region"),
                                  ("chnowa el produits elli fama fil fichier?", "Product"),
                                  ("شنوة المنتوجات اللي فما في الملف؟", "Product")]:
            analyse = analyser_question(question)
            with self.subTest(question=question):
                self.assertEqual(liste_par_regles(VENTES, analyse.question_pour_llm), attendu)
                r = repondre(VENTES, 999002, question, analyse, "Autre")      # sans appel au LLM
                self.assertEqual(sorted(l[attendu] for l in r.resultat["tableau"]),
                                 sorted(VENTES[attendu].unique().tolist()))
        # Pièges : calcul ou filtre -> ce n'est pas une simple liste
        for question in ["Quel produit a le plus de ventes ?", "Quels clients ont le statut Pending ?",
                         "Quel est le total des ventes ?"]:
            with self.subTest(question=question):
                self.assertIsNone(liste_par_regles(VENTES, question))

    def test_types_de_colonnes(self):
        self.assertFalse(stats.est_numerique(VENTES, "Invoice_ID"))   # « INV-10001 » n'est pas un nombre
        valeurs = stats.en_numerique(pd.Series(["1 200,50", "1,200.50", "1.234,56", "12%", "100 DT", "INV-1"])).tolist()
        self.assertEqual(valeurs[:5], [1200.5, 1200.5, 1234.56, 12.0, 100.0])
        self.assertTrue(pd.isna(valeurs[5]))

    def test_garde_fou_reformulation(self):
        autorises = VALEURS_ATTENDUES
        self.assertTrue(redaction.reformulation_valide("Le total est de 424.", autorises))
        self.assertTrue(redaction.reformulation_valide("المجموع هو ٤٢٤", autorises))
        self.assertFalse(redaction.reformulation_valide("Le total des ventes est de 105,00.", autorises))
        self.assertFalse(redaction.reformulation_valide("مجموع المبيعات هو 106.20 دينار", autorises))


@unittest.skipUnless(OLLAMA_OK, "Ollama arrêté : tests avec LLM ignorés")
class TestCasReelProduitsMagasin(unittest.TestCase):
    """Parcours complet (routeur LLM + pandas) sur le cas réel."""

    def test_meme_reponse_quelle_que_soit_la_langue(self):
        for langue, question in QUESTIONS_VENTES.items():
            analyse = analyser_question(question)
            reponse = repondre(PRODUITS, 999001, question, analyse, "Autre")
            with self.subTest(langue=langue):
                self.assertEqual(reponse.intent, "stat")
                self.assertTrue(reponse.demande_precision)
                valeurs = [round(o["valeur"], 2) for o in reponse.resultat["options"]]
                self.assertEqual(valeurs, VALEURS_ATTENDUES)
                for faux in VALEURS_INVENTEES:
                    self.assertNotIn(faux, reponse.texte, f"valeur inventée {faux} dans la réponse")
                self.assertEqual(len(reponse.suggestions), 3)

    def test_suggestion_cliquee_donne_424(self):
        for question in ["Quel est le total de price × stock_quantity ?", "ما هو مجموع price × stock_quantity؟"]:
            reponse = repondre(PRODUITS, 999001, question, analyser_question(question), "Autre")
            with self.subTest(question=question):
                self.assertEqual(reponse.resultat["valeur"], 424.0)
                self.assertIn("424", reponse.texte)
                self.assertIn("price × stock_quantity", reponse.texte)


@unittest.skipUnless(OLLAMA_OK, "Ollama arrêté : tests avec LLM ignorés")
class TestVentesSalesData(unittest.TestCase):
    """Quand une colonne de ventes existe : elle est choisie et indiquée dans la réponse."""

    @classmethod
    def tearDownClass(cls):
        from services.rag import supprimer_index
        supprimer_index(999002)      # index FAISS temporaire créé par le test RAG

    def test_total_ventes_identique_et_explique(self):
        attendu = float(VENTES["Total_Price"].sum())
        for langue in ("fr", "ar", "en"):
            question = QUESTIONS_VENTES[langue]
            reponse = repondre(VENTES, 999002, question, analyser_question(question), "Autre")
            with self.subTest(langue=langue):
                self.assertEqual(reponse.intent, "stat")
                self.assertEqual(reponse.resultat["valeur"], attendu)
                self.assertEqual(reponse.resultat["mesure"], "Total_Price")
                self.assertIn("`Total_Price`", reponse.texte)    # « calculé sur la colonne X »

    def test_questions_du_banc_de_mesure(self):
        """Les questions du banc avant/après : valeurs comparées à pandas exécuté directement."""
        q = "Quel est le chiffre d'affaires par région ?"
        r = repondre(VENTES, 999002, q, analyser_question(q), "Autre")
        attendu = VENTES.groupby("Region")["Total_Price"].sum().sort_values(ascending=False)
        self.assertEqual(r.resultat["filtres"], [])
        self.assertEqual([l["Region"] for l in r.resultat["tableau"]], attendu.index.tolist())
        self.assertEqual([l["sum(Total_Price)"] for l in r.resultat["tableau"]], attendu.tolist())

        q = "Combien de factures ont le statut Pending ?"
        r = repondre(VENTES, 999002, q, analyser_question(q), "Autre")
        self.assertEqual(r.resultat["valeur"], float((VENTES["Status"] == "Pending").sum()))

        q = "What are the top 3 products by total sales?"
        r = repondre(VENTES, 999002, q, analyser_question(q), "Autre")
        self.assertEqual([l["Product"] for l in r.resultat["tableau"]],
                         VENTES.groupby("Product")["Total_Price"].sum().nlargest(3).index.tolist())

    def test_rag_identifiant_exact(self):
        """Question texte sur un identifiant : la recherche hybride retrouve la bonne ligne."""
        from services.rag import lignes_exactes
        self.assertEqual(lignes_exactes(VENTES, "Qui est le client de la facture INV-10002 ?"), [1])
        q = "Qui est le client de la facture INV-10002 et quel produit a-t-il acheté ?"
        r = repondre(VENTES, 999002, q, analyser_question(q), "Autre")
        self.assertEqual(r.intent, "text")
        self.assertIn("Gamma Store", r.texte)
        self.assertIn("Router", r.texte)

    def test_modele_hors_domaine(self):
        question = "Quels clients risquent de partir ?"
        reponse = repondre(VENTES, 999002, question, analyser_question(question), "E-commerce")
        self.assertEqual(reponse.intent, "churn")
        self.assertIn("Banque", reponse.texte)


if __name__ == "__main__":
    unittest.main(verbosity=2)

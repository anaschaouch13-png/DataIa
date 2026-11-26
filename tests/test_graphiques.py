"""
tests/test_graphiques.py — Tests automatiques de la Phase 4 (moteur de graphiques).

Lancer depuis le dossier DataIa (venv activé) :
    python -m unittest tests.test_graphiques -v

Principe vérifié : CHAQUE valeur dessinée est recalculée ici avec pandas et comparée
à la figure (aucune valeur ne vient du LLM). Les questions de ce fichier sont
résolues par les règles (pas d'appel au LLM) sauf mention contraire.
"""

import base64
import logging
import os
import sys
import unittest

import numpy as np

DOSSIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(DOSSIER))
logging.disable(logging.INFO)

from services import charts                                # noqa: E402
from services.langue import analyser_question              # noqa: E402
from services.parsers import charger_dataframe             # noqa: E402
from services.router import intent_par_regles              # noqa: E402
from services.stats import en_dates                        # noqa: E402

VENTES = charger_dataframe(os.path.join(DOSSIER, "donnees", "sales_data_1000_rows.xlsx"))
PRODUITS = charger_dataframe(os.path.join(DOSSIER, "donnees", "produits_magasin.csv"))


def valeurs(trace, cle):
    """Valeurs d'une trace Plotly (gère l'encodage binaire « bdata » de plotly 6)."""
    v = trace.get(cle)
    if isinstance(v, dict) and "bdata" in v:
        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"])).tolist()
    return list(v)


def generer(question, df=VENTES):
    analyse = analyser_question(question)
    return charts.generer(df, analyse.question_pour_llm, analyse.langue_reponse)


class TestValeursCalculeesParPandas(unittest.TestCase):
    """Les valeurs de la figure = pandas exécuté directement."""

    def test_camembert_par_region(self):
        r = generer("Montre les ventes par région en camembert")
        attendu = VENTES.groupby("Region")["Total_Price"].sum().sort_values(ascending=False)
        trace = r.figure["data"][0]
        self.assertEqual(trace["type"], "pie")
        self.assertEqual(trace["labels"], attendu.index.tolist())
        self.assertEqual(valeurs(trace, "values"), attendu.tolist())

    def test_barres_groupees(self):
        r = generer("barres groupées des ventes par région et par catégorie")
        pivot = VENTES.pivot_table(index="Region", columns="Category", values="Total_Price", aggfunc="sum")
        for trace in r.figure["data"]:
            with self.subTest(categorie=trace["name"]):
                attendu = pivot[trace["name"]].reindex(trace["x"]).tolist()
                self.assertEqual(valeurs(trace, "y"), attendu)
        self.assertEqual(r.figure["layout"]["barmode"], "group")

    def test_barres_empilees(self):
        r = generer("barres empilées des ventes par catégorie et par statut")
        self.assertEqual(r.figure["layout"]["barmode"], "stack")
        total_dessine = sum(sum(valeurs(t, "y")) for t in r.figure["data"])
        self.assertEqual(total_dessine, VENTES["Total_Price"].sum())

    def test_courbe_mensuelle(self):
        r = generer("évolution des ventes par mois")
        mois = en_dates(VENTES["Date"]).dt.to_period("M")
        attendu = VENTES.groupby(mois)["Total_Price"].sum().sort_index()
        self.assertEqual(valeurs(r.figure["data"][0], "y"), attendu.tolist())

    def test_nombre_de_lignes_par_statut(self):
        r = generer("Graphique du nombre de factures par statut")
        attendu = VENTES["Status"].value_counts()
        trace = r.figure["data"][0]
        self.assertEqual(dict(zip(trace["labels"], valeurs(trace, "values"))), attendu.to_dict())

    def test_heatmap_correlations(self):
        r = generer("heatmap de corrélation")
        trace = r.figure["data"][0]
        colonnes = trace["x"]
        attendu = VENTES[colonnes].corr().values
        z = np.array(trace["z"]) if not isinstance(trace["z"], dict) else \
            np.frombuffer(base64.b64decode(trace["z"]["bdata"]), dtype=trace["z"]["dtype"]).reshape(attendu.shape)
        np.testing.assert_allclose(z, attendu, rtol=1e-9)
        self.assertNotIn("Invoice_ID", colonnes)          # identifiant exclu

    def test_histogramme_et_boite(self):
        r = generer("histogramme de Total_Price")
        self.assertEqual(sorted(valeurs(r.figure["data"][0], "x")), sorted(VENTES["Total_Price"].tolist()))
        r = generer("boîte à moustaches des ventes par région")
        self.assertEqual({t["name"] for t in r.figure["data"]}, set(VENTES["Region"].unique()))

    def test_nuage_de_points(self):
        r = generer("nuage de points entre Quantity et Total_Price")
        self.assertEqual((r.spec["x"], r.spec["y"]), ("Quantity", "Total_Price"))   # ordre de la question
        self.assertIn(charts.formater_nombre(round(VENTES["Quantity"].corr(VENTES["Total_Price"]), 3), "fr"), r.texte)

    def test_filtres_ancres(self):
        r = generer("graphique des ventes à Tunis par catégorie")
        attendu = VENTES[VENTES["Region"] == "Tunis"].groupby("Category")["Total_Price"].sum()
        trace = r.figure["data"][0]
        self.assertEqual(dict(zip(trace["labels"], valeurs(trace, "values"))), attendu.to_dict())


class TestTypesEtRegles(unittest.TestCase):

    def test_les_11_variantes(self):
        cas = {"bar": "Graphique en barres des ventes par produit",
               "bar_groupe": "barres groupées des ventes par région et par catégorie",
               "bar_empile": "barres empilées des ventes par catégorie et par statut",
               "line": "évolution des ventes par mois", "area": "aire des ventes par mois par catégorie",
               "pie": "Montre les ventes par région en camembert", "donut": "ventes par catégorie en donut",
               "scatter": "nuage de points entre Quantity et Total_Price", "histogram": "histogramme de Total_Price",
               "box": "boîte à moustaches des ventes par région", "heatmap": "heatmap de corrélation"}
        for attendu, question in cas.items():
            with self.subTest(type=attendu):
                r = generer(question)
                self.assertEqual(r.spec["type"], attendu)
                self.assertEqual(r.spec["source_colonnes"], "regles")   # aucun appel au LLM
                self.assertTrue(r.figure["data"])

    def test_choix_automatique(self):
        for question, attendu, raison in [
                ("évolution des ventes par mois", "line", "auto_line"),                 # date + nombre
                ("Graphique des ventes par région", "pie", "auto_pie"),                 # 5 catégories ≤ 6
                ("Graphique des ventes par produit", "bar", "auto_bar"),                # 8 catégories > 6
                ("Graphique des ventes par région et par catégorie", "bar_groupe", "auto_bar_groupe"),
                ("graphique de Quantity et Total_Price", "scatter", "auto_scatter"),     # 2 nombres
                ("graphique de Total_Price", "histogram", "auto_histogram"),            # 1 nombre
                ("graphique de Quantity, Unit_Price et Total_Price", "heatmap", "auto_heatmap")]:   # ≥ 3 nombres
            with self.subTest(question=question):
                r = generer(question)
                self.assertEqual((r.spec["type"], r.spec["raison"]), (attendu, raison))
                self.assertIn("automatiquement", r.texte)        # la raison est expliquée

    def test_type_demande_incompatible(self):
        r = generer("courbe des ventes par région")                  # pas de date sur l'axe X
        self.assertEqual((r.spec["incompatibilite"], r.spec["type"]), ("inc_ligne_sans_date", "bar"))
        self.assertIn("courbe", r.texte)
        self.assertIn("à la place", r.texte)
        r = generer("nuage de points des ventes")                     # une seule colonne numérique
        self.assertEqual(r.spec["incompatibilite"], "inc_nuage")
        r = generer("histogramme des ventes par région")              # catégories -> barres
        self.assertEqual((r.spec["incompatibilite"], r.spec["type"]), ("inc_histogramme_categories", "bar"))
        # Donut dont une PART (total par catégorie) est négative -> barres, pas un camembert
        import pandas as pd
        marges = pd.DataFrame({"Category": ["A", "A", "B", "B", "C"], "Total_Price": [100, 50, -80, 20, 30]})
        r = generer("Total_Price par Category en donut", marges)
        self.assertEqual((r.spec["incompatibilite"], r.spec["type"]), ("inc_camembert_negatif", "bar"))
        r = generer("Graphique de Total_Price par Category", marges)          # choix automatique : pas de camembert
        self.assertEqual(r.spec["type"], "bar")
        # Quelques lignes négatives (remboursements) mais tous les totaux positifs -> le camembert est accepté
        from services.parsers import charger_dataframe as charger
        demo = charger(os.path.join(os.path.dirname(DOSSIER), "uploads", "ventes_demo_dataia.xlsx"))
        self.assertTrue((demo["chiffre_affaires"] < 0).any())
        r = generer("ventes par catégorie en donut", demo)
        self.assertEqual((r.spec["incompatibilite"], r.spec["type"]), ("", "donut"))
        r = generer("courbe des prix", PRODUITS)                      # aucune date dans le fichier
        self.assertEqual(r.spec["incompatibilite"] if r.spec else "", "inc_ligne_aucune_date")

    def test_suggestions_reroutables(self):
        """Chaque suggestion, une fois cliquée, produit bien le type annoncé."""
        r = generer("Montre les ventes par région en camembert")
        self.assertTrue(r.suggestions)
        for suggestion in r.suggestions:
            with self.subTest(suggestion=suggestion):
                self.assertEqual(intent_par_regles(suggestion), "graph")
                r2 = generer(suggestion)
                self.assertFalse(r2.spec["incompatibilite"])
                self.assertEqual(r2.spec["raison"], "demande")

    def test_ventes_ambigu_demande_precision(self):
        r = generer("graphique des ventes par catégorie", PRODUITS)
        self.assertTrue(r.demande_precision)
        self.assertIsNone(r.figure)
        self.assertEqual(len(r.suggestions), 3)


class TestLangues(unittest.TestCase):

    def test_meme_graphique_dans_4_langues(self):
        questions = {"fr": "graphique des ventes par région", "en": "chart of sales by region",
                     "ar": "ارسم مخطط المبيعات حسب المنطقة", "derja": "orsomli graphique mta3 el ventes par région"}
        specs = {}
        for langue, q in questions.items():
            with self.subTest(langue=langue):
                self.assertEqual(intent_par_regles(analyser_question(q).question_pour_llm), "graph")
                r = generer(q)
                specs[langue] = (r.spec["type"], r.spec["x"], r.spec["y"], r.spec["agg"])
                trace = r.figure["data"][0]
                self.assertEqual(sum(valeurs(trace, "values")), VENTES["Total_Price"].sum())
        self.assertEqual(len(set(specs.values())), 1, specs)


class TestAncienFormatEtExport(unittest.TestCase):

    def test_nettoyage_ancien_format(self):
        texte = ('Voici :\n```json\n{"type_graph": "pie", "title": "CA", "data": {"x": ["Bizerte", "Sousse"], '
                 '"y": [11748, 11748]}}\n```\nExplication.')
        propre, ancien = charts.nettoyer_ancien_format(texte)
        self.assertTrue(ancien)
        self.assertNotIn("type_graph", propre)
        self.assertIn("Explication", propre)

    def test_export_png_avec_chrome_installe(self):
        r = generer("Montre les ventes par région en camembert")
        png = charts.exporter_png(r.figure, None)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertGreater(len(png), 10_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)

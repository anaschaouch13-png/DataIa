"""
Banc de mesure de la Phase 4 : temps de génération d'un graphique, étape par étape.

Usage (depuis DataIa/, venv activé, Ollama lancé) :
    python tests/benchmark_graphiques.py
Résultats : mesures/phase4_graphiques.json

Étapes mesurées pour chaque demande (parcours complet services.assistant.repondre) :
  - routage (règles, ou LLM si besoin), spec du graphique (règles, ou LLM si besoin),
  - calcul pandas + construction de la figure Plotly, taille du JSON envoyé au navigateur,
  - export PNG (kaleido + Chrome installé) : 1er export (Chrome démarre) puis exports suivants.
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
logging.disable(logging.INFO)

from services import charts                                   # noqa: E402
from services.assistant import repondre                       # noqa: E402
from services.langue import analyser_question                 # noqa: E402
from services.parsers import charger_dataframe                # noqa: E402

DF = charger_dataframe(os.path.join("tests", "donnees", "sales_data_1000_rows.xlsx"))
DEMANDES = [
    "Graphique en barres des ventes par produit",
    "barres groupées des ventes par région et par catégorie",
    "barres empilées des ventes par catégorie et par statut",
    "graphique de l'évolution des ventes par mois",
    "aire des ventes par mois par catégorie",
    "Montre les ventes par région en camembert",
    "ventes par catégorie en donut",
    "nuage de points entre Quantity et Total_Price",
    "histogramme de Total_Price",
    "boîte à moustaches des ventes par région",
    "heatmap de corrélation",
    "courbe des ventes par région",                    # type incompatible -> remplacé
    "ارسم مخطط المبيعات حسب المنطقة",                  # arabe
    "courbe des ventes",                               # courbe + colonne date : axe X évident (règle)
    "graphique des ventes",                            # axe X ambigu -> spec proposée par le LLM
]

# Préchauffage du LLM (non mesuré) pour ne pas compter le chargement du modèle
repondre(DF, 0, "Quel est le total des ventes ?", analyser_question("Quel est le total des ventes ?"), "Autre")

resultats = []
for q in DEMANDES:
    analyse = analyser_question(q)
    debut = time.time()
    r = repondre(DF, 0, q, analyse, "Autre")
    total = time.time() - debut
    t = r.temps
    ligne = {"demande": q, "type": (r.graphique or {}).get("spec", {}).get("type"),
             "total_s": round(total, 2), "routage_s": t.get("routage_s"),
             "spec_s": t.get("graphique_spec_s"), "spec_par": t.get("graphique_spec_par"),
             "pandas_figure_s": t.get("graphique_donnees_et_figure_s"),
             "json_ko": t.get("graphique_taille_json_ko"), "appels_llm": len(t.get("appels_llm", []))}
    if r.graphique:
        debut = time.time()
        charts.exporter_png(r.graphique["figure"], None)
        ligne["png_s"] = round(time.time() - debut, 2)
    resultats.append(ligne)
    print(json.dumps(ligne, ensure_ascii=False), flush=True)

os.makedirs("mesures", exist_ok=True)
with open(os.path.join("mesures", "phase4_graphiques.json"), "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)

sans_llm = [r["total_s"] for r in resultats if r["appels_llm"] == 0]
avec_llm = [r["total_s"] for r in resultats if r["appels_llm"] > 0]
png = [r["png_s"] for r in resultats if "png_s" in r]
print(f"\nSans LLM : {len(sans_llm)} graphiques, moyenne {sum(sans_llm) / len(sans_llm):.2f} s")
if avec_llm:
    print(f"Avec LLM : {len(avec_llm)} graphique(s), moyenne {sum(avec_llm) / len(avec_llm):.2f} s")
print(f"PNG : 1er export {png[0]} s (démarrage de Chrome), suivants {sum(png[1:]) / len(png[1:]):.2f} s en moyenne")

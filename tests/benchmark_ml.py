"""
Banc de mesure de la Phase 5 : temps d'exécution des modèles ML (parcours chat complet, sans base).
Usage (dossier DataIa, venv activé, Ollama lancé) : python tests/benchmark_ml.py
Résultats : mesures/phase5_ml.json
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
logging.disable(logging.INFO)

from services.assistant import repondre                        # noqa: E402
from services.langue import analyser_question                  # noqa: E402
from services.parsers import charger_dataframe                 # noqa: E402

CAS = [
    ("uploads/ventes_demo_dataia.xlsx", "Prévois le chiffre d'affaires des 6 prochains mois", "Autre"),
    ("donnees_demo/demo_ventes_synthetique.csv", "Prévois le chiffre d'affaires des 6 prochains mois", "Autre"),
    ("uploads/ventes_demo_dataia.xlsx", "Détecte les anomalies", "Autre"),
    ("donnees_demo/demo_transactions_anomalies_synthetique.csv", "Détecte les anomalies", "Autre"),
    ("donnees_demo/demo_clients_banque_synthetique.csv", "Quels clients risquent de partir ?", "Banque"),
    ("../a_integrer/modele_banque/Bank-Customer-Churn-Prediction.csv", "Quels clients risquent de partir ?", "Banque"),
]
resultats = []
for fichier, question, domaine in CAS:
    df = charger_dataframe(fichier)
    for passage in (1, 2):
        debut = time.time()
        r = repondre(df, 0, question, analyser_question(question), domaine)
        ligne = {"fichier": os.path.basename(fichier), "lignes": len(df), "question": question, "passage": passage,
                 "intent": r.intent, "total_s": round(time.time() - debut, 2), "modele_s": r.temps.get("modele_ml_s"),
                 "appels_llm": len(r.temps.get("appels_llm", [])), "graphiques": len(r.resultats_graphiques)}
        resultats.append(ligne)
        print(json.dumps(ligne, ensure_ascii=False), flush=True)
os.makedirs("mesures", exist_ok=True)
with open(os.path.join("mesures", "phase5_ml.json"), "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)

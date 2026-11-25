"""
Benchmark avant/après Phase 3 : mêmes questions, même ordre, temps + tokens + exactitude.
Usage (depuis DataIa/, venv activé) : python tests/benchmark_routeur.py <etiquette>
Résultats écrits dans mesures/phase3_<etiquette>.json.
Utilise les fichiers réels 35 (utilisateur 13) et 31 (utilisateur 1) ; les questions
de test sont supprimées de l'historique à la fin.
"""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
import logging; logging.disable(logging.INFO)

ETIQUETTE = sys.argv[1]
import app as appmod
from services.db import get_db_connection
import services.llm as llm

# Capture des métadonnées Ollama (tokens du prompt, durée) de chaque appel LLM
APPELS = []
_orig_invoke = type(llm.get_chat_llm()).invoke
def _invoke_trace(self, *a, **k):
    r = _orig_invoke(self, *a, **k)
    m = r.response_metadata or {}
    APPELS.append({"prompt_tokens": m.get("prompt_eval_count"), "sortie_tokens": m.get("eval_count"),
                   "duree_s": round((m.get("total_duration") or 0) / 1e9, 1)})
    return r
type(llm.get_chat_llm()).invoke = _invoke_trace

app = appmod.app; app.config["TESTING"] = True
def client(uid):
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = str(uid); s["_fresh"] = True
    return c

conn = get_db_connection(); cur = conn.cursor()
cur.execute("SELECT COALESCE(MAX(id_question),0) FROM questions"); max_q = cur.fetchone()[0]; cur.close(); conn.close()

QUESTIONS = [
    # (utilisateur, fichier, question, valeur exacte attendue pour info)
    (13, 35, "Quel est le total des ventes ?", "pas de colonne ventes : price=10,7 / stock=275 / price×stock=424"),
    (13, 35, "ما هو مجموع المبيعات؟", "idem"),
    (1, 31, "Quel est le total des ventes ?", "somme Total_Price"),
    (1, 31, "Quel est le chiffre d'affaires par région ?", "groupby Region sum Total_Price"),
    (1, 31, "Combien de factures ont le statut Pending ?", "count Status == Pending"),
    (1, 31, "What are the top 3 products by total sales?", "top 3 Product sum Total_Price"),
]

# Préchauffage (non mesuré) : charge le modèle dans le mode du pipeline testé
client(1).post("/ask_ia", json={"file_id": 31, "question": "Bonjour"})
APPELS.clear()

resultats = []
for uid, fid, q, attendu in QUESTIONS:
    APPELS.clear()
    t = time.time()
    r = client(uid).post("/ask_ia", json={"file_id": fid, "question": q})
    duree = time.time() - t
    d = r.get_json()
    resultats.append({"question": q, "fichier": fid, "duree_s": round(duree, 1),
                      "appels_llm": list(APPELS), "intent": d.get("intent"),
                      "reponse": (d.get("answer") or d.get("message", ""))[:600], "attendu": attendu})
    print(f"[{duree:5.1f}s] {q}\n   appels LLM: {APPELS}\n   -> {resultats[-1]['reponse'][:300]!r}\n", flush=True)

conn = get_db_connection(); cur = conn.cursor()
cur.execute("DELETE FROM questions WHERE id_question > %s", (max_q,)); conn.commit(); cur.close(); conn.close()

dossier = os.path.join(os.getcwd(), "mesures")
os.makedirs(dossier, exist_ok=True)
with open(os.path.join(dossier, f"phase3_{ETIQUETTE}.json"), "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)
tps = [r["duree_s"] for r in resultats]
print(f"MOYENNE {ETIQUETTE}: {sum(tps)/len(tps):.1f}s  (min {min(tps)}s, max {max(tps)}s)")

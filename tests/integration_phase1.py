"""
tests/integration_phase1.py — tests d'intégration de la Phase 1 (base MySQL réelle, client de test Flask).
Lancer depuis le dossier DataIa : python tests/integration_phase1.py
Les questions / comptes créés pendant le test sont supprimés à la fin.
"""
import os, sys, time
sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")
import logging; logging.disable(logging.INFO)

import app as appmod
from services.db import get_db_connection
import services.llm as llm

app = appmod.app
app.config["TESTING"] = True

conn = get_db_connection(); cur = conn.cursor()
cur.execute("SELECT COALESCE(MAX(id_question),0) FROM questions"); max_q = cur.fetchone()[0]
cur.close(); conn.close()

res = []
def check(nom, ok, detail=""):
    res.append((nom, ok, detail)); print(("OK  " if ok else "ECHEC"), nom, "|", detail)

def client_pour(uid):
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = str(uid); s["_fresh"] = True
    return c

# --- pandas 3 : la nouvelle dtype "str" est-elle vue comme catégorie ?
import pandas as pd
df = pd.read_excel("uploads/sales_data_1000_rows.xlsx")
from services.assistant import resume_categories   # déplacée en Phase 3
check("resume_categories voit les colonnes texte (pandas 3)", "Region" in resume_categories(df))

u1 = client_pour(1)
check("dashboard utilisateur", u1.get("/dashboard").status_code == 200)
r = u1.get("/api/sante"); check("/api/sante", r.status_code == 200, r.get_json())

# --- Sécurité
r = u1.post("/ask_ia", json={"file_id": 32, "question": "total ?"})
check("IDOR ask_ia : fichier d'un autre utilisateur refusé", r.status_code == 404, r.get_json()["message"])
check("view_report traversal ../.env", u1.get("/view_report/../.env").status_code == 404)
check("view_report chemin absolu système", u1.get("/view_report/C:/Windows/win.ini").status_code == 404)
check("view_report rapport d'un autre utilisateur", u1.get("/view_report/uploads%5Crapports%5CRapport_U10_20260401_010834.pdf").status_code == 403)
check("toggle_user par non-admin", u1.post("/admin/toggle_user/6").status_code == 403)
check("delete_user par non-admin", u1.post("/admin/delete_user/6").status_code == 403)
adm = client_pour(6)
check("admin dashboard (admin)", adm.get("/admin/dashboard").status_code == 200)
check("rapport ancien manquant sur disque -> 404 propre (admin)",
      adm.get("/view_report/uploads%5Crapports%5CRapport_U10_20260401_010834.pdf").status_code == 404)

# --- Questions multilingues (fichier 31 = sales_data de l'utilisateur 1)
questions = [
    ("fr", "Quelles sont les régions présentes dans le fichier ?"),
    ("en", "Which payment methods are used in this file?"),
    ("fr", "Quel est le total des ventes ?"),
    ("ar", "ما هي المناطق الموجودة في الملف؟"),
    ("derja_latin", "chnowa el produits elli fama fil fichier?"),
    ("derja_ar", "شنوة المنتوجات اللي فما في الملف؟"),
]
for attendu, q in questions:
    t = time.time()
    r = u1.post("/ask_ia", json={"file_id": 31, "question": q})
    d = r.get_json()
    ok = r.status_code == 200 and d.get("langue") == attendu
    check(f"ask_ia [{attendu}] ({time.time()-t:.0f}s)", ok,
          (d.get("answer") or d.get("message", ""))[:260].replace("\n", " "))

# --- Ollama arrêté (simulé : URL vers un port fermé)
url = llm.OLLAMA_BASE_URL
llm.OLLAMA_BASE_URL = "http://localhost:1"
llm._DERNIERE_VERIF_OK.clear()   # Phase 3 : vérification gardée en cache 30 s
for lang, q in [("fr", "Quel est le total ?"), ("ar", "ما هو المجموع؟")]:
    r = u1.post("/ask_ia", json={"file_id": 31, "question": q})
    check(f"Ollama arrêté -> 503 message clair [{lang}]", r.status_code == 503, r.get_json()["message"])
llm.OLLAMA_BASE_URL = url

# --- Déconnexion
check("logout redirige vers login", "/login" in u1.get("/logout").headers.get("Location", ""))
r = u1.get("/dashboard"); check("page protégée après logout -> login", r.status_code == 302 and "/login" in r.headers["Location"])

# --- Nettoyage : suppression des questions de test
conn = get_db_connection(); cur = conn.cursor()
cur.execute("DELETE FROM questions WHERE id_question > %s", (max_q,)); conn.commit()
print(f"\n{cur.rowcount} question(s) de test supprimée(s).")
cur.close(); conn.close()
print(f"BILAN : {sum(o for _, o, _ in res)}/{len(res)} tests OK")

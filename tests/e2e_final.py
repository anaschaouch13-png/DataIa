"""
tests/e2e_final.py — Test de bout en bout (Phase 9), « comme une vraie utilisatrice ».

Le serveur doit tourner (python app.py) ; MySQL et Ollama lancés. Lancer depuis DataIa :
    python tests/e2e_final.py [--url http://127.0.0.1:5000]

Tout passe par HTTP (requests), comme le navigateur : inscription, connexion, upload,
questions, ML, simulateur, téléchargements, PDF, profil, déconnexion.
Seule exception : la partie administrateur utilise le client de test Flask avec une session
d'administrateur (le mot de passe de l'admin n'est pas connu du script).

Les comptes E2E sont CONSERVÉS (pour pouvoir les ouvrir dans l'interface) :
    e2e.banque@dataia.local / e2e.ecommerce@dataia.local — mot de passe : Demo2026!
Les résultats sont écrits dans mesures/e2e_final.json et mesures/E2E_RESULTATS.md.
"""

import io
import json
import os
import re
import sys
import time

import pdfplumber
import requests

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
from services.parsers import charger_dataframe          # noqa: E402

URL = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://127.0.0.1:5000"
MDP = "Demo2026!"
UP = os.path.join(RACINE, "uploads")
DEMO = os.path.join(RACINE, "donnees_demo")
FICHIERS = {"xlsx": os.path.join(UP, "ventes_demo_dataia.xlsx"), "csv": os.path.join(UP, "ventes_demo_dataia.csv"),
            "pdf": os.path.join(UP, "rapport_ventes_2025.pdf"), "png": os.path.join(UP, "tableau_ventes_2025.png"),
            "clients": os.path.join(DEMO, "demo_clients_banque_synthetique.csv")}
RESULTATS = []
VENTES = charger_dataframe(FICHIERS["xlsx"])


def ligne(etape, attendu, obtenu, ok, remarque="", duree=None):
    RESULTATS.append({"etape": etape, "attendu": attendu, "obtenu": str(obtenu)[:160].replace("\n", " "),
                      "ok": bool(ok), "remarque": remarque, "duree_s": duree})
    print(f"[{'OK' if ok else 'KO'}] {etape} -> {str(obtenu)[:110]!r}" + (f" ({duree} s)" if duree else ""))


def formats(valeur):
    """Écritures possibles d'un entier dans une réponse (fr : espaces, en/ar : virgules)."""
    n = f"{int(valeur):,}"
    return {n, n.replace(",", " "), n.replace(",", " "), n.replace(",", " "), str(int(valeur))}


def contient_nombre(texte, valeur):
    return any(f in texte for f in formats(valeur))


class Utilisatrice:
    def __init__(self, nom, email, domaine):
        self.s = requests.Session()
        self.nom, self.email, self.domaine = nom, email, domaine
        self.fichiers = {}

    def inscrire_et_connecter(self):
        r = self.s.post(f"{URL}/api/signup", json={"nom_utilisateur": self.nom, "email": self.email,
                                                     "password": MDP, "domaine": self.domaine})
        cree = r.status_code
        r = self.s.post(f"{URL}/api/login", json={"email": self.email, "password": MDP})
        user = (r.json() or {}).get("user") or {}
        ligne(f"1. Inscription + connexion {self.domaine}", f"201 (ou 409 si déjà créé), domaine {self.domaine}",
              f"signup {cree}, login {r.status_code}, domaine {user.get('domaine')}",
              cree in (201, 409) and r.status_code == 200 and user.get("domaine") == self.domaine)
        self.id = user.get("id_utilisateur") or user.get("id")

    def upload(self, cle, nom=None):
        chemin = FICHIERS[cle]
        debut = time.time()
        with open(chemin, "rb") as f:
            r = self.s.post(f"{URL}/api/upload", files={"file": (nom or os.path.basename(chemin), f)})
        duree = round(time.time() - debut, 2)
        d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        fichier = d.get("fichier") or {}
        self.fichiers[cle] = fichier.get("id_fichier")
        ap = d.get("apercu") or {}
        nb_sugg = len(ap.get("questions_suggerees") or [])
        ligne(f"2. Upload {cle.upper()} ({self.domaine})", "201, aperçu + questions suggérées",
              f"{r.status_code}, type {fichier.get('type_fichier')}, {nb_sugg} suggestions",
              r.status_code in (200, 201) and self.fichiers[cle] and nb_sugg > 0, duree=duree)

    def demander(self, cle, question, timeout=300):
        debut = time.time()
        try:
            r = self.s.post(f"{URL}/ask_ia", json={"file_id": self.fichiers[cle], "question": question}, timeout=timeout)
            d = r.json()
        except Exception as e:                                # noqa: BLE001
            d = {"answer": f"ERREUR {e}", "intent": None}
        return d, round(time.time() - debut, 2)


def main():
    if requests.get(f"{URL}/api/sante", timeout=30).status_code != 200:
        print("Serveur, MySQL ou Ollama indisponible.")
        return 1
    banque = Utilisatrice("E2E Banque", "e2e.banque@dataia.local", "Banque")
    ecom = Utilisatrice("E2E E-commerce", "e2e.ecommerce@dataia.local", "E-commerce")

    # ---- 1. Inscriptions -------------------------------------------------
    banque.inscrire_et_connecter()
    ecom.inscrire_et_connecter()
    r = requests.post(f"{URL}/api/signup", json={"nom_utilisateur": "x", "email": "x@x.x", "password": "123456",
                                                 "domaine": "Pirate"})
    ligne("1. Inscription avec un domaine hors liste", "400 refusé", r.status_code, r.status_code == 400)

    # ---- 2. Uploads ----------------------------------------------------------
    for cle in ("xlsx", "csv", "pdf", "png", "clients"):
        banque.upload(cle)
    ecom.upload("xlsx")
    ecom.upload("clients")

    # ---- 3. Questions de calcul (4 langues) ---------------------------------
    tunis = VENTES.loc[VENTES["region"] == "Tunis", "chiffre_affaires"].sum()
    for langue, q in [("fr", "Quel est le chiffre d'affaires total à Tunis ?"),
                      ("en", "What is the total revenue in Tunis?"),
                      ("ar", "ما هو مجموع رقم المعاملات في تونس؟"),
                      ("derja", "a3tini el total mta3 el chiffre d'affaires fi Tunis")]:
        d, t = banque.demander("xlsx", q)
        ligne(f"3. Calcul {langue} (xlsx)", f"CA Tunis = {int(tunis):,} (pandas)".replace(",", " "),
              d.get("answer"), contient_nombre(d.get("answer") or "", tunis), f"intent {d.get('intent')}", t)

    cat = VENTES.groupby("categorie")["chiffre_affaires"].sum().sort_values()
    d, t = banque.demander("xlsx", "Quelle est la catégorie la plus forte ?")
    ligne("3. Superlatif (xlsx)", f"{cat.index[-1]} {int(cat.iloc[-1]):,}".replace(",", " "), d.get("answer"),
          cat.index[-1] in (d.get("answer") or "") and contient_nombre(d.get("answer") or "", cat.iloc[-1]), "", t)

    for cle, q, attendus, remarque in [
            ("pdf", "Quel est le CA total de Tunis ?", ["602 532"], ""),
            ("pdf", "Quelle est la catégorie la plus forte ?", ["Informatique", "1 037 167"], ""),
            ("pdf", "Quel est le mois le plus fort ?", ["Mai", "237 858"],
             "Le tableau du PDF donne Mai (Juillet 197 381 = meilleur mois de Tunis), voir JUSTIFICATIONS §57"),
            ("png", "Quel est le produit le plus vendu en CA ?", ["Ordinateur portable", "594 715"], "image OCR"),
            ("png", "Quelle est la quantité de télévisions ?", ["441"], "image OCR")]:
        d, t = banque.demander(cle, q)
        texte = (d.get("answer") or "").replace(" ", " ").replace(" ", " ")
        ligne(f"3. Calcul {cle.upper()} : {q}", " ".join(attendus), d.get("answer"),
              all(a in texte for a in attendus), remarque, t)

    # Graphiques : 9 types (11 variantes)
    for type_attendu, q in [("pie", "Montre les ventes par région en camembert"),
                            ("bar", "Graphique en barres des ventes par produit"),
                            ("bar_groupe", "barres groupées des ventes par région et par catégorie"),
                            ("bar_empile", "barres empilées des ventes par catégorie et par canal"),
                            ("line", "évolution des ventes par mois"),
                            ("area", "aire des ventes par mois par catégorie"),
                            ("donut", "ventes par région en donut"),
                            ("scatter", "nuage de points entre quantite et chiffre_affaires"),
                            ("histogram", "histogramme de chiffre_affaires"),
                            ("box", "boîte à moustaches des ventes par région"),
                            ("heatmap", "heatmap de corrélation")]:
        d, t = banque.demander("xlsx", q)
        obtenu = (d.get("graphique") or {}).get("type")
        ligne(f"3. Graphique {type_attendu}", type_attendu, obtenu, obtenu == type_attendu, "", t)
    for langue, q in [("en", "chart of sales by region"), ("ar", "ارسم مخطط المبيعات حسب المنطقة"),
                      ("derja", "orsomli graphique mta3 el ventes par région")]:
        d, t = banque.demander("xlsx", q)
        g = d.get("graphique") or {}
        ligne(f"3. Graphique {langue}", "graphique ventes par région", g.get("type"), bool(g.get("figure")), "", t)

    # Questions de texte (RAG + LLM)
    for langue, q, mots in [("fr", "Que dit le rapport sur les mois de fin d'année ?", ["novembre", "décembre"]),
                            ("en", "What does the report say about the end of the year?", ["november", "december"]),
                            ("ar", "ماذا يقول التقرير عن نهاية السنة؟", ["نوفمبر", "ديسمبر", "11", "12"])]:
        d, t = banque.demander("pdf", q)
        texte = (d.get("answer") or "").lower()
        ok = any(m in texte for m in mots)
        ligne(f"3. Question texte {langue} (PDF)", " / ".join(mots), d.get("answer"), ok, f"intent {d.get('intent')}", t)

    # ---- 4. ML ---------------------------------------------------------------
    for u in (banque, ecom):
        for q, intent in [("Prévois le chiffre d'affaires des 6 prochains mois", "forecast"),
                          ("Détecte les anomalies", "anomaly")]:
            d, t = u.demander("xlsx", q)
            ligne(f"4. {intent} ({u.domaine})", f"intent {intent}, modèle enregistré",
                  (d.get("answer") or "")[:120], d.get("intent") == intent and d.get("id_modele"), "", t)
    d, t = banque.demander("clients", "Quels clients risquent de partir ?")
    ligne("4. Churn (Banque)", "scores + 2 graphiques", (d.get("answer") or "")[:120],
          d.get("intent") == "churn" and len(d.get("graphiques") or []) == 2 and d.get("id_modele"), "", t)
    d, t = ecom.demander("clients", "Quels clients risquent de partir ?")
    ligne("4. Churn (E-commerce)", "refus poli (réservé Banque)", d.get("answer"),
          d.get("intent") == "churn" and "Banque" in (d.get("answer") or "") and not d.get("graphiques"), "", t)

    # ---- 5. Simulateur -------------------------------------------------------
    for u in (banque, ecom):
        mods = u.s.get(f"{URL}/api/simulateur/modeles", params={"file_id": u.fichiers["xlsx"]}).json()["modeles"]
        for m in mods:
            entrees = {c["nom"]: c.get("defaut") for c in m["champs"] if c.get("defaut") is not None}
            fid = u.fichiers["xlsx"] if m["besoin_fichier"] else None
            r = u.s.post(f"{URL}/api/simulateur/{m['cle']}", json={"file_id": fid, "entrees": entrees})
            res = (r.json() or {}).get("resultat") or {}
            ligne(f"5. Simulateur {m['cle']} ({u.domaine})", "200 + résultat", f"{r.status_code} {str(res)[:90]}",
                  r.status_code == 200 and res)
    r = ecom.s.post(f"{URL}/api/simulateur/churn", json={"entrees": {"age": 50}})
    ligne("5. Simulateur churn (E-commerce)", "403 refusé", r.status_code, r.status_code == 403)

    # ---- 6. Téléchargements --------------------------------------------------
    execs = banque.s.get(f"{URL}/api/donnees_nettoyees").json()["executions"]
    types = sorted({e["type"] for e in execs if e["disponible"]})
    codes = []
    for e in [e for e in execs if e["disponible"]][:3]:
        for fmt, lien in e["liens"].items():
            r = banque.s.get(URL + lien)
            codes.append(r.status_code == 200 and len(r.content) > 100)
    ligne("6. Données nettoyées (csv, xlsx, rapport)", "200 pour chaque lien", f"types {types}, {sum(codes)}/{len(codes)} OK",
          codes and all(codes))
    autre = ecom.s.get(URL + execs[0]["liens"]["csv"]) if execs else None
    ligne("6. Téléchargement d'un autre compte", "403", autre.status_code if autre is not None else "-",
          autre is not None and autre.status_code == 403)

    # ---- 7. PDF complet ------------------------------------------------------
    debut = time.time()
    r = banque.s.post(f"{URL}/api/rapport/{banque.fichiers['xlsx']}/pdf", json={})
    duree = round(time.time() - debut, 2)
    ok, info = False, r.status_code
    if r.status_code == 200:
        with pdfplumber.open(io.BytesIO(r.content)) as doc:
            texte = "\n".join(p.extract_text() or "" for p in doc.pages)
            images = sum(len(p.images) for p in doc.pages)
            pages = len(doc.pages)
        sections = all(s in texte for s in ("Sommaire", "Questions et réponses", "Graphiques",
                                            "Modèles de Machine Learning", "Simulations"))
        arabe = any(0xFE70 <= ord(c) <= 0xFEFF for c in texte)
        ok = sections and arabe and images >= 10
        info = f"{pages} pages, {images} images, {round(len(r.content) / 1024)} Ko, sections {sections}, arabe {arabe}"
    ligne("7. Rapport PDF complet", "sections + graphiques + ML + arabe", info, ok, "", duree)

    # ---- 8. Profil, admin, déconnexion --------------------------------------
    r = banque.s.put(f"{URL}/api/profil", json={"nom_utilisateur": "E2E Banque (modifié)", "domaine": "Banque"})
    me = banque.s.get(f"{URL}/api/me").json()["user"]
    ligne("8. Modifier le profil", "nom mis à jour", f"{r.status_code} {me.get('nom')}",
          r.status_code == 200 and me.get("nom") == "E2E Banque (modifié)")
    banque.s.put(f"{URL}/api/profil", json={"nom_utilisateur": "E2E Banque", "domaine": "Banque"})
    r = banque.s.get(f"{URL}/api/admin/data")
    ligne("8. Admin par une utilisatrice", "403", r.status_code, r.status_code == 403)
    ligne_admin()
    r = banque.s.post(f"{URL}/api/rapport/{ecom.fichiers['xlsx']}/pdf", json={})
    r2 = banque.s.post(f"{URL}/ask_ia", json={"file_id": ecom.fichiers["xlsx"], "question": "total"})
    ligne("8. Fichier d'un autre compte (IDOR)", "404", f"pdf {r.status_code}, ask {r2.status_code}",
          r2.status_code == 404 and r.status_code == 404)
    encore = banque.s.get(f"{URL}/api/me").status_code
    r = banque.s.post(f"{URL}/api/logout", json={})
    apres = [banque.s.get(f"{URL}{p}", allow_redirects=False).status_code
             for p in ("/api/me", "/api/files", f"/api/files/{banque.fichiers['xlsx']}/apercu")]
    r2 = banque.s.post(f"{URL}/ask_ia", json={"file_id": banque.fichiers["xlsx"], "question": "total"},
                       allow_redirects=False)
    page = banque.s.get(f"{URL}/dashboard", allow_redirects=False)
    ligne("8. Déconnexion (POST) puis accès refusé", "401 sur l'API, /dashboard redirige vers /login",
          f"avant {encore}; après : API {apres}, /ask_ia {r2.status_code}, /dashboard {page.status_code}",
          encore == 200 and r.status_code == 200 and all(c == 401 for c in apres) and r2.status_code in (401, 302)
          and page.status_code == 302 and "login" in page.headers.get("Location", ""))
    ecom.s.post(f"{URL}/api/logout", json={})

    # ---- 9. Base de données ---------------------------------------------------
    verifier_base(banque.id, ecom.id)

    ecrire_resultats()
    return 0 if all(r["ok"] for r in RESULTATS) else 2


def ligne_admin():
    import app as appmod
    from services.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id_utilisateur FROM utilisateurs WHERE role = 'administrateur' LIMIT 1")
    admin = cur.fetchone()
    cur.close()
    conn.close()
    c = appmod.app.test_client()
    with c.session_transaction() as s:
        s["_user_id"], s["_fresh"] = str(admin["id_utilisateur"]), True
    d = c.get("/api/admin/data").get_json() or {}
    emails = [u.get("email") for u in d.get("users", [])]
    page = c.get("/admin/dashboard")
    ligne("8. Tableau de bord admin", "liste des comptes (dont E2E) + page Jinja 200",
          f"{len(emails)} comptes, E2E présents {'e2e.banque@dataia.local' in emails}, page {page.status_code}",
          "e2e.banque@dataia.local" in emails and page.status_code == 200, "session admin du client de test Flask")


def verifier_base(*ids):
    from services.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")
    moteurs = {r["TABLE_NAME"]: r["ENGINE"] for r in cur.fetchall()}
    cur.execute("SELECT COUNT(*) n FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE()")
    nb_fk = cur.fetchone()["n"]
    ligne("9. Tables InnoDB + clés étrangères", "toutes InnoDB, FK présentes",
          f"{len(moteurs)} tables, InnoDB : {all(m == 'InnoDB' for m in moteurs.values())}, {nb_fk} FK",
          all(m == "InnoDB" for m in moteurs.values()) and nb_fk >= 8)
    p = ",".join(["%s"] * len(ids))
    comptes = {}
    for table in ("fichiers", "questions", "graphiques", "modeles_ml", "simulations"):
        cur.execute(f"SELECT COUNT(*) n FROM {table} WHERE id_utilisateur IN ({p})", ids)
        comptes[table] = cur.fetchone()["n"]
    cur.execute(f"SELECT COUNT(*) n FROM rapports r JOIN questions q USING(id_question) WHERE q.id_utilisateur IN ({p})", ids)
    comptes["rapports"] = cur.fetchone()["n"]
    ligne("9. Lignes enregistrées (comptes E2E)", "chaque table remplie", comptes, all(comptes.values()))
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    versions = [r["version"] for r in cur.fetchall()]
    ligne("9. Migrations appliquées", "001, 002, 003", versions, len(versions) >= 3)
    cur.close()
    conn.close()


def ecrire_resultats():
    os.makedirs(os.path.join(RACINE, "mesures"), exist_ok=True)
    with open(os.path.join(RACINE, "mesures", "e2e_final.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTATS, f, ensure_ascii=False, indent=2)
    lignes = ["| # | Étape | Attendu | Obtenu | OK/KO | Remarque |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(RESULTATS, 1):
        obtenu = re.sub(r"\s+", " ", r["obtenu"]).replace("|", "/")
        rem = r["remarque"] + (f" ({r['duree_s']} s)" if r["duree_s"] else "")
        lignes.append(f"| {i} | {r['etape']} | {r['attendu']} | {obtenu} | {'OK' if r['ok'] else '**KO**'} | {rem} |")
    total = sum(r["ok"] for r in RESULTATS)
    with open(os.path.join(RACINE, "mesures", "E2E_RESULTATS.md"), "w", encoding="utf-8") as f:
        f.write(f"# Test de bout en bout — {time.strftime('%Y-%m-%d %H:%M')}\n\n**{total}/{len(RESULTATS)} OK**\n\n")
        f.write("\n".join(lignes) + "\n")
    print(f"\nBILAN E2E : {total}/{len(RESULTATS)} OK")


if __name__ == "__main__":
    sys.exit(main())

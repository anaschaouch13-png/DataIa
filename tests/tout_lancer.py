"""
tests/tout_lancer.py — Lance TOUS les tests (unitaires + intégration) et affiche un bilan.

Usage (dossier DataIa, venv activé, MySQL et Ollama lancés) :  python tests/tout_lancer.py
"""
import subprocess
import sys

SUITES = [
    ("Phase 1 — sécurité, multilingue, Ollama", [sys.executable, "tests/integration_phase1.py"]),
    ("Phase 2 — comptes, domaine, déconnexion, base", [sys.executable, "tests/integration_phase2.py"]),
    ("Phase 3 — routeur hybride", [sys.executable, "-m", "unittest", "tests.test_routeur_hybride"]),
    ("Phase 4 — graphiques", [sys.executable, "-m", "unittest", "tests.test_graphiques"]),
    ("Phase 5 — modèles ML", [sys.executable, "-m", "unittest", "tests.test_ml"]),
]
import os
for nom, module in (("Phase 6 — API du frontend + simulateur", "test_frontend_api"),
                    ("Phase 7 — formats de fichiers", "test_parsers"),
                    ("Phase 8 — export PDF", "test_pdf")):
    if os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), module + ".py")):
        SUITES.append((nom, [sys.executable, "-m", "unittest", "tests." + module]))

bilan = []
for nom, commande in SUITES:
    print(f"\n===== {nom} =====", flush=True)
    r = subprocess.run(commande, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sortie = (r.stdout + r.stderr).strip().splitlines()
    resume = next((l for l in reversed(sortie) if l.startswith(("OK", "FAILED", "BILAN"))), "?")
    print("\n".join(l for l in sortie[-6:]))
    bilan.append((nom, r.returncode == 0 and "ECHEC" not in r.stdout, resume))
print("\n===== BILAN =====")
for nom, ok, resume in bilan:
    print(f"{'OK  ' if ok else 'KO  '} {nom} : {resume}")
sys.exit(0 if all(ok for _, ok, _ in bilan) else 1)

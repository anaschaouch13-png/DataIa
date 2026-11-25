#!/usr/bin/env python3
"""
migrate.py — Applique les migrations SQL de `migrations/` dans l'ordre, sans perte de données.

Garanties :
  1. AVANT toute modification : sauvegarde complète par `mysqldump` dans `backups/`,
     puis vérification de la sauvegarde (fichier non vide + marqueur "Dump completed").
     Si la sauvegarde échoue, AUCUNE migration n'est appliquée.
  2. Chaque migration n'est appliquée qu'une fois (table `schema_migrations`).
  3. Après la migration : comparaison du nombre de lignes de chaque table
     avant / après. Une différence est signalée comme ERREUR.

Usage (dossier DataIa, venv activé) :
    python migrate.py                    # sauvegarde + migrations en attente
    python migrate.py --statut           # liste les migrations appliquées / en attente
    python migrate.py --sauvegarde-seule # sauvegarde uniquement

Restauration en cas de problème :
    mysql -u root dataia < backups/<fichier>.sql
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import sys

for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from services.db import get_db_connection

TABLES_A_CONTROLER = ["utilisateurs", "fichiers", "questions", "rapports"]


# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------
def sauvegarder(etiquette: str = "manuel") -> str:
    """Lance mysqldump et vérifie le fichier produit. Retourne son chemin."""
    horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fichier = os.path.join(config.BACKUP_FOLDER, f"{config.DB_CONFIG['database']}_{horodatage}_{etiquette}.sql")
    commande = [
        config.MYSQLDUMP_PATH,
        f"--host={config.DB_CONFIG['host']}",
        f"--port={config.DB_CONFIG['port']}",
        f"--user={config.DB_CONFIG['user']}",
        "--default-character-set=utf8mb4",
        "--routines", "--triggers", "--events",
        "--add-drop-table",          # le fichier peut être rejoué pour restaurer l'état exact
        "--complete-insert",         # INSERT avec noms de colonnes (lisible, robuste)
        f"--result-file={fichier}",
        config.DB_CONFIG["database"],
    ]
    env = dict(os.environ)
    # Mot de passe par variable d'environnement : il n'apparaît pas dans la liste des processus
    env["MYSQL_PWD"] = config.DB_CONFIG["password"]
    resultat = subprocess.run(commande, capture_output=True, text=True, env=env)
    if resultat.returncode != 0:
        raise RuntimeError(f"mysqldump a échoué : {resultat.stderr.strip()}")

    with open(fichier, encoding="utf-8", errors="replace") as f:
        contenu = f.read()
    if os.path.getsize(fichier) == 0 or "Dump completed" not in contenu[-300:]:
        raise RuntimeError(f"Sauvegarde incomplète : {fichier}")
    nb_insert = contenu.count("INSERT INTO")
    print(f"[Sauvegarde] {fichier} ({os.path.getsize(fichier) // 1024} Ko, {nb_insert} blocs INSERT) : vérifiée")
    return fichier


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------
def lister_migrations() -> list:
    """Fichiers NNN_nom.sql triés par numéro."""
    return sorted(glob.glob(os.path.join(config.MIGRATIONS_FOLDER, "[0-9][0-9][0-9]_*.sql")))


def migrations_appliquees(cur) -> set:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(10) PRIMARY KEY,
            nom VARCHAR(255) NOT NULL,
            date_application DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("SELECT version FROM schema_migrations")
    return {r[0] for r in cur.fetchall()}


def decouper_sql(script: str) -> list:
    """Découpe un script en instructions (séparateur ';' en fin de ligne, commentaires '--' retirés)."""
    lignes = [l for l in script.splitlines() if not l.strip().startswith("--")]
    morceaux = re.split(r";\s*$", "\n".join(lignes), flags=re.MULTILINE)
    return [m.strip() for m in morceaux if m.strip()]


def compter_lignes(cur) -> dict:
    comptes = {}
    for t in TABLES_A_CONTROLER:
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        comptes[t] = cur.fetchone()[0]
    return comptes


def appliquer(fichier: str, conn) -> None:
    version = os.path.basename(fichier).split("_", 1)[0]
    with open(fichier, encoding="utf-8") as f:
        instructions = decouper_sql(f.read())
    cur = conn.cursor()
    print(f"\n[Migration {version}] {os.path.basename(fichier)} : {len(instructions)} instruction(s)")
    for i, instr in enumerate(instructions, 1):
        apercu = " ".join(instr.split())[:90]
        try:
            cur.execute(instr)
            if cur.with_rows:
                cur.fetchall()
            conn.commit()
            print(f"  [{i:02d}] OK  {apercu}")
        except Exception as e:
            # Les ALTER TABLE MySQL ne sont pas transactionnels : on s'arrête net,
            # la restauration se fait depuis la sauvegarde créée juste avant.
            print(f"  [{i:02d}] ERREUR {apercu}\n       -> {e}")
            raise
    cur.execute("INSERT INTO schema_migrations (version, nom) VALUES (%s, %s)",
                (version, os.path.basename(fichier)))
    conn.commit()
    cur.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrations SQL DataIA (avec sauvegarde automatique)")
    parser.add_argument("--statut", action="store_true")
    parser.add_argument("--sauvegarde-seule", action="store_true")
    args = parser.parse_args()

    if args.sauvegarde_seule:
        sauvegarder("manuel")
        return 0

    conn = get_db_connection()
    cur = conn.cursor()
    # Lecture seule à ce stade : on ne crée schema_migrations qu'après la sauvegarde
    cur.execute("SHOW TABLES LIKE 'schema_migrations'")
    deja = set()
    if cur.fetchone():
        cur.execute("SELECT version FROM schema_migrations")
        deja = {r[0] for r in cur.fetchall()}
    en_attente = [f for f in lister_migrations() if os.path.basename(f).split("_", 1)[0] not in deja]

    if args.statut or not en_attente:
        for f in lister_migrations():
            v = os.path.basename(f).split("_", 1)[0]
            print(f"  {'[appliquée] ' if v in deja else '[en attente]'} {os.path.basename(f)}")
        if not en_attente:
            print("Aucune migration en attente.")
        return 0

    # 1. Sauvegarde obligatoire AVANT toute modification
    try:
        sauvegarde = sauvegarder("avant_migration_" + "_".join(
            os.path.basename(f).split("_", 1)[0] for f in en_attente))
    except Exception as e:
        print(f"[ARRÊT] {e}\nAucune modification n'a été faite.")
        return 1

    avant = compter_lignes(cur)
    migrations_appliquees(cur)
    conn.commit()

    # 2. Application
    try:
        for f in en_attente:
            appliquer(f, conn)
    except Exception:
        print(f"\n[ÉCHEC] Migration interrompue. Pour restaurer :\n"
              f"  mysql -u {config.DB_CONFIG['user']} {config.DB_CONFIG['database']} < \"{sauvegarde}\"")
        return 2

    # 3. Vérification : aucune ligne perdue
    cur = conn.cursor()
    apres = compter_lignes(cur)
    print("\n[Vérification] Nombre de lignes avant -> après :")
    perte = False
    for t in TABLES_A_CONTROLER:
        etat = "OK" if avant[t] == apres[t] else "DIFFÉRENCE"
        perte |= avant[t] != apres[t]
        print(f"  {t:14} {avant[t]:5} -> {apres[t]:5}  {etat}")
    cur.close()
    conn.close()
    if perte:
        print(f"[ERREUR] Des lignes ont changé ! Restaurez avec : {sauvegarde}")
        return 3
    print("[OK] Migration terminée sans perte de données.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
creer_admin.py — Crée (ou promeut) un compte administrateur DataIA.

Usage :
    python creer_admin.py --email admin@dataia.local [--nom Administrateur]

Le mot de passe est demandé dans le terminal avec getpass : il ne s'affiche pas
et n'apparaît ni dans l'historique du shell ni dans les arguments du processus.
Il est haché avec werkzeug.generate_password_hash, exactement comme à l'inscription
(app.py /signup et api.py /api/signup).

Si l'email existe déjà, le script propose de passer ce compte en administrateur
et de changer son mot de passe. Aucun autre compte n'est modifié.
La connexion MySQL est celle de config.DB_CONFIG (fichier .env).
"""

import argparse
import getpass
import re
import sys

from werkzeug.security import generate_password_hash

from services.db import get_db_connection
from services.domaines import DOMAINE_PAR_DEFAUT

ROLE_ADMIN = "administrateur"   # valeur de l'ENUM utilisateurs.role (cf. database.sql)
LONGUEUR_MIN = 12


def mot_de_passe_valide(mdp: str) -> str | None:
    """Retourne un message d'erreur, ou None si le mot de passe est assez fort."""
    if len(mdp) < LONGUEUR_MIN:
        return f"au moins {LONGUEUR_MIN} caractères requis"
    if not re.search(r"[A-Za-z]", mdp) or not re.search(r"\d", mdp) or not re.search(r"[^A-Za-z0-9]", mdp):
        return "il faut des lettres, des chiffres et des symboles"
    return None


def demander_mot_de_passe() -> str:
    """Demande le mot de passe deux fois (masqué) jusqu'à obtenir une saisie valide."""
    for _ in range(3):
        mdp = getpass.getpass("Mot de passe : ")
        erreur = mot_de_passe_valide(mdp)
        if erreur:
            print(f"Mot de passe refusé : {erreur}.", file=sys.stderr)
            continue
        if getpass.getpass("Confirmation : ") != mdp:
            print("Les deux saisies ne correspondent pas.", file=sys.stderr)
            continue
        return mdp
    sys.exit("Abandon : trop de tentatives.")


def confirmer(question: str) -> bool:
    return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y", "yes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crée ou promeut un compte administrateur DataIA.")
    parser.add_argument("--email", required=True, help="email du compte administrateur")
    parser.add_argument("--nom", default="Administrateur", help="nom affiché (défaut : Administrateur)")
    args = parser.parse_args()

    email = args.email.strip().lower()          # même normalisation que l'inscription
    nom = args.nom.strip()[:50]
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", email):
        sys.exit(f"Email invalide : {email}")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id_utilisateur, role, est_bloque FROM utilisateurs WHERE email = %s", (email,))
        existant = cur.fetchone()

        if existant:
            print(f"Un compte existe déjà pour {email} (id {existant['id_utilisateur']}, "
                  f"rôle {existant['role']}, bloqué : {'oui' if existant['est_bloque'] else 'non'}).")
            if not confirmer("Le passer en administrateur (et le débloquer) ?"):
                sys.exit("Aucune modification.")
            changer_mdp = confirmer("Changer aussi son mot de passe ?")
            if changer_mdp:
                hache = generate_password_hash(demander_mot_de_passe())
                cur.execute("UPDATE utilisateurs SET role = %s, est_bloque = 0, mot_de_passe = %s "
                            "WHERE id_utilisateur = %s", (ROLE_ADMIN, hache, existant["id_utilisateur"]))
            else:
                cur.execute("UPDATE utilisateurs SET role = %s, est_bloque = 0 WHERE id_utilisateur = %s",
                            (ROLE_ADMIN, existant["id_utilisateur"]))
            conn.commit()
            print(f"Compte {email} promu administrateur"
                  f"{' avec un nouveau mot de passe' if changer_mdp else ''}.")
        else:
            hache = generate_password_hash(demander_mot_de_passe())
            cur.execute("INSERT INTO utilisateurs (nom_utilisateur, email, mot_de_passe, role, domaine, est_bloque) "
                        "VALUES (%s, %s, %s, %s, %s, 0)",
                        (nom, email, hache, ROLE_ADMIN, DOMAINE_PAR_DEFAUT))
            conn.commit()
            print(f"Compte administrateur créé : {email} (id {cur.lastrowid}).")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

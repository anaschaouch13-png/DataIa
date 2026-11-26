"""
services/ml/executeur.py — Exécution d'un modèle ML demandé dans le chat (Phase 5).

Pour chaque exécution :
  1. le modèle tourne (services/ml/forecast.py, anomalies.py, churn_banque.py) ;
  2. le jeu de données nettoyé (exactement ce que le modèle a reçu) est exporté en CSV +
     Excel + rapport de nettoyage dans exports/donnees_nettoyees/U<id>/<modele>_<date>.* ;
  3. une ligne est ajoutée dans `modeles_ml` (métriques, paramètres, chemin des données) ;
  4. une réponse est rédigée (3 langues) avec tableaux, figures et liens de téléchargement.

Aucune prédiction n'est faite à l'upload : uniquement quand l'utilisateur la demande.
"""

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
import plotly.io as pio

import config
from services.charts import ResultatGraphique
from services.ml import anomalies, churn_banque, forecast, nettoyage
from services.redaction import formater_nombre, tableau_markdown


@dataclass
class ResultatML:
    texte: str
    graphiques: List[ResultatGraphique] = field(default_factory=list)
    resultat: Optional[dict] = None
    id_modele: Optional[int] = None
    demande_precision: bool = False
    temps: dict = field(default_factory=dict)


def _l(langue: str) -> str:
    return langue if langue in ("fr", "en", "ar") else "fr"


def _graphique(fig, type_graphique: str, langue: str) -> ResultatGraphique:
    import json as _json
    figure = _json.loads(pio.to_json(fig))
    return ResultatGraphique(texte="", figure=figure,
                             spec={"type": type_graphique, "source": "ml", "langue": langue})


def _enregistrer(id_utilisateur, id_fichier, type_bdd: str, algorithme: str, metriques: dict,
                 parametres: dict, chemins: dict) -> Optional[int]:
    if not id_utilisateur:
        return None
    from services.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO modeles_ml (id_utilisateur, id_fichier, type, algorithme, metrique_mape, metrique_mae,
                   metrique_accuracy, parametres_json, chemin_donnees_nettoyees) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (id_utilisateur, id_fichier, type_bdd, algorithme, metriques.get("mape"), metriques.get("mae"),
                 metriques.get("accuracy"), json.dumps({**parametres, "metriques": metriques, "fichiers": chemins},
                                                       ensure_ascii=False, default=str),
                 os.path.relpath(chemins["csv"], config.BASE_DIR)))
    id_modele = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return id_modele


def _exporter(df: pd.DataFrame, rapport, id_utilisateur, type_bdd: str) -> dict:
    nom = f"{type_bdd}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    return nettoyage.exporter(df, rapport, nettoyage.dossier_utilisateur(id_utilisateur or "anonyme"), nom)


LIENS = {"fr": "📥 Données nettoyées passées au modèle : [CSV]({b}/csv) · [Excel]({b}/xlsx) · [rapport de nettoyage]({b}/rapport)",
         "en": "📥 Cleaned data given to the model: [CSV]({b}/csv) · [Excel]({b}/xlsx) · [cleaning report]({b}/rapport)",
         "ar": "📥 البيانات المنظفة المستعملة في النموذج: [CSV]({b}/csv) · [Excel]({b}/xlsx) · [تقرير التنظيف]({b}/rapport)"}


def _liens(id_modele, langue) -> str:
    return LIENS[_l(langue)].format(b=f"/telecharger/nettoyees/{id_modele}") if id_modele else ""


def _resume_nettoyage(rapport, langue) -> str:
    l = _l(langue)
    titre = {"fr": "🧹 Nettoyage", "en": "🧹 Cleaning", "ar": "🧹 التنظيف"}[l]
    return f"<details><summary>{titre} ({len(rapport.etapes)})</summary>\n\n" + \
        "\n".join(f"- {e}" for e in rapport.etapes) + "\n\n</details>"


# ---------------------------------------------------------------------------
# 1. Prévision du chiffre d'affaires
# ---------------------------------------------------------------------------
def lancer_prevision(df, question, langue, id_utilisateur=None, id_fichier=None, source="", horizon=None,
                     colonne_cible=None) -> ResultatML:
    l = _l(langue)
    try:
        res = forecast.prevoir(df, question, horizon=horizon, source=source, colonne_cible=colonne_cible)
    except forecast.HistoriqueInsuffisant as e:
        return ResultatML(texte=f"⚠️ {e}", demande_precision=True)
    chemins = _exporter(res.df_nettoye, res.rapport, id_utilisateur, "prevision")
    m = res.metriques
    critere = m[res.critere]
    id_modele = _enregistrer(id_utilisateur, id_fichier, "prevision", res.modele_retenu,
                             {"mape": round(m["mape"], 4), "mae": round(m["mae"], 2), "rmse": round(m["rmse"], 2),
                              "smape": round(m["smape"], 4)},
                             {"colonne_date": res.colonne_date, "colonne_cible": res.colonne_cible,
                              "frequence": res.frequence, "horizon": len(res.previsions), "nb_periodes": res.nb_periodes,
                              "nb_test": res.nb_test, "comparaison": res.comparaison, "critere": res.critere}, chemins)
    fmt = lambda x: formater_nombre(round(x, 2), l)
    titre = {"fr": f"📈 **Prévision de `{res.colonne_cible}`** par {res.frequence} — modèle retenu : **{res.modele_retenu}**",
             "en": f"📈 **Forecast of `{res.colonne_cible}`** per {res.frequence} — selected model: **{res.modele_retenu}**",
             "ar": f"📈 **توقع `{res.colonne_cible}`** — النموذج المختار: **{res.modele_retenu}**"}[l]
    precision = {"fr": f"**Précision : {fmt(max(0, 100 - critere))} % ({res.critere.upper()} = {fmt(critere)} %)** sur les "
                       f"{res.nb_test} dernières périodes, jamais vues pendant l'entraînement.",
                 "en": f"**Accuracy: {fmt(max(0, 100 - critere))}% ({res.critere.upper()} = {fmt(critere)}%)** on the last "
                       f"{res.nb_test} periods, never seen during training.",
                 "ar": f"**الدقة: {fmt(max(0, 100 - critere))}٪ ({res.critere.upper()} = {fmt(critere)}٪)** على آخر "
                       f"{res.nb_test} فترات لم يرها النموذج أثناء التدريب."}[l]
    comparaison = pd.DataFrame([{"modèle": c["modele"] + (" ✅" if c["modele"] == res.modele_retenu else "")
                                 + (" (référence)" if not c["candidat"] else ""),
                                 "MAPE %": round(c["mape"], 2), "sMAPE %": round(c["smape"], 2),
                                 "MAE": round(c["mae"], 0), "RMSE": round(c["rmse"], 0)} for c in res.comparaison])
    previsions = res.previsions.assign(periode=res.previsions["periode"].dt.strftime("%Y-%m-%d")).round(0)
    previsions.columns = {"fr": ["période", "prévision", "borne basse (95 %)", "borne haute (95 %)"],
                          "en": ["period", "forecast", "lower (95%)", "upper (95%)"],
                          "ar": ["الفترة", "التوقع", "الحد الأدنى", "الحد الأعلى"]}[l]
    alerte = ""
    naif = next((c for c in res.comparaison if not c["candidat"]), None)
    if naif and naif[res.critere] < critere:
        alerte = {"fr": "⚠️ Sur ce fichier, la référence naïve fait mieux que les modèles : les ventes semblent peu "
                        "prévisibles (forte part de hasard). La prévision est à prendre avec prudence.",
                  "en": "⚠️ On this file, the naive baseline beats the models: sales look hard to predict.",
                  "ar": "⚠️ في هذا الملف، المرجع البسيط أفضل من النماذج: المبيعات صعبة التوقع."}[l]
    texte = "\n\n".join(x for x in [titre, precision, alerte, tableau_markdown(comparaison, l),
                                     tableau_markdown(previsions, l), _resume_nettoyage(res.rapport, l),
                                     _liens(id_modele, l)] if x)
    return ResultatML(texte=texte, graphiques=[_graphique(forecast.figure(res, l), "line", l)], id_modele=id_modele,
                      resultat={"modele": res.modele_retenu, "critere": res.critere, "valeur_critere": critere,
                                "comparaison": res.comparaison,
                                "previsions": json.loads(previsions.to_json(orient="records"))},
                      temps=res.temps)


# ---------------------------------------------------------------------------
# 2. Détection d'anomalies
# ---------------------------------------------------------------------------
def lancer_anomalies(df, question, langue, id_utilisateur=None, id_fichier=None, source="") -> ResultatML:
    l = _l(langue)
    try:
        res = anomalies.detecter(df, question, source=source, langue=l)
    except ValueError as e:
        return ResultatML(texte=f"⚠️ {e}", demande_precision=True)
    chemins = _exporter(res.df_nettoye, res.rapport, id_utilisateur, "anomalie")
    taux = len(res.anomalies) / max(1, res.nb_lignes)
    id_modele = _enregistrer(id_utilisateur, id_fichier, "anomalie", "IsolationForest",
                             {"taux_anomalies": round(taux, 4), "nb_anomalies": len(res.anomalies)},
                             {"colonnes": res.modele.colonnes, "coherence": res.modele.coherence,
                              "seuil": res.modele.seuil, "n_estimators": 300}, chemins)
    from services.charts import _est_identifiant
    ident = [c for c in df.columns if _est_identifiant(df, c)][:1]
    colonnes = ident + list(res.modele.colonnes) + ["score_anomalie", "raison"]
    titre = {"fr": f"🔎 **{len(res.anomalies)} anomalie(s)** détectée(s) sur {formater_nombre(res.nb_lignes, l)} lignes "
                   f"(Isolation Forest, colonnes : {', '.join(f'`{c}`' for c in res.modele.colonnes)}"
                   + (", + cohérence montant / quantité × prix" if res.modele.coherence else "") + ").",
             "en": f"🔎 **{len(res.anomalies)} anomaly(ies)** found in {formater_nombre(res.nb_lignes, l)} rows (Isolation Forest).",
             "ar": f"🔎 **{len(res.anomalies)} حالة شاذة** من بين {formater_nombre(res.nb_lignes, l)} سطر (Isolation Forest)."}[l]
    surveiller = {"fr": "**À surveiller** (les plus inhabituelles juste sous le seuil) :",
                  "en": "**To watch** (most unusual rows just below the threshold):",
                  "ar": "**للمتابعة** (الأكثر غرابة تحت العتبة):"}[l]
    texte = "\n\n".join(x for x in [
        titre, tableau_markdown(res.anomalies[colonnes].head(30), l),
        surveiller, tableau_markdown(res.a_surveiller[colonnes].head(10), l),
        _resume_nettoyage(res.rapport, l), _liens(id_modele, l)] if x)
    return ResultatML(texte=texte, graphiques=[_graphique(anomalies.figure(res, df, l), "scatter", l)],
                      id_modele=id_modele, temps=res.temps,
                      resultat={"nb_anomalies": len(res.anomalies), "seuil": res.modele.seuil,
                                "anomalies": json.loads(res.anomalies[colonnes].head(50).to_json(orient="records"))})


# ---------------------------------------------------------------------------
# 3. Churn bancaire
# ---------------------------------------------------------------------------
def lancer_churn(df, question, langue, id_utilisateur=None, id_fichier=None, source="") -> ResultatML:
    l = _l(langue)
    try:
        res = churn_banque.predire_fichier(df, source)
    except churn_banque.ColonnesManquantes as e:
        _, meta = churn_banque.charger()
        texte = {"fr": "⚠️ Ce fichier ne contient pas toutes les colonnes attendues par le modèle de churn.\n\n"
                       f"- **Colonnes manquantes** : {', '.join(f'`{c}`' for c in e.manquantes)}\n"
                       f"- Colonnes reconnues : {', '.join(f'`{v}` → `{k}`' for k, v in e.presentes.items()) or '-'}\n"
                       f"- Colonnes attendues : {', '.join(f'`{c}`' for c in meta['features_entree'])}",
                 "en": f"⚠️ Missing columns for the churn model: {', '.join(e.manquantes)}.",
                 "ar": f"⚠️ أعمدة ناقصة لنموذج المغادرة: {', '.join(e.manquantes)}."}[l]
        return ResultatML(texte=texte, demande_precision=True)
    except churn_banque.ModeleChurnIndisponible as e:
        return ResultatML(texte=f"⚠️ {e}", demande_precision=True)
    chemins = _exporter(res.df_nettoye, res.rapport, id_utilisateur, "churn")
    mt = res.meta["metriques_test"]
    id_modele = _enregistrer(id_utilisateur, id_fichier, "churn", "DecisionTreeClassifier (Pipeline)",
                             {"accuracy": mt["accuracy"], "taux_risque": round(res.pourcentage / 100, 4)},
                             {"nb_clients": res.nb_clients, "nb_risque": res.nb_risque, "seuil": churn_banque.SEUIL,
                              "parametres_modele": res.meta["parametres"], "metriques_test": mt,
                              "categories_inconnues": res.categories_inconnues}, chemins)
    pct = formater_nombre(round(res.pourcentage, 1), l)
    titre = {"fr": f"👥 **{res.nb_risque} client(s) sur {formater_nombre(res.nb_clients, l)} ({pct} %) présentent un "
                   f"risque de départ** (probabilité ≥ 50 %).",
             "en": f"👥 **{res.nb_risque} of {formater_nombre(res.nb_clients, l)} customers ({pct}%) are at risk of leaving**.",
             "ar": f"👥 **{res.nb_risque} عميل من {formater_nombre(res.nb_clients, l)} ({pct}٪) معرضون لخطر المغادرة**."}[l]
    modele = {"fr": f"Modèle : arbre de décision (profondeur {res.meta['parametres']['max_depth']}) — sur le jeu de test : "
                    f"rappel {formater_nombre(round(mt['rappel'] * 100, 1), l)} % des départs détectés, précision "
                    f"{formater_nombre(round(mt['precision'] * 100, 1), l)} %, F1 {formater_nombre(mt['f1'], l)}.",
              "en": f"Model: decision tree (depth {res.meta['parametres']['max_depth']}) — test recall {mt['rappel']:.1%}, "
                    f"precision {mt['precision']:.1%}, F1 {mt['f1']}.",
              "ar": f"النموذج: شجرة قرار — الاسترجاع {mt['rappel']:.1%}، الدقة {mt['precision']:.1%}."}[l]
    ident = [c for c in res.clients.columns if "id" in c.lower()][:1]
    cols = ident + [res.colonnes.get(c, c) for c in ("age", "products_number", "active_member", "balance", "country")
                    if c in res.colonnes] + ["probabilite_depart", "prediction"]
    top = res.clients[cols].head(20).copy()
    top["probabilite_depart"] = (top["probabilite_depart"] * 100).round(1)
    top = top.rename(columns={"probabilite_depart": "probabilité de départ (%)"})
    importances = ", ".join(f"`{k}` {formater_nombre(round(v * 100, 1), l)} %" for k, v in
                            list(res.importances.items())[:5])
    imp_titre = {"fr": "Variables les plus importantes", "en": "Most important features", "ar": "أهم المتغيرات"}[l]
    alerte = ""
    if res.categories_inconnues:
        alerte = f"⚠️ {res.categories_inconnues}"
    texte = "\n\n".join(x for x in [titre, modele, alerte, tableau_markdown(top, l), f"**{imp_titre}** : {importances}",
                                     _resume_nettoyage(res.rapport, l), _liens(id_modele, l)] if x)
    return ResultatML(texte=texte, graphiques=[_graphique(f, t, l) for f, t in
                                               zip(churn_banque.figures(res, l), ("donut", "bar"))],
                      id_modele=id_modele, temps=res.temps,
                      resultat={"nb_clients": res.nb_clients, "nb_risque": res.nb_risque, "pourcentage": res.pourcentage,
                                "importances": res.importances})


LANCEURS = {"forecast": lancer_prevision, "anomaly": lancer_anomalies, "churn": lancer_churn}

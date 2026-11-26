import os
import joblib
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("==========================================================")
print("  ENTRAÎNEMENT DU MODÈLE D'ARBRE DE DÉCISION (BANK CHURN)  ")
print("==========================================================\n")

# 1. Chargement du fichier
data_path = os.path.join(BASE_DIR, 'uploads', 'Bank Customer Churn Prediction.csv')
print(f"[1/6] Chargement des données depuis : {data_path} ...")
df = pd.read_csv(data_path)
print(f"      -> {df.shape[0]} lignes et {df.shape[1]} colonnes chargées.")

# 2. Nettoyage : suppression de l'identifiant client
print("\n[2/6] Nettoyage des données...")
df = df.drop(columns=['customer_id'])
print("      -> Colonne 'customer_id' supprimée avec succès.")

# 3. Encodage des colonnes catégorielles en valeurs numériques
print("\n[3/6] Encodage des variables texte (country, gender)...")
df_encoded = pd.get_dummies(df, columns=['country', 'gender'], drop_first=True)
print(f"      -> Nouvelles colonnes prêtes pour l'algorithme : {df_encoded.columns.tolist()}")

# 4. Séparation X (Features) et y (Target)
X = df_encoded.drop(columns=['churn'])
y = df_encoded['churn']

# Séparation 80% entraînement (train) et 20% test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
print(f"\n[4/6] Découpage des données :")
print(f"      -> Données d'entraînement : {X_train.shape[0]} clients")
print(f"      -> Données de test : {X_test.shape[0]} clients")

# 5. Entraînement de l'Arbre de Décision
print("\n[5/6] Entraînement de l'Arbre de Décision (profondeur max = 4)...")
modele = DecisionTreeClassifier(max_depth=4, random_state=42)
modele.fit(X_train, y_train)

# Évaluation sur le jeu de test
y_pred = modele.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n>>> RÉSULTAT DU MODÈLE : Précision (Accuracy) = {accuracy * 100:.2f}% <<<")
print("\nMatrice de Confusion :")
print(confusion_matrix(y_test, y_pred))
print("\nRapport Détaillé (Précision, Rappel, F1-Score) :")
print(classification_report(y_test, y_pred, target_names=['Fidèle (0)', 'Parti (1)']))

# Importance des variables
print("Importance des caractéristiques selon l'arbre de décision :")
importances = pd.Series(modele.feature_importances_, index=X.columns).sort_values(ascending=False)
for col, imp in importances.items():
    if imp > 0:
        print(f"  - {col:25} : {imp * 100:.1f}%")

# 6. Sauvegarde du modèle et génération du graphique
print("\n[6/6] Sauvegarde du modèle et export de l'arbre graphique...")
modele_path = os.path.join(BASE_DIR, 'modele_churn.pkl')
colonnes_path = os.path.join(BASE_DIR, 'colonnes_churn.pkl')
joblib.dump(modele, modele_path)
joblib.dump(X.columns.tolist(), colonnes_path)
print(f"      -> Modèle sauvegardé dans : {modele_path}")
print(f"      -> Colonnes sauvegardées dans : {colonnes_path}")

# Dessin de l'arbre
plt.figure(figsize=(24, 12))
plot_tree(
    modele,
    feature_names=X.columns,
    class_names=['Fidèle', 'Parti'],
    filled=True,
    rounded=True,
    fontsize=9
)
plt.title("Arbre de Décision - Prédiction du Départ Client (Bank Customer Churn)", fontsize=16, fontweight='bold', pad=20)
output_img = os.path.join(BASE_DIR, 'arbre_decision.png')
plt.savefig(output_img, dpi=300, bbox_inches='tight')
plt.close()
print(f"      -> Schéma de l'arbre enregistré dans : {output_img}")
print("\n[SUCCÈS] Entraînement terminé avec succès !")

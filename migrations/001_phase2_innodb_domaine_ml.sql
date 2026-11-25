-- ============================================================================
--  Migration 001 — Phase 2
--  1. Conversion MyISAM -> InnoDB (transactions + vraies clés étrangères)
--  2. Colonne `domaine` dans `utilisateurs` (comptes existants : 'Autre')
--  3. Lignes orphelines : valeur d'origine conservée dans `migration_orphelins`
--  4. Clés étrangères
--  5. `rapports.type_graphique`
--  6. Nouvelles tables `modeles_ml` et `simulations`
--
--  Sans perte de données : aucune ligne n'est supprimée. Appliquée par
--  migrate.py, qui fait un mysqldump vérifié AVANT et compare le nombre
--  de lignes APRÈS.
--  Noms de tables en minuscules : convention déjà utilisée par la base
--  (et MySQL sous Windows a lower_case_table_names = 1).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. MyISAM -> InnoDB
--    MyISAM ignore les clés étrangères et n'a pas de transactions :
--    c'est pour cela que 39 questions pointent vers des fichiers supprimés.
-- ---------------------------------------------------------------------------
ALTER TABLE utilisateurs ENGINE = InnoDB;
ALTER TABLE fichiers     ENGINE = InnoDB;
ALTER TABLE questions    ENGINE = InnoDB;
ALTER TABLE rapports     ENGINE = InnoDB;

-- ---------------------------------------------------------------------------
-- 2. Domaine d'activité de l'utilisateur
--    NOT NULL DEFAULT 'Autre' : les comptes existants reçoivent 'Autre'.
-- ---------------------------------------------------------------------------
ALTER TABLE utilisateurs
    ADD COLUMN domaine ENUM('Banque','E-commerce','Finance','Poste','Assurance','Télécom','Industrie','Autre')
        NOT NULL DEFAULT 'Autre' AFTER role;

-- ---------------------------------------------------------------------------
-- 3. Orphelins : on garde une trace de la valeur d'origine avant de la mettre à NULL
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS migration_orphelins (
    id_orphelin      INT AUTO_INCREMENT PRIMARY KEY,
    table_source     VARCHAR(64) NOT NULL,
    id_ligne         INT NOT NULL,
    colonne          VARCHAR(64) NOT NULL,
    ancienne_valeur  INT NOT NULL,
    migration        VARCHAR(10) NOT NULL,
    date_detection   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- questions dont le fichier a été supprimé (l'historique est conservé)
INSERT INTO migration_orphelins (table_source, id_ligne, colonne, ancienne_valeur, migration)
SELECT 'questions', q.id_question, 'id_fichier', q.id_fichier, '001'
FROM questions q LEFT JOIN fichiers f ON f.id_fichier = q.id_fichier
WHERE f.id_fichier IS NULL;

-- rapports dont la question n'existe plus (0 aujourd'hui, par sécurité)
INSERT INTO migration_orphelins (table_source, id_ligne, colonne, ancienne_valeur, migration)
SELECT 'rapports', r.id_rapport, 'id_question', r.id_question, '001'
FROM rapports r LEFT JOIN questions q ON q.id_question = r.id_question
WHERE q.id_question IS NULL;

-- Colonnes rendues facultatives : supprimer un fichier ne doit pas effacer
-- l'historique des questions, et supprimer une question ne doit pas effacer le rapport.
ALTER TABLE questions MODIFY id_fichier  INT NULL;
ALTER TABLE rapports  MODIFY id_question INT NULL;

UPDATE questions q LEFT JOIN fichiers f ON f.id_fichier = q.id_fichier
SET q.id_fichier = NULL WHERE f.id_fichier IS NULL;

UPDATE rapports r LEFT JOIN questions q ON q.id_question = r.id_question
SET r.id_question = NULL WHERE q.id_question IS NULL;

-- ---------------------------------------------------------------------------
-- 4. Clés étrangères
--    CASCADE  : la donnée n'a pas de sens sans son propriétaire (fichiers d'un utilisateur supprimé)
--    SET NULL : on conserve l'historique quand l'objet lié disparaît
-- ---------------------------------------------------------------------------
ALTER TABLE fichiers
    ADD CONSTRAINT fk_fichiers_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs (id_utilisateur) ON DELETE CASCADE;

ALTER TABLE questions
    ADD CONSTRAINT fk_questions_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs (id_utilisateur) ON DELETE CASCADE,
    ADD CONSTRAINT fk_questions_fichier FOREIGN KEY (id_fichier)
        REFERENCES fichiers (id_fichier) ON DELETE SET NULL;

ALTER TABLE rapports
    ADD CONSTRAINT fk_rapports_question FOREIGN KEY (id_question)
        REFERENCES questions (id_question) ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- 5. Rapports : type du graphique (chemin_graphique existe déjà dans la base)
-- ---------------------------------------------------------------------------
ALTER TABLE rapports
    ADD COLUMN type_graphique VARCHAR(30) NULL AFTER chemin_graphique;

-- ---------------------------------------------------------------------------
-- 6. Nouvelles tables
-- ---------------------------------------------------------------------------
-- Chaque exécution d'un modèle de Machine Learning (Phase 5)
CREATE TABLE IF NOT EXISTS modeles_ml (
    id_modele                 INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur            INT NOT NULL,
    id_fichier                INT NULL,
    type                      ENUM('prevision','anomalie','churn') NOT NULL,
    algorithme                VARCHAR(50) NOT NULL,
    metrique_mape             DOUBLE NULL,   -- en %
    metrique_mae              DOUBLE NULL,   -- dans l'unité de la cible (ex. dinars)
    metrique_accuracy         DOUBLE NULL,   -- entre 0 et 1
    parametres_json           JSON NULL,
    chemin_donnees_nettoyees  VARCHAR(255) NULL,
    date_execution            DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_modeles_utilisateur_type (id_utilisateur, type),
    CONSTRAINT fk_modeles_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs (id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_modeles_fichier FOREIGN KEY (id_fichier)
        REFERENCES fichiers (id_fichier) ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- Chaque simulation "what-if" du panneau Simulateur (Phase 6)
CREATE TABLE IF NOT EXISTS simulations (
    id_simulation    INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur   INT NOT NULL,
    type_modele      ENUM('prevision','anomalie','churn') NOT NULL,
    entrees_json     JSON NOT NULL,
    resultat_json    JSON NOT NULL,
    date_simulation  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_simulations_utilisateur (id_utilisateur, date_simulation),
    CONSTRAINT fk_simulations_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs (id_utilisateur) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

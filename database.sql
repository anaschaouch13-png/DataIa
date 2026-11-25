-- ============================================================================
--  DataIA — schéma INITIAL (v1), tel qu'il existait avant la v2.
--
--  Installation d'une base neuve :
--    1. mysql -u root < database.sql        (crée la base dans son état v1)
--    2. python migrate.py                   (applique migrations/001, 002, ...)
--
--  Ne pas modifier ce fichier pour faire évoluer la base : toute évolution
--  passe par un nouveau script dans migrations/ (voir JUSTIFICATIONS.md).
--  Les tables sont en MyISAM ici car c'était l'état réel de la base v1 ;
--  la migration 001 les convertit en InnoDB et ajoute les clés étrangères.
-- ============================================================================
CREATE DATABASE IF NOT EXISTS dataia CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE dataia;

CREATE TABLE IF NOT EXISTS utilisateurs (
    id_utilisateur   INT NOT NULL AUTO_INCREMENT,
    nom_utilisateur  VARCHAR(50) NOT NULL,
    email            VARCHAR(100) NOT NULL,
    mot_de_passe     VARCHAR(255) NOT NULL,
    role             ENUM('utilisateur','administrateur') DEFAULT 'utilisateur',
    date_inscription DATETIME DEFAULT CURRENT_TIMESTAMP,
    est_bloque       TINYINT(1) DEFAULT '0',
    PRIMARY KEY (id_utilisateur),
    UNIQUE KEY email (email)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS fichiers (
    id_fichier      INT NOT NULL AUTO_INCREMENT,
    id_utilisateur  INT NOT NULL,
    nom_fichier     VARCHAR(255) NOT NULL,
    chemin_fichier  VARCHAR(255) NOT NULL,
    type_fichier    ENUM('CSV','Excel') NOT NULL,
    date_upload     DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_fichier),
    KEY id_utilisateur (id_utilisateur)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS questions (
    id_question     INT NOT NULL AUTO_INCREMENT,
    id_utilisateur  INT NOT NULL,
    id_fichier      INT NOT NULL,
    question_texte  TEXT NOT NULL,
    reponse_texte   TEXT,
    date_question   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_question),
    KEY id_utilisateur (id_utilisateur),
    KEY id_fichier (id_fichier)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS rapports (
    id_rapport        INT NOT NULL AUTO_INCREMENT,
    id_question       INT NOT NULL,
    rapport_texte     TEXT NOT NULL,
    chemin_graphique  VARCHAR(255) DEFAULT NULL,
    chemin_resume     VARCHAR(255) DEFAULT NULL,
    date_generation   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_rapport),
    KEY id_question (id_question)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Compte administrateur : à créer après installation (mot de passe haché par l'application).

-- Base de données pour le projet DataIA
CREATE DATABASE IF NOT EXISTS dataia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE dataia;

-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS utilisateurs (
    id_utilisateur INT AUTO_INCREMENT PRIMARY KEY,
    nom_utilisateur VARCHAR(100) NOT NULL,
    email VARCHAR(191) NOT NULL UNIQUE,
    mot_de_passe VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'utilisateur',
    est_bloque TINYINT(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table des fichiers uploadés
CREATE TABLE IF NOT EXISTS fichiers (
    id_fichier INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur INT NOT NULL,
    nom_fichier VARCHAR(255) NOT NULL,
    chemin_fichier VARCHAR(255) NOT NULL,
    type_fichier VARCHAR(50) NOT NULL,
    date_upload DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fichiers_utilisateurs FOREIGN KEY (id_utilisateur) 
        REFERENCES utilisateurs(id_utilisateur) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table des questions et réponses du chatbot
CREATE TABLE IF NOT EXISTS questions (
    id_question INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur INT NOT NULL,
    id_fichier INT NOT NULL,
    question_texte TEXT NOT NULL,
    reponse_texte LONGTEXT,
    date_question DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_questions_utilisateurs FOREIGN KEY (id_utilisateur) 
        REFERENCES utilisateurs(id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_questions_fichiers FOREIGN KEY (id_fichier) 
        REFERENCES fichiers(id_fichier) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table des rapports exportés
CREATE TABLE IF NOT EXISTS rapports (
    id_rapport INT AUTO_INCREMENT PRIMARY KEY,
    id_question INT NULL,
    rapport_texte TEXT,
    chemin_resume VARCHAR(255),
    date_generation DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rapports_questions FOREIGN KEY (id_question) 
        REFERENCES questions(id_question) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

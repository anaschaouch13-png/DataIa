-- ============================================================================
--  Migration 002 — Phase 4 : table `graphiques`
--
--  Chaque graphique généré (chat, modèle ML, simulation) est enregistré :
--  spécification + figure Plotly (JSON) + image PNG (pour l'export PDF, Phase 8).
--  Une question peut produire plusieurs graphiques (relation 1-n) : les colonnes
--  rapports.chemin_graphique / type_graphique ne suffisent pas.
--
--  Aucune donnée existante n'est modifiée (création de table uniquement).
--  Appliquée par migrate.py (mysqldump vérifié AVANT).
-- ============================================================================

CREATE TABLE IF NOT EXISTS graphiques (
    id_graphique     INT AUTO_INCREMENT PRIMARY KEY,
    id_utilisateur   INT NOT NULL,
    id_question      INT NULL,          -- question du chat qui a produit le graphique
    id_fichier       INT NULL,          -- fichier analysé
    source           ENUM('chat','ml','simulation') NOT NULL DEFAULT 'chat',
    type_graphique   VARCHAR(30) NOT NULL,       -- bar, bar_groupe, bar_empile, line, area, pie, donut, scatter, histogram, box, heatmap
    titre            VARCHAR(255) NOT NULL,
    spec_json        JSON NOT NULL,              -- spécification validée (x, y, agrégation, couleur, raison du choix)
    chemin_json      VARCHAR(255) NOT NULL,      -- figure Plotly complète (rechargeable dans le chat)
    chemin_png       VARCHAR(255) NULL,          -- image pour le PDF (générée en arrière-plan)
    date_creation    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_graphiques_question (id_question),
    INDEX idx_graphiques_utilisateur (id_utilisateur, date_creation),
    CONSTRAINT fk_graphiques_utilisateur FOREIGN KEY (id_utilisateur)
        REFERENCES utilisateurs (id_utilisateur) ON DELETE CASCADE,
    CONSTRAINT fk_graphiques_question FOREIGN KEY (id_question)
        REFERENCES questions (id_question) ON DELETE SET NULL,
    CONSTRAINT fk_graphiques_fichier FOREIGN KEY (id_fichier)
        REFERENCES fichiers (id_fichier) ON DELETE SET NULL
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ============================================================================
--  Migration 003 — Phase 7 : nouveaux formats de fichiers (PDF, images)
--
--  fichiers.type_fichier était ENUM('CSV','Excel') : un upload PDF ou PNG aurait été
--  refusé par MySQL. On AJOUTE des valeurs à l'ENUM (les valeurs existantes et l'ordre
--  sont conservés : aucune ligne n'est modifiée).
--  Appliquée par migrate.py (mysqldump vérifié AVANT).
-- ============================================================================

ALTER TABLE fichiers
    MODIFY type_fichier ENUM('CSV','Excel','PDF','Image') NOT NULL;

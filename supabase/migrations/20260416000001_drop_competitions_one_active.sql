-- Migration: drop_competitions_one_active
-- Propósito: Eliminar el índice UNIQUE parcial que limita a exactamente 1 competition
--            con is_active = true. Necesario para soportar LEC + LCK + LPL simultáneos.
-- Rollback: CREATE UNIQUE INDEX competitions_one_active ON competitions (is_active) WHERE is_active = true;

DROP INDEX IF EXISTS competitions_one_active;

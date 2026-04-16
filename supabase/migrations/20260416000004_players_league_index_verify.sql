-- Migration: players_league_index_verify
-- Propósito: Confirmar/crear el índice idx_players_league en players(league).
--            Necesario para que el filtro de _resolve_player_id por league sea performante.
--            Si 20260303000001 se aplicó correctamente, esta migración es un no-op.
-- Rollback: DROP INDEX IF EXISTS idx_players_league;

CREATE INDEX IF NOT EXISTS idx_players_league ON players (league);

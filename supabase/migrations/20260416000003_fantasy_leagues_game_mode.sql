-- Migration: fantasy_leagues_game_mode
-- Propósito: Agregar campo game_mode a fantasy_leagues para distinguir
--            entre draft_market (mercado diario) y budget_pick (presupuesto fijo).
-- Rollback: ALTER TABLE fantasy_leagues DROP COLUMN game_mode;

ALTER TABLE fantasy_leagues
  ADD COLUMN IF NOT EXISTS game_mode TEXT NOT NULL DEFAULT 'draft_market'
    CHECK (game_mode IN ('draft_market', 'budget_pick'));

COMMENT ON COLUMN fantasy_leagues.game_mode IS
  'draft_market: mercado diario, jugadores únicos. budget_pick: presupuesto fijo, jugadores repetibles, sin mercado.';

-- Migration: create_scoring_config
-- Created: 2026-04-17
-- Rollback:
--   DROP TABLE IF EXISTS scoring_config;

-- === FORWARD MIGRATION ===

CREATE TABLE IF NOT EXISTS scoring_config (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid        NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
  role           player_role NOT NULL,
  weights        jsonb       NOT NULL,
  multikill_bonuses jsonb    NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT scoring_config_competition_role_unique UNIQUE (competition_id, role)
);

CREATE INDEX IF NOT EXISTS idx_scoring_config_competition
  ON scoring_config (competition_id);

-- set_updated_at() already exists (defined in 20260314100000_series_games_schema.sql)
CREATE TRIGGER set_scoring_config_updated_at
  BEFORE UPDATE ON scoring_config
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Migration: add gold_diff_at_10 to player_match_stats
-- Created: 2026-03-14
-- Rollback: ALTER TABLE player_match_stats DROP COLUMN IF EXISTS gold_diff_at_10;

-- === FORWARD MIGRATION ===

ALTER TABLE player_match_stats
  ADD COLUMN IF NOT EXISTS gold_diff_at_10 NUMERIC NULL;

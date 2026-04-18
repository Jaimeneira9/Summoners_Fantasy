-- Migration: add_players_name_league_unique
-- Created: 2026-04-17
-- Purpose: Enforce uniqueness of player names within a league.
--          Prevents duplicate ingestion of the same player from the
--          data pipeline (e.g. gol.gg) creating ghost rows.
--
-- SAFETY CHECK — run this before applying to production:
--   SELECT name, league, COUNT(*)
--   FROM players
--   GROUP BY name, league
--   HAVING COUNT(*) > 1;
--   -- Must return 0 rows. If any duplicates exist, deduplicate first.
--
-- Rollback:
--   ALTER TABLE players DROP CONSTRAINT IF EXISTS players_name_league_unique;

-- === FORWARD MIGRATION ===

ALTER TABLE players
  ADD CONSTRAINT players_name_league_unique UNIQUE (name, league);

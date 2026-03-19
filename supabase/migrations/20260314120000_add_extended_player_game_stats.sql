-- Migration: add extended player game stats columns
-- Adds the columns that series_ingest.py sends but that don't exist yet
-- in player_game_stats.

ALTER TABLE player_game_stats
    ADD COLUMN IF NOT EXISTS dpm              INTEGER,
    ADD COLUMN IF NOT EXISTS wards_placed     INTEGER,
    ADD COLUMN IF NOT EXISTS wards_destroyed  INTEGER,
    ADD COLUMN IF NOT EXISTS solo_kills       INTEGER,
    ADD COLUMN IF NOT EXISTS xp_diff_15       INTEGER,
    ADD COLUMN IF NOT EXISTS turret_damage    INTEGER;

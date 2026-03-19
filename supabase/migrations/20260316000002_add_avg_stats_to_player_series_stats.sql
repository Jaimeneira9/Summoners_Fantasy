-- Migration: add avg_dpm, avg_wards_per_min, kill_participation to player_series_stats
-- Created: 2026-03-16

ALTER TABLE player_series_stats
  ADD COLUMN IF NOT EXISTS avg_dpm             numeric(8,2),
  ADD COLUMN IF NOT EXISTS avg_wards_per_min   numeric(6,3),
  ADD COLUMN IF NOT EXISTS kill_participation  numeric(5,4);

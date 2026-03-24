-- Adds price fluctuation tracking fields to players table
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS avg_points_baseline numeric(8,2),
  ADD COLUMN IF NOT EXISTS last_price_change_pct numeric(6,4) DEFAULT 0;

-- Backfill baseline with current average game points
UPDATE players p
SET avg_points_baseline = (
  SELECT AVG(game_points) FROM player_game_stats WHERE player_id = p.id
);

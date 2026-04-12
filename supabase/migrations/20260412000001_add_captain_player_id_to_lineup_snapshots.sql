ALTER TABLE lineup_snapshots ADD COLUMN IF NOT EXISTS captain_player_id uuid REFERENCES players(id) NULL;

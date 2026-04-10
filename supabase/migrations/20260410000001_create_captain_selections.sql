-- Captain selections: one captain per manager per week
CREATE TABLE IF NOT EXISTS captain_selections (
  id BIGSERIAL PRIMARY KEY,
  member_id UUID NOT NULL REFERENCES league_members(id) ON DELETE CASCADE,
  competition_id UUID NOT NULL,
  week INTEGER NOT NULL,
  captain_player_id UUID REFERENCES players(id) ON DELETE SET NULL,
  set_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT unique_captain_per_member_week UNIQUE (member_id, week)
);

CREATE INDEX IF NOT EXISTS idx_captain_selections_member_week
  ON captain_selections(member_id, week);

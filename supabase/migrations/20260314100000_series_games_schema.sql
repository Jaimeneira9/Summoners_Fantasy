-- Migration: series_games_schema
-- Created: 2026-03-14
-- Rollback:
--   DROP TABLE IF EXISTS player_series_stats;
--   DROP TABLE IF EXISTS player_game_stats;
--   DROP TABLE IF EXISTS games;
--   DROP TABLE IF EXISTS series;
--   DROP TABLE IF EXISTS teams;
--   DROP TABLE IF EXISTS competitions;
--   DROP TYPE IF EXISTS series_status;
--   DROP FUNCTION IF EXISTS set_updated_at();

-- === FORWARD MIGRATION ===

-- ------------------------------------------------------------
-- 0. Helper trigger function for updated_at
--    Guard: only create if it doesn't already exist
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ------------------------------------------------------------
-- 1. Enum: series_status
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type WHERE typname = 'series_status'
  ) THEN
    CREATE TYPE series_status AS ENUM ('scheduled', 'in_progress', 'finished');
  END IF;
END $$;

-- ------------------------------------------------------------
-- 2. Table: competitions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competitions (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text        NOT NULL UNIQUE,
  region     text        NOT NULL,
  tier       int         NOT NULL DEFAULT 1,
  is_active  boolean     NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN competitions.tier IS '1 = major league (LEC, LCK, LPL, LCS), 2 = secondary';

ALTER TABLE competitions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitions_select_public"
  ON competitions FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 3. Table: teams
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name           text        NOT NULL,
  code           text        NOT NULL UNIQUE,
  competition_id uuid        NOT NULL REFERENCES competitions(id) ON DELETE RESTRICT,
  logo_url       text,
  aliases        text[]      NOT NULL DEFAULT '{}',
  is_active      boolean     NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN teams.aliases IS 'Alternative names used by data sources such as gol.gg for fuzzy matching';

CREATE INDEX IF NOT EXISTS idx_teams_competition ON teams(competition_id);
CREATE INDEX IF NOT EXISTS idx_teams_code        ON teams(code);

ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "teams_select_public"
  ON teams FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 4. Table: series
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS series (
  id             uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid          NOT NULL REFERENCES competitions(id) ON DELETE RESTRICT,
  team_home_id   uuid          NOT NULL REFERENCES teams(id)        ON DELETE RESTRICT,
  team_away_id   uuid          NOT NULL REFERENCES teams(id)        ON DELETE RESTRICT,
  date           date          NOT NULL,
  week           int,
  split          text,
  season         int,
  status         series_status NOT NULL DEFAULT 'scheduled',
  winner_id      uuid          REFERENCES teams(id),
  game_count     int           NOT NULL DEFAULT 0,
  created_at     timestamptz   NOT NULL DEFAULT now(),
  updated_at     timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (team_home_id, team_away_id, date)
);

COMMENT ON COLUMN series.game_count IS 'Number of games played so far in this series';
COMMENT ON COLUMN series.winner_id  IS 'NULL until the series is finished';

CREATE INDEX IF NOT EXISTS idx_series_competition  ON series(competition_id);
CREATE INDEX IF NOT EXISTS idx_series_team_home    ON series(team_home_id);
CREATE INDEX IF NOT EXISTS idx_series_team_away    ON series(team_away_id);
CREATE INDEX IF NOT EXISTS idx_series_date         ON series(date);
CREATE INDEX IF NOT EXISTS idx_series_status       ON series(status);

CREATE TRIGGER trg_series_updated_at
  BEFORE UPDATE ON series
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE series ENABLE ROW LEVEL SECURITY;

CREATE POLICY "series_select_public"
  ON series FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 5. Table: games
--    Reuses the existing match_status enum ('scheduled', 'live', 'finished')
--    Does NOT rename or touch the existing matches table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
  id           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  series_id    uuid         NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  game_number  int          NOT NULL,
  team_home_id uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
  team_away_id uuid         NOT NULL REFERENCES teams(id) ON DELETE RESTRICT,
  duration_min numeric(6,2),
  winner_id    uuid         REFERENCES teams(id),
  status       match_status NOT NULL DEFAULT 'scheduled',
  created_at   timestamptz  NOT NULL DEFAULT now(),
  UNIQUE (series_id, game_number)
);

COMMENT ON COLUMN games.game_number IS 'Game sequence within the series (1-based)';
COMMENT ON COLUMN games.winner_id   IS 'NULL until the game is finished';

CREATE INDEX IF NOT EXISTS idx_games_series      ON games(series_id);
CREATE INDEX IF NOT EXISTS idx_games_team_home   ON games(team_home_id);
CREATE INDEX IF NOT EXISTS idx_games_team_away   ON games(team_away_id);
CREATE INDEX IF NOT EXISTS idx_games_status      ON games(status);

ALTER TABLE games ENABLE ROW LEVEL SECURITY;

CREATE POLICY "games_select_public"
  ON games FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 6. Table: player_game_stats
--    Individual game-level stats per player
--    Does NOT touch or rename player_match_stats
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_game_stats (
  id               uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id        uuid         NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  game_id          uuid         NOT NULL REFERENCES games(id)   ON DELETE CASCADE,
  kills            int          NOT NULL DEFAULT 0,
  deaths           int          NOT NULL DEFAULT 0,
  assists          int          NOT NULL DEFAULT 0,
  cs_per_min       numeric(5,2) NOT NULL DEFAULT 0,
  gold_diff_15     int,
  gold_diff_at_10  int,
  vision_score     int,
  damage_share     numeric(5,4),
  objective_steals int          NOT NULL DEFAULT 0,
  double_kill      boolean      NOT NULL DEFAULT false,
  triple_kill      boolean      NOT NULL DEFAULT false,
  quadra_kill      boolean      NOT NULL DEFAULT false,
  penta_kill       boolean      NOT NULL DEFAULT false,
  picks_correct    int,
  bans_effective   int,
  result           int          CHECK (result IN (0, 1)),
  game_points      numeric(8,2),
  created_at       timestamptz  NOT NULL DEFAULT now(),
  UNIQUE (player_id, game_id)
);

COMMENT ON COLUMN player_game_stats.result IS '0 = loss, 1 = win, NULL if game not finished';

CREATE INDEX IF NOT EXISTS idx_pgs_player  ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pgs_game    ON player_game_stats(game_id);

ALTER TABLE player_game_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "player_game_stats_select_public"
  ON player_game_stats FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 7. Table: player_series_stats
--    Aggregate stats per player per series (pre-computed by backend)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS player_series_stats (
  id                   uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id            uuid          NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  series_id            uuid          NOT NULL REFERENCES series(id)  ON DELETE CASCADE,
  games_played         int           NOT NULL DEFAULT 0,
  avg_kills            numeric(5,2)  NOT NULL DEFAULT 0,
  avg_deaths           numeric(5,2)  NOT NULL DEFAULT 0,
  avg_assists          numeric(5,2)  NOT NULL DEFAULT 0,
  avg_cs_per_min       numeric(5,2)  NOT NULL DEFAULT 0,
  avg_gold_diff_15     numeric(8,2),
  avg_gold_diff_at_10  numeric(8,2),
  avg_vision_score     numeric(5,2),
  avg_damage_share     numeric(5,4),
  avg_objective_steals numeric(5,2)  NOT NULL DEFAULT 0,
  -- 'penta', 'quadra', 'triple', 'double', NULL
  best_multikill       text          CHECK (best_multikill IN ('penta', 'quadra', 'triple', 'double')),
  avg_picks_correct    numeric(5,2),
  avg_bans_effective   numeric(5,2),
  series_points        numeric(8,2),
  created_at           timestamptz   NOT NULL DEFAULT now(),
  updated_at           timestamptz   NOT NULL DEFAULT now(),
  UNIQUE (player_id, series_id)
);

COMMENT ON COLUMN player_series_stats.best_multikill IS 'Highest multikill achieved across all games in the series';

CREATE INDEX IF NOT EXISTS idx_pss_player ON player_series_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_pss_series ON player_series_stats(series_id);

CREATE TRIGGER trg_player_series_stats_updated_at
  BEFORE UPDATE ON player_series_stats
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE player_series_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "player_series_stats_select_public"
  ON player_series_stats FOR SELECT
  USING (true);

-- ------------------------------------------------------------
-- 8. Seed data: LEC competition + 10 teams
--    Idempotent via ON CONFLICT DO NOTHING
-- ------------------------------------------------------------
DO $$
DECLARE
  v_competition_id uuid;
BEGIN
  -- Insert LEC competition
  INSERT INTO competitions (name, region, tier, is_active)
  VALUES ('LEC', 'EU', 1, true)
  ON CONFLICT (name) DO NOTHING;

  SELECT id INTO v_competition_id FROM competitions WHERE name = 'LEC';

  -- Insert 10 LEC 2026 teams
  INSERT INTO teams (name, code, competition_id, aliases) VALUES
    ('G2 Esports',      'G2',  v_competition_id, ARRAY['G2 Esports', 'G2']),
    ('Fnatic',          'FNC', v_competition_id, ARRAY['Fnatic', 'FNC']),
    ('Team Vitality',   'VIT', v_competition_id, ARRAY['Team Vitality', 'Vitality', 'VIT']),
    ('BDS Esports',     'BDS', v_competition_id, ARRAY['BDS Esports', 'Team BDS', 'BDS']),
    ('Karmine Corp',    'KC',  v_competition_id, ARRAY['Karmine Corp', 'KC']),
    ('SK Gaming',       'SK',  v_competition_id, ARRAY['SK Gaming', 'SK']),
    ('Team Heretics',   'TH',  v_competition_id, ARRAY['Team Heretics', 'Heretics', 'TH']),
    ('GIANTX',          'GX',  v_competition_id, ARRAY['GIANTX', 'Giants', 'GX']),
    ('Rogue',           'RGE', v_competition_id, ARRAY['Rogue', 'RGE']),
    ('MAD Lions KOI',   'MDK', v_competition_id, ARRAY['MAD Lions KOI', 'MAD Lions', 'MDK', 'KOI'])
  ON CONFLICT (code) DO NOTHING;
END $$;

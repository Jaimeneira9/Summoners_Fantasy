-- Migration: market_redesign_candidates_trades
-- Adds market_candidates (pre-listing queue) and trade_offers (player trades between members)

CREATE TABLE market_candidates (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  league_id  uuid NOT NULL REFERENCES fantasy_leagues(id) ON DELETE CASCADE,
  player_id  uuid NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  seller_id  uuid REFERENCES league_members(id) ON DELETE SET NULL,
  ask_price  numeric NOT NULL,
  added_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE trade_offers (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  league_id           uuid NOT NULL REFERENCES fantasy_leagues(id) ON DELETE CASCADE,
  from_member_id      uuid NOT NULL REFERENCES league_members(id) ON DELETE CASCADE,
  to_member_id        uuid NOT NULL REFERENCES league_members(id) ON DELETE CASCADE,
  offered_player_id   uuid REFERENCES players(id) ON DELETE SET NULL,
  requested_player_id uuid REFERENCES players(id) ON DELETE SET NULL,
  offered_money       numeric NOT NULL DEFAULT 0,
  requested_money     numeric NOT NULL DEFAULT 0,
  status              text NOT NULL DEFAULT 'pending',
  created_at          timestamptz NOT NULL DEFAULT now(),
  expires_at          timestamptz
);

ALTER TABLE trade_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_candidates ENABLE ROW LEVEL SECURITY;

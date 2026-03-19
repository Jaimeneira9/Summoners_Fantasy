-- Migration: rls_policies_new_market_tables
-- RLS policies for market_candidates, trade_offers, and sell_offers

-- market_candidates
CREATE POLICY "League members can view candidates"
  ON market_candidates FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM league_members
    WHERE league_members.league_id = market_candidates.league_id
      AND league_members.user_id = auth.uid()
  ));

CREATE POLICY "members can read own candidates"
  ON market_candidates FOR SELECT
  USING (
    seller_id IN (SELECT id FROM league_members WHERE user_id = auth.uid())
    OR seller_id IS NULL
  );

-- trade_offers
CREATE POLICY "Members can create trade offers"
  ON trade_offers FOR INSERT
  WITH CHECK (EXISTS (
    SELECT 1 FROM league_members
    WHERE league_members.id = trade_offers.from_member_id
      AND league_members.user_id = auth.uid()
      AND league_members.league_id = trade_offers.league_id
  ));

CREATE POLICY "Trade participants can view offers"
  ON trade_offers FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM league_members
    WHERE league_members.user_id = auth.uid()
      AND (
        league_members.id = trade_offers.from_member_id
        OR league_members.id = trade_offers.to_member_id
      )
  ));

-- sell_offers
CREATE POLICY "Members can view their own sell offers"
  ON sell_offers FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM league_members
    WHERE league_members.id = sell_offers.member_id
      AND league_members.user_id = auth.uid()
  ));

CREATE POLICY "members can read own sell_offers"
  ON sell_offers FOR SELECT
  USING (
    member_id IN (SELECT id FROM league_members WHERE user_id = auth.uid())
  );

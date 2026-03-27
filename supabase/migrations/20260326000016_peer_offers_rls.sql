-- Allow all members of the same league to READ peer sell_offers
-- (rows where from_member_id IS NOT NULL, meaning they originate from another manager)
CREATE POLICY "league members can read peer sell_offers"
  ON sell_offers FOR SELECT
  USING (
    from_member_id IS NOT NULL
    AND league_id IN (
      SELECT league_id FROM league_members WHERE user_id = auth.uid()
    )
  );

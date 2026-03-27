ALTER TABLE sell_offers
  ADD COLUMN IF NOT EXISTS from_member_id uuid REFERENCES league_members(id) ON DELETE SET NULL;

COMMENT ON COLUMN sell_offers.from_member_id IS 'NULL = oferta del sistema, UUID = oferta de otro manager';

-- Adds release clause system to roster_players
ALTER TABLE roster_players
  ADD COLUMN IF NOT EXISTS clause_amount    numeric(10,2),
  ADD COLUMN IF NOT EXISTS clause_expires_at timestamptz;

-- Add clause transaction type
ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'clause';

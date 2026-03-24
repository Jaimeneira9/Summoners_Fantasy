-- Atomic budget deduction to prevent TOCTOU race conditions
-- Returns TRUE if deduction succeeded, FALSE if insufficient funds
CREATE OR REPLACE FUNCTION deduct_budget(
  p_member_id  uuid,
  p_amount     numeric
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  rows_affected integer;
BEGIN
  UPDATE league_members
  SET remaining_budget = remaining_budget - p_amount
  WHERE id = p_member_id
    AND remaining_budget >= p_amount;

  GET DIAGNOSTICS rows_affected = ROW_COUNT;
  RETURN rows_affected > 0;
END;
$$;

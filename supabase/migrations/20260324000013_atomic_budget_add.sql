-- Atomic budget addition (for seller credit)
CREATE OR REPLACE FUNCTION add_budget(
  p_member_id  uuid,
  p_amount     numeric
) RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE league_members
  SET remaining_budget = remaining_budget + p_amount
  WHERE id = p_member_id;
END;
$$;

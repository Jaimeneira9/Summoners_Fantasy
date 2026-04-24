CREATE OR REPLACE FUNCTION public.swap_budget(
  p_member_id    uuid,
  p_release      numeric,
  p_cost         numeric
) RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  rows_affected integer;
BEGIN
  UPDATE league_members
  SET remaining_budget = remaining_budget + p_release - p_cost
  WHERE id = p_member_id
    AND remaining_budget + p_release >= p_cost;

  GET DIAGNOSTICS rows_affected = ROW_COUNT;
  RETURN rows_affected > 0;
END;
$$;

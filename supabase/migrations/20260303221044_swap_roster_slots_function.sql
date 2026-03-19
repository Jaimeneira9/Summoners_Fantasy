-- Migration: swap_roster_slots_function
-- Atomic swap of two roster slots using a single UPDATE to avoid constraint violations

CREATE OR REPLACE FUNCTION public.swap_roster_slots(
  p_roster_id uuid,
  p_id_a      uuid,
  p_slot_a    text,
  p_id_b      uuid,
  p_slot_b    text
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- Mueve A a un slot temporal fuera del check constraint no es posible,
  -- así que actualizamos ambas filas en una sola sentencia usando un CTE.
  UPDATE roster_players AS rp
  SET slot = CASE
    WHEN rp.id = p_id_a THEN p_slot_a
    WHEN rp.id = p_id_b THEN p_slot_b
  END
  WHERE rp.roster_id = p_roster_id
    AND rp.id IN (p_id_a, p_id_b);
END;
$$;

-- Migration: fantasy_leagues_competition_fk
-- Propósito: Reemplazar fantasy_leagues.competition (TEXT) por competition_id (UUID FK)
--            para tener integridad referencial con la tabla competitions.
-- Pre-requisito: 20260416000001_drop_competitions_one_active debe estar aplicada.
-- CRÍTICO: Hacer backup de fantasy_leagues antes de ejecutar.
-- Rollback: ver design doc sdd/fase-1-db-foundations/design en engram.

-- Paso 1: Agregar columna nullable
ALTER TABLE fantasy_leagues
  ADD COLUMN IF NOT EXISTS competition_id UUID REFERENCES competitions(id) ON DELETE RESTRICT;

-- Paso 2: Backfill — asignar la competition LEC activa a todas las ligas existentes
UPDATE fantasy_leagues
SET competition_id = COALESCE(
  (SELECT id FROM competitions WHERE name ILIKE '%LEC%' AND is_active = true LIMIT 1),
  (SELECT id FROM competitions WHERE name ILIKE '%LEC%' LIMIT 1),
  (SELECT id FROM competitions LIMIT 1)
)
WHERE competition_id IS NULL;

-- Paso 3a: Guard pre-NOT NULL — falla ruidosamente si backfill incompleto
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM fantasy_leagues WHERE competition_id IS NULL) THEN
    RAISE EXCEPTION 'Backfill incompleto: hay rows en fantasy_leagues con competition_id NULL. Verificar que existe al menos una competition en la tabla.';
  END IF;
END $$;

-- Paso 3b: Hacer NOT NULL
ALTER TABLE fantasy_leagues
  ALTER COLUMN competition_id SET NOT NULL;

-- Paso 3c: Drop la columna competition (texto) — IRREVERSIBLE sin backup
ALTER TABLE fantasy_leagues
  DROP COLUMN IF EXISTS competition;

-- Paso 3d: Índice para performance de lookups por competition
CREATE INDEX IF NOT EXISTS idx_fantasy_leagues_competition_id
  ON fantasy_leagues (competition_id);

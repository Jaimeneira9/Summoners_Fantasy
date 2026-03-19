-- Migration: unify_splits_into_competitions
-- Created: 2026-03-16
-- Rollback:
--   (no rollback provided — this is a destructive migration)
--
-- Context:
--   La tabla `splits` fue creada en 20260309000006 como entidad separada a competitions.
--   Ahora que `competitions` es la fuente de verdad para una competición activa,
--   unificamos ambas tablas: movemos start_date/end_date/reset_date a competitions,
--   migramos las FKs de member_split_scores y split_protect_history, y dropeamos splits.
--
--   Dependencias con FK a splits(id) que hay que migrar primero:
--     - member_split_scores.split_id
--     - split_protect_history.split_id
--   Dependencias sin FK directo a splits pero que usaban splits.is_active:
--     - matches.split_id (UUID, era FK a splits) → se setea NULL, la columna se mantiene
--       como referencia interna no crítica (no hay datos importantes ahí)

-- === FORWARD MIGRATION ===

-- ------------------------------------------------------------
-- 1. Agregar columnas faltantes a competitions
-- ------------------------------------------------------------
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS start_date date,
  ADD COLUMN IF NOT EXISTS end_date   date,
  ADD COLUMN IF NOT EXISTS reset_date date;

-- ------------------------------------------------------------
-- 2. Migrar datos de splits → competitions (match por nombre)
--    Solo rows con reset_date configurado tienen valor real.
--    El match es por nombre exacto (ambas tienen UNIQUE name).
-- ------------------------------------------------------------
UPDATE competitions c
SET
  start_date = s.start_date,
  end_date   = s.end_date,
  reset_date = s.reset_date
FROM splits s
WHERE lower(c.name) = lower(s.name)
  AND s.reset_date IS NOT NULL;

-- ------------------------------------------------------------
-- 3. Unique partial index en competitions para garantizar
--    al máximo una competición activa a la vez
--    (splits ya tenía splits_one_active sobre su propia tabla)
-- ------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS competitions_one_active
  ON competitions (is_active)
  WHERE is_active = true;

-- ------------------------------------------------------------
-- 4. Migrar FKs de member_split_scores
--    split_id actualmente apunta a splits(id).
--    Lo convertimos en competition_id apuntando a competitions(id).
--    Paso: DROP constraint FK + renombrar columna + recrear FK.
-- ------------------------------------------------------------

-- 4a. Primero setear split_id = competitions.id donde haya match por nombre
--     (la mayoría de rows en un sistema de test/staging no tendrán datos reales,
--      pero si los hay, los preservamos)
ALTER TABLE member_split_scores
  ADD COLUMN IF NOT EXISTS competition_id uuid REFERENCES competitions(id) ON DELETE CASCADE;

-- Intentar migrar los datos si hay match entre splits.id y la columna split_id
UPDATE member_split_scores mss
SET competition_id = c.id
FROM splits s
JOIN competitions c ON lower(c.name) = lower(s.name)
WHERE mss.split_id = s.id;

-- Para rows que no pudieron matchearse (split sin competition equivalente),
-- asignar la competition activa como fallback
UPDATE member_split_scores
SET competition_id = (
  SELECT id FROM competitions WHERE is_active = true LIMIT 1
)
WHERE competition_id IS NULL;

-- 4b. Drop la columna vieja + drop el unique constraint que la incluía
--     El constraint UNIQUE (member_id, split_id) incluye split_id.
ALTER TABLE member_split_scores DROP CONSTRAINT IF EXISTS member_split_scores_member_id_split_id_key;

-- 4c. Drop la columna split_id (ya no apunta a splits — la tabla se va a dropear)
ALTER TABLE member_split_scores DROP COLUMN IF EXISTS split_id;

-- 4d. Recrear el unique constraint sobre (member_id, competition_id)
ALTER TABLE member_split_scores
  ADD CONSTRAINT member_split_scores_member_id_competition_id_key
  UNIQUE (member_id, competition_id);

-- ------------------------------------------------------------
-- 5. Migrar FKs de split_protect_history
--    Mismo proceso: split_id → competition_id
-- ------------------------------------------------------------

-- 5a. Agregar columna nueva
ALTER TABLE split_protect_history
  ADD COLUMN IF NOT EXISTS competition_id uuid REFERENCES competitions(id) ON DELETE CASCADE;

-- 5b. Migrar datos por match de nombre
UPDATE split_protect_history sph
SET competition_id = c.id
FROM splits s
JOIN competitions c ON lower(c.name) = lower(s.name)
WHERE sph.split_id = s.id;

-- Fallback: asignar competition activa para rows huérfanas
UPDATE split_protect_history
SET competition_id = (
  SELECT id FROM competitions WHERE is_active = true LIMIT 1
)
WHERE competition_id IS NULL;

-- 5c. Drop unique constraint que incluye split_id
ALTER TABLE split_protect_history DROP CONSTRAINT IF EXISTS split_protect_history_member_id_player_id_split_id_key;

-- 5d. Drop la columna split_id
ALTER TABLE split_protect_history DROP COLUMN IF EXISTS split_id;

-- 5e. Recrear el unique constraint
ALTER TABLE split_protect_history
  ADD CONSTRAINT split_protect_history_member_id_player_id_competition_id_key
  UNIQUE (member_id, player_id, competition_id);

-- ------------------------------------------------------------
-- 6. Limpiar FK de matches.split_id
--    matches.split_id apuntaba a splits(id) con un índice, pero la columna
--    split_id en matches es nullable y probablemente sin datos reales.
--    La constraint FK debe dropearse antes de eliminar splits.
--    Nota: matches ya tiene una columna text 'split' (Spring/Summer) separada —
--    la columna split_id (uuid) fue la FK a splits y ya no se necesita.
-- ------------------------------------------------------------
ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_split_id_fkey;
ALTER TABLE matches DROP COLUMN IF EXISTS split_id;

-- ------------------------------------------------------------
-- 7. Drop tabla splits (y sus dependencias directas)
--    En este punto ya no hay FKs apuntando a splits(id).
--    CASCADE por si quedan políticas RLS u objetos dependientes.
-- ------------------------------------------------------------
DROP TABLE IF EXISTS splits CASCADE;


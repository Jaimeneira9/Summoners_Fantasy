-- Agregar current_week a competitions para que el pipeline sepa en qué jornada está
ALTER TABLE competitions ADD COLUMN IF NOT EXISTS current_week INT DEFAULT 1;

-- Backfill: la competition activa está en week=3 (según datos actuales)
UPDATE competitions SET current_week = 3 WHERE is_active = true;

COMMENT ON COLUMN competitions.current_week IS
  'Semana actual de la competición. El pipeline solo procesa y snapshottea esta semana.';

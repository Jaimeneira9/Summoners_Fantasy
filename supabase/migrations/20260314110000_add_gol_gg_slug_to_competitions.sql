-- Migration: add_gol_gg_slug_to_competitions
-- Created: 2026-03-14
-- Rollback:
--   ALTER TABLE competitions DROP COLUMN IF EXISTS gol_gg_slug;

-- === FORWARD MIGRATION ===

ALTER TABLE competitions ADD COLUMN IF NOT EXISTS gol_gg_slug text;

UPDATE competitions SET gol_gg_slug = 'LEC 2026 Versus Season' WHERE name = 'LEC';

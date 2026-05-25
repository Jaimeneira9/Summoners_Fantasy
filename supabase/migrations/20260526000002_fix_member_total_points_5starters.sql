-- Fix: Regla de negocio "5 starters o 0 puntos por jornada" en vista member_total_points
--
-- Problema: la vista sumaba puntos de TODAS las jornadas, incluso aquellas donde el manager
-- tenía menos de 5 starters con player_id asignado (lineup incompleto).
-- El backend (scoring.py _calc_week_points) ya aplicaba esta regla correctamente,
-- pero la vista la ignoraba, generando inconsistencias entre la vista y el scoring real.
--
-- Fix: agregar filtro EXISTS que solo incluye filas de jornadas donde el manager
-- tenía >= 5 starters (slots sin 'bench%') con player_id NOT NULL.

CREATE OR REPLACE VIEW member_total_points AS
SELECT
  ls.member_id,
  SUM(
    CASE
      WHEN ls.player_id = ls.captain_player_id THEN COALESCE(pss.series_points, 0::numeric) * 2::numeric
      ELSE COALESCE(pss.series_points, 0::numeric)
    END
  ) AS total_points
FROM lineup_snapshots ls
JOIN league_members lm ON lm.id = ls.member_id
JOIN fantasy_leagues fl ON fl.id = lm.league_id
JOIN series s ON s.competition_id = fl.competition_id
           AND s.week = ls.week
           AND s.status = 'finished'::series_status
JOIN player_series_stats pss ON pss.player_id = ls.player_id AND pss.series_id = s.id
WHERE ls.slot::text !~~ 'bench%'::text
  AND EXISTS (
    SELECT 1
    FROM lineup_snapshots ls2
    WHERE ls2.member_id = ls.member_id
      AND ls2.week = ls.week
      AND ls2.slot !~~ 'bench%'
      AND ls2.player_id IS NOT NULL
    HAVING COUNT(*) >= 5
  )
GROUP BY ls.member_id;

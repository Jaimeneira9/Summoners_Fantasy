-- Migration: backfill avg_dpm, avg_wards_per_min, kill_participation
--            in player_series_stats from existing player_game_stats data.
-- Created: 2026-03-16
--
-- Columnas fuente en player_game_stats:
--   dpm            INTEGER  (added by 20260314120000_add_extended_player_game_stats.sql)
--   wards_placed   INTEGER  (added by 20260314120000_add_extended_player_game_stats.sql)
--   wards_destroyed INTEGER (added by 20260314120000_add_extended_player_game_stats.sql)
--   kills          INTEGER
--   assists        INTEGER
-- Columna fuente en games:
--   duration_min   numeric(6,2)
--
-- Para kill_participation necesitamos team_kills por game.
-- Se calcula sumando kills de todos los jugadores del mismo equipo en el game.
-- La asignación de equipo se hace via: players.team (text) = teams.name (text),
-- y games.team_home_id / games.team_away_id para saber qué equipo jugó cada lado.

WITH

-- Paso 1: kills totales por equipo por game
team_kills_per_game AS (
  SELECT
    pgs.game_id,
    t.id AS team_id,
    SUM(pgs.kills) AS team_total_kills
  FROM player_game_stats pgs
  JOIN players p ON p.id = pgs.player_id
  -- Joinear el nombre del equipo del jugador con la tabla teams
  JOIN teams t ON t.name = p.team
  GROUP BY pgs.game_id, t.id
),

-- Paso 2: stats por jugador por game con métricas calculadas
per_game_metrics AS (
  SELECT
    pgs.player_id,
    g.series_id,
    -- avg_dpm: directamente de la columna dpm
    pgs.dpm::numeric                                      AS game_dpm,
    -- avg_wards_per_min: (wards_placed + wards_destroyed) / duration_min
    CASE
      WHEN g.duration_min IS NOT NULL AND g.duration_min > 0
        THEN (pgs.wards_placed + pgs.wards_destroyed)::numeric / g.duration_min
      ELSE NULL
    END                                                   AS game_wards_per_min,
    -- kill_participation: (kills + assists) / team_kills
    -- Determinamos el equipo del jugador y usamos los team_kills del mismo equipo en el game
    CASE
      WHEN tkpg.team_total_kills IS NOT NULL AND tkpg.team_total_kills > 0
        THEN (pgs.kills + pgs.assists)::numeric / tkpg.team_total_kills
      ELSE NULL
    END                                                   AS game_kill_participation
  FROM player_game_stats pgs
  JOIN games g ON g.id = pgs.game_id
  JOIN players p ON p.id = pgs.player_id
  JOIN teams t ON t.name = p.team
  -- Unir con team_kills del mismo equipo del jugador en este game
  LEFT JOIN team_kills_per_game tkpg
    ON tkpg.game_id = pgs.game_id AND tkpg.team_id = t.id
),

-- Paso 3: agregar por (player_id, series_id)
series_aggregates AS (
  SELECT
    player_id,
    series_id,
    AVG(game_dpm)               AS avg_dpm,
    AVG(game_wards_per_min)     AS avg_wards_per_min,
    AVG(game_kill_participation) AS kill_participation
  FROM per_game_metrics
  GROUP BY player_id, series_id
)

-- Paso 4: actualizar player_series_stats solo donde los valores calculados son no nulos
UPDATE player_series_stats pss
SET
  avg_dpm            = ROUND(sa.avg_dpm::numeric, 2),
  avg_wards_per_min  = ROUND(sa.avg_wards_per_min::numeric, 3),
  kill_participation = ROUND(
    -- clamp entre 0 y 1 por si hay datos de multikill que eleven kills/assists artificialmente
    LEAST(sa.kill_participation::numeric, 1.0),
    4
  )
FROM series_aggregates sa
WHERE pss.player_id = sa.player_id
  AND pss.series_id = sa.series_id
  AND (sa.avg_dpm IS NOT NULL
       OR sa.avg_wards_per_min IS NOT NULL
       OR sa.kill_participation IS NOT NULL);

-- Fix B: Hardening de la vista member_total_points
--
-- Problema: la vista original usaba `ls.competition_id` (del snapshot) para hacer JOIN con series.
-- Si el snapshot tenía competition_id incorrecto (bug del backfill LES→LEC), el JOIN no encontraba
-- series y el manager sumaba 0 puntos para esas semanas.
--
-- Fix: usar `fl.competition_id` (de la fantasy_league del manager via league_members) en lugar de
-- `ls.competition_id`. Así el JOIN siempre usa la competition correcta del manager, independientemente
-- de lo que haya en el snapshot.

CREATE OR REPLACE VIEW member_total_points AS
SELECT ls.member_id,
    sum(
        CASE
            WHEN ls.player_id = ls.captain_player_id THEN COALESCE(pss.series_points, 0::numeric) * 2::numeric
            ELSE COALESCE(pss.series_points, 0::numeric)
        END) AS total_points
FROM lineup_snapshots ls
JOIN league_members lm ON lm.id = ls.member_id
JOIN fantasy_leagues fl ON fl.id = lm.league_id
JOIN series s ON s.competition_id = fl.competition_id
             AND s.week = ls.week
             AND s.status = 'finished'
JOIN player_series_stats pss ON pss.player_id = ls.player_id AND pss.series_id = s.id
WHERE ls.slot::text !~~ 'bench%'::text
GROUP BY ls.member_id;

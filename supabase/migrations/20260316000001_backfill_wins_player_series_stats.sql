UPDATE player_series_stats pss
SET wins = (
    SELECT COUNT(*)
    FROM player_game_stats pgs
    JOIN games g ON pgs.game_id = g.id
    WHERE pgs.player_id = pss.player_id
      AND g.series_id = pss.series_id
      AND pgs.result = 1
);

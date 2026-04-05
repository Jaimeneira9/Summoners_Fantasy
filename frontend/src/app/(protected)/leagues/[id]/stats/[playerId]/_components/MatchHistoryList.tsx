"use client";

import { api, type GameDetailStat } from "@/lib/api";
import type { WeekStat } from "./types";

export function MatchHistoryList({
  matchStats,
  selectedWeek,
  expandedSeriesId,
  gamesCache,
  gamesLoading,
  player,
  playerId,
  onSelectWeek,
  onGamesLoaded,
  onGamesLoadingChange,
  onExpandedSeriesIdChange,
}: {
  matchStats: WeekStat[];
  selectedWeek: number | null;
  expandedSeriesId: string | null;
  gamesCache: Map<string, GameDetailStat[]>;
  gamesLoading: string | null;
  player: { team: string };
  playerId: string;
  onSelectWeek: (week: number) => void;
  onGamesLoaded: (seriesId: string, games: GameDetailStat[]) => void;
  onGamesLoadingChange: (seriesId: string | null) => void;
  onExpandedSeriesIdChange: (seriesId: string | null) => void;
}) {
  return (
    <div style={{
      flex: 1,
      background: "#111111",
      borderRadius: 12,
      padding: 20,
      border: "1px solid #1E1E1E",
      overflowY: "auto",
      maxHeight: 300,
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", marginBottom: 14 }}>
        Jornadas
      </div>

      {matchStats.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {[...matchStats].reverse().map((stat) => {
            const isActive = stat.week === selectedWeek;
            const isWin = stat.result === 1;
            const kda = `${typeof stat.kills === 'number' ? stat.kills.toFixed(1) : stat.kills}/${typeof stat.deaths === 'number' ? stat.deaths.toFixed(1) : stat.deaths}/${typeof stat.assists === 'number' ? stat.assists.toFixed(1) : stat.assists}`;
            const rival = stat.matches
              ? (stat.matches.team_1 === player.team ? stat.matches.team_2 : stat.matches.team_1)
              : null;
            const seriesId = stat.series_id ?? null;
            const isExpanded = seriesId !== null && expandedSeriesId === seriesId;
            const isLoadingGames = seriesId !== null && gamesLoading === seriesId;
            const cachedGames = seriesId ? gamesCache.get(seriesId) : undefined;

            const handleToggleExpand = (e: React.MouseEvent) => {
              e.stopPropagation();
              if (!seriesId) return;
              if (isExpanded) {
                onExpandedSeriesIdChange(null);
                return;
              }
              onExpandedSeriesIdChange(seriesId);
              if (!gamesCache.has(seriesId)) {
                onGamesLoadingChange(seriesId);
                api.players.seriesGames(playerId, seriesId)
                  .then((resp) => {
                    onGamesLoaded(seriesId, resp.games);
                  })
                  .catch(() => {
                    onGamesLoaded(seriesId, []);
                  })
                  .finally(() => onGamesLoadingChange(null));
              }
            };

            return (
              <div key={stat.week} style={{ display: "flex", flexDirection: "column" }}>
                <div
                  onClick={() => onSelectWeek(stat.week)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 10px",
                    borderRadius: isExpanded ? "8px 8px 0 0" : 8,
                    cursor: "pointer",
                    background: isActive ? "#1E1A00" : "transparent",
                    border: isActive ? "1px solid rgba(252,212,0,0.25)" : "1px solid transparent",
                    transition: "background 0.1s",
                  }}
                >
                  {/* Week badge */}
                  <div style={{
                    background: "#1A1A1A",
                    borderRadius: 6,
                    padding: "3px 8px",
                    fontSize: 12,
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontWeight: 700,
                    color: isActive ? "#FCD400" : "#888",
                    flexShrink: 0,
                    minWidth: 36,
                    textAlign: "center",
                  }}>
                    S{stat.week}
                  </div>

                  {/* W/L badge */}
                  <div style={{
                    width: 22,
                    height: 22,
                    borderRadius: 4,
                    background: isWin ? "#1B3A1B" : "#3A1A1A",
                    color: isWin ? "#4CAF50" : "#EF5350",
                    fontSize: 10,
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    {isWin ? "W" : "L"}
                  </div>

                  {/* Rival + KDA */}
                  <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                    {rival && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${rival.toLowerCase().replace(/ /g, "-")}.webp`}
                        alt={rival}
                        style={{ width: 20, height: 20, objectFit: "contain", flexShrink: 0 }}
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                      />
                    )}
                    <div style={{ fontSize: 11, color: "#444" }}>{kda}</div>
                  </div>

                  {/* Puntos */}
                  <div style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontSize: 14,
                    fontWeight: 700,
                    color: isWin ? "#FCD400" : "#555",
                    flexShrink: 0,
                  }}>
                    +{Math.round(stat.fantasy_points)}
                  </div>

                  {/* Expand chevron */}
                  {seriesId && (
                    <div
                      onClick={handleToggleExpand}
                      style={{
                        fontSize: 10,
                        color: isExpanded ? "#FCD400" : "#444",
                        cursor: "pointer",
                        flexShrink: 0,
                        padding: "2px 4px",
                        transition: "transform 0.15s",
                        transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                      }}
                    >
                      ▶
                    </div>
                  )}
                </div>

                {/* Accordion: game-by-game detail */}
                {isExpanded && (
                  <div style={{
                    background: "#1a1a1a",
                    border: "1px solid #2a2a2a",
                    borderTop: "none",
                    borderRadius: "0 0 8px 8px",
                    padding: "8px 10px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}>
                    {isLoadingGames ? (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 0" }}>
                        <div style={{
                          width: 14,
                          height: 14,
                          borderRadius: "50%",
                          border: "2px solid #333",
                          borderTopColor: "#FCD400",
                          animation: "spin 0.7s linear infinite",
                        }} />
                      </div>
                    ) : cachedGames && cachedGames.length > 0 ? (
                      <>
                        {/* Header */}
                        <div style={{
                          display: "grid",
                          gridTemplateColumns: "40px 28px 1fr 52px 44px 44px",
                          gap: 4,
                          fontSize: 9,
                          color: "#444",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          paddingBottom: 4,
                          borderBottom: "1px solid #222",
                        }}>
                          <span>Game</span>
                          <span></span>
                          <span>K/D/A</span>
                          <span style={{ textAlign: "right" }}>CS/min</span>
                          <span style={{ textAlign: "right" }}>DPM</span>
                          <span style={{ textAlign: "right" }}>Pts</span>
                        </div>
                        {cachedGames.map((g) => {
                          const gWin = g.result === 1;
                          return (
                            <div
                              key={g.game_number}
                              style={{
                                display: "grid",
                                gridTemplateColumns: "40px 28px 1fr 52px 44px 44px",
                                gap: 4,
                                alignItems: "center",
                                fontSize: 11,
                                color: "#ccc",
                                fontFamily: "'Space Grotesk', sans-serif",
                              }}
                            >
                              <span style={{ color: "#555", fontFamily: "'Barlow Condensed', sans-serif", fontSize: 12, fontWeight: 700 }}>
                                G{g.game_number}
                              </span>
                              <div style={{
                                width: 20,
                                height: 20,
                                borderRadius: 3,
                                background: g.result === null ? "#222" : gWin ? "#1B3A1B" : "#3A1A1A",
                                color: g.result === null ? "#555" : gWin ? "#4CAF50" : "#EF5350",
                                fontSize: 9,
                                fontWeight: 700,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}>
                                {g.result === null ? "?" : gWin ? "W" : "L"}
                              </div>
                              <span style={{ color: "#666", fontSize: 11 }}>
                                {g.kills}/{g.deaths}/{g.assists}
                              </span>
                              <span style={{ textAlign: "right", color: "#888", fontSize: 11 }}>
                                {g.cs_per_min.toFixed(1)}
                              </span>
                              <span style={{ textAlign: "right", color: "#888", fontSize: 11 }}>
                                {Math.round(g.dpm)}
                              </span>
                              <span style={{
                                textAlign: "right",
                                fontFamily: "'Barlow Condensed', sans-serif",
                                fontSize: 12,
                                fontWeight: 700,
                                color: gWin ? "#FCD400" : "#555",
                              }}>
                                {Math.round(g.game_points)}
                              </span>
                            </div>
                          );
                        })}
                      </>
                    ) : (
                      <p style={{ fontSize: 11, color: "#444", textAlign: "center", margin: 0 }}>Sin datos de games</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
          <p style={{ color: "#333", fontSize: 13 }}>Sin jornadas disponibles</p>
        </div>
      )}
    </div>
  );
}

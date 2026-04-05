"use client";

import type { WeekStat } from "./types";

export function WeekSelector({
  matchStats,
  selectedWeek,
  onSelectWeek,
  player,
}: {
  matchStats: WeekStat[];
  selectedWeek: number | null;
  onSelectWeek: (week: number) => void;
  player: { team: string };
}) {
  const activeStat = matchStats.find((s) => s.week === selectedWeek);
  const activeIsWin = activeStat ? activeStat.result === 1 : false;
  const activeRival = activeStat?.matches
    ? (activeStat.matches.team_1 === player.team
        ? activeStat.matches.team_2
        : activeStat.matches.team_1)
    : null;

  return (
    <div style={{
      background: "#111111",
      borderRadius: 10,
      padding: "12px 16px",
      border: "1px solid #1E1E1E",
      marginBottom: 12,
    }}>
      {/* Week chips — scrollable horizontal strip */}
      <div style={{
        display: "flex",
        overflowX: "auto",
        flexWrap: "nowrap",
        gap: 6,
        paddingBottom: 4,
        scrollbarWidth: "none",
        msOverflowStyle: "none",
        WebkitOverflowScrolling: "touch",
      } as React.CSSProperties}>
        {matchStats.map((stat) => {
          const isActive = stat.week === selectedWeek;
          return (
            <button
              key={stat.week}
              onClick={() => onSelectWeek(stat.week)}
              className={`week-chip ${isActive ? "week-chip-active" : "week-chip-inactive"}`}
              style={{
                background: isActive ? "#FCD400" : "#1A1A1A",
                border: `1px solid ${isActive ? "#FCD400" : "#2A2A2A"}`,
                borderRadius: 8,
                padding: "6px 14px",
                color: isActive ? "#000" : "#777",
                fontSize: 12,
                fontWeight: isActive ? 700 : 500,
                cursor: "pointer",
                fontFamily: "'Barlow Condensed', sans-serif",
                letterSpacing: "0.04em",
                flexShrink: 0,
              }}
            >
              S{stat.week}
            </button>
          );
        })}
      </div>

      {/* Active week badge */}
      {activeStat && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
          <div style={{
            background: activeIsWin ? "#1B3A1B" : "#3A1A1A",
            color: activeIsWin ? "#4CAF50" : "#EF5350",
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 6,
          }}>
            {activeIsWin ? "W" : "L"}
          </div>
          {activeRival && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${activeRival.toLowerCase().replace(/ /g, "-")}.webp`}
              alt={activeRival}
              style={{ width: 20, height: 20, objectFit: "contain" }}
              onError={(e) => { e.currentTarget.style.display = "none"; }}
            />
          )}
          <span style={{ fontSize: 12, color: "#FCD400", fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif" }}>
            +{Math.round(activeStat.fantasy_points)} pts
          </span>
        </div>
      )}
    </div>
  );
}

"use client";

import type { WeekStat } from "./types";

type StatCard = {
  label: string;
  value: string;
  barPct: number | null;
  deathColor?: string;
  breakdownKey?: string;
};

export function StatCards({
  statCards,
  selectedStat,
}: {
  statCards: StatCard[];
  selectedStat: WeekStat;
}) {
  return (
    <div style={{ overflowX: "auto", marginBottom: 12, WebkitOverflowScrolling: "touch" } as React.CSSProperties}>
      <div style={{ display: "flex", gap: 10, minWidth: "max-content" }}>
        {statCards.map((card) => (
          <div
            key={card.label}
            className="stat-card"
            style={{
              background: "#111111",
              borderRadius: 10,
              padding: 16,
              border: "1px solid #1E1E1E",
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 4,
              cursor: "default",
            }}
          >
            <div style={{
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "#555",
              fontFamily: "'Space Grotesk', sans-serif",
            }}>
              {card.label}
            </div>
            <div style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 26,
              fontWeight: 700,
              color: card.deathColor ?? "#FFF",
              lineHeight: 1.1,
            }}>
              {card.value}
            </div>
            {card.breakdownKey && selectedStat?.stat_breakdown?.[card.breakdownKey] != null && (() => {
              const pts = selectedStat.stat_breakdown![card.breakdownKey];
              return (
                <div style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: pts >= 0 ? "#4ade80" : "#f87171",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}>
                  {pts >= 0 ? `+${Math.round(pts)}` : Math.round(pts)} pts
                </div>
              );
            })()}
            {card.barPct != null && (
              <div style={{ height: 3, background: "#1E1E1E", borderRadius: 2, marginTop: 4 }}>
                <div style={{
                  height: "100%",
                  width: `${card.barPct}%`,
                  background: "#FCD400",
                  borderRadius: 2,
                }} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

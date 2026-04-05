"use client";

import React from "react";
import type { Split } from "@/lib/api";
import type { WeekStat } from "./types";
import { BarChart as RBarChart, Bar, Cell, XAxis, Tooltip, ResponsiveContainer } from "recharts";

type BarChartProps = {
  matchStats: WeekStat[];
  selectedWeek: number | null;
  selectedSplitId: string | null;
  splits: Split[];
  maxPts: number;
  historyDataStats: import("@/lib/api").PlayerMatchStat[];
  onSelectWeek: (week: number) => void;
  onSelectSplit: (splitId: string, newWeek: number) => void;
};

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: WeekStat }> }) {
  if (!active || !payload?.length) return null;
  const stat = payload[0].payload;
  return (
    <div style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 6, padding: "4px 8px", fontSize: 11, fontFamily: "'Space Grotesk', sans-serif" }}>
      <span style={{ color: "#FCD400", fontWeight: 700 }}>{Math.round(stat.fantasy_points)}</span>
    </div>
  );
}

export function BarChart({
  matchStats,
  selectedWeek,
  selectedSplitId,
  splits,
  historyDataStats,
  onSelectWeek,
  onSelectSplit,
}: BarChartProps) {
  return (
    <div style={{
      flex: 1.4,
      background: "#111111",
      borderRadius: 12,
      padding: 20,
      border: "1px solid #1E1E1E",
    }}>
      {/* Selector de splits — chips custom */}
      {splits.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20, overflowX: "auto", flexWrap: "nowrap", scrollbarWidth: "none", WebkitOverflowScrolling: "touch" } as React.CSSProperties}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/lec.webp"
            alt="LEC"
            style={{ width: 24, height: 24, borderRadius: 4, objectFit: "contain", flexShrink: 0 }}
          />
          {splits.map((split) => {
            const isActive = split.id === selectedSplitId;
            return (
              <button
                key={split.id}
                onClick={() => {
                  const newFiltered = historyDataStats.filter(s => s.competition_id === split.id);
                  const newWeek = newFiltered.length > 0
                    ? newFiltered.length
                    : historyDataStats.length > 0
                    ? historyDataStats.length
                    : 1;
                  onSelectSplit(split.id, newWeek);
                }}
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
                {split.name}
              </button>
            );
          })}
        </div>
      )}

      {matchStats.length > 0 ? (
        <>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif" }}>
              Puntos por semana
            </div>
            <div style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
              Últimas {matchStats.length} semanas
            </div>
          </div>

          <ResponsiveContainer width="100%" height={140}>
            <RBarChart
              data={matchStats}
              onClick={(data) => {
                if (!data?.activePayload?.[0]) return;
                onSelectWeek(data.activePayload[0].payload.week);
              }}
            >
              <XAxis
                dataKey="week"
                tickFormatter={(v) => `S${v}`}
                tick={{ fill: "#555", fontSize: 9, fontFamily: "'Barlow Condensed', sans-serif" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                wrapperStyle={{ outline: "none" }}
              />
              <Bar dataKey="fantasy_points" radius={[4, 4, 0, 0]}>
                {matchStats.map((stat) => (
                  <Cell
                    key={stat.week}
                    fill={selectedWeek === stat.week ? "#FCD400" : "#2A2A2A"}
                  />
                ))}
              </Bar>
            </RBarChart>
          </ResponsiveContainer>
        </>
      ) : (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 140 }}>
          <p style={{ color: "#333", fontSize: 13 }}>No hay partidas registradas para este split</p>
        </div>
      )}
    </div>
  );
}

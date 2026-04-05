"use client";

import type { PriceHistoryEntry } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

type Props = { entries: PriceHistoryEntry[] };

// Custom tooltip — must be a proper component (not inline arrow) for Recharts to render correctly
function PriceTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: PriceHistoryEntry }> }) {
  if (!active || !payload?.length) return null;
  const entry = payload[0].payload;
  const deltaColor = entry.delta_pct > 0 ? "#4ade80" : entry.delta_pct < 0 ? "#f87171" : "#888";
  return (
    <div style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 6, padding: "6px 10px", fontSize: 11, fontFamily: "'Space Grotesk', sans-serif" }}>
      <div style={{ color: "#555", marginBottom: 2 }}>{entry.date}</div>
      <div style={{ color: "#FCD400", fontWeight: 700 }}>{entry.price.toFixed(1)}M</div>
      {entry.delta_pct !== 0 && (
        <div style={{ color: deltaColor }}>{entry.delta_pct > 0 ? "+" : ""}{(entry.delta_pct * 100).toFixed(1)}%</div>
      )}
    </div>
  );
}

export function PriceHistoryChart({ entries }: Props) {
  if (entries.length === 0) return null;

  const prices = entries.map(e => e.price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const first = entries[0].price;
  const last = entries[entries.length - 1].price;
  const pct = first > 0 ? ((last - first) / first) * 100 : 0;
  const deltaColor = pct > 0 ? "#4ade80" : pct < 0 ? "#f87171" : "#888";

  return (
    <div style={{ background: "#111111", borderRadius: 12, padding: 20, border: "1px solid #1E1E1E" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif" }}>
            Historial de precio
          </div>
          <div style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
            Últimas {entries.length} actualizaciones
          </div>
        </div>
        {entries.length >= 2 && (
          <div style={{ fontSize: 12, color: deltaColor, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}>
            {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={entries} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis domain={[minP * 0.95, maxP * 1.05]} hide />
          <Tooltip content={<PriceTooltip />} cursor={{ stroke: "#2A2A2A" }} wrapperStyle={{ outline: "none" }} />
          <ReferenceLine y={first} stroke="#2A2A2A" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="price" stroke="#FCD400" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: "#FCD400", stroke: "#0A0A0A", strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

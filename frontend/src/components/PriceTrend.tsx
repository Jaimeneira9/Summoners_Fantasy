"use client";

// Props: changePct (number) — ej: 0.023 = +2.3%, -0.011 = -1.1%
// Si |changePct| < 0.001 → no renderiza nada
// Si > 0 → flecha ↑ + porcentaje en color #4ade80 (verde)
// Si < 0 → flecha ↓ + porcentaje en color #f87171 (rojo)
// Formato: "↑ 2.3%" o "↓ 1.1%"
// Estilo: texto pequeño (text-xs), inline, al lado del precio

export interface PriceTrendProps {
  changePct: number;
}

export function PriceTrend({ changePct }: PriceTrendProps) {
  if (Math.abs(changePct) < 0.001) return null;

  const isUp = changePct > 0;
  const color = isUp ? "#4ade80" : "#f87171";
  const arrow = isUp ? "↑" : "↓";
  const pct = (Math.abs(changePct) * 100).toFixed(1);

  return (
    <span
      className="text-xs font-semibold"
      style={{ color }}
    >
      {arrow} {pct}%
    </span>
  );
}

"use client";

import { useState } from "react";

export function UpgradeForm({
  currentClause,
  loading,
  error,
  onSubmit,
  onCancel,
}: {
  leagueId: string;
  rosterPlayerId: string;
  currentClause: number;
  loading: boolean;
  error: string | null;
  onSubmit: (amount: number) => Promise<void>;
  onCancel: () => void;
}) {
  const [amountStr, setAmountStr] = useState("1.0");
  const parsed = parseFloat(amountStr);
  const isValid = !isNaN(parsed) && parsed > 0;
  const newClause = isValid ? (currentClause + parsed * 0.5).toFixed(1) : null;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="number"
          step="0.5"
          min="0.5"
          value={amountStr}
          onChange={(e) => setAmountStr(e.target.value)}
          style={{
            flex: 1,
            background: "#1e2535",
            border: "1px solid rgba(252,212,0,0.2)",
            borderRadius: 8,
            color: "#F0E8D0",
            padding: "8px 12px",
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 14,
            outline: "none",
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = "#FCD400"; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(252,212,0,0.2)"; }}
        />
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#555" }}>M</span>
      </div>
      {newClause && (
        <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#8892aa" }}>
          Nueva cláusula: {newClause}M
        </p>
      )}
      {error && (
        <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#f87171" }}>{error}</p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={onCancel}
          style={{
            flex: 1,
            padding: "10px 20px",
            borderRadius: 8,
            border: "1px solid #2A2A2A",
            background: "transparent",
            color: "#888888",
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          Cancelar
        </button>
        <button
          disabled={loading || !isValid}
          onClick={() => isValid && onSubmit(parsed)}
          style={{
            flex: 2,
            padding: "10px 20px",
            borderRadius: 8,
            border: "none",
            background: "#FCD400",
            color: "#111111",
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 700,
            fontSize: 13,
            cursor: loading || !isValid ? "not-allowed" : "pointer",
            opacity: loading || !isValid ? 0.5 : 1,
          }}
        >
          {loading ? "…" : "Subir"}
        </button>
      </div>
    </>
  );
}

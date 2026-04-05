"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function SellPanel({
  leagueId,
  rosterPlayerId,
  forSale,
  onToggle,
}: {
  leagueId: string;
  rosterPlayerId: string;
  forSale: boolean;
  onToggle: (newValue: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cardStyle: React.CSSProperties = {
    background: "#111111",
    border: "1px solid #1E1E1E",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
  };

  const sectionLabelStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 12,
    color: "#888888",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: 6,
  };

  const descStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 13,
    color: "#555555",
    marginBottom: 14,
    lineHeight: 1.5,
  };

  const handleSell = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.roster.setSellIntent(leagueId, rosterPlayerId);
      onToggle(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al poner en venta");
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.roster.cancelSellIntent(leagueId, rosterPlayerId);
      onToggle(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cancelar la venta");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={cardStyle}>
      <p style={sectionLabelStyle}>Mercado</p>

      {forSale ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{
              background: "rgba(252,212,0,0.12)",
              border: "1px solid rgba(252,212,0,0.3)",
              color: "#FCD400",
              fontSize: 10,
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: 20,
              letterSpacing: "0.06em",
              textTransform: "uppercase" as const,
            }}>
              EN VENTA
            </span>
          </div>
          <p style={descStyle}>
            Recibirás ofertas de la liga y otros managers. Tú decides si aceptar.
          </p>
          <button
            onClick={handleCancel}
            disabled={loading}
            style={{
              background: "transparent",
              color: "#888888",
              border: "1px solid #2A2A2A",
              borderRadius: 8,
              padding: "10px 20px",
              fontSize: 13,
              fontFamily: "'Space Grotesk', sans-serif",
              cursor: loading ? "not-allowed" : "pointer",
              width: "100%",
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "…" : "Cancelar venta"}
          </button>
        </>
      ) : (
        <>
          <p style={descStyle}>
            Pon este jugador en venta para recibir ofertas de la liga y otros managers.
          </p>
          <button
            onClick={handleSell}
            disabled={loading}
            style={{
              background: "#FCD400",
              color: "#111111",
              fontWeight: 700,
              borderRadius: 8,
              padding: "10px 20px",
              fontSize: 13,
              fontFamily: "'Space Grotesk', sans-serif",
              border: "none",
              cursor: loading ? "not-allowed" : "pointer",
              width: "100%",
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "…" : "Poner en venta"}
          </button>
        </>
      )}

      {error && (
        <p style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 12,
          color: "#f87171",
          marginTop: 8,
        }}>
          {error}
        </p>
      )}
    </div>
  );
}

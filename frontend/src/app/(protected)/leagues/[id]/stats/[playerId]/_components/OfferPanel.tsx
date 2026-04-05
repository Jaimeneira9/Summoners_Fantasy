"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function OfferPanel({
  leagueId,
  rosterPlayerId,
}: {
  leagueId: string;
  rosterPlayerId: string;
}) {
  const [amount, setAmount] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const cardStyle: React.CSSProperties = {
    background: "#111111",
    border: "1px solid #1E1E1E",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
  };

  const handleSubmit = async () => {
    const parsed = parseFloat(amount);
    if (!parsed || parsed <= 0) return;
    setLoading(true);
    setError(null);
    try {
      await api.market.makeOffer(leagueId, rosterPlayerId, parsed);
      setSuccess(`Oferta enviada por ${parsed.toFixed(1)}M`);
      setAmount("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al enviar la oferta");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={cardStyle}>
      <p
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          marginBottom: 4,
        }}
      >
        Jugador en venta
      </p>
      <p
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 12,
          color: "#555",
          marginBottom: 14,
        }}
      >
        El propietario acepta ofertas manualmente
      </p>
      {success ? (
        <p
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 13,
            color: "#4CAF50",
            fontWeight: 600,
          }}
        >
          ✓ {success}
        </p>
      ) : (
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="number"
            min={1}
            step={0.5}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Tu oferta en M"
            style={{
              background: "#0A0A0A",
              border: "1px solid #2A2A2A",
              borderRadius: 8,
              padding: "8px 12px",
              color: "#F0E8D0",
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 13,
              outline: "none",
              width: 150,
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={loading || !amount || parseFloat(amount) <= 0}
            style={{
              background: "#FCD400",
              color: "#111111",
              border: "none",
              borderRadius: 8,
              padding: "10px 20px",
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 13,
              fontWeight: 700,
              cursor: loading || !amount || parseFloat(amount) <= 0 ? "not-allowed" : "pointer",
              opacity: loading || !amount || parseFloat(amount) <= 0 ? 0.5 : 1,
            }}
          >
            {loading ? "…" : "Hacer oferta"}
          </button>
        </div>
      )}
      {error && (
        <p
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 12,
            color: "#EF5350",
            marginTop: 8,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

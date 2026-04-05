"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type ClauseInfo } from "@/lib/api";
import { UpgradeForm } from "./UpgradeForm";

function daysRemaining(expiresAt: string): number {
  const diff = new Date(expiresAt).getTime() - Date.now();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

export function ClausePanel({
  info,
  leagueId,
  player,
  onActivated,
}: {
  info: ClauseInfo;
  leagueId: string;
  player: { name: string; role: string; team: string; image_url: string | null };
  onActivated: () => void;
}) {
  const router = useRouter();
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const cardStyle: React.CSSProperties = {
    background: "#111111",
    border: "1px solid #1E1E1E",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
    display: "flex",
    alignItems: "center",
    gap: 16,
    flexWrap: "wrap" as const,
  };

  const labelStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 13,
    fontWeight: 600,
    color: "#fff",
  };

  const mutedStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 13,
    color: "#444",
  };

  // Owned by me + protection active (clause_active = false = window still open): show upgrade UI
  // clause_active = false → expires > now → protection period not yet over
  if (info.owned_by_me && info.clause_amount !== null && info.clause_expires_at !== null && !info.clause_active) {
    const days = daysRemaining(info.clause_expires_at);
    return (
      <div style={{ ...cardStyle, border: "1px solid #3A2E00" }}>
        {/* Badge */}
        <div style={{
          background: "#3A2E00",
          color: "#FCD400",
          fontSize: 10,
          fontWeight: 700,
          padding: "3px 8px",
          borderRadius: 6,
          letterSpacing: "0.06em",
          textTransform: "uppercase" as const,
          flexShrink: 0,
        }}>
          Cláusula activa
        </div>

        {/* Amount + days */}
        <div style={{ flex: 1, display: "flex", gap: 16, flexWrap: "wrap" as const }}>
          <div>
            <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 2 }}>Importe</div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: "#FCD400" }}>
              {info.clause_amount.toFixed(1)}M
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 2 }}>Vence en</div>
            <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color: days <= 3 ? "#EF5350" : "#fff" }}>
              {days}d
            </div>
          </div>
        </div>

        {/* Upgrade button — danger style (irreversible, costs money) */}
        <button
          onClick={() => { setError(null); setSuccess(null); setUpgradeOpen(true); }}
          style={{
            background: "transparent",
            color: "#FCD400",
            border: "1px solid rgba(252,212,0,0.3)",
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 700,
            fontSize: 13,
            padding: "10px 20px",
            borderRadius: 8,
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          Subir cláusula
        </button>

        {success && (
          <div style={{ width: "100%", fontSize: 12, color: "#4CAF50", fontFamily: "'Space Grotesk', sans-serif" }}>
            {success}
          </div>
        )}

        {/* Upgrade popup */}
        {upgradeOpen && info.roster_player_id && (
          <div
            className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.7)" }}
            onClick={(e) => { if (e.target === e.currentTarget) setUpgradeOpen(false); }}
          >
            <div style={{
              background: "#161b27",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 16,
              padding: "24px",
              width: "100%",
              maxWidth: 360,
              display: "flex",
              flexDirection: "column" as const,
              gap: 16,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 700, color: "#F0E8D0" }}>
                  Subir cláusula — {player.name}
                </p>
                <button onClick={() => setUpgradeOpen(false)} style={{ color: "#555", fontSize: 18, background: "none", border: "none", cursor: "pointer" }}>✕</button>
              </div>
              <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#8892aa" }}>
                Cláusula actual: {info.clause_amount.toFixed(1)}M. El monto que pagues se suma en un 50% a la cláusula.
              </p>
              <UpgradeForm
                leagueId={leagueId}
                rosterPlayerId={info.roster_player_id}
                currentClause={info.clause_amount}
                loading={loading}
                error={error}
                onSubmit={async (amount) => {
                  setLoading(true);
                  setError(null);
                  try {
                    await api.clause.upgrade(leagueId, info.roster_player_id!, amount);
                    setSuccess(`Cláusula subida a ${(info.clause_amount! + amount * 0.5).toFixed(1)}M`);
                    setUpgradeOpen(false);
                    onActivated();
                  } catch (e: unknown) {
                    setError(e instanceof Error ? e.message : "Error al subir la cláusula");
                  } finally {
                    setLoading(false);
                  }
                }}
                onCancel={() => setUpgradeOpen(false)}
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  // Owned by someone else + protection expired (clause_active = true = can activate): show activate button
  // clause_active = true → expires <= now → protection period is over, rival can trigger clause
  if (info.is_owned && !info.owned_by_me && info.clause_active && info.clause_amount !== null) {
    return (
      <div style={{ ...cardStyle, border: "1px solid #2A1A00", background: "#130F00" }}>
        <div style={{ flex: 1, display: "flex", gap: 16, flexWrap: "wrap" as const, alignItems: "center" }}>
          <span style={labelStyle}>Cláusula:</span>
          <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 18, fontWeight: 700, color: "#FCD400" }}>
            {info.clause_amount.toFixed(1)}M
          </span>
        </div>

        <button
          onClick={() => { setError(null); setConfirmOpen(true); }}
          style={{
            background: "#FCD400",
            color: "#111111",
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 700,
            fontSize: 13,
            padding: "10px 20px",
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          Activar cláusula
        </button>

        {error && (
          <div style={{ width: "100%", fontSize: 12, color: "#f87171", fontFamily: "'Space Grotesk', sans-serif" }}>
            {error}
          </div>
        )}

        {/* Confirm dialog */}
        {confirmOpen && info.roster_player_id && (
          <div
            className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.7)" }}
            onClick={(e) => { if (e.target === e.currentTarget) setConfirmOpen(false); }}
          >
            <div style={{
              background: "#161b27",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 16,
              padding: "24px",
              width: "100%",
              maxWidth: 360,
              display: "flex",
              flexDirection: "column" as const,
              gap: 16,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, fontWeight: 700, color: "#F0E8D0" }}>
                  Activar cláusula — {player.name}
                </p>
                <button onClick={() => setConfirmOpen(false)} style={{ color: "#555", fontSize: 18, background: "none", border: "none", cursor: "pointer" }}>✕</button>
              </div>
              <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 13, color: "#8892aa" }}>
                Pagarás {info.clause_amount.toFixed(1)}M para fichar a {player.name}. Esta acción no se puede deshacer.
              </p>
              {error && (
                <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#f87171" }}>{error}</p>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => setConfirmOpen(false)}
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
                  disabled={loading}
                  onClick={async () => {
                    setLoading(true);
                    setError(null);
                    try {
                      await api.clause.activate(leagueId, info.roster_player_id!);
                      setConfirmOpen(false);
                      router.push(`/leagues/${leagueId}/lineup`);
                    } catch (e: unknown) {
                      setError(e instanceof Error ? e.message : "Error al activar la cláusula");
                    } finally {
                      setLoading(false);
                    }
                  }}
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
                    cursor: loading ? "not-allowed" : "pointer",
                    opacity: loading ? 0.6 : 1,
                  }}
                >
                  {loading ? "…" : "Confirmar"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Owned by someone else + protection still active (clause_active = false): rival can't activate yet
  if (info.is_owned && !info.owned_by_me && !info.clause_active && info.clause_amount !== null && info.clause_expires_at !== null) {
    const days = daysRemaining(info.clause_expires_at);
    return (
      <div style={{ ...cardStyle, border: "1px solid #1A2A1A", background: "#0D130D" }}>
        <div style={{ flex: 1, display: "flex", gap: 16, flexWrap: "wrap" as const, alignItems: "center" }}>
          <span style={{ ...labelStyle, color: "#4CAF50" }}>Período de protección</span>
          <span style={mutedStyle}>|</span>
          <span style={{ ...mutedStyle, color: "#888" }}>
            {days} días restantes
          </span>
          <span style={mutedStyle}>|</span>
          <span style={{ ...mutedStyle }}>
            Cláusula: <span style={{ color: "#FCD400" }}>{info.clause_amount.toFixed(1)}M</span>
          </span>
        </div>
      </div>
    );
  }

  // Owned but no clause (clause_amount is null)
  if (info.is_owned) {
    return (
      <div style={cardStyle}>
        <span style={mutedStyle}>Sin cláusula activa</span>
      </div>
    );
  }

  // Not owned — free agent, no clause panel needed
  return null;
}

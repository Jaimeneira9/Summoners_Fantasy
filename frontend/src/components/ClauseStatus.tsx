"use client";

import { useState } from "react";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ClauseStatusProps {
  clauseAmount: number | null;
  clauseExpiresAt: string | null;
  isOwnPlayer: boolean;
  leagueId: string;
  rosterPlayerId: string;
  onSuccess?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getDaysRemaining(expiresAt: string): number {
  return Math.ceil(
    (new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24),
  );
}

// ---------------------------------------------------------------------------
// ClauseStatus
// ---------------------------------------------------------------------------

export function ClauseStatus({
  clauseAmount,
  clauseExpiresAt,
  isOwnPlayer,
  leagueId,
  rosterPlayerId,
  onSuccess,
}: ClauseStatusProps) {
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [upgradeAmount, setUpgradeAmount] = useState<string>("");

  const days = clauseExpiresAt ? getDaysRemaining(clauseExpiresAt) : 0;
  const isActive = days > 0 && clauseAmount != null;

  // ── Own player ──────────────────────────────────────────────────────────

  if (isOwnPlayer) {
    const handleUpgrade = async () => {
      const parsed = parseFloat(upgradeAmount);
      if (isNaN(parsed) || parsed <= 0) {
        setError("Ingresá un monto válido");
        return;
      }
      setError(null);
      setLoading(true);
      try {
        await api.clause.upgrade(leagueId, rosterPlayerId, parsed);
        setShowUpgrade(false);
        setUpgradeAmount("");
        onSuccess?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al subir cláusula");
      } finally {
        setLoading(false);
      }
    };

    const parsed = parseFloat(upgradeAmount);
    const upgradePreview = !isNaN(parsed) && parsed > 0
      ? parsed * 0.5
      : null;

    return (
      <div className="flex flex-col gap-2">
        {/* Status row */}
        <div className="flex items-center gap-2">
          {isActive ? (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
              style={{
                background: "rgba(56,189,248,0.08)",
                border: "1px solid rgba(56,189,248,0.2)",
              }}
            >
              <span className="text-sky-400 text-xs">🔒</span>
              <span className="text-sky-400 text-xs font-semibold">
                Protegido · {days} {days === 1 ? "día" : "días"}
              </span>
            </div>
          ) : (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
              style={{
                background: "rgba(234,179,8,0.08)",
                border: "1px solid rgba(234,179,8,0.2)",
              }}
            >
              <span className="text-yellow-400 text-xs">⚠️</span>
              <span className="text-yellow-400 text-xs font-semibold">Sin protección</span>
            </div>
          )}

          <button
            onClick={() => setShowUpgrade((v) => !v)}
            className="text-xs font-semibold px-2.5 py-1 rounded-lg transition-all hover:brightness-110 active:scale-95"
            style={{
              background: "rgba(252,212,0,0.1)",
              border: "1px solid rgba(252,212,0,0.25)",
              color: "#fcd400",
            }}
          >
            {showUpgrade ? "Cancelar" : isActive ? "Subir cláusula" : "Asignar cláusula"}
          </button>
        </div>

        {/* Inline upgrade / assign form */}
        {showUpgrade && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                step="0.5"
                placeholder="Monto (M)"
                value={upgradeAmount}
                onChange={(e) => setUpgradeAmount(e.target.value)}
                className="flex-1 text-xs px-2.5 py-1.5 rounded-lg outline-none transition-colors"
                style={{
                  background: "#1e2535",
                  border: "1px solid rgba(252,212,0,0.2)",
                  color: "#f0f4ff",
                }}
              />
              <button
                onClick={handleUpgrade}
                disabled={loading}
                className="text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:brightness-110 active:scale-95 disabled:opacity-50"
                style={{
                  background: "linear-gradient(135deg, #fcd400, #fcb900)",
                  color: "#000",
                }}
              >
                {loading ? "..." : "Confirmar"}
              </button>
            </div>
            {upgradePreview !== null && (
              <p className="text-xs" style={{ color: "#8892aa" }}>
                {isActive
                  ? `Pagarás ${parsed.toFixed(1)}M → cláusula sube ${upgradePreview.toFixed(1)}M`
                  : `Pagarás ${parsed.toFixed(1)}M → cláusula de ${upgradePreview.toFixed(1)}M`}
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="text-red-400 text-xs">{error}</p>
        )}
      </div>
    );
  }

  // ── Rival player ─────────────────────────────────────────────────────────

  // No clause — don't render anything (ficha por sistema normal)
  if (!isActive || clauseAmount == null) return null;

  const handleActivate = async () => {
    setError(null);
    setLoading(true);
    try {
      await api.clause.activate(leagueId, rosterPlayerId);
      onSuccess?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al activar cláusula");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-semibold"
          style={{ color: "#8892aa" }}
        >
          Cláusula: {clauseAmount.toFixed(1)}M
        </span>

        <button
          onClick={handleActivate}
          disabled={loading}
          className="text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:brightness-110 active:scale-95 disabled:opacity-50"
          style={{
            background: "linear-gradient(135deg, #fcd400, #fcb900)",
            color: "#000",
          }}
        >
          {loading ? "..." : "Activar cláusula"}
        </button>
      </div>

      {error && (
        <p className="text-red-400 text-xs">{error}</p>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type PlayerMatchStat, type PlayerSplitHistory, type Split, type UpcomingMatch, type ClauseInfo, type GameDetailStat } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PLAYER_PHOTO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PlayerHistoryResponse = {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    image_url: string | null;
    current_price: number;
  };
  stats: PlayerMatchStat[];
  total_points: number;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPlayerPhotoUrl(name: string): string {
  return `${PLAYER_PHOTO_BASE}${name.toLowerCase().replace(/ /g, "-")}.webp`;
}

function calcKDA(kills: number, deaths: number, assists: number): string {
  if (deaths === 0) return "PERFECT";
  return ((kills + assists) / deaths).toFixed(2);
}

function barWidth(value: number, max: number): number {
  return Math.min(Math.max((value / max) * 100, 0), 100);
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0A" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px 96px" }}>
        <div style={{ height: 14, width: 120, borderRadius: 6, background: "#1A1A1A", marginBottom: 24 }} />
        <div style={{ height: 140, borderRadius: 12, background: "#111", marginBottom: 12 }} />
        <div style={{ height: 40, borderRadius: 8, background: "#111", marginBottom: 12 }} />
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} style={{ flex: 1, height: 90, borderRadius: 10, background: "#111" }} />
          ))}
        </div>
        <div style={{ display: "flex", gap: 20 }}>
          <div style={{ flex: 1.4, height: 260, borderRadius: 12, background: "#111" }} />
          <div style={{ flex: 1, height: 260, borderRadius: 12, background: "#111" }} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// UpcomingSchedule widget
// ---------------------------------------------------------------------------

function UpcomingSchedule({
  matches,
  loading,
  role,
  leagueId,
}: {
  matches: UpcomingMatch[] | null;
  loading: boolean;
  role: string;
  leagueId: string;
}) {
  if (role === "coach") return null;

  const cardStyle = {
    background: "#111111",
    border: "1px solid #1E1E1E",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
  };

  if (loading) {
    return (
      <div style={cardStyle}>
        <p style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          marginBottom: 12,
        }}>
          Próximas partidas
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              className="animate-pulse"
              style={{ height: 40, borderRadius: 8, background: "#1A1A1A" }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (matches !== null && matches.length === 0) {
    return (
      <div style={cardStyle}>
        <p style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          marginBottom: 8,
        }}>
          Próximas partidas
        </p>
        <p style={{ fontSize: 13, color: "#555" }}>Sin partidas programadas</p>
      </div>
    );
  }

  if (!matches) return null;

  return (
    <div style={cardStyle}>
      <p style={{
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 13,
        fontWeight: 600,
        color: "#fff",
        marginBottom: 12,
      }}>
        Próximas partidas
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {matches.slice(0, 3).map((match, i) => {
          const dateObj = new Date(match.date);
          const formatted = dateObj.toLocaleDateString("es-ES", {
            weekday: "short",
            day: "numeric",
            month: "short",
          });
          const opponentSlug = match.opponent.toLowerCase().replace(/ /g, "-");
          const inner = (
            <>
              {/* Team logo */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${opponentSlug}.webp`}
                alt={match.opponent}
                style={{ width: 22, height: 22, objectFit: "contain", flexShrink: 0 }}
                onError={(e) => { e.currentTarget.style.display = "none"; }}
              />
              {/* Opponent name */}
              <span style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#F5F5F5",
                flex: 1,
              }}>
                {match.opponent}
              </span>
              {/* Home/away badge */}
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                color: match.home_or_away === "home" ? "#4CAF50" : "#888",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                flexShrink: 0,
              }}>
                {match.home_or_away === "home" ? "LOCAL" : "VISITANTE"}
              </span>
              {/* Date */}
              <span style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: 12,
                color: "#555",
                flexShrink: 0,
                minWidth: 72,
                textAlign: "right",
                textTransform: "capitalize",
              }}>
                {formatted}
              </span>
            </>
          );
          const sharedStyle: React.CSSProperties = {
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 10px",
            borderRadius: 8,
            background: "#0F0F0F",
            border: "1px solid #1A1A1A",
            textDecoration: "none",
          };
          return match.series_id ? (
            <Link
              key={i}
              href={`/leagues/${leagueId}/h2h/${match.series_id}`}
              style={{ ...sharedStyle, cursor: "pointer" }}
            >
              {inner}
            </Link>
          ) : (
            <div key={i} style={sharedStyle}>
              {inner}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SellPanel
// ---------------------------------------------------------------------------

function SellPanel({
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

// ---------------------------------------------------------------------------
// ClausePanel
// ---------------------------------------------------------------------------

function daysRemaining(expiresAt: string): number {
  const diff = new Date(expiresAt).getTime() - Date.now();
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

function ClausePanel({
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

  // Owned by me + clause active: show upgrade UI
  if (info.owned_by_me && info.clause_active && info.clause_amount !== null && info.clause_expires_at !== null) {
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

  // Owned by someone else + clause active: show activate button
  if (info.is_owned && !info.owned_by_me && info.clause_active && info.clause_amount !== null && info.clause_expires_at !== null) {
    const days = daysRemaining(info.clause_expires_at);
    return (
      <div style={{ ...cardStyle, border: "1px solid #2A1A00", background: "#130F00" }}>
        <div style={{ flex: 1, display: "flex", gap: 16, flexWrap: "wrap" as const, alignItems: "center" }}>
          <span style={labelStyle}>Cláusula:</span>
          <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 18, fontWeight: 700, color: "#FCD400" }}>
            {info.clause_amount.toFixed(1)}M
          </span>
          <span style={mutedStyle}>|</span>
          <span style={{ ...mutedStyle, color: days <= 3 ? "#EF5350" : "#888" }}>
            {days} días restantes
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

  // Owned but clause not active
  if (info.is_owned && !info.clause_active) {
    return (
      <div style={cardStyle}>
        <span style={mutedStyle}>Sin cláusula activa</span>
      </div>
    );
  }

  // Not owned — free agent, no clause panel needed
  return null;
}

// ---------------------------------------------------------------------------
// UpgradeForm (inline sub-component used by ClausePanel)
// ---------------------------------------------------------------------------

function UpgradeForm({
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

// ---------------------------------------------------------------------------
// OfferPanel
// ---------------------------------------------------------------------------

function OfferPanel({
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PlayerStatsPage() {
  const { id: leagueId, playerId } = useParams<{ id: string; playerId: string }>();
  const searchParams = useSearchParams();
  const fromScout = searchParams.get("from") === "scout";

  const chartRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<PlayerHistoryResponse | null>(null);
  const [, setSplitHistory] = useState<PlayerSplitHistory[]>([]);
  const [splits, setSplits] = useState<Split[]>([]);
  const [selectedSplitId, setSelectedSplitId] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<UpcomingMatch[] | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [clauseInfo, setClauseInfo] = useState<ClauseInfo | null>(null);
  const [forSale, setForSale] = useState<boolean>(false);
  const [expandedSeriesId, setExpandedSeriesId] = useState<string | null>(null);
  const [gamesCache, setGamesCache] = useState<Map<string, GameDetailStat[]>>(new Map());
  const [gamesLoading, setGamesLoading] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.scoring.playerHistory(playerId),
      api.splits.playerHistory(playerId),
      api.splits.list(),
    ])
      .then(([history, splitHistory, splitList]) => {
        if (cancelled) return;
        const h = history as PlayerHistoryResponse;
        setHistoryData(h);
        setSplitHistory(splitHistory as PlayerSplitHistory[]);
        const availableSplits = splitList as Split[];
        setSplits(availableSplits);

        // Por defecto mostrar el split activo
        const activeSplit = availableSplits.find(s => s.is_active) ?? null;
        const defaultSplitId = activeSplit?.id ?? null;
        setSelectedSplitId(defaultSplitId);

        // Default to last week del split activo (o de todas las series si no hay split activo)
        const defaultStats = defaultSplitId
          ? h.stats.filter(s => s.competition_id === defaultSplitId)
          : h.stats;
        if (defaultStats.length > 0) {
          setSelectedWeek(defaultStats.length);
        } else if (h.stats.length > 0) {
          setSelectedWeek(h.stats.length);
        }
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [playerId]);

  // Independent schedule fetch — does not block hero render
  useEffect(() => {
    setScheduleLoading(true);
    api.players.schedule(playerId)
      .then((data) => setSchedule(data.upcoming))
      .catch(() => setSchedule([]))
      .finally(() => setScheduleLoading(false));
  }, [playerId]);

  // Independent clause fetch — silent failure if endpoint not yet available
  useEffect(() => {
    if (!leagueId) return;
    api.clause.info(leagueId, playerId).then((info) => {
      setClauseInfo(info);
      setForSale(info.for_sale ?? false);
    }).catch(() => {});
  }, [leagueId, playerId]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const player = historyData?.player ?? null;
  // matchStats filtrados por split seleccionado, con 1-based week index
  const matchStats = (historyData?.stats ?? [])
    .filter(s => !selectedSplitId || s.competition_id === selectedSplitId)
    .sort((a, b) => new Date(a.matches?.scheduled_at ?? 0).getTime() - new Date(b.matches?.scheduled_at ?? 0).getTime())
    .map((s, i) => ({ ...s, week: i + 1 }));
  const totalPoints = matchStats.reduce((sum, s) => sum + (s.fantasy_points ?? 0), 0);

  const lastMatchPts = matchStats.length > 0 ? matchStats[matchStats.length - 1].fantasy_points : 0;

  const roleHex = player ? getRoleColor(player.role) : getRoleColor("coach");
  const roleColor = player ? (ROLE_COLORS[player.role] ?? ROLE_COLORS.coach) : ROLE_COLORS.coach;
  const photoUrl = player ? (player.image_url ?? getPlayerPhotoUrl(player.name)) : "";

  // Selected stat for zona 3
  const selectedStat = matchStats.find((s) => s.week === selectedWeek) ?? null;

  // Computed per-game stats for zona 3
  const statCards = selectedStat
    ? [
        {
          label: "KDA",
          value: calcKDA(selectedStat.kills, selectedStat.deaths, selectedStat.assists),
          barPct: selectedStat.deaths === 0 ? null : (() => {
            const kda = (selectedStat.kills + selectedStat.assists) / selectedStat.deaths;
            return kda >= 5 ? 80 : barWidth(kda, 10);
          })(),
          deathColor: selectedStat.deaths === 0 ? "#FCD400" : undefined,
        },
        {
          label: "Kills",
          value: String(selectedStat.kills),
          barPct: barWidth(selectedStat.kills, 10),
          breakdownKey: "kills",
        },
        {
          label: "Deaths",
          value: String(selectedStat.deaths),
          barPct: Math.max(0, 100 - (selectedStat.deaths / 10) * 100),
          deathColor: selectedStat.deaths <= 2 ? "#4CAF50" : selectedStat.deaths >= 5 ? "#EF5350" : "#FFF",
          breakdownKey: "deaths",
        },
        {
          label: "Assists",
          value: String(selectedStat.assists),
          barPct: barWidth(selectedStat.assists, 15),
          breakdownKey: "assists",
        },
        {
          label: "CS/min",
          value: selectedStat.cs_per_min != null ? selectedStat.cs_per_min.toFixed(1) : "—",
          barPct: selectedStat.cs_per_min != null ? barWidth(selectedStat.cs_per_min, 10) : null,
          breakdownKey: "cs_per_min",
        },
        {
          label: "Daño/min",
          value: selectedStat.dpm != null ? String(Math.round(selectedStat.dpm)) : "—",
          barPct: selectedStat.dpm != null ? barWidth(selectedStat.dpm, 1200) : null,
          breakdownKey: "dpm",
        },
        {
          label: "XP @15",
          value: selectedStat.xp_diff_at_15 != null
            ? (selectedStat.xp_diff_at_15 >= 0 ? `+${Math.round(selectedStat.xp_diff_at_15)}` : String(Math.round(selectedStat.xp_diff_at_15)))
            : "—",
          barPct: selectedStat.xp_diff_at_15 != null
            ? Math.min(Math.max(50 + (selectedStat.xp_diff_at_15 / 2000) * 50, 0), 100)
            : null,
          deathColor: selectedStat.xp_diff_at_15 != null
            ? (selectedStat.xp_diff_at_15 > 0 ? "#4ade80" : selectedStat.xp_diff_at_15 < 0 ? "#f87171" : "#888888")
            : undefined,
          breakdownKey: "xp_diff_15",
        },
        {
          label: "Gold @15",
          value: selectedStat.gold_diff_at_15 != null
            ? (selectedStat.gold_diff_at_15 >= 0 ? `+${Math.round(selectedStat.gold_diff_at_15)}` : String(Math.round(selectedStat.gold_diff_at_15)))
            : "—",
          barPct: selectedStat.gold_diff_at_15 != null
            ? Math.min(Math.max(50 + (selectedStat.gold_diff_at_15 / 2000) * 50, 0), 100)
            : null,
          deathColor: selectedStat.gold_diff_at_15 != null
            ? (selectedStat.gold_diff_at_15 > 0 ? "#4ade80" : selectedStat.gold_diff_at_15 < 0 ? "#f87171" : "#888888")
            : undefined,
          breakdownKey: "gold_diff_15",
        },
      ]
    : null;

  // Active week badge info
  const activeStat = matchStats.find((s) => s.week === selectedWeek);
  const activeIsWin = activeStat ? activeStat.result === 1 : false;
  const activeRival = activeStat?.matches
    ? (activeStat.matches.team_1 === player?.team
        ? activeStat.matches.team_2
        : activeStat.matches.team_1)
    : null;

  // Bar chart max
  const maxPts = Math.max(...matchStats.map((s) => s.fantasy_points), 1);

  // ---------------------------------------------------------------------------
  // GSAP: animación del gráfico de barras
  // ---------------------------------------------------------------------------

  useGSAP(() => {
    if (matchStats.length === 0) return;
    gsap.from(".bar-item", {
      scaleY: 0,
      transformOrigin: "bottom center",
      duration: 0.6,
      ease: "power3.out",
      stagger: 0.04,
    });
    gsap.from(".bar-label", {
      autoAlpha: 0,
      y: 8,
      duration: 0.4,
      delay: 0.3,
      stagger: 0.04,
    });
  }, { scope: chartRef, dependencies: [selectedSplitId, matchStats.length] });

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (loading) return <LoadingSkeleton />;

  if (error || !player) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0A0A0A" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "rgba(255,255,255,0.3)", fontSize: 14, marginBottom: 12 }}>
            {error ?? "Jugador no encontrado"}
          </p>
          <Link
            href={`/leagues/${leagueId}/lineup`}
            style={{ color: "#FCD400", fontSize: 12, textDecoration: "underline" }}
          >
            Volver al lineup
          </Link>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div style={{ minHeight: "100dvh", background: "#0A0A0A", color: "#fff", overflowX: "hidden" }}>
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "16px 16px 96px" }}>

        {/* Breadcrumb */}
        <nav style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#444", marginBottom: 20 }}>
          <Link
            href={fromScout ? `/leagues/${leagueId}/market?tab=scout` : `/leagues/${leagueId}/lineup`}
            style={{ color: "#555", textDecoration: "none" }}
          >
            {fromScout ? "Explorar" : "Mi Equipo"}
          </Link>
          <span>›</span>
          <span style={{ color: "#888" }}>Stats de Jugador</span>
        </nav>

        {/* ================================================================ */}
        {/* ZONA 1: Player Hero                                              */}
        {/* ================================================================ */}
        <div className="player-hero" style={{
          background: "#111111",
          borderRadius: 12,
          padding: "16px",
          border: "1px solid #222",
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 12,
        }}>
          {/* Photo + role badge */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div style={{
              width: 80,
              height: 80,
              borderRadius: 10,
              border: `2px solid ${roleHex}`,
              overflow: "hidden",
              background: `${roleHex}22`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              {!imgError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={photoUrl}
                  alt={player.name}
                  style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
                  onError={() => setImgError(true)}
                />
              ) : (
                <RoleIcon role={player.role} className={`w-10 h-10 ${roleColor.text} opacity-60`} />
              )}
            </div>
            {/* Role badge */}
            <div style={{
              background: roleHex,
              color: "#000",
              fontSize: 9,
              fontWeight: 900,
              padding: "2px 8px",
              borderRadius: 4,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}>
              {ROLE_LABEL[player.role] ?? player.role.toUpperCase()}
            </div>
          </div>

          {/* Player info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 28,
              fontWeight: 700,
              color: "#fff",
              lineHeight: 1.1,
              margin: 0,
              textTransform: "uppercase",
            }}>
              {player.name}
            </h1>
            <p style={{ fontSize: 13, color: "#555", margin: "2px 0 0", fontFamily: "'Space Grotesk', sans-serif" }}>
              {player.team}
            </p>
            <p style={{ fontSize: 12, color: "#444", margin: "2px 0 0" }}>
              LEC · {player.current_price.toFixed(1)}M
            </p>
          </div>

          {/* Total points */}
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 40,
              fontWeight: 700,
              color: "#FCD400",
              lineHeight: 1,
            }}>
              {Math.round(totalPoints)}
            </div>
            <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
              pts total
            </div>
            {lastMatchPts > 0 && (
              <div style={{ fontSize: 12, color: "#4CAF50", marginTop: 4, fontWeight: 600 }}>
                +{Math.round(lastMatchPts)} esta semana
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* UPCOMING SCHEDULE: between hero and week selector               */}
        {/* ================================================================ */}
        <UpcomingSchedule
          matches={schedule}
          loading={scheduleLoading}
          role={player.role}
          leagueId={leagueId}
        />

        {/* ================================================================ */}
        {/* SELL PANEL: shown only when owned_by_me                         */}
        {/* ================================================================ */}
        {clauseInfo?.owned_by_me === true && clauseInfo.roster_player_id && (
          <SellPanel
            leagueId={leagueId}
            rosterPlayerId={clauseInfo.roster_player_id}
            forSale={forSale}
            onToggle={setForSale}
          />
        )}

        {/* ================================================================ */}
        {/* CLAUSE PANEL: below hero zone                                    */}
        {/* ================================================================ */}
        {clauseInfo && (
          <ClausePanel
            info={clauseInfo}
            leagueId={leagueId}
            player={player}
            onActivated={() => {
              // Refetch clause info after upgrade
              api.clause.info(leagueId, playerId).then((info) => {
                setClauseInfo(info);
                setForSale(info.for_sale ?? false);
              }).catch(() => {});
            }}
          />
        )}

        {/* ================================================================ */}
        {/* OFFER PANEL: shown when player is owned by someone else + for_sale */}
        {/* ================================================================ */}
        {clauseInfo &&
          clauseInfo.is_owned &&
          !clauseInfo.owned_by_me &&
          forSale === true &&
          clauseInfo.roster_player_id && (
            <OfferPanel
              leagueId={leagueId}
              rosterPlayerId={clauseInfo.roster_player_id}
            />
          )}

        {/* ================================================================ */}
        {/* ZONA 2: Selector de jornada                                      */}
        {/* ================================================================ */}
        {matchStats.length > 0 && (
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
                    onClick={() => setSelectedWeek(stat.week)}
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
        )}

        {/* ================================================================ */}
        {/* ZONA 3: Stat cards de la jornada seleccionada                    */}
        {/* ================================================================ */}
        {statCards && (
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
        )}

        {/* ================================================================ */}
        {/* ZONA 4: Dos columnas                                             */}
        {/* ================================================================ */}
        <div className="flex flex-col sm:flex-row gap-5">

          {/* Col izquierda: Selector de splits + Bar chart */}
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
                {/* Chip "Todos" — sin filtro de split */}
                <button
                  onClick={() => {
                    setSelectedSplitId(null);
                    const allStats = historyData?.stats ?? [];
                    setSelectedWeek(allStats.length > 0 ? allStats.length : null);
                  }}
                  style={{
                    background: selectedSplitId === null ? "#FCD400" : "#1A1A1A",
                    border: `1px solid ${selectedSplitId === null ? "#FCD400" : "#2A2A2A"}`,
                    borderRadius: 8,
                    padding: "6px 14px",
                    color: selectedSplitId === null ? "#000" : "#777",
                    fontSize: 12,
                    fontWeight: selectedSplitId === null ? 700 : 500,
                    cursor: "pointer",
                    fontFamily: "'Barlow Condensed', sans-serif",
                    letterSpacing: "0.04em",
                    flexShrink: 0,
                  }}
                >
                  Todos
                </button>
                {splits.map((split) => {
                  const isActive = split.id === selectedSplitId;
                  return (
                    <button
                      key={split.id}
                      onClick={() => {
                        setSelectedSplitId(split.id);
                        const newFiltered = (historyData?.stats ?? [])
                          .filter(s => s.competition_id === split.id);
                        setSelectedWeek(newFiltered.length > 0 ? newFiltered.length : null);
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

                <div ref={chartRef} style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 140 }}>
                  {matchStats.map((stat) => {
                    const isActive = stat.week === selectedWeek;
                    const heightPx = Math.max((stat.fantasy_points / maxPts) * 110, 2);
                    return (
                      <div
                        key={stat.week}
                        onClick={() => setSelectedWeek(stat.week)}
                        style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}
                      >
                        <span className="bar-label" style={{
                          fontSize: 10,
                          color: isActive ? "#FCD400" : "#555",
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontWeight: 700,
                        }}>
                          {Math.round(stat.fantasy_points)}
                        </span>
                        <div className="bar-item" style={{
                          width: "100%",
                          height: `${heightPx}px`,
                          background: isActive ? "#FCD400" : "#2A2A2A",
                          borderRadius: "4px 4px 0 0",
                        }} />
                        <span style={{
                          fontSize: 9,
                          color: isActive ? "#FCD400" : "#333",
                          fontFamily: "'Barlow Condensed', sans-serif",
                        }}>
                          S{stat.week}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 140 }}>
                <p style={{ color: "#333", fontSize: 13 }}>No hay partidas registradas para este split</p>
              </div>
            )}
          </div>

          {/* Col derecha: Historial de jornadas */}
          <div style={{
            flex: 1,
            background: "#111111",
            borderRadius: 12,
            padding: 20,
            border: "1px solid #1E1E1E",
            overflowY: "auto",
            maxHeight: 300,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", marginBottom: 14 }}>
              Jornadas
            </div>

            {matchStats.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {[...matchStats].reverse().map((stat) => {
                  const isActive = stat.week === selectedWeek;
                  const isWin = stat.result === 1;
                  const kda = `${typeof stat.kills === 'number' ? stat.kills.toFixed(1) : stat.kills}/${typeof stat.deaths === 'number' ? stat.deaths.toFixed(1) : stat.deaths}/${typeof stat.assists === 'number' ? stat.assists.toFixed(1) : stat.assists}`;
                  const rival = stat.matches
                    ? (stat.matches.team_1 === player.team ? stat.matches.team_2 : stat.matches.team_1)
                    : null;
                  const seriesId = stat.series_id ?? null;
                  const isExpanded = seriesId !== null && expandedSeriesId === seriesId;
                  const isLoadingGames = seriesId !== null && gamesLoading === seriesId;
                  const cachedGames = seriesId ? gamesCache.get(seriesId) : undefined;

                  const handleToggleExpand = (e: React.MouseEvent) => {
                    e.stopPropagation();
                    if (!seriesId) return;
                    if (isExpanded) {
                      setExpandedSeriesId(null);
                      return;
                    }
                    setExpandedSeriesId(seriesId);
                    if (!gamesCache.has(seriesId)) {
                      setGamesLoading(seriesId);
                      api.players.seriesGames(playerId, seriesId)
                        .then((resp) => {
                          setGamesCache((prev) => {
                            const next = new Map(prev);
                            next.set(seriesId, resp.games);
                            return next;
                          });
                        })
                        .catch(() => {
                          setGamesCache((prev) => {
                            const next = new Map(prev);
                            next.set(seriesId, []);
                            return next;
                          });
                        })
                        .finally(() => setGamesLoading(null));
                    }
                  };

                  return (
                    <div key={stat.week} style={{ display: "flex", flexDirection: "column" }}>
                      <div
                        onClick={() => setSelectedWeek(stat.week)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          padding: "8px 10px",
                          borderRadius: isExpanded ? "8px 8px 0 0" : 8,
                          cursor: "pointer",
                          background: isActive ? "#1E1A00" : "transparent",
                          border: isActive ? "1px solid rgba(252,212,0,0.25)" : "1px solid transparent",
                          transition: "background 0.1s",
                        }}
                      >
                        {/* Week badge */}
                        <div style={{
                          background: "#1A1A1A",
                          borderRadius: 6,
                          padding: "3px 8px",
                          fontSize: 12,
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontWeight: 700,
                          color: isActive ? "#FCD400" : "#888",
                          flexShrink: 0,
                          minWidth: 36,
                          textAlign: "center",
                        }}>
                          S{stat.week}
                        </div>

                        {/* W/L badge */}
                        <div style={{
                          width: 22,
                          height: 22,
                          borderRadius: 4,
                          background: isWin ? "#1B3A1B" : "#3A1A1A",
                          color: isWin ? "#4CAF50" : "#EF5350",
                          fontSize: 10,
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}>
                          {isWin ? "W" : "L"}
                        </div>

                        {/* Rival + KDA */}
                        <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                          {rival && (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${rival.toLowerCase().replace(/ /g, "-")}.webp`}
                              alt={rival}
                              style={{ width: 20, height: 20, objectFit: "contain", flexShrink: 0 }}
                              onError={(e) => { e.currentTarget.style.display = "none"; }}
                            />
                          )}
                          <div style={{ fontSize: 11, color: "#444" }}>{kda}</div>
                        </div>

                        {/* Puntos */}
                        <div style={{
                          fontFamily: "'Barlow Condensed', sans-serif",
                          fontSize: 14,
                          fontWeight: 700,
                          color: isWin ? "#FCD400" : "#555",
                          flexShrink: 0,
                        }}>
                          +{Math.round(stat.fantasy_points)}
                        </div>

                        {/* Expand chevron */}
                        {seriesId && (
                          <div
                            onClick={handleToggleExpand}
                            style={{
                              fontSize: 10,
                              color: isExpanded ? "#FCD400" : "#444",
                              cursor: "pointer",
                              flexShrink: 0,
                              padding: "2px 4px",
                              transition: "transform 0.15s",
                              transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                            }}
                          >
                            ▶
                          </div>
                        )}
                      </div>

                      {/* Accordion: game-by-game detail */}
                      {isExpanded && (
                        <div style={{
                          background: "#1a1a1a",
                          border: "1px solid #2a2a2a",
                          borderTop: "none",
                          borderRadius: "0 0 8px 8px",
                          padding: "8px 10px",
                          display: "flex",
                          flexDirection: "column",
                          gap: 4,
                        }}>
                          {isLoadingGames ? (
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 0" }}>
                              <div style={{
                                width: 14,
                                height: 14,
                                borderRadius: "50%",
                                border: "2px solid #333",
                                borderTopColor: "#FCD400",
                                animation: "spin 0.7s linear infinite",
                              }} />
                            </div>
                          ) : cachedGames && cachedGames.length > 0 ? (
                            <>
                              {/* Header */}
                              <div style={{
                                display: "grid",
                                gridTemplateColumns: "40px 28px 1fr 52px 44px 44px",
                                gap: 4,
                                fontSize: 9,
                                color: "#444",
                                textTransform: "uppercase",
                                letterSpacing: "0.06em",
                                paddingBottom: 4,
                                borderBottom: "1px solid #222",
                              }}>
                                <span>Game</span>
                                <span></span>
                                <span>K/D/A</span>
                                <span style={{ textAlign: "right" }}>CS/min</span>
                                <span style={{ textAlign: "right" }}>DPM</span>
                                <span style={{ textAlign: "right" }}>Pts</span>
                              </div>
                              {cachedGames.map((g) => {
                                const gWin = g.result === 1;
                                return (
                                  <div
                                    key={g.game_number}
                                    style={{
                                      display: "grid",
                                      gridTemplateColumns: "40px 28px 1fr 52px 44px 44px",
                                      gap: 4,
                                      alignItems: "center",
                                      fontSize: 11,
                                      color: "#ccc",
                                      fontFamily: "'Space Grotesk', sans-serif",
                                    }}
                                  >
                                    <span style={{ color: "#555", fontFamily: "'Barlow Condensed', sans-serif", fontSize: 12, fontWeight: 700 }}>
                                      G{g.game_number}
                                    </span>
                                    <div style={{
                                      width: 20,
                                      height: 20,
                                      borderRadius: 3,
                                      background: g.result === null ? "#222" : gWin ? "#1B3A1B" : "#3A1A1A",
                                      color: g.result === null ? "#555" : gWin ? "#4CAF50" : "#EF5350",
                                      fontSize: 9,
                                      fontWeight: 700,
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                    }}>
                                      {g.result === null ? "?" : gWin ? "W" : "L"}
                                    </div>
                                    <span style={{ color: "#666", fontSize: 11 }}>
                                      {g.kills}/{g.deaths}/{g.assists}
                                    </span>
                                    <span style={{ textAlign: "right", color: "#888", fontSize: 11 }}>
                                      {g.cs_per_min.toFixed(1)}
                                    </span>
                                    <span style={{ textAlign: "right", color: "#888", fontSize: 11 }}>
                                      {Math.round(g.dpm)}
                                    </span>
                                    <span style={{
                                      textAlign: "right",
                                      fontFamily: "'Barlow Condensed', sans-serif",
                                      fontSize: 12,
                                      fontWeight: 700,
                                      color: gWin ? "#FCD400" : "#555",
                                    }}>
                                      {Math.round(g.game_points)}
                                    </span>
                                  </div>
                                );
                              })}
                            </>
                          ) : (
                            <p style={{ fontSize: 11, color: "#444", textAlign: "center", margin: 0 }}>Sin datos de games</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200 }}>
                <p style={{ color: "#333", fontSize: 13 }}>Sin jornadas disponibles</p>
              </div>
            )}
          </div>

        </div>

      </main>
    </div>
  );
}


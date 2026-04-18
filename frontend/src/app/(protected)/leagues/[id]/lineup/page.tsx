"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);
import { api, type Roster, type RosterPlayer, type Slot, type Split } from "@/lib/api";
import { JornadaSelector } from "@/components/JornadaSelector";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getTeamBadgeUrl } from "@/components/PlayerCard";
import { getRoleColor } from "@/lib/roles";
import { ActionPopup } from "@/components/ActionPopup";
import { Button } from "@/components/ui/Button";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const STARTER_SLOTS: { slot: Slot; role: string }[] = [
  { slot: "starter_1", role: "top"     },
  { slot: "starter_2", role: "jungle"  },
  { slot: "starter_3", role: "mid"     },
  { slot: "starter_4", role: "adc"     },
  { slot: "starter_5", role: "support" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function calcJornadaPoints(players: RosterPlayer[], captainId: string | null): number {
  const STARTER_SLOT_SET = new Set(["starter_1", "starter_2", "starter_3", "starter_4", "starter_5"]);
  return players
    .filter((rp) => STARTER_SLOT_SET.has(rp.slot))
    .reduce((sum, rp) => {
      const pts = rp.jornada_points ?? 0;
      const multiplier = rp.player.id === captainId ? 2 : 1;
      return sum + pts * multiplier;
    }, 0);
}

// ---------------------------------------------------------------------------
// Split reset warning banner
// ---------------------------------------------------------------------------
function SplitResetWarning({ split, leagueId }: { split: Split | null; leagueId: string }) {
  if (!split?.reset_date) return null;

  const msUntilReset = new Date(split.reset_date).getTime() - Date.now();
  const hoursUntilReset = msUntilReset / (1000 * 60 * 60);

  if (hoursUntilReset > 48 || hoursUntilReset < 0) return null;

  const hoursLeft = Math.ceil(hoursUntilReset);

  return (
    <div className="mx-4 sm:mx-6 mt-4 animate-fade-in rounded-xl" style={{ background: "#1a1a1a", border: "1px solid #2a2a2a", padding: "12px 16px" }}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <p style={{ color: "#e5e5e5", fontWeight: 600, fontSize: 13, margin: 0 }}>Reset de split en {hoursLeft}h</p>
          <p style={{ color: "#737373", fontSize: 11, marginTop: 2 }}>
            Podés proteger 1 jugador antes del reinicio.
          </p>
        </div>
        <Link href={`/leagues/${leagueId}/lineup`} style={{ color: "#737373", fontSize: 11, whiteSpace: "nowrap", fontWeight: 500 }}>
          Proteger →
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PriceTrend indicator
// ---------------------------------------------------------------------------
function PriceTrend({ pct }: { pct?: number | null }) {
  if (!pct || pct === 0) return null;
  const isUp = pct > 0;
  const color = isUp ? "#22c55e" : "#ef4444";
  const sign = isUp ? "+" : "";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "2px",
        fontSize: "10px",
        fontFamily: "'Space Grotesk', sans-serif",
        color,
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        {isUp ? (
          <path d="M5 8V2M5 2L2 5M5 2L8 5" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <path d="M5 2V8M5 8L2 5M5 8L8 5" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        )}
      </svg>
      {sign}{pct.toFixed(1)}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// Roster Stats Bar
// ---------------------------------------------------------------------------
function RosterStatsBar({
  remainingBudget,
  totalPoints,
  jornadaPoints,
  rankPosition,
  rankTotal,
  hasCaptain,
}: {
  remainingBudget: number;
  totalPoints: number;
  jornadaPoints: number;
  rankPosition: number | null;
  rankTotal: number;
  hasCaptain?: boolean;
}) {
  const cells = [
    {
      label: "Presupuesto",
      value: remainingBudget.toFixed(1),
      unit: "M",
      valueColor: "#ffffff",
    },
    {
      label: "Puntos totales",
      value: String(Math.round(totalPoints)),
      unit: "pts",
      valueColor: "#fcd400",
    },
    {
      label: "Posición liga",
      value: rankPosition !== null ? `#${rankPosition}` : "—",
      unit: rankPosition !== null ? `de ${rankTotal}` : "",
      valueColor: "#ffffff",
    },
    {
      label: "Jornada",
      value: String(Math.round(jornadaPoints)),
      unit: "pts",
      valueColor: "#ffffff",
    },
  ];

  return (
    <div
      className="w-full mb-6"
      style={{
        background: "#161616",
        border: "1px solid #252525",
        borderRadius: "12px",
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex" }}>
        {cells.map((cell, i) => (
          <div
            key={cell.label}
            style={{
              flex: 1,
              padding: "12px 0",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "4px",
              borderLeft: i > 0 ? "1px solid #252525" : "none",
            }}
          >
            <span
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "11px",
                fontWeight: 500,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                lineHeight: 1,
              }}
            >
              {cell.label}
            </span>
            <div style={{ display: "flex", alignItems: "baseline", gap: "3px" }}>
              <span
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "24px",
                  fontWeight: 700,
                  color: cell.valueColor,
                  lineHeight: 1,
                  letterSpacing: "-0.02em",
                }}
              >
                {cell.value}
              </span>
              {cell.unit && (
                <span
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "13px",
                    color: "#6b7280",
                    lineHeight: 1,
                  }}
                >
                  {cell.unit}
                </span>
              )}
            </div>
            {cell.label === "Jornada" && hasCaptain && jornadaPoints > 0 && (
              <span
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "10px",
                  fontWeight: 600,
                  color: "#fcd400",
                  lineHeight: 1,
                  letterSpacing: "0.02em",
                }}
              >
                cap. ×2
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function LineupPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const router = useRouter();
  const [roster, setRoster]   = useState<Roster | null>(null);
  const [split, setSplit]     = useState<Split | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const startersRef = useRef<HTMLDivElement>(null);

  // Historical week state
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [availableWeeks, setAvailableWeeks] = useState<number[]>([]);
  const [weekLoading, setWeekLoading] = useState(false);

  // Captain state
  const [captainPlayerId, setCaptainPlayerId] = useState<string | null>(null);
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);
  const [captainWeek, setCaptainWeek] = useState<number | null>(null);
  const [captainModal, setCaptainModal] = useState<{
    open: boolean;
    target: RosterPlayer | null;
    mode: "assign" | "change" | "remove";
  } | null>(null);
  const [captainLoading, setCaptainLoading] = useState(false);
  const [captainError, setCaptainError] = useState<string | null>(null);

  // Rank state
  const [myRank, setMyRank] = useState<{ position: number | null; total: number }>({
    position: null,
    total: 0,
  });

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // PERF FIX: parallel fetch — roster + split + leaderboard in one Promise.all
  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.roster.get(leagueId),
      api.splits.active().catch(() => null),
      api.scoring.leaderboard(leagueId).catch(() => null),
    ])
      .then(([rosterData, splitData, leaderboard]) => {
        setRoster(rosterData);
        setSplit(splitData);
        setCaptainPlayerId(rosterData.captain_player_id ?? null);
        setCurrentWeek(rosterData.current_week ?? null);
        setCaptainWeek(rosterData.captain_week ?? null);
        if (leaderboard?.available_weeks) {
          setAvailableWeeks(leaderboard.available_weeks);
        }
        // Rank extraction — REQ-1.2, 1.3, 1.4
        if (leaderboard?.entries) {
          const myEntry = leaderboard.entries.find(
            (e: { member_id: string; rank: number }) => e.member_id === rosterData.member_id
          );
          setMyRank({
            position: myEntry?.rank ?? null,
            total: leaderboard.entries.length,
          });
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);


  useEffect(() => { load(); }, [load]);

  // Re-fetch roster when selectedWeek changes (skip initial load — load() handles it)
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    setWeekLoading(true);
    api.roster.get(leagueId, selectedWeek)
      .then((rosterData) => {
        setRoster(rosterData);
        if (selectedWeek === null) {
          setCaptainPlayerId(rosterData.captain_player_id ?? null);
        } else {
          setCaptainPlayerId(rosterData.captain_player_id ?? null);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setWeekLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId, selectedWeek]);

  useGSAP(() => {
    gsap.from(".lineup-card", {
      autoAlpha: 0,
      y: 32,
      scale: 0.96,
      duration: 0.6,
      ease: "power3.out",
      stagger: 0.07,
    });
  }, { scope: startersRef, dependencies: [loading] });

  const playerBySlot = (slot: Slot) => roster?.players.find((p) => p.slot === slot) ?? null;

  // Captain helpers
  const handleSetCaptain = (rp: RosterPlayer) => {
    if (selectedWeek !== null) return;
    if (captainPlayerId === rp.player.id) {
      // Already captain — open remove modal
      setCaptainModal({ open: true, target: rp, mode: "remove" });
    } else if (captainPlayerId) {
      // Change captain
      setCaptainModal({ open: true, target: rp, mode: "change" });
    } else {
      // Assign captain
      setCaptainModal({ open: true, target: rp, mode: "assign" });
    }
  };

  const handleCaptainConfirm = async () => {
    if (!captainWeek) return;
    const isRemove = captainModal?.mode === "remove";
    const newCaptainId = isRemove ? null : (captainModal?.target?.player.id ?? null);
    const prevCaptainId = captainPlayerId;
    const prevModal = captainModal;

    setCaptainLoading(true);
    setCaptainError(null);
    // Optimistic update
    setCaptainPlayerId(newCaptainId);
    setCaptainModal(null);
    try {
      await api.roster.setCaptain(leagueId, captainWeek, newCaptainId);
    } catch (e) {
      // Revert on error
      setCaptainPlayerId(prevCaptainId);
      setCaptainError(e instanceof Error ? e.message : "Error al asignar capitán");
      if (prevModal) setCaptainModal({ ...prevModal, open: true });
    } finally {
      setCaptainLoading(false);
    }
  };

  const captainPlayer = captainPlayerId
    ? roster?.players.find((p) => p.player.id === captainPlayerId) ?? null
    : null;

  const captainModalTitle = () => {
    if (!captainModal) return "";
    if (captainModal.mode === "remove") return `¿Remover capitán a ${captainModal.target?.player.name}?`;
    if (captainModal.mode === "change") return `¿Cambiar capitán de ${captainPlayer?.player.name} a ${captainModal.target?.player.name}?`;
    return `¿Hacer capitán a ${captainModal.target?.player.name}?`;
  };

  return (
    <div className="min-h-[100dvh] flex flex-col overflow-x-hidden" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <SplitResetWarning split={split} leagueId={leagueId} />

      <main className="flex-1 flex flex-col justify-center max-w-4xl w-full mx-auto px-4 sm:px-6 py-8 pb-24 sm:pb-8">
        {error && (
          <div className="mb-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-500 text-sm">{error}</div>
        )}

        {/* Selector de jornadas */}
        {availableWeeks.length > 0 && (
          <div className="mb-4">
            <JornadaSelector
              weeks={availableWeeks}
              selected={selectedWeek}
              onChange={setSelectedWeek}
            />
          </div>
        )}

        {weekLoading ? (
          <LineupSkeleton />
        ) : loading ? (
          <LineupSkeleton />
        ) : roster?.snapshot_missing ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No hay datos para la jornada seleccionada</p>
          </div>
        ) : !roster || roster.players.length === 0 ? (
          <EmptyRoster leagueId={leagueId} />
        ) : (
          <>

            {/* Stats bar */}
            <RosterStatsBar
              remainingBudget={roster.remaining_budget}
              totalPoints={roster.total_points}
              jornadaPoints={calcJornadaPoints(roster.players, captainPlayerId)}
              rankPosition={myRank.position}
              rankTotal={myRank.total}
              hasCaptain={captainPlayerId !== null}
            />

            {/* Starters */}
            <section>
              <div className="flex items-center gap-3 mb-3">
                <h2 className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--text-muted)" }}>
                  Titulares
                </h2>
                {captainPlayer ? (
                  <button
                    onClick={() => handleSetCaptain(captainPlayer)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      background: "rgba(252,212,0,0.1)",
                      border: "1px solid rgba(252,212,0,0.3)",
                      borderRadius: "20px",
                      padding: "2px 8px",
                      fontSize: "11px",
                      fontWeight: 600,
                      color: "#FCD400",
                      cursor: "pointer",
                      lineHeight: 1.4,
                    }}
                  >
                    C · {captainPlayer.player.name} · ×2
                  </button>
                ) : null}
              </div>
              <div ref={startersRef} className={isMobile ? "flex flex-col gap-3" : "grid grid-cols-5 gap-6"}>
                {STARTER_SLOTS.map(({ slot, role }) => {
                  const rp = playerBySlot(slot);
                  return (
                    <div key={slot} className="lineup-card" style={isMobile ? { width: "100%" } : undefined}>
                      <PlayerCard
                        expectedRole={role}
                        rp={rp}
                        leagueId={leagueId}
                        splitName={split?.name ?? undefined}
                        isMobile={isMobile}
                        onRefresh={load}
                        onOpenStats={(playerId) => router.push(`/leagues/${leagueId}/stats/${playerId}`)}
                        isCaptain={rp !== null && rp.player.id === captainPlayerId}
                        onSetCaptain={rp ? () => handleSetCaptain(rp) : undefined}
                        currentWeek={currentWeek}
                        readOnly={selectedWeek !== null}
                      />
                    </div>
                  );
                })}
              </div>
            </section>

          </>
        )}
      </main>

      {/* Captain confirmation modal */}
      {captainModal?.target && (
        <ActionPopup
          isOpen={captainModal.open}
          onClose={() => { setCaptainModal(null); setCaptainError(null); }}
          title={captainModalTitle()}
          playerName={captainModal.target.player.name}
          playerRole={captainModal.target.player.role}
          playerTeam={captainModal.target.player.team}
          playerImage={
            captainModal.target.player.image_url ||
            `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/${captainModal.target.player.name.toLowerCase().replace(/ /g, "-")}.webp`
          }
          mode="confirm"
          confirmLabel={captainModal.mode === "remove" ? "Remover" : captainModal.mode === "change" ? "Cambiar" : "Sí, capitán"}
          confirmMessage={
            captainModal.mode === "remove"
              ? "Este jugador dejará de ser tu capitán y perderás el multiplicador ×2."
              : captainModal.mode === "change"
              ? `${captainPlayer?.player.name} dejará de ser capitán. ${captainModal.target.player.name} obtendrá el multiplicador ×2.`
              : `${captainModal.target.player.name} obtendrá el multiplicador ×2 en sus puntos esta jornada.`
          }
          onConfirm={handleCaptainConfirm}
          isLoading={captainLoading}
          error={captainError}
        />
      )}

    </div>
  );
}

// ---------------------------------------------------------------------------
// PlayerCard — gaming trading card style with inline stats overlay
// ---------------------------------------------------------------------------

function PlayerCard({
  expectedRole,
  rp,
  leagueId,
  splitName,
  isMobile,
  onRefresh,
  onOpenStats,
  isCaptain,
  onSetCaptain,
  currentWeek,
  readOnly,
}: {
  expectedRole: string;
  rp: RosterPlayer | null;
  leagueId: string;
  splitName?: string;
  isMobile?: boolean;
  onRefresh?: () => void;
  onOpenStats?: (playerId: string) => void;
  isCaptain?: boolean;
  onSetCaptain?: () => void;
  currentWeek?: number | null;
  readOnly?: boolean;
}) {
  const roleColor = ROLE_COLORS[expectedRole] ?? ROLE_COLORS.coach;

  // Empty slot
  if (!rp) {
    if (isMobile) {
      return (
        <div
          className={`relative rounded-xl border-2 border-dashed flex flex-row items-center gap-3 px-4 ${roleColor.border} opacity-60`}
          style={{
            width: "100%",
            height: "64px",
            background: "var(--bg-panel)",
          }}
        >
          <div className="p-2 rounded-lg bg-white/5">
            <RoleIcon role={expectedRole} className="w-5 h-5" />
          </div>
          <span className={`text-xs font-bold ${roleColor.text}`}>
            {ROLE_LABEL[expectedRole] ?? "BENCH"}
          </span>
          <span style={{ color: "#ef4444", fontSize: 18, fontWeight: 700, lineHeight: 1, marginLeft: "auto" }}>!</span>
        </div>
      );
    }
    return (
      <div
        className={`relative rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 ${roleColor.border} opacity-60`}
        style={{
          width: "100%",
          minHeight: "340px",
          background: "var(--bg-panel)",
        }}
      >
        <div className="p-2 rounded-lg bg-white/5">
          <RoleIcon role={expectedRole} className="w-6 h-6" />
        </div>
        <span className={`text-xs font-bold ${roleColor.text}`}>
          {ROLE_LABEL[expectedRole] ?? "BENCH"}
        </span>
        <span style={{ color: "#ef4444", fontSize: 18, fontWeight: 700, lineHeight: 1 }}>!</span>
      </div>
    );
  }

  const p = rp.player;
  const rc = ROLE_COLORS[p.role] ?? ROLE_COLORS.coach;

  return (
    <PlayerCardFilled
      rp={rp}
      p={p}
      rc={rc}
      leagueId={leagueId}
      splitName={splitName}
      isMvp={false}
      isMobile={isMobile}
      onRefresh={onRefresh}
      onOpenStats={onOpenStats ? () => onOpenStats(p.id) : undefined}
      isCaptain={isCaptain ?? false}
      onSetCaptain={onSetCaptain}
      currentWeek={currentWeek}
      readOnly={readOnly}
    />
  );
}

// Separate component to keep hooks at top level (no conditional hook calls)
function PlayerCardFilled({
  rp,
  p,
  leagueId,
  isMvp,
  isMobile,
  onRefresh,
  onOpenStats,
  isCaptain,
  onSetCaptain,
  currentWeek,
  readOnly,
}: {
  rp: RosterPlayer;
  p: RosterPlayer["player"];
  rc?: (typeof ROLE_COLORS)[string];
  leagueId: string;
  splitName?: string;
  isMvp?: boolean;
  isMobile?: boolean;
  onRefresh?: () => void;
  onOpenStats?: () => void;
  isCaptain?: boolean;
  onSetCaptain?: () => void;
  currentWeek?: number | null;
  readOnly?: boolean;
}) {
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupLoading, setPopupLoading] = useState(false);
  const [popupError, setPopupError] = useState<string | null>(null);
  const roleHex = getRoleColor(p.role);

  // Helpers para cláusula
  const clauseDays = rp.clause_expires_at
    ? Math.ceil((new Date(rp.clause_expires_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : 0;
  const clauseActive = clauseDays > 0 && rp.clause_amount != null;

  // Points display logic: show jornada_points when jornada is active, split_points otherwise
  const showJornada = currentWeek != null;
  const basePoints = showJornada ? (rp.jornada_points ?? 0) : (rp.split_points ?? 0);
  const displayPoints = showJornada && isCaptain ? Math.round(basePoints * 2) : Math.round(basePoints);
  const pointsSuffix = showJornada && isCaptain ? "pts ×2" : "pts";
  const displayPointsStr = showJornada ? String(displayPoints) : (rp.split_points != null ? String(Math.round(rp.split_points)) : "—");

  const handleUpgrade = async (amount?: number) => {
    if (!amount) return;
    setPopupLoading(true);
    setPopupError(null);
    try {
      await api.clause.upgrade(leagueId, rp.id, amount);
      setPopupOpen(false);
      onRefresh?.();
    } catch (e) {
      setPopupError(e instanceof Error ? e.message : "Error al subir cláusula");
    } finally {
      setPopupLoading(false);
    }
  };

  // Build image URL — fallback to Supabase storage if image_url is null
  const imageUrl =
    p.image_url ||
    `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/${p.name.toLowerCase().replace(/ /g, "-")}.webp`;

  // ── MOBILE: horizontal card ─────────────────────────────────────────────
  if (isMobile) {
    return (
      <>
        <div
          className="group relative flex flex-row overflow-hidden transition-all duration-150 active:scale-[0.99]"
          style={{
            width: "100%",
            borderRadius: "12px",
            border: "1px solid #222222",
            background: "#111111",
            overflow: "hidden",
          }}
        >
          {/* LEFT: image 64×80 */}
          <div style={{ width: 64, height: 80, position: "relative", background: roleHex, flexShrink: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt={p.name}
              style={{ objectFit: "cover", objectPosition: "center top", width: "100%", height: "100%" }}
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
            {/* Badges overlaid on image */}
            {isMvp && (
              <div style={{ position: "absolute", top: 4, right: 4, background: "#FCD400", borderRadius: 3, padding: "1px 4px", fontSize: 8, fontWeight: 700, color: "#000" }}>
                MVP
              </div>
            )}
            {rp.is_protected && (
              <div style={{ position: "absolute", top: 4, left: 4, fontSize: 10 }}>🛡</div>
            )}
            {/* Captain badge / button */}
            {isCaptain ? (
              <button
                onClick={(e) => { e.stopPropagation(); onSetCaptain?.(); }}
                style={{
                  position: "absolute",
                  bottom: 4,
                  right: 4,
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: "#FCD400",
                  border: "1.5px solid #000",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 8,
                  fontWeight: 700,
                  color: "#000",
                  cursor: "pointer",
                  zIndex: 10,
                  padding: 0,
                }}
              >
                C
              </button>
            ) : (
              <button
                onClick={(e) => { e.stopPropagation(); onSetCaptain?.(); }}
                style={{
                  position: "absolute",
                  bottom: 4,
                  right: 4,
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: "rgba(252,212,0,0.15)",
                  border: "1px solid rgba(252,212,0,0.3)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 8,
                  fontWeight: 700,
                  color: "rgba(252,212,0,0.6)",
                  cursor: "pointer",
                  zIndex: 10,
                  padding: 0,
                }}
              >
                C
              </button>
            )}
          </div>

          {/* RIGHT: info stacked */}
          <div style={{ flex: 1, minWidth: 0, padding: "8px 10px", display: "flex", flexDirection: "column", gap: "3px" }}>
            {/* Row 1: name + badges */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <p
                style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "#FFFFFF",
                  lineHeight: 1.2,
                  margin: 0,
                  flex: 1,
                  minWidth: 0,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {p.name}
              </p>
              {rp.for_sale && (
                <span style={{ fontSize: 9, color: "#fb923c", background: "rgba(251,146,60,0.2)", border: "1px solid rgba(251,146,60,0.3)", padding: "1px 5px", borderRadius: 4, fontWeight: 600, flexShrink: 0 }}>
                  venta
                </span>
              )}
            </div>

            {/* Row 2: role badge + team */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ backgroundColor: roleHex, borderRadius: "3px", padding: "1px 5px", fontSize: "9px", fontWeight: 700, color: "#000000" }}>
                {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
              </span>
              <span style={{ fontSize: "11px", color: "#888888", fontFamily: "'Space Grotesk', sans-serif" }}>
                {p.team}
              </span>
            </div>

            {/* Row 3: pts | precio */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#FCD400", letterSpacing: "-0.02em", lineHeight: 1 }}>
                {displayPointsStr}
              </span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", color: "#888888" }}>{pointsSuffix}</span>
              <span style={{ width: 1, height: 12, background: "#2a2a2a", display: "inline-block", marginLeft: "2px", alignSelf: "center" }} />
              <span style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "11px", color: "#555555" }}>
                  {p.current_price.toFixed(1)}M
                </span>
                <PriceTrend pct={p.last_price_change_pct} />
              </span>
            </div>

            {/* Row 4: action buttons */}
            <div style={{ display: "flex", gap: "6px", marginTop: "auto" }}>
              {onOpenStats && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); onOpenStats(); }}
                  className="flex-1"
                >
                  Stats →
                </Button>
              )}
              {clauseActive && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); if (!readOnly) setPopupOpen(true); }}
                  className="flex-1"
                >
                  🔒 {clauseDays}d
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Clause upgrade popup */}
        <ActionPopup
          isOpen={popupOpen}
          onClose={() => { setPopupOpen(false); setPopupError(null); }}
          title={clauseActive ? `Subir cláusula de ${p.name}` : `Asignar cláusula a ${p.name}`}
          playerName={p.name}
          playerRole={p.role}
          playerTeam={p.team}
          playerImage={imageUrl}
          mode="input"
          minAmount={0.5}
          confirmLabel={clauseActive ? "Subir cláusula" : "Asignar cláusula"}
          previewText={(amount) =>
            clauseActive
              ? `Pagas ${amount.toFixed(1)}M · Cláusula sube ${(amount * 0.5).toFixed(1)}M`
              : `Pagas ${amount.toFixed(1)}M · Cláusula de ${(amount * 0.5).toFixed(1)}M`
          }
          onConfirm={handleUpgrade}
          isLoading={popupLoading}
          error={popupError}
        />
      </>
    );
  }

  // ── DESKTOP: vertical card ───────────────────────────────────────────────
  return (
    <div
      className="group relative flex flex-col overflow-hidden hover:-translate-y-1 transition-transform duration-150"
      style={{
        width: "100%",
        minHeight: "340px",
        borderRadius: "12px",
        border: "1px solid #222222",
        background: "#111111",
        overflow: "hidden",
      }}
    >
      {/* PHOTO ZONE — 180px tall */}
      <div
        style={{
          height: "180px",
          width: "100%",
          position: "relative",
          background: roleHex,
          flexShrink: 0,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt={p.name}
          style={{ objectFit: "cover", objectPosition: "center top", width: "100%", height: "100%" }}
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
        {/* Bottom gradient overlay */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            width: "100%",
            height: "80px",
            background: "linear-gradient(180deg, transparent 0%, #0C0C0F 100%)",
            pointerEvents: "none",
          }}
        />
        {/* MVP badge */}
        {isMvp && (
          <div
            style={{
              position: "absolute",
              top: "8px",
              right: "8px",
              background: "#FCD400",
              borderRadius: "3px",
              padding: "2px 6px",
              fontSize: "9px",
              fontWeight: 700,
              color: "#000",
              letterSpacing: "0.04em",
            }}
          >
            MVP
          </div>
        )}
        {/* Protected badge */}
        {rp.is_protected && (
          <div
            style={{
              position: "absolute",
              top: "8px",
              left: "8px",
              fontSize: "11px",
              background: "rgba(14,165,233,0.2)",
              border: "1px solid rgba(56,189,248,0.4)",
              padding: "2px 6px",
              borderRadius: "4px",
            }}
          >
            🛡
          </div>
        )}
        {/* Unified bottom panel */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 30,
            background: "rgba(0,0,0,0.75)",
            display: "flex",
            alignItems: "center",
            padding: "0 10px",
            zIndex: 2,
          }}
        >
          {/* Captain button */}
          <div
            onClick={onSetCaptain}
            style={{
              width: 18,
              height: 18,
              borderRadius: "50%",
              background: isCaptain ? "#FCD400" : "rgba(252,212,0,0.15)",
              border: isCaptain ? "1.5px solid rgba(0,0,0,0.5)" : "1px solid rgba(252,212,0,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              flexShrink: 0,
              zIndex: 10,
            }}
          >
            <span style={{ fontFamily: "Space Grotesk", fontSize: 8, fontWeight: 700, color: isCaptain ? "#000" : "rgba(252,212,0,0.6)" }}>C</span>
          </div>

          <div style={{ flex: 1 }} />

          {rp.for_sale && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#f97316", flexShrink: 0 }} />
              <span style={{ fontFamily: "Space Grotesk", fontSize: 9, fontWeight: 500, color: "#f97316" }}>en venta</span>
            </div>
          )}

          {rp.for_sale && clauseDays !== null && (
            <div style={{ width: 1, height: 8, background: "#2a2a2a", margin: "0 8px" }} />
          )}

          {clauseDays !== null && (
            <div onClick={() => setPopupOpen(true)} style={{ display: "flex", alignItems: "center", gap: 3, cursor: "pointer" }}>
              <svg width="7" height="8" viewBox="0 0 9 10" fill="none">
                <rect x="0.7" y="4.5" width="7.6" height="5" rx="1.2" stroke="#2dd4bf" strokeWidth="1.2" />
                <path d="M2.3 4.5V3C2.3 1.95 3.2 1.1 4.5 1.1C5.8 1.1 6.7 1.95 6.7 3V4.5" stroke="#2dd4bf" strokeWidth="1.2" />
              </svg>
              <span style={{ fontFamily: "Space Grotesk", fontSize: 9, fontWeight: 600, color: "#2dd4bf" }}>{clauseDays}d</span>
            </div>
          )}
        </div>
      </div>

      {/* INFO ZONE */}
      <div
        style={{ padding: "14px 16px 16px", display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}
      >
        {/* Fila 1 — Role badge + Team */}
        <div style={{ display: "flex", alignItems: "center" }}>
          <span
            style={{
              backgroundColor: roleHex,
              borderRadius: "4px",
              padding: "3px 7px",
              fontSize: "10px",
              fontWeight: 700,
              color: "#000000",
            }}
          >
            {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
          </span>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={getTeamBadgeUrl(p.team)}
            alt={p.team}
            style={{ width: 18, height: 18, objectFit: "contain", marginLeft: "auto" }}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
          />
        </div>

        {/* Fila 2 — Player name */}
        <p
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: "22px",
            fontWeight: 700,
            color: "#FFFFFF",
            letterSpacing: "-0.01em",
            lineHeight: 1.1,
            margin: 0,
          }}
        >
          {p.name}
        </p>

        {/* Divisor */}
        <div style={{ height: "1px", background: "#1E1E1E", marginBlock: "4px" }} />

        {/* Fila 3 — Pts */}
        <div style={{ display: "flex", alignItems: "baseline" }}>
          <span
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: "30px",
              fontWeight: 700,
              color: "#FCD400",
              letterSpacing: "-0.02em",
              lineHeight: 1,
            }}
          >
            {displayPointsStr}
          </span>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "12px",
              color: "#888888",
              marginLeft: "8px",
            }}
          >
            {pointsSuffix}
          </span>
        </div>

        {/* Fila 3b — Precio */}
        <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "12px",
              color: "#555555",
            }}
          >
            {p.current_price.toFixed(1)}M
          </span>
          <PriceTrend pct={p.last_price_change_pct} />
        </div>

        {/* Fila 4 — Stats button */}
        {onOpenStats && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => { e.stopPropagation(); onOpenStats(); }}
            className="w-full justify-start"
          >
            Ver stats →
          </Button>
        )}

      </div>

      {/* Clause upgrade popup */}
      <ActionPopup
        isOpen={popupOpen}
        onClose={() => { setPopupOpen(false); setPopupError(null); }}
        title={clauseActive ? `Subir cláusula de ${p.name}` : `Asignar cláusula a ${p.name}`}
        playerName={p.name}
        playerRole={p.role}
        playerTeam={p.team}
        playerImage={imageUrl}
        mode="input"
        minAmount={0.5}
        confirmLabel={clauseActive ? "Subir cláusula" : "Asignar cláusula"}
        previewText={(amount) =>
          clauseActive
            ? `Pagás ${amount.toFixed(1)}M · Cláusula sube ${(amount * 0.5).toFixed(1)}M`
            : `Pagás ${amount.toFixed(1)}M · Cláusula de ${(amount * 0.5).toFixed(1)}M`
        }
        onConfirm={handleUpgrade}
        isLoading={popupLoading}
        error={popupError}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeletons & Empty
// ---------------------------------------------------------------------------
function LineupSkeleton() {
  return (
    <div className="space-y-6">
      <div>
        <div className="h-3 w-16 rounded mb-3 animate-pulse" style={{ background: "var(--bg-panel)" }} />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="aspect-[3/4] rounded-xl animate-pulse"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyRoster({ leagueId }: { leagueId: string }) {
  return (
    <div className="py-20 text-center">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
        style={{ background: "var(--color-primary-bg)", border: "1px solid rgba(252,212,0,0.2)" }}
      >
        <RoleIcon role="support" className="w-7 h-7 text-[var(--color-primary)] opacity-60" />
      </div>
      <p className="font-semibold mb-2" style={{ color: "var(--text-secondary)" }}>Tu equipo está vacío</p>
      <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>Ve al mercado y ficha a tus primeros jugadores.</p>
      <Link
        href={`/leagues/${leagueId}/market`}
        className="inline-block px-5 py-2.5 text-sm font-bold text-white rounded-xl transition-all active:scale-95 hover:brightness-90"
        style={{ background: "linear-gradient(135deg, var(--color-primary), var(--color-primary-light))" }}
      >
        Ir al mercado →
      </Link>
    </div>
  );
}

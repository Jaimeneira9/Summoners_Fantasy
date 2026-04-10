"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);
import { api, type Roster, type RosterPlayer, type Slot, type Split } from "@/lib/api";
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

  // Captain state
  const [captainPlayerId, setCaptainPlayerId] = useState<string | null>(null);
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);
  const [captainModal, setCaptainModal] = useState<{
    open: boolean;
    target: RosterPlayer | null;
    mode: "assign" | "change" | "remove";
  } | null>(null);
  const [captainLoading, setCaptainLoading] = useState(false);
  const [captainError, setCaptainError] = useState<string | null>(null);

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
    ])
      .then(([rosterData, splitData]) => {
        setRoster(rosterData);
        setSplit(splitData);
        setCaptainPlayerId(rosterData.captain_player_id ?? null);
        setCurrentWeek(rosterData.current_week ?? null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);


  useEffect(() => { load(); }, [load]);

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
    if (!currentWeek) return;
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
      await api.roster.setCaptain(leagueId, currentWeek, newCaptainId);
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

        {loading ? (
          <LineupSkeleton />
        ) : !roster || roster.players.length === 0 ? (
          <EmptyRoster leagueId={leagueId} />
        ) : (
          <>

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

            {/* Row 3: price + pts */}
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#FCD400", letterSpacing: "-0.02em", lineHeight: 1 }}>
                {rp.split_points != null ? Math.round(rp.split_points) : "—"}
              </span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", color: "#888888" }}>pts</span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "11px", color: "#777777", marginLeft: "auto" }}>
                {p.current_price.toFixed(1)}M
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
                  onClick={(e) => { e.stopPropagation(); setPopupOpen(true); }}
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
        {/* For sale badge */}
        {rp.for_sale && (
          <div
            style={{
              position: "absolute",
              bottom: "8px",
              left: "8px",
              fontSize: "9px",
              color: "#fb923c",
              background: "rgba(251,146,60,0.2)",
              border: "1px solid rgba(251,146,60,0.3)",
              padding: "2px 6px",
              borderRadius: "4px",
              fontWeight: 600,
            }}
          >
            venta
          </div>
        )}
        {/* Clause badge */}
        {clauseActive && (
          <button
            onClick={(e) => { e.stopPropagation(); setPopupOpen(true); }}
            style={{
              position: "absolute",
              bottom: "8px",
              right: "8px",
              display: "flex",
              alignItems: "center",
              gap: "3px",
              fontSize: "10px",
              fontWeight: 700,
              color: "#5eead4",
              background: "rgba(20,184,166,0.15)",
              border: "1px solid rgba(20,184,166,0.3)",
              padding: "2px 6px",
              borderRadius: "4px",
              cursor: "pointer",
              fontFamily: "'Space Grotesk', sans-serif",
              lineHeight: 1.4,
            }}
          >
            🔒 {clauseDays}d
          </button>
        )}
        {/* Captain badge / button (desktop) */}
        {isCaptain ? (
          <button
            onClick={(e) => { e.stopPropagation(); onSetCaptain?.(); }}
            style={{
              position: "absolute",
              top: isMvp ? "36px" : "8px",
              right: "8px",
              width: 20,
              height: 20,
              borderRadius: "50%",
              background: "#FCD400",
              border: "1.5px solid #000",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 10,
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
              top: isMvp ? "36px" : "8px",
              right: "8px",
              width: 20,
              height: 20,
              borderRadius: "50%",
              background: "rgba(252,212,0,0.15)",
              border: "1px solid rgba(252,212,0,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 9,
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

        {/* Fila 3 — Pts + Precio */}
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
            {rp.split_points != null ? Math.round(rp.split_points) : "—"}
          </span>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "12px",
              color: "#888888",
              marginLeft: "4px",
            }}
          >
            pts
          </span>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "12px",
              color: "#777777",
              marginLeft: "auto",
            }}
          >
            {p.current_price.toFixed(1)}M
          </span>
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

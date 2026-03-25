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
    <div className="mx-4 sm:mx-6 mt-4 px-4 py-3 bg-orange-500/10 border border-orange-500/30 rounded-xl animate-fade-in">
      <div className="flex items-start gap-3">
        <span className="text-orange-400 text-lg flex-shrink-0">⚠️</span>
        <div>
          <p className="text-orange-300 font-semibold text-sm">Reset de split en {hoursLeft}h</p>
          <p className="text-orange-400/70 text-xs mt-0.5">
            Los equipos se reiniciarán al comenzar el nuevo split. Puedes proteger 1 jugador para que se quede contigo.
          </p>
          <Link href={`/leagues/${leagueId}/lineup`} className="text-orange-400 text-xs underline mt-1 inline-block">
            Elegir jugador protegido →
          </Link>
        </div>
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
  const startersRef = useRef<HTMLDivElement>(null);

  // PERF FIX: parallel fetch — roster + split in one Promise.all
  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.roster.get(leagueId),
      api.splits.active().catch(() => null),
    ])
      .then(([rosterData, splitData]) => {
        setRoster(rosterData);
        setSplit(splitData);
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

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <SplitResetWarning split={split} leagueId={leagueId} />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-8">
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
              <h2 className="text-xs uppercase tracking-widest mb-3 font-semibold" style={{ color: "var(--text-muted)" }}>
                Titulares
              </h2>
              <div ref={startersRef} className="flex flex-wrap justify-center gap-4">
                {STARTER_SLOTS.map(({ slot, role }) => {
                  const rp = playerBySlot(slot);
                  return (
                    <div key={slot} className="lineup-card">
                      <PlayerCard
                        expectedRole={role}
                        rp={rp}
                        leagueId={leagueId}
                        splitName={split?.name ?? undefined}
                        onRefresh={load}
                        onOpenStats={(playerId) => router.push(`/leagues/${leagueId}/stats/${playerId}`)}
                      />
                    </div>
                  );
                })}
              </div>
            </section>

          </>
        )}
      </main>

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
  onRefresh,
  onOpenStats,
}: {
  expectedRole: string;
  rp: RosterPlayer | null;
  leagueId: string;
  splitName?: string;
  onRefresh?: () => void;
  onOpenStats?: (playerId: string) => void;
}) {
  const roleColor = ROLE_COLORS[expectedRole] ?? ROLE_COLORS.coach;

  // Empty slot
  if (!rp) {
    return (
      <div
        className={`relative rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 ${roleColor.border} opacity-60`}
        style={{
          width: "200px",
          minHeight: "340px",
          background: "var(--bg-panel)",
        }}
      >
        <div className={`p-2 rounded-lg ${roleColor.bg}`}>
          <RoleIcon role={expectedRole} className={`w-6 h-6 ${roleColor.text}`} />
        </div>
        <span className={`text-xs font-bold ${roleColor.text}`}>
          {ROLE_LABEL[expectedRole] ?? "BENCH"}
        </span>
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
      onRefresh={onRefresh}
      onOpenStats={onOpenStats ? () => onOpenStats(p.id) : undefined}
    />
  );
}

// Separate component to keep hooks at top level (no conditional hook calls)
function PlayerCardFilled({
  rp,
  p,
  leagueId,
  isMvp,
  onRefresh,
  onOpenStats,
}: {
  rp: RosterPlayer;
  p: RosterPlayer["player"];
  rc?: (typeof ROLE_COLORS)[string];
  leagueId: string;
  splitName?: string;
  isMvp?: boolean;
  onRefresh?: () => void;
  onOpenStats?: () => void;
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

  return (
    <div
      className="group relative flex flex-col overflow-hidden hover:-translate-y-1 transition-transform duration-150"
      style={{
        width: "200px",
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
            {rp.split_points != null ? rp.split_points.toFixed(1) : "—"}
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
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOpenStats(); }}
            style={{
              fontSize: "11px",
              color: "#FCD400",
              fontFamily: "'Space Grotesk', sans-serif",
              background: "none",
              border: "none",
              padding: 0,
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            Ver stats →
          </button>
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

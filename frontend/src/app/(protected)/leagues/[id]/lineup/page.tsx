"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Roster, type RosterPlayer, type Slot, type Split } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { PlayerStatsModal } from "@/components/PlayerStatsModal";
import { getTeamBadgeUrl } from "@/components/PlayerCard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type StatsPlayer = {
  playerId: string;
  hint: { name: string; team: string; role: string; image_url: string | null };
};

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
  const [roster, setRoster]           = useState<Roster | null>(null);
  const [split, setSplit]             = useState<Split | null>(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [selected, setSelected]       = useState<RosterPlayer | null>(null);
  const [statsPlayer, setStatsPlayer] = useState<StatsPlayer | null>(null);

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

  const playerBySlot = (slot: Slot) => roster?.players.find((p) => p.slot === slot) ?? null;

  const handleSlotClick = async (slot: Slot) => {
    if (!roster) return;
    const target = playerBySlot(slot);
    if (!selected) { if (target) setSelected(target); return; }
    if (selected.slot === slot) { setSelected(null); return; }
    try {
      await api.roster.move(leagueId, selected.id, slot);
      setSelected(null);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al mover");
      setSelected(null);
    }
  };

  const handleSellToggle = async (rp: RosterPlayer) => {
    try {
      if (rp.for_sale) await api.roster.cancelSellIntent(leagueId, rp.id);
      else await api.roster.setSellIntent(leagueId, rp.id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const handleProtectToggle = async (rp: RosterPlayer) => {
    try {
      await api.roster.toggleProtect(leagueId, rp.id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cambiar protección");
    }
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <SplitResetWarning split={split} leagueId={leagueId} />

      {/* Player stats modal */}
      {statsPlayer && (
        <PlayerStatsModal
          playerId={statsPlayer.playerId}
          playerHint={statsPlayer.hint}
          onClose={() => setStatsPlayer(null)}
        />
      )}

      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-8">
        {/* Move selection banner */}
        {selected && (
          <div
            className="mb-5 px-4 py-3 rounded-xl text-sm flex items-center justify-between animate-fade-in"
            style={{
              background: "var(--color-primary-bg)",
              border: "1px solid rgba(107,33,232,0.3)",
              color: "var(--color-primary)",
            }}
          >
            <span>
              Moviendo <strong style={{ color: "var(--text-primary)" }}>{selected.player.name}</strong> — toca el slot de destino
            </span>
            <button
              onClick={() => setSelected(null)}
              className="ml-4 transition-colors"
              style={{ color: "var(--text-muted)" }}
            >
              ✕ Cancelar
            </button>
          </div>
        )}

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
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {STARTER_SLOTS.map(({ slot, role }) => {
                  const rp = playerBySlot(slot);
                  return (
                    <PlayerCard
                      key={slot}
                      expectedRole={role}
                      rp={rp}
                      isSelected={selected?.slot === slot}
                      isTarget={!!selected && selected.slot !== slot}
                      splitName={split?.name ?? undefined}
                      onClick={() => handleSlotClick(slot)}
                      onSellToggle={rp ? () => handleSellToggle(rp) : undefined}
                      onProtectToggle={rp ? () => handleProtectToggle(rp) : undefined}
                      onShowStats={rp ? () => setStatsPlayer({ playerId: rp.player.id, hint: { name: rp.player.name, team: rp.player.team, role: rp.player.role, image_url: rp.player.image_url } }) : undefined}
                    />
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
  isSelected,
  isTarget,
  splitName,
  onClick,
  onSellToggle,
  onProtectToggle,
  onShowStats,
}: {
  expectedRole: string;
  rp: RosterPlayer | null;
  isSelected: boolean;
  isTarget: boolean;
  splitName?: string;
  onClick: () => void;
  onSellToggle?: () => void;
  onProtectToggle?: () => void;
  onShowStats?: () => void;
}) {
  const roleColor = ROLE_COLORS[expectedRole] ?? ROLE_COLORS.coach;

  // Empty slot
  if (!rp) {
    return (
      <button
        onClick={onClick}
        className={`relative w-full aspect-[3/4] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-all duration-200
          ${isTarget
            ? "border-[rgba(107,33,232,0.5)] scale-[1.02]"
            : `${roleColor.border} opacity-60 hover:opacity-90`
          }`}
        style={{
          background: isTarget ? "var(--color-primary-bg)" : "var(--bg-panel)",
        }}
      >
        <div className={`p-2 rounded-lg ${roleColor.bg}`}>
          <RoleIcon role={expectedRole} className={`w-6 h-6 ${roleColor.text}`} />
        </div>
        <span
          className={`text-xs font-bold ${isTarget ? "" : roleColor.text}`}
          style={isTarget ? { color: "var(--color-primary)" } : undefined}
        >
          {isTarget ? "Mover aquí" : (ROLE_LABEL[expectedRole] ?? "BENCH")}
        </span>
      </button>
    );
  }

  const p = rp.player;
  const rc = ROLE_COLORS[p.role] ?? ROLE_COLORS.coach;

  return (
    <PlayerCardFilled
      rp={rp}
      p={p}
      rc={rc}
      isSelected={isSelected}
      isTarget={isTarget}
      splitName={splitName}
      onClick={onClick}
      onSellToggle={onSellToggle}
      onProtectToggle={onProtectToggle}
      onShowStats={onShowStats}
    />
  );
}

// Separate component to keep hooks at top level (no conditional hook calls)
function PlayerCardFilled({
  rp,
  p,
  rc,
  isSelected,
  isTarget,
  splitName,
  onClick,
  onSellToggle,
  onProtectToggle,
  onShowStats,
}: {
  rp: RosterPlayer;
  p: RosterPlayer["player"];
  rc: (typeof ROLE_COLORS)[string];
  isSelected: boolean;
  isTarget: boolean;
  splitName?: string;
  onClick: () => void;
  onSellToggle?: () => void;
  onProtectToggle?: () => void;
  onShowStats?: () => void;
}) {
  const handleStatsClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onShowStats?.();
  };

  return (
    <div
      className={`group relative w-full aspect-[3/4] rounded-xl overflow-hidden border-2 transition-all duration-200 flex flex-col
        ${isSelected
          ? "scale-[1.02]"
          : isTarget
            ? "cursor-pointer scale-[1.01] hover:scale-[1.03]"
            : "cursor-pointer hover:scale-[1.02] hover:-translate-y-0.5"
        }`}
      style={{
        borderColor: isSelected
          ? "var(--color-primary)"
          : isTarget
            ? "rgba(107,33,232,0.4)"
            : "var(--border-subtle)",
        boxShadow: isSelected
          ? "0 0 20px rgba(107,33,232,0.25)"
          : "0 2px 8px rgba(26,28,26,0.08)",
      }}
    >
      {/* Photo fills the card — click opens stats */}
      <div
        className="absolute inset-0"
        style={{ background: "var(--bg-panel)" }}
        onClick={(e) => { e.stopPropagation(); onShowStats?.(); }}
      >
        {p.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={p.image_url} alt={p.name}
            className="w-full h-full object-cover object-top grayscale group-hover:grayscale-0 group-hover:-translate-y-1 transition-all duration-300"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{ background: "var(--bg-surface)" }}
          >
            <RoleIcon role={p.role} className={`w-16 h-16 ${rc.text} opacity-20`} />
          </div>
        )}
        {/* Gradient overlay */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(to top, rgba(30,27,30,0.95) 0%, rgba(30,27,30,0.7) 25%, transparent 50%)" }}
        />
      </div>

      {/* Role badge — top left */}
      <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-1 rounded-lg ${rc.bg} border ${rc.border} backdrop-blur-sm`}>
        <RoleIcon role={p.role} className={`w-3 h-3 ${rc.text}`} />
        <span className={`text-[9px] font-black ${rc.text}`}>{ROLE_LABEL[p.role] ?? p.role.toUpperCase()}</span>
      </div>

      {/* Price — top right */}
      <div
        className="absolute top-2 right-2 font-mono text-[10px] font-bold px-1.5 py-0.5 rounded-md backdrop-blur-sm"
        style={{
          color: "var(--color-gold)",
          background: "rgba(0,0,0,0.6)",
          border: "1px solid rgba(252,212,0,0.2)",
        }}
      >
        {p.current_price.toFixed(1)}M
      </div>

      {/* For sale badge */}
      {rp.for_sale && (
        <div className="absolute top-8 right-2 text-[9px] text-orange-400 bg-orange-400/20 border border-orange-400/30 px-1.5 py-0.5 rounded-md font-semibold">
          venta
        </div>
      )}

      {/* Protected badge */}
      {rp.is_protected && (
        <div className="absolute top-2 right-10 text-[11px] bg-sky-500/20 border border-sky-400/40 px-1.5 py-0.5 rounded-md">
          🛡
        </div>
      )}

      {/* Selected overlay */}
      {isSelected && (
        <div className="absolute inset-0 pointer-events-none" style={{ background: "var(--color-primary-bg)" }} />
      )}

      {/* Team badge — bottom right of photo area */}
      {p.team && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={getTeamBadgeUrl(p.team)}
          alt={p.team}
          className="absolute bottom-12 right-2 w-6 h-6 object-contain rounded-sm pointer-events-none"
          style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.8))" }}
        />
      )}

      {/* Info — bottom */}
      <div className="absolute bottom-0 inset-x-0 p-3" onClick={onClick}>
        <p
          className="font-black text-sm leading-tight truncate text-white uppercase tracking-tight"
          style={{ fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {p.name}
        </p>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          <p className="text-white/50 text-[11px] truncate">{p.team}</p>
        </div>
      </div>

      {/* Action buttons — slide up on hover */}
      <div className="absolute bottom-0 inset-x-0 translate-y-full group-hover:translate-y-0 transition-transform duration-200 flex flex-wrap gap-1 p-2 bg-black/80 backdrop-blur-sm">
        {onProtectToggle && (
          <button
            onClick={(e) => { e.stopPropagation(); onProtectToggle(); }}
            title={rp.is_protected ? "Quitar protección" : "Proteger para el reset de split"}
            className={`py-1.5 px-2 text-[10px] font-semibold rounded-lg transition-all active:scale-95
              ${rp.is_protected
                ? "text-sky-300 bg-sky-500/20 hover:bg-sky-500/30"
                : "text-white/30 bg-white/5 hover:bg-white/10 hover:text-white/60"
              }`}
          >
            🛡
          </button>
        )}
        {onSellToggle && (
          <button
            onClick={(e) => { e.stopPropagation(); onSellToggle(); }}
            className={`flex-1 py-1.5 text-[10px] font-semibold rounded-lg transition-all active:scale-95
              ${rp.for_sale
                ? "text-orange-400 bg-orange-400/20 hover:bg-orange-400/30"
                : "text-white/30 bg-white/5 hover:bg-white/10 hover:text-white/60"
              }`}
          >
            {rp.for_sale ? "✕ Venta" : "Vender"}
          </button>
        )}
      </div>
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
        style={{ background: "var(--color-primary-bg)", border: "1px solid rgba(107,33,232,0.2)" }}
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

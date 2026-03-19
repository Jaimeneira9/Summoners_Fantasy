"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, type Listing, type SellOffer, type MyBid, type Split } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getTeamBadgeUrl } from "@/components/PlayerCard";
import { PlayerStatsModal } from "@/components/PlayerStatsModal";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = "mercado" | "mis-pujas" | "ofertas";

type StatsPlayer = {
  playerId: string;
  hint: { name: string; team: string; role: string; image_url: string | null };
};

// ---------------------------------------------------------------------------
// Countdown hook
// ---------------------------------------------------------------------------
function useCountdown(closesAt: string | null | undefined): string {
  const [label, setLabel] = useState("");
  useEffect(() => {
    if (!closesAt) return;
    const update = () => {
      const diff = new Date(closesAt).getTime() - Date.now();
      if (diff <= 0) { setLabel("Cerrado"); return; }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1_000);
      setLabel(`${h}h ${m.toString().padStart(2, "0")}m ${s.toString().padStart(2, "0")}s`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [closesAt]);
  return label;
}

// ---------------------------------------------------------------------------
// Market page
// ---------------------------------------------------------------------------
// Map URL query param values from sidebar to internal Tab keys
const URL_TAB_MAP: Record<string, Tab> = {
  live:   "mercado",
  bids:   "mis-pujas",
  offers: "ofertas",
};

export default function MarketPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();

  const tabFromUrl = searchParams.get("tab");
  const initialTab: Tab = (tabFromUrl && URL_TAB_MAP[tabFromUrl]) ?? "mercado";

  const [tab, setTab]               = useState<Tab>(initialTab);
  const [budget, setBudget]         = useState<number | null>(null);
  const [statsPlayer, setStatsPlayer] = useState<StatsPlayer | null>(null);
  const [split, setSplit]           = useState<Split | null>(null);

  useEffect(() => {
    api.leagues.get(leagueId).then((l) => {
      if (l.member) setBudget(l.member.remaining_budget);
    }).catch(() => {});
    api.splits.active().then(setSplit).catch(() => {});
  }, [leagueId]);

  const refreshBudget = useCallback(() => {
    api.leagues.get(leagueId)
      .then((l) => l.member && setBudget(l.member.remaining_budget))
      .catch(() => {});
  }, [leagueId]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "mercado",   label: "Mercado"   },
    { key: "mis-pujas", label: "Mis pujas" },
    { key: "ofertas",   label: "Ofertas"   },
  ];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      {/* Tabs */}
      <div className="border-b px-4 sm:px-6" style={{ borderBottomColor: "var(--border-subtle)" }}>
        <nav className="flex gap-0 overflow-x-auto scrollbar-none">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-3 sm:px-4 py-3 text-xs sm:text-sm border-b-2 transition-all duration-200 -mb-px whitespace-nowrap font-medium"
              style={{
                borderBottomColor: tab === t.key ? "var(--color-primary)" : "transparent",
                color: tab === t.key ? "var(--color-primary)" : "var(--text-muted)",
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 pb-24 sm:py-8">
        {tab === "mercado"   && <MarketTab  leagueId={leagueId} splitName={split?.name} onBid={refreshBudget} onShowStats={setStatsPlayer} />}
        {tab === "mis-pujas" && <MyBidsTab  leagueId={leagueId} />}
        {tab === "ofertas"   && <OffersTab  leagueId={leagueId} />}
      </main>

      {/* Player stats modal */}
      {statsPlayer && (
        <PlayerStatsModal
          playerId={statsPlayer.playerId}
          playerHint={statsPlayer.hint}
          onClose={() => setStatsPlayer(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Market tab
// ---------------------------------------------------------------------------
function MarketTab({ leagueId, splitName, onBid, onShowStats }: { leagueId: string; splitName?: string; onBid: () => void; onShowStats: (p: StatsPlayer) => void }) {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<string>("all");

  const load = useCallback(() => {
    setLoading(true);
    api.market.listings(leagueId)
      .then(setListings)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { load(); }, [load]);

  const roles = ["all", "top", "jungle", "mid", "adc", "support", "coach"];
  const filtered = roleFilter === "all" ? listings : listings.filter((l) => l.players.role === roleFilter);

  if (loading) return <CardSkeleton />;
  if (error)   return <ErrorState message={error} onRetry={load} />;
  if (listings.length === 0) return (
    <EmptyState
      title="El mercado está vacío"
      description="No hay jugadores disponibles hoy. El mercado abre a medianoche con una ventana de 24 horas."
    />
  );

  return (
    <div>
      {/* Role filter pills */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {roles.map((r) => {
          const rc = r !== "all" ? (ROLE_COLORS[r] ?? ROLE_COLORS.coach) : null;
          const active = roleFilter === r;
          return (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-150 active:scale-95
                ${active
                  ? rc
                    ? `${rc.bg} ${rc.text} ${rc.border}`
                    : ""
                  : ""
                }`}
              style={active && !rc ? {
                background: "var(--color-primary-bg)",
                color: "var(--color-primary)",
                borderColor: "rgba(107,33,232,0.3)",
              } : !active ? {
                background: "var(--bg-surface)",
                color: "var(--text-muted)",
                borderColor: "var(--border-subtle)",
              } : undefined}
            >
              {rc && r !== "all" && <RoleIcon role={r} className={`w-3 h-3 ${active ? rc.text : "text-[var(--text-muted)]"}`} />}
              {r === "all" ? "Todos" : ROLE_LABEL[r] ?? r.toUpperCase()}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
        {filtered.map((l) => (
          <PlayerCard
            key={l.id}
            listing={l}
            leagueId={leagueId}
            splitName={splitName}
            onBid={() => { onBid(); load(); }}
            onShowStats={onShowStats}
          />
        ))}
      </div>

      {filtered.length === 0 && listings.length > 0 && (
        <div className="py-16 text-center">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Sin jugadores para este rol.</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player card — trading card style, clicking photo/info opens stats modal
// ---------------------------------------------------------------------------
function PlayerCard({
  listing,
  leagueId,
  splitName,
  onBid,
  onShowStats,
}: {
  listing: Listing;
  leagueId: string;
  splitName?: string;
  onBid: () => void;
  onShowStats: (p: StatsPlayer) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [bidAmount, setBidAmount] = useState(listing.ask_price.toFixed(1));
  const [busy, setBusy]         = useState(false);
  const [err, setErr]           = useState<string | null>(null);
  const [success, setSuccess]   = useState(false);

  const inputRef  = useRef<HTMLInputElement>(null);
  const countdown = useCountdown(listing.closes_at);
  const roleColor = ROLE_COLORS[listing.players.role] ?? ROLE_COLORS.coach;
  const closed    = countdown === "Cerrado";
  const p         = listing.players;

  const handleBid = async () => {
    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= 0) { setErr("Cantidad inválida"); return; }
    setBusy(true); setErr(null);
    try {
      await api.bids.place(leagueId, listing.id, amount);
      setSuccess(true);
      setExpanded(false);
      setTimeout(() => setSuccess(false), 3000);
      onBid();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Error al pujar");
    } finally { setBusy(false); }
  };

  const handleCardClick = () => {
    onShowStats({
      playerId: listing.player_id,
      hint: { name: p.name, team: p.team, role: p.role, image_url: p.image_url },
    });
  };

  return (
    <div
      className={`group relative border rounded-xl overflow-hidden transition-all duration-300 flex flex-col hover:scale-[1.02] hover:-translate-y-1`}
      style={{
        background: "var(--bg-panel)",
        borderColor: success ? "rgba(34,197,94,0.4)" : "var(--border-subtle)",
        boxShadow: success ? "0 0 16px rgba(34,197,94,0.08)" : "0 2px 8px rgba(26,28,26,0.08)",
      }}
    >
      {/* Photo section — clickable to open stats modal */}
      <button
        type="button"
        onClick={handleCardClick}
        className="relative w-full aspect-[3/4] overflow-hidden flex-shrink-0 text-left focus:outline-none"
        style={{ background: "var(--bg-surface)" }}
        aria-label={`Ver estadísticas de ${p.name}`}
      >
        {p.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={p.image_url}
            alt={p.name}
            className="w-full h-full object-cover object-top grayscale group-hover:grayscale-0 group-hover:-translate-y-1 transition-all duration-300"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{ background: "var(--bg-surface)" }}
          >
            <RoleIcon role={p.role} className={`w-16 h-16 ${roleColor.text} opacity-10`} />
          </div>
        )}

        {/* Gradient overlay */}
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(to top, rgba(30,27,30,0.95) 0%, rgba(30,27,30,0.7) 25%, transparent 55%)" }}
        />

        {/* Role badge — top left */}
        <div className={`absolute top-2 left-2 p-1.5 rounded-lg ${roleColor.bg} ${roleColor.border} border backdrop-blur-sm`}>
          <RoleIcon role={p.role} className={`w-3.5 h-3.5 ${roleColor.text}`} />
        </div>

        {/* Price chip — top right */}
        <div
          className="absolute top-2 right-2 font-mono text-[11px] font-bold backdrop-blur-sm px-2 py-0.5 rounded-md"
          style={{
            color: "var(--color-gold)",
            background: "rgba(0,0,0,0.7)",
            border: "1px solid rgba(252,212,0,0.2)",
          }}
        >
          {listing.ask_price.toFixed(1)}M
        </div>

        {/* Team badge — bottom right of photo */}
        {p.team && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={getTeamBadgeUrl(p.team)}
            alt={p.team}
            className="absolute bottom-2 right-2 w-6 h-6 object-contain rounded-sm pointer-events-none"
            style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.8))" }}
          />
        )}

        {/* Stats hint — bottom center on hover */}
        <div className="absolute bottom-2 inset-x-0 flex justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
          <span
            className="text-[10px] backdrop-blur-sm px-2 py-0.5 rounded-full"
            style={{
              color: "var(--color-primary-light)",
              background: "rgba(0,0,0,0.7)",
              border: "1px solid rgba(107,33,232,0.3)",
            }}
          >
            Ver stats →
          </span>
        </div>

        {/* Success overlay */}
        {success && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="text-green-400 text-center">
              <svg className="w-10 h-10 mx-auto mb-1" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <p className="text-xs font-semibold">Puja enviada</p>
            </div>
          </div>
        )}
      </button>

      {/* Player info + bid section */}
      <div className="p-3 flex flex-col flex-1" style={{ background: "var(--bg-surface)", borderTop: "1px solid var(--border-subtle)" }}>
        <button
          type="button"
          onClick={handleCardClick}
          className="text-left focus:outline-none"
        >
          <h3
            className="font-bold text-sm truncate leading-tight transition-colors"
            style={{ color: "var(--text-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLHeadingElement).style.color = "var(--color-primary)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLHeadingElement).style.color = "var(--text-primary)"; }}
          >
            {p.name}
          </h3>
        </button>
        <div className="flex items-center justify-between mt-0.5 gap-1">
          <span className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{p.team}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${roleColor.bg} ${roleColor.text}`}>
            {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
          </span>
        </div>
        {/* Countdown */}
        {listing.closes_at && !closed && countdown && (
          <p className="text-[10px] mt-1 font-mono" style={{ color: "var(--text-muted)" }}>⏱ {countdown}</p>
        )}
        {closed && <p className="text-[10px] mt-1" style={{ color: "var(--color-danger, rgb(220,38,38))" }}>Cerrado</p>}

        {/* Bid section */}
        <div className="mt-2 flex-1 flex flex-col justify-end gap-1.5">
          {!expanded ? (
            <button
              onClick={() => { setExpanded(true); setTimeout(() => inputRef.current?.focus(), 50); }}
              disabled={closed}
              className="w-full py-1.5 text-xs rounded-lg border transition-all duration-150 active:scale-95"
              style={success ? {
                borderColor: "rgba(34,197,94,0.4)",
                color: "rgb(22,163,74)",
              } : closed ? {
                borderColor: "var(--border-subtle)",
                color: "var(--text-muted)",
                cursor: "not-allowed",
                opacity: "0.5",
              } : {
                borderColor: "var(--border-medium)",
                color: "var(--text-secondary)",
              }}
              onMouseEnter={(e) => {
                if (!closed && !success) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(107,33,232,0.4)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--color-primary)";
                  (e.currentTarget as HTMLButtonElement).style.background = "var(--color-primary-bg)";
                }
              }}
              onMouseLeave={(e) => {
                if (!closed && !success) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-medium)";
                  (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                }
              }}
            >
              {success ? "✓ Puja enviada" : closed ? "Cerrado" : "Pujar"}
            </button>
          ) : (
            <div className="space-y-1.5">
              <div className="flex items-center gap-1">
                <input
                  ref={inputRef}
                  type="number"
                  step="0.5"
                  min={listing.ask_price}
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                  className="flex-1 min-w-0 text-xs rounded px-2 py-1.5 outline-none transition-colors appearance-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none [&::-moz-appearance]:textfield"
                  style={{
                    background: "var(--bg-base)",
                    border: "1px solid var(--border-medium)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "rgba(107,33,232,0.5)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-medium)"; }}
                />
                <span className="text-xs flex-shrink-0" style={{ color: "var(--text-muted)" }}>M</span>
              </div>
              {err && <p className="text-red-400 text-[10px]">{err}</p>}
              <div className="flex gap-1.5">
                <button
                  onClick={() => { setExpanded(false); setErr(null); }}
                  className="flex-1 py-1 text-xs transition-colors"
                  style={{ color: "var(--text-muted)" }}
                >
                  ✕
                </button>
                <button
                  onClick={handleBid}
                  disabled={busy}
                  className="flex-[2] py-1.5 text-xs font-bold text-white rounded-lg transition-all active:scale-95 disabled:opacity-40 hover:brightness-90"
                  style={{ background: "linear-gradient(135deg, var(--color-primary), var(--color-primary-light))" }}
                >
                  {busy ? "…" : "Confirmar"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// My bids tab
// ---------------------------------------------------------------------------
function MyBidsTab({ leagueId }: { leagueId: string }) {
  const [bids, setBids]       = useState<MyBid[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.bids.myBids(leagueId)
      .then(setBids)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <ListSkeleton rows={3} />;
  if (error)   return <ErrorState message={error} onRetry={load} />;
  if (bids.length === 0) return (
    <EmptyState
      title="Sin pujas activas"
      description="Visita el mercado y haz una puja. El ganador se conoce al cierre (medianoche)."
    />
  );

  return (
    <div className="space-y-2">
      {bids.map((b) => <BidRow key={b.id} bid={b} leagueId={leagueId} onCancel={load} />)}
    </div>
  );
}

function BidRow({ bid, leagueId, onCancel }: { bid: MyBid; leagueId: string; onCancel: () => void }) {
  const [busy, setBusy] = useState(false);
  const countdown       = useCountdown(bid.status === "active" ? bid.listing_closes_at : null);
  const roleColor       = ROLE_COLORS[bid.player_role] ?? ROLE_COLORS.coach;

  const handleCancel = async () => {
    setBusy(true);
    try { await api.bids.cancel(leagueId, bid.listing_id); onCancel(); }
    catch { /* ignore */ }
    finally { setBusy(false); }
  };

  return (
    <div
      className="flex items-center gap-3 sm:gap-4 rounded-xl px-4 py-3 transition-all duration-150 border"
      style={{
        background: "var(--bg-surface)",
        borderColor: bid.status === "won"
          ? "rgba(34,197,94,0.3)"
          : bid.status === "lost"
            ? "var(--border-subtle)"
            : "var(--border-subtle)",
      }}
    >
      <div
        className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border-medium)" }}
      >
        {bid.player_image_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={bid.player_image_url} alt={bid.player_name} className="w-full h-full object-cover object-top" />
          : <RoleIcon role={bid.player_role} className={`w-5 h-5 ${roleColor.text}`} />
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm truncate" style={{ color: "var(--text-primary)" }}>{bid.player_name}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${roleColor.bg} ${roleColor.text}`}>
            {ROLE_LABEL[bid.player_role] ?? bid.player_role.toUpperCase()}
          </span>
        </div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{bid.player_team}</p>
        {bid.status === "active" && bid.listing_closes_at && countdown && countdown !== "Cerrado" && (
          <p className="text-[10px] mt-0.5 font-mono" style={{ color: "var(--text-muted)" }}>⏱ {countdown}</p>
        )}
      </div>
      <div className="text-right flex-shrink-0 mr-2">
        <p className="font-mono text-sm font-semibold" style={{ color: "var(--color-gold-dark)" }}>
          {bid.bid_amount.toFixed(1)}M
        </p>
        <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>tu puja</p>
      </div>
      {bid.status === "won" && (
        <span className="px-2.5 py-1 text-xs font-bold text-green-600 bg-green-500/10 border border-green-500/20 rounded-lg flex-shrink-0">
          ✓ Ganada
        </span>
      )}
      {bid.status === "lost" && (
        <span
          className="px-2.5 py-1 text-xs font-bold rounded-lg flex-shrink-0"
          style={{
            color: "var(--text-muted)",
            background: "var(--bg-panel)",
            border: "1px solid var(--border-medium)",
          }}
        >
          ✗ Perdida
        </span>
      )}
      {bid.status === "active" && (
        <button
          onClick={handleCancel}
          disabled={busy || countdown === "Cerrado"}
          className="px-3 py-1.5 text-xs rounded-lg transition-all disabled:opacity-40 active:scale-95 flex-shrink-0"
          style={{
            color: "var(--text-muted)",
            border: "1px solid var(--border-medium)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(220,38,38,0.3)";
            (e.currentTarget as HTMLButtonElement).style.color = "rgb(220,38,38)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-medium)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)";
          }}
        >
          {busy ? "…" : "Cancelar"}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Offers tab
// ---------------------------------------------------------------------------
function OffersTab({ leagueId }: { leagueId: string }) {
  const [offers, setOffers]   = useState<SellOffer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.market.sellOffers(leagueId)
      .then(setOffers)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <ListSkeleton rows={3} />;
  if (error)   return <ErrorState message={error} onRetry={load} />;
  if (offers.length === 0) return (
    <EmptyState
      title="Sin ofertas pendientes"
      description="Cuando marques un jugador para venta, el sistema te enviará una oferta aquí."
    />
  );

  return (
    <div className="space-y-2">
      {offers.map((o) => <OfferRow key={o.id} offer={o} leagueId={leagueId} onAction={load} />)}
    </div>
  );
}

function OfferRow({ offer, leagueId, onAction }: { offer: SellOffer; leagueId: string; onAction: () => void }) {
  const [busy, setBusy] = useState<"accept" | "reject" | null>(null);
  const [err, setErr]   = useState<string | null>(null);
  const roleColor = ROLE_COLORS[offer.player.role] ?? ROLE_COLORS.coach;
  const expiresIn = Math.ceil((new Date(offer.expires_at).getTime() - Date.now()) / 86_400_000);

  const handle = async (action: "accept" | "reject") => {
    setBusy(action); setErr(null);
    try {
      if (action === "accept") await api.market.acceptOffer(leagueId, offer.id);
      else await api.market.rejectOffer(leagueId, offer.id);
      onAction();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Error");
    } finally { setBusy(null); }
  };

  const p = offer.player;
  return (
    <div
      className="flex items-center gap-3 sm:gap-4 rounded-xl px-4 py-3 transition-all duration-150 border"
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border-subtle)",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(107,33,232,0.2)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-subtle)"; }}
    >
      <div
        className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
        style={{ background: "var(--bg-panel)", border: "1px solid var(--border-medium)" }}
      >
        {p.image_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover object-top" />
          : <RoleIcon role={p.role} className={`w-5 h-5 ${roleColor.text}`} />
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm truncate" style={{ color: "var(--text-primary)" }}>{p.name}</span>
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${roleColor.bg} ${roleColor.text}`}>
            {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
          </span>
        </div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{p.team}</p>
      </div>
      <div className="text-right flex-shrink-0 mr-1">
        <p className="font-mono text-sm font-semibold" style={{ color: "var(--color-gold-dark)" }}>
          {offer.ask_price.toFixed(1)}M
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{expiresIn > 0 ? `${expiresIn}d` : "hoy"}</p>
      </div>
      {err && <span className="text-red-500 text-xs">{err}</span>}
      <div className="flex gap-2 flex-shrink-0">
        <button
          onClick={() => handle("reject")}
          disabled={busy !== null}
          className="px-2 sm:px-3 py-1.5 text-xs rounded-lg transition-all disabled:opacity-40 active:scale-95"
          style={{ color: "var(--text-muted)", border: "1px solid var(--border-medium)" }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(220,38,38,0.3)";
            (e.currentTarget as HTMLButtonElement).style.color = "rgb(220,38,38)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-medium)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)";
          }}
        >
          {busy === "reject" ? "…" : "Rechazar"}
        </button>
        <button
          onClick={() => handle("accept")}
          disabled={busy !== null}
          className="px-2 sm:px-3 py-1.5 text-xs text-white font-semibold rounded-lg transition-all disabled:opacity-40 active:scale-95 hover:brightness-90"
          style={{ background: "linear-gradient(135deg, var(--color-primary), var(--color-primary-light))" }}
        >
          {busy === "accept" ? "…" : "Aceptar"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------
function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="py-20 text-center">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
        style={{ background: "var(--color-primary-bg)", border: "1px solid rgba(107,33,232,0.15)" }}
      >
        <svg className="w-7 h-7 opacity-60" style={{ color: "var(--color-primary)" }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
      </div>
      <p className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{title}</p>
      <p className="text-sm max-w-sm mx-auto" style={{ color: "var(--text-secondary)" }}>{description}</p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="py-20 text-center">
      <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>{message}</p>
      <button
        onClick={onRetry}
        className="text-sm rounded-lg px-4 py-2 transition-all active:scale-95"
        style={{
          color: "var(--text-secondary)",
          border: "1px solid var(--border-medium)",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(107,33,232,0.3)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--color-primary)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-medium)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
        }}
      >
        Reintentar
      </button>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
      {Array.from({ length: 10 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl overflow-hidden animate-pulse"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="w-full aspect-[3/4]" style={{ background: "var(--bg-panel)" }} />
          <div className="p-3 space-y-2">
            <div className="h-3.5 rounded w-3/4" style={{ background: "var(--bg-panel)" }} />
            <div className="h-3 rounded w-1/2" style={{ background: "var(--bg-panel)" }} />
            <div className="h-7 rounded mt-2" style={{ background: "var(--bg-panel)" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-16 rounded-xl animate-pulse"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        />
      ))}
    </div>
  );
}


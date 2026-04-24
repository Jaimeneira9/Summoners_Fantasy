"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);
import { api, type Listing, type SellOffer, type MyBid, type Split, type League, type ScoutPlayer } from "@/lib/api";
import { ROLE_LABEL } from "@/components/RoleIcon";
import { getTeamBadgeUrl } from "@/components/PlayerCard";
import { getRoleColor } from "@/lib/roles";
import { PriceTrend } from "@/components/PriceTrend";
import { ActionPopup } from "@/components/ActionPopup";
import FilterDrawer, { FilterDrawerFilters } from "@/components/FilterDrawer";
import { Button } from "@/components/ui/Button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = "mercado" | "mis-pujas" | "ofertas" | "explorar";

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
const URL_TAB_MAP: Record<string, Tab> = {
  live:   "mercado",
  bids:   "mis-pujas",
  offers: "ofertas",
  scout:  "explorar",
};

const MOBILE_TABS: { key: string; label: string }[] = [
  { key: "live",   label: "En vivo" },
  { key: "bids",   label: "Mis Pujas" },
  { key: "offers", label: "Ofertas" },
  { key: "scout",  label: "Explorar" },
];

export default function MarketPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const tabFromUrl = searchParams.get("tab");
  const tab: Tab = (tabFromUrl ? URL_TAB_MAP[tabFromUrl] : null) ?? "mercado";

  const [hoveredTab, setHoveredTab] = useState<string | null>(null);
  const [budget, setBudget]               = useState<number | null>(null);
  const [retainedBudget, setRetainedBudget] = useState(0);
  const [bidsByListing, setBidsByListing] = useState<Map<string, number>>(new Map());
  const [league, setLeague]               = useState<League | null>(null);
  const [split, setSplit]                 = useState<Split | null>(null);

  const refreshRetained = useCallback(() => {
    api.bids.myBids(leagueId)
      .then((bids) => {
        const active = bids.filter((b) => b.status === "active");
        const sum = active.reduce((acc, b) => acc + b.bid_amount, 0);
        setRetainedBudget(sum);
        const map = new Map<string, number>();
        active.forEach((b) => map.set(b.listing_id, b.bid_amount));
        setBidsByListing(map);
      })
      .catch(() => {});
  }, [leagueId]);

  useEffect(() => {
    api.leagues.get(leagueId).then((l) => {
      setLeague(l);
      if (l.member) setBudget(l.member.remaining_budget);
    }).catch(() => {});
    api.splits.active().then(setSplit).catch(() => {});
    refreshRetained();
  }, [leagueId, refreshRetained]);

  const refreshBudget = useCallback(() => {
    api.leagues.get(leagueId)
      .then((l) => {
        setLeague(l);
        if (l.member) setBudget(l.member.remaining_budget);
      })
      .catch(() => {});
    refreshRetained();
  }, [leagueId, refreshRetained]);

  if (league?.game_mode === "budget_pick") {
    return (
      <div className="min-h-[100dvh] flex items-center justify-center" style={{ background: "#0A0A0A", color: "#F0E8D0" }}>
        <div className="text-center py-20 px-6">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}
          >
            <span className="material-symbols-outlined text-3xl" style={{ color: "#333333" }}>storefront</span>
          </div>
          <p
            className="font-semibold mb-2"
            style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "16px" }}
          >
            Este modo de juego no tiene mercado.
          </p>
          <p
            className="text-sm"
            style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            En Budget Pick los jugadores son elegidos al inicio de la temporada y no se pueden fichar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] overflow-x-hidden" style={{ background: "#0A0A0A", color: "#F0E8D0" }}>
      {/* Page header */}
      <div
        className="px-6 pt-6 pb-0"
        style={{ borderBottom: "1px solid #1A1A1A" }}
      >
        <div className="max-w-6xl mx-auto">
          <div className="flex items-start justify-between gap-4 mb-5">
            {/* Title block */}
            <div>
              {league && (
                <p
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "10px",
                    fontWeight: 700,
                    letterSpacing: "0.1em",
                    color: "#333333",
                    textTransform: "uppercase",
                    marginBottom: "4px",
                  }}
                >
                  {league.name}
                </p>
              )}
              <h1
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "30px",
                  fontWeight: 700,
                  letterSpacing: "-0.02em",
                  color: "#F0E8D0",
                  lineHeight: 1,
                }}
              >
                Mercado de Fichajes
              </h1>
            </div>

            {/* Budget badge */}
            {budget !== null && (
              <div
                style={{
                  background: "#1A1A1A",
                  border: "1px solid #2A2A2A",
                  borderRadius: "8px",
                  padding: "8px 14px",
                  flexShrink: 0,
                }}
              >
                <p
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "11px",
                    color: "#555555",
                    marginBottom: "2px",
                  }}
                >
                  Disponible
                </p>
                <p
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#FCD400",
                  }}
                >
                  {(budget - retainedBudget).toFixed(1)}M
                </p>
                {retainedBudget > 0 && (
                  <>
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: "11px",
                        color: "#555555",
                        marginTop: "6px",
                        marginBottom: "2px",
                      }}
                    >
                      En pujas
                    </p>
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: "13px",
                        fontWeight: 700,
                        color: "#E8834A",
                      }}
                    >
                      {retainedBudget.toFixed(1)}M
                    </p>
                  </>
                )}
              </div>
            )}
          </div>

        </div>
      </div>

      {/* Mobile pill tab bar — hidden on sm+ */}
      <div className="block sm:hidden px-4 pt-3 pb-1 overflow-x-auto">
        <div className="flex gap-2 min-w-max">
          {MOBILE_TABS.map(({ key, label }) => {
            const isActive = tab === URL_TAB_MAP[key];
            return (
              <button
                key={key}
                onClick={() => router.push(`?tab=${key}`)}
                onMouseEnter={() => !isActive && setHoveredTab(key)}
                onMouseLeave={() => setHoveredTab(null)}
                className="px-4 py-2 text-xs font-bold active:scale-95 flex-shrink-0"
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  borderRadius: "20px",
                  background: isActive
                    ? "#FCD400"
                    : hoveredTab === key
                      ? "rgba(255,255,255,0.06)"
                      : "#1A1A1A",
                  color:  isActive ? "#111111" : "#555555",
                  border: isActive ? "1px solid #FCD400" : "1px solid #2A2A2A",
                  transition: "all 150ms",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 pb-24">
        {tab === "mercado"   && <MarketTab  leagueId={leagueId} budget={budget} availableBudget={budget !== null ? budget - retainedBudget : null} splitName={split?.name} onBid={refreshBudget} isMobile={isMobile} bidsByListing={bidsByListing} />}
        {tab === "mis-pujas" && <MyBidsTab  leagueId={leagueId} />}
        {tab === "ofertas"   && <OffersTab  leagueId={leagueId} />}
        {tab === "explorar"  && <ScoutTab   leagueId={leagueId} isMobile={isMobile} />}
      </main>

    </div>
  );
}

// ---------------------------------------------------------------------------
// Market tab
// ---------------------------------------------------------------------------
function MarketTab({
  leagueId,
  budget,
  availableBudget,
  splitName,
  onBid,
  isMobile,
  bidsByListing,
}: {
  leagueId: string;
  budget: number | null;
  availableBudget: number | null;
  splitName?: string;
  onBid: () => void;
  isMobile?: boolean;
  bidsByListing?: Map<string, number>;
}) {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [search, setSearch]     = useState("");
  const router = useRouter();
  const [popupListing, setPopupListing]         = useState<Listing | null>(null);
  const [popupExistingBid, setPopupExistingBid] = useState<number | null>(null);
  const [popupLoading, setPopupLoading]         = useState(false);
  const [popupError, setPopupError]             = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    api.market.listings(leagueId)
      .then(setListings)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  useEffect(() => { load(); }, [load]);

  const roles = ["all", "top", "jungle", "mid", "adc", "support"];
  const roleLabels: Record<string, string> = {
    all:     "TODOS",
    top:     "TOP",
    jungle:  "JGL",
    mid:     "MID",
    adc:     "ADC",
    support: "SUP",
  };

  const filtered = listings
    .filter((l) => roleFilter === "all" || l.players.role === roleFilter)
    .filter((l) => search === "" || l.players.name.toLowerCase().includes(search.toLowerCase()) || l.players.team.toLowerCase().includes(search.toLowerCase()));

  useGSAP(() => {
    gsap.from(".market-card", {
      autoAlpha: 0,
      y: 24,
      duration: 0.5,
      ease: "power2.out",
      stagger: 0.05,
    });
  }, { scope: gridRef, dependencies: [roleFilter, filtered.length] });

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
      {/* Search + role filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: "#555555" }}
            fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Buscar jugador o equipo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm outline-none transition-colors"
            style={{
              background: "#1A1A1A",
              border: "1px solid #2A2A2A",
              borderRadius: "8px",
              color: "#F0E8D0",
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          />
        </div>

        {/* Role select */}
        <div style={{ position: "relative", display: "inline-flex", alignItems: "stretch", width: "fit-content" }}>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            style={{
              appearance: "none",
              background: "#1A1A1A",
              border: "1px solid #2A2A2A",
              borderRadius: 8,
              padding: "8px 36px 8px 12px",
              color: "#F0E8D0",
              fontSize: 13,
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 600,
              cursor: "pointer",
              outline: "none",
            }}
          >
            {roles.map((r) => (
              <option key={r} value={r}>{roleLabels[r] ?? r.toUpperCase()}</option>
            ))}
          </select>
          <svg style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 4L6 8L10 4" stroke="#555555" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>

      <div ref={gridRef} className={isMobile ? "flex flex-col gap-3" : "flex flex-wrap gap-4"}>
        {filtered.map((l) => (
          <div key={l.id} className="market-card" style={isMobile ? { width: "100%" } : undefined}>
            <PlayerCard
              listing={l}
              leagueId={leagueId}
              budget={budget}
              splitName={splitName}
              isMobile={isMobile}
              existingBid={bidsByListing?.get(l.id)}
              onOpenPopup={() => { setPopupListing(l); setPopupExistingBid(bidsByListing?.get(l.id) ?? null); setPopupError(null); }}
              onOpenStats={() => router.push(`/leagues/${leagueId}/stats/${l.player_id}`)}
            />
          </div>
        ))}
      </div>

      {/* Bid popup */}
      {popupListing && (
        <ActionPopup
          isOpen={!!popupListing}
          onClose={() => { setPopupListing(null); setPopupExistingBid(null); setPopupError(null); }}
          title={popupExistingBid != null ? `Actualizar puja — ${popupListing.players.name}` : `Fichar a ${popupListing.players.name}`}
          playerName={popupListing.players.name}
          playerRole={popupListing.players.role}
          playerTeam={popupListing.players.team}
          playerImage={popupListing.players.image_url ?? undefined}
          mode="input"
          minAmount={popupListing.players.current_price}
          maxAmount={availableBudget !== null ? availableBudget + (popupExistingBid ?? 0) : undefined}
          existingBid={popupExistingBid ?? undefined}
          confirmLabel={popupExistingBid != null ? "Actualizar puja" : "Pujar"}
          previewText={(amount) => `Puja de ${amount.toFixed(1)}M`}
          onConfirm={async (amount) => {
            if (!amount) return;
            setPopupLoading(true);
            setPopupError(null);
            try {
              await api.bids.place(leagueId, popupListing.id, amount);
              setPopupListing(null);
              setPopupExistingBid(null);
              onBid();
              load();
            } catch (e) {
              setPopupError(e instanceof Error ? e.message : "Error al pujar");
            } finally {
              setPopupLoading(false);
            }
          }}
          isLoading={popupLoading}
          error={popupError}
        />
      )}

      {filtered.length === 0 && listings.length > 0 && (
        <div className="py-16 text-center">
          <p
            className="text-sm"
            style={{ fontFamily: "'Space Grotesk', sans-serif", color: "#555555" }}
          >
            Sin jugadores para este filtro.
          </p>
        </div>
      )}

    </div>
  );
}

// ---------------------------------------------------------------------------
// Player card — Paper B Premium style
// ---------------------------------------------------------------------------
function PlayerCard({
  listing,
  leagueId,
  budget,
  splitName,
  isMobile,
  onOpenPopup,
  onOpenStats,
  existingBid,
}: {
  listing: Listing;
  leagueId: string;
  budget: number | null;
  splitName?: string;
  isMobile?: boolean;
  onOpenPopup: () => void;
  onOpenStats: () => void;
  existingBid?: number;
}) {
  const [success, setSuccess]   = useState(false);

  const countdown = useCountdown(listing.closes_at);
  const closed    = countdown === "Cerrado";
  const p         = listing.players;

  const roleColorHex = getRoleColor(p.role);
  const hasBudget = budget !== null && budget >= listing.ask_price;

  // Initials fallback
  const initials = p.name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  // suppress unused warning
  void splitName;
  void leagueId;

  // ── MOBILE: horizontal card ──────────────────────────────────────────────
  if (isMobile) {
    const bidLabel = success
      ? "✓ Enviada"
      : closed
      ? "Cerrado"
      : existingBid != null && existingBid > 0
      ? `Pujar · ${existingBid.toFixed(1)}M`
      : `Pujar · ${listing.ask_price.toFixed(1)}M`;

    return (
      <div
        className="transition-all duration-150 active:scale-[0.99]"
        style={{
          width: "100%",
          borderRadius: "14px",
          border: success ? "1px solid rgba(34,197,94,0.4)" : "1px solid #222222",
          background: "#111111",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* TOP: photo + info */}
        <div style={{ display: "flex", flexDirection: "row" }}>
          {/* Photo — 72×96, rounded top-left */}
          <button
            type="button"
            onClick={onOpenStats}
            className="focus:outline-none flex-shrink-0 hover:brightness-75 transition-all duration-150"
            aria-label={`Ver estadísticas de ${p.name}`}
            style={{ width: 72, height: 96, position: "relative", background: roleColorHex, borderRadius: "10px 0 0 0", overflow: "hidden" }}
          >
            {p.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={p.image_url}
                alt={p.name}
                style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <span style={{ fontSize: "24px", fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif", color: "rgba(255,255,255,0.15)", letterSpacing: "0.05em" }}>
                  {initials}
                </span>
              </div>
            )}
            {/* Role color bar */}
            <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 3, background: roleColorHex, filter: "brightness(1.4)" }} />
            {success && (
              <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
                <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
            )}
          </button>

          {/* Info */}
          <div style={{ flex: 1, minWidth: 0, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 5 }}>
            <button type="button" onClick={onOpenStats} className="text-left focus:outline-none">
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 17, fontWeight: 700, color: "#F0E8D0", lineHeight: 1, letterSpacing: "-0.01em" }}>
                {p.name}
              </span>
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 6, paddingBottom: 2 }}>
              <span style={{ background: `${roleColorHex}30`, color: roleColorHex, fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 3, letterSpacing: "0.06em" }}>
                {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
              </span>
              <span style={{ fontSize: 11, color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}>{p.team}</span>
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 22, fontWeight: 700, color: "#FCD400", lineHeight: 1 }}>
                {p.split_points != null ? Math.round(p.split_points) : "—"}
              </span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 10, color: "#555555", fontWeight: 600 }}>pts</span>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, color: "#FCD400", marginLeft: "auto", display: "flex", alignItems: "baseline", gap: 6 }}>
                {p.current_price.toFixed(2)}M
                <PriceTrend changePct={p.last_price_change_pct ?? 0} />
              </span>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: "#1E1E1E", marginInline: 12 }} />

        {/* BOTTOM: timer + pujas + button */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px" }}>
          {/* Timer */}
          {listing.closes_at && !closed && countdown && (
            <div style={{ display: "flex", alignItems: "center", gap: 5, background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 7, padding: "6px 10px", flexShrink: 0 }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#888888" }}>{countdown}</span>
            </div>
          )}
          {closed && (
            <div style={{ display: "flex", alignItems: "center", background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 7, padding: "6px 10px", flexShrink: 0 }}>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#C62828" }}>Cerrado</span>
            </div>
          )}
          {/* Pujas count */}
          {(listing.bid_count ?? 0) > 0 && (
            <div style={{ display: "flex", alignItems: "center", background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 7, padding: "6px 10px", flexShrink: 0 }}>
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 11, fontWeight: 600, color: "#555555" }}>
                {listing.bid_count} {listing.bid_count === 1 ? "puja" : "pujas"}
              </span>
            </div>
          )}
          {/* Action button */}
          <Button
            variant={success ? "feedback-success" : hasBudget && !closed ? "primary" : "secondary"}
            onClick={() => { if (!closed) { setSuccess(false); onOpenPopup(); } }}
            disabled={closed}
            className="flex-1"
          >
            {bidLabel}
          </Button>
        </div>
      </div>
    );
  }

  // ── DESKTOP: vertical card ───────────────────────────────────────────────
  return (
    <div
      className="group relative flex flex-col overflow-hidden hover:-translate-y-1 transition-transform duration-150"
      style={{
        width: "200px",
        minHeight: "340px",
        borderRadius: "12px",
        border: success ? "1px solid rgba(34,197,94,0.4)" : "1px solid #222222",
        background: "#111111",
        overflow: "hidden",
      }}
    >
      {/* PHOTO ZONE — 180px */}
      <div
        style={{
          height: "180px",
          width: "100%",
          position: "relative",
          background: roleColorHex,
          flexShrink: 0,
        }}
      >
        <button
          type="button"
          onClick={onOpenStats}
          className="absolute inset-0 focus:outline-none hover:brightness-75 transition-all duration-150"
          aria-label={`Ver estadísticas de ${p.name}`}
        >
          {p.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={p.image_url}
              alt={p.name}
              className="w-full h-full"
              style={{ objectFit: "cover", objectPosition: "center top" }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span
                style={{
                  fontSize: "48px",
                  fontWeight: 700,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  color: "rgba(255,255,255,0.15)",
                  letterSpacing: "0.05em",
                }}
              >
                {initials}
              </span>
            </div>
          )}
        </button>

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

        {/* Success overlay */}
        {success && (
          <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}>
            <div className="text-green-400 text-center">
              <svg className="w-10 h-10 mx-auto mb-1" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <p className="text-xs font-semibold">Puja enviada</p>
            </div>
          </div>
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
              backgroundColor: roleColorHex,
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
        <button
          type="button"
          onClick={onOpenStats}
          className="text-left focus:outline-none"
        >
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
        </button>

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
            {p.split_points != null ? Math.round(p.split_points) : "—"}
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
              color: "#FCD400",
              marginLeft: "auto",
              display: "flex",
              alignItems: "baseline",
              gap: "4px",
            }}
          >
            {p.current_price.toFixed(2)}M
            <PriceTrend changePct={p.last_price_change_pct ?? 0} />
          </span>
        </div>

        {/* Fila 4 — chips row + button row */}
        <div style={{ marginTop: "auto", paddingTop: "6px", display: "flex", flexDirection: "column", gap: 6 }}>
          {/* Row 1: combined timer+pujas chip left, green bid chip right */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
            {/* Combined timer + pujas chip — left */}
            {listing.closes_at && !closed && countdown && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 20, padding: "4px 10px", flexShrink: 0 }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#888888" }}>{countdown}</span>
                {(listing.bid_count ?? 0) > 0 && (
                  <>
                    <div style={{ width: 1, height: 12, background: "#2A2A2A" }} />
                    <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 600, color: "#FCD400" }}>
                      {listing.bid_count} {listing.bid_count === 1 ? "puja" : "pujas"}
                    </span>
                  </>
                )}
              </div>
            )}
            {/* Closed chip — left */}
            {closed && (
              <div style={{ display: "flex", alignItems: "center", background: "#1A1A1A", border: "1px solid #2A2A2A", borderRadius: 20, padding: "4px 10px", flexShrink: 0 }}>
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 12, fontWeight: 700, color: "#C62828" }}>Cerrado</span>
              </div>
            )}
          </div>
          {/* Row 2: action button full width */}
          <Button
            variant={
              success
                ? "feedback-success"
                : (existingBid != null && existingBid > 0 && !closed)
                  ? "feedback-success"
                  : (hasBudget && !closed)
                    ? "primary"
                    : "secondary"
            }
            onClick={() => { if (!closed) { setSuccess(false); onOpenPopup(); } }}
            disabled={closed}
            fullWidth
          >
            {success ? "✓ Enviada" : closed ? "Cerrado" : existingBid != null && existingBid > 0 ? `Pujar · ${existingBid.toFixed(1)}M` : `Pujar · ${listing.ask_price.toFixed(1)}M`}
          </Button>
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
  const roleColorHex    = getRoleColor(bid.player_role);

  const handleCancel = async () => {
    setBusy(true);
    try { await api.bids.cancel(leagueId, bid.listing_id); onCancel(); }
    catch { /* ignore */ }
    finally { setBusy(false); }
  };

  return (
    <div
      className="flex items-center gap-3 sm:gap-4 rounded-xl px-4 py-3 transition-all duration-150"
      style={{
        background: "#111111",
        border: bid.status === "won"
          ? "1px solid rgba(34,197,94,0.3)"
          : "1px solid #1A1A1A",
      }}
    >
      <div
        className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
        style={{ background: roleColorHex + "33", border: `1px solid ${roleColorHex}44` }}
      >
        {bid.player_image_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={bid.player_image_url} alt={bid.player_name} className="w-full h-full object-cover object-top" />
          : (
            <span
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "14px",
                fontWeight: 700,
                color: roleColorHex,
              }}
            >
              {bid.player_name[0]?.toUpperCase()}
            </span>
          )
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="font-semibold text-sm truncate"
            style={{ color: "#F0E8D0", fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px" }}
          >
            {bid.player_name}
          </span>
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0"
            style={{
              background: roleColorHex + "22",
              color: roleColorHex,
              border: `1px solid ${roleColorHex}44`,
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          >
            {ROLE_LABEL[bid.player_role] ?? bid.player_role.toUpperCase()}
          </span>
        </div>
        <p
          className="text-xs"
          style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {bid.player_team}
        </p>
        {bid.status === "active" && bid.listing_closes_at && countdown && countdown !== "Cerrado" && (
          <p
            className="text-[10px] mt-0.5 font-mono"
            style={{ color: "#555555" }}
          >
            {countdown}
          </p>
        )}
      </div>
      <div className="text-right flex-shrink-0 mr-2">
        <p
          className="font-mono text-sm font-semibold"
          style={{ color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {bid.bid_amount.toFixed(1)}M
        </p>
        <p
          className="text-[10px]"
          style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          tu puja
        </p>
      </div>
      {bid.status === "won" && (
        <span
          className="px-2.5 py-1 text-xs font-bold rounded-lg flex-shrink-0"
          style={{
            color: "rgb(22,163,74)",
            background: "rgba(34,197,94,0.1)",
            border: "1px solid rgba(34,197,94,0.2)",
            fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          ✓ Ganada
        </span>
      )}
      {bid.status === "lost" && (
        <span
          className="px-2.5 py-1 text-xs font-bold rounded-lg flex-shrink-0"
          style={{
            color: "#555555",
            background: "#1A1A1A",
            border: "1px solid #2A2A2A",
            fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          ✗ Perdida
        </span>
      )}
      {bid.status === "cancelled" && (
        <span
          className="px-2.5 py-1 text-xs font-bold rounded-lg flex-shrink-0"
          style={{
            color: "#666666",
            background: "#161616",
            border: "1px solid #222222",
            fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          — Cancelada
        </span>
      )}
      {bid.status === "active" && (
        <Button
          variant="destructive"
          size="sm"
          onClick={handleCancel}
          disabled={busy || countdown === "Cerrado"}
          isLoading={busy}
          className="flex-shrink-0"
        >
          {busy ? "…" : "Cancelar"}
        </Button>
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
  const roleColorHex    = getRoleColor(offer.player.role);
  const expiresIn       = Math.ceil((new Date(offer.expires_at).getTime() - Date.now()) / 86_400_000);

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
      className="flex items-center gap-3 sm:gap-4 rounded-xl px-4 py-3 transition-all duration-150"
      style={{
        background: "#111111",
        border: "1px solid #1A1A1A",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#2A2A2A"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#1A1A1A"; }}
    >
      <div
        className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
        style={{ background: roleColorHex + "33", border: `1px solid ${roleColorHex}44` }}
      >
        {p.image_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover object-top" />
          : (
            <span
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "14px",
                fontWeight: 700,
                color: roleColorHex,
              }}
            >
              {p.name[0]?.toUpperCase()}
            </span>
          )
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="font-semibold truncate"
            style={{
              color: "#F0E8D0",
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: "16px",
            }}
          >
            {p.name}
          </span>
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0"
            style={{
              background: roleColorHex + "22",
              color: roleColorHex,
              border: `1px solid ${roleColorHex}44`,
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          >
            {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
          </span>
        </div>
        <p
          className="text-xs"
          style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {p.team}
        </p>
      </div>
      <div className="text-right flex-shrink-0 mr-1">
        <p
          className="font-mono text-sm font-semibold"
          style={{ color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {offer.ask_price.toFixed(1)}M
        </p>
        <p
          className="text-xs"
          style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          {expiresIn > 0 ? `${expiresIn}d` : "hoy"}
        </p>
        {offer.offer_type === "manager" ? (
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 10,
              fontWeight: 700,
              color: "#FCD400",
              background: "rgba(252,212,0,0.10)",
              border: "1px solid rgba(252,212,0,0.25)",
              borderRadius: 4,
              padding: "1px 5px",
              display: "inline-block",
              marginTop: 2,
            }}
          >
            Manager{offer.from_username ? ` · ${offer.from_username}` : ""}
          </span>
        ) : (
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 10,
              fontWeight: 600,
              color: "#555555",
              background: "#1A1A1A",
              border: "1px solid #2A2A2A",
              borderRadius: 4,
              padding: "1px 5px",
              display: "inline-block",
              marginTop: 2,
            }}
          >
            Liga
          </span>
        )}
      </div>
      {err && <span className="text-red-500 text-xs">{err}</span>}
      <div className="flex gap-2 flex-shrink-0">
        <Button
          variant="destructive"
          size="sm"
          onClick={() => handle("reject")}
          disabled={busy !== null}
          isLoading={busy === "reject"}
        >
          {busy === "reject" ? "…" : "Rechazar"}
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => handle("accept")}
          disabled={busy !== null}
          isLoading={busy === "accept"}
        >
          {busy === "accept" ? "…" : "Aceptar"}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scout tab
// ---------------------------------------------------------------------------
type SortField =
  | "total_points"
  | "current_price"
  | "kda"
  | "avg_kills"
  | "avg_deaths"
  | "avg_assists"
  | "avg_cs_per_min"
  | "avg_gold_diff_15"
  | "avg_xp_diff_15"
  | "avg_dpm"
  | "avg_vision_score";
type SortDir = "asc" | "desc";

function ScoutTab({ leagueId, isMobile }: { leagueId: string; isMobile?: boolean }) {
  const router = useRouter();
  const [players, setPlayers]           = useState<ScoutPlayer[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [filters, setFilters]           = useState<FilterDrawerFilters>({
    splitId: null,
    role: "all",
    team: "all",
    priceMin: 0,
    priceMax: undefined,
  });
  const [drawerOpen, setDrawerOpen]     = useState(false);
  const [sortField, setSortField]       = useState<SortField>("total_points");
  const [sortDir, setSortDir]           = useState<SortDir>("desc");
  const [animationKey, setAnimationKey] = useState(0);
  const [splits, setSplits]             = useState<Split[]>([]);
  const [splitInitializing, setSplitInitializing] = useState(true);

  // Cargar splits en el mount y pre-seleccionar el split activo
  useEffect(() => {
    api.splits.list().then((data) => {
      setSplits(data);
      const active = data.find((s) => s.is_active);
      setFilters(f => ({ ...f, splitId: active?.id ?? data[0]?.id ?? null }));
      setSplitInitializing(false);
    }).catch(() => { setSplitInitializing(false); /* no-op — filtro de split es opcional */ });
  }, []);

  const load = useCallback(() => {
    if (splitInitializing) return;
    setLoading(true);
    api.players.scout(leagueId, filters.splitId ?? undefined)
      .then((data) => { setPlayers(data); setAnimationKey((k) => k + 1); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId, filters.splitId, splitInitializing]);

  useEffect(() => { load(); }, [load]);

  const roleLabels: Record<string, string> = {
    all: "TODOS", top: "TOP", jungle: "JGL", mid: "MID", adc: "ADC", support: "SUP",
  };

  const teamsWithoutAll = Array.from(new Set(players.map((p) => p.team))).sort();

  const activeFilterCount = [
    splits.length > 0 && filters.splitId !== (splits[0]?.id ?? null),
    filters.role !== "all",
    filters.team !== "all",
    filters.priceMin !== 0 || filters.priceMax !== undefined,
  ].filter(Boolean).length;

  const kda = (p: ScoutPlayer) => p.total_deaths > 0
    ? (p.total_kills + p.total_assists) / p.total_deaths
    : p.total_kills + p.total_assists;

  const sortOptions: { value: SortField; label: string }[] = [
    { value: "total_points",     label: "Puntos totales" },
    { value: "current_price",    label: "Precio" },
    { value: "kda",              label: "KDA" },
    { value: "avg_kills",        label: "Kills" },
    { value: "avg_deaths",       label: "Deaths (menor)" },
    { value: "avg_assists",      label: "Assists" },
    { value: "avg_cs_per_min",   label: "CS/min" },
    { value: "avg_gold_diff_15", label: "Gold Diff @15" },
    { value: "avg_xp_diff_15",   label: "XP Diff @15" },
    { value: "avg_dpm",          label: "Daño/min" },
    { value: "avg_vision_score", label: "Vision Score" },
  ];

  const getSortValue = (p: ScoutPlayer): number => {
    if (sortField === "kda") return kda(p);
    if (sortField === "avg_deaths") return -p.avg_deaths; // menor es mejor → invertimos para que desc = mejores primero
    return p[sortField] as number;
  };

  const filtered = players
    .filter((p) => filters.role === "all" || p.role === filters.role)
    .filter((p) => filters.team === "all" || p.team === filters.team)
    .filter((p) => p.current_price >= filters.priceMin && (filters.priceMax === undefined || p.current_price <= filters.priceMax))
    .sort((a, b) => {
      const diff = getSortValue(a) - getSortValue(b);
      return sortDir === "desc" ? -diff : diff;
    });

  if (splitInitializing || loading) return <ListSkeleton rows={8} />;
  if (error)   return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      {/* Filtros */}
      <div className="flex flex-nowrap items-center gap-2 mb-4 overflow-x-auto">
        {/* Filtros button */}
        <button
          onClick={() => setDrawerOpen(true)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: activeFilterCount > 0 ? "#FCD400" : "#1A1A1A",
            border: `1px solid ${activeFilterCount > 0 ? "#FCD400" : "#2A2A2A"}`,
            borderRadius: 6,
            padding: "5px 12px",
            color: activeFilterCount > 0 ? "#000" : "#888888",
            fontSize: 11,
            fontWeight: activeFilterCount > 0 ? 700 : 500,
            cursor: "pointer",
            fontFamily: "'Space Grotesk', sans-serif",
            letterSpacing: "0.04em",
            flexShrink: 0,
          }}
        >
          FILTROS
          {activeFilterCount > 0 && (
            <span style={{
              background: activeFilterCount > 0 ? "#000" : "#FCD400",
              color: activeFilterCount > 0 ? "#FCD400" : "#000",
              borderRadius: "50%",
              width: 16,
              height: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 10,
              fontWeight: 700,
            }}>{activeFilterCount}</span>
          )}
        </button>

        {/* Sort controls */}
        <div className="flex items-center gap-1 ml-auto flex-shrink-0">
          <select
            value={sortField}
            onChange={(e) => { setSortField(e.target.value as SortField); setSortDir("desc"); setAnimationKey((k) => k + 1); }}
            className="outline-none"
            style={{
              background: "#1A1A1A",
              border: "1px solid #2A2A2A",
              borderRadius: "6px",
              color: "#888888",
              padding: "5px 6px",
              fontFamily: "'Space Grotesk', sans-serif",
              cursor: "pointer",
              fontSize: "11px",
            }}
          >
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value} style={{ background: "#1A1A1A" }}>
                {o.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => { setSortDir((d) => (d === "desc" ? "asc" : "desc")); setAnimationKey((k) => k + 1); }}
            className="transition-all active:scale-95 flex-shrink-0"
            style={{
              background: "#1A1A1A",
              border: "1px solid #2A2A2A",
              borderRadius: "6px",
              padding: "5px 7px",
              color: "#888888",
              fontSize: "12px",
              fontFamily: "'Space Grotesk', sans-serif",
              cursor: "pointer",
            }}
            title={sortDir === "desc" ? "Descendente" : "Ascendente"}
          >
            {sortDir === "desc" ? "↓" : "↑"}
          </button>
        </div>
      </div>

      {/* Tabla */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center">
          <p style={{ fontFamily: "'Space Grotesk', sans-serif", color: "#555555", fontSize: "14px" }}>
            Sin jugadores para este filtro.
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          {/* Header */}
          <div
            className="flex items-center px-4 py-1.5"
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "10px",
              fontWeight: 700,
              color: "#333333",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            <span style={{ flex: 1 }}>Jugador</span>
          </div>

          {filtered.map((p, index) => (
            <ScoutRow
              key={`${animationKey}-${p.id}`}
              player={p}
              animationDelay={index * 60}
              onOpen={() => router.push(`/leagues/${leagueId}/stats/${p.id}?from=scout`)}
            />
          ))}
        </div>
      )}

      <FilterDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onApply={(f) => {
          setFilters(f);
          setDrawerOpen(false);
          setAnimationKey((k) => k + 1);
        }}
        committed={filters}
        splits={splits}
        teams={teamsWithoutAll}
        roleLabels={roleLabels}
        isMobile={isMobile ?? false}
      />

    </div>
  );
}

function ScoutRow({ player: p, animationDelay, onOpen }: { player: ScoutPlayer; animationDelay: number; onOpen: () => void }) {
  const roleColorHex = getRoleColor(p.role);
  const kdaVal = p.total_deaths > 0
    ? (p.total_kills + p.total_assists) / p.total_deaths
    : p.total_kills + p.total_assists;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full text-left group animate-cascade-in active:scale-[0.98] transition-all duration-150"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      <div
        className="flex items-center gap-2 sm:gap-4 px-2 sm:px-4 py-3 rounded-xl transition-all duration-150"
        style={{
          background: "#111111",
          border: "1px solid #1A1A1A",
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#2A2A2A"; (e.currentTarget as HTMLDivElement).style.background = "#141414"; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "#1A1A1A"; (e.currentTarget as HTMLDivElement).style.background = "#111111"; }}
      >
        {/* Foto grande */}
        <div
          className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 flex items-center justify-center"
          style={{ background: roleColorHex + "22", border: `1px solid ${roleColorHex}33` }}
        >
          {p.image_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover object-top" />
            : (
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "22px", fontWeight: 700, color: roleColorHex }}>
                {p.name[0]?.toUpperCase()}
              </span>
            )
          }
        </div>

        {/* Nombre + equipo + badges */}
        <div className="min-w-0 flex-1 overflow-hidden">
          {/* Fila 1: nombre + badges */}
          <div className="flex items-center gap-1 min-w-0 overflow-hidden">
            <span
              className="truncate"
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "16px",
                fontWeight: 700,
                color: "#F0E8D0",
                lineHeight: 1.2,
              }}
            >
              {p.name}
            </span>
            {/* Rol badge */}
            <span
              className="text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0"
              style={{
                background: roleColorHex + "22",
                color: roleColorHex,
                border: `1px solid ${roleColorHex}44`,
                fontFamily: "'Space Grotesk', sans-serif",
                letterSpacing: "0.05em",
              }}
            >
              {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
            </span>
            {/* Owner badge */}
            {p.owner_name && (
              <span
                className="text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0"
                style={{
                  background: "#1F2A1A",
                  color: "#7DBF5A",
                  border: "1px solid #3A5A2A",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
              >
                @{p.owner_name}
              </span>
            )}
            {/* Clause badge */}
            {p.owner_name && p.clause_amount != null && p.clause_expires_at != null && new Date(p.clause_expires_at).getTime() > Date.now() && (
              <span
                className="text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0"
                style={{
                  background: "#2A2000",
                  color: "#FCD400",
                  border: "1px solid #4A3A00",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
              >
                🔒 {p.clause_amount.toFixed(0)}M
              </span>
            )}
            {/* EN VENTA badge */}
            {p.for_sale && (
              <span
                className="text-[10px] font-semibold px-1.5 py-0.5 flex-shrink-0"
                style={{
                  background: "rgba(252,212,0,0.12)",
                  border: "1px solid rgba(252,212,0,0.3)",
                  color: "#FCD400",
                  fontSize: 10,
                  borderRadius: 4,
                  padding: "2px 6px",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
              >
                EN VENTA
              </span>
            )}
          </div>
          {/* Fila 2: equipo */}
          <div className="flex items-center gap-1.5 mt-1 min-w-0">
            <div className="flex-shrink-0 flex items-center justify-center" style={{ width: 14, height: 14 }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={getTeamBadgeUrl(p.team)}
                alt={p.team}
                style={{ width: 14, height: 14, objectFit: "contain" }}
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  (e.currentTarget.nextSibling as HTMLElement)?.style.setProperty("display", "flex");
                }}
              />
              <span style={{ display: "none", fontSize: "8px", color: "#C8A84B", fontWeight: 700 }}>
                {p.team.substring(0, 2).toUpperCase()}
              </span>
            </div>
            <span
              className="truncate hidden sm:inline"
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "12px",
                color: "#555555",
              }}
            >
              {p.team}
            </span>
            <span className="flex-shrink-0" style={{ color: "#2A2A2A", fontSize: "11px" }}>·</span>
            <span
              className="flex-shrink-0 whitespace-nowrap"
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "12px",
                color: "#444444",
                display: "inline-flex",
                alignItems: "baseline",
                gap: 10,
              }}
            >
              {p.current_price.toFixed(2)}M
              {p.last_price_change_pct !== 0 && (
                <PriceTrend changePct={p.last_price_change_pct ?? 0} />
              )}
            </span>
          </div>
        </div>

        {/* Stats grid — mobile: solo PTS, KDA, CS/m + "Ver más"; desktop: 5 cols completas */}
        <div className="flex items-center gap-1 sm:gap-0 flex-shrink-0">
          {/* Mobile: 3 stats visibles */}
          <div className="grid grid-cols-3 gap-x-1 sm:hidden">
            {/* PTS */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>PTS</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#FCD400", lineHeight: 1 }}>
                {p.total_points > 0 ? Math.round(p.total_points) : "—"}
              </span>
            </div>
            {/* KDA */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>KDA</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {kdaVal.toFixed(1)}
              </span>
            </div>
            {/* CS/m */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>CS/m</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_cs_per_min > 0 ? p.avg_cs_per_min.toFixed(1) : "—"}
              </span>
            </div>
          </div>

          {/* Desktop: grid completo con todas las stats */}
          <div className="hidden sm:grid sm:grid-cols-5 gap-x-3 gap-y-1 flex-shrink-0">
            {/* PTS */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>PTS</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#FCD400", lineHeight: 1 }}>
                {p.total_points > 0 ? Math.round(p.total_points) : "—"}
              </span>
            </div>
            {/* KDA */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>KDA</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {kdaVal.toFixed(1)}
              </span>
            </div>
            {/* Kills */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>Kills</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_kills > 0 ? p.avg_kills.toFixed(1) : "—"}
              </span>
            </div>
            {/* Muertes */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>Muertes</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: p.avg_deaths > 3 ? "#f87171" : "#F0E8D0", lineHeight: 1 }}>
                {p.avg_deaths > 0 ? p.avg_deaths.toFixed(1) : "—"}
              </span>
            </div>
            {/* Asist */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>Asist</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_assists > 0 ? p.avg_assists.toFixed(1) : "—"}
              </span>
            </div>
            {/* CS/m */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>CS/m</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_cs_per_min > 0 ? p.avg_cs_per_min.toFixed(1) : "—"}
              </span>
            </div>
            {/* GD15 */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>GD15</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: p.avg_gold_diff_15 > 0 ? "#4ade80" : p.avg_gold_diff_15 < 0 ? "#f87171" : "#F0E8D0", lineHeight: 1 }}>
                {p.avg_gold_diff_15 !== 0
                  ? (p.avg_gold_diff_15 > 0 ? "+" : "") + Math.round(p.avg_gold_diff_15)
                  : "—"}
              </span>
            </div>
            {/* XPD15 */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>XPD15</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: p.avg_xp_diff_15 > 0 ? "#4ade80" : p.avg_xp_diff_15 < 0 ? "#f87171" : "#F0E8D0", lineHeight: 1 }}>
                {p.avg_xp_diff_15 !== 0
                  ? (p.avg_xp_diff_15 > 0 ? "+" : "") + Math.round(p.avg_xp_diff_15)
                  : "—"}
              </span>
            </div>
            {/* DPM */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>DPM</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_dpm > 0 ? Math.round(p.avg_dpm) : "—"}
              </span>
            </div>
            {/* Visión */}
            <div className="flex flex-col items-center justify-center">
              <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "10px", fontWeight: 700, color: "#555555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1px" }}>Visión</span>
              <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: "16px", fontWeight: 700, color: "#F0E8D0", lineHeight: 1 }}>
                {p.avg_vision_score > 0 ? Math.round(p.avg_vision_score) : "—"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </button>
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
        style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}
      >
        <svg
          className="w-7 h-7"
          style={{ color: "#333333" }}
          fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
      </div>
      <p
        className="font-semibold mb-2"
        style={{ color: "#F0E8D0", fontFamily: "'Space Grotesk', sans-serif" }}
      >
        {title}
      </p>
      <p
        className="text-sm max-w-sm mx-auto"
        style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}
      >
        {description}
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="py-20 text-center">
      <p className="text-sm mb-4" style={{ color: "#555555", fontFamily: "'Space Grotesk', sans-serif" }}>
        {message}
      </p>
      <Button variant="secondary" onClick={onRetry}>
        Reintentar
      </Button>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl overflow-hidden animate-pulse"
          style={{ background: "#111111", border: "1px solid #1A1A1A" }}
        >
          <div className="w-full" style={{ height: "130px", background: "#1A1A1A" }} />
          <div className="p-3 space-y-2">
            <div className="h-4 rounded w-3/4" style={{ background: "#1A1A1A" }} />
            <div className="h-3 rounded w-1/2" style={{ background: "#1A1A1A" }} />
            <div className="h-7 rounded mt-2" style={{ background: "#1A1A1A" }} />
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
          style={{ background: "#111111", border: "1px solid #1A1A1A" }}
        />
      ))}
    </div>
  );
}

"use client";

import { useEffect, useState, useMemo } from "react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { api, type TeamStandingEntry, type TeamStandingsOut, type Split } from "@/lib/api";

const TEAM_LOGO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

function teamLogoUrl(name: string, logo_url: string | null): string {
  if (logo_url) return logo_url;
  return TEAM_LOGO_BASE + name.toLowerCase().replace(/ /g, "-") + ".webp";
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmt(value: number | null, decimals = 2): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

function fmtGold(value: number | null): string {
  if (value == null) return "—";
  const v = Math.round(value);
  return v >= 0 ? `+${v}` : String(v);
}

function fmtPct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

// ---------------------------------------------------------------------------
// Skeleton rows
// ---------------------------------------------------------------------------
function SkeletonRows() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse"
          style={{
            height: 56,
            borderRadius: 10,
            background: "#1A1A1A",
            border: "1px solid #2A2A2A",
          }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playoff bracket row styling
// ---------------------------------------------------------------------------
function getPlayoffRowStyle(pos: number): React.CSSProperties {
  const green = "#22C55E";
  const yellow = "#EAB308";
  const red = "#EF4444";
  const borderWidth = 3;

  if (pos === 1) return { borderLeft: `${borderWidth}px solid ${green}`, borderTop: `1px solid ${green}`, borderTopLeftRadius: 6 };
  if (pos >= 2 && pos <= 3) return { borderLeft: `${borderWidth}px solid ${green}` };
  if (pos === 4) return { borderLeft: `${borderWidth}px solid ${green}`, borderBottom: `1px solid ${green}`, borderBottomLeftRadius: 6 };
  if (pos === 5) return { borderLeft: `${borderWidth}px solid ${yellow}`, borderTop: `1px solid ${yellow}`, borderTopLeftRadius: 6 };
  if (pos === 6) return { borderLeft: `${borderWidth}px solid ${yellow}`, borderBottom: `1px solid ${yellow}`, borderBottomLeftRadius: 6 };
  return { borderLeft: `${borderWidth}px solid ${red}` };
}

// ---------------------------------------------------------------------------
// Team row
// ---------------------------------------------------------------------------
function TeamRow({
  entry,
  pos,
  animationDelay,
}: {
  entry: TeamStandingEntry;
  pos: number;
  animationDelay: number;
}) {
  const isFirst = pos === 1;

  const posBadgeStyle: React.CSSProperties = isFirst
    ? { width: 24, height: 24, borderRadius: 6, background: "#FCD400", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }
    : { width: 24, height: 24, borderRadius: 6, background: "#2A2A2A", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 };

  const posNumStyle: React.CSSProperties = {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: 13, fontWeight: 700,
    color: isFirst ? "#111111" : "#555555",
  };

  const rowStyle: React.CSSProperties = {
    background: "#1A1A1A",
    border: "1px solid #2A2A2A",
    borderRadius: 10,
    padding: "0 20px",
    height: 56,
    display: "flex",
    alignItems: "center",
    gap: 12,
    animationDelay: `${animationDelay}ms`,
    ...getPlayoffRowStyle(pos),
  };

  const wl = entry.wins + entry.losses;
  const goldDiff = entry.avg_gold_diff_15;

  return (
    <div className="animate-cascade-in" style={rowStyle}>
      {/* POS — 40px */}
      <div style={{ width: 40, display: "flex", alignItems: "center", justifyContent: "flex-start", flexShrink: 0 }}>
        <div style={posBadgeStyle}>
          <span style={posNumStyle}>{pos}</span>
        </div>
      </div>

      {/* EQUIPO — flex-grow */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 10 }}>
        <Image
          src={teamLogoUrl(entry.team_name, entry.logo_url)}
          alt={entry.team_name}
          width={32}
          height={32}
          onError={(e) => { e.currentTarget.style.display = "none"; }}
          style={{ borderRadius: "50%", objectFit: "contain", background: "#1A1A1A", flexShrink: 0 }}
        />
        <span style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 14, fontWeight: 700,
          color: isFirst ? "#F0E8D0" : "#888888",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {entry.team_name}
        </span>
      </div>

      {/* W */}
      <div style={{ width: 28, flexShrink: 0, textAlign: "center" }}>
        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, color: "#22C55E" }}>
          {entry.wins}
        </span>
      </div>

      {/* L */}
      <div style={{ width: 28, flexShrink: 0, textAlign: "center" }}>
        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, color: "#EF4444" }}>
          {entry.losses}
        </span>
      </div>

      {/* W% */}
      <div style={{ width: 48, flexShrink: 0, textAlign: "center" }}>
        <span style={{ fontSize: 12, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, color: wl === 0 ? "#555555" : "#888888" }}>
          {wl === 0 ? "—" : fmtPct(entry.win_rate)}
        </span>
      </div>

      {/* GW — desktop only */}
      <div style={{ width: 28, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, color: "#22C55E" }}>
          {entry.game_wins}
        </span>
      </div>

      {/* GL — desktop only */}
      <div style={{ width: 28, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        <span style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, color: "#EF4444" }}>
          {entry.game_losses}
        </span>
      </div>

      {/* KDA — desktop only */}
      <div style={{ width: 56, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        <span style={{ fontSize: 12, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600, color: entry.avg_kda == null ? "#555555" : "#888888" }}>
          {fmt(entry.avg_kda, 2)}
        </span>
      </div>

      {/* GOLD@15 — desktop only */}
      <div style={{ width: 72, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        {entry.avg_gold_diff_15 == null ? (
          <span style={{ color: "#555555", fontSize: 12 }}>—</span>
        ) : (
          <span style={{
            fontSize: 12, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600,
            color: goldDiff != null && goldDiff >= 0 ? "#22C55E" : "#EF4444",
          }}>
            {fmtGold(entry.avg_gold_diff_15)}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Playoff legend
// ---------------------------------------------------------------------------
const LEGEND_ITEMS = [
  { color: "#22C55E", label: "Winner Bracket (1-4)" },
  { color: "#EAB308", label: "Lower Bracket (5-6)" },
  { color: "#EF4444", label: "Eliminado (7+)" },
];

function PlayoffLegend() {
  return (
    <div style={{ display: "flex", gap: 16, paddingInline: 4, flexWrap: "wrap" }}>
      {LEGEND_ITEMS.map(({ color, label }) => (
        <div key={color} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: color, flexShrink: 0 }} />
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 10, color: "#555555" }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function TeamsPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const [data, setData] = useState<TeamStandingsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [animationKey, setAnimationKey] = useState(0);
  const [splits, setSplits] = useState<Split[]>([]);
  const [selectedCompetitionId, setSelectedCompetitionId] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.splits
      .list()
      .then((splitList) => {
        if (cancelled) return;
        setSplits(splitList);
        const activeSplit = splitList.find((s) => s.is_active);
        const defaultId = activeSplit?.id ?? splitList[0]?.id ?? null;
        setSelectedCompetitionId(defaultId);
        setInitializing(false);
      })
      .catch((e: Error) => {
        if (!cancelled) { setError(e.message); setInitializing(false); }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (selectedCompetitionId === null || initializing) return;
    setLoading(true);
    setError(null);
    api.teams
      .standings(leagueId, selectedCompetitionId)
      .then((d) => { setData(d); setAnimationKey((k) => k + 1); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId, selectedCompetitionId, initializing]);

  const sortedEntries = useMemo(() => {
    if (!data) return [];
    return [...data.entries].sort((a, b) => b.wins - a.wins || b.win_rate - a.win_rate);
  }, [data]);

  const headerLabelStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 10, fontWeight: 600,
    letterSpacing: "0.08em",
    color: "#333333",
    textTransform: "uppercase",
  };

  return (
    <div className="min-h-[100dvh]" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">

        {/* Page header */}
        <div style={{ marginBottom: 28 }}>
          {data && (
            <p style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 10, fontWeight: 700,
              letterSpacing: "0.1em", color: "#333333",
              textTransform: "uppercase", marginBottom: 4,
            }}>
              {data.competition_name}
            </p>
          )}
          <h1 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 30, fontWeight: 700,
            color: "#F0E8D0", lineHeight: 1.1,
          }}>
            Equipos
          </h1>
        </div>

        {/* Competition selector */}
        {splits.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{ position: "relative", display: "inline-block" }}>
              <select
                value={selectedCompetitionId ?? ""}
                onChange={(e) => setSelectedCompetitionId(e.target.value)}
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
                {splits.map((split) => (
                  <option key={split.id} value={split.id}>{split.name}</option>
                ))}
              </select>
              <svg
                style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
                width="12" height="12" viewBox="0 0 12 12" fill="none"
              >
                <path d="M2 4L6 8L10 4" stroke="#555555" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {(initializing || loading) && <SkeletonRows />}

        {/* Error */}
        {error && (
          <p className="text-sm text-center py-20" style={{ color: "var(--text-muted)" }}>
            {error}
          </p>
        )}

        {/* Empty state */}
        {!loading && !error && (!data || data.entries.length === 0) && (
          <div className="py-20 text-center">
            <p style={{ color: "#888888", fontWeight: 500 }}>No hay datos disponibles</p>
            <p className="text-sm mt-2" style={{ color: "#555555" }}>
              Los datos se actualizan tras cada jornada de LEC.
            </p>
          </div>
        )}

        {/* Table */}
        {!loading && !error && data && data.entries.length > 0 && (
          <div>
            {/* Legend — mobile: above headers | desktop: after headers */}
            <div className="sm:hidden" style={{ marginBottom: 12 }}>
              <PlayoffLegend />
            </div>

            {/* Table header — two rows */}
            <div style={{ paddingInline: 20, marginBottom: 8 }}>
              {/* Row 1 — group labels */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 2 }}>
                <div style={{ width: 40, flexShrink: 0 }} />
                <div style={{ flex: 1 }} />
                <div style={{ width: 128, flexShrink: 0, textAlign: "center" }}>
                  <span style={{ ...headerLabelStyle, color: "#555555" }}>BO</span>
                </div>
                <div style={{ width: 68, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                  <span style={{ ...headerLabelStyle, color: "#555555" }}>GAMES</span>
                </div>
                <div style={{ width: 56, flexShrink: 0 }} className="hidden sm:block" />
                <div style={{ width: 72, flexShrink: 0 }} className="hidden sm:block" />
              </div>

              {/* Row 2 — column labels */}
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 40, flexShrink: 0 }}>
                  <span style={headerLabelStyle}>POS</span>
                </div>
                <div style={{ flex: 1 }}>
                  <span style={headerLabelStyle}>EQUIPO</span>
                </div>
                <div style={{ width: 28, flexShrink: 0, textAlign: "center" }}>
                  <span style={headerLabelStyle}>W</span>
                </div>
                <div style={{ width: 28, flexShrink: 0, textAlign: "center" }}>
                  <span style={headerLabelStyle}>L</span>
                </div>
                <div style={{ width: 48, flexShrink: 0, textAlign: "center" }}>
                  <span style={headerLabelStyle}>W%</span>
                </div>
                <div style={{ width: 28, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                  <span style={headerLabelStyle}>GW</span>
                </div>
                <div style={{ width: 28, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                  <span style={headerLabelStyle}>GL</span>
                </div>
                <div style={{ width: 56, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                  <span style={headerLabelStyle}>KDA</span>
                </div>
                <div style={{ width: 72, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                  <span style={headerLabelStyle}>GOLD@15</span>
                </div>
              </div>
            </div>

            {/* Legend — desktop: after headers */}
            <div className="hidden sm:block" style={{ marginBottom: 16 }}>
              <PlayoffLegend />
            </div>

            {/* Rows */}
            <div key={animationKey} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {sortedEntries.map((entry, index) => (
                <TeamRow
                  key={entry.team_id}
                  entry={entry}
                  pos={index + 1}
                  animationDelay={index * 60}
                />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { api, type TeamStandingEntry, type TeamStandingsOut, type Split } from "@/lib/api";

// ---------------------------------------------------------------------------
// Sort types
// ---------------------------------------------------------------------------
type SortKey = "wins" | "avg_kda" | "avg_gold_diff_15" | "avg_dpm" | "avg_cs_per_min";

const SORT_PILLS: { key: SortKey; label: string }[] = [
  { key: "wins", label: "Resultados" },
  { key: "avg_kda", label: "KDA" },
  { key: "avg_gold_diff_15", label: "Gold @15" },
  { key: "avg_dpm", label: "DPM" },
  { key: "avg_cs_per_min", label: "CS/min" },
];

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
// Team row
// ---------------------------------------------------------------------------
function TeamRow({
  entry,
  pos,
  animationDelay,
  activeSort,
}: {
  entry: TeamStandingEntry;
  pos: number;
  animationDelay: number;
  activeSort: SortKey;
}) {
  const isFirst = pos === 1;

  const posBadgeStyle: React.CSSProperties = isFirst
    ? {
        width: 24,
        height: 24,
        borderRadius: 6,
        background: "#FCD400",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }
    : {
        width: 24,
        height: 24,
        borderRadius: 6,
        background: "#2A2A2A",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      };

  const posNumStyle: React.CSSProperties = {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: 13,
    fontWeight: 700,
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
        <img
          src={teamLogoUrl(entry.team_name, entry.logo_url)}
          alt={entry.team_name}
          onError={(e) => { e.currentTarget.style.display = "none"; }}
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            objectFit: "contain",
            background: "#1A1A1A",
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 14,
            fontWeight: 700,
            color: isFirst ? "#F0E8D0" : "#888888",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {entry.team_name}
        </span>
        {(entry.wins > 0 || entry.losses > 0) && (
          <span style={{ fontSize: 11, color: "#444444", flexShrink: 0 }}>
            {entry.wins}W {entry.losses}L
          </span>
        )}
      </div>

      {/* W */}
      <div style={{ width: 36, flexShrink: 0, textAlign: "center" }}>
        <span style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 16,
          fontWeight: 700,
          color: activeSort === "wins" ? "#FCD400" : "#22C55E",
        }}>
          {entry.wins}
        </span>
      </div>

      {/* L */}
      <div style={{ width: 36, flexShrink: 0, textAlign: "center" }}>
        <span style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 16,
          fontWeight: 700,
          color: "#EF4444",
        }}>
          {entry.losses}
        </span>
      </div>

      {/* W% */}
      <div style={{ width: 48, flexShrink: 0, textAlign: "center" }}>
        <span style={{
          fontSize: 12,
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600,
          color: wl === 0 ? "#555555" : "#888888",
        }}>
          {wl === 0 ? "—" : fmtPct(entry.win_rate)}
        </span>
      </div>

      {/* KDA */}
      <div style={{ width: 56, flexShrink: 0, textAlign: "center" }}>
        <span style={{
          fontSize: 12,
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600,
          color: activeSort === "avg_kda" && entry.avg_kda != null ? "#FCD400" : entry.avg_kda == null ? "#555555" : "#888888",
        }}>
          {fmt(entry.avg_kda, 2)}
        </span>
      </div>

      {/* GOLD@15 — desktop only */}
      <div style={{ width: 72, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        {entry.avg_gold_diff_15 == null ? (
          <span style={{ color: "#555555", fontSize: 12 }}>—</span>
        ) : (
          <span style={{
            fontSize: 12,
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 600,
            color: activeSort === "avg_gold_diff_15"
              ? "#FCD400"
              : goldDiff != null && goldDiff >= 0 ? "#22C55E" : "#EF4444",
          }}>
            {fmtGold(entry.avg_gold_diff_15)}
          </span>
        )}
      </div>

      {/* DPM — desktop only */}
      <div style={{ width: 60, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        <span style={{
          fontSize: 12,
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600,
          color: activeSort === "avg_dpm" && entry.avg_dpm != null ? "#FCD400" : entry.avg_dpm == null ? "#555555" : "#888888",
        }}>
          {entry.avg_dpm != null ? Math.round(entry.avg_dpm).toLocaleString() : "—"}
        </span>
      </div>

      {/* CS/MIN — desktop only */}
      <div style={{ width: 60, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
        <span style={{
          fontSize: 12,
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 600,
          color: activeSort === "avg_cs_per_min" && entry.avg_cs_per_min != null ? "#FCD400" : entry.avg_cs_per_min == null ? "#555555" : "#888888",
        }}>
          {fmt(entry.avg_cs_per_min, 1)}
        </span>
      </div>
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
  const [sortKey, setSortKey] = useState<SortKey>("wins");
  const [animationKey, setAnimationKey] = useState(0);
  const [splits, setSplits] = useState<Split[]>([]);
  const [selectedCompetitionId, setSelectedCompetitionId] = useState<string | null>(null);

  // On mount: load splits and default to the active one
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
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Fetch standings whenever leagueId or selectedCompetitionId changes
  useEffect(() => {
    if (selectedCompetitionId === null) return;
    setLoading(true);
    setError(null);
    api.teams
      .standings(leagueId, selectedCompetitionId)
      .then((d) => { setData(d); setAnimationKey((k) => k + 1); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId, selectedCompetitionId]);

  const sortedEntries = useMemo(() => {
    if (!data) return [];
    const entries = [...data.entries];
    if (sortKey === "wins") {
      return entries.sort((a, b) => b.wins - a.wins || b.win_rate - a.win_rate);
    }
    return entries.sort((a, b) => {
      const va = a[sortKey] ?? -Infinity;
      const vb = b[sortKey] ?? -Infinity;
      return (vb as number) - (va as number);
    });
  }, [data, sortKey]);

  function handleSort(key: SortKey) {
    setSortKey(key);
    setAnimationKey((k) => k + 1);
  }

  const headerLabelStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.08em",
    color: "#333333",
    textTransform: "uppercase",
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">

        {/* Page header */}
        <div style={{ marginBottom: 28 }}>
          {data && (
            <p style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.1em",
              color: "#333333",
              textTransform: "uppercase",
              marginBottom: 4,
            }}>
              {data.competition_name}
            </p>
          )}
          <h1 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 30,
            fontWeight: 700,
            color: "#F0E8D0",
            lineHeight: 1.1,
          }}>
            Equipos
          </h1>
        </div>

        {/* Split selector */}
        {splits.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
            {splits.map((split) => {
              const isActive = split.id === selectedCompetitionId;
              return (
                <button
                  key={split.id}
                  onClick={() => {
                    setSelectedCompetitionId(split.id);
                    setSortKey("wins");
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
                  }}
                >
                  {split.name}
                </button>
              );
            })}
          </div>
        )}

        {/* Sort pills */}
        {!loading && !error && data && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
            {SORT_PILLS.map(({ key, label }) => {
              const isActive = sortKey === key;
              return (
                <button
                  key={key}
                  onClick={() => handleSort(key)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 20,
                    border: isActive ? "1px solid rgba(252,212,0,0.5)" : "1px solid #2A2A2A",
                    background: isActive ? "rgba(252,212,0,0.12)" : "#1A1A1A",
                    color: isActive ? "#FCD400" : "#555555",
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 150ms ease",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && <SkeletonRows />}

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
            {/* Table header */}
            <div style={{
              display: "flex",
              alignItems: "center",
              paddingInline: 20,
              marginBottom: 8,
              gap: 12,
            }}>
              <div style={{ width: 40, flexShrink: 0 }}>
                <span style={headerLabelStyle}>POS</span>
              </div>
              <div style={{ flex: 1 }}>
                <span style={headerLabelStyle}>EQUIPO</span>
              </div>
              <div style={{ width: 36, flexShrink: 0, textAlign: "center" }}>
                <span style={headerLabelStyle}>W</span>
              </div>
              <div style={{ width: 36, flexShrink: 0, textAlign: "center" }}>
                <span style={headerLabelStyle}>L</span>
              </div>
              <div style={{ width: 48, flexShrink: 0, textAlign: "center" }}>
                <span style={headerLabelStyle}>W%</span>
              </div>
              <div style={{ width: 56, flexShrink: 0, textAlign: "center" }}>
                <span style={{ ...headerLabelStyle, color: sortKey === "avg_kda" ? "#FCD400" : "#333333" }}>KDA</span>
              </div>
              <div style={{ width: 72, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                <span style={{ ...headerLabelStyle, color: sortKey === "avg_gold_diff_15" ? "#FCD400" : "#333333" }}>GOLD@15</span>
              </div>
              <div style={{ width: 60, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                <span style={{ ...headerLabelStyle, color: sortKey === "avg_dpm" ? "#FCD400" : "#333333" }}>DPM</span>
              </div>
              <div style={{ width: 60, flexShrink: 0, textAlign: "center" }} className="hidden sm:block">
                <span style={{ ...headerLabelStyle, color: sortKey === "avg_cs_per_min" ? "#FCD400" : "#333333" }}>CS/MIN</span>
              </div>
            </div>

            {/* Rows — animationKey forces cascade restart on sort */}
            <div key={animationKey} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {sortedEntries.map((entry, index) => (
                <TeamRow
                  key={entry.team_id}
                  entry={entry}
                  pos={index + 1}
                  animationDelay={index * 60}
                  activeSort={sortKey}
                />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

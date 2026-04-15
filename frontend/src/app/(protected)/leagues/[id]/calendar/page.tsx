"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type SeriesCalendarEntry, type CalendarResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEAM_LOGO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

function teamLogoUrl(name: string): string {
  return `${TEAM_LOGO_BASE}${name.toLowerCase().replace(/ /g, "-")}.webp`;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function groupByWeek(
  series: SeriesCalendarEntry[]
): Array<{ week: number | null; label: string; matches: SeriesCalendarEntry[] }> {
  const map = new Map<string, SeriesCalendarEntry[]>();
  for (const s of series) {
    const key = s.week != null ? String(s.week) : "sin-semana";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(s);
  }
  const result: Array<{ week: number | null; label: string; matches: SeriesCalendarEntry[] }> = [];
  for (const [key, matches] of Array.from(map.entries())) {
    const week = key === "sin-semana" ? null : Number(key);
    result.push({
      week,
      label: week != null ? `SEMANA ${week}` : "SIN SEMANA",
      matches,
    });
  }
  return result;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status, result }: { status: string; result: string | null }) {
  if (status === "finished" && result) {
    return (
      <span
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 16,
          fontWeight: 700,
          color: "#F0E8D0",
          minWidth: 36,
          textAlign: "center",
          letterSpacing: "0.04em",
        }}
      >
        {result}
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          minWidth: 64,
          justifyContent: "center",
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#FCD400",
            animation: "pulse 1.5s ease-in-out infinite",
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 11,
            fontWeight: 700,
            color: "#FCD400",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          EN CURSO
        </span>
      </span>
    );
  }
  // scheduled
  return (
    <span
      style={{
        fontFamily: "'Barlow Condensed', sans-serif",
        fontSize: 16,
        fontWeight: 700,
        color: "#555555",
        minWidth: 36,
        textAlign: "center",
        letterSpacing: "0.04em",
      }}
    >
      - -
    </span>
  );
}

// ---------------------------------------------------------------------------
// Team display
// ---------------------------------------------------------------------------

function TeamDisplay({
  name,
  align,
}: {
  name: string;
  align: "left" | "right";
}) {
  const isLeft = align === "left";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        flex: 1,
        flexDirection: isLeft ? "row" : "row-reverse",
        minWidth: 0,
        overflow: "hidden",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={teamLogoUrl(name)}
        alt={name}
        onError={(e) => {
          e.currentTarget.style.display = "none";
        }}
        style={{
          width: 24,
          height: 24,
          objectFit: "contain",
          flexShrink: 0,
          background: "transparent",
        }}
      />
      <span
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 12,
          fontWeight: 700,
          color: "#F0E8D0",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          textAlign: isLeft ? "left" : "right",
          minWidth: 0,
        }}
      >
        {name}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match card
// ---------------------------------------------------------------------------

function MatchCard({
  entry,
  leagueId,
}: {
  entry: SeriesCalendarEntry;
  leagueId: string;
}) {
  const router = useRouter();

  return (
    <div
      onClick={() => router.push(`/leagues/${leagueId}/h2h/${entry.series_id}`)}
      style={{
        background: "#111111",
        border: "1px solid #1E1E1E",
        borderRadius: 10,
        padding: "12px 12px",
        cursor: "pointer",
        transition: "border-color 150ms ease, background 150ms ease",
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "#2A2A2A";
        (e.currentTarget as HTMLDivElement).style.background = "#161616";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "#1E1E1E";
        (e.currentTarget as HTMLDivElement).style.background = "#111111";
      }}
    >
      {/* Main row: home — status — away */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <TeamDisplay name={entry.team_home} align="left" />

        <div style={{ display: "flex", justifyContent: "center", flexShrink: 0, minWidth: 56 }}>
          <StatusBadge status={entry.status} result={entry.result} />
        </div>

        <TeamDisplay name={entry.team_away} align="right" />
      </div>

      {/* Date row */}
      <div style={{ textAlign: "center" }}>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 12,
            color: "#555555",
            textTransform: "capitalize",
            letterSpacing: "0.03em",
          }}
        >
          {formatDate(entry.date)}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonCards() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse"
          style={{
            height: 68,
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
// Page
// ---------------------------------------------------------------------------

export default function CalendarPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.series
      .calendar(leagueId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setInitializing(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (initializing) return null;

  const weeks = data ? groupByWeek(data.series) : [];

  return (
    <div className="min-h-[100dvh]" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">
        {/* Page header */}
        <div style={{ marginBottom: 28 }}>
          <h1
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 30,
              fontWeight: 700,
              color: "#F0E8D0",
              lineHeight: 1.1,
            }}
          >
            Calendario
          </h1>
        </div>

        {/* Loading */}
        {loading && <SkeletonCards />}

        {/* Error */}
        {error && (
          <p className="text-sm text-center py-20" style={{ color: "#888888" }}>
            {error}
          </p>
        )}

        {/* Empty */}
        {!loading && !error && weeks.length === 0 && (
          <div className="py-20 text-center">
            <p style={{ color: "#888888", fontWeight: 500 }}>No hay partidas disponibles</p>
          </div>
        )}

        {/* Weeks */}
        {!loading &&
          !error &&
          weeks.map((week) => (
            <div key={week.label} style={{ marginBottom: 28 }}>
              {/* Week header */}
              <p
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  color: "#333333",
                  textTransform: "uppercase",
                  marginBottom: 10,
                }}
              >
                {week.label}
              </p>
              {/* Match cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {week.matches.map((entry) => (
                  <MatchCard key={entry.series_id} entry={entry} leagueId={leagueId} />
                ))}
              </div>
            </div>
          ))}
      </main>
    </div>
  );
}

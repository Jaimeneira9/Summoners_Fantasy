"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type H2HResponse, type TeamH2HStats, type PlayerH2HStats } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEAM_LOGO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

const ROLE_LABEL: Record<string, string> = {
  top: "TOP",
  jungle: "JUNGLE",
  mid: "MID",
  adc: "ADC",
  support: "SUPPORT",
};

const ROLE_ORDER = ["top", "jungle", "mid", "adc", "support"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function teamLogoUrl(name: string): string {
  return `${TEAM_LOGO_BASE}${name.toLowerCase().replace(/ /g, "-")}.webp`;
}

function fmt(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

function fmtGold(value: number): string {
  const v = Math.round(value);
  return v >= 0 ? `+${v}` : String(v);
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
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
          fontSize: 22,
          fontWeight: 700,
          color: "#F0E8D0",
          letterSpacing: "0.06em",
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
          gap: 6,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "#FCD400",
            animation: "pulse 1.5s ease-in-out infinite",
          }}
        />
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 13,
            fontWeight: 700,
            color: "#FCD400",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          EN CURSO
        </span>
      </span>
    );
  }
  return (
    <span
      style={{
        fontFamily: "'Barlow Condensed', sans-serif",
        fontSize: 13,
        fontWeight: 600,
        color: "#555555",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
      }}
    >
      PROGRAMADO
    </span>
  );
}

// ---------------------------------------------------------------------------
// Comparison stat row
// ---------------------------------------------------------------------------

function StatRow({
  label,
  homeVal,
  awayVal,
  format,
  higherIsBetter = true,
}: {
  label: string;
  homeVal: number;
  awayVal: number;
  format: (v: number) => string;
  higherIsBetter?: boolean;
}) {
  const homeWins = higherIsBetter ? homeVal > awayVal : homeVal < awayVal;
  const awayWins = higherIsBetter ? awayVal > homeVal : awayVal < homeVal;
  const tie = homeVal === awayVal;

  const highlightStyle = { color: "#FCD400", fontWeight: 700 };
  const neutralStyle = { color: "#888888", fontWeight: 600 };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto 1fr",
        alignItems: "center",
        gap: 12,
        padding: "10px 0",
        borderBottom: "1px solid #1A1A1A",
      }}
    >
      {/* Home value */}
      <div style={{ textAlign: "right" }}>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 16,
            ...(tie ? neutralStyle : homeWins ? highlightStyle : neutralStyle),
          }}
        >
          {format(homeVal)}
        </span>
      </div>
      {/* Label */}
      <div style={{ textAlign: "center", minWidth: 90 }}>
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 10,
            fontWeight: 700,
            color: "#333333",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          {label}
        </span>
      </div>
      {/* Away value */}
      <div style={{ textAlign: "left" }}>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 16,
            ...(tie ? neutralStyle : awayWins ? highlightStyle : neutralStyle),
          }}
        >
          {format(awayVal)}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Team stats tab
// ---------------------------------------------------------------------------

function TeamStatsTab({
  home,
  away,
}: {
  home: TeamH2HStats;
  away: TeamH2HStats;
}) {
  return (
    <div
      style={{
        background: "#111111",
        border: "1px solid #1E1E1E",
        borderRadius: 12,
        padding: "16px 20px",
      }}
    >
      {/* Team name headers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          gap: 12,
          marginBottom: 4,
          alignItems: "center",
        }}
      >
        <div style={{ textAlign: "right" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={teamLogoUrl(home.team_name)}
            alt={home.team_name}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
            style={{ width: 24, height: 24, objectFit: "contain", display: "inline-block" }}
          />
        </div>
        <div style={{ minWidth: 90 }} />
        <div style={{ textAlign: "left" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={teamLogoUrl(away.team_name)}
            alt={away.team_name}
            onError={(e) => { e.currentTarget.style.display = "none"; }}
            style={{ width: 24, height: 24, objectFit: "contain", display: "inline-block" }}
          />
        </div>
      </div>

      <StatRow label="Victorias" homeVal={home.wins} awayVal={away.wins} format={(v) => String(v)} />
      <StatRow label="Derrotas" homeVal={home.losses} awayVal={away.losses} format={(v) => String(v)} higherIsBetter={false} />
      <StatRow label="KDA" homeVal={home.avg_kda} awayVal={away.avg_kda} format={(v) => fmt(v, 2)} />
      <StatRow label="Gold Diff @15" homeVal={home.avg_gold_diff_15} awayVal={away.avg_gold_diff_15} format={fmtGold} />
      <StatRow label="DPM" homeVal={home.avg_dpm} awayVal={away.avg_dpm} format={(v) => Math.round(v).toLocaleString()} />
      <StatRow label="CS/min" homeVal={home.avg_cs_per_min} awayVal={away.avg_cs_per_min} format={(v) => fmt(v, 1)} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player stat mini
// ---------------------------------------------------------------------------

function PlayerStatPair({
  label,
  homeVal,
  awayVal,
  format,
  higherIsBetter = true,
}: {
  label: string;
  homeVal: number | null;
  awayVal: number | null;
  format: (v: number) => string;
  higherIsBetter?: boolean;
}) {
  const hv = homeVal ?? 0;
  const av = awayVal ?? 0;
  const homeWins = higherIsBetter ? hv > av : hv < av;
  const awayWins = higherIsBetter ? av > hv : av < hv;
  const tie = hv === av;

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <span
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 12,
          color: tie ? "#555" : homeWins ? "#FCD400" : "#555",
          fontWeight: 600,
        }}
      >
        {homeVal != null ? format(hv) : "—"}
      </span>
      <span style={{ fontSize: 9, color: "#333", fontFamily: "'Space Grotesk', sans-serif", textTransform: "uppercase" }}>
        {label}
      </span>
      <span
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 12,
          color: tie ? "#555" : awayWins ? "#FCD400" : "#555",
          fontWeight: 600,
        }}
      >
        {awayVal != null ? format(av) : "—"}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Players tab
// ---------------------------------------------------------------------------

function PlayersTab({
  playersHome,
  playersAway,
}: {
  playersHome: PlayerH2HStats[];
  playersAway: PlayerH2HStats[];
}) {
  const homeByRole = Object.fromEntries(playersHome.map((p) => [p.role, p]));
  const awayByRole = Object.fromEntries(playersAway.map((p) => [p.role, p]));

  return (
    <div
      style={{
        background: "#111111",
        border: "1px solid #1E1E1E",
        borderRadius: 12,
        overflow: "hidden",
      }}
    >
      {ROLE_ORDER.map((role, idx) => {
        const hp = homeByRole[role] ?? null;
        const ap = awayByRole[role] ?? null;

        return (
          <div
            key={role}
            style={{
              padding: "14px 20px",
              borderBottom: idx < ROLE_ORDER.length - 1 ? "1px solid #1A1A1A" : "none",
            }}
          >
            {/* Role label */}
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 9,
                fontWeight: 700,
                color: "#333333",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: 8,
                textAlign: "center",
              }}
            >
              {ROLE_LABEL[role] ?? role}
            </p>

            {/* Player row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto 1fr",
                gap: 8,
                alignItems: "start",
              }}
            >
              {/* Home player */}
              <div style={{ textAlign: "right" }}>
                {hp ? (
                  <>
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#F0E8D0",
                        marginBottom: 2,
                      }}
                    >
                      {hp.name}
                    </p>
                    <p
                      style={{
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontSize: 11,
                        color: "#555",
                      }}
                    >
                      {fmt(hp.avg_kda, 2)} KDA · {fmt(hp.avg_cs_per_min, 1)} CS · {Math.round(hp.avg_dpm)} DPM
                    </p>
                  </>
                ) : (
                  <p style={{ fontSize: 12, color: "#444" }}>Sin datos</p>
                )}
              </div>

              {/* VS divider */}
              <div style={{ textAlign: "center", paddingTop: 2 }}>
                <span
                  style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontSize: 11,
                    fontWeight: 700,
                    color: "#333333",
                    letterSpacing: "0.06em",
                  }}
                >
                  VS
                </span>
              </div>

              {/* Away player */}
              <div style={{ textAlign: "left" }}>
                {ap ? (
                  <>
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#F0E8D0",
                        marginBottom: 2,
                      }}
                    >
                      {ap.name}
                    </p>
                    <p
                      style={{
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontSize: 11,
                        color: "#555",
                      }}
                    >
                      {fmt(ap.avg_kda, 2)} KDA · {fmt(ap.avg_cs_per_min, 1)} CS · {Math.round(ap.avg_dpm)} DPM
                    </p>
                  </>
                ) : (
                  <p style={{ fontSize: 12, color: "#444" }}>Sin datos</p>
                )}
              </div>
            </div>

            {/* Stat comparison row */}
            {(hp || ap) && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  gap: 16,
                  marginTop: 8,
                  flexWrap: "wrap",
                }}
              >
                <PlayerStatPair
                  label="KDA"
                  homeVal={hp?.avg_kda ?? null}
                  awayVal={ap?.avg_kda ?? null}
                  format={(v) => fmt(v, 2)}
                />
                <PlayerStatPair
                  label="CS"
                  homeVal={hp?.avg_cs_per_min ?? null}
                  awayVal={ap?.avg_cs_per_min ?? null}
                  format={(v) => fmt(v, 1)}
                />
                <PlayerStatPair
                  label="DPM"
                  homeVal={hp?.avg_dpm ?? null}
                  awayVal={ap?.avg_dpm ?? null}
                  format={(v) => Math.round(v).toLocaleString()}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="animate-pulse" style={{ height: 90, borderRadius: 12, background: "#111" }} />
      <div className="animate-pulse" style={{ height: 40, borderRadius: 8, background: "#111" }} />
      <div className="animate-pulse" style={{ height: 220, borderRadius: 12, background: "#111" }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function H2HPage() {
  const { seriesId } = useParams<{ id: string; seriesId: string }>();
  const [data, setData] = useState<H2HResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"equipos" | "jugadores">("equipos");

  useEffect(() => {
    let cancelled = false;
    api.series
      .h2h(seriesId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [seriesId]);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">
        {loading && <LoadingSkeleton />}

        {error && (
          <p className="text-sm text-center py-20" style={{ color: "#888888" }}>
            {error}
          </p>
        )}

        {!loading && !error && data && (
          <>
            {/* Header card */}
            <div
              style={{
                background: "#111111",
                border: "1px solid #1E1E1E",
                borderRadius: 12,
                padding: "20px 24px",
                marginBottom: 20,
                textAlign: "center",
              }}
            >
              {/* Teams row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 16,
                  marginBottom: 12,
                }}
              >
                {/* Home team */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flex: 1 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={teamLogoUrl(data.team_home.team_name)}
                    alt={data.team_home.team_name}
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    style={{ width: 44, height: 44, objectFit: "contain" }}
                  />
                  <span
                    style={{
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontSize: 14,
                      fontWeight: 700,
                      color: "#F0E8D0",
                    }}
                  >
                    {data.team_home.team_name}
                  </span>
                </div>

                {/* Center: status/result + date */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 6,
                    flexShrink: 0,
                  }}
                >
                  <StatusBadge status={data.status} result={data.result} />
                  <span
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontSize: 11,
                      color: "#444",
                      textTransform: "capitalize",
                      letterSpacing: "0.03em",
                    }}
                  >
                    {formatDate(data.date)}
                  </span>
                </div>

                {/* Away team */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flex: 1 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={teamLogoUrl(data.team_away.team_name)}
                    alt={data.team_away.team_name}
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    style={{ width: 44, height: 44, objectFit: "contain" }}
                  />
                  <span
                    style={{
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontSize: 14,
                      fontWeight: 700,
                      color: "#F0E8D0",
                    }}
                  >
                    {data.team_away.team_name}
                  </span>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {(["equipos", "jugadores"] as const).map((tab) => {
                const isActive = activeTab === tab;
                return (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    style={{
                      padding: "8px 18px",
                      borderRadius: 20,
                      border: isActive ? "1px solid rgba(252,212,0,0.5)" : "1px solid #2A2A2A",
                      background: isActive ? "rgba(252,212,0,0.12)" : "#111111",
                      color: isActive ? "#FCD400" : "#555555",
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      transition: "all 150ms ease",
                      textTransform: "capitalize",
                    }}
                  >
                    {tab === "equipos" ? "Equipos" : "Jugadores"}
                  </button>
                );
              })}
            </div>

            {/* Tab content */}
            {activeTab === "equipos" && (
              <TeamStatsTab home={data.team_home} away={data.team_away} />
            )}
            {activeTab === "jugadores" && (
              <PlayersTab playersHome={data.players_home} playersAway={data.players_away} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

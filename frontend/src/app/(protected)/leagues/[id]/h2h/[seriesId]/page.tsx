"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type H2HResponse, type TeamH2HStats, type PlayerH2HStats } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TEAM_LOGO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

const PLAYER_PHOTO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/";

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

function playerPhotoUrl(player: PlayerH2HStats): string {
  return player.image_url || `${PLAYER_PHOTO_BASE}${player.name.toLowerCase().replace(/ /g, "-")}.webp`;
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
      <div style={{ textAlign: "center", minWidth: 72 }}>
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 9,
            fontWeight: 700,
            color: "#333333",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            whiteSpace: "nowrap",
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
        <div style={{ minWidth: 72 }} />
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
// Player avatar (photo with initial fallback)
// ---------------------------------------------------------------------------

function PlayerAvatar({
  player,
  size = 80,
  side = "home",
}: {
  player: PlayerH2HStats;
  size?: number;
  side?: "home" | "away";
}) {
  const [failed, setFailed] = useState(false);
  const initial = player.name.charAt(0).toUpperCase();

  const containerStyle: React.CSSProperties = {
    width: size,
    height: size,
    background: "#0D0D0D",
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    borderRight: side === "home" ? "2px solid #FCD400" : "none",
    borderLeft: side === "away" ? "2px solid #FCD400" : "none",
    borderTop: "none",
    borderBottom: "none",
    overflow: "hidden",
  };

  if (failed) {
    return (
      <div style={containerStyle}>
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: size * 0.38,
            fontWeight: 700,
            color: "#555555",
          }}
        >
          {initial}
        </span>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={playerPhotoUrl(player)}
        alt={player.name}
        onError={() => setFailed(true)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center top",
          display: "block",
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player stat row (vertical table, one stat per line)
// ---------------------------------------------------------------------------

function PlayerStatRow({
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
  const tie = homeVal === null || awayVal === null || hv === av;

  const winColor = "#4ADE80";
  const neutralColor = "#555555";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto 1fr",
        alignItems: "center",
        gap: 8,
        padding: "7px 0",
        borderBottom: "1px solid #181818",
      }}
    >
      <div style={{ textAlign: "right" }}>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 15,
            fontWeight: tie ? 600 : homeWins ? 700 : 500,
            color: tie ? neutralColor : homeWins ? winColor : neutralColor,
          }}
        >
          {homeVal != null ? format(hv) : "—"}
        </span>
      </div>
      <div style={{ textAlign: "center", minWidth: 60 }}>
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 9,
            fontWeight: 700,
            color: "#FCD400",
            textTransform: "uppercase",
            letterSpacing: "0.07em",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
      </div>
      <div style={{ textAlign: "left" }}>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: 15,
            fontWeight: tie ? 600 : awayWins ? 700 : 500,
            color: tie ? neutralColor : awayWins ? winColor : neutralColor,
          }}
        >
          {awayVal != null ? format(av) : "—"}
        </span>
      </div>
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
              padding: "20px 16px",
              borderBottom: idx < ROLE_ORDER.length - 1 ? "1px solid #1E1E1E" : "none",
            }}
          >
            {/* Role label */}
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 9,
                fontWeight: 700,
                color: "#FCD400",
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                marginBottom: 14,
                textAlign: "center",
              }}
            >
              {ROLE_LABEL[role] ?? role}
            </p>

            {/* Main layout: photo | stats | photo */}
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
              }}
            >
              {/* Home player column */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 6,
                  flexShrink: 0,
                  width: 80,
                }}
              >
                {hp ? (
                  <>
                    <PlayerAvatar player={hp} size={80} side="home" />
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 10,
                        fontWeight: 700,
                        color: "#F0E8D0",
                        textAlign: "center",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        maxWidth: 80,
                      }}
                    >
                      {hp.name}
                    </p>
                  </>
                ) : (
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      borderRadius: 10,
                      background: "#0D0D0D",
                      borderRight: "2px solid #FCD400",
                    }}
                  />
                )}
              </div>

              {/* Stats column */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <PlayerStatRow
                  label="KDA"
                  homeVal={hp?.avg_kda ?? null}
                  awayVal={ap?.avg_kda ?? null}
                  format={(v) => fmt(v, 2)}
                />
                <PlayerStatRow
                  label="Kills"
                  homeVal={hp?.avg_kills ?? null}
                  awayVal={ap?.avg_kills ?? null}
                  format={(v) => fmt(v, 1)}
                />
                <PlayerStatRow
                  label="Deaths"
                  homeVal={hp?.avg_deaths ?? null}
                  awayVal={ap?.avg_deaths ?? null}
                  format={(v) => fmt(v, 1)}
                  higherIsBetter={false}
                />
                <PlayerStatRow
                  label="Assists"
                  homeVal={hp?.avg_assists ?? null}
                  awayVal={ap?.avg_assists ?? null}
                  format={(v) => fmt(v, 1)}
                />
                <PlayerStatRow
                  label="CS/min"
                  homeVal={hp?.avg_cs_per_min ?? null}
                  awayVal={ap?.avg_cs_per_min ?? null}
                  format={(v) => fmt(v, 1)}
                />
                <PlayerStatRow
                  label="DPM"
                  homeVal={hp?.avg_dpm ?? null}
                  awayVal={ap?.avg_dpm ?? null}
                  format={(v) => Math.round(v).toLocaleString()}
                />
              </div>

              {/* Away player column */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 6,
                  flexShrink: 0,
                  width: 80,
                }}
              >
                {ap ? (
                  <>
                    <PlayerAvatar player={ap} size={80} side="away" />
                    <p
                      style={{
                        fontFamily: "'Space Grotesk', sans-serif",
                        fontSize: 10,
                        fontWeight: 700,
                        color: "#F0E8D0",
                        textAlign: "center",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        maxWidth: 80,
                      }}
                    >
                      {ap.name}
                    </p>
                  </>
                ) : (
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      borderRadius: 10,
                      background: "#0D0D0D",
                      borderLeft: "2px solid #FCD400",
                    }}
                  />
                )}
              </div>
            </div>
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
  const { id: leagueId, seriesId } = useParams<{ id: string; seriesId: string }>();
  const [data, setData] = useState<H2HResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"equipos" | "jugadores">("equipos");

  useEffect(() => {
    let cancelled = false;
    api.series
      .h2h(seriesId, leagueId)
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
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, flex: 1, minWidth: 0 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={teamLogoUrl(data.team_home.team_name)}
                    alt={data.team_home.team_name}
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    style={{ width: 36, height: 36, objectFit: "contain", flexShrink: 0 }}
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
                      maxWidth: "100%",
                      textAlign: "center",
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
                    gap: 4,
                    flexShrink: 0,
                    minWidth: 56,
                  }}
                >
                  <StatusBadge status={data.status} result={data.result} />
                  <span
                    style={{
                      fontFamily: "'Barlow Condensed', sans-serif",
                      fontSize: 10,
                      color: "#444",
                      textTransform: "capitalize",
                      letterSpacing: "0.03em",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {formatDate(data.date)}
                  </span>
                </div>

                {/* Away team */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, flex: 1, minWidth: 0 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={teamLogoUrl(data.team_away.team_name)}
                    alt={data.team_away.team_name}
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                    style={{ width: 36, height: 36, objectFit: "contain", flexShrink: 0 }}
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
                      maxWidth: "100%",
                      textAlign: "center",
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
                      flex: 1,
                      padding: "8px 12px",
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
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
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

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type PlayerMatchStat, type PlayerSplitHistory, type Split } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PLAYER_PHOTO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PlayerHistoryResponse = {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    image_url: string | null;
    current_price: number;
  };
  stats: PlayerMatchStat[];
  total_points: number;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPlayerPhotoUrl(name: string): string {
  return `${PLAYER_PHOTO_BASE}${name.toLowerCase().replace(/ /g, "-")}.webp`;
}

function calcKDA(kills: number, deaths: number, assists: number): string {
  if (deaths === 0) return "∞";
  return ((kills + assists) / deaths).toFixed(2);
}

function barWidth(value: number, max: number): number {
  return Math.min(Math.max((value / max) * 100, 0), 100);
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0A" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px 96px" }}>
        <div style={{ height: 14, width: 120, borderRadius: 6, background: "#1A1A1A", marginBottom: 24 }} />
        <div style={{ height: 140, borderRadius: 12, background: "#111", marginBottom: 12 }} />
        <div style={{ height: 40, borderRadius: 8, background: "#111", marginBottom: 12 }} />
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} style={{ flex: 1, height: 90, borderRadius: 10, background: "#111" }} />
          ))}
        </div>
        <div style={{ display: "flex", gap: 20 }}>
          <div style={{ flex: 1.4, height: 260, borderRadius: 12, background: "#111" }} />
          <div style={{ flex: 1, height: 260, borderRadius: 12, background: "#111" }} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PlayerStatsPage() {
  const { id: leagueId, playerId } = useParams<{ id: string; playerId: string }>();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<PlayerHistoryResponse | null>(null);
  const [, setSplitHistory] = useState<PlayerSplitHistory[]>([]);
  const [splits, setSplits] = useState<Split[]>([]);
  const [selectedSplitId, setSelectedSplitId] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([
      api.scoring.playerHistory(playerId),
      api.splits.playerHistory(playerId),
      api.splits.list(),
    ])
      .then(([history, splitHistory, splitList]) => {
        const h = history as PlayerHistoryResponse;
        setHistoryData(h);
        setSplitHistory(splitHistory as PlayerSplitHistory[]);
        const availableSplits = splitList as Split[];
        setSplits(availableSplits);

        // Seleccionar el split activo por defecto
        const activeSplit = availableSplits.find(s => s.is_active);
        const defaultSplitId = activeSplit?.id ?? availableSplits[0]?.id ?? null;
        setSelectedSplitId(defaultSplitId);

        // Default to last week del split seleccionado
        const filteredStats = defaultSplitId
          ? h.stats.filter(s => s.competition_id === defaultSplitId)
          : h.stats;
        if (filteredStats.length > 0) {
          setSelectedWeek(filteredStats.length);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const player = historyData?.player ?? null;
  // matchStats filtrados por split seleccionado, con 1-based week index
  const matchStats = (historyData?.stats ?? [])
    .filter(s => !selectedSplitId || s.competition_id === selectedSplitId)
    .map((s, i) => ({ ...s, week: i + 1 }));
  const totalPoints = historyData?.total_points ?? 0;

  const lastMatchPts = matchStats.length > 0 ? matchStats[matchStats.length - 1].fantasy_points : 0;

  const roleHex = player ? getRoleColor(player.role) : getRoleColor("coach");
  const roleColor = player ? (ROLE_COLORS[player.role] ?? ROLE_COLORS.coach) : ROLE_COLORS.coach;
  const photoUrl = player ? getPlayerPhotoUrl(player.name) : "";

  // Selected stat for zona 3
  const selectedStat = matchStats.find((s) => s.week === selectedWeek) ?? null;

  // Computed per-game stats for zona 3
  const statCards = selectedStat
    ? [
        {
          label: "KDA",
          value: calcKDA(selectedStat.kills, selectedStat.deaths, selectedStat.assists),
          barPct: (() => {
            const kda = selectedStat.deaths === 0 ? 10 : (selectedStat.kills + selectedStat.assists) / selectedStat.deaths;
            return kda >= 5 ? 80 : barWidth(kda, 10);
          })(),
        },
        {
          label: "Kills",
          value: String(selectedStat.kills),
          barPct: barWidth(selectedStat.kills, 10),
        },
        {
          label: "Deaths",
          value: String(selectedStat.deaths),
          barPct: Math.max(0, 100 - (selectedStat.deaths / 10) * 100),
          deathColor: selectedStat.deaths <= 2 ? "#4CAF50" : selectedStat.deaths >= 5 ? "#EF5350" : "#FFF",
        },
        {
          label: "Assists",
          value: String(selectedStat.assists),
          barPct: barWidth(selectedStat.assists, 15),
        },
        {
          label: "CS/min",
          value: selectedStat.cs_per_min != null ? selectedStat.cs_per_min.toFixed(1) : "—",
          barPct: selectedStat.cs_per_min != null ? barWidth(selectedStat.cs_per_min, 10) : null,
        },
        {
          label: "Daño/min",
          value: selectedStat.damage_share != null ? `${(selectedStat.damage_share * 100).toFixed(0)}%` : "—",
          barPct: selectedStat.damage_share != null ? barWidth(selectedStat.damage_share * 100, 40) : null,
        },
        {
          label: "Visión",
          value: selectedStat.vision_score != null ? String(selectedStat.vision_score) : "—",
          barPct: selectedStat.vision_score != null ? barWidth(selectedStat.vision_score, 50) : null,
        },
        {
          label: "Gold @15",
          value: selectedStat.gold_diff_at_15 != null
            ? (selectedStat.gold_diff_at_15 >= 0 ? `+${selectedStat.gold_diff_at_15}` : String(selectedStat.gold_diff_at_15))
            : "—",
          barPct: selectedStat.gold_diff_at_15 != null
            ? Math.min(Math.max(50 + (selectedStat.gold_diff_at_15 / 2000) * 50, 0), 100)
            : null,
        },
      ]
    : null;

  // Active week badge info
  const activeStat = matchStats.find((s) => s.week === selectedWeek);
  const activeIsWin = activeStat ? activeStat.fantasy_points > 12 : false;
  const activeRival = activeStat?.matches
    ? (activeStat.matches.team_1 === player?.team
        ? activeStat.matches.team_2
        : activeStat.matches.team_1)
    : null;

  // Bar chart max
  const maxPts = Math.max(...matchStats.map((s) => s.fantasy_points), 1);

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (loading) return <LoadingSkeleton />;

  if (error || !player) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0A0A0A" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "rgba(255,255,255,0.3)", fontSize: 14, marginBottom: 12 }}>
            {error ?? "Jugador no encontrado"}
          </p>
          <Link
            href={`/leagues/${leagueId}/lineup`}
            style={{ color: "#FCD400", fontSize: 12, textDecoration: "underline" }}
          >
            Volver al lineup
          </Link>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0A", color: "#fff" }}>
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px 96px" }}>

        {/* Breadcrumb */}
        <nav style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#444", marginBottom: 20 }}>
          <Link href={`/leagues/${leagueId}/lineup`} style={{ color: "#555", textDecoration: "none" }}>
            Mi Equipo
          </Link>
          <span>›</span>
          <span style={{ color: "#888" }}>Stats de Jugador</span>
        </nav>

        {/* ================================================================ */}
        {/* ZONA 1: Player Hero                                              */}
        {/* ================================================================ */}
        <div style={{
          background: "#111111",
          borderRadius: 12,
          padding: "24px 28px",
          border: "1px solid #222",
          display: "flex",
          alignItems: "center",
          gap: 20,
          marginBottom: 12,
        }}>
          {/* Photo + role badge */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div style={{
              width: 80,
              height: 80,
              borderRadius: 10,
              border: `2px solid ${roleHex}`,
              overflow: "hidden",
              background: `${roleHex}22`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}>
              {!imgError ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={photoUrl}
                  alt={player.name}
                  style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
                  onError={() => setImgError(true)}
                />
              ) : (
                <RoleIcon role={player.role} className={`w-10 h-10 ${roleColor.text} opacity-60`} />
              )}
            </div>
            {/* Role badge */}
            <div style={{
              background: roleHex,
              color: "#000",
              fontSize: 9,
              fontWeight: 900,
              padding: "2px 8px",
              borderRadius: 4,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}>
              {ROLE_LABEL[player.role] ?? player.role.toUpperCase()}
            </div>
          </div>

          {/* Player info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 28,
              fontWeight: 700,
              color: "#fff",
              lineHeight: 1.1,
              margin: 0,
              textTransform: "uppercase",
            }}>
              {player.name}
            </h1>
            <p style={{ fontSize: 13, color: "#555", margin: "2px 0 0", fontFamily: "'Space Grotesk', sans-serif" }}>
              {player.team}
            </p>
            <p style={{ fontSize: 12, color: "#444", margin: "2px 0 0" }}>
              LEC · {player.current_price.toFixed(1)}M
            </p>
          </div>

          {/* Total points */}
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: 40,
              fontWeight: 700,
              color: "#FCD400",
              lineHeight: 1,
            }}>
              {totalPoints.toFixed(0)}
            </div>
            <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
              pts total
            </div>
            {lastMatchPts > 0 && (
              <div style={{ fontSize: 12, color: "#4CAF50", marginTop: 4, fontWeight: 600 }}>
                +{lastMatchPts.toFixed(1)} esta semana
              </div>
            )}
          </div>
        </div>

        {/* ================================================================ */}
        {/* ZONA 2: Selector de jornada                                      */}
        {/* ================================================================ */}
        {matchStats.length > 0 && (
          <div style={{
            background: "#111111",
            borderRadius: 10,
            padding: "12px 16px",
            border: "1px solid #1E1E1E",
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 8,
            flexWrap: "wrap",
          }}>
            {/* Week chips */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", flex: 1 }}>
              {matchStats.map((stat) => {
                const isActive = stat.week === selectedWeek;
                return (
                  <button
                    key={stat.week}
                    onClick={() => setSelectedWeek(stat.week)}
                    style={{
                      background: isActive ? "#FCD400" : "#1A1A1A",
                      border: `1px solid ${isActive ? "#FCD400" : "#2A2A2A"}`,
                      borderRadius: 8,
                      padding: "6px 14px",
                      color: isActive ? "#000" : "#555",
                      fontSize: 12,
                      fontWeight: isActive ? 700 : 400,
                      cursor: "pointer",
                      fontFamily: "'Barlow Condensed', sans-serif",
                      letterSpacing: "0.04em",
                    }}
                  >
                    S{stat.week}
                  </button>
                );
              })}
            </div>

            {/* Active week badge */}
            {activeStat && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                <div style={{
                  background: activeIsWin ? "#1B3A1B" : "#3A1A1A",
                  color: activeIsWin ? "#4CAF50" : "#EF5350",
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: 6,
                }}>
                  {activeIsWin ? "W" : "L"}
                </div>
                {activeRival && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${activeRival.toLowerCase().replace(/ /g, "-")}.webp`}
                    alt={activeRival}
                    style={{ width: 20, height: 20, objectFit: "contain" }}
                    onError={(e) => { e.currentTarget.style.display = "none"; }}
                  />
                )}
                <span style={{ fontSize: 12, color: "#FCD400", fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif" }}>
                  +{activeStat.fantasy_points.toFixed(1)} pts
                </span>
              </div>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* ZONA 3: Stat cards de la jornada seleccionada                    */}
        {/* ================================================================ */}
        {statCards && (
          <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
            {statCards.map((card) => (
              <div
                key={card.label}
                className="stat-card"
                style={{
                  background: "#111111",
                  borderRadius: 10,
                  padding: 16,
                  border: "1px solid #1E1E1E",
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  cursor: "default",
                }}
              >
                <div style={{
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "#555",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}>
                  {card.label}
                </div>
                <div style={{
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontSize: 26,
                  fontWeight: 700,
                  color: card.deathColor ?? "#FFF",
                  lineHeight: 1.1,
                }}>
                  {card.value}
                </div>
                {card.barPct != null && (
                  <div style={{ height: 3, background: "#1E1E1E", borderRadius: 2, marginTop: 6 }}>
                    <div style={{
                      height: "100%",
                      width: `${card.barPct}%`,
                      background: "#FCD400",
                      borderRadius: 2,
                    }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ================================================================ */}
        {/* ZONA 4: Dos columnas                                             */}
        {/* ================================================================ */}
        {matchStats.length > 0 && (
          <div style={{ display: "flex", gap: 20 }}>

            {/* Col izquierda: Bar chart */}
            <div style={{
              flex: 1.4,
              background: "#111111",
              borderRadius: 12,
              padding: 20,
              border: "1px solid #1E1E1E",
            }}>
              {/* Selector de splits */}
              {splits.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/lec.webp"
                    alt="LEC"
                    style={{ width: 24, height: 24, borderRadius: 4, objectFit: "contain" }}
                  />
                  <select
                    value={selectedSplitId ?? ""}
                    onChange={(e) => {
                      const newId = e.target.value;
                      setSelectedSplitId(newId);
                      // Seleccionar la última jornada del nuevo split
                      const newFiltered = (historyData?.stats ?? [])
                        .filter(s => s.competition_id === newId);
                      setSelectedWeek(newFiltered.length > 0 ? newFiltered.length : null);
                    }}
                    style={{
                      background: "rgba(255,255,255,0.07)",
                      border: "1px solid rgba(252,212,0,0.3)",
                      color: "var(--text-on-dark)",
                      borderRadius: 8,
                      padding: "4px 12px",
                      fontSize: 12,
                      fontFamily: "'Space Grotesk', sans-serif",
                      fontWeight: 600,
                      cursor: "pointer",
                      outline: "none",
                    }}
                  >
                    {splits.map(split => (
                      <option key={split.id} value={split.id} style={{ background: "var(--bg-card)" }}>
                        {split.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif" }}>
                  Puntos por semana
                </div>
                <div style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
                  Últimas {matchStats.length} semanas
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 140 }}>
                {matchStats.map((stat) => {
                  const isActive = stat.week === selectedWeek;
                  const heightPx = Math.max((stat.fantasy_points / maxPts) * 110, 2);
                  return (
                    <div
                      key={stat.week}
                      onClick={() => setSelectedWeek(stat.week)}
                      style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}
                    >
                      <span style={{
                        fontSize: 10,
                        color: isActive ? "#FCD400" : "#555",
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontWeight: 700,
                      }}>
                        {stat.fantasy_points.toFixed(0)}
                      </span>
                      <div style={{
                        width: "100%",
                        height: `${heightPx}px`,
                        background: isActive ? "#FCD400" : "#2A2A2A",
                        borderRadius: "4px 4px 0 0",
                      }} />
                      <span style={{
                        fontSize: 9,
                        color: isActive ? "#FCD400" : "#333",
                        fontFamily: "'Barlow Condensed', sans-serif",
                      }}>
                        S{stat.week}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Col derecha: Historial de jornadas */}
            <div style={{
              flex: 1,
              background: "#111111",
              borderRadius: 12,
              padding: 20,
              border: "1px solid #1E1E1E",
              overflowY: "auto",
              maxHeight: 300,
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", marginBottom: 14 }}>
                Jornadas
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {[...matchStats].reverse().map((stat) => {
                  const isActive = stat.week === selectedWeek;
                  const isWin = stat.fantasy_points > 12;
                  const kda = `${stat.kills}/${stat.deaths}/${stat.assists}`;
                  const rival = stat.matches
                    ? (stat.matches.team_1 === player.team ? stat.matches.team_2 : stat.matches.team_1)
                    : null;

                  return (
                    <div
                      key={stat.week}
                      onClick={() => setSelectedWeek(stat.week)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 10px",
                        borderRadius: 8,
                        cursor: "pointer",
                        background: isActive ? "#1E1A00" : "transparent",
                        border: isActive ? "1px solid rgba(252,212,0,0.25)" : "1px solid transparent",
                        transition: "background 0.1s",
                      }}
                    >
                      {/* Week badge */}
                      <div style={{
                        background: "#1A1A1A",
                        borderRadius: 6,
                        padding: "3px 8px",
                        fontSize: 12,
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontWeight: 700,
                        color: isActive ? "#FCD400" : "#888",
                        flexShrink: 0,
                        minWidth: 36,
                        textAlign: "center",
                      }}>
                        S{stat.week}
                      </div>

                      {/* W/L badge */}
                      <div style={{
                        width: 22,
                        height: 22,
                        borderRadius: 4,
                        background: isWin ? "#1B3A1B" : "#3A1A1A",
                        color: isWin ? "#4CAF50" : "#EF5350",
                        fontSize: 10,
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}>
                        {isWin ? "W" : "L"}
                      </div>

                      {/* Rival + KDA */}
                      <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                        {rival && (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${rival.toLowerCase().replace(/ /g, "-")}.webp`}
                            alt={rival}
                            style={{ width: 20, height: 20, objectFit: "contain", flexShrink: 0 }}
                            onError={(e) => { e.currentTarget.style.display = "none"; }}
                          />
                        )}
                        <div style={{ fontSize: 11, color: "#444" }}>{kda}</div>
                      </div>

                      {/* Puntos */}
                      <div style={{
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontSize: 14,
                        fontWeight: 700,
                        color: isWin ? "#FCD400" : "#555",
                        flexShrink: 0,
                      }}>
                        +{stat.fantasy_points.toFixed(1)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>
        )}

        {/* Estado vacío */}
        {matchStats.length === 0 && (
          <div style={{ textAlign: "center", padding: "64px 0" }}>
            <p style={{ color: "#333", fontSize: 14 }}>Sin datos de partidos disponibles aún</p>
          </div>
        )}

      </main>
    </div>
  );
}


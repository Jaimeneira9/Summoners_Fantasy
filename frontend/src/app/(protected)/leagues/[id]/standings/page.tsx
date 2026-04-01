"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  api,
  type LeaderboardEntry,
  type LeaderboardResponse,
  type DetailedLeaderboardEntry,
  type MemberStats,
  type MemberRoster,
  type League,
} from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";

// ---------------------------------------------------------------------------
// Sort types
// ---------------------------------------------------------------------------
type SortKey = "total_points" | "avg_pts_per_week";

// ---------------------------------------------------------------------------
// Modal: equipo de un miembro
// ---------------------------------------------------------------------------
function TeamModal({ leagueId, memberId, memberName, onClose }: {
  leagueId: string;
  memberId: string;
  memberName: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<MemberRoster | null>(null);
  const [loading, setLoading] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    api.leagues.memberRoster(leagueId, memberId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [leagueId, memberId]);

  const SLOT_ORDER = ["starter_1","starter_2","starter_3","starter_4","starter_5","coach","bench_1","bench_2"];
  const starterCount = data ? data.players.filter((rp) => !rp.slot.startsWith("bench")).length : 0;

  return (
    <>
      {/* Keyframes de animación */}
      <style>{`
        @keyframes tm-fade-scale {
          from { opacity: 0; transform: scale(0.96); }
          to   { opacity: 1; transform: scale(1); }
        }
        @keyframes tm-slide-up {
          from { opacity: 0; transform: translateY(100%); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .tm-card-desktop {
          animation: tm-fade-scale 200ms ease-out both;
        }
        .tm-card-mobile {
          animation: tm-slide-up 280ms ease-out both;
        }
        .tm-player-row:hover {
          background: rgba(255,255,255,0.03) !important;
        }
      `}</style>

      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
        style={{
          background: "rgba(0,0,0,0.7)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
        }}
        onClick={onClose}
      >
        {/* Card */}
        <div
          className={isMobile ? "tm-card-mobile" : "tm-card-desktop"}
          style={{
            width: "100%",
            maxWidth: isMobile ? "100%" : 480,
            maxHeight: "85vh",
            overflowY: "auto",
            background: "#1e1b1e",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
            borderRadius: isMobile ? "20px 20px 0 0" : 20,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              padding: "20px 20px 16px",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <div>
              {/* Nombre del manager */}
              <p style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 20,
                fontWeight: 700,
                color: "#f5f5f5",
                lineHeight: 1.2,
              }}>
                {memberName}
              </p>
              {/* Subtítulo con puntos y titulares */}
              {data && (
                <p style={{ marginTop: 4, fontSize: 13, color: "#999" }}>
                  <span style={{
                    fontFamily: "'Barlow Condensed', sans-serif",
                    fontSize: 15,
                    fontWeight: 700,
                    color: "#fcd400",
                  }}>
                    {Math.round(data.member.total_points)}
                  </span>
                  {" "}
                  <span style={{ color: "#555" }}>pts</span>
                  {" · "}
                  {starterCount} titulares
                </p>
              )}
            </div>

            {/* Botón cerrar */}
            <button
              onClick={onClose}
              style={{
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "#666",
                borderRadius: 8,
                flexShrink: 0,
                transition: "color 150ms ease",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#f5f5f5"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "#666"; }}
              aria-label="Cerrar"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {/* Contenido */}
          {loading ? (
            <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 8 }}>
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="animate-pulse"
                  style={{ height: 60, borderRadius: 10, background: "rgba(255,255,255,0.05)" }}
                />
              ))}
            </div>
          ) : !data || data.players.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", fontSize: 14, color: "#555" }}>
              Sin jugadores en el equipo.
            </div>
          ) : (
            <div style={{ padding: "8px 0 16px" }}>
              {[...data.players]
                .filter((rp) => !rp.slot.startsWith("bench"))
                .sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot))
                .map((rp, i, arr) => {
                  const p = rp.players;
                  const rc = ROLE_COLORS[p.role] ?? ROLE_COLORS.coach;
                  const isLast = i === arr.length - 1;
                  return (
                    <div
                      key={i}
                      className="tm-player-row"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        padding: "10px 20px",
                        borderBottom: isLast ? "none" : "1px solid rgba(255,255,255,0.05)",
                        transition: "background 150ms ease",
                        cursor: "default",
                      }}
                    >
                      {/* Foto circular 44px */}
                      <div style={{
                        width: 44,
                        height: 44,
                        borderRadius: "50%",
                        overflow: "hidden",
                        flexShrink: 0,
                        background: "#141414",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}>
                        {p.image_url
                          // eslint-disable-next-line @next/next/no-img-element
                          ? <img src={p.image_url} alt={p.name} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }} />
                          : <RoleIcon role={p.role} className={`w-5 h-5 ${rc.text}`} />
                        }
                      </div>

                      {/* Nombre + equipo */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{
                          fontFamily: "'Space Grotesk', sans-serif",
                          fontSize: 14,
                          fontWeight: 700,
                          color: "#f5f5f5",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          lineHeight: 1.3,
                        }}>
                          {p.name}
                        </p>
                        <p style={{ fontSize: 12, color: "#666", lineHeight: 1.3 }}>{p.team}</p>
                      </div>

                      {/* Badge de rol */}
                      <span className={`${rc.bg} ${rc.text}`} style={{
                        fontSize: 10,
                        fontWeight: 700,
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                        padding: "2px 7px",
                        borderRadius: 20,
                        flexShrink: 0,
                      }}>
                        {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
                      </span>

                      {/* Puntos */}
                      <p style={{
                        fontFamily: "'Barlow Condensed', sans-serif",
                        fontSize: 16,
                        fontWeight: 700,
                        color: "#fcd400",
                        flexShrink: 0,
                        minWidth: 48,
                        textAlign: "right",
                      }}>
                        {Math.round(rp.split_points ?? 0)}
                      </p>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getInitials(name: string | null): string {
  if (!name) return "?";
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

// ---------------------------------------------------------------------------
// SortableHeader inline component
// ---------------------------------------------------------------------------
function SortableHeader({
  label,
  sortKey,
  activeSortKey,
  sortDir,
  onSort,
  width,
  hideOnMobile = false,
}: {
  label: string;
  sortKey: SortKey;
  activeSortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
  width: number;
  hideOnMobile?: boolean;
}) {
  const isActive = activeSortKey === sortKey;
  const headerStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.08em",
    color: isActive ? "#FCD400" : "#333333",
    textTransform: "uppercase",
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 3,
    cursor: "pointer",
    userSelect: "none",
  };

  return (
    <div
      style={{ width, flexShrink: 0, textAlign: "right" }}
      className={hideOnMobile ? "hidden sm:block" : undefined}
    >
      <button style={headerStyle} onClick={() => onSort(sortKey)}>
        {label}
        {/* Chevron SVG */}
        <svg
          width="8"
          height="8"
          viewBox="0 0 8 8"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ opacity: isActive ? 1 : 0.3 }}
        >
          {isActive && sortDir === "asc" ? (
            <path d="M4 2L7 6H1L4 2Z" fill="currentColor" />
          ) : (
            <path d="M4 6L1 2H7L4 6Z" fill="currentColor" />
          )}
        </svg>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat cell helper
// ---------------------------------------------------------------------------
function StatCell({
  value,
  format,
  hideOnMobile = false,
  width,
}: {
  value: number | null | undefined;
  format: (v: number) => string;
  hideOnMobile?: boolean;
  width: number;
}) {
  const isNull = value == null;
  return (
    <div
      style={{ width, flexShrink: 0, textAlign: "right" }}
      className={hideOnMobile ? "hidden sm:block" : undefined}
    >
      {isNull ? (
        <span style={{ color: "#555555", fontSize: 12 }}>—</span>
      ) : (
        <span style={{ color: "#888888", fontSize: 12, fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}>
          {format(value as number)}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------
function StandingRow({
  entry,
  isMe,
  weekPoints,
  stats,
  animationDelay,
  onClick,
}: {
  entry: LeaderboardEntry;
  isMe: boolean;
  weekPoints: number | null;
  stats: MemberStats | null;
  animationDelay: number;
  onClick: () => void;
}) {
  const isFirst = entry.rank === 1;
  const initials = getInitials(entry.username);

  // Styles for the position badge
  const posBadgeStyle: React.CSSProperties = isMe
    ? {
        width: 24, height: 24, borderRadius: 6,
        background: "rgba(252,212,0,0.2)",
        border: "1px solid rgba(252,212,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }
    : isFirst
    ? {
        width: 24, height: 24, borderRadius: 6,
        background: "#FCD400",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }
    : {
        width: 24, height: 24, borderRadius: 6,
        background: "#2A2A2A",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      };

  const posNumStyle: React.CSSProperties = {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: 13, fontWeight: 700,
    color: isMe ? "#FCD400" : isFirst ? "#111111" : "#555555",
  };

  // Avatar
  const avatarStyle: React.CSSProperties = isMe
    ? {
        width: 32, height: 32, borderRadius: "50%",
        background: "#FCD400",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 12, fontWeight: 700, color: "#111111",
        flexShrink: 0,
      }
    : {
        width: 32, height: 32, borderRadius: "50%",
        background: "#2A2A2A",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 12, color: "#666666",
        flexShrink: 0,
      };

  // Row container
  const rowStyle: React.CSSProperties = isMe
    ? {
        background: "#1E1A00",
        border: "1px solid rgba(252,212,0,0.25)",
        borderRadius: 10,
        padding: "14px 20px",
        display: "flex", alignItems: "center", gap: 12,
        cursor: "pointer", width: "100%", textAlign: "left",
        animationDelay: `${animationDelay}ms`,
      }
    : {
        background: "#1A1A1A",
        border: "1px solid #2A2A2A",
        borderRadius: 10,
        padding: "14px 20px",
        display: "flex", alignItems: "center", gap: 12,
        cursor: "pointer", width: "100%", textAlign: "left",
        animationDelay: `${animationDelay}ms`,
      };

  const usernameStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 13,
    fontWeight: isMe ? 700 : 600,
    color: isMe ? "#FCD400" : isFirst ? "#E8D8A0" : "#888888",
  };

  const teamStyle: React.CSSProperties = {
    fontSize: 11,
    color: isMe ? "#8A7800" : "#444444",
  };

  const weekPtsStyle: React.CSSProperties = {
    fontSize: 13, fontWeight: 600, textAlign: "right",
    color: isMe ? "#FCD400" : "#888888",
  };

  const totalPtsStyle: React.CSSProperties = {
    fontFamily: "'Barlow Condensed', sans-serif",
    fontSize: 20, fontWeight: 700, textAlign: "right",
    color: isMe ? "#FCD400" : isFirst ? "#FCD400" : "#666666",
  };

  return (
    <button className="standing-row animate-cascade-in" style={rowStyle} onClick={onClick}>
      {/* POS — 52px */}
      <div style={{ width: 52, display: "flex", alignItems: "center", justifyContent: "flex-start", flexShrink: 0 }}>
        <div style={posBadgeStyle}>
          <span style={posNumStyle}>{entry.rank}</span>
        </div>
      </div>

      {/* MANAGER — flex-grow */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
        <div style={avatarStyle}>
          {entry.avatar_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={entry.avatar_url} alt={entry.username ?? "avatar"} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
            : initials
          }
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={usernameStyle} className="truncate">
              {entry.username ?? "Manager"}
            </span>
            {isMe && (
              <span
                style={{
                  background: "#FCD400", borderRadius: 3, padding: "1px 5px",
                  fontSize: 9, fontWeight: 700, color: "#111111",
                  flexShrink: 0,
                }}
              >
                TÚ
              </span>
            )}
          </div>
          <div style={teamStyle}>{entry.player_count} jugadores</div>
        </div>
      </div>

      {/* AVG PTS — 80px, desktop only */}
      <StatCell
        value={stats?.avg_pts_per_week}
        format={(v) => v.toFixed(1)}
        width={80}
        hideOnMobile
      />

      {/* PTS ESTA SEM. — 90px */}
      <div style={{ width: 90, flexShrink: 0, textAlign: "right" }}>
        {weekPoints !== null
          ? <span style={weekPtsStyle}>{Math.round(weekPoints)}</span>
          : <span style={{ fontSize: 13, fontWeight: 600, color: "#555555" }}>—</span>
        }
      </div>

      {/* TOTAL — 80px */}
      <div style={{ width: 80, flexShrink: 0, textAlign: "right" }}>
        <span style={totalPtsStyle}>{Math.round(entry.total_points)}</span>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function StandingsPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const initialLoadDone = useRef(false);
  const [entries, setEntries]               = useState<LeaderboardEntry[]>([]);
  const [detailedEntries, setDetailedEntries] = useState<DetailedLeaderboardEntry[]>([]);
  const [league, setLeague]                 = useState<League | null>(null);
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState<string | null>(null);
  const [myMemberId, setMyMemberId]         = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<{ id: string; name: string } | null>(null);
  const [sortKey, setSortKey]               = useState<SortKey>("total_points");
  const [sortDir, setSortDir]               = useState<"asc" | "desc">("desc");
  const [animationKey, setAnimationKey]     = useState(0);
  const [selectedWeek, setSelectedWeek]     = useState<number | null>(null);
  const [currentWeek, setCurrentWeek]       = useState<number | null>(null);
  const [availableWeeks, setAvailableWeeks] = useState<number[]>([]);

  // Build a stats lookup map from detailedEntries
  const statsMap = useMemo(() => {
    const map = new Map<string, MemberStats>();
    for (const d of detailedEntries) {
      map.set(d.member_id, d.stats);
    }
    return map;
  }, [detailedEntries]);

  // Sorted entries — client-side, derived from detailedEntries when available, else entries
  // When a week is selected, always use entries (which have week_points from the re-fetch)
  const sortedEntries = useMemo(() => {
    const base: LeaderboardEntry[] = (selectedWeek == null && detailedEntries.length > 0) ? detailedEntries : entries;
    if (sortKey === "total_points") {
      const sorted = [...base].sort((a, b) =>
        sortDir === "desc"
          ? b.total_points - a.total_points
          : a.total_points - b.total_points,
      );
      return sorted;
    }
    return [...base].sort((a, b) => {
      const statsA = statsMap.get(a.member_id);
      const statsB = statsMap.get(b.member_id);
      const valA = statsA ? (statsA[sortKey] ?? -Infinity) : -Infinity;
      const valB = statsB ? (statsB[sortKey] ?? -Infinity) : -Infinity;
      return sortDir === "desc" ? (valB as number) - (valA as number) : (valA as number) - (valB as number);
    });
  }, [entries, detailedEntries, statsMap, sortKey, sortDir, selectedWeek]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
    // Re-trigger cascade animation
    setAnimationKey((k) => k + 1);
  }

  useEffect(() => {
    initialLoadDone.current = false;
    Promise.all([
      api.leagues.get(leagueId).catch(() => null),
      api.scoring.leaderboard(leagueId),
    ])
      .then(([lg, board]: [League | null, LeaderboardResponse]) => {
        if (lg?.member) setMyMemberId(lg.member.id);
        setLeague(lg);
        setEntries(board.entries);
        setAvailableWeeks(board.available_weeks);
        setCurrentWeek(board.current_week);
        // Inicializar en la semana actual; el useEffect de selectedWeek lo re-fetcheará con week_points
        setSelectedWeek(board.current_week);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => {
        setLoading(false);
        initialLoadDone.current = true;
      });
  }, [leagueId]);

  // Phase 2: load detailed stats non-blocking
  useEffect(() => {
    if (loading) return; // wait until phase 1 is done
    api.scoring.detailedLeaderboard(leagueId)
      .then((detailed) => {
        setDetailedEntries(detailed);
        setAnimationKey((k) => k + 1); // re-trigger cascade when stats arrive
      })
      .catch(() => {
        // Graceful degradation — keep entries without stats
      });
  }, [leagueId, loading]);

  // Re-fetch leaderboard cuando cambia la semana seleccionada (skip durante carga inicial)
  useEffect(() => {
    if (!initialLoadDone.current) return;
    api.scoring.leaderboard(leagueId, selectedWeek)
      .then((board: LeaderboardResponse) => {
        setEntries(board.entries);
        setAnimationKey((k) => k + 1);
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId, selectedWeek]);

  const headerLabelStyle: React.CSSProperties = {
    fontFamily: "'Space Grotesk', sans-serif",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.08em",
    color: "#333333",
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">

        {/* ---- Page header ---- */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
          <div>
            {league && (
              <p style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 10, fontWeight: 700,
                letterSpacing: "0.1em", color: "#333333",
                textTransform: "uppercase", marginBottom: 4,
              }}>
                {league.name}
              </p>
            )}
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 30, fontWeight: 700, color: "#F0E8D0",
              lineHeight: 1.1,
            }}>
              Clasificación
            </h1>
          </div>

          {/* Week navigator */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0, marginTop: 4 }}>
            <button
              onClick={() => {
                if (selectedWeek === null) {
                  // From Total → go to currentWeek
                  setSelectedWeek(currentWeek);
                } else if (selectedWeek > (availableWeeks[0] ?? 1)) {
                  setSelectedWeek((w) => (w as number) - 1);
                }
              }}
              disabled={selectedWeek !== null && selectedWeek <= (availableWeeks[0] ?? 1)}
              style={{ background: "none", border: "1px solid #333", color: "#aaa", borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
            >
              ‹
            </button>
            <div style={{ textAlign: "center", minWidth: 80 }}>
              <span style={{ fontSize: 11, color: "#555555", display: "block" }}>Jornada</span>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}>
                {selectedWeek != null ? `${selectedWeek} / ${currentWeek ?? "—"}` : "Total"}
              </div>
            </div>
            <button
              onClick={() => setSelectedWeek((w) => (w != null && w < (currentWeek ?? 0) ? w + 1 : null))}
              disabled={selectedWeek === null || selectedWeek >= (currentWeek ?? 0)}
              style={{ background: "none", border: "1px solid #333", color: "#aaa", borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
            >
              ›
            </button>
            <button
              onClick={() => setSelectedWeek(null)}
              style={{
                background: selectedWeek === null ? "#FCD400" : "none",
                color: selectedWeek === null ? "#000" : "#aaa",
                border: "1px solid #333",
                borderRadius: 4,
                padding: "2px 8px",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              Total
            </button>
          </div>
        </div>

        {/* ---- Loading skeleton ---- */}
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-14 rounded-xl animate-pulse"
                style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}
              />
            ))}
          </div>
        )}

        {/* ---- Error ---- */}
        {error && <p className="text-sm text-center py-20" style={{ color: "var(--text-muted)" }}>{error}</p>}

        {/* ---- Empty state ---- */}
        {!loading && !error && entries.length === 0 && (
          <div className="py-20 text-center">
            <p className="font-medium mb-2" style={{ color: "#888888" }}>Sin datos aún</p>
            <p className="text-sm" style={{ color: "#555555" }}>Los puntos se actualizan tras cada jornada de LEC.</p>
          </div>
        )}

        {/* ---- Table ---- */}
        {!loading && !error && entries.length > 0 && (
          <div>
            {/* Table header */}
            <div style={{
              display: "flex", alignItems: "center", gap: 12,
              paddingInline: 20, marginBottom: 8,
            }}>
              <div style={{ width: 52, flexShrink: 0 }}>
                <span style={headerLabelStyle}>POS</span>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={headerLabelStyle}>MANAGER</span>
              </div>

              {/* Avg Pts header — desktop only */}
              <SortableHeader
                label="AVG PTS"
                sortKey="avg_pts_per_week"
                activeSortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
                width={80}
                hideOnMobile
              />

              <div style={{ width: 90, flexShrink: 0, textAlign: "right" }}>
                <span style={headerLabelStyle}>
                  {selectedWeek != null ? `J${selectedWeek}` : "PTS SEM."}
                </span>
              </div>

              {/* TOTAL header with sort */}
              <SortableHeader
                label="TOTAL"
                sortKey="total_points"
                activeSortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
                width={80}
              />
            </div>

            {/* Rows — animationKey forces re-render to restart CSS animation */}
            <div key={animationKey} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {sortedEntries.map((e, index) => (
                <StandingRow
                  key={e.member_id}
                  entry={e}
                  isMe={e.member_id === myMemberId}
                  weekPoints={selectedWeek != null ? (e.week_points ?? null) : null}
                  stats={statsMap.get(e.member_id) ?? null}
                  animationDelay={index * 60}
                  onClick={() => setSelectedMember({ id: e.member_id, name: e.username ?? "Manager" })}
                />
              ))}
            </div>
          </div>
        )}
      </main>

      {selectedMember && (
        <TeamModal
          leagueId={leagueId}
          memberId={selectedMember.id}
          memberName={selectedMember.name}
          onClose={() => setSelectedMember(null)}
        />
      )}
    </div>
  );
}

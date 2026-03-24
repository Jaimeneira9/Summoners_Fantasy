"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { api, type LeaderboardEntry, type MemberRoster, type League } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";

gsap.registerPlugin(useGSAP);

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
                    {data.member.total_points.toFixed(1)}
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
                        {(rp.split_points ?? 0).toFixed(1)}
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

function DeltaBadge({ value }: { value: number | null }) {
  if (value === null) return <span style={{ color: "#555555", fontSize: 11, fontWeight: 600 }}>—</span>;
  if (value === 0) return <span style={{ color: "#555555", fontSize: 11, fontWeight: 600 }}>—</span>;
  const positive = value > 0;
  return (
    <span style={{ color: positive ? "#22C55E" : "#EF4444", fontSize: 11, fontWeight: 600 }}>
      {positive ? "+" : ""}{value.toFixed(1)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Row component
// ---------------------------------------------------------------------------
function StandingRow({
  entry,
  isMe,
  weekPoints,
  onClick,
}: {
  entry: LeaderboardEntry;
  isMe: boolean;
  weekPoints: number | null;
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
      }
    : {
        background: "#1A1A1A",
        border: "1px solid #2A2A2A",
        borderRadius: 10,
        padding: "14px 20px",
        display: "flex", alignItems: "center", gap: 12,
        cursor: "pointer", width: "100%", textAlign: "left",
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
    <button className="standing-row" style={rowStyle} onClick={onClick}>
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

      {/* PTS ESTA SEM. — 120px */}
      <div style={{ width: 120, flexShrink: 0, textAlign: "right" }}>
        {weekPoints !== null
          ? <span style={weekPtsStyle}>{weekPoints.toFixed(1)}</span>
          : <span style={{ fontSize: 13, fontWeight: 600, color: "#555555" }}>—</span>
        }
      </div>

      {/* TOTAL — 100px */}
      <div style={{ width: 100, flexShrink: 0, textAlign: "right" }}>
        <span style={totalPtsStyle}>{entry.total_points.toFixed(1)}</span>
      </div>

      {/* Δ — 60px */}
      <div style={{ width: 60, flexShrink: 0, textAlign: "right" }}>
        <DeltaBadge value={null} />
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function StandingsPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const [entries, setEntries]       = useState<LeaderboardEntry[]>([]);
  const [league, setLeague]         = useState<League | null>(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [myMemberId, setMyMemberId] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<{ id: string; name: string } | null>(null);
  const rowsRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!entries.length) return;
      gsap.from(".standing-row", {
        autoAlpha: 0,
        y: 20,
        duration: 0.5,
        ease: "power2.out",
        stagger: 0.06,
      });
    },
    { scope: rowsRef, dependencies: [entries] }
  );

  useEffect(() => {
    Promise.all([
      api.leagues.get(leagueId).catch(() => null),
      api.scoring.leaderboard(leagueId),
    ])
      .then(([lg, board]) => {
        if (lg?.member) setMyMemberId(lg.member.id);
        setLeague(lg);
        setEntries(board as LeaderboardEntry[]);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

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

          {/* Week badge */}
          <div style={{
            background: "#1A1A1A",
            border: "1px solid #2A2A2A",
            borderRadius: 8,
            padding: "8px 14px",
            display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2,
            flexShrink: 0, marginTop: 4,
          }}>
            <span style={{ fontSize: 11, color: "#555555" }}>Semana</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}>
              — / —
            </span>
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
              display: "flex", alignItems: "center",
              paddingInline: 20, marginBottom: 8,
            }}>
              <div style={{ width: 52, flexShrink: 0 }}>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#333333",
                  textTransform: "uppercase",
                }}>POS</span>
              </div>
              <div style={{ flex: 1 }}>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#333333",
                  textTransform: "uppercase",
                }}>MANAGER</span>
              </div>
              <div style={{ width: 120, flexShrink: 0, textAlign: "right" }}>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#333333",
                  textTransform: "uppercase",
                }}>PTS ESTA SEM.</span>
              </div>
              <div style={{ width: 100, flexShrink: 0, textAlign: "right" }}>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#333333",
                  textTransform: "uppercase",
                }}>TOTAL</span>
              </div>
              <div style={{ width: 60, flexShrink: 0, textAlign: "right" }}>
                <span style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.08em", color: "#333333",
                  textTransform: "uppercase",
                }}>Δ</span>
              </div>
            </div>

            {/* Rows */}
            <div ref={rowsRef} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {entries.map((e) => (
                <StandingRow
                  key={e.member_id}
                  entry={e}
                  isMe={e.member_id === myMemberId}
                  weekPoints={null}
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

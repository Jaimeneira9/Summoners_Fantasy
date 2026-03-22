"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type LeaderboardEntry, type MemberRoster, type League } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";

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

  useEffect(() => {
    api.leagues.memberRoster(leagueId, memberId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [leagueId, memberId]);

  const SLOT_ORDER = ["starter_1","starter_2","starter_3","starter_4","starter_5","coach","bench_1","bench_2"];

  return (
    <div
      className="fixed inset-0 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4"
      style={{ background: "rgba(26,28,26,0.5)" }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto animate-slide-up"
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-medium)",
          boxShadow: "0 8px 40px rgba(26,28,26,0.15)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between p-4 border-b"
          style={{ borderBottomColor: "var(--border-subtle)" }}
        >
          <div>
            <p className="font-bold" style={{ color: "var(--text-primary)" }}>{memberName}</p>
            {data && (
              <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>
                <span className="font-mono font-bold" style={{ color: "var(--color-primary)" }}>
                  {data.member.total_points.toFixed(1)}
                </span>
                {" "}pts · {data.players.length} jugadores
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--text-muted)"; }}
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="p-6 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 rounded-lg animate-pulse" style={{ background: "var(--bg-surface)" }} />
            ))}
          </div>
        ) : !data || data.players.length === 0 ? (
          <div className="p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Sin jugadores en el equipo.</div>
        ) : (
          <div className="p-4 space-y-2">
            {[...data.players]
              .filter((rp) => !rp.slot.startsWith("bench"))
              .sort((a, b) => SLOT_ORDER.indexOf(a.slot) - SLOT_ORDER.indexOf(b.slot))
              .map((rp, i) => {
                const p = rp.players;
                const rc = ROLE_COLORS[p.role] ?? ROLE_COLORS.coach;
                return (
                  <div
                    key={i}
                    className="flex items-center gap-3 border rounded-xl px-4 py-3 transition-all"
                    style={{
                      background: "var(--bg-surface)",
                      borderColor: "var(--border-subtle)",
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(252,212,0,0.25)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border-subtle)"; }}
                  >
                    <div
                      className="w-10 h-10 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
                      style={{ background: "var(--bg-panel)" }}
                    >
                      {p.image_url
                        // eslint-disable-next-line @next/next/no-img-element
                        ? <img src={p.image_url} alt={p.name} className="w-full h-full object-cover object-top" />
                        : <RoleIcon role={p.role} className={`w-5 h-5 ${rc.text}`} />
                      }
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm truncate" style={{ color: "var(--text-primary)" }}>{p.name}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{p.team}</p>
                    </div>
                    <div className={`text-[10px] font-bold px-2 py-0.5 rounded ${rc.bg} ${rc.text} flex-shrink-0`}>
                      {ROLE_LABEL[p.role] ?? p.role.toUpperCase()}
                    </div>
                    <div className="text-right flex-shrink-0 min-w-[56px]">
                      <p className="font-mono text-sm font-bold" style={{ color: "var(--color-primary)" }}>
                        {(rp.split_points ?? 0).toFixed(1)}
                      </p>
                      <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>pts</p>
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
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
  const initials = getInitials(entry.display_name);

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
    <button style={rowStyle} onClick={onClick}>
      {/* POS — 52px */}
      <div style={{ width: 52, display: "flex", alignItems: "center", justifyContent: "flex-start", flexShrink: 0 }}>
        <div style={posBadgeStyle}>
          <span style={posNumStyle}>{entry.rank}</span>
        </div>
      </div>

      {/* MANAGER — flex-grow */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
        <div style={avatarStyle}>{initials}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={usernameStyle} className="truncate">
              {entry.display_name ?? "Manager"}
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
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {entries.map((e) => (
                <StandingRow
                  key={e.member_id}
                  entry={e}
                  isMe={e.member_id === myMemberId}
                  weekPoints={null}
                  onClick={() => setSelectedMember({ id: e.member_id, name: e.display_name ?? "Manager" })}
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

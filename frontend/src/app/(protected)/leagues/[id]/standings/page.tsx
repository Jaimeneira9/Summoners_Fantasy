"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type LeaderboardEntry, type MemberRoster } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";

const RANK_STYLES = [
  // rank 1 — gold
  { medal: "🥇", glow: "shadow-[0_0_20px_rgba(234,179,8,0.15)]", border: "border-yellow-400/30", bg: "bg-yellow-400/5" },
  // rank 2 — silver
  { medal: "🥈", glow: "shadow-[0_0_16px_rgba(148,163,184,0.10)]", border: "border-slate-400/25", bg: "bg-slate-400/5" },
  // rank 3 — bronze
  { medal: "🥉", glow: "shadow-[0_0_12px_rgba(180,83,9,0.08)]", border: "border-orange-700/25", bg: "bg-orange-900/5" },
];

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
          background: "white",
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
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(107,33,232,0.25)"; }}
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
// Page
// ---------------------------------------------------------------------------
export default function StandingsPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const [entries, setEntries]       = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [myMemberId, setMyMemberId] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<{ id: string; name: string } | null>(null);

  // PERF FIX: parallel fetch with Promise.all
  useEffect(() => {
    Promise.all([
      api.leagues.get(leagueId).catch(() => null),
      api.scoring.leaderboard(leagueId),
    ])
      .then(([league, board]) => {
        if (league?.member) setMyMemberId(league.member.id);
        setEntries(board as LeaderboardEntry[]);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  // Reorder for podium: [2nd, 1st, 3rd]
  const podiumEntries = entries.length >= 3
    ? ([entries[1], entries[0], entries[2]] as LeaderboardEntry[])
    : null;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">
        <h1
          className="text-xl sm:text-2xl font-bold mb-1"
          style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text-primary)" }}
        >
          Clasificación
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>Toca un manager para ver su equipo.</p>

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-14 rounded-xl animate-pulse"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
              />
            ))}
          </div>
        )}

        {error && <p className="text-sm text-center py-20" style={{ color: "var(--text-muted)" }}>{error}</p>}

        {!loading && !error && entries.length === 0 && (
          <div className="py-20 text-center">
            <span className="text-4xl mb-4 block">🏆</span>
            <p className="font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Sin datos aún</p>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Los puntos se actualizan tras cada jornada de LEC.</p>
          </div>
        )}

        {/* Podio top 3 */}
        {!loading && !error && podiumEntries && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            {podiumEntries.map((e, i) => {
              const podiumRank = [2, 1, 3][i];
              const style = RANK_STYLES[podiumRank - 1];
              const heights = ["h-24", "h-32", "h-20"];
              const isMe = e.member_id === myMemberId;
              return (
                <button
                  key={e.member_id}
                  onClick={() => setSelectedMember({ id: e.member_id, name: e.display_name ?? "Manager" })}
                  className={`flex flex-col items-center justify-end ${heights[i]} rounded-xl border ${style.border} ${style.bg} ${style.glow} pb-3 px-2 transition-all duration-200 hover:scale-[1.03] cursor-pointer w-full`}
                >
                  <span className="text-2xl mb-1">{style.medal}</span>
                  <p
                    className="text-xs font-bold truncate w-full text-center"
                    style={{ color: isMe ? "var(--color-primary)" : "var(--text-primary)" }}
                  >
                    {e.display_name ?? "Manager"}
                  </p>
                  <p className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                    {e.total_points.toFixed(1)} pts
                  </p>
                </button>
              );
            })}
          </div>
        )}

        {/* Lista completa */}
        {!loading && !error && entries.length > 0 && (
          <div className="space-y-1.5">
            {entries.map((e) => {
              const isMe = e.member_id === myMemberId;
              const style = e.rank <= 3 ? RANK_STYLES[e.rank - 1] : null;
              return (
                <button
                  key={e.member_id}
                  onClick={() => setSelectedMember({ id: e.member_id, name: e.display_name ?? "Manager" })}
                  className={`flex items-center gap-3 sm:gap-4 px-4 py-3 rounded-xl border w-full text-left transition-all duration-200 hover:-translate-y-0.5 active:scale-[0.99]
                    ${style ? `${style.bg} ${style.border}` : ""}`}
                  style={isMe ? {
                    background: "var(--color-primary-bg)",
                    borderColor: "rgba(107,33,232,0.25)",
                  } : !style ? {
                    background: "var(--bg-surface)",
                    borderColor: "var(--border-subtle)",
                  } : undefined}
                  onMouseEnter={(e_) => {
                    if (!isMe && !style) {
                      (e_.currentTarget as HTMLButtonElement).style.borderColor = "rgba(107,33,232,0.2)";
                    }
                  }}
                  onMouseLeave={(e_) => {
                    if (!isMe && !style) {
                      (e_.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-subtle)";
                    }
                  }}
                >
                  <span
                    className="w-7 text-center font-bold text-sm flex-shrink-0"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {e.rank <= 3 && style ? style.medal : e.rank}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p
                      className="font-semibold text-sm truncate"
                      style={{ color: isMe ? "var(--color-primary)" : "var(--text-primary)" }}
                    >
                      {e.display_name ?? "Manager"}
                      {isMe && (
                        <span className="text-xs font-normal ml-1.5" style={{ color: "var(--text-muted)" }}>(tú)</span>
                      )}
                    </p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>{e.player_count} jugadores</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p
                      className="font-mono text-sm font-bold"
                      style={{ color: isMe ? "var(--color-primary)" : "var(--text-primary)" }}
                    >
                      {e.total_points.toFixed(1)} pts
                    </p>
                    {e.remaining_budget !== undefined && (
                      <p className="font-mono text-xs" style={{ color: "var(--color-gold-dark)" }}>
                        {e.remaining_budget.toFixed(1)}M
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
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


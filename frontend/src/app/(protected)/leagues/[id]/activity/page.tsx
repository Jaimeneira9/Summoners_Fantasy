"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type ActivityEvent } from "@/lib/api";
import { RoleIcon, ROLE_COLORS } from "@/components/RoleIcon";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `hace ${d}d`;
  if (h > 0) return `hace ${h}h`;
  if (m > 0) return `hace ${m}m`;
  return "ahora";
}

const TYPE_CONFIG: Record<string, { icon: string; colorClass: string; label: (e: ActivityEvent) => string }> = {
  buy: {
    icon: "↑",
    colorClass: "text-green-600 bg-green-500/10 border-green-500/20",
    label: (e) => `${e.buyer_name ?? "Alguien"} ha fichado a ${e.player_name} por ${e.price.toFixed(1)}M`,
  },
  bid_win: {
    icon: "⚡",
    colorClass: "text-yellow-600 bg-yellow-500/10 border-yellow-500/20",
    label: (e) => `${e.buyer_name ?? "Alguien"} ganó la puja de ${e.player_name} por ${e.price.toFixed(1)}M`,
  },
  sell: {
    icon: "↓",
    colorClass: "text-red-600 bg-red-500/10 border-red-500/20",
    label: (e) => `${e.seller_name ?? "Alguien"} vendió a ${e.player_name} por ${e.price.toFixed(1)}M`,
  },
  trade: {
    icon: "⇄",
    colorClass: "text-purple-600 bg-purple-500/10 border-purple-500/20",
    label: (e) => `${e.buyer_name ?? "Alguien"} y ${e.seller_name ?? "alguien"} intercambiaron a ${e.player_name}`,
  },
};

export default function ActivityPage() {
  const { id: leagueId } = useParams<{ id: string }>();
  const [events, setEvents]   = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    api.activity.feed(leagueId)
      .then(setEvents)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId]);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <main className="max-w-2xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-10">
        <h1
          className="text-xl sm:text-2xl font-bold mb-1"
          style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text-primary)" }}
        >
          Actividad reciente
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>Todos los movimientos de la liga.</p>

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-xl animate-pulse"
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
              />
            ))}
          </div>
        )}

        {error && (
          <div className="py-20 text-center">
            <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>{error}</p>
          </div>
        )}

        {!loading && !error && events.length === 0 && (
          <div className="py-20 text-center">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: "var(--bg-panel)", border: "1px solid var(--border-medium)" }}
            >
              <svg className="w-7 h-7" style={{ color: "var(--text-muted)" }} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="font-medium mb-2" style={{ color: "var(--text-secondary)" }}>Sin actividad todavía</p>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>Los fichajes y ventas aparecerán aquí.</p>
          </div>
        )}

        {!loading && !error && events.length > 0 && (
          <div className="space-y-2">
            {events.map((e) => {
              const config = TYPE_CONFIG[e.type] ?? TYPE_CONFIG.buy;
              const roleColor = ROLE_COLORS[e.player_role] ?? ROLE_COLORS.coach;
              return (
                <div
                  key={e.id}
                  className="flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-200 group"
                  style={{
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border-subtle)",
                  }}
                  onMouseEnter={(e_) => { (e_.currentTarget as HTMLDivElement).style.borderColor = "rgba(107,33,232,0.2)"; }}
                  onMouseLeave={(e_) => { (e_.currentTarget as HTMLDivElement).style.borderColor = "var(--border-subtle)"; }}
                >
                  {/* Event type icon */}
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0 border ${config.colorClass}`}>
                    {config.icon}
                  </div>

                  {/* Player avatar */}
                  <div
                    className="w-9 h-9 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
                    style={{ background: "var(--bg-panel)", border: "1px solid var(--border-medium)" }}
                  >
                    {e.player_image_url
                      // eslint-disable-next-line @next/next/no-img-element
                      ? <img src={e.player_image_url} alt={e.player_name} className="w-full h-full object-cover object-top" />
                      : <RoleIcon role={e.player_role} className={`w-4 h-4 ${roleColor.text}`} />
                    }
                  </div>

                  {/* Message */}
                  <p
                    className="flex-1 text-sm leading-snug min-w-0 transition-colors"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {config.label(e)}
                  </p>

                  {/* Timestamp */}
                  <span className="text-xs flex-shrink-0 font-mono whitespace-nowrap" style={{ color: "var(--text-muted)" }}>
                    {timeAgo(e.executed_at)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}


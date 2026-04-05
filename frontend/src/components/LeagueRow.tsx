"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type League } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

/** Deterministically pick one of our role-ish accent colors from a string */
function leagueAccentColor(name: string): string {
  const palette = ["#3b82f6", "#22c55e", "#a855f7", "#eab308", "#0ea5e9", "#ef4444"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return palette[hash % palette.length];
}

export function LeagueRow({ league }: { league: League }) {
  const router = useRouter();
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [deleting, setDeleting]           = useState(false);
  const [hovered, setHovered]             = useState(false);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setCurrentUserId(data.user?.id ?? null));
  }, []);

  const isOwner   = currentUserId === league.owner_id;
  const accent    = leagueAccentColor(league.name);

  const handleDelete = async () => {
    if (!confirm(`¿Eliminar la liga "${league.name}"? Esta acción no se puede deshacer.`)) return;
    setDeleting(true);
    try {
      await api.leagues.delete(league.id);
      router.refresh();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al eliminar");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-200"
      style={{
        background: hovered ? "var(--bg-panel)" : "var(--bg-surface)",
        borderTop: "1px solid var(--border-subtle)",
        borderRight: "1px solid var(--border-subtle)",
        borderBottom: "1px solid var(--border-subtle)",
        borderLeft: `4px solid ${accent}`,
        boxShadow: hovered ? "0 4px 20px rgba(0,0,0,0.4)" : "none",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Main card body */}
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          {/* Left: name + nick */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-black text-base leading-tight truncate" style={{ color: "var(--text-primary)" }}>
                {league.name}
              </p>
              {isOwner && (
                <span
                  className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md"
                  style={{
                    background: "rgba(107,33,232,0.1)",
                    color: "var(--color-primary)",
                    border: "1px solid rgba(107,33,232,0.2)",
                  }}
                >
                  Admin
                </span>
              )}
            </div>

            {/* Invite code */}
            <p className="text-[11px] mt-0.5 font-mono" style={{ color: "var(--text-muted)" }}>
              {league.invite_code}
            </p>
          </div>

          {/* Right: budget + points */}
          {league.member && (
            <div className="text-right flex-shrink-0">
              <p className="font-mono text-sm font-bold" style={{ color: "var(--color-gold-dark)" }}>
                {league.member.remaining_budget.toFixed(1)}M
              </p>
              <p className="text-xs mt-0.5 font-mono" style={{ color: "var(--text-secondary)" }}>
                {Math.round(league.member.total_points)} pts
              </p>
            </div>
          )}
        </div>

        {/* Navigation links */}
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <NavLink href={`/leagues/${league.id}/lineup`}>Mi equipo</NavLink>
          <NavLink href={`/leagues/${league.id}/market`}>Mercado</NavLink>
          <NavLink href={`/leagues/${league.id}/standings`}>Clasificación</NavLink>
          <NavLink href={`/leagues/${league.id}/activity`}>Actividad</NavLink>

          {/* Entrar CTA — pushes to the right */}
          <Link
            href={`/leagues/${league.id}/lineup`}
            className="ml-auto text-xs font-bold text-white rounded-lg px-3 py-1.5 transition-all active:scale-95 flex items-center gap-1 hover:brightness-90"
            style={{ background: "linear-gradient(135deg, var(--color-primary), var(--color-primary-light))" }}
          >
            Entrar
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Link>

          {isOwner && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-3 py-1.5 text-xs rounded-lg transition-all active:scale-95 disabled:opacity-40"
              style={{
                border: "1px solid rgba(239,68,68,0.2)",
                color: deleting ? "var(--text-muted)" : "rgba(239,68,68,0.6)",
              }}
              onMouseEnter={(e) => {
                if (!deleting) (e.currentTarget as HTMLButtonElement).style.color = "rgb(220,38,38)";
              }}
              onMouseLeave={(e) => {
                if (!deleting) (e.currentTarget as HTMLButtonElement).style.color = "rgba(239,68,68,0.6)";
              }}
            >
              {deleting ? "Eliminando…" : "Eliminar"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 text-xs rounded-lg transition-all active:scale-95 font-medium border-b-2 border-transparent pb-1"
      style={{
        color: "var(--text-secondary)",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.color = "var(--color-primary)";
        (e.currentTarget as HTMLAnchorElement).style.borderBottomColor = "var(--color-primary)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLAnchorElement).style.color = "var(--text-secondary)";
        (e.currentTarget as HTMLAnchorElement).style.borderBottomColor = "transparent";
      }}
    >
      {children}
    </Link>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { api, type League } from "@/lib/api";

const NO_LIMIT_SENTINEL = 9999;

// ---------------------------------------------------------------------------
// Competition config
// ---------------------------------------------------------------------------

type CompetitionConfig = {
  accentFrom: string;
  accentTo: string;
  badgeBg: string;
  badgeText: string;
};

const COMPETITION_MAP: Record<string, CompetitionConfig> = {
  LEC: {
    accentFrom: "#6B46C1",
    accentTo: "#9333EA",
    badgeBg: "bg-purple-900",
    badgeText: "text-purple-300",
  },
  LCK: {
    accentFrom: "#1e40af",
    accentTo: "#3b82f6",
    badgeBg: "bg-blue-900",
    badgeText: "text-blue-300",
  },
  LPL: {
    accentFrom: "#9a1313",
    accentTo: "#ef4444",
    badgeBg: "bg-red-900",
    badgeText: "text-red-300",
  },
  LCS: {
    accentFrom: "#065f46",
    accentTo: "#10b981",
    badgeBg: "bg-emerald-900",
    badgeText: "text-emerald-300",
  },
  MSI: {
    accentFrom: "#92400e",
    accentTo: "#f59e0b",
    badgeBg: "bg-amber-900",
    badgeText: "text-amber-300",
  },
};

function getCompetitionConfig(competitionName: string): CompetitionConfig | null {
  const upper = competitionName.toUpperCase();
  for (const key of Object.keys(COMPETITION_MAP)) {
    if (upper.includes(key)) return COMPETITION_MAP[key];
  }
  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LeagueRow({ league }: { league: League }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  const config = getCompetitionConfig(league.competition_name);
  const isUnlimited =
    league.game_mode === "budget_pick" &&
    (league.max_members === null || league.max_members >= NO_LIMIT_SENTINEL);

  const maxDisplay = isUnlimited ? "∞" : String(league.max_members);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`¿Eliminar la liga "${league.name}"? Esta acción no se puede deshacer.`)) return;
    setDeleting(true);
    try {
      await api.leagues.delete(league.id);
      router.refresh();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error al eliminar");
    } finally {
      setDeleting(false);
    }
  };

  // Determine top strip gradient
  const accentFrom = config?.accentFrom ?? "#4b5563";
  const accentTo = config?.accentTo ?? "#6b7280";

  return (
    <div
      className="rounded-xl overflow-hidden cursor-pointer border border-white/5 hover:border-white/10 transition-all duration-200 group"
      style={{ background: "#0f0f1a" }}
      onClick={() => router.push(`/leagues/${league.id}/lineup`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(`/leagues/${league.id}/lineup`);
        }
      }}
    >
      {/* 3px colored top strip */}
      <div
        className="h-[3px] w-full"
        style={{ background: `linear-gradient(to right, ${accentFrom}, ${accentTo})` }}
      />

      {/* Card body */}
      <div className="px-4 py-3 flex items-center gap-4">
        {/* Logo container */}
        <div
          className="flex-shrink-0 w-11 h-11 rounded-lg flex items-center justify-center overflow-hidden"
          style={{ background: "#0a0a14" }}
        >
          {league.logo_url ? (
            <Image
              src={league.logo_url}
              alt={league.competition_name}
              width={44}
              height={44}
              className="object-contain"
            />
          ) : (
            <CrownIcon />
          )}
        </div>

        {/* Text content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-base font-bold text-white leading-tight truncate">
              {league.name}
            </span>
            {/* Competition badge */}
            <CompetitionBadge config={config} name={league.competition_name} />
            {/* Mode badge */}
            <ModeBadge gameMode={league.game_mode} />
          </div>

          {/* Stats bar */}
          <div className="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
            <span>
              Managers{" "}
              <span className="text-gray-300 font-medium">
                —/{maxDisplay}
              </span>
            </span>
            {league.member && (
              <>
                <span className="text-white/20">|</span>
                <span className="text-yellow-400 font-medium">
                  {Math.round(league.member.total_points)} pts
                </span>
                {league.game_mode === "budget_pick" && (
                  <>
                    <span className="text-white/20">|</span>
                    <span>{league.member.remaining_budget.toFixed(1)}M restante</span>
                  </>
                )}
              </>
            )}
          </div>
        </div>

        {/* Delete button (owner only visible on hover) */}
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 px-2 py-1 text-xs rounded-md border border-red-500/20 text-red-500/50 hover:text-red-400 hover:border-red-500/40 disabled:opacity-30"
          title="Eliminar liga"
        >
          {deleting ? "…" : "✕"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CompetitionBadge({
  config,
  name,
}: {
  config: CompetitionConfig | null;
  name: string;
}) {
  const label = name.length > 12 ? name.slice(0, 12) + "…" : name;
  const bg = config?.badgeBg ?? "bg-gray-800";
  const text = config?.badgeText ?? "text-gray-400";
  return (
    <span
      className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${bg} ${text}`}
    >
      {label}
    </span>
  );
}

function ModeBadge({ gameMode }: { gameMode: string }) {
  if (gameMode === "budget_pick") {
    return (
      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-400">
        PRESUPUESTO
      </span>
    );
  }
  return (
    <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-yellow-900/50 text-yellow-400">
      MERCADO
    </span>
  );
}

function CrownIcon() {
  return (
    <svg
      className="w-6 h-6 text-gray-500"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
      />
    </svg>
  );
}

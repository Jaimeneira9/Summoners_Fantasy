"use client";

import { useState } from "react";
import Link from "next/link";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";

// ---------------------------------------------------------------------------
// Team badge URL helper
// ---------------------------------------------------------------------------
const TEAM_BADGE_EXCEPTIONS: Record<string, string> = {
  "Movistar KOI": "koi.webp",
};

const STORAGE_BASE = "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

export function getTeamBadgeUrl(teamName: string): string {
  if (TEAM_BADGE_EXCEPTIONS[teamName]) {
    return STORAGE_BASE + TEAM_BADGE_EXCEPTIONS[teamName];
  }
  return STORAGE_BASE + teamName.toLowerCase().replace(/ /g, "-") + ".webp";
}

export interface MatchStat {
  match_id: string;
  week: number;
  kills: number;
  deaths: number;
  assists: number;
  cs_per_min: number;
  dpm?: number;
  match_points: number;
  gold_diff_at_15?: number | null;
  vision_score?: number | null;
  damage_share?: number | null;
}

export interface PlayerCardProps {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    current_price: number;
    image_url: string | null;
  };
  matchStats?: MatchStat[];
  totalPoints?: number;
  showPrice?: boolean;
  splitName?: string;
  leagueId?: string;
}

export function PlayerCard({ player, matchStats = [], totalPoints, showPrice = true, leagueId }: PlayerCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(
    matchStats.length > 0 ? matchStats[matchStats.length - 1].week : null
  );

  const roleColor = ROLE_COLORS[player.role] ?? ROLE_COLORS.coach;
  const roleHex   = getRoleColor(player.role);
  const selectedStat = matchStats.find((s) => s.week === selectedWeek) ?? null;

  const kda = selectedStat
    ? selectedStat.deaths === 0
      ? "∞"
      : ((selectedStat.kills + selectedStat.assists) / selectedStat.deaths).toFixed(2)
    : null;

  const goldDiff = selectedStat?.gold_diff_at_15 ?? null;
  const dmgPct   = selectedStat?.damage_share != null ? selectedStat.damage_share : null;
  const vision   = selectedStat?.vision_score ?? null;

  return (
    <div
      className="group relative rounded-xl overflow-hidden transition-all duration-300 cursor-pointer select-none"
      style={{
        borderLeft: `4px solid ${roleHex}`,
        background: "var(--bg-card)",
        boxShadow: expanded
          ? `0 0 0 1px rgba(255,255,255,0.07), 0 4px 24px rgba(0,0,0,0.4), -2px 0 12px ${roleHex}33`
          : undefined,
      }}
      onClick={() => setExpanded((v) => !v)}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Photo header — fixed 110px when expanded, aspect-[3/4] when closed  */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="relative w-full overflow-hidden transition-all duration-300"
        style={{
          height: expanded ? "110px" : undefined,
          aspectRatio: expanded ? undefined : "2/3",
          background: "var(--bg-surface)",
        }}
      >
        {player.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={player.image_url}
            alt={player.name}
            className="w-full h-full object-cover object-top grayscale group-hover:grayscale-0 group-hover:-translate-y-1 transition-all duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center" style={{ background: "var(--bg-surface)" }}>
            <RoleIcon role={player.role} className={`w-16 h-16 ${roleColor.text} opacity-20`} />
          </div>
        )}

        {/* Bottom gradient — always present so name is readable */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(to bottom, transparent 40%, rgba(30,27,30,0.95) 75%, var(--bg-card) 100%)" }}
        />

        {/* Role badge — top left */}
        <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md ${roleColor.bg} border ${roleColor.border} backdrop-blur-sm`}>
          <RoleIcon role={player.role} className={`w-3 h-3 ${roleColor.text}`} />
          <span className={`text-[9px] font-black ${roleColor.text}`}>{ROLE_LABEL[player.role] ?? player.role.toUpperCase()}</span>
        </div>

        {/* Team badge — bottom right of photo */}
        {player.team && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={getTeamBadgeUrl(player.team)}
            alt={player.team}
            className="absolute bottom-10 right-2 w-6 h-6 object-contain rounded-sm pointer-events-none"
            style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.8))" }}
          />
        )}

        {/* Name / team + price — bottom of photo */}
        <div className="absolute bottom-0 inset-x-0 px-3 py-2">
          <p
            className="font-black text-sm leading-tight truncate text-white uppercase tracking-tight"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            {player.name}
          </p>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className="text-white/50 text-[10px] truncate">{player.team}</span>
            {showPrice && (
              <span
                className="text-[10px] font-semibold"
                style={{ color: "var(--color-gold)" }}
              >
                💰 {player.current_price.toFixed(1)}M
              </span>
            )}
            {totalPoints !== undefined && (
              <span
                className="text-[10px] font-bold"
                style={{ color: totalPoints > 0 ? "var(--color-primary-light)" : "rgba(255,255,255,0.5)" }}
              >
                ● {totalPoints.toFixed(1)} pts
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Expanded stats panel                                                */}
      {/* ------------------------------------------------------------------ */}
      {expanded && (
        <div
          className="animate-fade-in"
          style={{ background: "rgba(0,0,0,0.3)" }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Total points banner */}
          {totalPoints !== undefined && (
            <div
              className="px-4 py-3 flex items-center justify-between border-b"
              style={{ borderColor: "rgba(255,255,255,0.07)" }}
            >
              <span className="text-white/40 text-[10px] uppercase tracking-widest font-semibold">Puntos totales</span>
              <div className="flex items-baseline gap-1">
                <span
                  className="font-black text-2xl"
                  style={{ color: totalPoints > 0 ? "var(--color-primary-light)" : "rgba(255,255,255,0.7)" }}
                >
                  {totalPoints.toFixed(1)}
                </span>
                <span className="text-white/30 text-xs">pts</span>
              </div>
            </div>
          )}

          {matchStats.length > 0 ? (
            <div className="px-3 pt-3 pb-4 space-y-3">
              {/* Jornada selector */}
              <select
                value={selectedWeek ?? ""}
                onChange={(e) => setSelectedWeek(Number(e.target.value))}
                className="w-full text-xs rounded-lg px-3 py-2 outline-none cursor-pointer font-semibold transition-colors"
                style={{
                  background: "rgba(255,255,255,0.07)",
                  border: "1px solid rgba(252,212,0,0.3)",
                  color: "var(--text-on-dark)",
                }}
              >
                {matchStats.map((s) => (
                  <option key={s.match_id} value={s.week} style={{ background: "var(--bg-card)" }}>
                    Jornada {s.week}
                  </option>
                ))}
              </select>

              {selectedStat ? (
                <div className="space-y-2">
                  {/* K / D / A — full-width row */}
                  <div
                    className="rounded-lg px-3 py-2.5 flex items-center justify-between"
                    style={{ background: "rgba(255,255,255,0.05)" }}
                  >
                    <span className="text-white/30 text-[10px] uppercase tracking-widest font-semibold">K / D / A</span>
                    <div className="font-mono text-sm font-bold flex items-center gap-1">
                      <span className="text-green-400">{selectedStat.kills}</span>
                      <span className="text-white/30">/</span>
                      <span className="text-red-400">{selectedStat.deaths}</span>
                      <span className="text-white/30">/</span>
                      <span className="text-blue-400">{selectedStat.assists}</span>
                    </div>
                  </div>

                  {/* Stats grid — 2 columns */}
                  <div className="grid grid-cols-2 gap-2">
                    {/* KDA ratio */}
                    <StatCell label="KDA" value={kda ?? "—"} valueClass="text-white/80" />

                    {/* CS/min */}
                    <StatCell label="CS/min" value={selectedStat.cs_per_min.toFixed(1)} valueClass="text-white/80" />

                    {/* DMG% with progress bar */}
                    {dmgPct !== null ? (
                      <div className="rounded-lg px-2.5 py-2 text-center" style={{ background: "rgba(255,255,255,0.05)" }}>
                        <p className="font-mono text-sm font-bold text-orange-400">{(dmgPct * 100).toFixed(0)}%</p>
                        <div className="mt-1.5 h-[3px] rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.07)" }}>
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${Math.min(dmgPct * 100, 100)}%`, background: "#f97316" }}
                          />
                        </div>
                        <p className="text-white/30 text-[9px] mt-1 uppercase tracking-wider">DMG%</p>
                      </div>
                    ) : null}

                    {/* Vision Score */}
                    {vision !== null ? (
                      <StatCell label="Visión" value={String(vision)} valueClass="text-purple-400" />
                    ) : null}

                    {/* Gold diff @ 15 */}
                    {goldDiff !== null ? (
                      <div className="col-span-2 rounded-lg px-3 py-2 flex items-center justify-between" style={{ background: "rgba(255,255,255,0.05)" }}>
                        <span className="text-white/30 text-[10px] uppercase tracking-widest font-semibold">Gold @15</span>
                        <span
                          className={`font-mono text-sm font-bold ${goldDiff >= 0 ? "text-green-400" : "text-red-400"}`}
                        >
                          {goldDiff >= 0 ? "+" : ""}{goldDiff.toLocaleString()}
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {/* Match points — prominent, accent colored */}
                  <div
                    className="rounded-lg px-3 py-2.5 flex items-center justify-between"
                    style={{
                      background: "var(--color-primary-bg)",
                      border: "1px solid rgba(252,212,0,0.25)",
                    }}
                  >
                    <span className="text-white/40 text-[10px] uppercase tracking-widest font-semibold">Puntos jornada</span>
                    <div className="flex items-baseline gap-1">
                      <span className="font-black text-lg" style={{ color: "var(--color-primary-light)" }}>
                        {selectedStat.match_points.toFixed(1)}
                      </span>
                      <span className="text-white/30 text-[10px]">pts</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-white/30 text-xs text-center py-3">Sin datos para esta jornada</p>
              )}
            </div>
          ) : (
            <p className="text-white/30 text-xs text-center px-3 py-6">Sin datos para esta jornada</p>
          )}

          {/* Ver stats link */}
          {leagueId && (
            <div
              className="px-4 py-3 border-t flex justify-end"
              style={{ borderColor: "rgba(255,255,255,0.07)" }}
              onClick={(e) => e.stopPropagation()}
            >
              <Link
                href={`/leagues/${leagueId}/stats/${player.id}`}
                className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all hover:opacity-80"
                style={{
                  background: "var(--color-primary-bg, rgba(252,212,0,0.1))",
                  border: "1px solid rgba(252,212,0,0.25)",
                  color: "var(--color-primary)",
                }}
              >
                Ver stats completas →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helper to keep the stat grid DRY
// ---------------------------------------------------------------------------
function StatCell({ label, value, valueClass }: { label: string; value: string; valueClass: string }) {
  return (
    <div className="rounded-lg px-2.5 py-2 text-center" style={{ background: "rgba(255,255,255,0.05)" }}>
      <p className={`font-mono text-sm font-bold ${valueClass}`}>{value}</p>
      <p className="text-white/30 text-[9px] mt-0.5 uppercase tracking-wider">{label}</p>
    </div>
  );
}

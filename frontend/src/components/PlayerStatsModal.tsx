"use client";

import { useEffect, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { api, type PlayerSplitHistory } from "@/lib/api";
import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";
import { ClauseStatus } from "@/components/ClauseStatus";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MatchStat = {
  kills: number;
  deaths: number;
  assists: number;
  cs_per_min: number;
  vision_score: number;
  fantasy_points: number;
  damage_share?: number;
  gold_diff_at_15?: number | null;
  matches?: { scheduled_at: string; team_1: string; team_2: string };
};

type PlayerHistory = {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    image_url: string | null;
    current_price: number;
  };
  stats: MatchStat[];
  total_points: number;
};

export interface ClauseInfo {
  rosterPlayerId: string;
  leagueId: string;
  clauseAmount: number | null;
  clauseExpiresAt: string | null;
  isOwnPlayer: boolean;
}

export interface PlayerStatsModalProps {
  playerId: string;
  playerHint?: {
    name: string;
    team: string;
    role: string;
    image_url: string | null;
  };
  onClose: () => void;
  /** If provided, renders clause controls at the bottom of the modal */
  clauseInfo?: ClauseInfo;
  /** Called after a successful clause action so the parent can refresh */
  onClauseAction?: () => void;
}

type StatsTab = "jornada" | "split";


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtKDA(k: number, d: number, a: number): string {
  if (d === 0) return "Perfect";
  return ((k + a) / d).toFixed(2);
}

function fmtGoldDiff(val: number | null | undefined): { text: string; color: string } {
  if (val == null) return { text: "N/A", color: "text-white/50" };
  const sign = val >= 0 ? "+" : "";
  const color = val >= 0 ? "text-green-400" : "text-red-400";
  return { text: `${sign}${val.toLocaleString("es-ES")}`, color };
}

function matchLabel(stat: MatchStat, idx: number): string {
  if (stat.matches?.team_1 && stat.matches?.team_2) {
    return `${stat.matches.team_1} vs ${stat.matches.team_2}`;
  }
  return `J${idx + 1}`;
}

// ---------------------------------------------------------------------------
// Skeleton (layout-matching)
// ---------------------------------------------------------------------------

function ModalSkeleton() {
  return (
    <div className="animate-pulse flex flex-col">
      {/* Hero skeleton */}
      <div className="h-56 bg-[#1e2535] flex-shrink-0" />
      {/* Tab bar skeleton */}
      <div className="h-11 bg-[#161b27] border-b border-[rgba(255,255,255,0.06)] flex-shrink-0" />
      {/* Stats skeleton */}
      <div className="p-5 space-y-4 flex-1" style={{ background: "#161b27" }}>
        {/* Pills row */}
        <div className="flex gap-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-7 w-16 bg-[#252d3d] rounded-full" />
          ))}
        </div>
        {/* KDA block */}
        <div className="flex items-center justify-around h-24 bg-[#1e2535] rounded-2xl" />
        {/* 3-col grid */}
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-[#252d3d] rounded-xl" />)}
        </div>
        {/* 2-col grid */}
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map((i) => <div key={i} className="h-16 bg-[#252d3d] rounded-xl" />)}
        </div>
        {/* Points box */}
        <div className="h-20 bg-[#252d3d] rounded-2xl" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KdaTriangle({
  kills,
  deaths,
  assists,
}: {
  kills: number;
  deaths: number;
  assists: number;
}) {
  const kdaStr = fmtKDA(kills, deaths, assists);
  const isPerfect = deaths === 0;

  return (
    <div
      className="flex items-stretch rounded-2xl overflow-hidden"
      style={{ border: "1px solid rgba(255,255,255,0.07)" }}
    >
      {/* K */}
      <div
        className="flex-1 flex flex-col items-center justify-center py-5 gap-1"
        style={{ background: "rgba(34,197,94,0.07)" }}
      >
        <span className="font-datatype font-black text-4xl leading-none text-green-400">{kills}</span>
        <span className="text-[10px] uppercase tracking-widest text-green-400/50 font-bold">Kills</span>
      </div>

      {/* Divider + KDA badge */}
      <div
        className="flex flex-col items-center justify-center px-4 gap-2"
        style={{ background: "#1a2030", borderLeft: "1px solid rgba(255,255,255,0.05)", borderRight: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="text-white/50 text-[11px] font-datatype">/</span>
        <div
          className="px-2.5 py-1 rounded-lg text-center"
          style={{
            background: isPerfect
              ? "rgba(34,197,94,0.15)"
              : "rgba(252,212,0,0.1)",
            border: isPerfect
              ? "1px solid rgba(34,197,94,0.3)"
              : "1px solid rgba(252,212,0,0.2)",
          }}
        >
          <span
            className={`font-datatype font-black text-sm leading-none whitespace-nowrap ${
              isPerfect ? "text-green-400" : "text-yellow-400"
            }`}
          >
            {isPerfect ? "∞" : kdaStr}
          </span>
          <p className="text-[9px] uppercase tracking-wider text-white/50 mt-0.5">KDA</p>
        </div>
        <span className="text-white/50 text-[11px] font-datatype">/</span>
      </div>

      {/* D */}
      <div
        className="flex-1 flex flex-col items-center justify-center py-5 gap-1"
        style={{ background: "rgba(239,68,68,0.06)" }}
      >
        <span className="font-datatype font-black text-4xl leading-none text-red-400">{deaths}</span>
        <span className="text-[10px] uppercase tracking-widest text-red-400/50 font-bold">Deaths</span>
      </div>

      {/* Separator */}
      <div
        className="w-px self-stretch"
        style={{ background: "rgba(255,255,255,0.05)" }}
      />

      {/* A */}
      <div
        className="flex-1 flex flex-col items-center justify-center py-5 gap-1"
        style={{ background: "rgba(59,130,246,0.06)" }}
      >
        <span className="font-datatype font-black text-4xl leading-none text-blue-400">{assists}</span>
        <span className="text-[10px] uppercase tracking-widest text-blue-400/50 font-bold">Assists</span>
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  accent,
  sub,
}: {
  label: string;
  value: string;
  accent?: string;
  sub?: string;
}) {
  return (
    <div
      className="rounded-xl px-3 py-3 flex flex-col gap-0.5"
      style={{ background: "#1e2535", border: "1px solid rgba(255,255,255,0.06)" }}
    >
      <span
        className={`font-datatype font-bold text-lg leading-tight ${accent ?? "text-[#f0f4ff]"}`}
      >
        {value}
      </span>
      <span className="text-[#8892aa] text-[11px]">{label}</span>
      {sub && <span className="text-white/50 text-[10px]">{sub}</span>}
    </div>
  );
}

function DmgProgressBar({ pct, roleHex }: { pct: number; roleHex: string }) {
  // Scale: 0–50% range → fill ratio 0–100%
  const fill = Math.min(Math.max(pct / 50, 0), 1) * 100;
  return (
    <div className="w-full h-1.5 rounded-full mt-2" style={{ background: "rgba(255,255,255,0.06)" }}>
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${fill}%`, background: roleHex }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Por Jornada
// ---------------------------------------------------------------------------

function TabJornada({
  stats,
  role,
}: {
  stats: MatchStat[];
  role: string;
}) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const roleHex = getRoleColor(role);

  if (stats.length === 0) {
    return (
      <div className="py-20 text-center">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <svg className="w-5 h-5 text-white/50" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <p className="text-white/50 text-sm">Sin partidas registradas aún.</p>
      </div>
    );
  }

  const stat = stats[selectedIdx];
  const hasDmg = stat.damage_share != null;
  const dmgPct = hasDmg ? (stat.damage_share! * 100) : 0;
  const goldDiff = fmtGoldDiff(stat.gold_diff_at_15);
  const bestPoints = Math.max(...stats.map((s) => s.fantasy_points));
  const relPct = bestPoints > 0 ? Math.round((stat.fantasy_points / bestPoints) * 100) : 0;
  const csMin = stat.cs_per_min != null ? stat.cs_per_min.toFixed(1) : "—";

  return (
    <div className="p-4 sm:p-5 space-y-4">
      {/* ── Match selector ── */}
      <select
        value={selectedIdx}
        onChange={(e) => setSelectedIdx(Number(e.target.value))}
        className="w-full text-sm font-semibold rounded-xl px-3 py-2.5 outline-none cursor-pointer transition-colors"
        style={{
          background: "#1e2535",
          border: "1px solid rgba(252,212,0,0.25)",
          color: "#f0f4ff",
        }}
      >
        {stats.map((s, i) => (
          <option key={i} value={i} style={{ background: "#1e2535" }}>
            {matchLabel(s, i)}
          </option>
        ))}
      </select>

      {/* ── Row 1: K / D / A ── */}
      <KdaTriangle kills={stat.kills} deaths={stat.deaths} assists={stat.assists} />

      {/* ── Row 2: CS/min / Vision ── */}
      <div className="grid grid-cols-2 gap-3">
        <StatTile
          label="CS/min"
          value={csMin}
          accent="text-[#f0f4ff]"
        />
        <StatTile
          label="Vision"
          value={stat.vision_score > 0 ? stat.vision_score.toString() : "—"}
          accent="text-[#f0f4ff]"
        />
      </div>

      {/* ── Row 3: DMG% + Gold@15 ── */}
      <div className="grid grid-cols-2 gap-3">
        {/* DMG% */}
        <div
          className="rounded-xl px-3 py-3"
          style={{ background: "#1e2535", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <span className="font-datatype font-bold text-lg leading-tight text-[#f0f4ff]">
            {hasDmg ? `${dmgPct.toFixed(1)}%` : "—"}
          </span>
          <p className="text-[#8892aa] text-[11px] mt-0.5">Daño %</p>
          {hasDmg && <DmgProgressBar pct={dmgPct} roleHex={roleHex} />}
          {hasDmg && (
            <p className="text-white/50 text-[9px] mt-1">de 50% máx</p>
          )}
        </div>

        {/* Gold@15 */}
        <div
          className="rounded-xl px-3 py-3"
          style={{ background: "#1e2535", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <span className={`font-datatype font-bold text-lg leading-tight ${goldDiff.color}`}>
            {goldDiff.text}
          </span>
          <p className="text-[#8892aa] text-[11px] mt-0.5">Gold@15</p>
          <p className="text-white/50 text-[9px] mt-1">diferencia oro min 15</p>
        </div>
      </div>

      {/* ── Row 4: Fantasy points highlight ── */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          background: "linear-gradient(135deg, rgba(252,212,0,0.08), rgba(252,212,0,0.04))",
          border: "1px solid rgba(252,212,0,0.2)",
        }}
      >
        {/* Top section */}
        <div className="px-5 pt-4 pb-3 flex items-end justify-between gap-3">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="font-datatype font-black text-4xl text-[#f0f4ff] leading-none">
                {stat.fantasy_points.toFixed(1)}
              </span>
              <span className="text-white/50 text-xs uppercase tracking-wider pb-0.5">pts</span>
            </div>
            <p className="text-[#8892aa] text-xs mt-1">esta jornada</p>
          </div>
          {/* Relative performance badge */}
          <div
            className="flex flex-col items-end"
            title={`${relPct}% de su mejor actuación`}
          >
            <div
              className="px-2.5 py-1 rounded-lg text-center"
              style={{
                background: relPct >= 80
                  ? "rgba(34,197,94,0.12)"
                  : relPct >= 50
                    ? "rgba(252,212,0,0.1)"
                    : "rgba(255,255,255,0.04)",
                border: relPct >= 80
                  ? "1px solid rgba(34,197,94,0.25)"
                  : relPct >= 50
                    ? "1px solid rgba(252,212,0,0.2)"
                    : "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <span
                className={`font-datatype font-black text-sm ${
                  relPct >= 80 ? "text-green-400" : relPct >= 50 ? "text-yellow-400" : "text-white/50"
                }`}
              >
                {relPct}%
              </span>
              <p className="text-[9px] text-white/50 mt-0.5 whitespace-nowrap">mejor actuación</p>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="px-5 pb-4">
          <div className="w-full h-1.5 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${relPct}%`,
                background: "linear-gradient(90deg, #fcd400, #fcb900)",
              }}
            />
          </div>
          <div className="flex justify-between mt-1.5">
            <span className="text-white/50 text-[9px]">0</span>
            <span className="text-white/50 text-[9px] font-datatype">best: {bestPoints.toFixed(1)} pts</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Resumen Split
// ---------------------------------------------------------------------------

function TabSplit({ splits }: { splits: PlayerSplitHistory[] }) {
  if (splits.length === 0) {
    return (
      <div className="py-20 text-center">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-3"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <svg className="w-5 h-5 text-white/50" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
        <p className="text-white/50 text-sm">Sin datos de este split aún.</p>
      </div>
    );
  }

  const s = splits[0];
  const winRate = s.games_played > 0 ? Math.round((s.wins / s.games_played) * 100) : null;

  type StatRow = { label: string; value: string; highlight?: boolean };
  const rows: StatRow[] = [
    { label: "Partidas jugadas", value: s.games_played.toString() },
    ...(winRate != null ? [{ label: "Win rate", value: `${winRate}%` }] : []),
    { label: "KDA promedio", value: s.kda != null && isFinite(s.kda) ? s.kda.toFixed(2) : "—", highlight: true },
    { label: "CS/min", value: s.cspm != null ? s.cspm.toFixed(2) : "—" },
    { label: "DPM", value: s.dpm != null ? Math.round(s.dpm).toLocaleString("es-ES") : "—" },
    {
      label: "Kill participation",
      value: s.kill_participation != null ? `${(s.kill_participation * 100).toFixed(1)}%` : "—",
      highlight: true,
    },
    {
      label: "Wards/min",
      value: s.wards_per_min != null ? s.wards_per_min.toFixed(2) : "—",
    },
    {
      label: "Daño %",
      value: s.damage_pct != null ? `${(s.damage_pct * 100).toFixed(1)}%` : "—",
    },
  ];

  return (
    <div className="p-4 sm:p-5 space-y-4">
      {/* Split header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/lec.webp"
              alt="LEC"
              width={18}
              height={18}
              className="object-contain flex-shrink-0"
              style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.6))" }}
            />
            <p className="text-[#f0f4ff] font-bold text-sm">{s.split_name}</p>
          </div>
          <p className="text-white/50 text-xs mt-0.5">Estadísticas del split actual</p>
        </div>
        <span
          className="text-xs font-bold px-3 py-1.5 rounded-full flex-shrink-0"
          style={{
            background: "rgba(252,212,0,0.1)",
            border: "1px solid rgba(252,212,0,0.2)",
            color: "#fcd400",
          }}
        >
          {s.games_played} partidas
        </span>
      </div>

      {/* KDA highlight tiles */}
      {s.kda != null && isFinite(s.kda) && (
        <div className="grid grid-cols-3 gap-2">
          <div
            className="rounded-xl px-3 py-3 text-center"
            style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.15)" }}
          >
            <p className="font-datatype font-black text-xl text-green-400 leading-none">
              {s.kills != null ? s.kills.toFixed(1) : "—"}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-green-400/50 mt-1 font-bold">K/G</p>
          </div>
          <div
            className="rounded-xl px-3 py-3 text-center"
            style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.15)" }}
          >
            <p className="font-datatype font-black text-xl text-red-400 leading-none">
              {s.deaths != null ? s.deaths.toFixed(1) : "—"}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-red-400/50 mt-1 font-bold">D/G</p>
          </div>
          <div
            className="rounded-xl px-3 py-3 text-center"
            style={{ background: "rgba(59,130,246,0.07)", border: "1px solid rgba(59,130,246,0.15)" }}
          >
            <p className="font-datatype font-black text-xl text-blue-400 leading-none">
              {s.assists != null ? s.assists.toFixed(1) : "—"}
            </p>
            <p className="text-[10px] uppercase tracking-wider text-blue-400/50 mt-1 font-bold">A/G</p>
          </div>
        </div>
      )}

      {/* Stats table */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{ border: "1px solid rgba(255,255,255,0.06)" }}
      >
        {rows.map((row, i) => (
          <div
            key={row.label}
            className="flex items-center justify-between px-4 py-3"
            style={{
              background: i % 2 === 0 ? "#1e2535" : "#161b27",
              borderBottom: i < rows.length - 1 ? "1px solid rgba(255,255,255,0.04)" : undefined,
            }}
          >
            <span className="text-[#8892aa] text-sm">{row.label}</span>
            <span
              className={`font-datatype font-bold text-sm ${
                row.highlight ? "text-yellow-400" : "text-[#f0f4ff]"
              }`}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>

      {/* Previous splits */}
      {splits.length > 1 && (
        <div className="space-y-2">
          <p className="text-white/50 text-xs uppercase tracking-wider font-semibold">
            Splits anteriores
          </p>
          {splits.slice(1).map((prev) => (
            <div
              key={prev.split_id}
              className="flex items-center justify-between px-4 py-3 rounded-xl"
              style={{ background: "#1e2535", border: "1px solid rgba(255,255,255,0.06)" }}
            >
              <span className="text-[#8892aa] text-sm">{prev.split_name}</span>
              <div className="flex items-center gap-3 text-xs font-datatype">
                <span className="text-white/50">{prev.games_played}G</span>
                <span className="text-green-400">
                  {prev.kda != null && isFinite(prev.kda) ? prev.kda.toFixed(2) : "—"} KDA
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hero Section
// ---------------------------------------------------------------------------

function HeroSection({
  name,
  team,
  role,
  imageUrl,
  price,
  totalPoints,
  loading,
}: {
  name: string;
  team: string;
  role: string;
  imageUrl: string | null;
  price: number | undefined;
  totalPoints: number;
  loading: boolean;
}) {
  const rc = ROLE_COLORS[role] ?? ROLE_COLORS.coach;
  const roleHex = getRoleColor(role);

  return (
    <div className="relative flex-shrink-0 overflow-hidden" style={{ height: 220 }}>
      {/* Role-colored top accent stripe */}
      <div
        className="absolute top-0 inset-x-0 h-0.5"
        style={{
          background: `linear-gradient(90deg, transparent, ${roleHex}, transparent)`,
          opacity: 0.6,
        }}
      />

      {/* Blurred bg photo */}
      {imageUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl}
          alt=""
          aria-hidden
          className="absolute inset-0 w-full h-full object-cover object-top scale-110"
          style={{ filter: "blur(20px) saturate(1.2)", opacity: 0.25 }}
        />
      )}

      {/* Dark gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background: imageUrl
            ? `linear-gradient(
                to bottom,
                rgba(15,17,23,0.35) 0%,
                rgba(22,27,39,0.6) 50%,
                #161b27 100%
              )`
            : `linear-gradient(135deg, #1e2535 0%, #161b27 100%)`,
        }}
      />

      {/* Role-colored side glow */}
      <div
        className="absolute left-0 inset-y-0 w-1"
        style={{
          background: `linear-gradient(to bottom, transparent, ${roleHex}66, transparent)`,
        }}
      />

      {/* Content row — image left, info right */}
      <div className="relative z-10 flex h-full">
        {/* Player photo — left panel */}
        <div className="flex-shrink-0 flex items-end pl-4 pb-4">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={name}
              className="h-[190px] w-[130px] object-cover object-top rounded-xl"
              style={{
                boxShadow: `0 4px 24px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05)`,
              }}
            />
          ) : (
            <div
              className="h-[190px] w-[130px] rounded-xl flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #1e2535, #252d3d)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <RoleIcon role={role} className={`w-14 h-14 ${rc.text} opacity-20`} />
            </div>
          )}
        </div>

        {/* Info column — right */}
        <div className="flex-1 min-w-0 flex flex-col justify-end px-4 pb-4 gap-3">
          {/* Name + team */}
          <div>
            <h2 className="text-[#f0f4ff] text-2xl font-black leading-tight truncate">
              {name || "—"}
            </h2>
            <p className="text-[#8892aa] text-sm truncate mt-0.5">{team}</p>
          </div>

          {/* Role badge + price */}
          <div className="flex items-center gap-2 flex-wrap">
            {role && (
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-black px-2.5 py-1 rounded-full ${rc.bg} ${rc.text} border ${rc.border}`}
              >
                <RoleIcon role={role} className="w-3 h-3" />
                {ROLE_LABEL[role] ?? role.toUpperCase()}
              </span>
            )}
            {price != null && !loading && (
              <span
                className="font-datatype text-yellow-400 text-sm font-black px-2 py-0.5 rounded-lg"
                style={{
                  background: "rgba(234,179,8,0.1)",
                  border: "1px solid rgba(234,179,8,0.2)",
                }}
              >
                {price.toFixed(1)}M
              </span>
            )}
          </div>

          {/* Total points — the key number */}
          {!loading && (
            <div
              className="flex items-center gap-3 px-3 py-2 rounded-xl self-start"
              style={{
                background: "rgba(252,212,0,0.08)",
                border: "1px solid rgba(252,212,0,0.2)",
              }}
            >
              <div>
                <span className="font-datatype font-black text-3xl text-yellow-400 leading-none">
                  {totalPoints.toFixed(1)}
                </span>
                <p className="text-white/50 text-[10px] uppercase tracking-wider mt-0.5">
                  pts totales
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Modal
// ---------------------------------------------------------------------------

export function PlayerStatsModal({ playerId, playerHint, onClose, clauseInfo, onClauseAction }: PlayerStatsModalProps) {
  const [data, setData]     = useState<PlayerHistory | null>(null);
  const [splits, setSplits] = useState<PlayerSplitHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]       = useState<StatsTab>("jornada");

  // Body scroll lock
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  // Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Data fetch — parallel
  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.scoring.playerHistory(playerId).catch(() => null),
      api.splits.playerHistory(playerId).catch(() => []),
    ]).then(([historyRes, splitRes]) => {
      setData(historyRes as PlayerHistory | null);
      setSplits(splitRes as PlayerSplitHistory[]);
    }).finally(() => setLoading(false));
  }, [playerId]);

  // Resolved meta — hint shown immediately, data fills in after load
  const name      = data?.player.name      ?? playerHint?.name   ?? "";
  const team      = data?.player.team      ?? playerHint?.team   ?? "";
  const role      = data?.player.role      ?? playerHint?.role   ?? "";
  const imageUrl  = data?.player.image_url ?? playerHint?.image_url ?? null;
  const price     = data?.player.current_price;
  const totalPoints = data?.total_points ?? 0;

  const handleBackdrop = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  const TABS: { key: StatsTab; label: string }[] = [
    { key: "jornada", label: "Por Jornada" },
    { key: "split",   label: "Resumen Split" },
  ];

  const modal = (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-[3px] p-0 sm:p-4"
      onClick={handleBackdrop}
    >
      {/* Modal panel */}
      <div
        className={`
          relative w-full sm:max-w-2xl
          max-h-[85vh] sm:max-h-[90vh]
          flex flex-col
          rounded-t-3xl sm:rounded-2xl
          overflow-hidden
          sm:animate-modal-in animate-sheet-up
        `}
        style={{
          background: "#161b27",
          boxShadow: "0 0 0 1px rgba(255,255,255,0.07), 0 25px 80px rgba(0,0,0,0.7), 0 0 60px rgba(252,212,0,0.06)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-20 w-8 h-8 flex items-center justify-center rounded-lg text-white/50 hover:text-[#f0f4ff] hover:bg-[rgba(255,255,255,0.06)] transition-all"
          aria-label="Cerrar"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Mobile drag handle */}
        <div className="sm:hidden flex justify-center pt-3 pb-1 flex-shrink-0">
          <div className="w-10 h-1 rounded-full bg-[rgba(255,255,255,0.12)]" />
        </div>

        {/* ── Hero — always visible, uses hint data immediately ── */}
        <HeroSection
          name={name}
          team={team}
          role={role}
          imageUrl={imageUrl}
          price={price}
          totalPoints={totalPoints}
          loading={loading}
        />

        {loading ? (
          /* Skeleton for stats body while data loads */
          <div className="flex-1 overflow-y-auto" style={{ background: "#161b27" }}>
            <ModalSkeleton />
          </div>
        ) : (
          <>
            {/* ── Tab bar ── */}
            <div
              className="flex flex-shrink-0 border-b"
              style={{ background: "#161b27", borderColor: "rgba(255,255,255,0.07)" }}
            >
              {TABS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex-1 py-3 text-sm font-semibold border-b-2 transition-all duration-150
                    ${tab === key
                      ? "border-yellow-400 text-[#f0f4ff]"
                      : "border-transparent text-white/50 hover:text-[#8892aa]"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* ── Scrollable body ── */}
            <div className="flex-1 overflow-y-auto" style={{ background: "#161b27" }}>
              {tab === "jornada" && (
                <TabJornada
                  stats={data?.stats ?? []}
                  role={role}
                />
              )}
              {tab === "split" && <TabSplit splits={splits} />}

              {/* ── Clause section ── */}
              {clauseInfo && (
                <div
                  className="mx-4 sm:mx-5 mb-5 px-4 py-3 rounded-2xl"
                  style={{
                    background: clauseInfo.isOwnPlayer
                      ? "rgba(56,189,248,0.04)"
                      : "rgba(252,212,0,0.04)",
                    border: clauseInfo.isOwnPlayer
                      ? "1px solid rgba(56,189,248,0.12)"
                      : "1px solid rgba(252,212,0,0.12)",
                  }}
                >
                  <p
                    className="text-[10px] uppercase tracking-widest font-semibold mb-2"
                    style={{ color: "#8892aa" }}
                  >
                    Cláusula de rescisión
                  </p>
                  <ClauseStatus
                    clauseAmount={clauseInfo.clauseAmount}
                    clauseExpiresAt={clauseInfo.clauseExpiresAt}
                    isOwnPlayer={clauseInfo.isOwnPlayer}
                    leagueId={clauseInfo.leagueId}
                    rosterPlayerId={clauseInfo.rosterPlayerId}
                    onSuccess={onClauseAction}
                  />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}

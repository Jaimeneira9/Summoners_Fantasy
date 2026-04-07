import { RoleIcon } from "@/components/RoleIcon";
import type {
  PlayerGameStatRow,
  PlayerSeriesStatRow,
  PlayerSeasonAvgRow,
} from "@/types/match-detail";

// ─── helpers ──────────────────────────────────────────────────────────────────

export const ROLE_ORDER = ["top", "jungle", "mid", "adc", "support"];

function playerImageUrl(name: string): string {
  return `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/${name
    .toLowerCase()
    .replace(/ /g, "-")}.webp`;
}

function formatDiff(value: number): string {
  const abs = Math.abs(value);
  const sign = value >= 0 ? "+" : "-";
  if (abs >= 1000) {
    return `${sign}${(abs / 1000).toFixed(1)}k`;
  }
  return `${sign}${abs}`;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export type AnyPlayer = PlayerGameStatRow | PlayerSeriesStatRow | PlayerSeasonAvgRow;
export type RoleRowMode = "game" | "series" | "upcoming";

function getKDA(player: AnyPlayer, mode: RoleRowMode): string {
  if (mode === "game") {
    const p = player as PlayerGameStatRow;
    return `${Math.round(p.kills)}/${Math.round(p.deaths)}/${Math.round(p.assists)}`;
  }
  const p = player as PlayerSeriesStatRow | PlayerSeasonAvgRow;
  return `${p.avg_kills.toFixed(1)}/${p.avg_deaths.toFixed(1)}/${p.avg_assists.toFixed(1)}`;
}

function getPoints(player: AnyPlayer, mode: RoleRowMode): number | null {
  if (mode === "game") return (player as PlayerGameStatRow).game_points;
  if (mode === "series") return (player as PlayerSeriesStatRow).series_points;
  return (player as PlayerSeasonAvgRow).avg_points;
}

// ─── Avatar con role badge ────────────────────────────────────────────────────

interface AvatarProps {
  name: string;
  imageUrl: string | null;
  isMvp: boolean;
}

function Avatar({ name, imageUrl, isMvp }: AvatarProps) {
  const src = imageUrl ?? playerImageUrl(name);

  return (
    <div className="relative shrink-0" style={{ width: 56, height: 56 }}>
      <div
        className="w-full h-full rounded-lg overflow-hidden bg-[#1a1a1a] flex items-center justify-center"
        style={isMvp ? { outline: "2px solid #fcd400", outlineOffset: 1 } : undefined}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={name}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={(e) => {
            const target = e.currentTarget as HTMLImageElement;
            target.style.display = "none";
            const parent = target.parentElement;
            if (parent) {
              parent.innerHTML = `<span style="color:#fff;font-size:18px;font-weight:700">${name.charAt(0).toUpperCase()}</span>`;
            }
          }}
        />
      </div>
    </div>
  );
}

// ─── StatsLine ────────────────────────────────────────────────────────────────

interface StatsLineProps {
  player: AnyPlayer;
  mode: RoleRowMode;
  align: "left" | "right";
  isWinner: boolean;
}

function StatsLine({ player, mode, align, isWinner }: StatsLineProps) {
  const dimColor = "#4b5563"; // neutral-600
  const kda = getKDA(player, mode);

  if (mode !== "game") {
    return (
      <span style={{ fontSize: 12, color: isWinner ? "#737373" : dimColor }}>
        KDA {kda}
      </span>
    );
  }

  const gamePlayer = player as PlayerGameStatRow;
  const hasGold = gamePlayer.gold_diff_15 !== null;
  const hasXp = gamePlayer.xp_diff_15 !== null;

  const goldVal = hasGold ? gamePlayer.gold_diff_15! : null;
  const xpVal = hasXp ? gamePlayer.xp_diff_15! : null;

  function diffColor(val: number | null): string {
    if (!isWinner) return dimColor;
    if (val === null) return "#6b7280";
    if (val > 0) return "#22c55e";
    if (val < 0) return "#ef4444";
    return "#6b7280";
  }

  const kdaColor = isWinner ? "#a3a3a3" : dimColor;
  const goldColor = diffColor(goldVal);
  const xpColor = diffColor(xpVal);

  // Segmentos: [KDA, Gold, XP]
  const segments: Array<{ label: string; color: string }> = [
    { label: `KDA ${kda}`, color: kdaColor },
    ...(hasGold ? [{ label: `${formatDiff(goldVal!)}G`, color: goldColor }] : []),
    ...(hasXp ? [{ label: `${formatDiff(xpVal!)}XP`, color: xpColor }] : []),
  ];

  // Lado derecho: invertir orden para efecto espejo
  const ordered = align === "right" ? [...segments].reverse() : segments;

  return (
    <span style={{ fontSize: 12, display: "flex", gap: 8, flexWrap: "nowrap" }}>
      {ordered.map((seg, i) => (
        <span key={i} style={{ color: seg.color, whiteSpace: "nowrap" }}>
          {seg.label}
        </span>
      ))}
    </span>
  );
}

// ─── RoleRow ───────────────────────────────────────────────────────────────────

export interface RoleRowProps {
  home: AnyPlayer | null;
  away: AnyPlayer | null;
  mode: RoleRowMode;
  role: string;
  homeIsWinner: boolean;
  isMvp?: "home" | "away" | null;
}

export function RoleRow({ home, away, mode, role, homeIsWinner, isMvp = null }: RoleRowProps) {
  const homePts = home ? getPoints(home, mode) : null;
  const awayPts = away ? getPoints(away, mode) : null;

  const diff =
    homePts !== null && awayPts !== null
      ? homeIsWinner
        ? homePts - awayPts
        : awayPts - homePts
      : null;

  const diffPositive = diff !== null && diff > 0;
  const diffColor = diffPositive ? "#22c55e" : "#6b7280";
  const diffBg = diffPositive ? "rgba(34,197,94,0.15)" : "rgba(107,114,128,0.15)";

  // Colores de pts
  const winnerPtsColor = "#fcd400";
  const loserPtsColor = "#525252"; // neutral-600

  const homePtsColor = homeIsWinner ? winnerPtsColor : loserPtsColor;
  const awayPtsColor = homeIsWinner ? loserPtsColor : winnerPtsColor;

  function formatPts(pts: number): string {
    return pts % 1 === 0 ? pts.toFixed(1) : pts.toFixed(1);
  }

  return (
    <div
      className="rounded-xl overflow-hidden mb-2"
      style={{ background: "#111111" }}
    >
      <div
        className="grid items-center p-3"
        style={{ gridTemplateColumns: "auto 1fr auto 1fr auto", gap: "0 14px" }}
      >
        {/* ── Col 1: Home avatar ── */}
        <div style={{ borderLeft: homeIsWinner ? "3px solid #fcd400" : "3px solid transparent", paddingLeft: 6 }}>
          {home ? (
            <Avatar
              name={home.name}
              imageUrl={home.image_url}
              isMvp={isMvp === "home"}
            />
          ) : (
            <div
              className="rounded-lg"
              style={{ width: 56, height: 56, background: "#1a1a1a", border: "1px solid #1e1e1e" }}
            />
          )}
        </div>

        {/* ── Col 2: Home info ── */}
        <div className="flex items-center justify-between gap-2 min-w-0">
          {home ? (
            <>
              <div className="flex flex-col min-w-0">
                <span
                  className="truncate leading-tight"
                  style={{
                    color: homeIsWinner ? "#fff" : "#525252",
                    fontWeight: homeIsWinner ? 700 : 500,
                    fontSize: 13,
                  }}
                >
                  {home.name}
                </span>
                <div style={{ marginTop: 5 }}>
                  <StatsLine player={home} mode={mode} align="left" isWinner={homeIsWinner} />
                </div>
              </div>
              {homePts !== null && (
                <div className="flex flex-col items-end shrink-0 gap-1">
                  {isMvp === "home" && (
                    <span style={{ fontSize: 9, background: "#fcd400", color: "#000", padding: "1px 5px", borderRadius: 4, fontWeight: 900, letterSpacing: "0.05em" }}>
                      MVP
                    </span>
                  )}
                  <span
                    className="tabular-nums font-black"
                    style={{ color: homePtsColor, fontSize: 22, lineHeight: 1 }}
                  >
                    {formatPts(homePts)}
                  </span>
                </div>
              )}
            </>
          ) : (
            <span style={{ color: "#404040", fontSize: 13 }}>—</span>
          )}
        </div>

        {/* ── Col 3: Center (role icon + diff badge) ── */}
        <div className="flex flex-col items-center justify-center gap-1 px-2">
          <RoleIcon role={role} className="w-6 h-6 shrink-0 opacity-90" />
          {diff !== null && (
            <span
              className="tabular-nums font-semibold"
              style={{
                fontSize: 10,
                color: diffColor,
                background: diffBg,
                borderRadius: 999,
                padding: "1px 5px",
                lineHeight: "14px",
              }}
            >
              {diffPositive ? "+" : ""}{diff.toFixed(1)}
            </span>
          )}
        </div>

        {/* ── Col 4: Away info (pts a la izq, nombre a la der) ── */}
        <div className="flex items-center justify-between gap-2 min-w-0">
          {away ? (
            <>
              {awayPts !== null && (
                <div className="flex flex-col items-start shrink-0 gap-1">
                  {isMvp === "away" && (
                    <span style={{ fontSize: 9, background: "#fcd400", color: "#000", padding: "1px 5px", borderRadius: 4, fontWeight: 900, letterSpacing: "0.05em" }}>
                      MVP
                    </span>
                  )}
                  <span
                    className="tabular-nums font-black"
                    style={{ color: awayPtsColor, fontSize: 22, lineHeight: 1 }}
                  >
                    {formatPts(awayPts)}
                  </span>
                </div>
              )}
              <div className="flex flex-col min-w-0 items-end">
                <span
                  className="truncate leading-tight"
                  style={{
                    color: homeIsWinner ? "#525252" : "#fff",
                    fontWeight: homeIsWinner ? 500 : 700,
                    fontSize: 13,
                  }}
                >
                  {away.name}
                </span>
                <div style={{ marginTop: 5 }}>
                  <StatsLine player={away} mode={mode} align="right" isWinner={!homeIsWinner} />
                </div>
              </div>
            </>
          ) : (
            <span style={{ color: "#404040", fontSize: 13, marginLeft: "auto" }}>—</span>
          )}
        </div>

        {/* ── Col 5: Away avatar ── */}
        <div style={{ borderRight: homeIsWinner ? "3px solid transparent" : "3px solid #fcd400", paddingRight: 6 }}>
          {away ? (
            <Avatar
              name={away.name}
              imageUrl={away.image_url}
              isMvp={isMvp === "away"}
            />
          ) : (
            <div
              className="rounded-lg"
              style={{ width: 56, height: 56, background: "#1a1a1a", border: "1px solid #1e1e1e" }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

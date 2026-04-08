import type { MatchDetailPlayed, PlayerSeriesStatRow } from "@/types/match-detail";
import { RoleRow, ROLE_ORDER } from "./RoleRow";

interface SeriesViewProps {
  data: MatchDetailPlayed;
  leagueId?: string;
}

export function SeriesView({ data, leagueId }: SeriesViewProps) {
  const { team_home, team_away, series_stats } = data;

  const byRole = (players: PlayerSeriesStatRow[], role: string) =>
    players.find((p) => p.role === role) ?? null;

  const homePlayers = series_stats.filter((p) => p.team_id === team_home.name);
  const awayPlayers = series_stats.filter((p) => p.team_id === team_away.name);

  // MVP global de la serie: jugador con más series_points
  const allPlayers = [
    ...homePlayers.map((p) => ({ side: "home" as const, pts: p.series_points ?? 0, role: p.role })),
    ...awayPlayers.map((p) => ({ side: "away" as const, pts: p.series_points ?? 0, role: p.role })),
  ];
  const mvpPlayer =
    allPlayers.length > 0
      ? allPlayers.reduce((a, b) => (b.pts > a.pts ? b : a))
      : null;
  const mvpRole = mvpPlayer && mvpPlayer.pts > 0 ? mvpPlayer.role : null;
  const mvpSide = mvpPlayer && mvpPlayer.pts > 0 ? mvpPlayer.side : null;

  // Ganador de la serie (para el header): quién tiene más puntos totales
  const homeTotalPts = homePlayers.reduce((acc, p) => acc + (p.series_points ?? 0), 0);
  const awayTotalPts = awayPlayers.reduce((acc, p) => acc + (p.series_points ?? 0), 0);
  const homeIsSeriesWinner = homeTotalPts >= awayTotalPts;

  return (
    <div className="flex flex-col gap-1 p-4">
      {/* Team header row — mismo grid que RoleRow para alinear columnas */}
      <div
        className="hidden sm:grid items-center px-3 pb-2 border-b border-[#1e1e1e] mb-1"
        style={{ gridTemplateColumns: "auto 1fr auto 1fr auto", gap: "0 14px" }}
      >
        <div style={{ width: 65 }} />
        <TeamLabel
          name={team_home.name}
          logoUrl={team_home.logo_url}
          align="left"
          score={team_home.score}
          isWinner={homeIsSeriesWinner}
        />
        <div style={{ width: 44 }} />
        <TeamLabel
          name={team_away.name}
          logoUrl={team_away.logo_url}
          align="right"
          score={team_away.score}
          isWinner={!homeIsSeriesWinner}
        />
        <div style={{ width: 65 }} />
      </div>

      {ROLE_ORDER.map((role) => {
        const homePlayer = byRole(homePlayers, role);
        const awayPlayer = byRole(awayPlayers, role);

        // homeIsWinner por rol: comparar series_points del jugador en ese rol
        const homePts = homePlayer?.series_points ?? 0;
        const awayPts = awayPlayer?.series_points ?? 0;
        const homeIsWinnerForRole = homePts >= awayPts;

        return (
          <RoleRow
            key={role}
            role={role}
            mode="series"
            home={homePlayer}
            away={awayPlayer}
            homeIsWinner={homeIsWinnerForRole}
            isMvp={mvpRole === role ? mvpSide : null}
            leagueId={leagueId}
          />
        );
      })}
    </div>
  );
}

// ─── Team label (mini header) ─────────────────────────────────────────────────

function TeamLabel({
  name,
  logoUrl,
  align,
  score,
  isWinner,
}: {
  name: string;
  logoUrl: string | null;
  align: "left" | "right";
  score: number;
  isWinner: boolean;
}) {
  const src =
    logoUrl ??
    `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${name
      .toLowerCase()
      .replace(/ /g, "-")}.webp`;

  const nameEl = (
    <span
      className="text-xs font-semibold uppercase tracking-wide"
      style={{ color: isWinner ? "#e5e5e5" : "#525252" }}
    >
      {name}
    </span>
  );

  const logoEl = (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img
      src={src}
      alt={name}
      width={20}
      height={20}
      className="w-5 h-5 object-contain"
      style={{ opacity: isWinner ? 1 : 0.4 }}
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.display = "none";
      }}
    />
  );

  const scoreEl = (
    <span
      className="text-sm font-bold"
      style={{ color: isWinner ? "#fff" : "#525252" }}
    >
      {score}
    </span>
  );

  return (
    <div className={`flex items-center gap-2 ${align === "right" ? "justify-end flex-row-reverse" : ""}`}>
      {logoEl}
      {nameEl}
      {scoreEl}
    </div>
  );
}

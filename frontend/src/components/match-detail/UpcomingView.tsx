import type { MatchDetailUpcoming, PlayerSeasonAvgRow } from "@/types/match-detail";
import { RoleRow, ROLE_ORDER } from "./RoleRow";

interface UpcomingViewProps {
  data: MatchDetailUpcoming;
}

export function UpcomingView({ data }: UpcomingViewProps) {
  const { team_home, team_away, season_averages } = data;

  const byRole = (players: PlayerSeasonAvgRow[], role: string) =>
    players.find((p) => p.role === role) ?? null;

  const homePlayers = season_averages.filter((p) => p.team_id === team_home.name);
  const awayPlayers = season_averages.filter((p) => p.team_id === team_away.name);

  return (
    <div className="flex flex-col gap-1 p-4">
      <p className="text-xs text-center uppercase tracking-widest mb-2" style={{ color: "#525252" }}>
        Promedios de temporada
      </p>

      {/* Team header row */}
      <div
        className="grid items-center px-3 pb-2 border-b border-[#1e1e1e] mb-1"
        style={{ gridTemplateColumns: "68px 1fr auto 1fr 68px" }}
      >
        <div />
        <TeamLabel name={team_home.name} logoUrl={team_home.logo_url} align="left" />
        <div className="w-6" />
        <TeamLabel name={team_away.name} logoUrl={team_away.logo_url} align="right" />
        <div />
      </div>

      {ROLE_ORDER.map((role) => {
        const homePlayer = byRole(homePlayers, role);
        const awayPlayer = byRole(awayPlayers, role);
        const homePts = homePlayer?.avg_points ?? 0;
        const awayPts = awayPlayer?.avg_points ?? 0;
        return (
          <RoleRow
            key={role}
            role={role}
            mode="upcoming"
            home={homePlayer}
            away={awayPlayer}
            homeIsWinner={homePts >= awayPts}
            isMvp={null}
          />
        );
      })}
    </div>
  );
}

// ─── Team label ───────────────────────────────────────────────────────────────

function TeamLabel({
  name,
  logoUrl,
  align,
}: {
  name: string;
  logoUrl: string | null;
  align: "left" | "right";
}) {
  const src =
    logoUrl ??
    `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${name
      .toLowerCase()
      .replace(/ /g, "-")}.webp`;

  const nameEl = (
    <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: "#a3a3a3" }}>
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
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.display = "none";
      }}
    />
  );

  return (
    <div className={`flex items-center gap-2 ${align === "right" ? "justify-end" : ""}`}>
      {align === "left" ? (
        <>{logoEl}{nameEl}</>
      ) : (
        <>{nameEl}{logoEl}</>
      )}
    </div>
  );
}

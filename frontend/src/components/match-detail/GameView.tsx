import type {
  GameDetailData,
  TeamDetailInfo,
  PlayerGameStatRow,
} from "@/types/match-detail";
import { RoleRow, ROLE_ORDER } from "./RoleRow";

interface GameViewProps {
  game: GameDetailData;
  teamHome: TeamDetailInfo;
  teamAway: TeamDetailInfo;
}

function formatDuration(durationMin: number | null): string {
  if (durationMin === null) return "—";
  const totalSeconds = Math.round(durationMin * 60);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function GameView({ game, teamHome, teamAway }: GameViewProps) {
  const byRole = (players: PlayerGameStatRow[], role: string) =>
    players.find((p) => p.role === role) ?? null;

  const homePlayers = game.players.filter((p) => p.team_id === teamHome.name);
  const awayPlayers = game.players.filter((p) => p.team_id === teamAway.name);

  // ¿Quién ganó? winner_team_id puede ser el id o el nombre del equipo
  const homeIsGameWinner =
    game.winner_team_id === teamHome.id || game.winner_team_id === teamHome.name;

  // MVP global del game: jugador con más game_points
  const allPlayers = [
    ...homePlayers.map((p) => ({ side: "home" as const, pts: p.game_points ?? 0, role: p.role })),
    ...awayPlayers.map((p) => ({ side: "away" as const, pts: p.game_points ?? 0, role: p.role })),
  ];
  const mvpPlayer = allPlayers.length > 0
    ? allPlayers.reduce((a, b) => (b.pts > a.pts ? b : a))
    : null;
  const mvpRole = mvpPlayer && mvpPlayer.pts > 0 ? mvpPlayer.role : null;
  const mvpSide = mvpPlayer && mvpPlayer.pts > 0 ? mvpPlayer.side : null;

  const winnerName = homeIsGameWinner ? teamHome.name : teamAway.name;

  return (
    <div className="flex flex-col gap-1 p-4">
      {/* Game sub-header */}
      <div className="flex items-center justify-center gap-2 px-3 py-2 bg-[#1a1a1a] rounded-lg mb-1">
        <span className="text-white text-sm font-bold">
          Game {game.game_number}
        </span>
        {winnerName && (
          <span className="text-sm font-semibold" style={{ color: "#22c55e" }}>
            — {winnerName} won
          </span>
        )}
        {game.duration_min && (
          <span className="text-xs font-mono" style={{ color: "#737373" }}>
            · {formatDuration(game.duration_min)}
          </span>
        )}
      </div>

      {/* Team header row */}
      <div
        className="grid items-center px-3 pb-2 border-b border-[#1e1e1e] mb-1"
        style={{ gridTemplateColumns: "68px 1fr auto 1fr 68px" }}
      >
        <div />
        <TeamLabel name={teamHome.name} logoUrl={teamHome.logo_url} align="left" isWinner={homeIsGameWinner} />
        <div className="w-6" />
        <TeamLabel name={teamAway.name} logoUrl={teamAway.logo_url} align="right" isWinner={!homeIsGameWinner} />
        <div />
      </div>

      {ROLE_ORDER.map((role) => (
        <RoleRow
          key={role}
          role={role}
          mode="game"
          home={byRole(homePlayers, role)}
          away={byRole(awayPlayers, role)}
          homeIsWinner={homeIsGameWinner}
          isMvp={mvpRole === role ? mvpSide : null}
        />
      ))}
    </div>
  );
}

// ─── Team label ───────────────────────────────────────────────────────────────

function TeamLabel({
  name,
  logoUrl,
  align,
  isWinner,
}: {
  name: string;
  logoUrl: string | null;
  align: "left" | "right";
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

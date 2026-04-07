import type { TeamDetailInfo } from "@/types/match-detail";

interface MatchHeaderProps {
  teamHome: TeamDetailInfo;
  teamAway: TeamDetailInfo;
  mode: "played" | "upcoming";
  scheduledAt?: string | null;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function teamLogoUrl(team: TeamDetailInfo): string {
  if (team.logo_url) return team.logo_url;
  return `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${team.name
    .toLowerCase()
    .replace(/ /g, "-")}.webp`;
}

export function MatchHeader({
  teamHome,
  teamAway,
  mode,
  scheduledAt,
}: MatchHeaderProps) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-5 bg-[#111111] border-b border-[#1e1e1e]">
      {/* Teams row */}
      <div className="flex items-center gap-4 w-full justify-center">
        {/* Home team */}
        <div className="flex flex-col items-center gap-1 min-w-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={teamLogoUrl(teamHome)}
            alt={teamHome.name}
            className="w-12 h-12 object-contain"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
          <span className="text-white text-sm font-bold truncate max-w-[80px] text-center">
            {teamHome.name}
          </span>
        </div>

        {/* Score / VS */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          {mode === "played" ? (
            <span className="text-[#fcd400] text-3xl font-black tracking-tight">
              {teamHome.score}&nbsp;–&nbsp;{teamAway.score}
            </span>
          ) : (
            <span className="text-neutral-400 text-2xl font-bold tracking-widest">
              VS
            </span>
          )}

          {/* Status badge */}
          {mode === "played" ? (
            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 bg-[#1a1a1a] px-2 py-0.5 rounded-full">
              COMPLETADO
            </span>
          ) : (
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#fcd400] bg-[#fcd400]/10 px-2 py-0.5 rounded-full">
              PRÓXIMO
            </span>
          )}
        </div>

        {/* Away team */}
        <div className="flex flex-col items-center gap-1 min-w-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={teamLogoUrl(teamAway)}
            alt={teamAway.name}
            className="w-12 h-12 object-contain"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
          <span className="text-white text-sm font-bold truncate max-w-[80px] text-center">
            {teamAway.name}
          </span>
        </div>
      </div>

      {/* Date */}
      {scheduledAt && mode === "upcoming" && (
        <span className="text-neutral-500 text-xs">{formatDate(scheduledAt)}</span>
      )}
    </div>
  );
}

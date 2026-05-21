const TEAM_BADGE_EXCEPTIONS: Record<string, string> = {
  "Movistar KOI": "movistar-koi.webp",
};

const STORAGE_BASE = "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/";

export function getTeamBadgeUrl(teamName: string): string {
  if (TEAM_BADGE_EXCEPTIONS[teamName]) {
    return STORAGE_BASE + TEAM_BADGE_EXCEPTIONS[teamName];
  }
  return STORAGE_BASE + teamName.toLowerCase().replace(/ /g, "-") + ".webp";
}

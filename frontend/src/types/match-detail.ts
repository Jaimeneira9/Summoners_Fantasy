export type PlayerRole = "top" | "jungle" | "mid" | "adc" | "support";

export interface TeamDetailInfo {
  id: string;
  name: string;
  logo_url: string | null;
  score: number;
}

export interface PlayerGameStatRow {
  player_id: string;
  name: string;
  role: PlayerRole;
  image_url: string | null;
  team_id: string;
  kills: number;
  deaths: number;
  assists: number;
  game_points: number | null;
  gold_diff_15: number | null;
  xp_diff_15: number | null;
  result: 0 | 1 | null;
}

export interface PlayerSeriesStatRow {
  player_id: string;
  name: string;
  role: PlayerRole;
  image_url: string | null;
  team_id: string;
  games_played: number;
  series_points: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_gold_diff_15: number | null;
  avg_xp_diff_15: number | null;
}

export interface GameDetailData {
  game_id: string;
  game_number: number;
  duration_min: number | null;
  winner_team_id: string | null;
  players: PlayerGameStatRow[];
}

export interface MatchDetailPlayed {
  series_id: string;
  status: string;
  score_home: number;
  score_away: number;
  team_home: TeamDetailInfo;
  team_away: TeamDetailInfo;
  games: GameDetailData[];
  series_stats: PlayerSeriesStatRow[];
}

export interface PlayerSeasonAvgRow {
  player_id: string;
  name: string;
  role: PlayerRole;
  image_url: string | null;
  team_id: string;
  games_played: number;
  avg_points: number | null;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_gold_diff_15: number | null;
  avg_xp_diff_15: number | null;
}

export interface MatchDetailUpcoming {
  series_id: string;
  status: string;
  scheduled_at: string | null;
  team_home: TeamDetailInfo;
  team_away: TeamDetailInfo;
  season_averages: PlayerSeasonAvgRow[];
}

export interface MatchDetailEnvelope {
  mode: "played" | "upcoming";
  played: MatchDetailPlayed | null;
  upcoming: MatchDetailUpcoming | null;
}

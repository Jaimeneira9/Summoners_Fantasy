"use client";

import { createClient } from "@/lib/supabase/client";

const BASE = process.env.NEXT_PUBLIC_API_URL!;

async function token(): Promise<string | null> {
  const sb = createClient();
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? null;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const t = await token();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PlayerBrief = {
  name: string;
  team: string;
  role: string;
  image_url: string | null;
  current_price: number;
  total_season_points?: number | null;
  split_points?: number | null;
  last_price_change_pct?: number;
};

export type Listing = {
  id: string;
  player_id: string;
  seller_id: string | null;
  league_id: string;
  ask_price: number;
  status: string;
  listed_at: string;
  closes_at: string | null;
  players: PlayerBrief;
  bid_count?: number;
};

export type LeaderboardEntry = {
  rank: number;
  member_id: string;
  username: string | null;
  avatar_url: string | null;
  total_points: number;
  remaining_budget: number;
  player_count: number;
  week_points?: number | null;
};

export type LeaderboardResponse = {
  entries: LeaderboardEntry[];
  current_week: number | null;
  available_weeks: number[];
  selected_week: number | null;
};

export type ActivityEvent = {
  id: string;
  type: string;
  player_name: string;
  player_role: string;
  player_image_url: string | null;
  player_team: string;
  buyer_name: string | null;
  seller_name: string | null;
  price: number;
  executed_at: string;
};

export type PlayerMatchStat = {
  series_id?: string | null;
  kills: number;
  deaths: number;
  assists: number;
  cs_per_min: number;
  fantasy_points: number;
  result?: number | null;
  dpm: number | null;
  gold_diff_at_15: number | null;
  xp_diff_at_15?: number | null;
  turret_damage?: number | null;
  competition_id: string;
  competition_name: string;
  stat_breakdown?: Record<string, number>;
  matches?: { scheduled_at: string | null; team_1: string; team_2: string } | null;
};

export type GameDetailStat = {
  game_number: number;
  result: number | null;
  kills: number;
  deaths: number;
  assists: number;
  cs_per_min: number;
  dpm: number;
  game_points: number;
};

export type SeriesGamesResponse = {
  series_id: string;
  games: GameDetailStat[];
};

export type MyBid = {
  id: string;
  listing_id: string;
  bid_amount: number;
  placed_at: string;
  status: string;
  player_name: string;
  player_role: string;
  player_image_url: string | null;
  player_team: string;
  listing_closes_at: string | null;
  listing_ask_price: number;
};

export type SellOffer = {
  id: string;
  ask_price: number;
  status: string;
  expires_at: string;
  player: PlayerBrief;
  offer_type: "sistema" | "manager";
  from_username?: string | null;
};

export type Candidate = {
  id: string;
  player_id: string;
  ask_price: number;
  added_at: string;
  players: PlayerBrief;
};

export type League = {
  id: string;
  name: string;
  invite_code: string;
  owner_id: string;
  budget: number;
  competition: string;
  is_active: boolean;
  member: { id: string; remaining_budget: number; total_points: number } | null;
};

export type Slot =
  | "starter_1" | "starter_2" | "starter_3" | "starter_4" | "starter_5"
  | "coach" | "bench_1" | "bench_2";

export type RosterPlayer = {
  id: string;
  slot: Slot;
  price_paid: number;
  for_sale: boolean;
  is_protected: boolean;
  split_points?: number | null;
  clause_amount: number | null;
  clause_expires_at: string | null;
  player: PlayerBrief & { id: string };
};

export type Split = {
  id: string;
  name: string;
  competition: string;
  start_date: string | null;
  end_date: string | null;
  reset_date: string | null;
  is_active: boolean;
};

export type ScoutPlayer = {
  id: string;
  name: string;
  team: string;
  role: string;
  image_url: string | null;
  current_price: number;
  last_price_change_pct: number;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  total_kills: number;
  total_deaths: number;
  total_assists: number;
  avg_cs_per_min: number;
  avg_gold_diff_15: number;
  avg_xp_diff_15: number;
  avg_dpm: number;
  avg_vision_score: number;
  avg_points: number;
  total_points: number;
  owner_name: string | null;
  clause_amount?: number | null;
  clause_expires_at?: string | null;
  for_sale?: boolean;
  for_sale_price?: number | null;
};

export type ClauseInfo = {
  is_owned: boolean;
  owned_by_me: boolean;
  clause_amount: number | null;
  clause_expires_at: string | null;
  clause_active: boolean;
  roster_player_id: string | null;
  for_sale?: boolean;
  owner_username?: string | null;
};

export type PlayerSplitHistory = {
  split_id: string;
  split_name: string;
  games_played: number;
  wins: number;
  kills: number;
  deaths: number;
  assists: number;
  kda: number | null;
  cspm: number | null;
  dpm: number | null;
  damage_pct: number | null;
  kill_participation: number | null;
  wards_per_min: number | null;
};

export type Roster = {
  league_id: string;
  member_id: string;
  remaining_budget: number;
  total_points: number;
  players: RosterPlayer[];
};

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export type MemberRoster = {
  member: { id: string; total_points: number };
  players: { slot: string; price_paid: number; split_points: number; players: { id: string; name: string; team: string; role: string; image_url: string | null } }[];
};

export type MemberStats = {
  avg_kda: number | null;
  avg_gold_diff_15: number | null;
  avg_pts_per_week: number | null;
  games_counted: number;
};

export type DetailedLeaderboardEntry = {
  rank: number;
  member_id: string;
  username: string | null;
  avatar_url: string | null;
  total_points: number;
  remaining_budget: number;
  player_count: number;
  stats: MemberStats;
};

export type UpcomingMatch = {
  date: string;
  opponent: string;
  home_or_away: string;
  series_id?: string | null;
};

export type PlayerSchedule = {
  player_id: string;
  team: string;
  upcoming: UpcomingMatch[];
};

export type PriceHistoryEntry = {
  date: string;
  price: number;
  delta_pct: number;
  week?: number;
  rival?: string;
};
export type PriceHistoryResponse = {
  player_id: string;
  entries: PriceHistoryEntry[];
};

export type TeamStandingEntry = {
  team_id: string;
  team_name: string;
  logo_url: string | null;
  wins: number;
  losses: number;
  win_rate: number;
  avg_kda: number | null;
  avg_gold_diff_15: number | null;
  avg_dpm: number | null;
  avg_cs_per_min: number | null;
  games_played: number;
};

export type TeamStandingsOut = {
  competition_name: string;
  entries: TeamStandingEntry[];
};

export type SeriesCalendarEntry = {
  series_id: string;
  team_home: string;
  team_away: string;
  date: string;
  week: number | null;
  status: string;
  result: string | null;
};

export type CalendarResponse = {
  series: SeriesCalendarEntry[];
};

export type TeamH2HStats = {
  team_id: string;
  team_name: string;
  wins: number;
  losses: number;
  avg_kda: number;
  avg_gold_diff_15: number;
  avg_dpm: number;
  avg_cs_per_min: number;
};

export type PlayerH2HStats = {
  player_id: string;
  name: string;
  role: string;
  image_url?: string | null;
  avg_kills: number;
  avg_deaths: number;
  avg_assists: number;
  avg_cs_per_min: number;
  avg_dpm: number;
  avg_kda: number;
  series_played: number;
};

export type H2HResponse = {
  series_id: string;
  date: string;
  status: string;
  result: string | null;
  team_home: TeamH2HStats;
  team_away: TeamH2HStats;
  players_home: PlayerH2HStats[];
  players_away: PlayerH2HStats[];
};

export const api = {
  leagues: {
    list: () => req<League[]>("/leagues/"),
    get: (id: string) => req<League>(`/leagues/${id}`),
    create: (name: string, maxMembers: number) =>
      req<League>("/leagues/", {
        method: "POST",
        body: JSON.stringify({ name, max_members: maxMembers }),
      }),
    join: (inviteCode: string) =>
      req("/leagues/join", {
        method: "POST",
        body: JSON.stringify({ invite_code: inviteCode }),
      }),
    delete: (id: string) => req(`/leagues/${id}`, { method: "DELETE" }),
    memberRoster: (leagueId: string, memberId: string) =>
      req<MemberRoster>(`/leagues/${leagueId}/members/${memberId}/roster`),
  },
  roster: {
    get: (leagueId: string) => req<Roster>(`/roster/${leagueId}`),
    move: (leagueId: string, rosterPlayerId: string, newSlot: Slot) =>
      req(`/roster/${leagueId}/move`, {
        method: "PATCH",
        body: JSON.stringify({ roster_player_id: rosterPlayerId, new_slot: newSlot }),
      }),
    toggleProtect: (leagueId: string, rosterPlayerId: string) =>
      req<{ message: string; is_protected: boolean }>(`/roster/${leagueId}/protect`, {
        method: "PATCH",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
    setSellIntent: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/sell`, {
        method: "POST",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
    cancelSellIntent: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/sell`, {
        method: "DELETE",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
  },
  market: {
    listings: (leagueId: string) =>
      req<Listing[]>(`/market/${leagueId}/listings`),
    buy: (leagueId: string, listingId: string) =>
      req(`/market/${leagueId}/buy`, {
        method: "POST",
        body: JSON.stringify({ listing_id: listingId }),
      }),
    sellOffers: (leagueId: string) =>
      req<SellOffer[]>(`/market/${leagueId}/sell-offers`),
    acceptOffer: (leagueId: string, offerId: string) =>
      req(`/market/${leagueId}/sell-offers/${offerId}/accept`, { method: "POST" }),
    rejectOffer: (leagueId: string, offerId: string) =>
      req(`/market/${leagueId}/sell-offers/${offerId}/reject`, { method: "POST" }),
    candidates: (leagueId: string) =>
      req<Candidate[]>(`/market/${leagueId}/candidates`),
    makeOffer: (leagueId: string, rosterPlayerId: string, amount: number) =>
      req<{ id: string; ask_price: number; message: string }>(`/market/${leagueId}/offer`, {
        method: "POST",
        body: JSON.stringify({ roster_player_id: rosterPlayerId, amount }),
      }),
  },
  scoring: {
    leaderboard: (leagueId: string, week?: number | null) =>
      req<LeaderboardResponse>(`/scoring/leaderboard/${leagueId}${week != null ? `?week=${week}` : ""}`),
    detailedLeaderboard: (leagueId: string) =>
      req<DetailedLeaderboardEntry[]>(`/scoring/leaderboard/${leagueId}/detailed`),
    playerHistory: (playerId: string) =>
      req<{ player: { id: string; name: string; team: string; role: string; image_url: string | null; current_price: number }; stats: PlayerMatchStat[]; total_points: number }>(`/scoring/player/${playerId}/history`),
  },
  splits: {
    active: () => req<Split | null>("/splits/active"),
    list: () => req<Split[]>("/splits/"),
    playerHistory: (playerId: string) => req<PlayerSplitHistory[]>(`/splits/player/${playerId}/history`),
  },
  players: {
    scout: (leagueId: string, competitionId?: string) =>
      req<ScoutPlayer[]>(`/players/scout?league_id=${leagueId}${competitionId ? `&competition_id=${competitionId}` : ""}`),
    schedule: (playerId: string) =>
      req<PlayerSchedule>(`/players/${playerId}/schedule`),
    seriesGames: (playerId: string, seriesId: string) =>
      req<SeriesGamesResponse>(`/players/${playerId}/series/${seriesId}/games`),
    priceHistory: (playerId: string) =>
      req<PriceHistoryResponse>(`/players/${playerId}/price-history`),
  },
  activity: {
    feed: (leagueId: string, limit = 50) =>
      req<ActivityEvent[]>(`/activity/${leagueId}?limit=${limit}`),
  },
  clause: {
    info: (leagueId: string, playerId: string) =>
      req<ClauseInfo>(`/market/${leagueId}/clause/${playerId}`),
    activate: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/clause/${rosterPlayerId}/activate`, { method: "POST" }),
    upgrade: (leagueId: string, rosterPlayerId: string, amount: number) =>
      req(`/market/${leagueId}/clause/${rosterPlayerId}/upgrade`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      }),
  },
  bids: {
    place: (leagueId: string, listingId: string, bidAmount: number) =>
      req<{ id: string; listing_id: string; member_id: string; bid_amount: number; placed_at: string; status: string }>(
        `/bids/${leagueId}/listings/${listingId}`,
        { method: "POST", body: JSON.stringify({ bid_amount: bidAmount }) },
      ),
    myBids: (leagueId: string) => req<MyBid[]>(`/bids/${leagueId}/my-bids`),
    cancel: (leagueId: string, listingId: string) =>
      req(`/bids/${leagueId}/listings/${listingId}`, { method: "DELETE" }),
  },
  teams: {
    standings: (leagueId: string, competitionId?: string) =>
      req<TeamStandingsOut>(
        `/teams/standings/${leagueId}${competitionId ? `?competition_id=${competitionId}` : ""}`
      ),
  },
  series: {
    calendar: (leagueId: string) =>
      req<CalendarResponse>(`/series/${leagueId}/calendar`),
    h2h: (seriesId: string, leagueId: string) =>
      req<H2HResponse>(`/series/${seriesId}/h2h?league_id=${leagueId}`),
  },
};

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
};

export type LeaderboardEntry = {
  rank: number;
  member_id: string;
  display_name: string | null;
  total_points: number;
  remaining_budget: number;
  player_count: number;
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
  kills: number;
  deaths: number;
  assists: number;
  cs_per_min: number;
  vision_score: number;
  fantasy_points: number;
  damage_share: number | null;
  gold_diff_at_15: number | null;
  competition_id: string;
  competition_name: string;
  matches?: { scheduled_at: string | null; team_1: string; team_2: string } | null;
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
  member: { id: string; remaining_budget: number; total_points: number; display_name: string | null } | null;
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
  member: { id: string; display_name: string | null; total_points: number };
  players: { slot: string; price_paid: number; split_points: number; players: { id: string; name: string; team: string; role: string; image_url: string | null } }[];
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
    join: (inviteCode: string, displayName?: string) =>
      req("/leagues/join", {
        method: "POST",
        body: JSON.stringify({ invite_code: inviteCode, display_name: displayName || null }),
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
    updateNick: (leagueId: string, displayName: string) =>
      req(`/leagues/${leagueId}/me`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      }),
  },
  scoring: {
    leaderboard: (leagueId: string) =>
      req<LeaderboardEntry[]>(`/scoring/leaderboard/${leagueId}`),
    playerHistory: (playerId: string) =>
      req<{ player: { id: string; name: string; team: string; role: string; image_url: string | null; current_price: number }; stats: PlayerMatchStat[]; total_points: number }>(`/scoring/player/${playerId}/history`),
  },
  splits: {
    active: () => req<Split | null>("/splits/active"),
    list: () => req<Split[]>("/splits/"),
    playerHistory: (playerId: string) => req<PlayerSplitHistory[]>(`/splits/player/${playerId}/history`),
  },
  activity: {
    feed: (leagueId: string, limit = 50) =>
      req<ActivityEvent[]>(`/activity/${leagueId}?limit=${limit}`),
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
};

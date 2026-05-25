/**
 * @module api
 *
 * Cliente HTTP centralizado para toda la comunicación con el backend FastAPI.
 *
 * Patrón: objeto `api` singleton con namespaces por dominio (leagues, roster,
 * market, scoring, etc.). Cada método devuelve una Promise tipada y lanza un
 * Error con el mensaje del servidor en caso de fallo.
 *
 * Uso típico:
 *   import { api } from "@/lib/api";
 *   const leagues = await api.leagues.list();
 *
 * Autenticación: cada request incluye automáticamente el JWT de Supabase Auth
 * en el header `Authorization: Bearer <token>`. Si no hay sesión activa, el
 * header simplemente se omite.
 */
"use client";

import { createClient } from "@/lib/supabase/client";
import type { MatchDetailEnvelope } from "@/types/match-detail";

/** URL base del backend (variable de entorno NEXT_PUBLIC_API_URL). */
const BASE = process.env.NEXT_PUBLIC_API_URL!;

/**
 * Obtiene el JWT de la sesión activa de Supabase.
 * Retorna null si no hay sesión (usuario no autenticado).
 */
async function token(): Promise<string | null> {
  const sb = createClient();
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? null;
}

/**
 * Función de request genérica y tipada.
 * Agrega el JWT al header, maneja errores HTTP y deserializa el body JSON.
 * En caso de 204 No Content, retorna undefined casteado al tipo T.
 *
 * @param path - Ruta relativa al BASE (ej: "/leagues/")
 * @param init - Opciones de fetch (method, body, headers adicionales)
 * @throws Error con el mensaje de detalle del backend (Pydantic o string)
 */
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
    const detail = body.detail;
    let message: string;
    if (!detail) {
      message = `HTTP ${res.status}`;
    } else if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      // Pydantic validation errors: [{loc, msg, type}, ...]
      message = detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; ");
    } else {
      message = JSON.stringify(detail);
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Competición de LoL (LEC, LCK, etc.) con su logo. */
export type Competition = {
  id: string;
  name: string;
  logo_url: string | null;
};

/** Resumen de un jugador tal como aparece en listings y rosters. */
export type PlayerBrief = {
  name: string;
  team: string;
  role: string;
  image_url: string | null;
  /** URL del escudo del equipo con subdirectorio de competición (LEC/ o LES/). */
  team_logo_url?: string | null;
  /** Precio de mercado actual en millones. */
  current_price: number;
  /** Puntos acumulados en la temporada completa. */
  total_season_points?: number | null;
  /** Puntos acumulados en el split activo. */
  split_points?: number | null;
  /** Variación de precio porcentual desde la última actualización. */
  last_price_change_pct?: number;
};

/**
 * Listing del mercado: un jugador puesto a la venta.
 * Puede tener bids activos (bid_count) y tiene una ventana de cierre (closes_at).
 */
export type Listing = {
  id: string;
  player_id: string;
  /** null si fue publicado por el sistema (no por un manager). */
  seller_id: string | null;
  league_id: string;
  /** Precio mínimo de puja. */
  ask_price: number;
  status: string;
  listed_at: string;
  /** ISO timestamp — cuando termina la subasta. null = sin expiración. */
  closes_at: string | null;
  players: PlayerBrief;
  bid_count?: number;
};

/** Entrada del leaderboard para un manager en una liga. */
export type LeaderboardEntry = {
  rank: number;
  member_id: string;
  username: string | null;
  avatar_url: string | null;
  total_points: number;
  remaining_budget: number;
  player_count: number;
  /** Puntos de la semana seleccionada (null si se pidió el total). */
  week_points?: number | null;
};

/**
 * Respuesta completa del endpoint de leaderboard.
 * Incluye metadatos de semanas disponibles para el navegador de jornadas.
 */
export type LeaderboardResponse = {
  entries: LeaderboardEntry[];
  /** Jornada en curso según el backend. */
  current_week: number | null;
  /** Lista de semanas con datos (para el selector de jornadas). */
  available_weeks: number[];
  /** Semana efectivamente consultada (null = acumulado total). */
  selected_week: number | null;
};

/** Evento del feed de actividad de la liga (compras, ventas, pujas). */
export type ActivityEvent = {
  id: string;
  /** Tipo de evento: "buy", "sell", "bid_won", etc. */
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

/** Estadísticas de un jugador en una serie (partido BO3/BO1) específica. */
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
  /** Desglose de puntos por categoría (kills, vision, etc.). */
  stat_breakdown?: Record<string, number>;
  matches?: { scheduled_at: string | null; team_1: string; team_2: string } | null;
};

/** Estadísticas de un juego individual dentro de una serie. */
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

/** Respuesta del detalle de juegos de una serie para un jugador. */
export type SeriesGamesResponse = {
  series_id: string;
  games: GameDetailStat[];
};

/** Puja realizada por el usuario en curso sobre un listing. */
export type MyBid = {
  id: string;
  listing_id: string;
  bid_amount: number;
  placed_at: string;
  /** "active" | "won" | "lost" | "cancelled" */
  status: string;
  player_name: string;
  player_role: string;
  player_image_url: string | null;
  player_team: string;
  listing_closes_at: string | null;
  listing_ask_price: number;
};

/**
 * Oferta de venta recibida por el manager para uno de sus jugadores.
 * Puede ser generada por el sistema ("sistema") o por otro manager ("manager").
 */
export type SellOffer = {
  id: string;
  ask_price: number;
  /** "pending" | "accepted" | "rejected" | "expired" */
  status: string;
  expires_at: string;
  player: PlayerBrief;
  /** "sistema" = oferta automática del mercado; "manager" = oferta de otro usuario. */
  offer_type: "sistema" | "manager";
  from_username?: string | null;
};

/** Jugador candidato en la wishlist del manager (para draft). */
export type Candidate = {
  id: string;
  player_id: string;
  ask_price: number;
  added_at: string;
  players: PlayerBrief;
};

/** Liga de fantasía con sus configuraciones y datos del miembro autenticado. */
export type League = {
  id: string;
  name: string;
  invite_code: string;
  owner_id: string;
  /** Presupuesto inicial de cada manager en millones. */
  budget: number;
  competition_id: string;
  competition_name: string;
  logo_url: string | null;
  max_members: number;
  is_active: boolean;
  /** "draft_market" (mercado + pujas) o "budget_pick" (selección directa). */
  game_mode: string;
  /** Datos del miembro autenticado en esta liga. null si el usuario no es miembro. */
  member: { id: string; remaining_budget: number; total_points: number; display_name: string | null } | null;
};

/** Slot disponible en el roster de un manager. */
export type Slot =
  | "starter_1" | "starter_2" | "starter_3" | "starter_4" | "starter_5"
  | "coach" | "bench_1" | "bench_2";

/** Jugador en el roster de un manager, con su slot y metadatos de gestión. */
export type RosterPlayer = {
  id: string;
  slot: Slot;
  price_paid: number;
  for_sale: boolean;
  is_protected: boolean;
  split_points?: number | null;
  /** Puntos de la jornada seleccionada (null si se consulta el total). */
  jornada_points?: number | null;
  /** Monto de la cláusula de rescisión activa. null si no tiene. */
  clause_amount: number | null;
  /** Timestamp de expiración de la cláusula. null si no tiene. */
  clause_expires_at: string | null;
  player: PlayerBrief & { id: string };
};

/** Split (temporada corta) de LEC con sus fechas. */
export type Split = {
  id: string;
  name: string;
  competition: string;
  start_date: string | null;
  end_date: string | null;
  /** Fecha en que se resetea el scoring para el siguiente split. */
  reset_date: string | null;
  is_active: boolean;
};

/**
 * Jugador con estadísticas agregadas para la vista de scouting.
 * Incluye promedios, totales y metadata de ownership/cláusulas.
 */
export type ScoutPlayer = {
  id: string;
  name: string;
  team: string;
  role: string;
  image_url: string | null;
  /** URL del escudo del equipo en Supabase Storage (subdirectorio LEC o LES según competición). */
  team_logo_url: string | null;
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
  /** Nombre del manager que posee este jugador. null si está libre. */
  owner_name: string | null;
  clause_amount?: number | null;
  clause_expires_at?: string | null;
  /** Si el dueño lo puso a la venta en el mercado. */
  for_sale?: boolean;
  for_sale_price?: number | null;
};

/** Estado de la cláusula de rescisión de un jugador para el manager autenticado. */
export type ClauseInfo = {
  is_owned: boolean;
  owned_by_me: boolean;
  clause_amount: number | null;
  clause_expires_at: string | null;
  /** true si la cláusula expiró (no se puede activar). */
  clause_expired: boolean;
  roster_player_id: string | null;
  for_sale?: boolean;
  owner_username?: string | null;
};

/** Historial de rendimiento de un jugador en un split completo. */
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

/** Roster completo de un manager con presupuesto y capitán. */
export type Roster = {
  league_id: string;
  member_id: string;
  remaining_budget: number;
  total_points: number;
  players: RosterPlayer[];
  captain_player_id: string | null;
  /** Jornada en curso según el backend. */
  current_week: number | null;
  captain_week: number | null;
  /** true si no existe snapshot para la semana solicitada. */
  snapshot_missing?: boolean;
  week?: number | null;
};

/** Respuesta al establecer un capitán. */
export type CaptainResponse = {
  success: boolean;
  captain_player_id: string | null;
  message: string;
};

/** Jugador disponible para fichar en modo budget_pick. */
export type AvailablePlayer = {
  id: string;
  name: string;
  team: string;
  role: string;
  image_url: string | null;
  current_price: number;
  last_price_change_pct: number;
  split_points: number;
  in_my_roster: boolean;
};

/** Resultado de fichar (pick) un jugador en modo budget_pick. */
export type PickResult = {
  ok: boolean;
  slot: string;
  player_id: string;
  price_paid: number;
  remaining_budget: number;
  /** ID del jugador liberado si se hizo swap. null si no hubo. */
  released_player_id: string | null;
};

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

/** Roster de un miembro específico de la liga, con snapshot semanal opcional. */
export type MemberRoster = {
  member: { id: string; total_points: number };
  players: { slot: string; price_paid: number | null; split_points: number; jornada_points?: number | null; is_captain?: boolean; players: { id: string; name: string; team: string; role: string; image_url: string | null } }[];
  captain_player_id?: string | null;
  snapshot_available?: boolean;
  week?: number | null;
};

/** Estadísticas agregadas de un manager (para columnas avanzadas del leaderboard). */
export type MemberStats = {
  avg_kda: number | null;
  avg_gold_diff_15: number | null;
  /** Promedio de puntos por jornada. */
  avg_pts_per_week: number | null;
  games_counted: number;
};

/** Entrada del leaderboard detallado con estadísticas de equipo incluidas. */
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

/** Próximo partido de un jugador. */
export type UpcomingMatch = {
  date: string;
  opponent: string;
  home_or_away: string;
  series_id?: string | null;
};

/** Calendario de próximos partidos de un jugador. */
export type PlayerSchedule = {
  player_id: string;
  team: string;
  upcoming: UpcomingMatch[];
};

/** Entrada del historial de precios de un jugador. */
export type PriceHistoryEntry = {
  /** Fecha de la actualización de precio. */
  date: string;
  price: number;
  /** Variación porcentual respecto al precio anterior. */
  delta_pct: number;
  week?: number;
  rival?: string;
  /** Puntos de fantasía obtenidos en la serie que generó el cambio de precio. */
  series_points?: number;
};

/** Historial completo de precios de un jugador. */
export type PriceHistoryResponse = {
  player_id: string;
  entries: PriceHistoryEntry[];
};

export type TeamBrief = {
  id: string;
  name: string;
  code: string | null;
  logo_url: string | null;
};

/** Estadísticas de un equipo LEC en la tabla de clasificación. */
export type TeamStandingEntry = {
  team_id: string;
  team_name: string;
  logo_url: string | null;
  /** Victorias en series (BO3). */
  wins: number;
  losses: number;
  /** Porcentaje de victorias sobre series jugadas. */
  win_rate: number;
  /** Victorias individuales en partidas (juegos). */
  game_wins: number;
  game_losses: number;
  avg_kda: number | null;
  avg_gold_diff_15: number | null;
  games_played: number;
};

/**
 * Respuesta completa de standings de equipos para una liga.
 * Incluye los umbrales de playoffs para colorear las filas.
 */
export type TeamStandingsOut = {
  competition_name: string;
  /** Primeros N equipos que clasifican directamente a playoffs. */
  playoff_spots: number;
  /** Equipos que entran al lower bracket de playoffs. */
  lower_bracket_spots: number;
  entries: TeamStandingEntry[];
};

/** Serie del calendario (BO3 programado, en curso o finalizado). */
export type SeriesCalendarEntry = {
  series_id: string;
  team_home: string;
  team_away: string;
  team_home_logo_url: string | null;
  team_away_logo_url: string | null;
  date: string;
  week: number | null;
  /** "scheduled" | "in_progress" | "finished" */
  status: string;
  /** Marcador final tipo "2-0", "1-2". null si no finalizó. */
  result: string | null;
};

/** Calendario completo de series de una liga. */
export type CalendarResponse = {
  series: SeriesCalendarEntry[];
};

/** Estadísticas de un equipo en un enfrentamiento head-to-head. */
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

/** Estadísticas de un jugador en un enfrentamiento head-to-head. */
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

/** Respuesta completa de un head-to-head entre dos equipos. */
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

/**
 * Objeto principal de acceso a la API.
 * Cada namespace agrupa los métodos por dominio de negocio.
 */
export const api = {
  leagues: {
    /** Obtiene todas las ligas del usuario autenticado. GET /leagues/ */
    list: () => req<League[]>("/leagues/"),
    /** Obtiene el detalle de una liga por ID, incluyendo datos del miembro. GET /leagues/:id */
    get: (id: string) => req<League>(`/leagues/${id}`),
    /**
     * Crea una nueva liga.
     * @param gameMode "draft_market" (subasta) o "budget_pick" (selección directa)
     * POST /leagues/
     */
    create: (name: string, maxMembers: number | null, gameMode: "draft_market" | "budget_pick" = "draft_market", competitionId: string) =>
      req<League>("/leagues/", {
        method: "POST",
        body: JSON.stringify({ name, max_members: maxMembers, game_mode: gameMode, competition_id: competitionId }),
      }),
    /** Une al usuario a una liga existente usando el código de invitación. POST /leagues/join */
    join: (inviteCode: string) =>
      req("/leagues/join", {
        method: "POST",
        body: JSON.stringify({ invite_code: inviteCode }),
      }),
    /** Elimina una liga (solo el owner puede hacerlo). DELETE /leagues/:id */
    delete: (id: string) => req(`/leagues/${id}`, { method: "DELETE" }),
    /**
     * Obtiene el roster de otro miembro de la liga (para ver su equipo).
     * @param week Si se pasa, devuelve el snapshot histórico de esa jornada.
     * GET /leagues/:leagueId/members/:memberId/roster
     */
    memberRoster: (leagueId: string, memberId: string, week?: number | null) =>
      req<MemberRoster>(`/leagues/${leagueId}/members/${memberId}/roster${week != null ? `?week=${week}` : ""}`),
  },
  roster: {
    /**
     * Obtiene el roster del usuario autenticado en la liga.
     * @param week Si se pasa, devuelve el snapshot histórico de esa jornada.
     * GET /roster/:leagueId
     */
    get: (leagueId: string, week?: number | null) =>
      req<Roster>(`/roster/${leagueId}${week != null ? `?week=${week}` : ""}`),
    /**
     * Lista jugadores disponibles para fichar en modo budget_pick.
     * @param role Filtra por posición (top, jungle, mid, adc, support).
     * GET /roster/:leagueId/available-players
     */
    availablePlayers: (leagueId: string, role?: string) =>
      req<AvailablePlayer[]>(`/roster/${leagueId}/available-players${role ? `?role=${role}` : ""}`),
    /**
     * Ficha un jugador en el slot indicado (modo budget_pick).
     * Si el slot ya tiene un jugador, lo libera y lo reemplaza.
     * POST /roster/:leagueId/pick
     */
    pick: (leagueId: string, playerId: string, slot: string) =>
      req<PickResult>(`/roster/${leagueId}/pick`, {
        method: "POST",
        body: JSON.stringify({ player_id: playerId, slot }),
      }),
    /** Mueve un jugador del roster a otro slot. PATCH /roster/:leagueId/move */
    move: (leagueId: string, rosterPlayerId: string, newSlot: Slot) =>
      req(`/roster/${leagueId}/move`, {
        method: "PATCH",
        body: JSON.stringify({ roster_player_id: rosterPlayerId, new_slot: newSlot }),
      }),
    /** Alterna la protección de un jugador (protegido no puede ser vendido). PATCH /roster/:leagueId/protect */
    toggleProtect: (leagueId: string, rosterPlayerId: string) =>
      req<{ message: string; is_protected: boolean }>(`/roster/${leagueId}/protect`, {
        method: "PATCH",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
    /**
     * Establece el capitán para una jornada específica.
     * El capitán multiplica los puntos de esa semana.
     * @param captainPlayerId null para quitar el capitán.
     * PUT /roster/:leagueId/lineups/:week/captain
     */
    setCaptain: (leagueId: string, week: number, captainPlayerId: string | null) =>
      req<CaptainResponse>(`/roster/${leagueId}/lineups/${week}/captain`, {
        method: "PUT",
        body: JSON.stringify({ captain_player_id: captainPlayerId }),
      }),
    /**
     * Marca un jugador como "en venta" para que el sistema genere una oferta.
     * POST /market/:leagueId/sell
     */
    setSellIntent: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/sell`, {
        method: "POST",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
    /** Cancela la intención de venta de un jugador. DELETE /market/:leagueId/sell */
    cancelSellIntent: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/sell`, {
        method: "DELETE",
        body: JSON.stringify({ roster_player_id: rosterPlayerId }),
      }),
  },
  market: {
    /** Lista todos los jugadores disponibles en el mercado de la liga. GET /market/:leagueId/listings */
    listings: (leagueId: string) =>
      req<Listing[]>(`/market/${leagueId}/listings`),
    /**
     * Compra directa de un listing (sin subasta, modo legacy).
     * POST /market/:leagueId/buy
     */
    buy: (leagueId: string, listingId: string) =>
      req(`/market/${leagueId}/buy`, {
        method: "POST",
        body: JSON.stringify({ listing_id: listingId }),
      }),
    /** Lista las ofertas de compra recibidas para los jugadores del manager. GET /market/:leagueId/sell-offers */
    sellOffers: (leagueId: string) =>
      req<SellOffer[]>(`/market/${leagueId}/sell-offers`),
    /** Acepta una oferta de venta recibida. POST /market/:leagueId/sell-offers/:offerId/accept */
    acceptOffer: (leagueId: string, offerId: string) =>
      req(`/market/${leagueId}/sell-offers/${offerId}/accept`, { method: "POST" }),
    /** Rechaza una oferta de venta recibida. POST /market/:leagueId/sell-offers/:offerId/reject */
    rejectOffer: (leagueId: string, offerId: string) =>
      req(`/market/${leagueId}/sell-offers/${offerId}/reject`, { method: "POST" }),
    /** Lista los jugadores candidatos (wishlist) del manager. GET /market/:leagueId/candidates */
    candidates: (leagueId: string) =>
      req<Candidate[]>(`/market/${leagueId}/candidates`),
    /**
     * Hace una oferta de compra a otro manager por uno de sus jugadores.
     * @param rosterPlayerId ID del jugador en el roster del vendedor (no el player_id global)
     * @param amount Monto ofrecido en millones
     * POST /market/:leagueId/offer
     */
    makeOffer: (leagueId: string, rosterPlayerId: string, amount: number) =>
      req<{ id: string; ask_price: number; message: string }>(`/market/${leagueId}/offer`, {
        method: "POST",
        body: JSON.stringify({ roster_player_id: rosterPlayerId, amount }),
      }),
  },
  scoring: {
    /**
     * Obtiene el leaderboard de managers de la liga.
     * @param week Si se pasa, filtra por jornada e incluye week_points en cada entrada.
     * GET /scoring/leaderboard/:leagueId
     */
    leaderboard: (leagueId: string, week?: number | null) =>
      req<LeaderboardResponse>(`/scoring/leaderboard/${leagueId}${week != null ? `?week=${week}` : ""}`),
    /**
     * Versión enriquecida del leaderboard con stats avanzadas de equipo.
     * Se carga en segundo plano (fase 2) para no bloquear el render inicial.
     * GET /scoring/leaderboard/:leagueId/detailed
     */
    detailedLeaderboard: (leagueId: string) =>
      req<DetailedLeaderboardEntry[]>(`/scoring/leaderboard/${leagueId}/detailed`),
    /**
     * Historial de puntos de un jugador en la liga (por serie/jornada).
     * GET /scoring/player/:playerId/history?league_id=:leagueId
     */
    playerHistory: (playerId: string, leagueId: string) =>
      req<{ player: { id: string; name: string; team: string; role: string; image_url: string | null; current_price: number }; stats: PlayerMatchStat[]; total_points: number }>(`/scoring/player/${playerId}/history?league_id=${leagueId}`),
  },
  splits: {
    /** Obtiene el split activo (el que se está jugando actualmente). GET /splits/active */
    active: () => req<Split | null>("/splits/active"),
    /** Lista todos los splits disponibles, activos e históricos. GET /splits/ */
    list: () => req<Split[]>("/splits/"),
    /** Historial de estadísticas de un jugador split a split. GET /splits/player/:playerId/history */
    playerHistory: (playerId: string) => req<PlayerSplitHistory[]>(`/splits/player/${playerId}/history`),
  },
  players: {
    /**
     * Lista todos los jugadores con stats agregadas para scouting.
     * Incluye ownership y cláusulas para saber si cada jugador está disponible.
     * GET /players/scout?league_id=:leagueId
     */
    scout: (leagueId: string) =>
      req<ScoutPlayer[]>(`/players/scout?league_id=${leagueId}`),
    /** Próximos partidos del jugador (para planificación de lineup). GET /players/:playerId/schedule */
    schedule: (playerId: string) =>
      req<PlayerSchedule>(`/players/${playerId}/schedule`),
    /** Estadísticas por juego dentro de una serie específica. GET /players/:playerId/series/:seriesId/games */
    seriesGames: (playerId: string, seriesId: string) =>
      req<SeriesGamesResponse>(`/players/${playerId}/series/${seriesId}/games`),
    /** Historial de precios del jugador para graficar la evolución. GET /players/:playerId/price-history */
    priceHistory: (playerId: string) =>
      req<PriceHistoryResponse>(`/players/${playerId}/price-history`),
  },
  activity: {
    /**
     * Feed de actividad reciente de la liga (compras, ventas, pujas resueltas).
     * @param limit Cantidad máxima de eventos a retornar (default 50).
     * GET /activity/:leagueId
     */
    feed: (leagueId: string, limit = 50) =>
      req<ActivityEvent[]>(`/activity/${leagueId}?limit=${limit}`),
  },
  clause: {
    /**
     * Consulta el estado de la cláusula de rescisión de un jugador para el manager autenticado.
     * GET /market/:leagueId/clause/:playerId
     */
    info: (leagueId: string, playerId: string) =>
      req<ClauseInfo>(`/market/${leagueId}/clause/${playerId}`),
    /**
     * Activa la cláusula de rescisión para forzar la venta de un jugador de otro manager.
     * POST /market/:leagueId/clause/:rosterPlayerId/activate
     */
    activate: (leagueId: string, rosterPlayerId: string) =>
      req(`/market/${leagueId}/clause/${rosterPlayerId}/activate`, { method: "POST" }),
    /**
     * Sube el monto de la cláusula de rescisión de uno de tus propios jugadores.
     * POST /market/:leagueId/clause/:rosterPlayerId/upgrade
     */
    upgrade: (leagueId: string, rosterPlayerId: string, amount: number) =>
      req(`/market/${leagueId}/clause/${rosterPlayerId}/upgrade`, {
        method: "POST",
        body: JSON.stringify({ amount }),
      }),
  },
  bids: {
    /**
     * Coloca o actualiza una puja sobre un listing del mercado.
     * El bid_amount debe ser >= ask_price del listing.
     * POST /bids/:leagueId/listings/:listingId
     */
    place: (leagueId: string, listingId: string, bidAmount: number) =>
      req<{ id: string; listing_id: string; member_id: string; bid_amount: number; placed_at: string; status: string }>(
        `/bids/${leagueId}/listings/${listingId}`,
        { method: "POST", body: JSON.stringify({ bid_amount: bidAmount }) },
      ),
    /** Lista todas las pujas activas e históricas del manager en la liga. GET /bids/:leagueId/my-bids */
    myBids: (leagueId: string) => req<MyBid[]>(`/bids/${leagueId}/my-bids`),
    /** Cancela una puja activa sobre un listing. DELETE /bids/:leagueId/listings/:listingId */
    cancel: (leagueId: string, listingId: string) =>
      req(`/bids/${leagueId}/listings/${listingId}`, { method: "DELETE" }),
  },
  teams: {
    list: () => req<TeamBrief[]>("/teams/"),
    /**
     * Clasificación de equipos LEC con stats para la liga indicada.
     * @param competitionId Filtra por competición específica (opcional).
     * GET /teams/standings/:leagueId
     */
    standings: (leagueId: string, competitionId?: string) =>
      req<TeamStandingsOut>(
        `/teams/standings/${leagueId}${competitionId ? `?competition_id=${competitionId}` : ""}`
      ),
  },
  series: {
    /** Calendario completo de series de la competición asociada a la liga. GET /series/:leagueId/calendar */
    calendar: (leagueId: string) =>
      req<CalendarResponse>(`/series/${leagueId}/calendar`),
    /**
     * Head-to-head entre los dos equipos de una serie, con stats de jugadores.
     * GET /series/:seriesId/h2h?league_id=:leagueId
     */
    h2h: (seriesId: string, leagueId: string) =>
      req<H2HResponse>(`/series/${seriesId}/h2h?league_id=${leagueId}`),
    /**
     * Detalle completo de una serie: lineup de la jornada, puntos por juego, etc.
     * GET /series/:seriesId/match-detail?league_id=:leagueId
     */
    matchDetail: (seriesId: string, leagueId: string) =>
      req<MatchDetailEnvelope>(`/series/${seriesId}/match-detail?league_id=${leagueId}`),
  },
  competitions: {
    /** Lista todas las competiciones disponibles para crear ligas. GET /competitions/ */
    list: () => req<Competition[]>("/competitions/"),
  },
};

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase
from utils.teams import resolve_team_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level schedule cache: team_name -> (matches, cached_at)
_schedule_cache: dict[str, tuple[list, datetime]] = {}
_SCHEDULE_CACHE_TTL_SECONDS = 3600  # 60 minutes

Role = Literal["top", "jungle", "mid", "adc", "support", "coach"]


class PlayerOut(BaseModel):
    id: UUID
    name: str
    team: str
    role: Role
    league: str
    current_price: float
    image_url: str | None
    is_active: bool


class ScoutPlayer(BaseModel):
    id: UUID
    name: str
    team: str
    role: Role
    image_url: str | None
    current_price: float
    last_price_change_pct: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    total_kills: float
    total_deaths: float
    total_assists: float
    avg_cs_per_min: float
    avg_gold_diff_15: float = 0.0
    avg_xp_diff_15: float = 0.0
    avg_dpm: float
    avg_vision_score: float
    avg_points: float
    total_points: float
    owner_name: str | None
    clause_amount: float | None = None
    clause_expires_at: str | None = None
    for_sale: bool = False
    for_sale_price: float | None = None


@router.get("/", response_model=list[PlayerOut])
async def list_players(
    role: Role | None = Query(None),
    team: str | None = Query(None),
    league: str = Query("LEC"),
    supabase: Client = Depends(get_supabase),
) -> list[PlayerOut]:
    query = supabase.table("players").select(
        "id, name, team, role, league, current_price, image_url, is_active"
    ).eq("league", league).eq("is_active", True)

    if role:
        query = query.eq("role", role)
    if team:
        query = query.eq("team", team)

    response = query.order("team").order("role").execute()
    return response.data


@router.get("/scout", response_model=list[ScoutPlayer])
async def scout_players(
    league_id: UUID = Query(..., description="ID de la liga para resolver owner_name"),
    competition_id: str | None = Query(None, description="Filtrar stats por competición/split"),
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[ScoutPlayer]:
    """Todos los jugadores activos con stats promedio y owner dentro de la liga dada."""

    # 1. Todos los jugadores activos
    players_resp = (
        supabase.table("players")
        .select("id, name, team, role, image_url, current_price, last_price_change_pct")
        .eq("is_active", True)
        .order("name")
        .execute()
    )
    players = players_resp.data or []
    if not players:
        return []

    player_ids = [p["id"] for p in players]

    # 2. Stats desde player_series_stats (nivel serie, no game)
    # Si se filtra por competition_id, join con series para filtrar en Python
    if competition_id:
        stats_resp = (
            supabase.table("player_series_stats")
            .select("player_id, avg_kills, avg_deaths, avg_assists, avg_cs_per_min, avg_dpm, avg_vision_score, series_points, series(competition_id)")
            .in_("player_id", player_ids)
            .execute()
        )
        raw_stats = [
            row for row in (stats_resp.data or [])
            if (row.get("series") or {}).get("competition_id") == competition_id
        ]
    else:
        stats_resp = (
            supabase.table("player_series_stats")
            .select("player_id, avg_kills, avg_deaths, avg_assists, avg_cs_per_min, avg_dpm, avg_vision_score, series_points")
            .in_("player_id", player_ids)
            .execute()
        )
        raw_stats = stats_resp.data or []

    # Agregar por player_id — cada row ya es un promedio de serie
    buckets: dict[str, list] = defaultdict(list)
    for row in raw_stats:
        buckets[row["player_id"]].append(row)

    # 2b. Calcular avg_gold_diff_15 y avg_xp_diff_15 desde player_game_stats.
    # Una sola query bulk para todos los jugadores; filtramos por competition_id en Python.
    gold_diff_map: dict[str, float] = {}
    xp_diff_map: dict[str, float] = {}
    pgs_resp = (
        supabase.table("player_game_stats")
        .select("player_id, gold_diff_15, xp_diff_15, games(series_id, series(competition_id))")
        .in_("player_id", player_ids)
        .execute()
    )
    gold_by_player: dict[str, list[float]] = defaultdict(list)
    xp_by_player: dict[str, list[float]] = defaultdict(list)
    for pgs_row in (pgs_resp.data or []):
        if competition_id:
            game = pgs_row.get("games") or {}
            series_data = game.get("series") or {}
            if str(series_data.get("competition_id") or "") != competition_id:
                continue
        pid = pgs_row["player_id"]
        if pgs_row.get("gold_diff_15") is not None:
            gold_by_player[pid].append(float(pgs_row["gold_diff_15"]))
        if pgs_row.get("xp_diff_15") is not None:
            xp_by_player[pid].append(float(pgs_row["xp_diff_15"]))
    for pid in player_ids:
        gold_vals = gold_by_player.get(pid, [])
        xp_vals = xp_by_player.get(pid, [])
        if gold_vals:
            gold_diff_map[pid] = round(sum(gold_vals) / len(gold_vals), 1)
        if xp_vals:
            xp_diff_map[pid] = round(sum(xp_vals) / len(xp_vals), 1)

    def avg(rows: list, field: str) -> float:
        vals = [r[field] for r in rows if r.get(field) is not None]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    def total(rows: list, field: str) -> float:
        vals = [r[field] for r in rows if r.get(field) is not None]
        return round(sum(vals), 3)

    # 3. Owners: roster_players → rosters → league_members → profiles filtrado por league_id
    # Traemos todos los roster_players de la liga en una query con joins
    owners_resp = (
        supabase.table("roster_players")
        .select(
            "id, player_id, clause_amount, clause_expires_at, for_sale,"
            " rosters(member_id, league_members(league_id, user_id))"
        )
        .in_("player_id", player_ids)
        .execute()
    )

    # Construir mapa player_id → user_id para esta liga
    # y mapa player_id → cláusula para esta liga
    # y mapa player_id → (for_sale, roster_player_id)
    player_owner_user: dict[str, str] = {}
    player_clause: dict[str, dict] = {}
    player_for_sale: dict[str, bool] = {}
    roster_player_id_map: dict[str, str] = {}  # player_id → roster_player_id
    for row in (owners_resp.data or []):
        roster = row.get("rosters") or {}
        lm = roster.get("league_members") or {}
        if lm.get("league_id") == str(league_id):
            pid = row["player_id"]
            player_owner_user[pid] = lm["user_id"]
            player_clause[pid] = {
                "clause_amount": row.get("clause_amount"),
                "clause_expires_at": row.get("clause_expires_at"),
            }
            player_for_sale[pid] = bool(row.get("for_sale", False))
            roster_player_id_map[pid] = row["id"]

    # Resolver usernames de profiles
    owner_user_ids = list(set(player_owner_user.values()))
    username_map: dict[str, str] = {}
    if owner_user_ids:
        profiles_resp = (
            supabase.table("profiles")
            .select("id, username")
            .in_("id", owner_user_ids)
            .execute()
        )
        username_map = {p["id"]: p["username"] for p in (profiles_resp.data or [])}

    # 3b. Fetch latest pending system sell_offer price for for_sale players
    # Sistema = from_member_id IS NULL
    for_sale_roster_player_ids = [
        roster_player_id_map[pid] for pid, fs in player_for_sale.items() if fs
    ]
    player_for_sale_price: dict[str, float] = {}
    if for_sale_roster_player_ids:
        so_resp = (
            supabase.table("sell_offers")
            .select("roster_player_id, ask_price, from_member_id")
            .in_("roster_player_id", for_sale_roster_player_ids)
            .eq("status", "pending")
            .is_("from_member_id", "null")
            .order("created_at", desc=True)
            .execute()
        )
        # Keep only the most recent system offer per roster_player (query already ordered)
        seen_rp: set[str] = set()
        for so_row in (so_resp.data or []):
            rp_id = so_row["roster_player_id"]
            if rp_id not in seen_rp:
                seen_rp.add(rp_id)
                # Map back to player_id
                for pid, rp_id_val in roster_player_id_map.items():
                    if rp_id_val == rp_id:
                        player_for_sale_price[pid] = float(so_row["ask_price"])
                        break

    # 4. Ensamblar resultado
    result: list[ScoutPlayer] = []
    for p in players:
        pid = p["id"]
        rows = buckets.get(pid, [])
        user_id = player_owner_user.get(pid)
        owner_name = username_map.get(user_id) if user_id else None
        clause_data = player_clause.get(pid, {})
        raw_clause_amount = clause_data.get("clause_amount")
        result.append(ScoutPlayer(
            id=pid,
            name=p["name"],
            team=p["team"],
            role=p["role"],
            image_url=p.get("image_url"),
            current_price=float(p.get("current_price") or 0),
            last_price_change_pct=float(p.get("last_price_change_pct") or 0),
            avg_kills=avg(rows, "avg_kills"),
            avg_deaths=avg(rows, "avg_deaths"),
            avg_assists=avg(rows, "avg_assists"),
            total_kills=total(rows, "avg_kills"),
            total_deaths=total(rows, "avg_deaths"),
            total_assists=total(rows, "avg_assists"),
            avg_cs_per_min=avg(rows, "avg_cs_per_min"),
            avg_gold_diff_15=gold_diff_map.get(pid, 0.0),
            avg_xp_diff_15=xp_diff_map.get(pid, 0.0),
            avg_dpm=avg(rows, "avg_dpm"),
            avg_vision_score=avg(rows, "avg_vision_score"),
            avg_points=avg(rows, "series_points"),
            total_points=total(rows, "series_points"),
            owner_name=owner_name,
            clause_amount=float(raw_clause_amount) if raw_clause_amount is not None else None,
            clause_expires_at=clause_data.get("clause_expires_at"),
            for_sale=player_for_sale.get(pid, False),
            for_sale_price=player_for_sale_price.get(pid),
        ))

    return result


class GameDetailStat(BaseModel):
    game_number: int
    result: int | None
    kills: int
    deaths: int
    assists: int
    cs_per_min: float
    dpm: float
    game_points: float


class SeriesGamesResponse(BaseModel):
    series_id: str
    games: list[GameDetailStat]


@router.get("/{player_id}/series/{series_id}/games", response_model=SeriesGamesResponse)
async def get_player_series_games(
    player_id: UUID,
    series_id: UUID,
    supabase: Client = Depends(get_supabase),
) -> SeriesGamesResponse:
    """Devuelve stats game-by-game de un jugador en una serie específica."""
    # Resolver team_id del jugador para determinar resultado por game
    player_resp = (
        supabase.table("players")
        .select("team")
        .eq("id", str(player_id))
        .single()
        .execute()
    )
    player_team_name: str = (player_resp.data or {}).get("team", "") if player_resp.data else ""
    player_team_id: str | None = resolve_team_id(supabase, player_team_name) if player_team_name else None

    # Fetch games in this series
    games_resp = (
        supabase.table("games")
        .select("id, game_number, winner_id")
        .eq("series_id", str(series_id))
        .order("game_number", desc=False)
        .execute()
    )
    game_rows = games_resp.data or []
    game_ids = [g["id"] for g in game_rows]
    game_meta: dict[str, dict] = {g["id"]: g for g in game_rows}

    if not game_ids:
        return SeriesGamesResponse(series_id=str(series_id), games=[])

    # Fetch player_game_stats for these games
    pgs_resp = (
        supabase.table("player_game_stats")
        .select("game_id, kills, deaths, assists, cs_per_min, dpm, game_points")
        .eq("player_id", str(player_id))
        .in_("game_id", game_ids)
        .execute()
    )
    pgs_rows = pgs_resp.data or []

    pgs_by_game_id: dict[str, dict] = {row["game_id"]: row for row in pgs_rows}

    detail_games: list[GameDetailStat] = []
    for game in game_rows:
        gid = game["id"]
        row = pgs_by_game_id.get(gid)
        if row is None:
            continue
        winner_id = game.get("winner_id")
        if winner_id is None:
            result = None
        elif player_team_id and winner_id == player_team_id:
            result = 1
        else:
            result = 0

        detail_games.append(GameDetailStat(
            game_number=game.get("game_number") or 0,
            result=result,
            kills=int(row.get("kills") or 0),
            deaths=int(row.get("deaths") or 0),
            assists=int(row.get("assists") or 0),
            cs_per_min=round(float(row.get("cs_per_min") or 0), 2),
            dpm=round(float(row.get("dpm") or 0), 1),
            game_points=round(float(row.get("game_points") or 0), 2),
        ))

    return SeriesGamesResponse(series_id=str(series_id), games=detail_games)


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(
    player_id: UUID,
    supabase: Client = Depends(get_supabase),
) -> PlayerOut:
    response = (
        supabase.table("players")
        .select("id, name, team, role, league, current_price, image_url, is_active")
        .eq("id", str(player_id))
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado")
    return response.data


class UpcomingMatch(BaseModel):
    date: str           # "2026-03-28"
    opponent: str       # "Fnatic"
    home_or_away: str   # "home" | "away"
    series_id: str | None = None  # UUID of the series row


class PlayerScheduleOut(BaseModel):
    player_id: str
    team: str
    upcoming: list[UpcomingMatch]


@router.get("/{player_id}/schedule", response_model=PlayerScheduleOut)
def get_player_schedule(
    player_id: UUID,
    supabase: Client = Depends(get_supabase),
) -> PlayerScheduleOut:
    """
    Devuelve las próximas partidas programadas del equipo del jugador.
    Usa module-level cache con TTL de 60 minutos por equipo.
    Corre en threadpool (sync def). Envuelto en try/except — nunca rompe el cliente.
    """
    try:
        # 1. Fetch player row
        player_resp = (
            supabase.table("players")
            .select("id, team, role")
            .eq("id", str(player_id))
            .single()
            .execute()
        )
        if not player_resp.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado")

        player = player_resp.data
        player_team: str = player.get("team") or ""
        player_role: str = player.get("role") or ""

        # 2. Coaches don't play — return empty immediately
        if player_role == "coach":
            return PlayerScheduleOut(player_id=str(player_id), team=player_team, upcoming=[])

        # 3. Check module-level cache (TTL = 60 min)
        now = datetime.now(tz=timezone.utc)
        cached = _schedule_cache.get(player_team)
        if cached is not None:
            cached_matches, cached_at = cached
            age_seconds = (now - cached_at).total_seconds()
            if age_seconds < _SCHEDULE_CACHE_TTL_SECONDS:
                return PlayerScheduleOut(
                    player_id=str(player_id),
                    team=player_team,
                    upcoming=cached_matches[:3],
                )

        # 4. Cache miss — resolve team UUID from teams table via alias matching.
        # players.team stores a name like "G2 Esports" or "Fnatic".
        # teams.aliases is an array that includes the canonical name and variants.
        team_id: str | None = resolve_team_id(supabase, player_team)

        if not team_id:
            logger.warning(
                "get_player_schedule: no team found for player %s team='%s'",
                player_id,
                player_team,
            )
            _schedule_cache[player_team] = ([], now)
            return PlayerScheduleOut(player_id=str(player_id), team=player_team, upcoming=[])

        # 5. Query series for upcoming scheduled matches
        today_str = now.strftime("%Y-%m-%d")

        # Fetch series where this team plays at home — join away team for opponent name
        home_resp = (
            supabase.table("series")
            .select("id, date, team_home_id, team_away_id, teams!series_team_away_id_fkey(name)")
            .eq("team_home_id", team_id)
            .eq("status", "scheduled")
            .gte("date", today_str)
            .order("date", desc=False)
            .limit(4)
            .execute()
        )

        # Fetch series where this team plays away — join home team for opponent name
        away_resp = (
            supabase.table("series")
            .select("id, date, team_home_id, team_away_id, teams!series_team_home_id_fkey(name)")
            .eq("team_away_id", team_id)
            .eq("status", "scheduled")
            .gte("date", today_str)
            .order("date", desc=False)
            .limit(4)
            .execute()
        )

        # 6. Build UpcomingMatch list from both result sets
        upcoming: list[UpcomingMatch] = []

        for row in (home_resp.data or []):
            opponent_info = row.get("teams") or {}
            opponent_name: str = opponent_info.get("name") or "Unknown"
            upcoming.append(
                UpcomingMatch(
                    date=str(row["date"]),
                    opponent=opponent_name,
                    home_or_away="home",
                    series_id=str(row["id"]),
                )
            )

        for row in (away_resp.data or []):
            opponent_info = row.get("teams") or {}
            opponent_name = opponent_info.get("name") or "Unknown"
            upcoming.append(
                UpcomingMatch(
                    date=str(row["date"]),
                    opponent=opponent_name,
                    home_or_away="away",
                    series_id=str(row["id"]),
                )
            )

        # Sort combined list by date ASC, keep up to 3
        upcoming.sort(key=lambda m: m.date)
        upcoming = upcoming[:3]

        # 7. Store in cache and return
        _schedule_cache[player_team] = (upcoming, now)
        return PlayerScheduleOut(player_id=str(player_id), team=player_team, upcoming=upcoming)

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "get_player_schedule: unexpected error for player %s: %s",
            player_id,
            exc,
        )
        return PlayerScheduleOut(player_id=str(player_id), team="", upcoming=[])

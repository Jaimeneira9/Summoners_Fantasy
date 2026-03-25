from collections import defaultdict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()

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
    avg_gold_diff_15: float
    avg_xp_diff_15: float
    avg_dpm: float
    avg_vision_score: float
    avg_points: float
    total_points: float
    owner_name: str | None


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

    # 2. Stats promedio desde player_game_stats
    stats_resp = (
        supabase.table("player_game_stats")
        .select("player_id, kills, deaths, assists, cs_per_min, gold_diff_15, xp_diff_15, dpm, vision_score, game_points")
        .in_("player_id", player_ids)
        .execute()
    )
    raw_stats = stats_resp.data or []

    # Agregar por player_id
    buckets: dict[str, list] = defaultdict(list)
    for row in raw_stats:
        buckets[row["player_id"]].append(row)

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
        .select("player_id, rosters(member_id, league_members(league_id, user_id))")
        .in_("player_id", player_ids)
        .execute()
    )

    # Construir mapa player_id → user_id para esta liga
    player_owner_user: dict[str, str] = {}
    for row in (owners_resp.data or []):
        roster = row.get("rosters") or {}
        lm = roster.get("league_members") or {}
        if lm.get("league_id") == str(league_id):
            player_owner_user[row["player_id"]] = lm["user_id"]

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

    # 4. Ensamblar resultado
    result: list[ScoutPlayer] = []
    for p in players:
        pid = p["id"]
        rows = buckets.get(pid, [])
        user_id = player_owner_user.get(pid)
        owner_name = username_map.get(user_id) if user_id else None
        result.append(ScoutPlayer(
            id=pid,
            name=p["name"],
            team=p["team"],
            role=p["role"],
            image_url=p.get("image_url"),
            current_price=float(p.get("current_price") or 0),
            last_price_change_pct=float(p.get("last_price_change_pct") or 0),
            avg_kills=avg(rows, "kills"),
            avg_deaths=avg(rows, "deaths"),
            avg_assists=avg(rows, "assists"),
            total_kills=total(rows, "kills"),
            total_deaths=total(rows, "deaths"),
            total_assists=total(rows, "assists"),
            avg_cs_per_min=avg(rows, "cs_per_min"),
            avg_gold_diff_15=avg(rows, "gold_diff_15"),
            avg_xp_diff_15=avg(rows, "xp_diff_15"),
            avg_dpm=avg(rows, "dpm"),
            avg_vision_score=avg(rows, "vision_score"),
            avg_points=avg(rows, "game_points"),
            total_points=total(rows, "game_points"),
            owner_name=owner_name,
        ))

    return result


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

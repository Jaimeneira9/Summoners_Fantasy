from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LeagueCreate(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    max_members: int = Field(default=8, ge=2, le=9)


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None
    remaining_budget: float
    total_points: float


class MemberBrief(BaseModel):
    id: UUID
    remaining_budget: float
    total_points: float
    display_name: str | None


class LeagueOut(BaseModel):
    id: UUID
    name: str
    invite_code: str
    owner_id: UUID
    competition: str
    budget: float
    max_members: int
    is_active: bool
    member: MemberBrief | None = None


class JoinRequest(BaseModel):
    invite_code: str
    display_name: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[LeagueOut])
async def list_leagues(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[LeagueOut]:
    """Ligas en las que el usuario es miembro o propietario."""
    memberships = (
        supabase.table("league_members")
        .select("league_id, id, remaining_budget, total_points, display_name")
        .eq("user_id", user["id"])
        .execute()
    )
    if not memberships.data:
        return []

    member_by_league = {m["league_id"]: m for m in memberships.data}
    league_ids = list(member_by_league.keys())

    response = (
        supabase.table("fantasy_leagues")
        .select("id, name, invite_code, owner_id, competition, budget, max_members, is_active")
        .in_("id", league_ids)
        .execute()
    )
    results = []
    for league in response.data:
        m = member_by_league.get(league["id"])
        results.append({
            **league,
            "member": {
                "id": m["id"],
                "remaining_budget": m["remaining_budget"],
                "total_points": m["total_points"],
                "display_name": m.get("display_name"),
            } if m else None,
        })
    return results


@router.post("/", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
async def create_league(
    body: LeagueCreate,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> LeagueOut:
    """Crea una liga y añade al creador como primer miembro. Inicializa el mercado."""
    league_resp = (
        supabase.table("fantasy_leagues")
        .insert({
            "name": body.name,
            "owner_id": user["id"],
            "max_members": body.max_members,
        })
        .execute()
    )
    league = league_resp.data[0]

    supabase.table("league_members").insert({
        "league_id": league["id"],
        "user_id": user["id"],
    }).execute()

    # Inicializar mercado inmediatamente (8 listings, closes_at = now + 24h)
    try:
        from market.refresh import initialize_league_market
        initialize_league_market(supabase, league["id"])
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to initialize market for league %s: %s", league["id"], exc)

    return league


@router.post("/join", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def join_by_invite_code(
    body: JoinRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> MemberOut:
    """Unirse a una liga conociendo solo el invite_code (sin necesitar el league_id)."""
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("id, invite_code, max_members, is_active")
        .eq("invite_code", body.invite_code)
        .single()
        .execute()
    )
    league = league_resp.data
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de invitación no válido")
    if not league["is_active"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La liga no está activa")

    existing = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league["id"])
        .eq("user_id", user["id"])
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya eres miembro de esta liga")

    count_resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league["id"])
        .execute()
    )
    if len(count_resp.data) >= league["max_members"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La liga está llena")

    member_resp = (
        supabase.table("league_members")
        .insert({
            "league_id": league["id"],
            "user_id": user["id"],
            "display_name": body.display_name,
        })
        .execute()
    )
    return member_resp.data[0]


@router.get("/{league_id}", response_model=LeagueOut)
async def get_league(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> LeagueOut:
    """Detalle de una liga. Solo accesible si el usuario es miembro."""
    member_resp = (
        supabase.table("league_members")
        .select("id, remaining_budget, total_points, display_name")
        .eq("league_id", str(league_id))
        .eq("user_id", user["id"])
        .execute()
    )
    if not member_resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")

    response = (
        supabase.table("fantasy_leagues")
        .select("id, name, invite_code, owner_id, competition, budget, max_members, is_active")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")

    m = member_resp.data[0]
    return {
        **response.data,
        "member": {
            "id": m["id"],
            "remaining_budget": m["remaining_budget"],
            "total_points": m["total_points"],
            "display_name": m.get("display_name"),
        },
    }


@router.get("/{league_id}/members", response_model=list[MemberOut])
async def list_members(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[MemberOut]:
    _assert_member(supabase, str(league_id), user["id"])

    response = (
        supabase.table("league_members")
        .select("id, user_id, display_name, remaining_budget, total_points")
        .eq("league_id", str(league_id))
        .execute()
    )
    return response.data


@router.post("/{league_id}/join", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def join_league(
    league_id: UUID,
    body: JoinRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> MemberOut:
    """Unirse a una liga mediante invite_code."""
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("id, invite_code, max_members, is_active")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    league = league_resp.data
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")
    if not league["is_active"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La liga no está activa")
    if league["invite_code"] != body.invite_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Código de invitación incorrecto")

    # Comprobar si ya es miembro
    existing = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", str(league_id))
        .eq("user_id", user["id"])
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya eres miembro de esta liga")

    # Comprobar aforo
    count_resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", str(league_id))
        .execute()
    )
    if len(count_resp.data) >= league["max_members"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La liga está llena")

    member_resp = (
        supabase.table("league_members")
        .insert({
            "league_id": str(league_id),
            "user_id": user["id"],
            "display_name": body.display_name,
        })
        .execute()
    )
    return member_resp.data[0]


# ---------------------------------------------------------------------------
# Endpoints: perfil de miembro
# ---------------------------------------------------------------------------

class UpdateNickRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=32)


@router.patch("/{league_id}/me", response_model=MemberOut)
async def update_my_nick(
    league_id: UUID,
    body: UpdateNickRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> MemberOut:
    """Actualiza el nick del usuario en una liga."""
    existing = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", str(league_id))
        .eq("user_id", user["id"])
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")

    resp = (
        supabase.table("league_members")
        .update({"display_name": body.display_name})
        .eq("id", existing.data[0]["id"])
        .execute()
    )
    return resp.data[0]


@router.get("/{league_id}/members/{member_id}/roster")
async def get_member_roster(
    league_id: UUID,
    member_id: UUID,
    week: int | None = None,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Devuelve el roster público de otro miembro de la liga.

    Si se pasa ?week=N, intenta servir el equipo snapshotted de esa jornada.
    Si no hay snapshot para esa semana, cae al roster actual.
    """
    _assert_member(supabase, str(league_id), user["id"])

    member_resp = (
        supabase.table("league_members")
        .select("id, display_name, total_points")
        .eq("id", str(member_id))
        .eq("league_id", str(league_id))
        .execute()
    )
    if not member_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado")
    member = member_resp.data[0]

    # Obtener competition activa (necesaria para snapshot y split_points)
    active_comp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    active_comp_id: str | None = active_comp.data[0]["id"] if active_comp.data else None

    # Si se pidió semana y hay competition activa, servir desde snapshot (sin fallback al roster actual)
    roster_players: list[dict] = []
    used_snapshot = False
    snap_captain_player_id: str | None = None

    if week is not None and active_comp_id:
        snap_resp = (
            supabase.table("lineup_snapshots")
            .select("slot, player_id, captain_player_id, created_at")
            .eq("member_id", str(member_id))
            .eq("competition_id", active_comp_id)
            .eq("week", week)
            .order("created_at", desc=True)
            .execute()
        )
        if not snap_resp.data:
            # No snapshot para esta semana: devolver respuesta explícita sin fallback
            return {
                "member": member,
                "players": [],
                "captain_player_id": None,
                "snapshot_available": False,
                "week": week,
            }

        # Tomar el más reciente (ORDER BY created_at DESC) — primer registro
        snap_captain_player_id = snap_resp.data[0].get("captain_player_id")

        # Fetch player details for snapshotted player_ids
        snapped_player_ids = [r["player_id"] for r in snap_resp.data if r.get("player_id")]
        snap_slot_map = {r["slot"]: r["player_id"] for r in snap_resp.data}
        players_map: dict[str, dict] = {}
        if snapped_player_ids:
            p_resp = (
                supabase.table("players")
                .select("id, name, team, role, image_url, current_price")
                .in_("id", snapped_player_ids)
                .execute()
            )
            players_map = {p["id"]: p for p in (p_resp.data or [])}

        for slot, player_id in snap_slot_map.items():
            if player_id and player_id in players_map:
                roster_players.append({
                    "slot": slot,
                    "price_paid": None,
                    "players": players_map[player_id],
                    "is_captain": player_id == snap_captain_player_id if snap_captain_player_id else False,
                })
        used_snapshot = True

    # For the fallback (current roster), we need captain_player_id from captain_selections
    fallback_captain_player_id: str | None = None
    if not used_snapshot:
        roster_resp = (
            supabase.table("rosters")
            .select("id")
            .eq("member_id", str(member_id))
            .execute()
        )
        if not roster_resp.data:
            return {"member": member, "players": [], "snapshot_available": False, "week": week}

        roster_id = roster_resp.data[0]["id"]
        players_resp = (
            supabase.table("roster_players")
            .select("slot, price_paid, players(id, name, team, role, image_url, current_price)")
            .eq("roster_id", roster_id)
            .execute()
        )
        roster_players = players_resp.data or []

        # Fetch current week's captain selection for fallback path
        if active_comp_id:
            current_week_resp = (
                supabase.table("series")
                .select("week")
                .eq("competition_id", active_comp_id)
                .eq("status", "finished")
                .order("week", desc=True)
                .limit(1)
                .execute()
            )
            if current_week_resp.data:
                current_week_val = current_week_resp.data[0]["week"]
                cap_resp = (
                    supabase.table("captain_selections")
                    .select("captain_player_id")
                    .eq("member_id", str(member_id))
                    .eq("week", current_week_val)
                    .limit(1)
                    .execute()
                )
                if cap_resp.data and cap_resp.data[0].get("captain_player_id"):
                    fallback_captain_player_id = cap_resp.data[0]["captain_player_id"]

    # Enrich with split/jornada points from player_series_stats
    player_ids = [rp["players"]["id"] for rp in roster_players if rp.get("players")]
    points_map: dict[str, float] = {}
    if player_ids and active_comp_id:
        # Scope series by week (finished only) if provided, else full split
        series_filter = (
            supabase.table("series")
            .select("id")
            .eq("competition_id", active_comp_id)
        )
        if week is not None:
            series_filter = series_filter.eq("week", week).eq("status", "finished")
        series_resp2 = series_filter.execute()
        active_series_ids = [s["id"] for s in (series_resp2.data or [])]

        if active_series_ids:
            stats_resp = (
                supabase.table("player_series_stats")
                .select("player_id, series_points")
                .in_("player_id", player_ids)
                .in_("series_id", active_series_ids)
                .execute()
            )
            for row in (stats_resp.data or []):
                pid = row["player_id"]
                points_map[pid] = points_map.get(pid, 0.0) + float(row["series_points"] or 0)

    # Attach split_points/jornada_points and is_captain to each player entry
    enriched = []
    for rp in roster_players:
        entry = dict(rp)
        if entry.get("players"):
            pid = entry["players"]["id"]
            pts = round(points_map.get(pid, 0.0), 2)
            entry["split_points"] = pts
            entry["jornada_points"] = pts if week is not None else None
            # is_captain only added when not already set (snapshot path sets it above)
            if "is_captain" not in entry:
                entry["is_captain"] = (pid == fallback_captain_player_id) if fallback_captain_player_id else False
        enriched.append(entry)

    response: dict = {"member": member, "players": enriched}
    if week is not None:
        response["captain_player_id"] = snap_captain_player_id
        response["snapshot_available"] = used_snapshot
        response["week"] = week
    return response


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_league(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> None:
    """Elimina una liga. Solo el propietario puede hacerlo."""
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("id, owner_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")
    if str(league_resp.data["owner_id"]) != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede eliminar la liga")

    supabase.table("fantasy_leagues").delete().eq("id", str(league_id)).execute()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_member(supabase: Client, league_id: str, user_id: str) -> None:
    resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")

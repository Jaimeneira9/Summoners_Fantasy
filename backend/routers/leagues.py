"""
Router: Ligas de fantasy (fantasy_leagues).

Rutas principales:
  GET  /                          — ligas del usuario autenticado
  POST /                          — crear una liga nueva
  POST /join                      — unirse por invite_code sin conocer el league_id
  GET  /{league_id}               — detalle de una liga
  GET  /{league_id}/members       — miembros de una liga
  POST /{league_id}/join          — unirse por invite_code conociendo el league_id
  PATCH/{league_id}/me            — actualizar nick del usuario en la liga
  GET  /{league_id}/members/{id}/roster — roster público de otro manager
  DELETE/{league_id}              — eliminar liga (solo el propietario)

Lógica de negocio central:
  - Dos modos de juego: 'draft_market' (mercado de pujas) y 'budget_pick' (fichajes directos).
  - Las ligas budget_pick no tienen mercado ni máximo de miembros obligatorio.
  - Al crear una liga en modo draft_market se inicializa el mercado de forma síncrona.
  - El roster de otro manager puede servirse desde snapshots históricos por jornada.
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

GameMode = Literal["draft_market", "budget_pick"]

# Sentinel used when budget_pick has no member cap (DB column is NOT NULL)
_NO_LIMIT_SENTINEL = 9999


class LeagueCreate(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    max_members: Optional[int] = None
    game_mode: GameMode = "draft_market"
    competition_id: UUID

    @model_validator(mode="after")
    def validate_max_members(self) -> "LeagueCreate":
        if self.game_mode == "draft_market":
            val = self.max_members if self.max_members is not None else 8
            if not (2 <= val <= 8):
                raise ValueError("draft_market requires max_members between 2 and 8")
            self.max_members = val
        else:  # budget_pick
            if self.max_members is not None and self.max_members < 2:
                raise ValueError("max_members must be >= 2 when provided")
            # None stays as None — will be mapped to sentinel on insert
        return self


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
    competition_id: UUID
    competition_name: str  # derivado del join con competitions
    logo_url: str | None = None
    budget: float
    max_members: int
    is_active: bool
    member: MemberBrief | None = None
    game_mode: str = "draft_market"


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
    """Devuelve todas las ligas en las que el usuario es miembro.

    Hace dos queries: primero obtiene los league_ids del usuario desde
    league_members, luego trae los datos de fantasy_leagues con join a
    competitions para obtener el nombre de la competición.
    """
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
        .select("id, name, invite_code, owner_id, competition_id, budget, max_members, is_active, game_mode, competitions(name, logo_url)")
        .in_("id", league_ids)
        .execute()
    )
    # Fetch real total_points from the view (league_members.total_points is always 0)
    member_ids = [m["id"] for m in memberships.data]
    pts_resp = (
        supabase.table("member_total_points")
        .select("member_id, total_points")
        .in_("member_id", member_ids)
        .execute()
    )
    pts_map = {r["member_id"]: float(r["total_points"] or 0) for r in (pts_resp.data or [])}

    results = []
    for league in response.data:
        competition_row = league.pop("competitions", None) or {}
        league["competition_name"] = competition_row.get("name", "")
        league["logo_url"] = competition_row.get("logo_url")
        m = member_by_league.get(league["id"])
        results.append({
            **league,
            "member": {
                "id": m["id"],
                "remaining_budget": m["remaining_budget"],
                "total_points": pts_map.get(m["id"], 0.0),
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
    """Crea una liga y añade al creador como primer miembro.

    Valida que la competición exista y esté activa antes de insertar.
    En ligas draft_market, inicializa el mercado inmediatamente (8 listings,
    cierre en 24 horas). En budget_pick no hay mercado, se omite ese paso.
    """
    active_comp_resp = (
        supabase.table("competitions")
        .select("id, name, logo_url")
        .eq("id", str(body.competition_id))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not active_comp_resp.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Competition not found or not active",
        )
    active_comp = active_comp_resp.data[0]

    db_max_members = (
        body.max_members if body.max_members is not None else _NO_LIMIT_SENTINEL
    )
    league_resp = (
        supabase.table("fantasy_leagues")
        .insert({
            "name": body.name,
            "owner_id": user["id"],
            "max_members": db_max_members,
            "competition_id": active_comp["id"],
            "game_mode": body.game_mode,
        })
        .execute()
    )
    league = league_resp.data[0]
    league["competition_name"] = active_comp["name"]
    league["logo_url"] = active_comp.get("logo_url")

    supabase.table("league_members").insert({
        "league_id": league["id"],
        "user_id": user["id"],
    }).execute()

    # Inicializar mercado inmediatamente (8 listings, closes_at = now + 24h)
    # En ligas budget_pick no hay mercado
    if body.game_mode != "budget_pick":
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
    """Permite unirse a una liga conociendo solo el invite_code, sin saber el league_id.

    Alternativa al endpoint POST /{league_id}/join, pensada para el flujo de
    compartir link de invitación. Verifica actividad de la liga, duplicados
    y aforo antes de insertar el miembro.
    """
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
    cap = league["max_members"]
    if cap != _NO_LIMIT_SENTINEL and len(count_resp.data) >= cap:
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
    """Devuelve el detalle de una liga.

    Solo accesible si el usuario es miembro de la liga. Incluye datos de la
    competición asociada (nombre, logo) via join a competitions.
    """
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
        .select("id, name, invite_code, owner_id, competition_id, budget, max_members, is_active, game_mode, competitions(name, logo_url)")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")

    data = dict(response.data)
    competition_row = data.pop("competitions", None) or {}
    data["competition_name"] = competition_row.get("name", "")
    data["logo_url"] = competition_row.get("logo_url")

    m = member_resp.data[0]
    # Fetch real total_points from the view (league_members.total_points is always 0)
    pts_resp = (
        supabase.table("member_total_points")
        .select("member_id, total_points")
        .eq("member_id", m["id"])
        .execute()
    )
    pts_map = {r["member_id"]: float(r["total_points"] or 0) for r in (pts_resp.data or [])}
    return {
        **data,
        "member": {
            "id": m["id"],
            "remaining_budget": m["remaining_budget"],
            "total_points": pts_map.get(m["id"], 0.0),
            "display_name": m.get("display_name"),
        },
    }


@router.get("/{league_id}/members", response_model=list[MemberOut])
async def list_members(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[MemberOut]:
    """Lista todos los miembros de una liga con su presupuesto y puntos totales."""
    _assert_member(supabase, str(league_id), user["id"])

    response = (
        supabase.table("league_members")
        .select("id, user_id, display_name, remaining_budget, total_points")
        .eq("league_id", str(league_id))
        .execute()
    )
    members = response.data or []
    if not members:
        return []

    # Overwrite total_points with values from the view (league_members.total_points is always 0)
    member_ids = [m["id"] for m in members]
    pts_resp = (
        supabase.table("member_total_points")
        .select("member_id, total_points")
        .in_("member_id", member_ids)
        .execute()
    )
    pts_map = {r["member_id"]: float(r["total_points"] or 0) for r in (pts_resp.data or [])}
    for m in members:
        m["total_points"] = pts_map.get(m["id"], 0.0)
    return members


@router.post("/{league_id}/join", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def join_league(
    league_id: UUID,
    body: JoinRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> MemberOut:
    """Permite unirse a una liga conociendo tanto el league_id como el invite_code.

    Complementa a POST /join (que no requiere league_id). Este endpoint valida
    que el invite_code coincida con la liga indicada en la ruta.
    """
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
    cap = league["max_members"]
    if cap != _NO_LIMIT_SENTINEL and len(count_resp.data) >= cap:
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
    """Actualiza el display_name del usuario en la liga indicada.

    El display_name es el apodo visible dentro de la liga (distinto del username
    global del perfil). Solo puede cambiarlo el propio miembro.
    """
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
    """Devuelve el roster público de otro manager en la liga.

    Si se pasa ?week=N, sirve el equipo snapshotted de esa jornada desde
    lineup_snapshots. Si no existe snapshot para esa semana, devuelve players=[]
    con snapshot_available=False (sin fallback al roster actual, para que el
    frontend diferencie 'sin datos' de 'equipo vacío').

    Sin week: devuelve el roster actual con split_points y jornada_points del
    último week con series finalizadas. El capitán se resuelve desde
    captain_selections para la semana en curso.
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
    member = dict(member_resp.data[0])
    # Overwrite total_points with the real value from the view
    pts_resp = (
        supabase.table("member_total_points")
        .select("member_id, total_points")
        .eq("member_id", member["id"])
        .execute()
    )
    if pts_resp.data:
        member["total_points"] = float(pts_resp.data[0]["total_points"] or 0)
    else:
        member["total_points"] = 0.0

    # Obtener competition_id desde fantasy_leagues (necesaria para snapshot y split_points)
    fl_resp = (
        supabase.table("fantasy_leagues")
        .select("competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    active_comp_id: str | None = str(fl_resp.data["competition_id"]) if fl_resp.data and fl_resp.data.get("competition_id") else None

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
    """Elimina una liga permanentemente. Solo el propietario puede ejecutar esta acción."""
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
    """Lanza HTTP 403 si el usuario no es miembro de la liga indicada."""
    resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")

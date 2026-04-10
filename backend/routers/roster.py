from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()

Slot = Literal[
    "starter_1", "starter_2", "starter_3", "starter_4", "starter_5",
    "coach", "bench_1", "bench_2",
]

ALL_SLOTS: list[Slot] = [
    "starter_1", "starter_2", "starter_3", "starter_4", "starter_5",
    "coach", "bench_1", "bench_2",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlayerBrief(BaseModel):
    id: UUID
    name: str
    team: str
    role: str
    image_url: str | None
    current_price: float
    last_price_change_pct: float = 0.0


class RosterPlayerOut(BaseModel):
    id: UUID
    slot: Slot
    price_paid: float
    for_sale: bool
    is_protected: bool = False
    split_points: float = 0.0
    clause_amount: float | None = None
    clause_expires_at: str | None = None
    player: PlayerBrief


class RosterOut(BaseModel):
    league_id: UUID
    member_id: str
    remaining_budget: float
    total_points: float
    players: list[RosterPlayerOut]
    captain_player_id: Optional[UUID] = None
    current_week: Optional[int] = None


class CaptainRequest(BaseModel):
    captain_player_id: Optional[UUID] = None  # None = remove captain


class CaptainResponse(BaseModel):
    success: bool
    captain_player_id: Optional[UUID]
    message: str


class MoveRequest(BaseModel):
    roster_player_id: UUID
    new_slot: Slot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member(supabase: Client, league_id: str, user_id: str) -> dict:
    resp = (
        supabase.table("league_members")
        .select("id, remaining_budget, total_points")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")
    return resp.data[0]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{league_id}", response_model=RosterOut)
async def get_roster(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> RosterOut:
    """Devuelve la plantilla del usuario en una liga."""
    member = _get_member(supabase, str(league_id), user["id"])

    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )

    players_out: list[RosterPlayerOut] = []

    if roster_resp.data:
        rp_resp = (
            supabase.table("roster_players")
            .select("id, slot, price_paid, for_sale, is_protected, clause_amount, clause_expires_at, players(id, name, team, role, image_url, current_price, last_price_change_pct)")
            .eq("roster_id", roster_resp.data[0]["id"])
            .execute()
        )
        # Collect player_ids to fetch split_points for the active competition
        player_ids = [row["players"]["id"] for row in (rp_resp.data or []) if row.get("players")]

        split_points_by_player: dict[str, float] = {}
        if player_ids:
            # Fetch series_points for all series in the active competition
            pss_resp = (
                supabase.table("player_series_stats")
                .select("player_id, series_points, series(competition_id, competitions(is_active))")
                .in_("player_id", player_ids)
                .execute()
            )
            for pss_row in (pss_resp.data or []):
                series = pss_row.get("series") or {}
                competition = series.get("competitions") or {}
                if competition.get("is_active"):
                    pid = str(pss_row["player_id"])
                    split_points_by_player[pid] = split_points_by_player.get(pid, 0.0) + float(pss_row.get("series_points") or 0.0)

        for row in (rp_resp.data or []):
            player_id = str(row["players"]["id"])
            players_out.append(RosterPlayerOut(
                id=row["id"],
                slot=row["slot"],
                price_paid=float(row["price_paid"]),
                for_sale=row["for_sale"],
                is_protected=bool(row.get("is_protected", False)),
                split_points=split_points_by_player.get(player_id, 0.0),
                clause_amount=float(row["clause_amount"]) if row.get("clause_amount") is not None else None,
                clause_expires_at=row.get("clause_expires_at"),
                player=PlayerBrief(**row["players"]),
            ))

    # Fetch active competition + current week to look up captain
    captain_player_id: Optional[UUID] = None
    current_week: Optional[int] = None
    try:
        comp_resp = (
            supabase.table("competitions")
            .select("id")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if comp_resp.data:
            competition_id = comp_resp.data[0]["id"]
            # Determine current week: max week from series
            week_resp = (
                supabase.table("series")
                .select("week")
                .eq("competition_id", competition_id)
                .order("week", desc=True)
                .limit(1)
                .execute()
            )
            if week_resp.data:
                current_week = week_resp.data[0]["week"]
                cap_resp = (
                    supabase.table("captain_selections")
                    .select("captain_player_id")
                    .eq("member_id", member["id"])
                    .eq("week", current_week)
                    .limit(1)
                    .execute()
                )
                if cap_resp.data and cap_resp.data[0]["captain_player_id"]:
                    captain_player_id = cap_resp.data[0]["captain_player_id"]
    except Exception:
        pass  # captain is non-critical — don't fail roster load

    return RosterOut(
        league_id=league_id,
        member_id=member["id"],
        remaining_budget=float(member["remaining_budget"]),
        total_points=float(member["total_points"]),
        players=players_out,
        captain_player_id=captain_player_id,
        current_week=current_week,
    )


@router.patch("/{league_id}/move", status_code=status.HTTP_200_OK)
async def move_player(
    league_id: UUID,
    body: MoveRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Mueve un jugador a otro slot. Si el destino está ocupado, intercambia ambos."""
    member = _get_member(supabase, str(league_id), user["id"])

    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )
    if not roster_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes equipo en esta liga")
    roster_id = roster_resp.data[0]["id"]

    # Jugador a mover
    rp_resp = (
        supabase.table("roster_players")
        .select("id, slot")
        .eq("id", str(body.roster_player_id))
        .eq("roster_id", roster_id)
        .execute()
    )
    if not rp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en tu equipo")

    current_slot: str = rp_resp.data[0]["slot"]
    if current_slot == body.new_slot:
        return {"message": "El jugador ya está en ese slot"}

    # Comprobar si el slot destino está ocupado
    occupant_resp = (
        supabase.table("roster_players")
        .select("id")
        .eq("roster_id", roster_id)
        .eq("slot", body.new_slot)
        .execute()
    )

    if occupant_resp.data:
        # Swap: el ocupante toma el slot actual del jugador que se mueve.
        # Usamos SQL directo para evitar conflicto de unique constraint.
        occupant_id = occupant_resp.data[0]["id"]
        supabase.rpc("swap_roster_slots", {
            "p_roster_id": roster_id,
            "p_id_a": str(body.roster_player_id),
            "p_slot_a": body.new_slot,
            "p_id_b": occupant_id,
            "p_slot_b": current_slot,
        }).execute()
    else:
        supabase.table("roster_players").update({"slot": body.new_slot}).eq(
            "id", str(body.roster_player_id)
        ).execute()

    return {"message": "Posición actualizada"}


class ProtectRequest(BaseModel):
    roster_player_id: UUID


@router.patch("/{league_id}/protect", status_code=status.HTTP_200_OK)
async def toggle_protect(
    league_id: UUID,
    body: ProtectRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Marca/desmarca un jugador como protegido para el reset de split.
    Solo puede haber 1 jugador protegido por equipo.
    No se puede proteger al mismo jugador que se protegió en el split anterior."""
    member = _get_member(supabase, str(league_id), user["id"])

    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )
    if not roster_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes equipo en esta liga")
    roster_id = roster_resp.data[0]["id"]

    # Verificar que el jugador pertenece al roster
    rp_resp = (
        supabase.table("roster_players")
        .select("id, is_protected, player_id")
        .eq("id", str(body.roster_player_id))
        .eq("roster_id", roster_id)
        .execute()
    )
    if not rp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en tu equipo")

    currently_protected = bool(rp_resp.data[0].get("is_protected", False))
    player_id = rp_resp.data[0]["player_id"]

    if currently_protected:
        # Desproteger
        supabase.table("roster_players").update({"is_protected": False}).eq(
            "id", str(body.roster_player_id)
        ).execute()
        return {"message": "Protección eliminada", "is_protected": False}

    # Comprobar restricción: ¿protegió este jugador en el split anterior?
    prev_split_resp = (
        supabase.table("splits")
        .select("id")
        .eq("is_active", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if prev_split_resp.data:
        prev_split_id = prev_split_resp.data[0]["id"]
        history_resp = (
            supabase.table("split_protect_history")
            .select("id")
            .eq("member_id", member["id"])
            .eq("player_id", str(player_id))
            .eq("split_id", prev_split_id)
            .execute()
        )
        if history_resp.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya protegiste a este jugador en el split anterior. Elige otro.",
            )

    # Proteger este, desproteger todos los demás
    supabase.table("roster_players").update({"is_protected": False}).eq(
        "roster_id", roster_id
    ).execute()
    supabase.table("roster_players").update({"is_protected": True}).eq(
        "id", str(body.roster_player_id)
    ).execute()
    return {"message": "Jugador protegido para el reset", "is_protected": True}


# ---------------------------------------------------------------------------
# Captain
# ---------------------------------------------------------------------------

@router.put("/{league_id}/lineups/{week}/captain", response_model=CaptainResponse)
async def set_captain(
    league_id: UUID,
    week: int,
    body: CaptainRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> CaptainResponse:
    """Asigna o remueve el capitán para la jornada indicada.

    Validaciones:
    - El manager debe ser miembro de la liga
    - La jornada no debe haber comenzado (series.start_time > now)
    - Si captain_player_id no es null: debe ser un starter en el roster actual
    """
    member = _get_member(supabase, str(league_id), user["id"])
    member_id = member["id"]

    # 1. Obtener competition_id activo
    comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not comp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay competición activa")
    competition_id = comp_resp.data[0]["id"]

    # 2. Verificar que la jornada no haya iniciado
    series_resp = (
        supabase.table("series")
        .select("date")
        .eq("competition_id", competition_id)
        .eq("week", week)
        .order("date", desc=False)
        .limit(1)
        .execute()
    )
    if series_resp.data:
        series_date = date.fromisoformat(series_resp.data[0]["date"])
        if series_date <= datetime.now(timezone.utc).date():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La jornada ya comenzó, no podés cambiar el capitán",
            )

    # 3. Si se asigna capitán (no null): validar que es starter
    if body.captain_player_id is not None:
        starter_slots = {"starter_1", "starter_2", "starter_3", "starter_4", "starter_5"}

        # Try snapshot first (if jornada already snapshotted)
        snap_resp = (
            supabase.table("lineup_snapshots")
            .select("slot, player_id")
            .eq("member_id", member_id)
            .eq("competition_id", competition_id)
            .eq("week", week)
            .in_("slot", list(starter_slots))
            .execute()
        )
        snapshot_player_ids = {
            str(row["player_id"])
            for row in (snap_resp.data or [])
            if row["slot"] in starter_slots
        }

        is_valid_starter = str(body.captain_player_id) in snapshot_player_ids

        if not is_valid_starter:
            # Fallback: check current roster_players if no snapshot yet
            roster_resp = (
                supabase.table("rosters")
                .select("id")
                .eq("member_id", member_id)
                .execute()
            )
            if roster_resp.data:
                rp_resp = (
                    supabase.table("roster_players")
                    .select("player_id, slot")
                    .eq("roster_id", roster_resp.data[0]["id"])
                    .eq("player_id", str(body.captain_player_id))
                    .execute()
                )
                if rp_resp.data and rp_resp.data[0]["slot"] in starter_slots:
                    is_valid_starter = True

        if not is_valid_starter:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El capitán debe ser un titular (starter_1 a starter_5)",
            )

    # 4. Upsert captain_selection
    upsert_data = {
        "member_id": str(member_id),
        "competition_id": str(competition_id),
        "week": week,
        "captain_player_id": str(body.captain_player_id) if body.captain_player_id else None,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    supabase.table("captain_selections").upsert(
        upsert_data,
        on_conflict="member_id,week",
    ).execute()

    # 5. Also update lineup_snapshots if they already exist for this week
    supabase.table("lineup_snapshots").update(
        {"captain_player_id": str(body.captain_player_id) if body.captain_player_id else None}
    ).eq("member_id", member_id).eq("competition_id", competition_id).eq("week", week).execute()

    return CaptainResponse(
        success=True,
        captain_player_id=body.captain_player_id,
        message="Capitán asignado" if body.captain_player_id else "Capitán removido",
    )

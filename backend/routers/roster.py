from typing import Literal
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

    return RosterOut(
        league_id=league_id,
        member_id=member["id"],
        remaining_budget=float(member["remaining_budget"]),
        total_points=float(member["total_points"]),
        players=players_out,
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

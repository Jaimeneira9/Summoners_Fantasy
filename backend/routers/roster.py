"""
Router: Plantilla del manager (roster).

Rutas principales:
  GET  /{league_id}                       — plantilla actual del usuario (o histórica por ?week)
  PATCH/{league_id}/move                  — mover/intercambiar jugadores de slot
  PATCH/{league_id}/protect               — marcar/desmarcar jugador como protegido para reset
  PUT  /{league_id}/lineups/{week}/captain — asignar o remover capitán de una jornada
  POST /{league_id}/pick                  — fichar jugador en ligas budget_pick
  GET  /{league_id}/available-players     — jugadores fichables en ligas budget_pick

Lógica de negocio central:
  - El roster actual enriquece cada jugador con split_points (puntos totales del split)
    y jornada_points (puntos de la jornada más reciente con series finalizadas).
  - ?week=N sirve desde lineup_snapshots; si no hay snapshot, devuelve players=[]
    con snapshot_missing=True (no fallback al roster actual).
  - La protección (is_protected) limita a 1 jugador por equipo y no puede repetirse
    el mismo jugador que se protegió en el split anterior.
  - El capitán dobla los puntos del jugador esa jornada. Solo puede ser un starter
    (starter_1 a starter_5). Se guarda en captain_selections y se propaga a
    lineup_snapshots si ya existen para esa semana.
  - En budget_pick, el pick hace un swap atómico (RPC swap_budget): descuenta el
    nuevo precio y devuelve el precio pagado por el jugador saliente.
"""

import asyncio
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    jornada_points: float = 0.0
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
    captain_week: Optional[int] = None
    snapshot_missing: bool = False
    week: Optional[int] = None


class CaptainRequest(BaseModel):
    captain_player_id: Optional[UUID] = None  # None = remove captain


class CaptainResponse(BaseModel):
    success: bool
    captain_player_id: Optional[UUID]
    message: str


class MoveRequest(BaseModel):
    roster_player_id: UUID
    new_slot: Slot


class PickRequest(BaseModel):
    player_id: UUID
    slot: Slot


class AvailablePlayerOut(BaseModel):
    id: UUID
    name: str
    team: str
    role: str
    image_url: str | None
    current_price: float
    last_price_change_pct: float = 0.0
    split_points: float = 0.0
    in_my_roster: bool = False


class PickResponse(BaseModel):
    ok: bool
    slot: Slot
    player_id: UUID
    price_paid: float
    remaining_budget: float
    released_player_id: UUID | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member(supabase: Client, league_id: str, user_id: str) -> dict:
    """Devuelve el registro de league_members del usuario incluyendo presupuesto y puntos, o lanza HTTP 403."""
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
    week: Optional[int] = Query(default=None, ge=1),
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> RosterOut:
    """Devuelve la plantilla del usuario en la liga, con puntos y capitán.

    Sin ?week: devuelve el roster actual con split_points (acumulados del split)
    y jornada_points (solo la jornada más reciente con series finalizadas).
    Con ?week=N: sirve desde lineup_snapshots. Si no hay snapshot retorna
    snapshot_missing=True con players=[].
    El capitán se resuelve desde captain_selections para la semana en curso.
    """
    # ── Group A: member + league queries in parallel (both only need league_id) ──
    loop = asyncio.get_event_loop()

    def _fetch_member():
        resp = (
            supabase.table("league_members")
            .select("id, remaining_budget, total_points")
            .eq("league_id", str(league_id))
            .eq("user_id", user["id"])
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")
        return resp.data[0]

    def _fetch_league():
        return (
            supabase.table("fantasy_leagues")
            .select("competition_id")
            .eq("id", str(league_id))
            .single()
            .execute()
        )

    member, fl_resp = await asyncio.gather(
        loop.run_in_executor(None, _fetch_member),
        loop.run_in_executor(None, _fetch_league),
    )

    # ── Step 2: Resolve competition_id from parallel result ──
    competition_id: Optional[str] = None
    current_week: Optional[int] = None

    if not fl_resp.data or not fl_resp.data.get("competition_id"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Liga sin competición asignada",
        )
    competition_id = str(fl_resp.data["competition_id"])

    try:
        week_resp = (
            supabase.table("series")
            .select("week")
            .eq("competition_id", competition_id)
            .eq("status", "finished")
            .order("week", desc=True)
            .limit(1)
            .execute()
        )
        if week_resp.data:
            current_week = week_resp.data[0]["week"]
    except Exception:
        pass  # non-critical — roster still loads without week

    # ── Historical snapshot branch (when week is provided) ──
    if week is not None:
        if competition_id is None:
            return RosterOut(
                league_id=league_id,
                member_id=member["id"],
                remaining_budget=float(member["remaining_budget"]),
                total_points=float(member["total_points"]),
                players=[],
                snapshot_missing=True,
                week=week,
            )

        snap_resp = (
            supabase.table("lineup_snapshots")
            .select("slot, player_id, captain_player_id")
            .eq("member_id", member["id"])
            .eq("competition_id", competition_id)
            .eq("week", week)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )

        if not snap_resp.data:
            return RosterOut(
                league_id=league_id,
                member_id=member["id"],
                remaining_budget=float(member["remaining_budget"]),
                total_points=float(member["total_points"]),
                players=[],
                snapshot_missing=True,
                week=week,
            )

        snap_captain_player_id: Optional[str] = snap_resp.data[0].get("captain_player_id")
        snap_player_ids = [r["player_id"] for r in snap_resp.data if r.get("player_id")]
        snap_slot_map = {r["slot"]: r["player_id"] for r in snap_resp.data}

        # ── Historical Group B: players + series for snap_series_ids in parallel ──
        snap_players_map: dict[str, dict] = {}
        snap_jornada_points: dict[str, float] = {}

        if snap_player_ids:
            def _fetch_snap_players():
                return (
                    supabase.table("players")
                    .select("id, name, team, role, image_url, current_price, last_price_change_pct")
                    .in_("id", snap_player_ids)
                    .execute()
                )

            def _fetch_snap_series():
                return (
                    supabase.table("series")
                    .select("id")
                    .eq("competition_id", competition_id)
                    .eq("week", week)
                    .eq("status", "finished")
                    .execute()
                )

            p_resp, week_series_resp = await asyncio.gather(
                loop.run_in_executor(None, _fetch_snap_players),
                loop.run_in_executor(None, _fetch_snap_series),
            )
            snap_players_map = {p["id"]: p for p in (p_resp.data or [])}

            snap_series_ids = [s["id"] for s in (week_series_resp.data or [])]
            if snap_series_ids:
                jp_resp = (
                    supabase.table("player_series_stats")
                    .select("player_id, series_points")
                    .in_("series_id", snap_series_ids)
                    .in_("player_id", snap_player_ids)
                    .execute()
                )
                for jp_row in (jp_resp.data or []):
                    pid = str(jp_row["player_id"])
                    snap_jornada_points[pid] = snap_jornada_points.get(pid, 0.0) + float(jp_row.get("series_points") or 0.0)

        snap_players_out: list[RosterPlayerOut] = []
        for slot, player_id in snap_slot_map.items():
            if player_id and player_id in snap_players_map:
                p_data = snap_players_map[player_id]
                pid = str(player_id)
                snap_players_out.append(RosterPlayerOut(
                    id=player_id,
                    slot=slot,
                    price_paid=0.0,
                    for_sale=False,
                    is_protected=False,
                    split_points=0.0,
                    jornada_points=snap_jornada_points.get(pid, 0.0),
                    player=PlayerBrief(**p_data),
                ))

        return RosterOut(
            league_id=league_id,
            member_id=member["id"],
            remaining_budget=float(member["remaining_budget"]),
            total_points=float(member["total_points"]),
            players=snap_players_out,
            captain_player_id=snap_captain_player_id,
            current_week=current_week,
            week=week,
        )

    # ── Step 4: Roster + players ──
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
        # Collect player_ids to fetch points
        player_ids = [row["players"]["id"] for row in (rp_resp.data or []) if row.get("players")]

        # ── Live Group B: split_points + jornada series query in parallel ──
        split_points_by_player: dict[str, float] = {}
        jornada_points_by_player: dict[str, float] = {}

        if player_ids:
            def _fetch_split_points():
                return (
                    supabase.table("player_series_stats")
                    .select("player_id, series_points, series(competition_id, competitions(is_active))")
                    .in_("player_id", player_ids)
                    .execute()
                )

            def _fetch_jornada_series():
                if current_week is not None and competition_id is not None:
                    return (
                        supabase.table("series")
                        .select("id")
                        .eq("competition_id", competition_id)
                        .eq("week", current_week)
                        .eq("status", "finished")
                        .execute()
                    )
                return None

            pss_resp, week_series_resp = await asyncio.gather(
                loop.run_in_executor(None, _fetch_split_points),
                loop.run_in_executor(None, _fetch_jornada_series),
            )

            for pss_row in (pss_resp.data or []):
                series = pss_row.get("series") or {}
                competition = series.get("competitions") or {}
                if competition.get("is_active"):
                    pid = str(pss_row["player_id"])
                    split_points_by_player[pid] = split_points_by_player.get(pid, 0.0) + float(pss_row.get("series_points") or 0.0)

            # ── Step 6b: jornada_points — sum series_points for finished series in current_week ──
            if week_series_resp is not None:
                series_ids = [row["id"] for row in (week_series_resp.data or [])]
                if series_ids:
                    jp_resp = (
                        supabase.table("player_series_stats")
                        .select("player_id, series_points")
                        .in_("series_id", series_ids)
                        .in_("player_id", player_ids)
                        .execute()
                    )
                    for jp_row in (jp_resp.data or []):
                        pid = str(jp_row["player_id"])
                        jornada_points_by_player[pid] = (
                            jornada_points_by_player.get(pid, 0.0)
                            + float(jp_row.get("series_points") or 0.0)
                        )

        # ── Step 7: Build players_out ──
        for row in (rp_resp.data or []):
            player_id = str(row["players"]["id"])
            players_out.append(RosterPlayerOut(
                id=row["id"],
                slot=row["slot"],
                price_paid=float(row["price_paid"]),
                for_sale=row["for_sale"],
                is_protected=bool(row.get("is_protected", False)),
                split_points=split_points_by_player.get(player_id, 0.0),
                jornada_points=jornada_points_by_player.get(player_id, 0.0),
                clause_amount=float(row["clause_amount"]) if row.get("clause_amount") is not None else None,
                clause_expires_at=row.get("clause_expires_at"),
                player=PlayerBrief(**row["players"]),
            ))

    # ── Step 8: Captain selection ──
    captain_player_id: Optional[UUID] = None
    try:
        if current_week is not None:
            cap_resp = (
                supabase.table("captain_selections")
                .select("captain_player_id")
                .eq("member_id", member["id"])
                .eq("week", current_week + 1)
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
        captain_week=(current_week or 0) + 1 if current_week is not None else None,
    )


@router.patch("/{league_id}/move", status_code=status.HTTP_200_OK)
async def move_player(
    league_id: UUID,
    body: MoveRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Mueve un jugador a un slot distinto. Si el destino está ocupado, intercambia ambos.

    El swap usa la RPC swap_roster_slots para evitar violación del unique constraint
    en (roster_id, slot) al cambiar los dos slots en una sola transacción SQL.
    """
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
    """Marca o desmarca un jugador como protegido para el reset de split.

    Reglas de negocio:
    - Solo puede haber 1 jugador protegido por equipo (al proteger uno, se desprotegen todos).
    - No se puede proteger el mismo jugador que fue protegido en el split anterior
      (verificado contra split_protect_history del último split inactivo).
    """
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

    # Comprobar restricción: ¿protegió este jugador en la competition anterior?
    prev_comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if prev_comp_resp.data:
        prev_competition_id = prev_comp_resp.data[0]["id"]
        history_resp = (
            supabase.table("split_protect_history")
            .select("id")
            .eq("member_id", member["id"])
            .eq("player_id", str(player_id))
            .eq("competition_id", prev_competition_id)
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
    """Asigna o remueve el capitán para una jornada específica.

    Restricciones:
    - No se puede cambiar si hay series en_progreso para esa semana.
    - El capitán debe ser un starter (starter_1 a starter_5), verificado primero
      en lineup_snapshots (si existe) y luego en el roster actual como fallback.
    - Se hace upsert en captain_selections y se propaga a lineup_snapshots si ya
      existen para esa semana (para mantener consistencia en los cálculos de leaderboard).
    """
    member = _get_member(supabase, str(league_id), user["id"])
    member_id = member["id"]

    # 1. Obtener competition_id desde la fantasy_league específica
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data or not league_resp.data.get("competition_id"):
        raise HTTPException(status_code=503, detail="Liga sin competición asignada")
    competition_id = str(league_resp.data["competition_id"])

    # 2. Bloquear solo si hay series en progreso (no si ya terminaron)
    series_resp = (
        supabase.table("series")
        .select("id")
        .eq("competition_id", competition_id)
        .eq("week", week)
        .eq("status", "in_progress")
        .limit(1)
        .execute()
    )
    if series_resp.data:
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
        on_conflict="member_id,competition_id,week",
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


# ---------------------------------------------------------------------------
# Budget Pick
# ---------------------------------------------------------------------------

SLOT_ROLES: dict[str, str] = {
    "starter_1": "top",
    "starter_2": "jungle",
    "starter_3": "mid",
    "starter_4": "adc",
    "starter_5": "support",
    "coach": "coach",
}


@router.post("/{league_id}/pick", response_model=PickResponse)
async def pick_player(
    league_id: UUID,
    body: PickRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> PickResponse:
    """Ficha un jugador (o reemplaza al actual del slot) en una liga budget_pick.

    Solo disponible en ligas de modo budget_pick. No se puede cambiar durante una
    jornada en curso. El slot debe corresponder al rol del jugador (SLOT_ROLES).
    Si el slot tiene ocupante, se libera el jugador saliente y se devuelve su precio
    al presupuesto. El swap de presupuesto se hace con la RPC atómica swap_budget.
    Si el jugador saliente era capitán de la próxima jornada, se limpia el capitán.
    """

    # 1. Verificar game_mode
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("id, game_mode, competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data or league_resp.data["game_mode"] != "budget_pick":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este endpoint solo aplica en ligas budget_pick",
        )
    competition_id = league_resp.data["competition_id"]

    # 2. Verificar membresía
    member = _get_member(supabase, str(league_id), user["id"])

    # 3. Bloqueo de jornada
    series_resp = (
        supabase.table("series")
        .select("id")
        .eq("competition_id", competition_id)
        .eq("status", "in_progress")
        .limit(1)
        .execute()
    )
    if series_resp.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No podés cambiar jugadores mientras hay una jornada en curso",
        )

    # 4. Validar jugador destino
    player_resp = (
        supabase.table("players")
        .select("id, role, current_price, name, team")
        .eq("id", str(body.player_id))
        .eq("is_active", True)
        .execute()
    )
    if not player_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado o inactivo")
    player = player_resp.data[0]
    new_price = float(player["current_price"])

    # 5. Validar coherencia slot ↔ rol
    expected_role = SLOT_ROLES.get(str(body.slot))
    if expected_role and player["role"] != expected_role:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El slot {body.slot} es para rol '{expected_role}', no '{player['role']}'",
        )

    # 6. Obtener/crear roster
    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )
    if roster_resp.data:
        roster_id = roster_resp.data[0]["id"]
    else:
        new_roster = supabase.table("rosters").insert({"member_id": member["id"]}).execute()
        roster_id = new_roster.data[0]["id"]

    # 7. Verificar que el jugador no esté ya en otro slot del mismo roster
    dup_resp = (
        supabase.table("roster_players")
        .select("id")
        .eq("roster_id", roster_id)
        .eq("player_id", str(body.player_id))
        .execute()
    )
    if dup_resp.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya tenés este jugador en tu equipo")

    # 8. Leer ocupante actual del slot
    occupant_resp = (
        supabase.table("roster_players")
        .select("id, player_id, price_paid")
        .eq("roster_id", roster_id)
        .eq("slot", str(body.slot))
        .execute()
    )
    occupant = occupant_resp.data[0] if occupant_resp.data else None
    release_amount = float(occupant["price_paid"]) if occupant else 0.0
    released_player_id = occupant["player_id"] if occupant else None

    # 9. Swap atómico de presupuesto via RPC
    rpc_result = supabase.rpc("swap_budget", {
        "p_member_id": member["id"],
        "p_release": release_amount,
        "p_cost": new_price,
    }).execute()
    if not rpc_result.data:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Presupuesto insuficiente")

    # 10. Limpiar capitán si el jugador saliente era capitán de captain_week
    if released_player_id:
        week_resp = (
            supabase.table("series")
            .select("week")
            .eq("competition_id", competition_id)
            .eq("status", "finished")
            .order("week", desc=True)
            .limit(1)
            .execute()
        )
        current_week = week_resp.data[0]["week"] if week_resp.data else None
        captain_week = current_week + 1 if current_week is not None else None
        if captain_week is not None:
            cap_resp = (
                supabase.table("captain_selections")
                .select("captain_player_id")
                .eq("member_id", member["id"])
                .eq("week", captain_week)
                .limit(1)
                .execute()
            )
            if cap_resp.data and str(cap_resp.data[0]["captain_player_id"]) == str(released_player_id):
                supabase.table("captain_selections").update(
                    {"captain_player_id": None}
                ).eq("member_id", member["id"]).eq("week", captain_week).execute()

    # 11. Eliminar ocupante del slot (si existía)
    if occupant:
        supabase.table("roster_players").delete().eq("id", occupant["id"]).execute()

    # 12. Insertar nuevo roster_player
    supabase.table("roster_players").insert({
        "roster_id": roster_id,
        "player_id": str(body.player_id),
        "slot": str(body.slot),
        "price_paid": new_price,
    }).execute()

    # 13. Retornar respuesta
    new_budget = float(member["remaining_budget"]) + release_amount - new_price
    return PickResponse(
        ok=True,
        slot=body.slot,
        player_id=body.player_id,
        price_paid=new_price,
        remaining_budget=new_budget,
        released_player_id=released_player_id,
    )


@router.get("/{league_id}/available-players", response_model=list[AvailablePlayerOut])
async def get_available_players(
    league_id: UUID,
    role: Optional[str] = Query(default=None),
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[AvailablePlayerOut]:
    """Lista todos los jugadores activos fichables en una liga budget_pick.

    Filtra por la league abbr de la competición (players.league = primer token del nombre).
    Añade split_points de la competición activa e in_my_roster para que el frontend
    pueda resaltar los jugadores ya fichados. Ordenados por split_points DESC.
    """

    # 1. Verificar game_mode y obtener competition_id
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("game_mode, competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data or league_resp.data["game_mode"] != "budget_pick":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este endpoint solo aplica en ligas budget_pick")
    competition_id = league_resp.data["competition_id"]

    # 2. Verificar membresía
    member = _get_member(supabase, str(league_id), user["id"])

    # 3. Obtener el nombre de la competición para filtrar jugadores por league
    # players.league es un campo de texto (ej: "LEC") que corresponde al prefijo del nombre de la competición
    comp_resp = (
        supabase.table("competitions")
        .select("name")
        .eq("id", str(competition_id))
        .single()
        .execute()
    )
    league_abbr = comp_resp.data["name"].split()[0] if comp_resp.data else None

    # 4. Query de jugadores activos filtrados por league
    players_query = (
        supabase.table("players")
        .select("id, name, team, role, image_url, current_price, last_price_change_pct")
        .eq("is_active", True)
    )
    if league_abbr:
        players_query = players_query.eq("league", league_abbr)
    if role:
        players_query = players_query.eq("role", role)
    players_resp = players_query.execute()
    players = players_resp.data or []

    # 4b. Calcular split_points por jugador (misma lógica que get_roster)
    player_ids = [str(p["id"]) for p in players]
    split_points_by_player: dict[str, float] = {}
    if player_ids:
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

    # 5. Obtener player_ids del roster del usuario
    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )
    my_player_ids: set[str] = set()
    if roster_resp.data:
        rp_resp = (
            supabase.table("roster_players")
            .select("player_id")
            .eq("roster_id", roster_resp.data[0]["id"])
            .execute()
        )
        my_player_ids = {str(r["player_id"]) for r in (rp_resp.data or [])}

    # 6. Construir resultado y ordenar por split_points desc
    result = [
        AvailablePlayerOut(
            id=p["id"],
            name=p["name"],
            team=p["team"],
            role=p["role"],
            image_url=p.get("image_url"),
            current_price=float(p["current_price"]),
            last_price_change_pct=float(p.get("last_price_change_pct") or 0.0),
            split_points=split_points_by_player.get(str(p["id"]), 0.0),
            in_my_roster=str(p["id"]) in my_player_ids,
        )
        for p in players
    ]
    result.sort(key=lambda x: x.split_points, reverse=True)
    return result

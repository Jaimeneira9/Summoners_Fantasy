"""
Router: Intercambios entre managers (trades).

Rutas principales:
  GET  /{league_id}                  — listar trades pendientes del/para el usuario
  POST /{league_id}                  — crear una oferta de trade
  POST /{league_id}/{offer_id}/accept — aceptar un trade (transfiere jugadores y presupuesto)
  POST /{league_id}/{offer_id}/reject — rechazar un trade
  DELETE /{league_id}/{offer_id}     — cancelar un trade (solo el creador)

Lógica de negocio central:
  - Un trade puede incluir: jugador ofrecido, jugador solicitado, dinero ofrecido,
    dinero solicitado. Debe haber al menos un jugador o dinero ofrecido.
  - Al aceptar: los jugadores cambian de roster (sin borrar el row, solo se actualiza
    roster_id), y los presupuestos se ajustan según el diferencial de dinero.
  - Supabase REST no soporta OR nativo en filtros eq, por lo que la lista de trades
    se obtiene con dos queries separadas (from_member + to_member) unidas en Python.
  - _get_or_create_roster garantiza que un manager sin roster lo tenga al recibir
    un jugador en un trade.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TradeOfferCreate(BaseModel):
    to_member_id: UUID
    offered_player_id: UUID | None = None
    requested_player_id: UUID | None = None
    offered_money: float = Field(default=0.0, ge=0)
    requested_money: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def at_least_something_offered(self) -> "TradeOfferCreate":
        if self.offered_player_id is None and self.offered_money == 0:
            raise ValueError("Debes ofrecer al menos un jugador o dinero")
        return self


class TradeOfferOut(BaseModel):
    id: UUID
    league_id: UUID
    from_member_id: UUID
    to_member_id: UUID
    offered_player_id: UUID | None
    requested_player_id: UUID | None
    offered_money: float
    requested_money: float
    status: str
    created_at: str
    expires_at: str | None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_member(supabase: Client, league_id: str, user_id: str) -> dict:
    """Devuelve el registro de league_members del usuario, o lanza HTTP 403."""
    resp = (
        supabase.table("league_members")
        .select("id, remaining_budget")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")
    return resp.data


def _get_member_by_id(supabase: Client, member_id: str) -> dict:
    """Devuelve el registro de league_members por su ID de miembro, o lanza HTTP 404."""
    resp = (
        supabase.table("league_members")
        .select("id, remaining_budget")
        .eq("id", member_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miembro no encontrado")
    return resp.data


def _get_roster_player_for_member(
    supabase: Client, member_id: str, player_id: str
) -> dict:
    """Devuelve el roster_player de un miembro para un jugador concreto."""
    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member_id)
        .single()
        .execute()
    )
    if not roster_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El miembro no tiene equipo")
    roster_id = roster_resp.data["id"]

    rp_resp = (
        supabase.table("roster_players")
        .select("id")
        .eq("roster_id", roster_id)
        .eq("player_id", player_id)
        .single()
        .execute()
    )
    if not rp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en el equipo")
    return rp_resp.data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{league_id}", response_model=list[TradeOfferOut])
async def list_trades(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[TradeOfferOut]:
    """Devuelve las ofertas de trade pendientes relacionadas con el usuario.

    Incluye trades que el usuario creó (from_member_id) y que recibió (to_member_id).
    Usa dos queries separadas y deduplicación en Python porque Supabase REST no soporta
    OR en filtros eq nativamente.
    """
    member = _get_member(supabase, str(league_id), user["id"])

    # Hacemos dos queries y unimos (Supabase REST no soporta OR nativo en eq)
    from_resp = (
        supabase.table("trade_offers")
        .select("*")
        .eq("league_id", str(league_id))
        .eq("status", "pending")
        .eq("from_member_id", member["id"])
        .execute()
    )
    to_resp = (
        supabase.table("trade_offers")
        .select("*")
        .eq("league_id", str(league_id))
        .eq("status", "pending")
        .eq("to_member_id", member["id"])
        .execute()
    )
    seen: set[str] = set()
    results = []
    for row in (from_resp.data or []) + (to_resp.data or []):
        if row["id"] not in seen:
            seen.add(row["id"])
            results.append(row)
    return results


@router.post("/{league_id}", response_model=TradeOfferOut, status_code=status.HTTP_201_CREATED)
async def create_trade(
    league_id: UUID,
    body: TradeOfferCreate,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> TradeOfferOut:
    """Crea una oferta de trade hacia otro manager de la liga.

    Valida que el jugador ofrecido pertenezca al creador y que el jugador solicitado
    pertenezca al destinatario. No se puede hacer trade con uno mismo.
    """
    from_member = _get_member(supabase, str(league_id), user["id"])

    if str(body.to_member_id) == from_member["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes hacer un trade contigo mismo")

    # Validar que to_member es miembro de la liga
    to_resp = (
        supabase.table("league_members")
        .select("id")
        .eq("id", str(body.to_member_id))
        .eq("league_id", str(league_id))
        .single()
        .execute()
    )
    if not to_resp.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El destinatario no es miembro de esta liga")

    # Validar que el jugador ofrecido pertenece al from_member
    if body.offered_player_id:
        _get_roster_player_for_member(supabase, from_member["id"], str(body.offered_player_id))

    # Validar que el jugador solicitado pertenece al to_member
    if body.requested_player_id:
        _get_roster_player_for_member(supabase, str(body.to_member_id), str(body.requested_player_id))

    offer_resp = (
        supabase.table("trade_offers")
        .insert({
            "league_id": str(league_id),
            "from_member_id": from_member["id"],
            "to_member_id": str(body.to_member_id),
            "offered_player_id": str(body.offered_player_id) if body.offered_player_id else None,
            "requested_player_id": str(body.requested_player_id) if body.requested_player_id else None,
            "offered_money": body.offered_money,
            "requested_money": body.requested_money,
        })
        .execute()
    )
    return offer_resp.data[0]


@router.post("/{league_id}/{offer_id}/accept", status_code=status.HTTP_200_OK)
async def accept_trade(
    league_id: UUID,
    offer_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Acepta una oferta de trade: transfiere jugadores y ajusta presupuestos.

    La transferencia de jugadores se hace actualizando roster_id del roster_player,
    no moviendo el row completo. El ajuste de presupuesto se calcula como diferencial
    neto (requested_money - offered_money) para cada parte.
    """
    to_member = _get_member(supabase, str(league_id), user["id"])

    offer_resp = (
        supabase.table("trade_offers")
        .select("*")
        .eq("id", str(offer_id))
        .eq("league_id", str(league_id))
        .eq("to_member_id", to_member["id"])
        .single()
        .execute()
    )
    offer = offer_resp.data
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta no encontrada")
    if offer["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La oferta ya no está pendiente")

    from_member = _get_member_by_id(supabase, offer["from_member_id"])

    # Validar presupuestos para el intercambio de dinero
    if offer["offered_money"] > 0 and float(from_member["remaining_budget"]) < float(offer["offered_money"]):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="El proponente no tiene presupuesto suficiente")
    if offer["requested_money"] > 0 and float(to_member["remaining_budget"]) < float(offer["requested_money"]):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="No tienes presupuesto suficiente")

    # Transferir jugador ofrecido: from → to
    if offer["offered_player_id"]:
        rp = _get_roster_player_for_member(supabase, from_member["id"], offer["offered_player_id"])
        supabase.table("roster_players").update({"roster_id": _get_or_create_roster(supabase, to_member["id"])}).eq("id", rp["id"]).execute()

    # Transferir jugador solicitado: to → from
    if offer["requested_player_id"]:
        rp2 = _get_roster_player_for_member(supabase, to_member["id"], offer["requested_player_id"])
        supabase.table("roster_players").update({"roster_id": _get_or_create_roster(supabase, from_member["id"])}).eq("id", rp2["id"]).execute()

    # Ajustar presupuestos
    net_from = float(offer["requested_money"]) - float(offer["offered_money"])
    net_to = float(offer["offered_money"]) - float(offer["requested_money"])
    if net_from != 0:
        supabase.table("league_members").update({
            "remaining_budget": float(from_member["remaining_budget"]) + net_from
        }).eq("id", from_member["id"]).execute()
    if net_to != 0:
        supabase.table("league_members").update({
            "remaining_budget": float(to_member["remaining_budget"]) + net_to
        }).eq("id", to_member["id"]).execute()

    # Registrar transaction(s)
    tx_price = max(float(offer["offered_money"]), float(offer["requested_money"]))
    supabase.table("transactions").insert({
        "league_id": str(league_id),
        "buyer_id": to_member["id"],
        "seller_id": from_member["id"],
        "player_id": offer["offered_player_id"] or offer["requested_player_id"],
        "type": "trade",
        "price": tx_price,
    }).execute()

    # Marcar oferta como aceptada
    supabase.table("trade_offers").update({"status": "accepted"}).eq("id", str(offer_id)).execute()

    return {"message": "Trade aceptado correctamente."}


@router.post("/{league_id}/{offer_id}/reject", status_code=status.HTTP_200_OK)
async def reject_trade(
    league_id: UUID,
    offer_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Rechaza la oferta de trade."""
    to_member = _get_member(supabase, str(league_id), user["id"])

    offer_resp = (
        supabase.table("trade_offers")
        .select("id, status, to_member_id")
        .eq("id", str(offer_id))
        .eq("league_id", str(league_id))
        .eq("to_member_id", to_member["id"])
        .single()
        .execute()
    )
    offer = offer_resp.data
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta no encontrada")
    if offer["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La oferta ya no está pendiente")

    supabase.table("trade_offers").update({"status": "rejected"}).eq("id", str(offer_id)).execute()
    return {"message": "Trade rechazado."}


@router.delete("/{league_id}/{offer_id}", status_code=status.HTTP_200_OK)
async def cancel_trade(
    league_id: UUID,
    offer_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Cancela la oferta de trade (solo el creador)."""
    from_member = _get_member(supabase, str(league_id), user["id"])

    offer_resp = (
        supabase.table("trade_offers")
        .select("id, status")
        .eq("id", str(offer_id))
        .eq("league_id", str(league_id))
        .eq("from_member_id", from_member["id"])
        .single()
        .execute()
    )
    offer = offer_resp.data
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta no encontrada o no eres el creador")
    if offer["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La oferta ya no está pendiente")

    supabase.table("trade_offers").update({"status": "cancelled"}).eq("id", str(offer_id)).execute()
    return {"message": "Trade cancelado."}


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _get_or_create_roster(supabase: Client, member_id: str) -> str:
    """Devuelve el roster_id del miembro; lo crea si no existe todavía.

    Garantiza que un manager que recibe un jugador por trade tenga un roster.
    """
    resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member_id)
        .single()
        .execute()
    )
    if resp.data:
        return resp.data["id"]
    new = supabase.table("rosters").insert({"member_id": member_id}).execute()
    return new.data[0]["id"]

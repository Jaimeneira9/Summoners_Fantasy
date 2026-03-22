from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()

Slot = Literal[
    "starter_1", "starter_2", "starter_3", "starter_4", "starter_5",
    "coach", "bench_1", "bench_2",
]

ROLE_TO_SLOT: dict[str, str] = {
    "top":     "starter_1",
    "jungle":  "starter_2",
    "mid":     "starter_3",
    "adc":     "starter_4",
    "support": "starter_5",
    "coach":   "coach",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlayerBrief(BaseModel):
    name: str
    team: str
    role: str
    image_url: str | None
    current_price: float
    split_points: float = 0.0


class ListingOut(BaseModel):
    id: UUID
    player_id: UUID
    seller_id: UUID | None
    league_id: UUID
    ask_price: float
    status: str
    listed_at: str
    closes_at: str | None = None


class ListingDetailOut(ListingOut):
    players: PlayerBrief


class BuyRequest(BaseModel):
    listing_id: UUID


class SellIntentRequest(BaseModel):
    roster_player_id: UUID


class SellIntentOut(BaseModel):
    roster_player_id: UUID
    player_id: UUID
    for_sale: bool
    message: str


class SellOfferOut(BaseModel):
    id: UUID
    ask_price: float
    status: str
    expires_at: str
    player: PlayerBrief


class CandidateOut(BaseModel):
    id: UUID
    player_id: UUID
    ask_price: float
    added_at: str
    players: PlayerBrief


class TransactionOut(BaseModel):
    id: UUID
    league_id: UUID
    buyer_id: UUID | None
    seller_id: UUID | None
    player_id: UUID
    type: str
    price: float
    executed_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_member(supabase: Client, league_id: str, user_id: str) -> dict:
    resp = (
        supabase.table("league_members")
        .select("id, remaining_budget")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")
    return resp.data[0]


def _get_roster(supabase: Client, member_id: str) -> dict:
    resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes equipo en esta liga")
    return resp.data[0]


def _auto_assign_slot(supabase: Client, roster_id: str, player_role: str) -> str:
    """Devuelve el slot natural del rol si está libre, si no el primer bench disponible."""
    natural = ROLE_TO_SLOT.get(player_role, "bench_1")
    occupied_resp = (
        supabase.table("roster_players")
        .select("slot")
        .eq("roster_id", roster_id)
        .execute()
    )
    occupied = {row["slot"] for row in (occupied_resp.data or [])}

    if natural not in occupied:
        return natural
    for bench in ["bench_1", "bench_2"]:
        if bench not in occupied:
            return bench
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Tu equipo está completo. Vende un jugador antes de fichar.",
    )


# ---------------------------------------------------------------------------
# Endpoints: listings
# ---------------------------------------------------------------------------

@router.get("/{league_id}/listings", response_model=list[ListingDetailOut])
async def get_listings(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[ListingDetailOut]:
    """Listado de jugadores disponibles en el mercado de una liga."""
    _get_member(supabase, str(league_id), user["id"])

    now = datetime.now(timezone.utc).isoformat()

    # Lazy refresh: si hay listings activos ya vencidos, resolver pujas y refrescar
    stale_resp = (
        supabase.table("market_listings")
        .select("id", count="exact")
        .eq("league_id", str(league_id))
        .eq("status", "active")
        .lt("closes_at", now)
        .execute()
    )
    if (stale_resp.count or 0) > 0:
        from market.refresh import run_all_leagues_refresh
        run_all_leagues_refresh(supabase)

    resp = (
        supabase.table("market_listings")
        .select(
            "id, player_id, seller_id, league_id, ask_price, status, listed_at, closes_at,"
            " players(name, team, role, image_url, current_price)"
        )
        .eq("league_id", str(league_id))
        .eq("status", "active")
        .gt("closes_at", now)
        .order("listed_at")
        .execute()
    )
    listings = resp.data or []

    # Fetch split_points for the active competition for each player in listings
    player_ids = [row["player_id"] for row in listings if row.get("player_id")]
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

    for listing in listings:
        pid = str(listing["player_id"])
        listing["players"]["split_points"] = split_points_by_player.get(pid, 0.0)

    return listings


@router.post("/{league_id}/buy", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def buy_player(
    league_id: UUID,
    body: BuyRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> TransactionOut:
    """Compra un jugador del mercado. El slot se asigna automáticamente según el rol."""
    member = _get_member(supabase, str(league_id), user["id"])

    # Get listing
    listing_resp = (
        supabase.table("market_listings")
        .select("id, player_id, seller_id, ask_price, candidate_id")
        .eq("id", str(body.listing_id))
        .eq("league_id", str(league_id))
        .eq("status", "active")
        .execute()
    )
    listing = listing_resp.data[0] if listing_resp.data else None
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing no encontrado o inactivo")

    if float(member["remaining_budget"]) < float(listing["ask_price"]):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Presupuesto insuficiente")

    # Get player role for auto-slot
    player_resp = (
        supabase.table("players")
        .select("role")
        .eq("id", listing["player_id"])
        .execute()
    )
    player_role = player_resp.data[0]["role"] if player_resp.data else "bench"

    # Get or create roster
    roster_resp = (
        supabase.table("rosters")
        .select("id")
        .eq("member_id", member["id"])
        .execute()
    )
    if roster_resp.data:
        roster_id = roster_resp.data[0]["id"]

        # Check not already owned
        owned_resp = (
            supabase.table("roster_players")
            .select("id")
            .eq("roster_id", roster_id)
            .eq("player_id", listing["player_id"])
            .execute()
        )
        if owned_resp.data:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya tienes este jugador en tu equipo")
    else:
        new_roster = (
            supabase.table("rosters")
            .insert({"member_id": member["id"]})
            .execute()
        )
        roster_id = new_roster.data[0]["id"]

    # Auto-assign slot based on role
    slot = _auto_assign_slot(supabase, roster_id, player_role)

    # Add player to roster
    supabase.table("roster_players").insert({
        "roster_id": roster_id,
        "player_id": listing["player_id"],
        "slot": slot,
        "price_paid": float(listing["ask_price"]),
    }).execute()

    # Deduct buyer budget
    supabase.table("league_members").update({
        "remaining_budget": float(member["remaining_budget"]) - float(listing["ask_price"])
    }).eq("id", member["id"]).execute()

    # Pay seller (if not a system listing)
    if listing["seller_id"]:
        seller_resp = (
            supabase.table("league_members")
            .select("remaining_budget")
            .eq("id", listing["seller_id"])
            .execute()
        )
        if seller_resp.data:
            supabase.table("league_members").update({
                "remaining_budget": float(seller_resp.data[0]["remaining_budget"]) + float(listing["ask_price"])
            }).eq("id", listing["seller_id"]).execute()

    # Mark listing sold
    supabase.table("market_listings").update({"status": "sold"}).eq("id", str(body.listing_id)).execute()

    # Remove from candidates pool if originated from one
    if listing.get("candidate_id"):
        supabase.table("market_candidates").delete().eq("id", listing["candidate_id"]).execute()

    # Record transaction
    tx_resp = (
        supabase.table("transactions")
        .insert({
            "league_id": str(league_id),
            "buyer_id": member["id"],
            "seller_id": listing.get("seller_id"),
            "player_id": listing["player_id"],
            "type": "buy",
            "price": float(listing["ask_price"]),
        })
        .execute()
    )
    return tx_resp.data[0]


# ---------------------------------------------------------------------------
# Endpoints: sell intent
# ---------------------------------------------------------------------------

@router.post("/{league_id}/sell", response_model=SellIntentOut, status_code=status.HTTP_200_OK)
async def set_sell_intent(
    league_id: UUID,
    body: SellIntentRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> SellIntentOut:
    """Señala la intención de vender un jugador (for_sale=True)."""
    member = _get_member(supabase, str(league_id), user["id"])
    roster = _get_roster(supabase, member["id"])

    rp_resp = (
        supabase.table("roster_players")
        .select("id, player_id")
        .eq("id", str(body.roster_player_id))
        .eq("roster_id", roster["id"])
        .execute()
    )
    if not rp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en tu equipo")

    supabase.table("roster_players").update({"for_sale": True}).eq(
        "id", str(body.roster_player_id)
    ).execute()

    return SellIntentOut(
        roster_player_id=body.roster_player_id,
        player_id=rp_resp.data[0]["player_id"],
        for_sale=True,
        message="Jugador marcado para venta. Recibirás una oferta en el próximo refresco diario.",
    )


@router.delete("/{league_id}/sell", status_code=status.HTTP_200_OK)
async def cancel_sell_intent(
    league_id: UUID,
    body: SellIntentRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> SellIntentOut:
    """Cancela la intención de venta (for_sale=False)."""
    member = _get_member(supabase, str(league_id), user["id"])
    roster = _get_roster(supabase, member["id"])

    rp_resp = (
        supabase.table("roster_players")
        .select("id, player_id")
        .eq("id", str(body.roster_player_id))
        .eq("roster_id", roster["id"])
        .execute()
    )
    if not rp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en tu equipo")

    supabase.table("roster_players").update({"for_sale": False}).eq(
        "id", str(body.roster_player_id)
    ).execute()

    return SellIntentOut(
        roster_player_id=body.roster_player_id,
        player_id=rp_resp.data[0]["player_id"],
        for_sale=False,
        message="Intención de venta cancelada.",
    )


# ---------------------------------------------------------------------------
# Endpoints: sell offers
# ---------------------------------------------------------------------------

@router.get("/{league_id}/sell-offers", response_model=list[SellOfferOut])
async def get_sell_offers(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[SellOfferOut]:
    """Devuelve las sell_offers pendientes del usuario en la liga."""
    member = _get_member(supabase, str(league_id), user["id"])

    resp = (
        supabase.table("sell_offers")
        .select(
            "id, ask_price, status, expires_at,"
            " players(name, team, role, image_url, current_price)"
        )
        .eq("league_id", str(league_id))
        .eq("member_id", member["id"])
        .eq("status", "pending")
        .execute()
    )
    result = []
    for row in (resp.data or []):
        result.append(SellOfferOut(
            id=row["id"],
            ask_price=row["ask_price"],
            status=row["status"],
            expires_at=row["expires_at"],
            player=PlayerBrief(**row["players"]),
        ))
    return result


@router.post(
    "/{league_id}/sell-offers/{offer_id}/accept",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def accept_sell_offer(
    league_id: UUID,
    offer_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> TransactionOut:
    """Acepta la oferta del sistema: elimina del roster, añade al pool de candidatos."""
    member = _get_member(supabase, str(league_id), user["id"])

    offer_resp = (
        supabase.table("sell_offers")
        .select("id, roster_player_id, player_id, ask_price, status")
        .eq("id", str(offer_id))
        .eq("league_id", str(league_id))
        .eq("member_id", member["id"])
        .execute()
    )
    offer = offer_resp.data[0] if offer_resp.data else None
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta no encontrada")
    if offer["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La oferta ya no está pendiente")

    supabase.table("sell_offers").update({"status": "accepted"}).eq("id", str(offer_id)).execute()

    if offer["roster_player_id"]:
        supabase.table("roster_players").delete().eq("id", offer["roster_player_id"]).execute()

    # Acreditar el precio de venta al presupuesto del vendedor
    supabase.table("league_members").update({
        "remaining_budget": float(member["remaining_budget"]) + float(offer["ask_price"])
    }).eq("id", member["id"]).execute()

    supabase.table("market_candidates").insert({
        "league_id": str(league_id),
        "player_id": offer["player_id"],
        "seller_id": member["id"],
        "ask_price": float(offer["ask_price"]),
    }).execute()

    tx_resp = (
        supabase.table("transactions")
        .insert({
            "league_id": str(league_id),
            "seller_id": member["id"],
            "player_id": offer["player_id"],
            "type": "sell",
            "price": float(offer["ask_price"]),
        })
        .execute()
    )
    return tx_resp.data[0]


@router.post("/{league_id}/sell-offers/{offer_id}/reject", status_code=status.HTTP_200_OK)
async def reject_sell_offer(
    league_id: UUID,
    offer_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Rechaza la oferta del sistema: limpia for_sale en roster_player."""
    member = _get_member(supabase, str(league_id), user["id"])

    offer_resp = (
        supabase.table("sell_offers")
        .select("id, roster_player_id, status")
        .eq("id", str(offer_id))
        .eq("league_id", str(league_id))
        .eq("member_id", member["id"])
        .execute()
    )
    offer = offer_resp.data[0] if offer_resp.data else None
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta no encontrada")
    if offer["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La oferta ya no está pendiente")

    supabase.table("sell_offers").update({"status": "rejected"}).eq("id", str(offer_id)).execute()

    if offer["roster_player_id"]:
        supabase.table("roster_players").update({"for_sale": False}).eq(
            "id", offer["roster_player_id"]
        ).execute()

    return {"message": "Oferta rechazada. El jugador ya no está marcado para venta."}


# ---------------------------------------------------------------------------
# Endpoints: candidates pool
# ---------------------------------------------------------------------------

@router.get("/{league_id}/candidates", response_model=list[CandidateOut])
async def get_candidates(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[CandidateOut]:
    """Candidatos en el pool que pertenecen al usuario (para ver su estado)."""
    member = _get_member(supabase, str(league_id), user["id"])

    resp = (
        supabase.table("market_candidates")
        .select(
            "id, player_id, ask_price, added_at,"
            " players(name, team, role, image_url, current_price)"
        )
        .eq("league_id", str(league_id))
        .eq("seller_id", member["id"])
        .execute()
    )
    return resp.data or []

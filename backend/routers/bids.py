"""
Router: Pujas en listings del mercado (bids).

Rutas principales:
  POST /{league_id}/listings/{listing_id}  — colocar o actualizar una puja
  GET  /{league_id}/my-bids                — ver las pujas activas del usuario
  DELETE /{league_id}/listings/{listing_id} — cancelar la puja en un listing

Lógica de negocio central:
  - Las pujas son competitivas: gana la más alta al cierre del listing.
  - El presupuesto disponible para pujar = remaining_budget - sum(pujas activas en otros listings).
    Esto evita que el usuario comprometa el mismo dinero en varias pujas simultáneas.
  - La puja mínima es igual al current_price del jugador.
  - Si el usuario ya tiene una puja en ese listing, se actualiza en lugar de crear una nueva.
  - No se puede cancelar una puja si el listing ya cerró (closes_at en el pasado).
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


class BidRequest(BaseModel):
    bid_amount: float = Field(..., gt=0)


class BidOut(BaseModel):
    id: UUID
    listing_id: UUID
    member_id: UUID
    bid_amount: float
    placed_at: str
    status: str


class MyBidOut(BaseModel):
    id: UUID
    listing_id: UUID
    bid_amount: float
    placed_at: str
    status: str
    player_name: str
    player_role: str
    player_image_url: str | None
    player_team: str
    listing_closes_at: str | None
    listing_ask_price: float


def _get_member(supabase: Client, league_id: str, user_id: str) -> dict:
    """Devuelve el registro de league_members del usuario, o lanza HTTP 403."""
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


@router.post("/{league_id}/listings/{listing_id}", response_model=BidOut, status_code=status.HTTP_201_CREATED)
async def place_bid(
    league_id: UUID,
    listing_id: UUID,
    body: BidRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> BidOut:
    """Coloca o actualiza una puja en un listing activo.

    Valida que el listing no haya cerrado, que la puja sea >= current_price del jugador,
    y que el presupuesto disponible (descontando otras pujas activas) sea suficiente.
    Si el usuario ya tiene puja en este listing, se actualiza en lugar de insertar.
    """
    member = _get_member(supabase, str(league_id), user["id"])

    listing_resp = (
        supabase.table("market_listings")
        .select("id, ask_price, closes_at, status, players(current_price)")
        .eq("id", str(listing_id))
        .eq("league_id", str(league_id))
        .eq("status", "active")
        .execute()
    )
    listing = listing_resp.data[0] if listing_resp.data else None
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing no encontrado o inactivo")

    if listing.get("closes_at"):
        closes = datetime.fromisoformat(listing["closes_at"].replace("Z", "+00:00"))
        if closes < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El periodo de pujas ha cerrado")

    player_price = float(listing["players"]["current_price"])
    if body.bid_amount < player_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La puja mínima es {player_price}M",
        )

    active_bids_resp = (
        supabase.table("market_bids")
        .select("bid_amount")
        .eq("member_id", member["id"])
        .eq("status", "active")
        .neq("listing_id", str(listing_id))
        .execute()
    )
    active_bids_sum = sum(float(b["bid_amount"]) for b in (active_bids_resp.data or []))
    available = float(member["remaining_budget"]) - active_bids_sum
    if body.bid_amount > available:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Presupuesto insuficiente — tenés {available:.1f}M disponibles ({active_bids_sum:.1f}M retenidos en pujas activas)",
        )

    existing_resp = (
        supabase.table("market_bids")
        .select("id")
        .eq("listing_id", str(listing_id))
        .eq("member_id", member["id"])
        .execute()
    )

    if existing_resp.data:
        bid_resp = (
            supabase.table("market_bids")
            .update({"bid_amount": body.bid_amount, "status": "active"})
            .eq("id", existing_resp.data[0]["id"])
            .execute()
        )
    else:
        bid_resp = (
            supabase.table("market_bids")
            .insert({
                "listing_id": str(listing_id),
                "league_id": str(league_id),
                "member_id": member["id"],
                "bid_amount": body.bid_amount,
            })
            .execute()
        )

    return bid_resp.data[0]


@router.get("/{league_id}/my-bids", response_model=list[MyBidOut])
async def get_my_bids(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[MyBidOut]:
    """Devuelve todas las pujas del usuario en la liga (excepto canceladas).

    Hace join manual de bids → listings → players para enriquecer cada puja
    con información del jugador y fecha de cierre del listing.
    """
    member = _get_member(supabase, str(league_id), user["id"])

    bids_resp = (
        supabase.table("market_bids")
        .select("id, listing_id, bid_amount, placed_at, status")
        .eq("league_id", str(league_id))
        .eq("member_id", member["id"])
        .neq("status", "cancelled")
        .order("placed_at", desc=True)
        .execute()
    )
    bids = bids_resp.data or []
    if not bids:
        return []

    listing_ids = [b["listing_id"] for b in bids]
    listings_resp = (
        supabase.table("market_listings")
        .select("id, ask_price, closes_at, player_id")
        .in_("id", listing_ids)
        .execute()
    )
    listings_map = {l["id"]: l for l in (listings_resp.data or [])}

    player_ids = list({l["player_id"] for l in listings_map.values()})
    players_resp = (
        supabase.table("players")
        .select("id, name, role, image_url, team")
        .in_("id", player_ids)
        .execute()
    )
    players_map = {p["id"]: p for p in (players_resp.data or [])}

    result = []
    for bid in bids:
        listing = listings_map.get(bid["listing_id"], {})
        player = players_map.get(listing.get("player_id", ""), {})
        result.append(MyBidOut(
            id=bid["id"],
            listing_id=bid["listing_id"],
            bid_amount=float(bid["bid_amount"]),
            placed_at=bid["placed_at"],
            status=bid["status"],
            player_name=player.get("name", ""),
            player_role=player.get("role", ""),
            player_image_url=player.get("image_url"),
            player_team=player.get("team", ""),
            listing_closes_at=listing.get("closes_at"),
            listing_ask_price=float(listing.get("ask_price", 0)),
        ))
    return result


@router.delete("/{league_id}/listings/{listing_id}", status_code=status.HTTP_200_OK)
async def cancel_bid(
    league_id: UUID,
    listing_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Cancela la puja del usuario en un listing, si el mercado todavía no ha cerrado."""
    member = _get_member(supabase, str(league_id), user["id"])

    listing_resp = (
        supabase.table("market_listings")
        .select("closes_at")
        .eq("id", str(listing_id))
        .execute()
    )
    if listing_resp.data and listing_resp.data[0].get("closes_at"):
        closes = datetime.fromisoformat(listing_resp.data[0]["closes_at"].replace("Z", "+00:00"))
        if closes < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El mercado ya ha cerrado")

    result = (
        supabase.table("market_bids")
        .update({"status": "cancelled"})
        .eq("listing_id", str(listing_id))
        .eq("member_id", member["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes puja en este listing")

    return {"message": "Puja cancelada"}

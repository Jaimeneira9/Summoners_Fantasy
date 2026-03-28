from datetime import datetime, timedelta, timezone
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
    last_price_change_pct: float = 0.0


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
    offer_type: str | None = None  # "peer" for sell_offers from another manager, None for system listings
    bid_count: int = 0


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
    offer_type: str  # "sistema" | "manager"
    from_username: str | None = None


class PeerOfferIn(BaseModel):
    roster_player_id: str
    amount: float


class PeerOfferOut(BaseModel):
    id: str
    ask_price: float
    message: str


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
            " players(name, team, role, image_url, current_price, last_price_change_pct)"
        )
        .eq("league_id", str(league_id))
        .eq("status", "active")
        .gt("closes_at", now)
        .order("listed_at")
        .execute()
    )
    listings = resp.data or []

    # Fetch peer sell_offers (from_member_id IS NOT NULL) and merge into listings
    peer_resp = (
        supabase.table("sell_offers")
        .select(
            "id, player_id, member_id, league_id, ask_price, status, created_at, expires_at,"
            " players(name, team, role, image_url, current_price, last_price_change_pct)"
        )
        .eq("league_id", str(league_id))
        .eq("status", "pending")
        .not_.is_("from_member_id", "null")
        .execute()
    )
    for offer in (peer_resp.data or []):
        listings.append({
            "id": offer["id"],
            "player_id": offer["player_id"],
            "seller_id": offer["member_id"],
            "league_id": offer["league_id"],
            "ask_price": offer["ask_price"],
            "status": "active",
            "listed_at": offer["created_at"],
            "closes_at": offer.get("expires_at"),
            "players": offer["players"],
            "offer_type": "peer",
        })

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

    # Count active bids per listing (only for market_listings, not peer sell_offers)
    listing_ids = [row["id"] for row in listings if not row.get("offer_type")]
    bid_counts: dict[str, int] = {}
    if listing_ids:
        bids_resp = (
            supabase.table("market_bids")
            .select("listing_id", count="exact")
            .in_("listing_id", listing_ids)
            .eq("status", "active")
            .execute()
        )
        # The Supabase client returns all rows; aggregate manually
        for bid_row in (bids_resp.data or []):
            lid = str(bid_row["listing_id"])
            bid_counts[lid] = bid_counts.get(lid, 0) + 1

    for listing in listings:
        listing["bid_count"] = bid_counts.get(str(listing["id"]), 0)

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
    ask_price = float(listing["ask_price"])
    supabase.table("roster_players").insert({
        "roster_id": roster_id,
        "player_id": listing["player_id"],
        "slot": slot,
        "price_paid": ask_price,
        "clause_expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "clause_amount": ask_price,
    }).execute()

    # Deduct buyer budget (atomic — verifica y descuenta en una sola transacción)
    result = supabase.rpc("deduct_budget", {
        "p_member_id": member["id"],
        "p_amount": float(ask_price)
    }).execute()

    if not result.data:
        raise HTTPException(status_code=400, detail="Presupuesto insuficiente")

    # Pay seller (if not a system listing) — atómico, sin read-modify-write
    if listing["seller_id"]:
        supabase.rpc("add_budget", {
            "p_member_id": listing["seller_id"],
            "p_amount": float(ask_price)
        }).execute()

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
            "id, ask_price, status, expires_at, from_member_id,"
            " players(name, team, role, image_url, current_price, last_price_change_pct)"
        )
        .eq("league_id", str(league_id))
        .eq("member_id", member["id"])
        .eq("status", "pending")
        .execute()
    )
    rows = resp.data or []

    # Resolve usernames for peer offers (from_member_id not null)
    peer_member_ids = list({row["from_member_id"] for row in rows if row.get("from_member_id")})
    peer_username_map: dict[str, str] = {}
    if peer_member_ids:
        lm_resp = (
            supabase.table("league_members")
            .select("id, user_id")
            .in_("id", peer_member_ids)
            .execute()
        )
        peer_user_ids = [lm["user_id"] for lm in (lm_resp.data or []) if lm.get("user_id")]
        member_user_map: dict[str, str] = {lm["id"]: lm["user_id"] for lm in (lm_resp.data or [])}

        if peer_user_ids:
            profiles_resp = (
                supabase.table("profiles")
                .select("id, username")
                .in_("id", peer_user_ids)
                .execute()
            )
            user_username_map: dict[str, str] = {p["id"]: p["username"] for p in (profiles_resp.data or [])}
            for member_id_key, user_id_val in member_user_map.items():
                peer_username_map[member_id_key] = user_username_map.get(user_id_val, "")

    result = []
    for row in rows:
        from_member_id_val: str | None = row.get("from_member_id")
        offer_type = "manager" if from_member_id_val else "sistema"
        from_username: str | None = peer_username_map.get(from_member_id_val) if from_member_id_val else None
        result.append(SellOfferOut(
            id=row["id"],
            ask_price=row["ask_price"],
            status=row["status"],
            expires_at=row["expires_at"],
            player=PlayerBrief(**row["players"]),
            offer_type=offer_type,
            from_username=from_username,
        ))
    return result


@router.post("/{league_id}/offer", response_model=PeerOfferOut, status_code=status.HTTP_201_CREATED)
async def create_peer_offer(
    league_id: UUID,
    body: PeerOfferIn,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> PeerOfferOut:
    """Crea una oferta de compra directa entre managers (peer offer)."""
    buyer_member = _get_member(supabase, str(league_id), user["id"])

    # Guard: amount debe ser > 0
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El monto debe ser mayor a 0",
        )

    # Fetch roster_player: verificar que pertenece a esta liga y está for_sale=True
    rp_resp = (
        supabase.table("roster_players")
        .select(
            "id, player_id, for_sale,"
            " rosters!inner(member_id, league_members!inner(id, league_id))"
        )
        .eq("id", body.roster_player_id)
        .eq("for_sale", True)
        .eq("rosters.league_members.league_id", str(league_id))
        .execute()
    )
    rp = rp_resp.data[0] if rp_resp.data else None
    if not rp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jugador no encontrado en esta liga o no está disponible para venta",
        )

    owner_member_id: str = rp["rosters"]["league_members"]["id"]
    player_id: str = rp["player_id"]

    # Guard: el comprador no puede ofertar por su propio jugador
    if owner_member_id == buyer_member["id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No podés hacer una oferta por tu propio jugador",
        )

    # Guard: presupuesto suficiente
    if float(buyer_member["remaining_budget"]) < body.amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Presupuesto insuficiente",
        )

    # Guard: no duplicar oferta pendiente del mismo comprador para el mismo roster_player
    existing_resp = (
        supabase.table("sell_offers")
        .select("id")
        .eq("roster_player_id", body.roster_player_id)
        .eq("from_member_id", buyer_member["id"])
        .eq("status", "pending")
        .execute()
    )
    if existing_resp.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tenés una oferta pendiente para este jugador",
        )

    # Insertar sell_offer con from_member_id = buyer
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    insert_resp = (
        supabase.table("sell_offers")
        .insert({
            "league_id": str(league_id),
            "member_id": owner_member_id,
            "roster_player_id": body.roster_player_id,
            "player_id": player_id,
            "ask_price": body.amount,
            "status": "pending",
            "from_member_id": buyer_member["id"],
            "expires_at": expires_at,
        })
        .execute()
    )
    new_offer = insert_resp.data[0]

    return PeerOfferOut(
        id=str(new_offer["id"]),
        ask_price=float(new_offer["ask_price"]),
        message="Oferta enviada al manager. Recibirás una notificación cuando responda.",
    )


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
            " players(name, team, role, image_url, current_price, last_price_change_pct)"
        )
        .eq("league_id", str(league_id))
        .eq("seller_id", member["id"])
        .execute()
    )
    return resp.data or []


# ---------------------------------------------------------------------------
# Endpoints: cláusulas de rescisión
# ---------------------------------------------------------------------------

class ClauseUpgradeRequest(BaseModel):
    amount: float = Field(..., gt=0)


class ClauseInfoOut(BaseModel):
    is_owned: bool
    owned_by_me: bool
    clause_amount: float | None
    clause_expires_at: str | None  # ISO string o None
    clause_active: bool
    roster_player_id: str | None
    for_sale: bool = False


@router.post("/{league_id}/clause/{roster_player_id}/activate", status_code=status.HTTP_200_OK)
async def activate_clause(
    league_id: str,
    roster_player_id: str,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Activa la cláusula de rescisión: paga el importe y ficha al jugador."""
    buyer_member = _get_member(supabase, league_id, user["id"])

    # Fetch roster_player con join a rosters → league_members para verificar que
    # el jugador pertenece a la liga del parámetro de ruta (previene cross-league exploit)
    rp_resp = (
        supabase.table("roster_players")
        .select("id, player_id, clause_expires_at, clause_amount, rosters(member_id, league_members(league_id))")
        .eq("id", roster_player_id)
        .eq("rosters.league_members.league_id", league_id)
        .execute()
    )
    rp = rp_resp.data[0] if rp_resp.data else None
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado")

    # Validar que el jugador pertenece a esta liga (defensa en profundidad contra
    # el caso en que PostgREST devuelva el row con el join nulo en vez de excluirlo)
    owner_league_id = (rp["rosters"].get("league_members") or {}).get("league_id")
    if owner_league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado")

    owner_member_id: str = rp["rosters"]["member_id"]

    # El activador no puede ser el propietario actual
    if owner_member_id == buyer_member["id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No podés activar la cláusula de un jugador que ya es tuyo",
        )

    # Validar que la cláusula existe y no ha expirado
    if not rp.get("clause_expires_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este jugador no tiene cláusula activa",
        )
    now = datetime.now(timezone.utc)
    clause_expires = datetime.fromisoformat(rp["clause_expires_at"])
    if clause_expires.tzinfo is None:
        clause_expires = clause_expires.replace(tzinfo=timezone.utc)
    if clause_expires <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cláusula de este jugador ha expirado",
        )

    clause_amount = float(rp["clause_amount"])
    player_id: str = rp["player_id"]

    # Obtener precio actual del jugador (para la nueva cláusula)
    player_resp = (
        supabase.table("players")
        .select("current_price, role")
        .eq("id", player_id)
        .execute()
    )
    if not player_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado en la BD")
    player = player_resp.data[0]

    # Obtener roster del comprador
    buyer_roster = _get_roster(supabase, buyer_member["id"])
    buyer_roster_id: str = buyer_roster["id"]

    # Verificar que el comprador no tiene ya este jugador
    owned_resp = (
        supabase.table("roster_players")
        .select("id")
        .eq("roster_id", buyer_roster_id)
        .eq("player_id", player_id)
        .execute()
    )
    if owned_resp.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tenés este jugador en tu equipo",
        )

    # Determinar slot libre para el comprador
    bench_slot: str | None = None
    occupied_resp = (
        supabase.table("roster_players")
        .select("slot")
        .eq("roster_id", buyer_roster_id)
        .execute()
    )
    occupied = {row["slot"] for row in (occupied_resp.data or [])}
    for candidate_slot in ["bench_1", "bench_2"]:
        if candidate_slot not in occupied:
            bench_slot = candidate_slot
            break
    if bench_slot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tu equipo está completo. Liberá un slot antes de activar la cláusula.",
        )

    new_clause_expires = (now + timedelta(days=14)).isoformat()

    # Ejecutar transferencia
    # 1. Descuento atómico — verifica y descuenta en una sola transacción
    result = supabase.rpc("deduct_budget", {
        "p_member_id": buyer_member["id"],
        "p_amount": clause_amount
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Presupuesto insuficiente para activar la cláusula",
        )

    # 2. Acreditar al vendedor (propietario actual) — atómico, sin read-modify-write
    supabase.rpc("add_budget", {
        "p_member_id": owner_member_id,
        "p_amount": clause_amount
    }).execute()

    # 3a. Cancelar sell_offers pendientes para este roster_player (si las hay)
    supabase.table("sell_offers").update({"status": "cancelled"}).eq(
        "roster_player_id", roster_player_id
    ).eq("status", "pending").execute()

    # 3b. Eliminar del roster actual
    supabase.table("roster_players").delete().eq("id", roster_player_id).execute()

    # 4. Insertar en el roster del comprador
    supabase.table("roster_players").insert({
        "roster_id": buyer_roster_id,
        "player_id": player_id,
        "slot": bench_slot,
        "price_paid": clause_amount,
        "clause_expires_at": new_clause_expires,
        "clause_amount": float(player["current_price"]),
    }).execute()

    # 5. Registrar transacción
    supabase.table("transactions").insert({
        "league_id": league_id,
        "buyer_id": buyer_member["id"],
        "seller_id": owner_member_id,
        "player_id": player_id,
        "type": "clause",
        "price": clause_amount,
    }).execute()

    return {
        "ok": True,
        "clause_amount": clause_amount,
        "new_clause_expires_at": new_clause_expires,
    }


@router.post("/{league_id}/clause/{roster_player_id}/upgrade", status_code=status.HTTP_200_OK)
async def upgrade_clause(
    league_id: str,
    roster_player_id: str,
    body: ClauseUpgradeRequest,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Sube el importe de la cláusula pagando una cantidad: nueva_cláusula = vieja + amount * 0.5."""
    member = _get_member(supabase, league_id, user["id"])
    roster = _get_roster(supabase, member["id"])

    # Verificar que el roster_player pertenece al usuario en esta liga
    rp_resp = (
        supabase.table("roster_players")
        .select("id, clause_amount, clause_expires_at")
        .eq("id", roster_player_id)
        .eq("roster_id", roster["id"])
        .execute()
    )
    rp = rp_resp.data[0] if rp_resp.data else None
    if not rp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jugador no encontrado en tu equipo",
        )

    amount = float(body.amount)

    now = datetime.now(timezone.utc)

    # Si ya tiene cláusula activa, validar que no haya expirado
    if rp.get("clause_expires_at"):
        clause_expires = datetime.fromisoformat(rp["clause_expires_at"])
        if clause_expires.tzinfo is None:
            clause_expires = clause_expires.replace(tzinfo=timezone.utc)
        if clause_expires <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La cláusula de este jugador ha expirado",
            )

    current_clause = float(rp.get("clause_amount") or 0)
    new_clause = current_clause + amount * 0.5

    # Descuento atómico — verifica y descuenta en una sola transacción
    result = supabase.rpc("deduct_budget", {
        "p_member_id": member["id"],
        "p_amount": amount
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Presupuesto insuficiente para subir la cláusula",
        )

    # Actualizar cláusula; si no existía, setear también clause_expires_at
    update_payload: dict = {"clause_amount": new_clause}
    if not rp.get("clause_expires_at"):
        update_payload["clause_expires_at"] = (
            now + timedelta(days=14)
        ).isoformat()

    supabase.table("roster_players").update(update_payload).eq("id", roster_player_id).execute()

    return {
        "ok": True,
        "old_clause": current_clause,
        "amount_paid": amount,
        "new_clause": new_clause,
    }


@router.get("/{league_id}/clause/{player_id}", response_model=ClauseInfoOut)
async def get_clause_info(
    league_id: str,
    player_id: str,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> ClauseInfoOut:
    """Devuelve información de la cláusula de un jugador en el contexto de una liga."""
    member = _get_member(supabase, league_id, user["id"])

    # Buscar roster_players para este jugador en esta liga via join
    rp_resp = (
        supabase.table("roster_players")
        .select("id, clause_amount, clause_expires_at, for_sale, rosters(member_id, league_members(league_id, user_id))")
        .eq("player_id", player_id)
        .execute()
    )

    # Filtrar por liga (defensa ante joins nulos de PostgREST)
    rp: dict | None = None
    for row in (rp_resp.data or []):
        roster = row.get("rosters") or {}
        lm = roster.get("league_members") or {}
        if lm.get("league_id") == league_id:
            rp = row
            break

    if not rp:
        return ClauseInfoOut(
            is_owned=False,
            owned_by_me=False,
            clause_amount=None,
            clause_expires_at=None,
            clause_active=False,
            roster_player_id=None,
        )

    roster = rp.get("rosters") or {}
    lm = roster.get("league_members") or {}
    owner_user_id: str = lm.get("user_id", "")
    owned_by_me = owner_user_id == user["id"]

    clause_expires_at: str | None = rp.get("clause_expires_at")
    clause_active = False
    if clause_expires_at:
        try:
            expires = datetime.fromisoformat(clause_expires_at)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            clause_active = expires > datetime.now(timezone.utc)
        except (ValueError, TypeError):
            clause_active = False

    return ClauseInfoOut(
        is_owned=True,
        owned_by_me=owned_by_me,
        clause_amount=float(rp["clause_amount"]) if rp.get("clause_amount") is not None else None,
        clause_expires_at=clause_expires_at,
        clause_active=clause_active,
        roster_player_id=str(rp["id"]),
        for_sale=bool(rp.get("for_sale", False)),
    )

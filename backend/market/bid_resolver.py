"""
Resuelve pujas vencidas: asigna jugadores al ganador de cada listing.
Se llama al inicio del job market_refresh (00:00 UTC).
"""
import logging
from datetime import datetime, timezone, timedelta

from supabase import Client

logger = logging.getLogger(__name__)

ROLE_TO_SLOT: dict[str, str] = {
    "top":     "starter_1",
    "jungle":  "starter_2",
    "mid":     "starter_3",
    "adc":     "starter_4",
    "support": "starter_5",
    "coach":   "coach",
}


def _get_or_create_roster(supabase: Client, member_id: str) -> str:
    resp = supabase.table("rosters").select("id").eq("member_id", member_id).execute()
    if resp.data:
        return resp.data[0]["id"]
    new = supabase.table("rosters").insert({"member_id": member_id}).execute()
    return new.data[0]["id"]


def _auto_slot(supabase: Client, roster_id: str, role: str) -> str | None:
    natural = ROLE_TO_SLOT.get(role, "bench_1")
    occupied_resp = supabase.table("roster_players").select("slot").eq("roster_id", roster_id).execute()
    occupied = {r["slot"] for r in (occupied_resp.data or [])}
    if natural not in occupied:
        return natural
    for bench in ["bench_1", "bench_2"]:
        if bench not in occupied:
            return bench
    return None  # equipo lleno


def resolve_expired_bids(supabase: Client) -> None:
    """Resuelve todos los listings cuyo closes_at < ahora."""
    now = datetime.now(timezone.utc).isoformat()

    listings_resp = (
        supabase.table("market_listings")
        .select("id, player_id, seller_id, league_id, ask_price, candidate_id")
        .eq("status", "active")
        .lt("closes_at", now)
        .execute()
    )
    listings = listings_resp.data or []
    logger.info("Resolving %d expired listings", len(listings))

    for listing in listings:
        try:
            _resolve_listing(supabase, listing)
        except Exception as exc:
            logger.error("Error resolving listing %s: %s", listing["id"], exc)


def _resolve_listing(supabase: Client, listing: dict) -> None:
    listing_id = listing["id"]
    league_id = listing["league_id"]

    # Puja ganadora: mayor importe, desempate por placed_at más antiguo
    bids_resp = (
        supabase.table("market_bids")
        .select("id, member_id, bid_amount")
        .eq("listing_id", listing_id)
        .eq("status", "active")
        .order("bid_amount", desc=True)
        .order("placed_at", desc=False)
        .limit(1)
        .execute()
    )

    if not bids_resp.data:
        supabase.table("market_listings").update({"status": "expired"}).eq("id", listing_id).execute()
        logger.info("Listing %s expired (no bids)", listing_id)
        return

    winning_bid = bids_resp.data[0]
    winner_member_id = winning_bid["member_id"]
    bid_amount = float(winning_bid["bid_amount"])

    member_resp = (
        supabase.table("league_members")
        .select("id, remaining_budget")
        .eq("id", winner_member_id)
        .execute()
    )
    if not member_resp.data:
        supabase.table("market_listings").update({"status": "expired"}).eq("id", listing_id).execute()
        return

    member = member_resp.data[0]
    if float(member["remaining_budget"]) < bid_amount:
        supabase.table("market_listings").update({"status": "expired"}).eq("id", listing_id).execute()
        logger.warning("Winner %s has insufficient budget for listing %s", winner_member_id, listing_id)
        return

    player_resp = supabase.table("players").select("role").eq("id", listing["player_id"]).execute()
    player_role = player_resp.data[0]["role"] if player_resp.data else "bench"

    roster_id = _get_or_create_roster(supabase, winner_member_id)
    slot = _auto_slot(supabase, roster_id, player_role)
    if slot is None:
        supabase.table("market_listings").update({"status": "expired"}).eq("id", listing_id).execute()
        logger.warning("Winner %s has full roster for listing %s", winner_member_id, listing_id)
        return

    supabase.table("roster_players").insert({
        "roster_id": roster_id,
        "player_id": listing["player_id"],
        "slot": slot,
        "price_paid": bid_amount,
        "clause_expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "clause_amount": bid_amount,
    }).execute()

    supabase.table("league_members").update({
        "remaining_budget": float(member["remaining_budget"]) - bid_amount
    }).eq("id", winner_member_id).execute()

    if listing.get("seller_id"):
        seller_resp = (
            supabase.table("league_members")
            .select("remaining_budget")
            .eq("id", listing["seller_id"])
            .execute()
        )
        if seller_resp.data:
            supabase.table("league_members").update({
                "remaining_budget": float(seller_resp.data[0]["remaining_budget"]) + bid_amount
            }).eq("id", listing["seller_id"]).execute()

    supabase.table("market_listings").update({
        "status": "sold",
        "winning_bid_id": winning_bid["id"],
    }).eq("id", listing_id).execute()

    supabase.table("market_bids").update({"status": "won"}).eq("id", winning_bid["id"]).execute()
    supabase.table("market_bids").update({"status": "lost"}).eq("listing_id", listing_id).neq("id", winning_bid["id"]).execute()

    if listing.get("candidate_id"):
        supabase.table("market_candidates").delete().eq("id", listing["candidate_id"]).execute()

    supabase.table("transactions").insert({
        "league_id": league_id,
        "buyer_id": winner_member_id,
        "seller_id": listing.get("seller_id"),
        "player_id": listing["player_id"],
        "type": "bid_win",
        "price": bid_amount,
    }).execute()

    logger.info(
        "Listing %s resolved: winner=%s, amount=%.1fM, slot=%s",
        listing_id, winner_member_id, bid_amount, slot,
    )

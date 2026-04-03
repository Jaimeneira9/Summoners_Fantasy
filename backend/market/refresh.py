"""
Mercado de fichajes.

Inicialización (al crear liga):
  - Todos los jugadores se añaden como candidatos de la liga.
  - Se crean 8 listings activos inmediatamente (closes_at = now + 24h).

Refresco (cada hora):
  0. Resuelve las pujas vencidas (bid_resolver).
  1. Expira los listings cuyo closes_at <= now.
  2. Si quedan menos de MARKET_SIZE listings activos, promociona candidatos.
  3. Para cada roster_player con for_sale=True, crea sell_offer si no existe.
"""
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)

# Número fijo de jugadores visibles en el mercado
MARKET_SIZE = 8

# Rango de precio al generar sell_offer (80-110 % del valor actual)
SELL_OFFER_PRICE_MIN = 0.80
SELL_OFFER_PRICE_MAX = 1.10

# Duración de un listing en minutos. En producción: 1440 (24h).
# Para testing sobreescribir con MARKET_LISTING_MINUTES=5.
_LISTING_MINUTES = int(os.getenv("MARKET_LISTING_MINUTES", "1440"))


def initialize_league_market(supabase: Client, league_id: str) -> None:
    """Inicializa el mercado en el momento de creación de una liga.
    Inserta todos los jugadores como candidatos y crea los primeros 8 listings."""
    players_resp = supabase.table("players").select("id, current_price").execute()
    players: list[dict[str, Any]] = players_resp.data or []
    if not players:
        logger.warning("No players found when initializing market for league %s", league_id)
        return

    # Insertar todos como candidatos
    candidates = [
        {"league_id": league_id, "player_id": p["id"], "seller_id": None, "ask_price": float(p["current_price"])}
        for p in players
    ]
    supabase.table("market_candidates").insert(candidates).execute()

    # Crear los primeros 8 listings
    selected = random.sample(players, min(MARKET_SIZE, len(players)))
    closes_at = (datetime.now(timezone.utc) + timedelta(minutes=_LISTING_MINUTES)).isoformat()

    # Para insertar listings con candidate_id, primero obtenemos los candidatos recién creados
    cands_resp = (
        supabase.table("market_candidates")
        .select("id, player_id, ask_price")
        .eq("league_id", league_id)
        .in_("player_id", [str(p["id"]) for p in selected])
        .execute()
    )
    listings = [
        {
            "player_id": c["player_id"],
            "seller_id": None,
            "league_id": league_id,
            "ask_price": float(c["ask_price"]),
            "status": "active",
            "candidate_id": c["id"],
            "closes_at": closes_at,
        }
        for c in (cands_resp.data or [])
    ]
    if listings:
        supabase.table("market_listings").insert(listings).execute()

    logger.info("Market initialized for league %s: %d candidates, %d listings", league_id, len(candidates), len(listings))


def refresh_market(supabase: Client, league_id: str) -> None:
    """Expira listings vencidos y rellena hasta MARKET_SIZE con candidatos disponibles."""
    # Expirar solo los listings cuyo closes_at ya pasó
    _expire_stale_listings(supabase, league_id)

    # Limpiar cláusulas vencidas
    _expire_clauses(supabase)

    # Contar activos que aún no han vencido
    now = datetime.now(timezone.utc).isoformat()
    active_resp = (
        supabase.table("market_listings")
        .select("id", count="exact")
        .eq("league_id", league_id)
        .eq("status", "active")
        .gt("closes_at", now)
        .execute()
    )
    active_count = active_resp.count or 0
    needed = MARKET_SIZE - active_count

    if needed > 0:
        _promote_candidates(supabase, league_id, needed)

    _create_sell_offers_for_flagged(supabase, league_id)
    logger.info("Market refresh completed for league %s (active=%d)", league_id, active_count)


def run_all_leagues_refresh(supabase: Client) -> None:
    """Resuelve pujas vencidas y refresca el mercado para cada liga activa."""
    from market.bid_resolver import resolve_expired_bids
    resolve_expired_bids(supabase)

    resp = (
        supabase.table("fantasy_leagues")
        .select("id")
        .eq("is_active", True)
        .execute()
    )
    leagues: list[dict[str, Any]] = resp.data or []
    for league in leagues:
        try:
            refresh_market(supabase, league["id"])
        except Exception as exc:
            logger.error("Market refresh failed for league %s: %s", league["id"], exc, exc_info=True)


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _expire_clauses(supabase: Client) -> None:
    """Limpia cláusulas vencidas — el jugador queda sin protección."""
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("roster_players").update({
        "clause_amount": None,
        "clause_expires_at": None,
    }).lte("clause_expires_at", now_iso).not_.is_("clause_expires_at", "null").execute()


def _expire_stale_listings(supabase: Client, league_id: str) -> None:
    """Expira solo los listings cuyo closes_at ya ha pasado."""
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("market_listings").update({"status": "expired"}).eq(
        "league_id", league_id
    ).eq("status", "active").lte("closes_at", now).execute()


def _promote_candidates(supabase: Client, league_id: str, needed: int = MARKET_SIZE) -> None:
    """Selecciona aleatoriamente `needed` candidatos y los convierte en listings activos."""
    # Excluir jugadores que ya tienen un listing activo para no duplicar
    active_resp = (
        supabase.table("market_listings")
        .select("player_id")
        .eq("league_id", league_id)
        .eq("status", "active")
        .execute()
    )
    active_player_ids = {row["player_id"] for row in (active_resp.data or [])}

    resp = (
        supabase.table("market_candidates")
        .select("id, player_id, seller_id, ask_price")
        .eq("league_id", league_id)
        .execute()
    )
    candidates: list[dict[str, Any]] = [
        c for c in (resp.data or []) if c["player_id"] not in active_player_ids
    ]
    if not candidates:
        return

    selected = random.sample(candidates, min(needed, len(candidates)))

    closes_at = (datetime.now(timezone.utc) + timedelta(minutes=_LISTING_MINUTES)).isoformat()
    new_listings = [
        {
            "player_id": c["player_id"],
            "seller_id": c["seller_id"],
            "league_id": league_id,
            "ask_price": float(c["ask_price"]),
            "status": "active",
            "candidate_id": c["id"],
            "closes_at": closes_at,
        }
        for c in selected
    ]
    supabase.table("market_listings").insert(new_listings).execute()


def _create_sell_offers_for_flagged(supabase: Client, league_id: str) -> None:
    """
    Para cada roster_player con for_sale=True en la liga, genera una sell_offer
    si no existe ya una pendiente para ese roster_player.
    """
    # roster_players con for_sale=True en esta liga
    rp_resp = (
        supabase.table("roster_players")
        .select(
            "id, player_id, roster_id,"
            " rosters!inner(member_id, league_members!inner(id, league_id))"
        )
        .eq("for_sale", True)
        .eq("rosters.league_members.league_id", league_id)
        .execute()
    )
    roster_players: list[dict[str, Any]] = rp_resp.data or []

    if not roster_players:
        return

    rp_ids: list[str] = [rp["id"] for rp in roster_players]
    player_ids: list[str] = [rp["player_id"] for rp in roster_players]

    # 1 query batch para sell_offers pendientes
    existing_resp = (
        supabase.table("sell_offers")
        .select("roster_player_id")
        .in_("roster_player_id", rp_ids)
        .eq("status", "pending")
        .execute()
    )
    already_listed: set[str] = {row["roster_player_id"] for row in (existing_resp.data or [])}

    # 1 query batch para precios actuales de jugadores
    prices_resp = (
        supabase.table("players")
        .select("id, current_price")
        .in_("id", player_ids)
        .execute()
    )
    price_by_player: dict[str, float] = {
        row["id"]: float(row["current_price"]) for row in (prices_resp.data or [])
    }

    new_offers: list[dict[str, Any]] = []
    for rp in roster_players:
        roster_player_id: str = rp["id"]
        player_id: str = rp["player_id"]
        member_id: str = rp["rosters"]["league_members"]["id"]

        if roster_player_id in already_listed:
            continue

        base_price = price_by_player.get(player_id)
        if base_price is None:
            continue

        ask_price = round(base_price * random.uniform(SELL_OFFER_PRICE_MIN, SELL_OFFER_PRICE_MAX), 2)
        new_offers.append({
            "league_id": league_id,
            "member_id": member_id,
            "roster_player_id": roster_player_id,
            "player_id": player_id,
            "ask_price": ask_price,
        })

    if new_offers:
        supabase.table("sell_offers").insert(new_offers).execute()

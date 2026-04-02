"""
Actualizador de precios post-serie.

Se llama al final de cada ingestión de series (series_ingest.py).
Actualiza current_price, last_price_change_pct, avg_points_baseline
y price_history para cada jugador con stats recientes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from supabase import Client

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 5
SENSITIVITY = 0.3
CAP_UP = 0.10
CAP_DOWN = -0.10
PRICE_FLOOR = 1.0


def update_player_prices_post_series(supabase: Client, player_ids: list[str]) -> None:
    """Llamado después de que se ingesta una jornada de series.

    Actualiza precios para todos los jugadores afectados. Un fallo en un
    jugador individual no detiene el procesamiento del resto.
    """
    for player_id in player_ids:
        try:
            _update_single_player_price(supabase, player_id)
        except Exception as exc:
            logger.warning("Price update failed for player %s: %s", player_id, exc)


def _update_single_player_price(supabase: Client, player_id: str) -> None:
    """Recalcula y persiste el precio de un jugador individual."""
    # 1. Fetch player: current_price, avg_points_baseline, price_history
    player_resp = (
        supabase.table("players")
        .select("current_price, avg_points_baseline, price_history")
        .eq("id", player_id)
        .single()
        .execute()
    )
    if not player_resp.data:
        logger.warning("Player %s not found, skipping price update", player_id)
        return

    player = player_resp.data

    # 2. Fetch last ROLLING_WINDOW game stats (game_points ORDER BY created_at DESC)
    stats_resp = (
        supabase.table("player_game_stats")
        .select("game_points")
        .eq("player_id", player_id)
        .order("created_at", desc=True)
        .limit(ROLLING_WINDOW)
        .execute()
    )
    stats = stats_resp.data or []

    # 3. recent_avg = mean(game_points) — si no hay stats, retornar sin cambios
    game_points_list = [
        float(r["game_points"])
        for r in stats
        if r.get("game_points") is not None
    ]
    if not game_points_list:
        return

    recent_avg = sum(game_points_list) / len(game_points_list)
    old_price = float(player["current_price"])
    baseline = (
        float(player["avg_points_baseline"])
        if player.get("avg_points_baseline") is not None
        else None
    )

    # 4. Si baseline es None, establecer baseline = recent_avg y retornar sin mover precio
    if baseline is None:
        supabase.table("players").update({
            "avg_points_baseline": round(recent_avg, 2),
        }).eq("id", player_id).execute()
        logger.info(
            "Baseline initialized for player=%s at %.2f (no price movement)",
            player_id,
            recent_avg,
        )
        return

    # 5. delta_pct = (recent_avg - baseline) / baseline * SENSITIVITY
    delta_pct = (recent_avg - baseline) / baseline * SENSITIVITY

    # 6. delta_pct = clamp(delta_pct, CAP_DOWN, CAP_UP)
    delta_pct = max(CAP_DOWN, min(CAP_UP, delta_pct))

    # 7. new_price = max(current_price * (1 + delta_pct), PRICE_FLOOR)
    new_price = max(round(old_price * (1 + delta_pct), 2), PRICE_FLOOR)

    # 8. Append to price_history: {"date": today_iso, "price": new_price, "delta_pct": delta_pct}
    history: list = player.get("price_history") or []
    history.append({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "price": new_price,
        "delta_pct": round(delta_pct, 4),
    })

    # 10. Trim price_history to last 90 entries
    history = history[-90:]

    # 11. UPDATE players: current_price, last_price_change_pct, price_history
    # avg_points_baseline NO se toca aquí — se resetea una vez por semana via reset_weekly_baseline
    supabase.table("players").update({
        "current_price": new_price,
        "last_price_change_pct": round(delta_pct, 4),
        "price_history": history,
    }).eq("id", player_id).execute()

    # 12. UPDATE market_candidates: ask_price WHERE player_id = player_id (all leagues)
    supabase.table("market_candidates").update({
        "ask_price": new_price,
    }).eq("player_id", player_id).execute()

    logger.info(
        "Price updated player=%s old=%.2f new=%.2f delta=%.2f%%",
        player_id,
        old_price,
        new_price,
        delta_pct * 100,
    )


def reset_weekly_baseline(supabase: Client, player_ids: list[str]) -> None:
    """Resetea avg_points_baseline al promedio reciente y last_price_change_pct a 0.

    Llamar una vez por semana (martes) después de que termine la jornada LEC.
    Establece el nuevo baseline contra el cual se medirá la tendencia de la
    semana siguiente.
    """
    for player_id in player_ids:
        try:
            _reset_single_player_baseline(supabase, player_id)
        except Exception as exc:
            logger.warning("Baseline reset failed for player %s: %s", player_id, exc)


def _reset_single_player_baseline(supabase: Client, player_id: str) -> None:
    """Recalcula y persiste el baseline semanal de un jugador individual."""
    stats_resp = (
        supabase.table("player_game_stats")
        .select("game_points")
        .eq("player_id", player_id)
        .order("created_at", desc=True)
        .limit(ROLLING_WINDOW)
        .execute()
    )
    stats = stats_resp.data or []

    game_points_list = [
        float(r["game_points"])
        for r in stats
        if r.get("game_points") is not None
    ]
    if not game_points_list:
        logger.info("No stats found for player=%s, skipping baseline reset", player_id)
        return

    recent_avg = round(sum(game_points_list) / len(game_points_list), 2)

    supabase.table("players").update({
        "avg_points_baseline": recent_avg,
        "last_price_change_pct": 0,
    }).eq("id", player_id).execute()

    logger.info(
        "Baseline reset player=%s new_baseline=%.2f",
        player_id,
        recent_avg,
    )

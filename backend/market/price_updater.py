"""
Actualizador de precios post-serie.

Se llama al final de cada ingestión de series (series_ingest.py).
Actualiza current_price, last_price_change_pct y price_history para cada
jugador en el lote, usando eficiencia relativa a la liga (pts/M).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from supabase import Client

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 3
SENSITIVITY = 0.375
CAP_UP = 0.20
CAP_DOWN = -0.20
PRICE_FLOOR = 8.0


def update_player_prices_post_series(
    supabase: Client,
    player_ids: list[str],
    week: int | None = None,
    rival_map: dict[str, str] | None = None,
) -> None:
    """Llamado después de que se ingesta una jornada de series.

    Actualiza precios para todos los jugadores del lote usando eficiencia
    relativa a la liga. Un fallo en un jugador individual no detiene el
    procesamiento del resto.

    Idempotente: si se llama dos veces con los mismos datos (mismo series_date),
    la segunda llamada no modifica ningún dato.
    """
    series_date = datetime.now(timezone.utc).date().isoformat()

    # ── FASE 1: Recolectar datos por jugador ────────────────────────────────
    # Un dict: player_id → {current_price, recent_avg, price_history, rival}
    player_data: dict[str, dict] = {}

    for player_id in player_ids:
        try:
            rival = (rival_map or {}).get(player_id)

            # 1a. Fetch player row
            player_resp = (
                supabase.table("players")
                .select("current_price, price_history")
                .eq("id", player_id)
                .single()
                .execute()
            )

            if not player_resp.data:
                logger.warning("Player %s not found, skipping", player_id)
                continue

            p = player_resp.data
            current_price = float(p["current_price"] or 0)

            # EC-6: Guard contra current_price=0 (corrupción de datos)
            if current_price <= 0:
                logger.warning(
                    "Player %s has current_price=%s, skipping", player_id, current_price
                )
                continue

            # 1b. Fetch últimas ROLLING_WINDOW partidas
            stats_resp = (
                supabase.table("player_game_stats")
                .select("game_points")
                .eq("player_id", player_id)
                .order("created_at", desc=True)
                .limit(ROLLING_WINDOW)
                .execute()
            )

            game_points_list = [
                float(r["game_points"])
                for r in (stats_resp.data or [])
                if r.get("game_points") is not None
            ]

            # EC-1: Sin stats → skip (excluir del cálculo de league_avg también)
            if not game_points_list:
                continue

            recent_avg = sum(game_points_list) / len(game_points_list)
            price_history = p.get("price_history") or []

            player_data[player_id] = {
                "current_price": current_price,
                "recent_avg": recent_avg,
                "price_history": price_history,
                "rival": rival,
            }

        except Exception as exc:
            logger.warning("Data fetch failed for player %s: %s", player_id, exc)

    # ── FASE 2: Calcular league_avg_efficiency ──────────────────────────────
    # Solo con jugadores que tienen stats válidos (ya filtrados en FASE 1)
    efficiencies = [
        d["recent_avg"] / d["current_price"]
        for d in player_data.values()
    ]
    league_avg = _calculate_league_avg_efficiency(efficiencies)

    # EC-7: Guard — si league_avg == 0, no tiene sentido calcular deltas
    if league_avg == 0:
        logger.warning("league_avg_efficiency=0, skipping all price updates")
        return

    # ── FASE 3: Actualizar precio por jugador ───────────────────────────────
    for player_id, d in player_data.items():
        try:
            rival = d["rival"]
            current_price = d["current_price"]
            recent_avg = d["recent_avg"]
            price_history = d["price_history"]

            # ── GUARD DE IDEMPOTENCIA ─────────────────────────────────────
            # Si ya existe una entrada para series_date, skip completo.
            # Previene acumulación de entradas duplicadas si la función se
            # llama dos veces con los mismos datos (misma serie, mismo día).
            if any(entry.get("date") == series_date for entry in price_history):
                logger.info(
                    "Price update already applied for player=%s date=%s, skipping (idempotent)",
                    player_id, series_date,
                )
                continue

            # ── CÁLCULO DE DELTA ──────────────────────────────────────────
            player_efficiency = recent_avg / current_price
            eff_ratio = (player_efficiency - league_avg) / league_avg

            delta_pct = eff_ratio * SENSITIVITY
            delta_pct = max(CAP_DOWN, min(CAP_UP, delta_pct))

            new_price = max(round(current_price * (1 + delta_pct), 2), PRICE_FLOOR)

            # ── APPEND A PRICE_HISTORY ────────────────────────────────────
            entry: dict = {
                "date": series_date,
                "price": round(new_price, 2),
                "delta_pct": round(delta_pct, 4),
            }
            if week is not None:
                entry["week"] = week
            if rival is not None:
                entry["rival"] = rival

            price_history = (price_history + [entry])[-90:]  # trim a 90 entradas

            # ── PERSISTENCIA ──────────────────────────────────────────────
            supabase.table("players").update({
                "current_price": new_price,
                "last_price_change_pct": round(delta_pct, 4),
                "price_history": price_history,
            }).eq("id", player_id).execute()

            supabase.table("market_candidates").update({
                "ask_price": new_price,
            }).eq("player_id", player_id).execute()

            # clause_amount solo sube (comportamiento existente preservado)
            rp_resp = (
                supabase.table("roster_players")
                .select("id, price_paid, clause_amount")
                .eq("player_id", player_id)
                .execute()
            )
            for rp_row in (rp_resp.data or []):
                if rp_row.get("clause_amount") is None:
                    continue
                price_paid = float(rp_row.get("price_paid") or 0)
                current_clause = float(rp_row["clause_amount"])
                updated_clause = max(price_paid, new_price, current_clause)
                if updated_clause > current_clause:
                    supabase.table("roster_players").update({
                        "clause_amount": round(updated_clause, 2),
                    }).eq("id", rp_row["id"]).execute()

            logger.info(
                "Price updated player=%s old=%.2f new=%.2f delta=%.2f%%",
                player_id, current_price, new_price, delta_pct * 100,
            )

        except Exception as exc:
            logger.warning("Price update failed for player %s: %s", player_id, exc)


def _calculate_league_avg_efficiency(efficiencies: list[float]) -> float:
    """Calcula la media de eficiencia (pts/M) del lote de jugadores válidos.

    Retorna 0.0 si la lista está vacía — el caller debe hacer guard contra 0.
    """
    if not efficiencies:
        return 0.0
    return sum(efficiencies) / len(efficiencies)


def reset_weekly_baseline(supabase: Client, player_ids: list[str]) -> None:
    """Resetea avg_points_baseline al promedio reciente y last_price_change_pct a 0.

    NOTA: Esta función ya no se llama desde el scheduler (desactivada en
    price-efficiency-formula). La fórmula nueva no depende de avg_points_baseline
    como comparador. Se preserva en el código para no romper imports hasta que se
    confirme que no hay dependencias activas.
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

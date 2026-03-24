"""
Funciones de ingestión de datos.

mark_pending_games: job de Leaguepedia — inserta partidas nuevas como pending_stats.
nightly_ingest:     job nocturno — procesa pending_stats con Oracle's Elixir.
"""
import logging
from datetime import datetime

from supabase import Client

from pipeline.leaguepedia import GameSummary
from pipeline.oracles_elixir import OraclesElixirClient, PlayerStats
from scoring.engine import calculate_match_points

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job de Leaguepedia
# ---------------------------------------------------------------------------

def mark_pending_games(games: list[GameSummary], supabase: Client) -> None:
    """
    Inserta partidas nuevas como pending_stats. Idempotente (ON CONFLICT DO NOTHING).
    """
    for game in games:
        payload = {
            "game_id": game.game_id,
            "riot_platform_game_id": game.riot_platform_game_id,
            "team1": game.team1,
            "team2": game.team2,
            "winner": game.winner,
            "duration_min": game.duration_min,
            "scheduled_at": game.scheduled_at.isoformat(),
            "team1_picks": game.team1_picks,
            "team2_picks": game.team2_picks,
            "team1_bans": game.team1_bans,
            "team2_bans": game.team2_bans,
            "status": "pending_stats",
        }
        try:
            supabase.table("matches").upsert(
                payload,
                on_conflict="game_id",
                ignore_duplicates=True,
            ).execute()
            logger.debug("Upserted match %s as pending_stats", game.game_id)
        except Exception as exc:
            logger.error("Failed to upsert match %s: %s", game.game_id, exc)


# ---------------------------------------------------------------------------
# Job nocturno
# ---------------------------------------------------------------------------

def nightly_ingest(supabase: Client) -> None:
    """
    Descarga Oracle's Elixir → calcula stats + puntos + precios para
    todas las partidas con status='pending_stats'.
    """
    year = datetime.utcnow().year
    oe = OraclesElixirClient()

    try:
        df = oe.download_lec_dataframe(year=year)
    except Exception as exc:
        logger.error("Failed to download Oracle's Elixir CSV: %s", exc)
        return
    finally:
        oe.close()

    pending_resp = (
        supabase.table("matches")
        .select("*")
        .eq("status", "pending_stats")
        .execute()
    )
    pending = pending_resp.data or []
    logger.info("Found %d pending_stats matches to process", len(pending))

    processed_count = 0

    for match in pending:
        riot_game_id = match.get("riot_platform_game_id") or ""
        match_id = match["id"]

        if not riot_game_id:
            logger.warning("Match %s has no riot_platform_game_id — skipping", match_id)
            continue

        stats_list = OraclesElixirClient().get_stats_for_game(df, riot_game_id)
        if not stats_list:
            logger.warning(
                "No Oracle's Elixir data yet for match %s (riot_id=%s) — will retry tonight",
                match_id,
                riot_game_id,
            )
            continue

        # Calcular y persistir stats de cada jugador
        players_updated: list[str] = []
        for stats in stats_list:
            player_id = _lookup_player(supabase, stats.playername)
            if not player_id:
                logger.warning("Player not found in DB: %s", stats.playername)
                continue

            match_points = calculate_match_points(
                stats=stats.model_dump(),
                role=stats.position,  # type: ignore[arg-type]
                game_duration_min=float(match.get("duration_min") or 0),
            )
            _upsert_player_match_stats(supabase, player_id, match_id, stats, match_points)
            players_updated.append(player_id)

        # Actualizar avg_points y precio para cada jugador de esta partida
        for player_id in players_updated:
            _update_avg_points(supabase, player_id)
            _update_price(supabase, player_id)

        # Marcar partida como terminada
        supabase.table("matches").update({"status": "finished"}).eq("id", match_id).execute()
        processed_count += 1
        logger.info("Finished processing match %s", match_id)

    logger.info("Nightly ingest complete. Processed %d / %d matches.", processed_count, len(pending))


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _lookup_player(supabase: Client, playername: str) -> str | None:
    """Devuelve el UUID del jugador en la tabla `players`, o None si no existe."""
    try:
        result = (
            supabase.table("players")
            .select("id")
            .eq("name", playername)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])
    except Exception as exc:
        logger.error("DB lookup failed for player %s: %s", playername, exc)
    return None


def _upsert_player_match_stats(
    supabase: Client,
    player_id: str,
    match_id: str,
    stats: PlayerStats,
    match_points: float,
) -> None:
    """Inserta o actualiza los stats del jugador para esta partida."""
    payload = {
        "player_id": player_id,
        "match_id": match_id,
        "champion": stats.champion,
        "kills": stats.kills,
        "deaths": stats.deaths,
        "assists": stats.assists,
        "cs_per_min": stats.cs_per_min,
        "gold_diff_15": stats.gold_diff_15,
        "damage_share": stats.damage_share,
        "vision_score": stats.vision_score,
        "objective_steals": stats.objective_steals,
        "result": stats.result,
        "match_points": match_points,
    }
    try:
        supabase.table("player_match_stats").upsert(
            payload,
            on_conflict="player_id,match_id",
        ).execute()
    except Exception as exc:
        logger.error(
            "Failed to upsert player_match_stats (player=%s, match=%s): %s",
            player_id,
            match_id,
            exc,
        )


def _update_avg_points(supabase: Client, player_id: str) -> None:
    """Recalcula avg_points como media de los últimos 5 partidos del jugador."""
    try:
        result = (
            supabase.table("player_match_stats")
            .select("match_points")
            .eq("player_id", player_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return
        avg = sum(r["match_points"] for r in rows) / len(rows)
        supabase.table("players").update({"avg_points": round(avg, 2)}).eq("id", player_id).execute()
    except Exception as exc:
        logger.error("Failed to update avg_points for player %s: %s", player_id, exc)


def _update_price(supabase: Client, player_id: str) -> None:
    """
    Actualiza current_price usando market.pricing y registra en price_history.
    Requiere que avg_points esté ya actualizado en la tabla players.
    """
    from market.pricing import calculate_new_price

    try:
        player_resp = (
            supabase.table("players")
            .select("current_price,avg_points,avg_points_baseline")
            .eq("id", player_id)
            .single()
            .execute()
        )
        player = player_resp.data
        if not player:
            return

        current_price: float = float(player.get("current_price") or 0)
        avg_points: float = float(player.get("avg_points") or 0)
        baseline_raw = player.get("avg_points_baseline")
        baseline: float | None = float(baseline_raw) if baseline_raw is not None else None

        if current_price <= 0:
            logger.warning("Player %s has no valid current_price — skipping price update", player_id)
            return

        # Calcular ownership global
        total_resp = (
            supabase.table("rosters")
            .select("id", count="exact")
            .execute()
        )
        total: int = total_resp.count or 0

        owned_resp = (
            supabase.table("roster_players")
            .select("id", count="exact")
            .eq("player_id", player_id)
            .execute()
        )
        owned: int = owned_resp.count or 0

        new_price, delta = calculate_new_price(
            current_price=current_price,
            recent_points=avg_points,
            baseline_avg_points=baseline,
            ownership_count=owned,
            total_rosters=total,
        )

        supabase.table("players").update({
            "current_price": new_price,
            "last_price_change_pct": delta,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("id", player_id).execute()

        # Registrar en historial de precios
        supabase.table("price_history").insert({
            "player_id": player_id,
            "price": new_price,
        }).execute()

        logger.debug("Updated price for player %s: %.2f → %.2f (delta=%.4f)", player_id, current_price, new_price, delta)

    except Exception as exc:
        logger.error("Failed to update price for player %s: %s", player_id, exc)

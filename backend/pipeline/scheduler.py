"""
Worker de pipeline de datos.

Jobs programados:
- keep_alive    (cada 14 min)   → ping /health para que Render no duerma el worker
- check_new_games (cada 30 min) → Leaguepedia → detectar partidas → marcar pending_stats
- nightly_job   (03:00 UTC)     → Oracle's Elixir → stats + scoring + precios
"""
import logging
import os

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase client compartido entre jobs
_supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

scheduler = BlockingScheduler()


# ---------------------------------------------------------------------------
# Job 1: Keep-alive (Render free tier)
# ---------------------------------------------------------------------------

@scheduler.scheduled_job("interval", minutes=14, id="keep_alive")
def keep_alive_ping() -> None:
    """Ping para evitar que Render duerma el free tier."""
    url = os.getenv("BACKEND_URL", "http://localhost:8000") + "/health"
    try:
        resp = httpx.get(url, timeout=10)
        logger.info("Keep-alive ping: %s", resp.status_code)
    except Exception as exc:
        logger.warning("Keep-alive ping failed: %s", exc)


# ---------------------------------------------------------------------------
# Job 2: Detectar partidas nuevas (Leaguepedia)
# ---------------------------------------------------------------------------

@scheduler.scheduled_job("interval", minutes=30, id="check_new_games")
def check_new_games() -> None:
    """Detecta partidas LEC terminadas → inserta como pending_stats."""
    from pipeline.leaguepedia import LeaguepediaClient
    from pipeline.ingest import mark_pending_games

    try:
        with LeaguepediaClient() as lp:
            # Override manual o auto-detección
            tournament = os.getenv("LEAGUEPEDIA_TOURNAMENT") or lp.get_active_tournament("LEC")
            since = _get_last_match_datetime(_supabase)
            games = lp.get_recent_games(tournament, since=since)

        new_games = [g for g in games if not _already_in_db(_supabase, g.game_id)]
        if new_games:
            mark_pending_games(new_games, _supabase)
            logger.info("Marked %d new games as pending_stats", len(new_games))
        else:
            logger.info("No new games detected (tournament=%s)", tournament)

    except Exception as exc:
        logger.error("check_new_games failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Job 3: Ingestión nocturna (Oracle's Elixir)
# ---------------------------------------------------------------------------

@scheduler.scheduled_job("cron", hour=3, minute=0, id="nightly_job")
def nightly_job() -> None:
    """Descarga Oracle's Elixir → stats + scoring + precios para partidas pending."""
    from pipeline.ingest import nightly_ingest

    try:
        nightly_ingest(_supabase)
    except Exception as exc:
        logger.error("nightly_job failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Job 4: Refresco diario del mercado (00:00 UTC)
# ---------------------------------------------------------------------------

@scheduler.scheduled_job("cron", hour=0, minute=0, id="market_refresh")
def market_refresh_job() -> None:
    """Refresca listings activos y genera sell_offers para todas las ligas."""
    from market.refresh import run_all_leagues_refresh

    try:
        run_all_leagues_refresh(_supabase)
    except Exception as exc:
        logger.error("market_refresh_job failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Job 5: Reset semanal de baseline de precios (martes 03:00 UTC)
# DESACTIVADO — reset_weekly_baseline ya no es necesario con la fórmula de
# eficiencia relativa (price-efficiency-formula). La fórmula nueva compara
# eficiencia entre jugadores, no contra el baseline histórico personal.
# La función permanece en price_updater.py para no romper imports.
# ---------------------------------------------------------------------------

# @scheduler.scheduled_job("cron", day_of_week="tue", hour=3, minute=0, id="weekly_baseline_reset")
# def weekly_baseline_reset_job() -> None:
#     """Resetea avg_points_baseline al promedio reciente tras terminar la jornada LEC."""
#     from market.price_updater import reset_weekly_baseline
#
#     try:
#         result = (
#             _supabase.table("players")
#             .select("id")
#             .eq("is_active", True)
#             .execute()
#         )
#         player_ids = [row["id"] for row in (result.data or [])]
#         if not player_ids:
#             logger.info("weekly_baseline_reset: no active players found, skipping")
#             return
#         reset_weekly_baseline(_supabase, player_ids)
#         logger.info("weekly_baseline_reset: reset %d players", len(player_ids))
#     except Exception as exc:
#         logger.error("weekly_baseline_reset_job failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_last_match_datetime(_supabase: Client):
    """Devuelve la fecha del último partido en DB, o None si no hay ninguno."""
    from datetime import datetime

    try:
        result = (
            _supabase.table("matches")
            .select("scheduled_at")
            .order("scheduled_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            raw = result.data[0]["scheduled_at"]
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as exc:
        logger.warning("Could not fetch last match datetime: %s", exc)
    return None


def _already_in_db(_supabase: Client, game_id: str) -> bool:
    """Comprueba si una partida ya existe en la tabla matches."""
    try:
        result = (
            _supabase.table("matches")
            .select("id")
            .eq("game_id", game_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as exc:
        logger.warning("Could not check game_id %s in DB: %s", game_id, exc)
        return False


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting pipeline scheduler...")
    scheduler.start()

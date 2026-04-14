from dotenv import load_dotenv
load_dotenv()

import logging
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import create_client, Client

from auth.dependencies import get_current_user, get_supabase

logger = logging.getLogger("summonersFantasy")
logging.basicConfig(level=logging.INFO)

_scheduler = BackgroundScheduler()


def _get_supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _job_market_refresh() -> None:
    from market.refresh import run_all_leagues_refresh
    try:
        run_all_leagues_refresh(_get_supabase())
        logger.info("Scheduled market refresh completed")
    except Exception as exc:
        logger.error("market_refresh failed: %s", exc, exc_info=True)


def _job_series_ingest() -> None:
    import asyncio
    from pipeline.series_ingest import run_series_ingest
    try:
        asyncio.run(run_series_ingest(_get_supabase()))
        logger.info("Series ingest completed")
    except Exception as exc:
        logger.error("series_ingest failed: %s", exc, exc_info=True)


def _job_check_split_reset() -> None:
    """Runs daily: check if today is the reset_date for any active split."""
    from admin.split_reset import run_split_reset_if_due
    try:
        run_split_reset_if_due(_get_supabase())
    except Exception as exc:
        logger.error("split_reset check failed: %s", exc, exc_info=True)


def _bootstrap_closes_at(supabase: Client) -> None:
    """Set closes_at on any active listings that have none (legacy data)."""
    from market.refresh import _LISTING_MINUTES
    closes_at = (datetime.now(timezone.utc) + timedelta(minutes=_LISTING_MINUTES)).isoformat()
    result = (
        supabase.table("market_listings")
        .update({"closes_at": closes_at})
        .eq("status", "active")
        .is_("closes_at", "null")
        .execute()
    )
    updated = len(result.data) if result.data else 0
    if updated:
        logger.info("Bootstrapped closes_at on %d active listings", updated)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from datetime import datetime, timedelta
    sb = _get_supabase()

    _scheduler.add_job(_job_market_refresh,   "interval", hours=1,  id="market_refresh",    replace_existing=True, next_run_time=datetime.now() + timedelta(hours=1))
    _scheduler.add_job(_job_series_ingest,    "interval", hours=1,  id="series_ingest",     replace_existing=True, next_run_time=datetime.now() + timedelta(hours=1))
    _scheduler.add_job(_job_check_split_reset,"cron",     hour=1,   minute=0, id="split_reset_check", replace_existing=True)
    _scheduler.start()
    logger.info("Background scheduler started")

    _bootstrap_closes_at(sb)

    yield

    _scheduler.shutdown(wait=False)
    logger.info("Background scheduler stopped")


from routers import players, leagues, market, scoring, trades, roster, activity, bids, teams as teams_router
from routers import splits as splits_router
from routers import series as series_router
from routers import match_detail as match_detail_router

app = FastAPI(title="Summoner's Fantasy API", version="0.1.0", lifespan=lifespan)

_raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    os.environ.get("FRONTEND_URL", "http://localhost:3000"),
)
CORS_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Production origins always allowed (regardless of env var)
_PRODUCTION_ORIGINS = [
    "https://summoners-fantasy.vercel.app",
    "https://summoners-fantasy.com",
    "https://www.summoners-fantasy.com",
]
for _origin in _PRODUCTION_ORIGINS:
    if _origin not in CORS_ORIGINS:
        CORS_ORIGINS.append(_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https://summoners-fantasy(-[a-z0-9-]+-jaimeneira9s-projects)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno: {type(exc).__name__}: {exc}"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
        },
    )


app.include_router(players.router,      prefix="/players",   tags=["players"])
app.include_router(leagues.router,      prefix="/leagues",   tags=["leagues"])
app.include_router(market.router,       prefix="/market",    tags=["market"])
app.include_router(scoring.router,      prefix="/scoring",   tags=["scoring"])
app.include_router(trades.router,       prefix="/trades",    tags=["trades"])
app.include_router(roster.router,       prefix="/roster",    tags=["roster"])
app.include_router(activity.router,     prefix="/activity",  tags=["activity"])
app.include_router(bids.router,         prefix="/bids",      tags=["bids"])
app.include_router(splits_router.router,prefix="/splits",    tags=["splits"])
app.include_router(teams_router.router,  prefix="/teams",     tags=["teams"])
app.include_router(series_router.router,       prefix="/series",    tags=["series"])
app.include_router(match_detail_router.router, prefix="/series",    tags=["match-detail"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


DEBUG_SECRET = os.environ.get("DEBUG_SECRET", "")


@app.post("/debug/series-ingest", tags=["debug"])
def debug_series_ingest(x_debug_secret: str = Header(default="")) -> dict:
    """Fuerza el pipeline de series desde gol.gg (sin auth, solo dev o con secret)."""
    env = os.environ.get("ENVIRONMENT", "development")
    if env == "production":
        if not DEBUG_SECRET or x_debug_secret != DEBUG_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")
    _job_series_ingest()
    return {"message": "Series ingest completado"}


@app.post("/debug/market-refresh", tags=["debug"])
def debug_market_refresh() -> dict:
    """Fuerza resolución de pujas y refresco del mercado (sin auth, solo dev).
    Solo activo cuando ENVIRONMENT=development."""
    if os.environ.get("ENVIRONMENT") != "development":
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=403, detail="Solo disponible en development")
    from market.refresh import run_all_leagues_refresh
    run_all_leagues_refresh(_get_supabase())
    return {"message": "Market refresh completado"}


@app.post("/admin/market-refresh", tags=["admin"])
async def trigger_market_refresh(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Fuerza un refresco del mercado inmediato (dev/admin)."""
    from market.refresh import run_all_leagues_refresh
    run_all_leagues_refresh(supabase)
    return {"message": "Market refresh completado"}


@app.post("/admin/split-reset", tags=["admin"])
async def trigger_split_reset(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Fuerza el reset de split manualmente (dev/admin)."""
    from admin.split_reset import run_split_reset_if_due
    run_split_reset_if_due(supabase, force=True)
    return {"message": "Split reset completado"}


@app.post("/admin/backfill-week-scoring", tags=["admin"])
def admin_backfill_week_scoring(
    week: int,
    x_debug_secret: str = Header(default=""),
) -> dict:
    """
    Backfills lineup snapshots and manager scoring for a given week.
    Reuses _take_lineup_snapshot_if_needed + _update_manager_total_points.
    Guard: refuses with 409 if any league_member already has total_points > 0.
    Auth: open in development, requires X-Debug-Secret header in production.
    """
    env = os.environ.get("ENVIRONMENT", "development")
    if env == "production":
        if not DEBUG_SECRET or x_debug_secret != DEBUG_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

    from pipeline.series_ingest import _update_manager_total_points

    supabase = _get_supabase()

    # 1. Fetch active competition
    comp_resp = (
        supabase.table("competitions")
        .select("id, name")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not comp_resp.data:
        raise HTTPException(status_code=404, detail="No active competition found")
    competition_id: str = str(comp_resp.data[0]["id"])

    # 2. Double-count guard
    guard_resp = (
        supabase.table("league_members")
        .select("id", count="exact")
        .gt("total_points", 0)
        .limit(1)
        .execute()
    )
    if guard_resp.data:
        raise HTTPException(
            status_code=409,
            detail="Some league members already have total_points > 0. Backfill refused to prevent double-counting.",
        )

    # 3. Score managers (absolute, idempotent)
    # Nota: snapshots son creados por el pipeline live, no por el backfill
    _update_manager_total_points(supabase, competition_id, week)

    return {
        "message": f"Backfill complete for week={week}",
        "competition_id": competition_id,
        "week": week,
    }


@app.post("/admin/pause-scheduler", tags=["admin"])
async def admin_pause_scheduler(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Pausa el job series_ingest del APScheduler."""
    try:
        _scheduler.pause_job("series_ingest")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to pause scheduler: {exc}")
    return {"status": "paused"}


@app.post("/admin/resume-scheduler", tags=["admin"])
async def admin_resume_scheduler(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Reanuda el job series_ingest del APScheduler."""
    try:
        _scheduler.resume_job("series_ingest")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resume scheduler: {exc}")
    return {"status": "resumed"}


@app.post("/admin/recalculate-scoring", tags=["admin"])
async def admin_recalculate_scoring(
    competition_id: str,
    week: int,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Recalcula total_points de forma absoluta e idempotente para la competition y week dadas."""
    from pipeline.series_ingest import _update_manager_total_points
    try:
        _update_manager_total_points(supabase, competition_id, week)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recalculation failed: {exc}")
    return {"status": "ok", "competition_id": competition_id, "week": week}

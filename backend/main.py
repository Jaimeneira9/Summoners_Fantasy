"""
Aplicación principal de Summoner's Fantasy — FastAPI.

Este módulo es el punto de entrada de la API REST. Combina tres responsabilidades:

  1. API REST: registra todos los routers (players, leagues, market, scoring, etc.)
     bajo sus prefijos correspondientes.

  2. Scheduler integrado: arranca un BackgroundScheduler (APScheduler) dentro del
     proceso FastAPI para ejecutar los jobs del pipeline activo (gol.gg) y del
     mercado. Jobs configurados:
       - series_ingest   (cada hora)   → pipeline gol.gg
       - market_refresh  (cada hora)   → refresco de listings y pujas
       - split_reset     (01:00 UTC)   → chequeo de reset de split

  3. Endpoints admin/debug: rutas que permiten forzar jobs manualmente
     (con protección por entorno o secret header en producción).

Cómo arranca (lifespan):
  FastAPI usa el context manager `lifespan` para inicialización y shutdown.
  Al iniciar: registra jobs en el scheduler, arranca el scheduler, y hace
  bootstrap de listings sin closes_at (datos legacy).
  Al parar: detiene el scheduler limpiamente.

CORS:
  Se permite el origen del frontend local (configurable via ALLOWED_ORIGINS o
  FRONTEND_URL) más los dominios de producción hardcodeados. También se acepta
  cualquier preview de Vercel via regex.
"""
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
    """
    Crea y devuelve un cliente Supabase con service_role key.

    Se usa service_role (no la anon key) para que el backend pueda leer y escribir
    sin restricciones de RLS. Cada job del scheduler crea su propia instancia para
    evitar problemas de estado compartido entre threads de APScheduler.
    """
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _job_market_refresh() -> None:
    """Wrapper del job de refresco de mercado para el scheduler."""
    from market.refresh import run_all_leagues_refresh
    try:
        run_all_leagues_refresh(_get_supabase())
        logger.info("Scheduled market refresh completed")
    except Exception as exc:
        logger.error("market_refresh failed: %s", exc, exc_info=True)


def _job_series_ingest() -> None:
    """
    Wrapper del job de ingestión de series para el scheduler.

    APScheduler ejecuta los jobs en threads síncronos, pero run_series_ingest()
    es una coroutine async. Se usa asyncio.run() para ejecutarla en un event loop
    nuevo, aislado del event loop principal de FastAPI (que no se puede compartir
    entre threads).
    """
    import asyncio
    from pipeline.series_ingest import run_series_ingest
    try:
        asyncio.run(run_series_ingest(_get_supabase()))
        logger.info("Series ingest completed")
    except Exception as exc:
        logger.error("series_ingest failed: %s", exc, exc_info=True)


def _job_check_split_reset() -> None:
    """
    Chequeo diario de reset de split. Corre a las 01:00 UTC.
    Si hoy es la reset_date configurada para algún split activo, ejecuta el reset.
    """
    from admin.split_reset import run_split_reset_if_due
    try:
        run_split_reset_if_due(_get_supabase())
    except Exception as exc:
        logger.error("split_reset check failed: %s", exc, exc_info=True)


def _bootstrap_closes_at(supabase: Client) -> None:
    """
    Migración de datos legacy: setea closes_at en listings activos que no lo tienen.

    Cuando se deployó el campo closes_at en market_listings, los listings
    existentes quedaron sin ese valor. Esta función los parchea al arrancar
    la app, asignándoles una fecha de cierre razonable (ahora + LISTING_MINUTES).

    Solo afecta registros con status='active' y closes_at NULL.
    """
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
    """
    Ciclo de vida de la aplicación FastAPI.

    Se ejecuta al iniciar y al apagar el servidor. APScheduler arranca en segundo
    plano (BackgroundScheduler) para no bloquear el event loop de asyncio.

    Los jobs se configuran con next_run_time=ahora+1h para que no corran
    inmediatamente al iniciar la app (evita conflictos en deploys y reinicios).
    """
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
from routers import competitions as competitions_router

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
    """
    Handler global de excepciones no capturadas.

    Sin esto, FastAPI devuelve 500 sin CORS headers cuando una ruta lanza una
    excepción no manejada, lo que hace que el frontend reciba un error de CORS
    en lugar del error real. Este handler agrega los headers necesarios.
    """
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
app.include_router(competitions_router.router, prefix="/competitions", tags=["competitions"])


@app.get("/health")
def health_check() -> dict[str, str]:
    """Endpoint de health check. Lo usan el scheduler keep_alive y los load balancers."""
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
    Recalcula puntos de managers para todas las semanas con snapshots.

    Útil para corregir totales después de un fix en el scoring engine o
    después de cargar datos de series que faltaban.

    Guard anti-double-count: rechaza con 409 si algún manager ya tiene
    total_points > 0 (indica que el scoring ya corrió previamente y el
    backfill podría acumular incorrectamente).

    Auth: abierto en development, requiere X-Debug-Secret en producción.
    """
    env = os.environ.get("ENVIRONMENT", "development")
    if env == "production":
        if not DEBUG_SECRET or x_debug_secret != DEBUG_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

    from pipeline.series_ingest import _update_manager_total_points

    supabase = _get_supabase()

    # 1. Fetch ALL active competitions
    comp_resp = (
        supabase.table("competitions")
        .select("id, name")
        .eq("is_active", True)
        .execute()
    )
    if not comp_resp.data:
        raise HTTPException(status_code=404, detail="No active competition found")

    # 2. Double-count guard (global: cualquier league_member con total_points > 0)
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

    # 3. Score managers para TODAS las competitions activas (absoluto, idempotente)
    # Nota: snapshots son creados por el pipeline live, no por el backfill
    processed = []
    for comp in comp_resp.data:
        competition_id: str = str(comp["id"])
        _update_manager_total_points(supabase, competition_id)
        processed.append(competition_id)

    return {
        "message": "Backfill complete (all snapped weeks)",
        "competitions_processed": processed,
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
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Recalcula total_points de forma absoluta e idempotente para todas las competitions."""
    from pipeline.series_ingest import _update_manager_total_points
    try:
        competitions_res = supabase.table("competitions").select("id").execute()
        competitions = competitions_res.data or []
        processed = []
        for comp in competitions:
            comp_id = comp["id"]
            _update_manager_total_points(supabase, comp_id)
            processed.append(comp_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recalculation failed: {exc}")
    return {"status": "ok", "competitions_processed": processed}

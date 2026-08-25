import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import alert_job
from app.config import get_settings
from app.database import init_db
from app.routers import atc, auth, flight, push, settings_router, traffic
from app.vatsim_client import vatsim_client
from app.vatspy_data import vatspy_boundaries

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vatsim.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await vatspy_boundaries.load()
    alert_task = None
    if settings.SERVERLESS:
        await vatsim_client.refresh(force=True)
    else:
        await vatsim_client.start()
        alert_task = asyncio.create_task(alert_job.run_forever())
    logger.info("ATC Watch Beta backend started (env=%s)", settings.ENV)
    try:
        yield
    finally:
        if alert_task:
            alert_task.cancel()
        if not settings.SERVERLESS:
            await vatsim_client.stop()


app = FastAPI(title="ATC Watch Beta API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(flight.router)
app.include_router(atc.router)
app.include_router(traffic.router)
app.include_router(push.router)
app.include_router(settings_router.router)


@app.get("/api/health")
async def health():
    snapshot = vatsim_client.snapshot
    return {
        "status": "ok",
        "vatsim_data_age_seconds": round(snapshot.age_seconds, 1) if snapshot.fetched_at else None,
        "vatsim_data_stale": snapshot.is_stale,
        "pilots_online": len(snapshot.pilots_by_cid),
        "controllers_online": len(snapshot.controllers),
    }


@app.get("/api/debug/state")
async def debug_state():
    """Developer/debug panel data source: last update time, and a coarse view
    of what the poller currently sees, for diagnosing ATC-alert behavior."""
    snapshot = vatsim_client.snapshot
    return {
        "last_vatsim_update": snapshot.fetched_at,
        "data_age_seconds": round(snapshot.age_seconds, 1) if snapshot.fetched_at else None,
        "data_stale": snapshot.is_stale,
        "pilots_online": len(snapshot.pilots_by_cid),
        "controllers_online": len(snapshot.controllers),
        "poll_interval_seconds": settings.VATSIM_POLL_INTERVAL_SECONDS,
    }


@app.get("/api/cron/alerts")
async def run_alert_cron(authorization: str | None = Header(default=None)):
    """Vercel Cron entry point.  Vercel supplies CRON_SECRET as a Bearer token."""
    expected = f"Bearer {settings.CRON_SECRET}"
    if not settings.CRON_SECRET or not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
    await vatsim_client.refresh(force=True)
    await alert_job._evaluate_all_users()
    return {"status": "ok"}

"""ME2 API — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.collector.sync_service import SyncService
from api.routers import alerts, auth, equipment, live, oee, production, reports
from api.services.oee_calculator import OEECalculator

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs on startup and shutdown."""
    logger.info("ME2 API starting up — version %s", app.version)

    # Start the SQLite -> PostgreSQL sync service as a background task
    sync_service = SyncService()
    sync_task = asyncio.create_task(sync_service.run_forever())
    logger.info("SyncService background task started")

    # Start OEE periodic calculator as a background task
    oee_calc = OEECalculator()
    oee_task = asyncio.create_task(oee_calc.run_periodic(interval_seconds=300))
    logger.info("OEE periodic calculator background task started")

    yield

    # Graceful shutdown of background tasks
    logger.info("ME2 API shutting down — stopping background services")
    sync_service.stop()
    sync_task.cancel()
    oee_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    try:
        await oee_task
    except asyncio.CancelledError:
        pass
    logger.info("ME2 API shut down complete")


app = FastAPI(
    title="ME2 API",
    version="1.0.0",
    description="Manufacturing Execution System for real-time OEE monitoring",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow all origins for POC
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(equipment.router)
app.include_router(oee.router)
app.include_router(production.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(live.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health() -> dict:
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Run with: python -m api.main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

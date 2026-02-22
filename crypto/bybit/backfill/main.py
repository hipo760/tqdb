"""Application entrypoint.

Starts the APScheduler and runs the FastAPI app via uvicorn.

Scheduler jobs:
  - minutely_job  : every minute (*/1)
  - daily_job     : daily at UTC 00:00
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from api import app
from jobs import daily_job, minutely_job

# ---------------------------------------------------------------------------
# Logging — structured, UTC timestamps, goes to stdout for Docker
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: attach the scheduler to the FastAPI app lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app):
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Every minute — patch last 2 minutes
    scheduler.add_job(
        minutely_job,
        CronTrigger(minute="*/1", timezone="UTC"),
        id="minutely_job",
        max_instances=1,
        coalesce=True,
    )

    # Daily at UTC 00:00 — patch last N days
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_job",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Scheduler started — minutely + daily jobs registered")

    yield  # application runs here

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))

    logger.info("Starting Bybit kline backfill service on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_config=None)

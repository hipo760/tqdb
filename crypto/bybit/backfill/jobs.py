"""Scheduled job implementations.

Two jobs:
  - minutely_job   runs every minute, patches last 2 minutes
  - daily_job      runs at UTC 00:00, patches last 3 days

Both use the same lock (_job_lock) so a slow daily run never overlaps
a minutely run.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta

from cassandra_client import get_session, get_table
from kline_sync import sync_symbol_smart, utc_now_truncated
from symbols import fetch_from_api, fetch_from_file

logger = logging.getLogger(__name__)

# A simple asyncio lock prevents overlapping runs.
_job_lock = asyncio.Lock()


def _symbol_source() -> str:
    return os.environ.get("SYMBOL_SOURCE", "api").lower()


async def _load_symbols() -> list[dict]:
    source = _symbol_source()
    if source == "file":
        symbols = await fetch_from_file()
    else:
        symbols = await fetch_from_api()

    if not symbols:
        logger.warning("No symbols loaded from source=%s", source)
    return symbols


async def minutely_job() -> None:
    """Patch the last 2 minutes for all symbols (runs every minute)."""
    if _job_lock.locked():
        logger.warning("minutely_job skipped — previous job still running")
        return

    async with _job_lock:
        logger.info("minutely_job starting")
        end_time = utc_now_truncated()
        start_time = end_time - timedelta(minutes=2)

        symbols = await _load_symbols()
        if not symbols:
            return

        try:
            session = get_session()
            table = get_table()
        except Exception:
            logger.exception("minutely_job — Cassandra connection failed")
            return

        tasks = [
            sync_symbol_smart(session, table, sym, start_time, end_time)
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok = sum(1 for r in results if not isinstance(r, Exception))
        err = len(results) - ok
        logger.info("minutely_job done — %d ok, %d errors", ok, err)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("minutely_job symbol[%d] error: %s", i, r)


async def daily_job() -> None:
    """Patch the last 3 days for all symbols (runs daily at UTC 00:00)."""
    if _job_lock.locked():
        logger.warning("daily_job skipped — previous job still running")
        return

    async with _job_lock:
        days = int(os.environ.get("DAILY_BACKFILL_DAYS", "3"))
        logger.info("daily_job starting — last %d days", days)

        end_time = utc_now_truncated()
        start_time = end_time - timedelta(days=days)

        symbols = await _load_symbols()
        if not symbols:
            return

        try:
            session = get_session()
            table = get_table()
        except Exception:
            logger.exception("daily_job — Cassandra connection failed")
            return

        tasks = [
            sync_symbol_smart(session, table, sym, start_time, end_time)
            for sym in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok = sum(1 for r in results if not isinstance(r, Exception))
        err = len(results) - ok
        logger.info("daily_job done — %d ok, %d errors", ok, err)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("daily_job symbol[%d] error: %s", i, r)

"""FastAPI application — manual sync trigger + health endpoints.

Endpoints:
    GET  /health                   liveness probe
    POST /sync/manual              trigger a smart patch over a custom time range
    POST /sync/symbol/{symbol}     trigger a smart patch for one symbol
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, field_validator

from cassandra_client import get_session, get_table
from kline_sync import sync_symbol_smart, sync_symbol_override, utc_now_truncated
from symbols import fetch_from_api, fetch_from_file
from jobs import minutely_job, daily_job

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bybit Kline Backfill API",
    description="Manual trigger for Bybit → Cassandra minbar sync",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    mode: Literal["smart", "override"] = "smart"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    days: Optional[int] = None  # shorthand: last N days

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_z_suffix(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    def resolve_window(self) -> tuple[datetime, datetime]:
        end = (self.end_time or utc_now_truncated()).replace(second=0, microsecond=0)
        if self.start_time:
            start = self.start_time.replace(second=0, microsecond=0)
        elif self.days:
            start = end - timedelta(days=self.days)
        else:
            start = end - timedelta(days=3)

        if start >= end:
            raise ValueError(f"start_time {start} must be earlier than end_time {end}")
        return start, end


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _all_symbols() -> list[dict]:
    symbols = await fetch_from_api()
    if not symbols:
        symbols = await fetch_from_file()
    return symbols


async def _run_sync(mode: str, symbols: list[dict], start_time: datetime, end_time: datetime) -> list[dict]:
    session = get_session()
    table = get_table()
    fn = sync_symbol_smart if mode == "smart" else sync_symbol_override
    tasks = [fn(session, table, sym, start_time, end_time) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for sym, r in zip(symbols, results):
        if isinstance(r, Exception):
            out.append({"symbol": sym["symbol"], "error": str(r)})
        else:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok"}


@app.post("/sync/manual", tags=["sync"])
async def manual_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    """Trigger a full sync for all symbols over the requested time window.

    Runs in the background — returns immediately with the resolved window.
    """
    try:
        start_time, end_time = req.resolve_window()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    async def _bg():
        symbols = await _all_symbols()
        if not symbols:
            logger.error("manual_sync: no symbols available")
            return
        results = await _run_sync(req.mode, symbols, start_time, end_time)
        ok = sum(1 for r in results if "error" not in r)
        logger.info("manual_sync done — %d ok, %d errors", ok, len(results) - ok)

    background_tasks.add_task(_bg)
    return {
        "accepted": True,
        "mode": req.mode,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


@app.post("/sync/symbol/{symbol}", tags=["sync"])
async def sync_one_symbol(symbol: str, req: SyncRequest, background_tasks: BackgroundTasks):
    """Trigger a sync for a single symbol by its DB name."""
    try:
        start_time, end_time = req.resolve_window()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    async def _bg():
        all_syms = await _all_symbols()
        matched = [s for s in all_syms if s["symbol"] == symbol]
        if not matched:
            logger.error("sync_one_symbol: symbol '%s' not found", symbol)
            return
        results = await _run_sync(req.mode, matched, start_time, end_time)
        logger.info("sync_one_symbol(%s) done: %s", symbol, results)

    background_tasks.add_task(_bg)
    return {
        "accepted": True,
        "symbol": symbol,
        "mode": req.mode,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


@app.post("/sync/minutely", tags=["sync", "ops"])
async def trigger_minutely(background_tasks: BackgroundTasks):
    """Manually fire the minutely job (last 2 minutes, all symbols)."""
    background_tasks.add_task(minutely_job)
    return {"accepted": True, "job": "minutely"}


@app.post("/sync/daily", tags=["sync", "ops"])
async def trigger_daily(background_tasks: BackgroundTasks):
    """Manually fire the daily job (last 3 days, all symbols)."""
    background_tasks.add_task(daily_job)
    return {"accepted": True, "job": "daily"}

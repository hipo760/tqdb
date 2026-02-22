"""Bybit kline fetching and Cassandra write helpers.

All pure data-logic — no scheduling, no API layer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from http_client import get_json, validate_bybit_payload

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def utc_now_truncated() -> datetime:
    """Current UTC time truncated to the minute."""
    now = datetime.now(timezone.utc)
    return now.replace(second=0, microsecond=0)


def split_into_chunks(
    start_time: datetime,
    end_time: datetime,
    chunk_minutes: int = 1000,
) -> list[tuple[datetime, datetime]]:
    """Split [start_time, end_time] into chunks of at most chunk_minutes."""
    chunks: list[tuple[datetime, datetime]] = []
    current = start_time
    while current <= end_time:
        chunk_end = min(current + timedelta(minutes=chunk_minutes - 1), end_time)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(minutes=1)
    return chunks


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def find_missing_minutes(
    existing: list[datetime],
    start_time: datetime,
    end_time: datetime,
) -> list[datetime]:
    existing_set = set(existing)
    missing: list[datetime] = []
    t = start_time
    while t <= end_time:
        if t not in existing_set:
            missing.append(t)
        t += timedelta(minutes=1)
    return missing


def group_into_blocks(
    missing_minutes: list[datetime],
) -> list[tuple[datetime, datetime]]:
    if not missing_minutes:
        return []
    blocks: list[tuple[datetime, datetime]] = []
    start = end = missing_minutes[0]
    for current in missing_minutes[1:]:
        if current == end + timedelta(minutes=1):
            end = current
        else:
            blocks.append((start, end))
            start = end = current
    blocks.append((start, end))
    return blocks


# ---------------------------------------------------------------------------
# Cassandra read
# ---------------------------------------------------------------------------

def fetch_existing_datetimes(
    session: Any,
    table: str,
    symbol: str,
    start_time: datetime,
    end_time: datetime,
) -> list[datetime]:
    query = f"""
        SELECT datetime FROM {table}
        WHERE symbol = %s AND datetime >= %s AND datetime <= %s
        ALLOW FILTERING
    """
    rows = session.execute(query, (symbol, start_time, end_time))
    return sorted(row.datetime.replace(tzinfo=timezone.utc) for row in rows)


# ---------------------------------------------------------------------------
# Bybit fetch
# ---------------------------------------------------------------------------

async def fetch_klines(
    client: httpx.AsyncClient,
    symbol_api_name: str,
    category: str,
    start_time: datetime,
    end_time: datetime,
    is_mark_price: bool = False,
) -> list[list]:
    url = (
        "https://api.bybit.com/v5/market/mark-price-kline"
        if is_mark_price
        else "https://api.bybit.com/v5/market/kline"
    )
    params = {
        "category": category,
        "symbol": symbol_api_name,
        "interval": 1,
        "start": int(start_time.timestamp() * 1000),
        "end": int(end_time.timestamp() * 1000),
        "limit": 1000,
    }
    data = await get_json(
        client,
        url,
        params=params,
        timeout=10,
        retries=3,
        backoff_factor=1.0,
        validate_json=validate_bybit_payload,
    )
    return data["result"]["list"]


# ---------------------------------------------------------------------------
# Cassandra write
# ---------------------------------------------------------------------------

def batch_insert_minbar(
    session: Any,
    table: str,
    symbol_db: str,
    bars: list[list],
    is_mark_price: bool = False,
    batch_size: int = 200,
) -> int:
    """Insert kline bars into Cassandra. Returns number of rows inserted."""
    from cassandra.query import BatchStatement  # type: ignore
    from cassandra import ConsistencyLevel  # type: ignore

    if not bars:
        return 0

    prepared = session.prepare(
        f"INSERT INTO {table} (symbol, datetime, open, high, low, close, vol) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )

    inserted = 0
    for i in range(0, len(bars), batch_size):
        batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_ONE)
        for bar in bars[i : i + batch_size]:
            ts_ms = int(bar[0])
            open_ = float(bar[1])
            high = float(bar[2])
            low = float(bar[3])
            close = float(bar[4])
            vol = 0.0 if is_mark_price else float(bar[5])

            # Bybit kline timestamp is the *start* of the bar;
            # store at bar-close time (start + 1 min) to match legacy behaviour.
            bar_close = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) + timedelta(minutes=1)

            batch.add(prepared, (symbol_db, bar_close, open_, high, low, close, vol))
            inserted += 1
        session.execute(batch)

    return inserted


# ---------------------------------------------------------------------------
# High-level sync strategies
# ---------------------------------------------------------------------------

async def sync_symbol_smart(
    session: Any,
    table: str,
    symbol_cfg: dict,
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """Fetch only missing minute-bars (gap-fill)."""
    symbol_db = symbol_cfg["symbol"]
    symbol_api = symbol_cfg["exchange_symbol"]
    is_mark_price = bool(symbol_cfg.get("is_mark_price", False))
    category = symbol_cfg["category"]

    existing = fetch_existing_datetimes(session, table, symbol_db, start_time, end_time)
    missing_minutes = find_missing_minutes(existing, start_time, end_time)
    blocks = group_into_blocks(missing_minutes)

    total_missing = len(missing_minutes)
    total_inserted = 0

    if not blocks:
        logger.info("smart | %s — no gaps found", symbol_db)
        return _summary(symbol_db, start_time, end_time, total_missing, total_inserted)

    async with httpx.AsyncClient() as client:
        logger.info("smart | %s — %d gap-block(s), %d missing min(s)", symbol_db, len(blocks), total_missing)
        for block_start, block_end in blocks:
            for sub_start, sub_end in split_into_chunks(block_start, block_end):
                try:
                    bars = await fetch_klines(
                        client, symbol_api, category,
                        sub_start - timedelta(minutes=1),
                        sub_end - timedelta(minutes=1),
                        is_mark_price,
                    )
                    total_inserted += batch_insert_minbar(session, table, symbol_db, bars, is_mark_price)
                    await asyncio.sleep(0.2)
                except Exception:
                    logger.exception("smart | %s failed block %s → %s", symbol_db, sub_start, sub_end)

    logger.info("smart | %s — inserted %d rows", symbol_db, total_inserted)
    return _summary(symbol_db, start_time, end_time, total_missing, total_inserted)


async def sync_symbol_override(
    session: Any,
    table: str,
    symbol_cfg: dict,
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """Overwrite the full range regardless of what already exists."""
    symbol_db = symbol_cfg["symbol"]
    symbol_api = symbol_cfg["exchange_symbol"]
    is_mark_price = bool(symbol_cfg.get("is_mark_price", False))
    category = symbol_cfg["category"]

    total_inserted = 0

    async with httpx.AsyncClient() as client:
        chunks = split_into_chunks(start_time, end_time)
        logger.info("override | %s — %d chunk(s)", symbol_db, len(chunks))
        for chunk_start, chunk_end in chunks:
            try:
                bars = await fetch_klines(
                    client, symbol_api, category,
                    chunk_start - timedelta(minutes=1),
                    chunk_end - timedelta(minutes=1),
                    is_mark_price,
                )
                total_inserted += batch_insert_minbar(session, table, symbol_db, bars, is_mark_price)
                await asyncio.sleep(0.2)
            except Exception:
                logger.exception("override | %s failed chunk %s → %s", symbol_db, chunk_start, chunk_end)

    logger.info("override | %s — inserted %d rows", symbol_db, total_inserted)
    return _summary(symbol_db, start_time, end_time, None, total_inserted)


def _summary(symbol_db, start_time, end_time, missing, inserted) -> dict:
    return {
        "symbol": symbol_db,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "missing": missing,
        "inserted": inserted,
    }

import os
import json
import time
import csv
import asyncio

from typing import List, Dict

import httpx
import argparse
from datetime import datetime, timedelta, timezone

from http_client import get_json, validate_bybit_payload


def _import_cassandra():
    """Import cassandra-driver lazily.

    This keeps `python backfill.py --help` working in environments where the
    cassandra driver can't load.
    """
    from cassandra.cluster import Cluster, BatchStatement  # type: ignore
    from cassandra.auth import PlainTextAuthProvider  # type: ignore
    from cassandra import ConsistencyLevel  # type: ignore

    return Cluster, BatchStatement, PlainTextAuthProvider, ConsistencyLevel


# ---------- Load Config ----------
def load_config(path="config.json"):
    with open(path, "r") as f:
        config = json.load(f)
    default_days = config.get("default_days", 3)
    cassandra_cfg = config["cassandra"]
    # symbols = config["symbols"]
    symbol_api_url = config["symbol_api_url"]

    # Optional auth token for the symbol API.
    # If provided, we send: Authorization: Bearer <token>
    symbol_api_token = config.get("symbol_api_token", "")

    return default_days, cassandra_cfg, symbol_api_url, symbol_api_token


# ---------- Utilities ----------
def split_into_chunks(start_time, end_time, chunk_minutes=1000):
    chunks = []
    current_start = start_time
    while current_start <= end_time:
        current_end = min(current_start + timedelta(minutes=chunk_minutes - 1), end_time)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(minutes=1)
    return chunks


async def retry_request(client, url, params, max_retries=3, backoff_factor=1):
    """Backward-compatible shim.

    Kept to minimize churn. Prefer using `get_json(..., validate_json=validate_bybit_payload)`.
    """

    return await get_json(
        client,
        url,
        params=params,
        timeout=10,
        retries=max_retries,
        backoff_factor=backoff_factor,
        validate_json=validate_bybit_payload,
    )


# ---------- Connect to Cassandra ----------
def get_cassandra_session(cassandra_cfg):
    Cluster, _, PlainTextAuthProvider, _ = _import_cassandra()
    if cassandra_cfg["user"] and cassandra_cfg["password"]:
        auth_provider = PlainTextAuthProvider(cassandra_cfg["user"], cassandra_cfg["password"])
        cluster = Cluster([cassandra_cfg["host"]], port=cassandra_cfg["port"], auth_provider=auth_provider)
    else:
        cluster = Cluster([cassandra_cfg["host"]], port=cassandra_cfg["port"])
    session = cluster.connect()
    session.set_keyspace(cassandra_cfg["keyspace"])
    return session


# ---------- Fetch existing datetimes ----------
def fetch_datetimes(session, table, symbol, start_time, end_time):
    query = f"""
        SELECT datetime FROM {table}
        WHERE symbol = %s AND datetime >= %s AND datetime <= %s ALLOW FILTERING
    """
    rows = session.execute(query, (symbol, start_time, end_time))
    datetimes = sorted([row.datetime.replace(tzinfo=timezone.utc) for row in rows])
    return datetimes


# ---------- Find missing minutes ----------
def find_missing_ranges(datetimes, start_time, end_time):
    missing = []
    expected_time = start_time
    datetimes_set = set(datetimes)

    while expected_time <= end_time:
        if expected_time not in datetimes_set:
            missing.append(expected_time)
        expected_time += timedelta(minutes=1)

    return missing


# ---------- Group missing into blocks ----------
def group_missing_into_blocks(missing_minutes):
    if not missing_minutes:
        return []

    blocks = []
    start = missing_minutes[0]
    end = missing_minutes[0]

    for current in missing_minutes[1:]:
        if current == end + timedelta(minutes=1):
            end = current
        else:
            blocks.append((start, end))
            start = current
            end = current

    blocks.append((start, end))
    return blocks


# ---------- Fetch kline data ----------
async def fetch_bybit_kline(client, symbol_api_name, category, start_time, end_time, is_mark_price=False):
    if is_mark_price:
        url = "https://api.bybit.com/v5/market/mark-price-kline"
    else:
        url = "https://api.bybit.com/v5/market/kline"

    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    params = {
        "category": category,
        "symbol": symbol_api_name,
        "interval": 1,
        "start": start_ms,
        "end": end_ms,
        "limit": 1000
    }
    data = await retry_request(client, url, params)
    return data["result"]["list"]


# ---------- Batch insert into Cassandra ----------
def batch_insert_minbar(session, table, symbol_db_name, bars, is_mark_price=False, batch_size=200):
    _, BatchStatement, _, ConsistencyLevel = _import_cassandra()
    prepared = session.prepare(f"""
        INSERT INTO {table} (symbol, datetime, open, high, low, close, vol)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """)

    for i in range(0, len(bars), batch_size):
        batch = BatchStatement(consistency_level=ConsistencyLevel.LOCAL_ONE)
        sub_bars = bars[i:i + batch_size]

        for bar in sub_bars:
            start_time_ms = int(bar[0])
            open_ = float(bar[1])
            high = float(bar[2])
            low = float(bar[3])
            close = float(bar[4])

            if is_mark_price:
                vol = 0.0  # No volume available
            else:
                vol = float(bar[5])

            start_time = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)
            record_time = start_time + timedelta(minutes=1)

            batch.add(prepared, (symbol_db_name, record_time, open_, high, low, close, vol))

        session.execute(batch)


# ---------- Save Summary CSV ----------
def save_summary_to_csv(summary_list, base_filename="summary"):
    now = datetime.now(timezone.utc)
    year_month = now.strftime("%Y-%m")  # e.g., '2025-04'
    filename = f"{base_filename}_{year_month}.csv"  # e.g., 'summary_2025-04.csv'

    file_exists = os.path.exists(filename)

    with open(filename, mode="a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["date_utc", "start_time", "end_time", "symbol", "missing_minutes", "backfilled_records"])

        for row in summary_list:
            writer.writerow([
                now.date(),
                row["start_time"],
                row["end_time"],
                row["symbol"],
                row.get("missing", "-"),
                row["backfilled"]
            ])

    print(f"Summary appended to '{filename}'")


# ---------- Smart Backfill ----------
async def process_symbol_smart(session, table, symbol_config, start_time, end_time):
    symbol_db = symbol_config["symbol"]
    symbol_api = symbol_config["exchange_symbol"]
    is_mark_price = symbol_config.get("is_mark_price", False)
    category = symbol_config["category"]

    datetimes = fetch_datetimes(session, table, symbol_db, start_time, end_time)
    missing_minutes = find_missing_ranges(datetimes, start_time, end_time)
    missing_blocks = group_missing_into_blocks(missing_minutes)

    total_missing = len(missing_minutes)
    total_backfilled = 0

    if not missing_blocks:
        print(f"No missing data for symbol '{symbol_db}'.")
        return {"symbol": symbol_db, "start_time": start_time, "end_time": end_time, "missing": total_missing,
                "backfilled": total_backfilled}

    async with httpx.AsyncClient() as client:
        total_blocks = len(missing_blocks)
        print(f"Backfilling {symbol_db}: {total_blocks} blocks")
        for idx, (block_start, block_end) in enumerate(missing_blocks, 1):
            print(f"  [{idx}/{total_blocks}] Processing block {block_start} to {block_end}")
            sub_blocks = split_into_chunks(block_start, block_end)

            for sub_start, sub_end in sub_blocks:
                try:
                    klines = await fetch_bybit_kline(client, symbol_api, category, sub_start - timedelta(minutes=1),
                                                     sub_end - timedelta(minutes=1), is_mark_price)
                    batch_insert_minbar(session, table, symbol_db, klines, is_mark_price)
                    total_backfilled += len(klines)

                    await asyncio.sleep(0.2)
                except Exception as e:
                    print(f"Failed to backfill {sub_start} to {sub_end}: {e}")

    return {"symbol": symbol_db, "start_time": start_time, "end_time": end_time, "missing": total_missing,
            "backfilled": total_backfilled}


# ---------- Override Backfill ----------
async def process_symbol_override(session, table, symbol_config, start_time, end_time):
    symbol_db = symbol_config["symbol"]
    symbol_api = symbol_config["exchange_symbol"]
    is_mark_price = symbol_config.get("is_mark_price", False)
    category = symbol_config["category"]

    # symbol_db = symbol_config["gta_symbol"]
    # category = symbol_config["category"]
    # symbol_api = symbol_config["symbol"]
    # is_mark_price = symbol_config.get("is_mark_price", False)

    total_backfilled = 0

    async with httpx.AsyncClient() as client:
        full_blocks = split_into_chunks(start_time, end_time)
        total_blocks = len(full_blocks)
        print(f"Backfilling {symbol_db}: {total_blocks} blocks")

        for idx, (block_start, block_end) in enumerate(full_blocks, 1):
            print(f"  [{idx}/{total_blocks}] Processing block {block_start} to {block_end}")
            try:
                klines = await fetch_bybit_kline(client, symbol_api, category, block_start - timedelta(minutes=1),
                                                 block_end - timedelta(minutes=1), is_mark_price)
                batch_insert_minbar(session, table, symbol_db, klines, is_mark_price)
                total_backfilled += len(klines)
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Failed to backfill {block_start} to {block_end}: {e}")

    return {"symbol": symbol_db, "start_time": start_time, "end_time": end_time, "backfilled": total_backfilled}


async def fetch_symbols_from_api(
    url: str,
    *,
    token: str = "",
    retries: int = 5,
    timeout_sec: int = 5,
) -> List[Dict]:
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            data = await get_json(
                client,
                url,
                headers=headers,
                timeout=timeout_sec,
                retries=retries,
                backoff_factor=1,
            )

        for item in data:
            item["is_mark_price"] = bool(item.get("is_mark_price", 0))
            margin_type = item.get("margin_type", "").upper()
            item["category"] = (
                "linear" if margin_type == "USDT"
                else "inverse" if margin_type == "COIN"
                else margin_type  # fallback if unknown
            )

        return data
    except Exception:
        return []


async def fetch_symbols_from_file() -> List[Dict]:
    try:
        with open("symbols.json", "r") as f:
            symbols = json.load(f)
            for item in symbols:
                item["is_mark_price"] = bool(item.get("is_mark_price", 0))
                margin_type = item.get("margin_type", "").upper()
                item["category"] = (
                    "linear" if margin_type == "USDT"
                    else "inverse" if margin_type == "COIN"
                    else margin_type  # fallback if unknown
                )
            return symbols
    except Exception:
        pass
    return []


# ---------- Main ----------
async def main():
    parser = argparse.ArgumentParser(description="Backfill Bybit MinBars into Cassandra")
    parser.add_argument("--mode", choices=["smart", "override"], default="smart",
                        help="Mode: smart (default) or override")
    parser.add_argument("--start-time", type=str, default=None,
                        help="Custom start time in ISO format, e.g., 2025-04-01T00:00:00Z")
    parser.add_argument("--default-days", type=int, default=None,
                        help="Override default_days from config.json if no --start-time")
    parser.add_argument("--source", choices=["file", "api"],  default="file",
                        help="The source of the symbols to back filling, choose 'file' or 'api'")
    args = parser.parse_args()

    default_days, cassandra_cfg, symbol_api_url, symbol_api_token = load_config()

    symbols = []

    if args.source == "file":
        symbols = await fetch_symbols_from_file()
    elif args.source == "api":
        symbols = await fetch_symbols_from_api(
            symbol_api_url,
            token=symbol_api_token,
            retries=5,
            timeout_sec=5,
        )
    print(f"Fetched {len(symbols)} symbols from {args.source}.")
    for symbol in symbols:
        print(f"{symbol}")


    now = datetime.now(timezone.utc)
    end_time = now.replace(second=0, microsecond=0)

    if args.start_time:
        try:
            start_time = datetime.fromisoformat(args.start_time.replace("Z", "+00:00"))
            start_time = start_time.replace(second=0, microsecond=0)
        except Exception:
            print(f"Invalid --start-time format: {args.start_time}")
            print("Please use ISO8601 format like 2025-04-01T00:00:00Z")
            return
    elif args.default_days is not None:
        start_time = end_time - timedelta(days=args.default_days)
    else:
        start_time = end_time - timedelta(days=default_days)

    if start_time >= end_time:
        print(f"Start time {start_time} must be earlier than end time {end_time}!")
        return

    print(f"Backfill Start Time: {start_time}")
    print(f"Backfill End Time:   {end_time}")

    session = get_cassandra_session(cassandra_cfg)
    table = cassandra_cfg["table"]

    start_exec = time.time()

    if args.mode == "override":
        tasks = [process_symbol_override(session, table, symbol_cfg, start_time, end_time) for symbol_cfg in symbols]
    else:
        tasks = [process_symbol_smart(session, table, symbol_cfg, start_time, end_time) for symbol_cfg in symbols]

    summary = await asyncio.gather(*tasks)

    save_summary_to_csv(summary)

    elapsed = time.time() - start_exec
    print(f"\n=== Completed {args.mode} backfill in {elapsed:.2f} seconds ===")
    print("Summary saved to 'summary.csv'.")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Continuous symbols built on External Instrument API + read-time bar composition.

Holiday and rollover schedule logic is delegated to two external API endpoints:
  - GET /intra/instrument/continuous_futures     -> symbol list and symbol_root metadata
  - GET /intra/instrument/contract_rollover_dt   -> exact per-symbol switch points

Configure via environment variables (set in docker-compose.yml):
  INSTRUMENT_API_BASE_URL   Base URL of the Instrument API, e.g. https://host
  INSTRUMENT_API_TOKEN      Bearer token for the Authorization header

Price adjustment:
  Close-to-close, cumulative backward adjustment.
  For each switch point the lookback reference is (switch_utc - 30 min).
  diff = close(new_contract, lookback) - close(old_contract, lookback)
  Older segments are cumulatively shifted by the sum of downstream diffs.
  If either close price is unavailable the diff for that pair is treated as 0.

DT-session filtering:
  DT symbols (TXDT, NQDT, ESDT, YMDT, HSIDT) only include bars within the
  exchange day-session window. ON symbols include all bars.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# TAIFEX month codes: Jan=A ... Dec=L
MONTH_CODES = "ABCDEFGHIJKL"
# Standard futures month codes: Jan=F, Feb=G, Mar=H, Apr=J, May=K, Jun=M,
#                                Jul=N, Aug=Q, Sep=U, Oct=V, Nov=X, Dec=Z
FUTURES_MONTH_CODES = "FGHJKMNQUVXZ"

# symbol_roots that use the TAIFEX (A-L) month code system
TAIFEX_ROOTS: frozenset[str] = frozenset({"TX", "TXF"})

UTC_TZ = timezone.utc
TW_TZ = timezone(timedelta(hours=8))    # Taiwan Time / Hong Kong Time (UTC+8)
HK_TZ = TW_TZ
try:
    CHICAGO_TZ = ZoneInfo("America/Chicago")
except Exception:
    CHICAGO_TZ = timezone(timedelta(hours=-6))  # fixed fallback if zoneinfo missing

# Minutes before switch_utc to look up close prices for price adjustment
_PRICE_ADJUST_LOOKBACK_MIN = 30

_FAR_FUTURE = datetime(9999, 12, 31, 23, 59, 59)

# DT-session filter: bars outside this local-time window are excluded for DT symbols.
# ON symbols and any unlisted symbol: all bars included.
_DT_SESSION_CONFIG: dict[str, tuple[time, time, object]] = {
    "TXDT":  (time(8, 45),  time(13, 45), TW_TZ),
    "NQDT":  (time(8, 30),  time(15, 15), CHICAGO_TZ),
    "ESDT":  (time(8, 30),  time(15, 15), CHICAGO_TZ),
    "YMDT":  (time(8, 30),  time(15, 15), CHICAGO_TZ),
    "HSIDT": (time(9, 15),  time(16, 30), HK_TZ),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Segment:
    tc_symbol: str
    start_utc: datetime
    end_utc: datetime


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _contract_month_to_tqdb_symbol(symbol_root: str, contract_month: str) -> str:
    """Build a TQDB contract symbol from symbol_root and YYYYMM string.

    Examples:
        ('TX',  '202604') -> 'TXD6'
        ('TXF', '202604') -> 'TXFD6'
        ('NQ',  '202606') -> 'NQM6'
        ('HSI', '202606') -> 'HSIM6'
    """
    year = int(contract_month[:4])
    month = int(contract_month[4:6])
    root = symbol_root.upper()
    if root in TAIFEX_ROOTS:
        return f"{root}{MONTH_CODES[month - 1]}{year % 10}"
    return f"{root}{FUTURES_MONTH_CODES[month - 1]}{year % 10}"


def _rollover_entry_to_utc(
    rollover_date: str | None,
    rollover_time: str,
    timezone_offset: int,
) -> datetime | None:
    """Convert API rollover_date (YYYY-MM-DD), rollover_time (HH:mm), and integer
    UTC offset to a UTC-naive datetime.  Returns None when rollover_date is null/empty.
    """
    if not rollover_date:
        return None
    local_str = f"{rollover_date} {rollover_time}:00"
    try:
        local_dt = datetime.strptime(local_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    tz = timezone(timedelta(hours=timezone_offset))
    return local_dt.replace(tzinfo=tz).astimezone(UTC_TZ).replace(tzinfo=None)


def _is_dt_session_bar(symbol: str, dt_utc_naive: datetime) -> bool:
    """Return True if the bar timestamp falls within the DT session for symbol.
    Symbols not in _DT_SESSION_CONFIG (ON symbols, unknown) always return True.
    """
    cfg = _DT_SESSION_CONFIG.get(normalize_symbol(symbol))
    if cfg is None:
        return True
    session_begin, session_end, local_tz = cfg
    local_t = dt_utc_naive.replace(tzinfo=UTC_TZ).astimezone(local_tz).time()
    return session_begin <= local_t <= session_end


# ---------------------------------------------------------------------------
# Instrument API client
# ---------------------------------------------------------------------------

def _instrument_api_config() -> tuple[str, str]:
    base_url = os.environ.get("INSTRUMENT_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("INSTRUMENT_API_TOKEN", "")
    return base_url, token


def _api_get(path: str, params: dict[str, str] | None = None) -> list | dict:
    base_url, token = _instrument_api_config()
    if not base_url:
        raise RuntimeError("INSTRUMENT_API_BASE_URL environment variable is not set")
    url = f"{base_url}{path}"
    if params:
        url += "?" + urlencode(params)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(
            f"Instrument API HTTP {exc.code} for {path}: {exc.reason}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"Instrument API unreachable ({path}): {exc.reason}"
        ) from exc


def fetch_continuous_futures(symbol: str | None = None) -> list[dict]:
    """GET /intra/instrument/continuous_futures.

    Optionally filter by exact symbol name.  Returns a list of rows.
    """
    params: dict[str, str] = {}
    if symbol:
        params["symbol"] = symbol
    result = _api_get("/intra/instrument/continuous_futures", params or None)
    return result if isinstance(result, list) else []


def fetch_contract_rollover_dt(symbol: str) -> list[dict]:
    """GET /intra/instrument/contract_rollover_dt?symbol=<symbol>.

    Returns the rollover schedule entries for the given continuous symbol.
    """
    result = _api_get("/intra/instrument/contract_rollover_dt", {"symbol": symbol})
    return result if isinstance(result, list) else []


def is_continuous_symbol(symbol: str) -> bool:
    """Return True if symbol is registered as a continuous future in the Instrument API."""
    sym = normalize_symbol(symbol)
    try:
        rows = fetch_continuous_futures(symbol=sym)
        return bool(rows)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Rollover schedule builders
# ---------------------------------------------------------------------------

def _build_rollover_schedule(
    symbol_root: str,
    rollover_entries: list[dict],
) -> list[tuple[datetime, str]]:
    """Convert raw API rollover entries to a sorted list of (switch_utc, tqdb_symbol).

    Each entry represents the moment a contract becomes active.
    Entries with null/unparseable rollover_date are skipped.
    """
    entries: list[tuple[datetime, str]] = []
    for row in rollover_entries:
        utc = _rollover_entry_to_utc(
            row.get("rollover_date"),
            row.get("rollover_time", "00:00"),
            int(row.get("timezone", 0)),
        )
        if utc is None:
            continue
        tqdb_sym = _contract_month_to_tqdb_symbol(symbol_root, str(row["contract"]))
        entries.append((utc, tqdb_sym))
    entries.sort(key=lambda x: x[0])
    return entries


def _schedule_to_raw_segments(
    entries: list[tuple[datetime, str]],
) -> list[tuple[datetime, datetime, str]]:
    """Convert sorted (switch_utc, tqdb_symbol) entries to (start, end, symbol) triples.

    Segment i spans [entries[i].utc, entries[i+1].utc - 1 min].
    The last segment spans [entries[-1].utc, _FAR_FUTURE].
    """
    raw: list[tuple[datetime, datetime, str]] = []
    for i, (seg_start, sym) in enumerate(entries):
        seg_end = (
            entries[i + 1][0] - timedelta(minutes=1)
            if i + 1 < len(entries)
            else _FAR_FUTURE
        )
        raw.append((seg_start, seg_end, sym))
    return raw


# ---------------------------------------------------------------------------
# Cassandra query helpers
# ---------------------------------------------------------------------------

def _query_minbar_rows(
    session,
    keyspace: str,
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime,
):
    query = (
        f"SELECT datetime, open, high, low, close, vol FROM {keyspace}.minbar "
        "WHERE symbol = %s AND datetime >= %s AND datetime <= %s ORDER BY datetime"
    )
    return session.execute(query, [symbol, begin_dt, end_dt], timeout=None)


def _query_last_close_at_or_before(
    session,
    keyspace: str,
    symbol: str,
    max_dt: datetime,
) -> float | None:
    """Return the close price of the last bar for symbol with datetime <= max_dt.

    Returns None when no bar is found or the value cannot be converted to float.
    """
    query = (
        f"SELECT close FROM {keyspace}.minbar "
        "WHERE symbol = %s AND datetime <= %s ORDER BY datetime DESC LIMIT 1"
    )
    row = session.execute(query, [symbol, max_dt], timeout=60).one()
    if row is None:
        return None
    try:
        return float(row.close)
    except (TypeError, ValueError):
        return None


def _query_bound(
    session,
    keyspace: str,
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime,
    order: str,
) -> datetime | None:
    query = (
        f"SELECT datetime FROM {keyspace}.minbar "
        "WHERE symbol = %s AND datetime >= %s AND datetime <= %s "
        f"ORDER BY datetime {order} LIMIT 1"
    )
    try:
        row = session.execute(query, [symbol, begin_dt, end_dt], timeout=60).one()
        return row.datetime if row else None
    except Exception as exc:
        print(f"Warning: query_bound failed for {symbol}: {exc}", file=sys.stderr)
        return None


def _cassandra_symbol_has_data(session, keyspace: str, symbol: str) -> bool:
    """Return True if the minbar table has at least one row for symbol."""
    query = f"SELECT datetime FROM {keyspace}.minbar WHERE symbol = %s LIMIT 1"
    row = session.execute(query, [symbol], timeout=30).one()
    return row is not None


# ---------------------------------------------------------------------------
# Price adjustment
# ---------------------------------------------------------------------------

def _compute_switch_diffs(
    session,
    keyspace: str,
    raw_segments: list[tuple[datetime, datetime, str]],
) -> list[float | None]:
    """Compute close-to-close diff at the lookback point for each consecutive segment pair.

    lookback_utc = switch_utc - _PRICE_ADJUST_LOOKBACK_MIN minutes
    diff[i] = close(segment[i+1].symbol, lookback) - close(segment[i].symbol, lookback)

    Returns None for a pair when either close price is unavailable (treated as 0
    in the cumulative offset computation).
    """
    diffs: list[float | None] = [None] * len(raw_segments)
    now_utc = datetime.utcnow()
    for i in range(len(raw_segments) - 1):
        # switch_utc is the start of the next segment
        switch_utc = raw_segments[i + 1][0]
        # Skip future switch points — the rollover hasn't happened yet so any
        # "close" we'd find is just today's price, not the actual rollover diff.
        if switch_utc > now_utc:
            continue
        lookback = switch_utc - timedelta(minutes=_PRICE_ADJUST_LOOKBACK_MIN)
        before_sym = raw_segments[i][2]
        after_sym = raw_segments[i + 1][2]
        before_close = _query_last_close_at_or_before(session, keyspace, before_sym, lookback)
        after_close = _query_last_close_at_or_before(session, keyspace, after_sym, lookback)
        if before_close is not None and after_close is not None:
            diffs[i] = after_close - before_close
    return diffs


def _cumulative_offsets(diffs: list[float | None]) -> list[float]:
    """Build cumulative backward price offsets from per-pair diffs.

    offset[N-1] = 0     (newest segment is the reference; no adjustment)
    offset[i]   = offset[i+1] + (diffs[i] if not None else 0)

    Adding offset[i] to all OHLC values of segment i makes them continuous
    with the newest segment's price level.
    """
    n = len(diffs)
    offsets = [0.0] * n
    running = 0.0
    for i in range(n - 2, -1, -1):
        if diffs[i] is not None:
            running += diffs[i]
        offsets[i] = running
    return offsets


# ---------------------------------------------------------------------------
# Public: compose_continuous_minbars
# ---------------------------------------------------------------------------

def compose_continuous_minbars(
    session,
    keyspace: str,
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime,
) -> list[tuple[datetime, object, object, object, object, object]]:
    """Compose backward-adjusted minute bars for a continuous symbol.

    Steps:
    1. Fetch symbol_root from /intra/instrument/continuous_futures.
    2. Fetch rollover schedule from /intra/instrument/contract_rollover_dt.
    3. Build all raw segments from the full schedule.
    4. Compute per-pair diffs (close-to-close at switch_utc - 30 min) and
       cumulative backward offsets for ALL segments.
    5. Query Cassandra bars for segments overlapping [begin_dt, end_dt],
       apply DT-session filtering, apply price offsets.
    6. Return sorted, deduplicated bar list.
    """
    sym = normalize_symbol(symbol)

    # 1. Resolve symbol_root from API
    cf_rows = fetch_continuous_futures(symbol=sym)
    if not cf_rows:
        return []
    symbol_root = cf_rows[0]["symbol_root"]

    # 2. Fetch rollover schedule
    rollover_entries = fetch_contract_rollover_dt(symbol=sym)
    if not rollover_entries:
        return []
    schedule = _build_rollover_schedule(symbol_root, rollover_entries)
    if not schedule:
        return []

    # 3. Build all raw segments (unclipped; needed for complete offset calculation)
    raw_segments = _schedule_to_raw_segments(schedule)

    # 4. Compute diffs and cumulative offsets across ALL segments
    diffs = _compute_switch_diffs(session, keyspace, raw_segments)
    offsets = _cumulative_offsets(diffs)

    # 5. Query bars for segments overlapping [begin_dt, end_dt] and apply offsets
    bars: list[tuple[datetime, object, object, object, object, object]] = []
    for i, (seg_start, seg_end, tqdb_sym) in enumerate(raw_segments):
        query_begin = max(seg_start, begin_dt)
        query_end = min(seg_end, end_dt)
        if query_begin > query_end:
            continue

        rows = list(_query_minbar_rows(session, keyspace, tqdb_sym, query_begin, query_end))
        if not rows:
            continue

        shift = offsets[i]
        for row in rows:
            if not _is_dt_session_bar(sym, row.datetime):
                continue
            if shift:
                bars.append((
                    row.datetime,
                    row.open + shift,
                    row.high + shift,
                    row.low + shift,
                    row.close + shift,
                    getattr(row, "vol", 0),
                ))
            else:
                bars.append((
                    row.datetime,
                    row.open,
                    row.high,
                    row.low,
                    row.close,
                    getattr(row, "vol", 0),
                ))

    # 6. Sort and deduplicate on timestamp
    bars.sort(key=lambda item: item[0])
    unique_bars: list[tuple[datetime, object, object, object, object, object]] = []
    seen: set[datetime] = set()
    for bar in bars:
        if bar[0] not in seen:
            unique_bars.append(bar)
            seen.add(bar[0])

    return unique_bars


# ---------------------------------------------------------------------------
# Public: discover_contract_switch_points
# ---------------------------------------------------------------------------

def discover_contract_switch_points(
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime,
) -> list[dict[str, str]]:
    """Return contract switch rows within [begin_dt, end_dt] for a continuous symbol.

    Each row contains:
      switch_utc     UTC datetime string of the switch point
      before_symbol  TQDB contract symbol of the expiring contract
      after_symbol   TQDB contract symbol of the incoming contract
    """
    sym = normalize_symbol(symbol)
    cf_rows = fetch_continuous_futures(symbol=sym)
    if not cf_rows:
        raise ValueError(f"Symbol not found in Instrument API: {sym}")
    symbol_root = cf_rows[0]["symbol_root"]

    rollover_entries = fetch_contract_rollover_dt(symbol=sym)
    schedule = _build_rollover_schedule(symbol_root, rollover_entries)
    if not schedule:
        return []

    raw_segments = _schedule_to_raw_segments(schedule)
    points: list[dict[str, str]] = []
    for i in range(1, len(raw_segments)):
        switch_utc = raw_segments[i][0]
        if begin_dt <= switch_utc <= end_dt:
            points.append({
                "switch_utc": switch_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "before_symbol": raw_segments[i - 1][2],
                "after_symbol": raw_segments[i][2],
            })
    return points


# ---------------------------------------------------------------------------
# Public: discover_continuous_bounds
# ---------------------------------------------------------------------------

def discover_continuous_bounds(
    session,
    keyspace: str,
    symbol: str,
) -> dict:
    """Return the earliest and latest bar datetime found in Cassandra for symbol.

    Iterates all contract segments from the rollover schedule, queries the
    actual data bounds in Cassandra for each contract, and returns the overall
    min/max timestamps.
    """
    sym = normalize_symbol(symbol)
    cf_rows = fetch_continuous_futures(symbol=sym)
    if not cf_rows:
        return {"symbol": sym, "start": None, "end": None,
                "note": "Not found in Instrument API"}

    symbol_root = cf_rows[0]["symbol_root"]
    rollover_entries = fetch_contract_rollover_dt(symbol=sym)
    schedule = _build_rollover_schedule(symbol_root, rollover_entries)
    if not schedule:
        return {"symbol": sym, "start": None, "end": None,
                "note": "No rollover schedule from API"}

    raw_segments = _schedule_to_raw_segments(schedule)
    now = datetime.utcnow()
    earliest: datetime | None = None
    latest: datetime | None = None

    for seg_start, seg_end, tqdb_sym in raw_segments:
        cap_end = min(seg_end, now)
        if seg_start > cap_end:
            continue
        first_dt = _query_bound(session, keyspace, tqdb_sym, seg_start, cap_end, "ASC")
        last_dt = _query_bound(session, keyspace, tqdb_sym, seg_start, cap_end, "DESC")
        if first_dt is not None and (earliest is None or first_dt < earliest):
            earliest = first_dt
        if last_dt is not None and (latest is None or last_dt > latest):
            latest = last_dt

    return {
        "symbol": sym,
        "start": earliest.strftime("%Y-%m-%d %H:%M:%S") if earliest else None,
        "end": latest.strftime("%Y-%m-%d %H:%M:%S") if latest else None,
    }


# ---------------------------------------------------------------------------
# Public: list_continuous_futures_with_availability
# ---------------------------------------------------------------------------

def list_continuous_futures_with_availability(session, keyspace: str) -> list[dict]:
    """List all continuous futures from the API with per-contract Cassandra availability.

    Returns one entry per continuous symbol:
      {
        "symbol":      "TXON",
        "symbol_root": "TX",
        "contracts": [
          {"contract_month": "202604", "tqdb_symbol": "TXD6", "has_data": true},
          ...
        ]
      }
    """
    cf_rows = fetch_continuous_futures()
    result: list[dict] = []

    for cf_row in cf_rows:
        sym = cf_row.get("symbol", "")
        symbol_root = cf_row.get("symbol_root", "")
        rollover_entries = fetch_contract_rollover_dt(symbol=sym)

        contracts_info: list[dict] = []
        for entry in rollover_entries:
            cm = str(entry.get("contract", ""))
            if not cm:
                continue
            tqdb_sym = _contract_month_to_tqdb_symbol(symbol_root, cm)
            has_data = _cassandra_symbol_has_data(session, keyspace, tqdb_sym)
            contracts_info.append({
                "contract_month": cm,
                "tqdb_symbol": tqdb_sym,
                "has_data": has_data,
            })

        result.append({
            "symbol": sym,
            "symbol_root": symbol_root,
            "contracts": contracts_info,
        })

    return result

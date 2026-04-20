#!/usr/bin/env python3
"""Continuous symbols (TXDT/TXON plus CME DT/ON symbols) built on read-time composition.

This module keeps schedule logic in one place so endpoints can:
- compose minute bars for continuous symbols at query time (view-like behavior)
- report available range for UI pages
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


CONTINUOUS_SYMBOLS = {"TXDT", "TXON", "NQDT", "NQON", "ESDT", "ESON", "YMDT", "YMON"}
TAIFEX_SYMBOLS = {"TXDT", "TXON"}
CME_DT_SYMBOLS = {"NQDT", "ESDT", "YMDT"}
CME_ON_SYMBOLS = {"NQON", "ESON", "YMON"}
CME_SYMBOLS = CME_DT_SYMBOLS | CME_ON_SYMBOLS
MONTH_CODES = "ABCDEFGHIJKL"
FUTURES_MONTH_CODES = "FGHJKMNQUVXZ"
TXF_PREFIX = "TXF"
CME_PRODUCT_CODES = {"NQ": "NQ", "ES": "ES", "YM": "YM"}


def _contract_month_to_taifex_symbol(contract_month: str) -> str:
    """Convert YYYYMM to TXF symbol, e.g. '202605' -> 'TXFE6'."""
    year = int(contract_month[:4])
    month = int(contract_month[4:6])
    return f"{TXF_PREFIX}{MONTH_CODES[month - 1]}{year % 10}"


def _continuous_to_cme_product(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized in CME_SYMBOLS:
        return normalized[:2]
    raise ValueError(f"Unsupported CME continuous symbol: {symbol}")


def _contract_month_to_cme_symbol(product: str, contract_month: str) -> str:
    """Convert YYYYMM to CME futures symbol, e.g. ('NQ','202606') -> 'NQM6'."""
    product = product.upper()
    if product not in CME_PRODUCT_CODES:
        raise ValueError(f"Unsupported CME product: {product}")
    year = int(contract_month[:4])
    month = int(contract_month[4:6])
    return f"{CME_PRODUCT_CODES[product]}{FUTURES_MONTH_CODES[month - 1]}{year % 10}"


def _family_for_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized in TAIFEX_SYMBOLS:
        return "TAIFEX"
    if normalized in CME_SYMBOLS:
        return "CME"
    raise ValueError(f"Unsupported continuous symbol: {symbol}")


YMD_RE = re.compile(r"^(\d{8})$")
TW_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc
try:
    CHICAGO_TZ = ZoneInfo("America/Chicago")
except Exception:
    CHICAGO_TZ = timezone(timedelta(hours=-6))

TXDT_SESSION_BEGIN = time(8, 45)
TXDT_SESSION_END = time(13, 45)
CME_DT_SESSION_BEGIN = time(8, 30)
CME_DT_SESSION_END = time(15, 15)
_CME_LAST_TRADE_CACHE: dict[str, dict[str, date]] = {}


@dataclass(frozen=True)
class Segment:
    tc_symbol: str
    start_utc: datetime
    end_utc: datetime


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def is_continuous_symbol(symbol: str) -> bool:
    return normalize_symbol(symbol) in CONTINUOUS_SYMBOLS


def _parse_yyyymmdd(text: str) -> date | None:
    if not YMD_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_date_flexible(text: str) -> date | None:
    value = text.strip()
    if not value:
        return None

    parsed = _parse_yyyymmdd(value)
    if parsed is not None:
        return parsed

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_cme_last_trade_csv_path(product: str) -> Path:
    product = product.upper()
    env_path = os.environ.get(f"CME_{product}_LAST_TRADE_CSV")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    candidates = [
        Path(__file__).resolve().parents[1] / "data" / "CME" / f"{product}_last_trade_datetime.csv",
        Path(__file__).resolve().parents[2] / "web" / "data" / "CME" / f"{product}_last_trade_datetime.csv",
        Path(f"/opt/tqdb/web/data/CME/{product}_last_trade_datetime.csv"),
        Path(f"/var/www/data/CME/{product}_last_trade_datetime.csv"),
        Path(f"/tqdb/tqdb_cassandra/web/data/CME/{product}_last_trade_datetime.csv"),
        Path(f"./web/data/CME/{product}_last_trade_datetime.csv"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"CME {product} last-trade CSV not found. Searched: {', '.join(str(c) for c in candidates)}. "
        f"Set CME_{product}_LAST_TRADE_CSV env var or ensure file exists."
    )


def _parse_datetime_text_flexible(text: str) -> datetime | None:
    value = (text or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _load_cme_last_trade_dates(product: str) -> dict[str, date]:
    product = product.upper()
    if product in _CME_LAST_TRADE_CACHE:
        return _CME_LAST_TRADE_CACHE[product]

    csv_path = _resolve_cme_last_trade_csv_path(product)
    rows = csv_path.read_text(encoding="utf-8").splitlines()
    out: dict[str, date] = {}

    for line in rows:
        row = line.strip()
        if not row or row.startswith("#"):
            continue

        parts = [part.strip() for part in row.split(",")]
        if len(parts) < 2:
            continue
        if parts[0].lower() == "symbol":
            continue

        sym = parts[0].upper()
        dt = _parse_datetime_text_flexible(parts[1])
        if not sym or dt is None:
            continue
        out[sym] = dt.date()

    _CME_LAST_TRADE_CACHE[product] = out
    return out


def _resolve_holiday_csv_path(symbol: str | None = None) -> Path:
    family = _family_for_symbol(symbol or "TXDT")

    if family == "CME":
        env_path = os.environ.get("CME_HOLIDAY_CSV")
        if env_path:
            candidate = Path(env_path)
            if candidate.exists():
                return candidate

        candidates = [
            Path(__file__).resolve().parents[2] / "feature-custom-symbol" / "CME" / "cme_holidays_sample.csv",
            Path("/opt/tqdb/feature-custom-symbol/CME/cme_holidays_sample.csv"),
            Path("/tqdb/feature-custom-symbol/CME/cme_holidays_sample.csv"),
            Path("./feature-custom-symbol/CME/cme_holidays_sample.csv"),
            Path("../../../feature-custom-symbol/CME/cme_holidays_sample.csv"),
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"CME holiday CSV not found. Searched: {', '.join(str(c) for c in candidates)}. "
            f"Set CME_HOLIDAY_CSV env var or ensure file exists."
        )

    env_path = os.environ.get("TAIFEX_HOLIDAY_CSV")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    candidates = [
        Path(__file__).resolve().parents[2] / "feature-custom-symbol" / "TAIFEX" / "taifex_holidays_sample.csv",
        Path("/opt/tqdb/feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv"),
        Path("/tqdb/feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv"),
        Path("./feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv"),
        Path("../../../feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"TAIFEX holiday CSV not found. Searched: {', '.join(str(c) for c in candidates)}. "
        f"Set TAIFEX_HOLIDAY_CSV env var or ensure file exists."
    )


def load_holiday_dates(symbol: str | None = None) -> set[date]:
    csv_path = _resolve_holiday_csv_path(symbol)
    content = csv_path.read_text(encoding="utf-8").splitlines()

    holiday_dates: set[date] = set()
    for line in content:
        row = line.strip()
        if not row or row.startswith("#"):
            continue

        parts = [part.strip() for part in row.split(",")]
        for part in parts:
            parsed = _parse_date_flexible(part)
            if parsed is not None:
                holiday_dates.add(parsed)
                break

    return holiday_dates


def _third_weekday_of_month(year: int, month: int, weekday: int) -> date:
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + 14)


def _adjust_to_next_trading_day(candidate: date, holidays: set[date]) -> date:
    day = candidate
    while day.weekday() >= 5 or day in holidays:
        day += timedelta(days=1)
    return day


def _adjust_to_prev_trading_day(candidate: date, holidays: set[date]) -> date:
    day = candidate
    while day.weekday() >= 5 or day in holidays:
        day -= timedelta(days=1)
    return day


def _estimate_last_trading_day(symbol: str, contract_month: str, holidays: set[date]) -> date:
    family = _family_for_symbol(symbol)
    year = int(contract_month[:4])
    month = int(contract_month[4:6])
    if family == "TAIFEX":
        third_wed = _third_weekday_of_month(year, month, 2)
        return _adjust_to_next_trading_day(third_wed, holidays)

    # CME products: prefer configured exchange last-trade date from CSV.
    product = _continuous_to_cme_product(symbol)
    cme_symbol = _contract_month_to_cme_symbol(product, contract_month)
    last_trade_map = _load_cme_last_trade_dates(product)
    if cme_symbol in last_trade_map:
        return last_trade_map[cme_symbol]

    # Fallback when CSV entry is missing.
    third_fri = _third_weekday_of_month(year, month, 4)
    fallback = _adjust_to_prev_trading_day(third_fri, holidays)
    print(
        f"Warning: Missing last-trade date for {cme_symbol} in CME CSV, using fallback={fallback}",
        file=sys.stderr,
    )
    return fallback


def _switch_day_for_symbol(symbol: str, last_trading_day: date) -> date:
    symbol = normalize_symbol(symbol)
    if symbol in CME_DT_SYMBOLS:
        return last_trading_day - timedelta(days=2)
    return last_trading_day


def _contract_months_for_range(symbol: str, begin_dt: datetime, end_dt: datetime) -> Iterable[str]:
    family = _family_for_symbol(symbol)
    start_year = begin_dt.year - 1
    end_year = end_dt.year + 1

    for year in range(start_year, end_year + 1):
        months = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
        if family == "CME":
            months = (3, 6, 9, 12)
        for month in months:
            yield f"{year}{month:02d}"


def _utc_naive_from_local(day: date, hhmm: str, tzinfo) -> datetime:
    hour = int(hhmm[:2])
    minute = int(hhmm[2:])
    local_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tzinfo)
    utc_dt = local_dt.astimezone(UTC_TZ)
    return utc_dt.replace(tzinfo=None)


def _build_segments(symbol: str, begin_dt: datetime, end_dt: datetime, holidays: set[date]) -> list[Segment]:
    symbol = normalize_symbol(symbol)
    if symbol not in CONTINUOUS_SYMBOLS:
        return []

    if symbol == "TXDT":
        start_hhmm = "0845"
        end_hhmm = "0845"
        end_offset_min = -1
        local_tz = TW_TZ
    elif symbol == "TXON":
        start_hhmm = "1346"
        end_hhmm = "1345"
        end_offset_min = 0
        local_tz = TW_TZ
    elif symbol in CME_DT_SYMBOLS:
        start_hhmm = "0830"
        end_hhmm = "0830"
        end_offset_min = -1
        local_tz = CHICAGO_TZ
    elif symbol in CME_ON_SYMBOLS:
        start_hhmm = "1516"
        end_hhmm = "1515"
        end_offset_min = 0
        local_tz = CHICAGO_TZ
    else:
        return []

    contracts: list[tuple[str, date]] = []
    for contract_month in _contract_months_for_range(symbol, begin_dt, end_dt):
        contracts.append((contract_month, _estimate_last_trading_day(symbol, contract_month, holidays)))

    contracts.sort(key=lambda item: item[0])

    segments: list[Segment] = []
    window_start = date(begin_dt.year - 1, 1, 1)

    for idx, (contract_month, last_trading_day) in enumerate(contracts):
        prev_last_trading_day = contracts[idx - 1][1] if idx > 0 else window_start
        prev_switch_day = _switch_day_for_symbol(symbol, prev_last_trading_day)
        curr_switch_day = _switch_day_for_symbol(symbol, last_trading_day)

        seg_start = _utc_naive_from_local(prev_switch_day, start_hhmm, local_tz)
        seg_end = _utc_naive_from_local(curr_switch_day, end_hhmm, local_tz)
        if end_offset_min:
            seg_end = seg_end + timedelta(minutes=end_offset_min)

        if symbol in TAIFEX_SYMBOLS:
            mapped_symbol = _contract_month_to_taifex_symbol(contract_month)
        else:
            mapped_symbol = _contract_month_to_cme_symbol(_continuous_to_cme_product(symbol), contract_month)

        if seg_end < begin_dt or seg_start > end_dt:
            continue

        segments.append(
            Segment(
                tc_symbol=mapped_symbol,
                start_utc=seg_start,
                end_utc=seg_end,
            )
        )

    return segments


def _query_minbar_rows(session, keyspace: str, symbol: str, begin_dt: datetime, end_dt: datetime):
    query = (
        f"SELECT datetime, open, high, low, close, vol FROM {keyspace}.minbar "
        "WHERE symbol = %s AND datetime >= %s AND datetime <= %s ORDER BY datetime"
    )
    return session.execute(query, [symbol, begin_dt, end_dt], timeout=None)


def _is_dt_session_bar(symbol: str, dt_utc_naive: datetime) -> bool:
    """True if UTC-naive bar datetime is inside DT session for target symbol."""
    symbol = normalize_symbol(symbol)
    if symbol == "TXDT":
        dt_local = dt_utc_naive.replace(tzinfo=UTC_TZ).astimezone(TW_TZ)
        local_t = dt_local.timetz().replace(tzinfo=None)
        return TXDT_SESSION_BEGIN <= local_t <= TXDT_SESSION_END

    if symbol in CME_DT_SYMBOLS:
        dt_local = dt_utc_naive.replace(tzinfo=UTC_TZ).astimezone(CHICAGO_TZ)
        local_t = dt_local.timetz().replace(tzinfo=None)
        return CME_DT_SESSION_BEGIN <= local_t <= CME_DT_SESSION_END

    return True


def _shift_price(v: object, shift: object) -> object:
    if not shift:
        return v
    return v + shift


def compose_continuous_minbars(
    session,
    keyspace: str,
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime,
    holidays: set[date],
) -> list[tuple[datetime, object, object, object, object, object]]:
    segments = _build_segments(symbol, begin_dt, end_dt, holidays)

    segment_bars: list[list[tuple[datetime, object, object, object, object, object]]] = []
    for seg in segments:
        query_begin = max(begin_dt, seg.start_utc)
        query_end = min(end_dt, seg.end_utc)
        if query_begin > query_end:
            segment_bars.append([])
            continue

        seg_rows: list[tuple[datetime, object, object, object, object, object]] = []
        rows = _query_minbar_rows(session, keyspace, seg.tc_symbol, query_begin, query_end)
        for row in rows:
            if symbol in (TAIFEX_SYMBOLS | CME_DT_SYMBOLS) and not _is_dt_session_bar(symbol, row.datetime):
                continue
            seg_rows.append((row.datetime, row.open, row.high, row.low, row.close, getattr(row, "vol", 0)))
        segment_bars.append(seg_rows)

    # Backward-adjust each older segment so switch-point price gaps are aligned to newer segments.
    offsets: list[object] = [0] * len(segment_bars)
    next_with_data_idx: int | None = None

    for idx in range(len(segment_bars) - 1, -1, -1):
        rows = segment_bars[idx]
        if not rows:
            continue

        if next_with_data_idx is None:
            offsets[idx] = 0
            next_with_data_idx = idx
            continue

        prev_last_close = rows[-1][4]
        next_first_open = segment_bars[next_with_data_idx][0][1]
        offsets[idx] = offsets[next_with_data_idx] + (next_first_open - prev_last_close)
        next_with_data_idx = idx

    bars: list[tuple[datetime, object, object, object, object, object]] = []
    for idx, rows in enumerate(segment_bars):
        shift = offsets[idx]
        for row in rows:
            if shift:
                bars.append(
                    (
                        row[0],
                        _shift_price(row[1], shift),
                        _shift_price(row[2], shift),
                        _shift_price(row[3], shift),
                        _shift_price(row[4], shift),
                        row[5],
                    )
                )
            else:
                bars.append(row)

    bars.sort(key=lambda item: item[0])

    # Overlap is unlikely, but dedupe on timestamp keeps output deterministic.
    unique_bars: list[tuple[datetime, object, object, object, object, object]] = []
    seen_dt: set[datetime] = set()
    for bar in bars:
        if bar[0] in seen_dt:
            continue
        unique_bars.append(bar)
        seen_dt.add(bar[0])

    return unique_bars


def _query_bound(session, keyspace: str, symbol: str, begin_dt: datetime, end_dt: datetime, order: str):
    try:
        query = (
            f"SELECT datetime FROM {keyspace}.minbar "
            "WHERE symbol = %s AND datetime >= %s AND datetime <= %s "
            f"ORDER BY datetime {order} LIMIT 1"
        )
        row = session.execute(query, [symbol, begin_dt, end_dt], timeout=60).one()
        return row.datetime if row else None
    except Exception as exc:
        raise RuntimeError(f"Query failed for symbol {symbol}: {exc}")


def discover_continuous_bounds(
    session,
    keyspace: str,
    symbol: str,
    holidays: set[date],
    today: date | None = None,
) -> dict[str, str | None]:
    symbol = normalize_symbol(symbol)
    if symbol not in CONTINUOUS_SYMBOLS:
        raise ValueError(f"Unsupported continuous symbol: {symbol}")

    if today is None:
        today = date.today()

    # Keep same range policy as schedule logic: Y-1..Y.
    probe_begin = datetime(today.year - 1, 1, 1, 0, 0, 0)
    probe_end = datetime(today.year, 12, 31, 23, 59, 59)

    try:
        segments = _build_segments(symbol, probe_begin, probe_end, holidays)
    except Exception as exc:
        raise RuntimeError(f"Failed to build segments for {symbol}: {exc}")

    if not segments:
        return {
            "symbol": symbol,
            "start": None,
            "end": None,
            "note": "No segments found",
        }

    earliest: datetime | None = None
    latest: datetime | None = None

    for seg in segments:
        seg_begin = max(seg.start_utc, probe_begin)
        seg_end = min(seg.end_utc, probe_end)
        if seg_begin > seg_end:
            continue

        try:
            first_dt = _query_bound(session, keyspace, seg.tc_symbol, seg_begin, seg_end, "ASC")
            last_dt = _query_bound(session, keyspace, seg.tc_symbol, seg_begin, seg_end, "DESC")

            if first_dt is not None and (earliest is None or first_dt < earliest):
                earliest = first_dt
            if last_dt is not None and (latest is None or last_dt > latest):
                latest = last_dt
        except Exception as exc:
            # Log but continue checking other segments
            import sys
            print(f"Warning: Failed to query segment {seg.tc_symbol}: {exc}", file=sys.stderr)

    return {
        "symbol": symbol,
        "start": earliest.strftime("%Y-%m-%d %H:%M:%S") if earliest else None,
        "end": latest.strftime("%Y-%m-%d %H:%M:%S") if latest else None,
    }


def discover_contract_switch_points(
    symbol: str,
    holidays: set[date],
    begin_dt: datetime,
    end_dt: datetime,
) -> list[dict[str, str]]:
    """Return contract switch rows in UTC for continuous symbols within [begin_dt, end_dt]."""
    symbol = normalize_symbol(symbol)
    if symbol not in CONTINUOUS_SYMBOLS:
        raise ValueError(f"Unsupported continuous symbol: {symbol}")

    if symbol == "TXDT":
        switch_hhmm = "0845"
        local_tz = TW_TZ
    elif symbol == "TXON":
        switch_hhmm = "1346"
        local_tz = TW_TZ
    elif symbol in CME_DT_SYMBOLS:
        switch_hhmm = "0830"
        local_tz = CHICAGO_TZ
    elif symbol in CME_ON_SYMBOLS:
        switch_hhmm = "1516"
        local_tz = CHICAGO_TZ
    else:
        raise ValueError(f"Unsupported continuous symbol: {symbol}")

    # Add year buffers to ensure adjacent contract switch points are available.
    scan_begin = datetime(begin_dt.year - 1, 1, 1, 0, 0, 0)
    scan_end = datetime(end_dt.year + 1, 12, 31, 23, 59, 59)

    contracts: list[tuple[str, date]] = []
    for contract_month in _contract_months_for_range(symbol, scan_begin, scan_end):
        contracts.append((contract_month, _estimate_last_trading_day(symbol, contract_month, holidays)))

    contracts.sort(key=lambda item: item[0])

    points: list[dict[str, str]] = []
    for idx in range(1, len(contracts)):
        prev_contract_month = contracts[idx - 1][0]
        prev_last_trading_day = contracts[idx - 1][1]
        next_contract_month = contracts[idx][0]
        switch_day = _switch_day_for_symbol(symbol, prev_last_trading_day)
        switch_dt = _utc_naive_from_local(switch_day, switch_hhmm, local_tz)
        if begin_dt <= switch_dt <= end_dt:
            if symbol in TAIFEX_SYMBOLS:
                before_symbol = _contract_month_to_taifex_symbol(prev_contract_month)
                after_symbol = _contract_month_to_taifex_symbol(next_contract_month)
            else:
                product = _continuous_to_cme_product(symbol)
                before_symbol = _contract_month_to_cme_symbol(product, prev_contract_month)
                after_symbol = _contract_month_to_cme_symbol(product, next_contract_month)

            points.append(
                {
                    "switch_utc": switch_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "before_symbol": before_symbol,
                    "after_symbol": after_symbol,
                }
            )

    return points

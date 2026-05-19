#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Return continuous contract switch rows for TXDT/TXON, CME DT/ON, and HKEX DT symbols.

Query params:
- symbol: TXDT, TXON, NQDT, NQON, ESDT, ESON, YMDT, YMON, or HSIDT
- BEG: UTC datetime (YYYY-MM-DD HH:MM:SS)
- END: UTC datetime (YYYY-MM-DD HH:MM:SS)
"""

import json
import os
import sys
from datetime import datetime
from urllib.parse import unquote

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

from continuous_symbols import (
    _rollover_close_to_utc,
    _rollover_entry_to_utc,
    discover_contract_switch_points,
    fetch_continuous_futures,
    fetch_contract_rollover_dt,
    is_continuous_symbol,
    normalize_symbol,
)


def send_json(payload, status_code=200):
    sys.stdout.write(f"Status: {status_code}\r\n")
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.flush()


def parse_params():
    import os

    query_string = os.environ.get("QUERY_STRING", "")
    params = {}
    for item in query_string.split("&"):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        params[k] = unquote(v)
    return params


def parse_utc_text(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _to_json_number(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def enrich_switch_points_with_gap(session, keyspace, points, close_dt_by_switch):
    """Enrich switch points with close-to-close diff at the market close time on rollover day.

    close_dt_by_switch maps switch_utc string -> UTC datetime of market close derived
    from the continuous_futures close_time + timezone fields, matching the price
    adjustment reference used in compose_continuous_minbars.
    """
    now_utc = datetime.utcnow()
    q_close = (
        f"SELECT datetime, close FROM {{keyspace}}.minbar "
        "WHERE symbol = %s AND datetime <= %s ORDER BY datetime DESC LIMIT 1"
    )

    for row in points:
        close_dt = close_dt_by_switch.get(row["switch_utc"])
        row["close_utc"] = close_dt.strftime("%Y-%m-%d %H:%M:%S") if close_dt else None

        # Close time unknown or market hasn't closed yet — no price data.
        if close_dt is None or close_dt > now_utc:
            row["before_close"] = None
            row["before_close_utc"] = None
            row["after_close"] = None
            row["after_close_utc"] = None
            row["diff"] = None
            continue

        before_symbol = row["before_symbol"]
        after_symbol = row["after_symbol"]

        q = q_close.format(keyspace=keyspace)
        before_row = session.execute(q, [before_symbol, close_dt], timeout=60).one()
        after_row = session.execute(q, [after_symbol, close_dt], timeout=60).one()

        before_close = before_row.close if before_row else None
        after_close = after_row.close if after_row else None
        diff = (
            (after_close - before_close)
            if (before_close is not None and after_close is not None)
            else None
        )

        row["before_close"] = _to_json_number(before_close)
        row["before_close_utc"] = before_row.datetime.strftime("%Y-%m-%d %H:%M:%S") if before_row else None
        row["after_close"] = _to_json_number(after_close)
        row["after_close_utc"] = after_row.datetime.strftime("%Y-%m-%d %H:%M:%S") if after_row else None
        row["diff"] = _to_json_number(diff)


def main():
    cluster = None
    try:
        params = parse_params()
        symbol = normalize_symbol(params.get("symbol", ""))
        beg_text = params.get("BEG", "")
        end_text = params.get("END", "")

        if not is_continuous_symbol(symbol):
            send_json({"status": "failed", "error": "symbol must be TXDT, TXON, NQDT, NQON, ESDT, ESON, YMDT, YMON, or HSIDT"}, status_code=400)
            return
        if not beg_text or not end_text:
            send_json({"status": "failed", "error": "BEG and END are required"}, status_code=400)
            return

        begin_dt = parse_utc_text(beg_text)
        end_dt = parse_utc_text(end_text)
        if begin_dt > end_dt:
            send_json({"status": "failed", "error": "BEG must be <= END"}, status_code=400)
            return

        cassandra_host = os.environ.get("CASSANDRA_HOST", "cassandra-node")
        cassandra_port = int(os.environ.get("CASSANDRA_PORT", "9042"))
        cassandra_keyspace = os.environ.get("CASSANDRA_KEYSPACE", "tqdb1")
        cassandra_user = os.environ.get("CASSANDRA_USER", "")
        cassandra_password = os.environ.get("CASSANDRA_PASSWORD", "")

        auth_provider = None
        if cassandra_user and cassandra_password:
            auth_provider = PlainTextAuthProvider(username=cassandra_user, password=cassandra_password)

        cluster = Cluster([cassandra_host], port=cassandra_port, auth_provider=auth_provider)
        session = cluster.connect(cassandra_keyspace)
        session.default_timeout = 60

        points = discover_contract_switch_points(symbol, begin_dt, end_dt)
        points.sort(key=lambda item: item["switch_utc"], reverse=True)

        # Build close_dt_by_switch: map switch_utc string -> close_dt in UTC.
        # Mirrors compose_continuous_minbars: for each rollover entry compute
        # switch_utc (rollover_date + rollover_time + integer tz offset) and
        # close_dt (rollover_date + close_time + IANA tz), then key by switch_utc string.
        cf_rows = fetch_continuous_futures(symbol=symbol)
        close_time_str = cf_rows[0].get("close_time", "") if cf_rows else ""
        close_timezone = cf_rows[0].get("timezone", "") if cf_rows else ""
        rollover_entries = fetch_contract_rollover_dt(symbol=symbol)
        close_dt_by_switch: dict[str, object] = {}
        for _row in rollover_entries:
            switch_utc_dt = _rollover_entry_to_utc(
                _row.get("rollover_date"),
                _row.get("rollover_time", "00:00"),
                int(_row.get("timezone", 0)),
            )
            if switch_utc_dt is None:
                continue
            switch_key = switch_utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            close_dt_by_switch[switch_key] = _rollover_close_to_utc(
                str(_row.get("rollover_date", "")),
                close_time_str,
                close_timezone,
            )

        enrich_switch_points_with_gap(session, cassandra_keyspace, points, close_dt_by_switch)

        send_json({
            "symbol": symbol,
            "begin": beg_text,
            "end": end_text,
            "switch_points": points,
        })

    except Exception as exc:
        send_json({"status": "failed", "error": str(exc)}, status_code=500)
    finally:
        if cluster is not None:
            try:
                cluster.shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    main()

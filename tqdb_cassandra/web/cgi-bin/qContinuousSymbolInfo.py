#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Return metadata for continuous symbols TXDT/TXON and CME DT/ON symbols.

Used by csymbol.html to show queryable 1-minute data range.
"""

import json
import os
import sys
import traceback

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

from continuous_symbols import discover_continuous_bounds, load_holiday_dates


def send_json(payload, status_code=200):
    sys.stdout.write(f"Status: {status_code}\r\n")
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.flush()


def main():
    cassandra_host = os.environ.get("CASSANDRA_HOST", "cassandra-node")
    cassandra_port = int(os.environ.get("CASSANDRA_PORT", "9042"))
    cassandra_keyspace = os.environ.get("CASSANDRA_KEYSPACE", "tqdb1")
    cassandra_user = os.environ.get("CASSANDRA_USER", "")
    cassandra_password = os.environ.get("CASSANDRA_PASSWORD", "")

    auth_provider = None
    if cassandra_user and cassandra_password:
        auth_provider = PlainTextAuthProvider(username=cassandra_user, password=cassandra_password)

    cluster = None
    session = None
    
    try:
        try:
            cluster = Cluster([cassandra_host], port=cassandra_port, auth_provider=auth_provider)
            session = cluster.connect(cassandra_keyspace)
            session.default_timeout = 60
        except Exception as exc:
            error_msg = f"Cassandra connection failed (host={cassandra_host}:{cassandra_port}, keyspace={cassandra_keyspace}): {exc}"
            print(error_msg, file=sys.stderr)
            send_json({"status": "failed", "error": error_msg}, status_code=503)
            return

        rows = []
        for symbol in ["TXON", "TXDT", "NQON", "NQDT", "ESON", "ESDT", "YMON", "YMDT"]:
            try:
                holidays = load_holiday_dates(symbol)
                bounds = discover_continuous_bounds(session, cassandra_keyspace, symbol, holidays)
                rows.append(bounds)
            except Exception as exc:
                error_msg = f"Failed to discover bounds for {symbol}: {exc}"
                print(error_msg, file=sys.stderr)
                rows.append({
                    "symbol": symbol,
                    "start": None,
                    "end": None,
                    "error": str(exc)
                })

        send_json({"symbols": rows})
    except Exception as exc:
        error_msg = f"Unexpected error: {exc}\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        send_json({"status": "failed", "error": str(exc)}, status_code=500)
    finally:
        if cluster:
            try:
                cluster.shutdown()
            except Exception as exc:
                print(f"Error closing cluster: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

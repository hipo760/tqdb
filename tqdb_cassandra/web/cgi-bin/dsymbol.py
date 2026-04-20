#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Delete all data partitions for a symbol.

Deletes from all existing symbol-partition tables in keyspace, including
`symbol`, `minbar`, `secbar`, and `tick` (and optional `daybar` if present).
"""

import json
import os
import sys
from urllib.parse import unquote

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster


def send_json(payload, status_code=200):
    sys.stdout.write(f"Status: {status_code}\r\n")
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.flush()


def parse_params():
    query_string = os.environ.get("QUERY_STRING", "")
    params = {}
    for item in query_string.split("&"):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        params[k] = unquote(v)
    return params


def main():
    cluster = None
    try:
        params = parse_params()
        symbol = (params.get("sym", "") or "").strip().upper()
        delete_symbol_table = (params.get("deleteSymbolTable", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
        if not symbol:
            send_json({"status": "failed", "error": "sym is required"}, status_code=400)
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
        session.default_timeout = 120

        table_order = ["tick", "secbar", "minbar", "daybar"]
        if delete_symbol_table:
            table_order.append("symbol")
        existing_tables = set(cluster.metadata.keyspaces[cassandra_keyspace].tables.keys())
        deleted_tables = []
        skipped_tables = []

        for table in table_order:
            if table not in existing_tables:
                skipped_tables.append(table)
                continue

            query = f"DELETE FROM {cassandra_keyspace}.{table} WHERE symbol = %s"
            session.execute(query, [symbol])
            deleted_tables.append(table)

        send_json(
            {
                "status": "ok",
                "symbol": symbol,
                "delete_symbol_table": delete_symbol_table,
                "deleted_tables": deleted_tables,
                "skipped_tables": skipped_tables,
            }
        )

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

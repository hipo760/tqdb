#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Return per-contract Cassandra availability for all continuous futures symbols.

Calls the Instrument API to get the full symbol and rollover schedule, then
probes Cassandra minbar for each underlying contract.

Response shape:
[
  {
    "symbol":      "TXON",
    "symbol_root": "TX",
    "contracts": [
      {"contract_month": "202604", "tqdb_symbol": "TXD6", "has_data": true},
      ...
    ]
  },
  ...
]
"""

import json
import os
import sys
import traceback

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

from continuous_symbols import list_continuous_futures_with_availability


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
    try:
        cluster = Cluster([cassandra_host], port=cassandra_port, auth_provider=auth_provider)
        session = cluster.connect(cassandra_keyspace)
        session.default_timeout = 60

        result = list_continuous_futures_with_availability(session, cassandra_keyspace)
        send_json(result)

    except Exception as exc:
        error_msg = str(exc)
        print(f"Error: {error_msg}\n{traceback.format_exc()}", file=sys.stderr)
        send_json({"status": "failed", "error": error_msg}, status_code=500)
    finally:
        if cluster is not None:
            try:
                cluster.shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    main()

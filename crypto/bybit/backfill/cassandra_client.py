"""Cassandra session factory.

Reads connection parameters from environment variables so the container
has no hard-coded credentials.

Environment variables (all required unless noted):
    CASSANDRA_HOST      default: cassandra
    CASSANDRA_PORT      default: 9042
    CASSANDRA_USER      optional – omit or leave blank for no-auth clusters
    CASSANDRA_PASSWORD  optional
    CASSANDRA_KEYSPACE  default: tqdb1
    CASSANDRA_TABLE     default: minbar
"""

from __future__ import annotations

import os


def _cfg() -> dict:
    return {
        "host": os.environ.get("CASSANDRA_HOST", "cassandra"),
        "port": int(os.environ.get("CASSANDRA_PORT", "9042")),
        "user": os.environ.get("CASSANDRA_USER", ""),
        "password": os.environ.get("CASSANDRA_PASSWORD", ""),
        "keyspace": os.environ.get("CASSANDRA_KEYSPACE", "tqdb1"),
        "table": os.environ.get("CASSANDRA_TABLE", "minbar"),
    }


def get_session():
    """Return a connected Cassandra session scoped to the configured keyspace."""
    from cassandra.cluster import Cluster  # type: ignore
    from cassandra.auth import PlainTextAuthProvider  # type: ignore

    cfg = _cfg()

    if cfg["user"] and cfg["password"]:
        auth = PlainTextAuthProvider(cfg["user"], cfg["password"])
        cluster = Cluster([cfg["host"]], port=cfg["port"], auth_provider=auth)
    else:
        cluster = Cluster([cfg["host"]], port=cfg["port"])

    session = cluster.connect()
    session.set_keyspace(cfg["keyspace"])
    return session


def get_table() -> str:
    return _cfg()["table"]

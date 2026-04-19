#!/usr/bin/env python3
"""Rename Cassandra symbols across all symbol-partitioned tables.

Example:
  uv run rename_symbols.py --host localhost --map TXON:TXON_D --map TXDT:TXDT_D
"""

import argparse
import sys
from typing import Dict, List

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster


def get_table_columns(session, keyspace: str, table: str) -> List[str]:
    query = (
        "SELECT column_name, position FROM system_schema.columns "
        "WHERE keyspace_name=%s AND table_name=%s"
    )
    rows = session.execute(query, [keyspace, table])

    # Primary-key columns can have position >= 0; regular columns usually -1.
    # Keep deterministic order: key columns by position first, then non-key sorted by name.
    key_cols = []
    non_key_cols = []
    for r in rows:
        if r.position is not None and r.position >= 0:
            key_cols.append((r.position, r.column_name))
        else:
            non_key_cols.append(r.column_name)

    key_cols.sort(key=lambda x: x[0])
    non_key_cols.sort()

    ordered = [c for _, c in key_cols] + non_key_cols
    if "symbol" not in ordered:
        raise RuntimeError(f"Table {keyspace}.{table} does not contain symbol column")
    return ordered


def count_symbol_rows(session, keyspace: str, table: str, symbol: str) -> int:
    query = f"SELECT count(*) FROM {keyspace}.{table} WHERE symbol = %s"
    return session.execute(query, [symbol]).one().count


def copy_symbol_partition(session, keyspace: str, table: str, old_symbol: str, new_symbol: str) -> int:
    columns = get_table_columns(session, keyspace, table)
    select_query = f"SELECT {', '.join(columns)} FROM {keyspace}.{table} WHERE symbol = %s"
    rows = session.execute(select_query, [old_symbol], timeout=None)

    insert_query = (
        f"INSERT INTO {keyspace}.{table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(['?'] * len(columns))})"
    )
    prepared_insert = session.prepare(insert_query)

    copied = 0
    for row in rows:
        values = []
        for col in columns:
            val = getattr(row, col)
            if col == "symbol":
                val = new_symbol
            values.append(val)
        session.execute(prepared_insert, values)
        copied += 1

    return copied


def delete_symbol_partition(session, keyspace: str, table: str, symbol: str) -> None:
    query = f"DELETE FROM {keyspace}.{table} WHERE symbol = %s"
    session.execute(query, [symbol])


def rename_symbol(session, keyspace: str, tables: List[str], old_symbol: str, new_symbol: str) -> None:
    print(f"\nRenaming {old_symbol} -> {new_symbol}")

    # Guard against accidental overwrite.
    for table in tables:
        target_count = count_symbol_rows(session, keyspace, table, new_symbol)
        if target_count > 0:
            raise RuntimeError(
                f"Target symbol {new_symbol} already has {target_count} row(s) in {keyspace}.{table}; aborting"
            )

    # Copy all partitions.
    old_counts: Dict[str, int] = {}
    for table in tables:
        old_count = count_symbol_rows(session, keyspace, table, old_symbol)
        old_counts[table] = old_count
        if old_count == 0:
            print(f"  {table}: 0 rows, skip copy")
            continue

        print(f"  {table}: copying {old_count} row(s)")
        copied = copy_symbol_partition(session, keyspace, table, old_symbol, new_symbol)
        print(f"  {table}: copied {copied} row(s)")

    # Verify and delete old partitions.
    for table in tables:
        old_count = old_counts[table]
        if old_count == 0:
            continue

        new_count = count_symbol_rows(session, keyspace, table, new_symbol)
        if new_count != old_count:
            raise RuntimeError(
                f"Verification failed in {keyspace}.{table}: expected {old_count} rows for {new_symbol}, got {new_count}"
            )

        delete_symbol_partition(session, keyspace, table, old_symbol)
        post_old = count_symbol_rows(session, keyspace, table, old_symbol)
        if post_old != 0:
            raise RuntimeError(
                f"Delete verification failed in {keyspace}.{table}: {old_symbol} still has {post_old} row(s)"
            )

        print(f"  {table}: old symbol removed, new symbol verified")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rename symbol partitions in Cassandra")
    parser.add_argument("--host", default="localhost", help="Cassandra host")
    parser.add_argument("--port", type=int, default=9042, help="Cassandra port")
    parser.add_argument("--keyspace", default="tqdb1", help="Keyspace name")
    parser.add_argument("--user", help="Cassandra username")
    parser.add_argument("--password", help="Cassandra password")
    parser.add_argument(
        "--map",
        action="append",
        required=True,
        help="Rename mapping in old:new format. Repeat for multiple mappings.",
    )
    return parser.parse_args()


def parse_mappings(items: List[str]) -> List[tuple[str, str]]:
    mappings: List[tuple[str, str]] = []
    for item in items:
        if ":" not in item:
            raise ValueError(f"Invalid --map '{item}', expected old:new")
        old_symbol, new_symbol = item.split(":", 1)
        old_symbol = old_symbol.strip().upper()
        new_symbol = new_symbol.strip().upper()
        if not old_symbol or not new_symbol:
            raise ValueError(f"Invalid --map '{item}', symbols cannot be empty")
        mappings.append((old_symbol, new_symbol))
    return mappings


def main() -> int:
    args = parse_args()
    mappings = parse_mappings(args.map)

    auth_provider = None
    if args.user and args.password:
        auth_provider = PlainTextAuthProvider(username=args.user, password=args.password)

    cluster = Cluster([args.host], port=args.port, auth_provider=auth_provider)
    session = cluster.connect(args.keyspace)
    session.default_timeout = 120

    # Tables where symbol is partition key in this deployment.
    tables = ["symbol", "minbar", "secbar", "tick"]

    try:
        for old_symbol, new_symbol in mappings:
            rename_symbol(session, args.keyspace, tables, old_symbol, new_symbol)
    finally:
        cluster.shutdown()

    print("\nAll renames completed successfully")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

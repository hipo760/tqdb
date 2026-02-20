#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
q1sec.py - Second Bar Query Tool (Python replacement for q1sec C++ binary)

Queries second bar data from Cassandra database.

Usage:
    ./q1sec.py <cassandra_host> <port> <keyspace.table> <symbol> <begin_dt> <end_dt> [format]

Example:
    ./q1sec.py cassandra-node 9042 tqdb1.secbar WTF.506 "2024-01-01 09:00:00" "2024-01-01 15:00:00"

Output:
    Tab-separated second bar data (datetime, symbol, open, high, low, close, volume)
"""

import sys
import os

# Add python-binaries directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cassandra_query import query_second_bars


def main():
    if len(sys.argv) < 7:
        print("Usage: q1sec <cassandra_host> <port> <keyspace.table> <symbol> <begin_dt> <end_dt> [format]", file=sys.stderr)
        sys.exit(1)
    
    # Parse arguments
    cassandra_host = sys.argv[1]
    port = sys.argv[2]
    keyspace_table = sys.argv[3]  # e.g., "tqdb1.secbar"
    symbol = sys.argv[4]
    begin_dt = sys.argv[5]
    end_dt = sys.argv[6]
    output_format = sys.argv[7] if len(sys.argv) > 7 else 'text'
    
    # Set environment variables
    os.environ['CASSANDRA_HOST'] = cassandra_host
    os.environ['CASSANDRA_PORT'] = port
    
    # Extract keyspace
    keyspace = keyspace_table.split('.')[0]
    os.environ['CASSANDRA_KEYSPACE'] = keyspace
    
    # Query second bars
    result = query_second_bars(symbol, begin_dt, end_dt, output_format=output_format)
    print(result)


if __name__ == '__main__':
    main()

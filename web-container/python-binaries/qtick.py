#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qtick.py - Tick Data Query Tool (Python replacement for qtick C++ binary)

Queries tick data from Cassandra database.

Usage:
    ./qtick.py <cassandra_host> <port> <keyspace.table> <symbol> <begin_dt> <end_dt> [format]

Example:
    ./qtick.py cassandra-node 9042 tqdb1.tick WTF.506 "2024-01-01 09:00:00" "2024-01-01 15:00:00"

Output:
    Tab-separated tick data (datetime, symbol, price, volume, bid, ask, bidsize, asksize)
"""

import sys
import os

# Add python-binaries directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cassandra_query import query_ticks


def main():
    if len(sys.argv) < 7:
        print("Usage: qtick <cassandra_host> <port> <keyspace.table> <symbol> <begin_dt> <end_dt> [format]", file=sys.stderr)
        sys.exit(1)
    
    # Parse arguments
    cassandra_host = sys.argv[1]
    port = sys.argv[2]
    keyspace_table = sys.argv[3]  # e.g., "tqdb1.tick"
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
    
    # Query ticks
    result = query_ticks(symbol, begin_dt, end_dt, output_format=output_format)
    print(result)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
itick.py - Tick Data Insertion Tool (Python replacement for itick C++ binary)

Inserts tick data into Cassandra database.

Usage:
    ./itick.py <cassandra_host> <port> <keyspace.table> <symbol> <datetime> <price> <volume> [bid] [ask] [bidsize] [asksize]

Example:
    ./itick.py cassandra-node 9042 tqdb1.tick WTF.506 "2024-01-01 09:30:00" 150.5 1000 150.0 151.0 500 500

Output:
    Success message or error
"""

import sys
import os

# Add python-binaries directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cassandra_query import insert_tick


def main():
    if len(sys.argv) < 8:
        print("Usage: itick <cassandra_host> <port> <keyspace.table> <symbol> <datetime> <price> <volume> [bid] [ask] [bidsize] [asksize]", file=sys.stderr)
        sys.exit(1)
    
    # Parse arguments
    cassandra_host = sys.argv[1]
    port = sys.argv[2]
    keyspace_table = sys.argv[3]  # e.g., "tqdb1.tick"
    symbol = sys.argv[4]
    dt = sys.argv[5]
    price = float(sys.argv[6])
    volume = int(sys.argv[7])
    bid = float(sys.argv[8]) if len(sys.argv) > 8 else 0.0
    ask = float(sys.argv[9]) if len(sys.argv) > 9 else 0.0
    bidsize = int(sys.argv[10]) if len(sys.argv) > 10 else 0
    asksize = int(sys.argv[11]) if len(sys.argv) > 11 else 0
    
    # Set environment variables
    os.environ['CASSANDRA_HOST'] = cassandra_host
    os.environ['CASSANDRA_PORT'] = port
    
    # Extract keyspace
    keyspace = keyspace_table.split('.')[0]
    os.environ['CASSANDRA_KEYSPACE'] = keyspace
    
    # Insert tick
    try:
        success = insert_tick(symbol, dt, price, volume, bid, ask, bidsize, asksize)
        if success:
            print(f"Successfully inserted tick for {symbol} at {dt}")
        else:
            print("Failed to insert tick", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error inserting tick: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

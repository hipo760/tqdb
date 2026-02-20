#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qsym.py - Symbol Query Tool (Python replacement for qsym C++ binary)

Queries symbol information from Cassandra database.

Usage:
    ./qsym.py <cassandra_host> <port> <keyspace.table> <mode> <symbol> <limit>

Example:
    ./qsym.py cassandra-node 9042 tqdb1.symbol 0 ALL 1000

Output:
    JSON array of symbol information
"""

import sys
import os

# Add python-binaries directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cassandra_query import query_symbols


def main():
    if len(sys.argv) < 7:
        print("Usage: qsym <cassandra_host> <port> <keyspace.table> <mode> <symbol> <limit>", file=sys.stderr)
        sys.exit(1)
    
    # Parse arguments (matching C++ binary interface)
    cassandra_host = sys.argv[1]
    port = sys.argv[2]
    keyspace_table = sys.argv[3]  # e.g., "tqdb1.symbol"
    mode = sys.argv[4]  # Not used, kept for compatibility
    symbol = sys.argv[5]
    limit = int(sys.argv[6])
    
    # Set environment variables for cassandra_query module
    os.environ['CASSANDRA_HOST'] = cassandra_host
    os.environ['CASSANDRA_PORT'] = port
    
    # Extract keyspace from keyspace.table
    keyspace = keyspace_table.split('.')[0]
    os.environ['CASSANDRA_KEYSPACE'] = keyspace
    
    # Query symbols
    result = query_symbols(symbol, limit, output_format='json')
    print(result)


if __name__ == '__main__':
    main()

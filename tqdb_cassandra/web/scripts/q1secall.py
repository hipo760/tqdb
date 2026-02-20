#!/usr/bin/env python3
"""
Query 1-second bar data from Cassandra TQ Database.

This script retrieves second-level OHLCV (Open, High, Low, Close, Volume) data
for a specified trading symbol and time range from the Cassandra secbar table.

Usage:
    python3 q1secall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> [gzip]

Arguments:
    cassandra_ip  : Cassandra server IP address or hostname
    port          : Cassandra server port (usually 9042)
    keyspace      : Cassandra keyspace name (usually tqdb1)
    symbol        : Trading symbol to query (e.g., 'TEST.BTC', 'AAPL')
    begin_dt      : Start datetime in format 'YYYY-MM-DD HH:MM:SS'
    end_dt        : End datetime in format 'YYYY-MM-DD HH:MM:SS'
    output_file   : Path to output file for results
    gzip          : Optional - '1' to enable gzip compression, '0' or omit to disable

Output Format:
    CSV format with columns: datetime,open,high,low,close,volume
    Example: 2024-01-15 09:30:01,100.5,101.2,100.3,100.8,1500

Table Schema:
    secbar table structure:
    - symbol (text, partition key)
    - datetime (timestamp, clustering key, DESC order)
    - open, high, low, close, vol (double)

Notes:
    - Datetime values are stored in UTC in Cassandra
    - Query results are ordered by datetime ascending
    - Empty result set produces empty output file
    - Connection timeout: 10 seconds
    - Query timeout: 5 minutes

Example:
    python3 q1secall.py cassandra-node 9042 tqdb1 'TEST.BTC' '2024-01-01 00:00:00' '2024-01-31 23:59:59' /tmp/output.csv 1

Author: TQDB Containerization
Date: 2024
"""

import sys
import gzip
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement


def parse_datetime(dt_str):
    """
    Parse datetime string to datetime object.
    
    Args:
        dt_str: Datetime string in format 'YYYY-MM-DD HH:MM:SS'
        
    Returns:
        datetime object
        
    Raises:
        ValueError if format is invalid
    """
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        raise ValueError(f"Invalid datetime format '{dt_str}'. Expected 'YYYY-MM-DD HH:MM:SS': {e}")


def query_second_bars(cassandra_ip, port, keyspace, symbol, begin_dt, end_dt):
    """
    Query second bar data from Cassandra secbar table.
    
    Args:
        cassandra_ip: Cassandra host
        port: Cassandra port
        keyspace: Cassandra keyspace
        symbol: Trading symbol
        begin_dt: Start datetime object
        end_dt: End datetime object
        
    Returns:
        List of tuples: (datetime, open, high, low, close, volume)
        
    Raises:
        Exception on connection or query failure
    """
    cluster = None
    try:
        # Connect to Cassandra
        cluster = Cluster([cassandra_ip], port=int(port), connect_timeout=10)
        session = cluster.connect(keyspace)
        
        # Prepare query
        query = """
        SELECT datetime, open, high, low, close, vol
        FROM secbar
        WHERE symbol = %s
        AND datetime >= %s
        AND datetime <= %s
        ORDER BY datetime ASC
        """
        
        statement = SimpleStatement(query, fetch_size=10000)
        
        # Execute query
        rows = session.execute(statement, (symbol, begin_dt, end_dt), timeout=300)
        
        # Collect results
        results = []
        for row in rows:
            results.append((
                row.datetime,
                row.open,
                row.high,
                row.low,
                row.close,
                row.vol
            ))
        
        return results
        
    except Exception as e:
        raise Exception(f"Cassandra query failed: {e}")
    finally:
        if cluster:
            cluster.shutdown()


def write_output(results, output_file, use_gzip):
    """
    Write query results to output file.
    
    Args:
        results: List of result tuples
        output_file: Output file path
        use_gzip: Boolean - compress with gzip if True
        
    Format:
        CSV with header: datetime,open,high,low,close,volume
    """
    open_func = gzip.open if use_gzip else open
    mode = 'wt' if use_gzip else 'w'
    
    with open_func(output_file, mode) as f:
        # Write header
        f.write("datetime,open,high,low,close,volume\n")
        
        # Write data rows
        for dt, open_price, high, low, close, vol in results:
            # Format datetime as string
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{dt_str},{open_price},{high},{low},{close},{vol}\n")


def main():
    """Main entry point."""
    # Check arguments
    if len(sys.argv) < 8:
        print("Usage: python3 q1secall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> [gzip]")
        print("Example: python3 q1secall.py cassandra-node 9042 tqdb1 'TEST.BTC' '2024-01-01 00:00:00' '2024-01-31 23:59:59' /tmp/output.csv 1")
        sys.exit(1)
    
    # Parse arguments
    cassandra_ip = sys.argv[1]
    port = sys.argv[2]
    keyspace = sys.argv[3]
    symbol = sys.argv[4]
    begin_dt_str = sys.argv[5]
    end_dt_str = sys.argv[6]
    output_file = sys.argv[7]
    use_gzip = len(sys.argv) > 8 and sys.argv[8] == '1'
    
    try:
        # Parse datetime strings
        begin_dt = parse_datetime(begin_dt_str)
        end_dt = parse_datetime(end_dt_str)
        
        # Validate date range
        if begin_dt > end_dt:
            raise ValueError(f"Begin datetime {begin_dt_str} is after end datetime {end_dt_str}")
        
        # Query data
        print(f"Querying second bars for {symbol} from {begin_dt_str} to {end_dt_str}...")
        results = query_second_bars(cassandra_ip, port, keyspace, symbol, begin_dt, end_dt)
        
        # Write output
        print(f"Writing {len(results)} second bars to {output_file}...")
        write_output(results, output_file, use_gzip)
        
        print(f"Success! Retrieved {len(results)} second bars")
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

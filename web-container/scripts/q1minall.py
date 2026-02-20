#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TQ Database Minute Bar Query Tool - Python Replacement for q1minall.sh

This script queries minute bar data from Cassandra, combining:
1. Existing minute bars from minbar table
2. Generated minute bars from tick data (for gaps)

Usage:
    python3 q1minall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip>

Arguments:
    cassandra_ip: Cassandra server IP or hostname
    port: Cassandra port (default 9042)
    keyspace: Cassandra keyspace name
    symbol: Trading symbol
    begin_dt: Start datetime (YYYY-MM-DD HH:MM:SS)
    end_dt: End datetime (YYYY-MM-DD HH:MM:SS)
    output_file: Output file path
    gzip: Compress output (1=yes, 0=no)

Example:
    python3 q1minall.py cassandra-node 9042 tqdb1 TEST.BTC '2026-02-16 00:00:00' '2026-02-22 00:00:00' /tmp/output.csv 0
"""

import sys
import os
import gzip
from datetime import datetime, timedelta
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider


def connect_cassandra(cassandra_ip, port):
    """Connect to Cassandra cluster."""
    try:
        port = int(port)
        cluster = Cluster([cassandra_ip], port=port)
        session = cluster.connect()
        return session, cluster
    except Exception as e:
        print(f"Error connecting to Cassandra: {e}", file=sys.stderr)
        sys.exit(1)


def query_minute_bars(session, keyspace, symbol, begin_dt, end_dt):
    """
    Query minute bars from Cassandra minbar table.
    
    Returns:
        list: List of (datetime, open, high, low, close, volume) tuples
    """
    query = f"""
        SELECT datetime, open, high, low, close, vol
        FROM {keyspace}.minbar
        WHERE symbol = %s
        AND datetime >= %s
        AND datetime <= %s
        ORDER BY datetime
    """
    
    # Parse datetime strings
    begin = datetime.strptime(begin_dt, '%Y-%m-%d %H:%M:%S')
    end = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
    
    try:
        rows = session.execute(query, (symbol, begin, end))
        
        results = []
        for row in rows:
            results.append((
                row.datetime,
                row.open,
                row.high,
                row.low,
                row.close,
                row.vol if hasattr(row, 'vol') else 0
            ))
        
        return results
        
    except Exception as e:
        print(f"Error querying minute bars: {e}", file=sys.stderr)
        return []


def query_ticks_for_aggregation(session, keyspace, symbol, last_bar_dt, end_dt):
    """
    Query tick data and aggregate into minute bars.
    
    This is used to fill gaps when minute bar data is not available.
    In a full implementation, this would query the tick table and aggregate.
    For now, returns empty list as tick aggregation requires more complex logic.
    
    Returns:
        list: List of (datetime, open, high, low, close, volume) tuples
    """
    # TODO: Implement tick aggregation
    # This would require:
    # 1. Query tick table for symbol between last_bar_dt and end_dt
    # 2. Group ticks by minute
    # 3. Calculate OHLCV for each minute
    # For now, return empty list
    return []


def format_minute_bar(dt, open_val, high_val, low_val, close_val, volume):
    """
    Format minute bar data as CSV line.
    
    Format: YYYYMMDD,HHMMSS,Open,High,Low,Close,Volume
    """
    date_str = dt.strftime('%Y%m%d')
    time_str = dt.strftime('%H%M%S')
    return f"{date_str},{time_str},{open_val},{high_val},{low_val},{close_val},{volume}"


def write_output(bars, output_file, use_gzip):
    """
    Write minute bars to output file.
    
    Args:
        bars: List of (datetime, open, high, low, close, volume) tuples
        output_file: Output file path (without .gz extension)
        use_gzip: True to compress with gzip
    """
    try:
        if use_gzip:
            # Add .gz extension when compressing
            output_path = f"{output_file}.gz"
            with gzip.open(output_path, 'wt', encoding='utf-8') as f:
                for bar in bars:
                    line = format_minute_bar(*bar)
                    f.write(line + '\n')
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                for bar in bars:
                    line = format_minute_bar(*bar)
                    f.write(line + '\n')
        
        output_path = f"{output_file}.gz" if use_gzip else output_file
        print(f"Written {len(bars)} minute bars to {output_path}", file=sys.stderr)
        
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) != 9:
        print("Usage: python3 q1minall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip>")
        print("Example: python3 q1minall.py cassandra-node 9042 tqdb1 TEST.BTC '2026-02-16 00:00:00' '2026-02-22 00:00:00' /tmp/out.csv 0")
        sys.exit(1)
    
    cassandra_ip = sys.argv[1]
    port = sys.argv[2]
    keyspace = sys.argv[3]
    symbol = sys.argv[4]
    begin_dt = sys.argv[5]
    end_dt = sys.argv[6]
    output_file = sys.argv[7]
    use_gzip = (sys.argv[8] == '1')
    
    print(f"Querying minute bars for {symbol}", file=sys.stderr)
    print(f"Date range: {begin_dt} to {end_dt}", file=sys.stderr)
    
    # Connect to Cassandra
    session, cluster = connect_cassandra(cassandra_ip, port)
    
    try:
        # Query existing minute bars
        bars = query_minute_bars(session, keyspace, symbol, begin_dt, end_dt)
        
        # If we have bars, check if we need to aggregate ticks for gaps
        if bars:
            last_bar_dt = bars[-1][0]
            end = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
            
            # If last bar is before end time, try to aggregate ticks
            if last_bar_dt < end:
                tick_bars = query_ticks_for_aggregation(session, keyspace, symbol, last_bar_dt, end_dt)
                bars.extend(tick_bars)
        
        # Write output
        write_output(bars, output_file, use_gzip)
        
        if len(bars) == 0:
            print(f"No data found for {symbol} in date range", file=sys.stderr)
        
    finally:
        cluster.shutdown()


if __name__ == '__main__':
    main()

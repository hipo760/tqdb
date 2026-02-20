#!/usr/bin/env python3
"""
Query and aggregate daily bar data from Cassandra TQ Database.

This script retrieves minute-level OHLCV data and aggregates it into daily bars
for a specified trading symbol and time range. Daily aggregation respects market
session times (open/close) to properly calculate daily OHLC values.

Usage:
    python3 q1dayall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip> <mk_open> <mk_close>

Arguments:
    cassandra_ip  : Cassandra server IP address or hostname
    port          : Cassandra server port (usually 9042)
    keyspace      : Cassandra keyspace name (usually tqdb1)
    symbol        : Trading symbol to query (e.g., 'TEST.BTC', 'AAPL')
    begin_dt      : Start datetime in format 'YYYY-MM-DD HH:MM:SS'
    end_dt        : End datetime in format 'YYYY-MM-DD HH:MM:SS'
    output_file   : Path to output file for results
    gzip          : '1' to enable gzip compression, '0' to disable
    mk_open       : Market open time in HHMMSS format (e.g., '093000' for 9:30 AM)
    mk_close      : Market close time in HHMMSS format (e.g., '160000' for 4:00 PM)

Output Format:
    CSV format with columns: date,open,high,low,close,volume
    Example: 2024-01-15,100.5,102.3,99.8,101.2,45000

Aggregation Logic:
    For each trading day:
    - Open: First minute's open price within market session
    - High: Maximum high price across all minutes in session
    - Low: Minimum low price across all minutes in session
    - Close: Last minute's close price within market session
    - Volume: Sum of all minute volumes in session

Market Session:
    - Only minute bars with time >= mk_open and time <= mk_close are included
    - If mk_open = mk_close = 0, includes all 24 hours
    - Days with no data in session window are excluded from output

Table Schema:
    minbar table structure:
    - symbol (text, partition key)
    - datetime (timestamp, clustering key, DESC order)
    - open, high, low, close, vol (double)

Notes:
    - Datetime values are stored in UTC in Cassandra
    - Query retrieves all minute bars for date range, then aggregates in Python
    - Empty result set produces empty output file
    - Connection timeout: 10 seconds
    - Query timeout: 10 minutes

Example:
    # Aggregate daily bars for 24-hour market (crypto)
    python3 q1dayall.py cassandra-node 9042 tqdb1 'TEST.BTC' '2024-01-01 00:00:00' '2024-01-31 23:59:59' /tmp/output.csv 1 0 0
    
    # Aggregate daily bars for stock market (9:30 AM - 4:00 PM)
    python3 q1dayall.py cassandra-node 9042 tqdb1 'AAPL' '2024-01-01 00:00:00' '2024-01-31 23:59:59' /tmp/output.csv 1 093000 160000

Author: TQDB Containerization
Date: 2024
"""

import sys
import gzip
from datetime import datetime, time
from collections import defaultdict
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


def parse_market_time(time_str):
    """
    Parse market time in HHMMSS format to time object.
    
    Args:
        time_str: Time string in HHMMSS format (e.g., '093000', '160000')
        
    Returns:
        time object, or None if time_str is '0' or '000000'
        
    Raises:
        ValueError if format is invalid
    """
    if time_str == '0' or time_str == '000000':
        return None
    
    try:
        # Parse HHMMSS
        if len(time_str) != 6:
            raise ValueError(f"Expected 6 digits, got {len(time_str)}")
        
        hour = int(time_str[0:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])
        
        return time(hour, minute, second)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid market time format '{time_str}'. Expected HHMMSS: {e}")


def in_market_session(dt, mk_open, mk_close):
    """
    Check if datetime is within market session.
    
    Args:
        dt: datetime object to check
        mk_open: Market open time object (or None for 24-hour)
        mk_close: Market close time object (or None for 24-hour)
        
    Returns:
        True if within session, False otherwise
    """
    # 24-hour market if both are None
    if mk_open is None and mk_close is None:
        return True
    
    dt_time = dt.time()
    
    # Handle session that doesn't cross midnight
    if mk_open <= mk_close:
        return mk_open <= dt_time <= mk_close
    else:
        # Handle session that crosses midnight (e.g., 22:00 - 02:00)
        return dt_time >= mk_open or dt_time <= mk_close


def query_minute_bars(cassandra_ip, port, keyspace, symbol, begin_dt, end_dt):
    """
    Query minute bar data from Cassandra minbar table.
    
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
        FROM minbar
        WHERE symbol = %s
        AND datetime >= %s
        AND datetime <= %s
        ORDER BY datetime ASC
        """
        
        statement = SimpleStatement(query, fetch_size=10000)
        
        # Execute query
        rows = session.execute(statement, (symbol, begin_dt, end_dt), timeout=600)
        
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


def aggregate_to_daily(minute_bars, mk_open, mk_close):
    """
    Aggregate minute bars into daily bars.
    
    Args:
        minute_bars: List of minute bar tuples (datetime, open, high, low, close, volume)
        mk_open: Market open time object (or None for 24-hour)
        mk_close: Market close time object (or None for 24-hour)
        
    Returns:
        Dict mapping date -> (open, high, low, close, volume)
        
    Logic:
        - Group minute bars by date
        - Filter by market session times
        - For each date:
          - Open: First minute's open in session
          - High: Max of all highs in session
          - Low: Min of all lows in session
          - Close: Last minute's close in session
          - Volume: Sum of all volumes in session
    """
    # Group by date
    daily_data = defaultdict(list)
    
    for dt, open_price, high, low, close, vol in minute_bars:
        # Check if within market session
        if not in_market_session(dt, mk_open, mk_close):
            continue
        
        date = dt.date()
        daily_data[date].append((dt, open_price, high, low, close, vol))
    
    # Aggregate each day
    daily_bars = {}
    
    for date in sorted(daily_data.keys()):
        bars = daily_data[date]
        
        if not bars:
            continue
        
        # Sort by datetime to ensure correct order
        bars.sort(key=lambda x: x[0])
        
        # Extract OHLCV
        day_open = bars[0][1]  # First bar's open
        day_high = max(bar[2] for bar in bars)  # Max of all highs
        day_low = min(bar[3] for bar in bars)  # Min of all lows
        day_close = bars[-1][4]  # Last bar's close
        day_volume = sum(bar[5] for bar in bars)  # Sum of all volumes
        
        daily_bars[date] = (day_open, day_high, day_low, day_close, day_volume)
    
    return daily_bars


def write_output(daily_bars, output_file, use_gzip):
    """
    Write daily bars to output file.
    
    Args:
        daily_bars: Dict mapping date -> (open, high, low, close, volume)
        output_file: Output file path
        use_gzip: Boolean - compress with gzip if True
        
    Format:
        CSV with header: date,open,high,low,close,volume
    """
    open_func = gzip.open if use_gzip else open
    mode = 'wt' if use_gzip else 'w'
    
    with open_func(output_file, mode) as f:
        # Write header
        f.write("date,open,high,low,close,volume\n")
        
        # Write data rows (sorted by date)
        for date in sorted(daily_bars.keys()):
            open_price, high, low, close, vol = daily_bars[date]
            date_str = date.strftime('%Y-%m-%d')
            f.write(f"{date_str},{open_price},{high},{low},{close},{vol}\n")


def main():
    """Main entry point."""
    # Check arguments
    if len(sys.argv) < 11:
        print("Usage: python3 q1dayall.py <cassandra_ip> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip> <mk_open> <mk_close>")
        print("Example: python3 q1dayall.py cassandra-node 9042 tqdb1 'TEST.BTC' '2024-01-01 00:00:00' '2024-01-31 23:59:59' /tmp/output.csv 1 093000 160000")
        sys.exit(1)
    
    # Parse arguments
    cassandra_ip = sys.argv[1]
    port = sys.argv[2]
    keyspace = sys.argv[3]
    symbol = sys.argv[4]
    begin_dt_str = sys.argv[5]
    end_dt_str = sys.argv[6]
    output_file = sys.argv[7]
    use_gzip = sys.argv[8] == '1'
    mk_open_str = sys.argv[9]
    mk_close_str = sys.argv[10]
    
    try:
        # Parse datetime strings
        begin_dt = parse_datetime(begin_dt_str)
        end_dt = parse_datetime(end_dt_str)
        
        # Validate date range
        if begin_dt > end_dt:
            raise ValueError(f"Begin datetime {begin_dt_str} is after end datetime {end_dt_str}")
        
        # Parse market times
        mk_open = parse_market_time(mk_open_str)
        mk_close = parse_market_time(mk_close_str)
        
        # Query minute bars
        print(f"Querying minute bars for {symbol} from {begin_dt_str} to {end_dt_str}...")
        minute_bars = query_minute_bars(cassandra_ip, port, keyspace, symbol, begin_dt, end_dt)
        print(f"Retrieved {len(minute_bars)} minute bars")
        
        # Aggregate to daily
        if mk_open or mk_close:
            print(f"Aggregating to daily bars (session: {mk_open_str} - {mk_close_str})...")
        else:
            print("Aggregating to daily bars (24-hour market)...")
        
        daily_bars = aggregate_to_daily(minute_bars, mk_open, mk_close)
        
        # Write output
        print(f"Writing {len(daily_bars)} daily bars to {output_file}...")
        write_output(daily_bars, output_file, use_gzip)
        
        print(f"Success! Generated {len(daily_bars)} daily bars from {len(minute_bars)} minute bars")
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cassandra Query Library for TQDB

This module provides direct Cassandra database access functions to replace
the legacy C++ binaries (qsym, qtick, q1min, q1sec, etc.). It uses the
Python cassandra-driver to efficiently query trading data.

Functions:
- query_symbols: Query symbol information (replaces qsym)
- query_ticks: Query tick data (replaces qtick)
- query_minute_bars: Query minute bars (replaces q1min/q1minsec)
- query_second_bars: Query second bars (replaces q1sec)
- insert_tick: Insert tick data (replaces itick)

Author: TQDB Containerization Team
"""

import os
import sys
import json
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from cassandra.auth import PlainTextAuthProvider


# Configuration from environment variables
CASSANDRA_HOST = os.environ.get('CASSANDRA_HOST', 'cassandra-node')
CASSANDRA_PORT = int(os.environ.get('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = os.environ.get('CASSANDRA_KEYSPACE', 'tqdb1')
CASSANDRA_USER = os.environ.get('CASSANDRA_USER', '')
CASSANDRA_PASSWORD = os.environ.get('CASSANDRA_PASSWORD', '')


def get_cassandra_session():
    """
    Create and return a Cassandra session.
    
    Returns:
        cassandra.cluster.Session: Active Cassandra session
    """
    if CASSANDRA_USER and CASSANDRA_PASSWORD:
        auth_provider = PlainTextAuthProvider(
            username=CASSANDRA_USER,
            password=CASSANDRA_PASSWORD
        )
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, auth_provider=auth_provider)
    else:
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    
    session = cluster.connect(CASSANDRA_KEYSPACE)
    return session, cluster


def query_symbols(symbol='ALL', limit=1000, output_format='json'):
    """
    Query symbol information from Cassandra (replaces qsym binary).
    
    Args:
        symbol (str): Symbol code or 'ALL' for all symbols
        limit (int): Maximum number of results
        output_format (str): Output format ('json' or 'text')
        
    Returns:
        str: JSON string or text output of symbol information
    """
    session, cluster = None, None
    try:
        session, cluster = get_cassandra_session()
        
        if symbol == 'ALL' or symbol == '*':
            query = f"SELECT * FROM symbol LIMIT {limit}"
            rows = session.execute(query)
        else:
            query = "SELECT * FROM symbol WHERE symbol = %s"
            rows = session.execute(query, (symbol,))
        
        results = []
        for row in rows:
            result = {
                'symbol': row.symbol,
                'keyval': dict(row.keyval) if hasattr(row, 'keyval') and row.keyval else {}
            }
            results.append(result)
        
        if output_format == 'json':
            return json.dumps(results, ensure_ascii=False, indent=2)
        else:
            # Text format compatible with legacy qsym output
            lines = []
            for r in results:
                lines.append(f"{r['symbol']}\t{r['market']}\t{r['name']}\t{r['exchange']}")
            return '\n'.join(lines)
            
    finally:
        if cluster:
            cluster.shutdown()


def query_ticks(symbol, begin_dt, end_dt, output_format='text'):
    """
    Query tick data from Cassandra (replaces qtick binary).
    
    Args:
        symbol (str): Symbol code
        begin_dt (datetime or str): Begin datetime
        end_dt (datetime or str): End datetime
        output_format (str): Output format ('text', 'json', 'csv')
        
    Returns:
        str: Formatted tick data
    """
    session, cluster = None, None
    try:
        session, cluster = get_cassandra_session()
        
        # Convert string to datetime if needed
        if isinstance(begin_dt, str):
            begin_dt = datetime.strptime(begin_dt, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_dt, str):
            end_dt = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT symbol, dt, price, volume, bid, ask, bidsize, asksize
            FROM tick
            WHERE symbol = %s AND dt >= %s AND dt <= %s
            ORDER BY dt ASC
        """
        
        rows = session.execute(query, (symbol, begin_dt, end_dt))
        
        if output_format == 'json':
            results = []
            for row in rows:
                results.append({
                    'symbol': row.symbol,
                    'dt': str(row.dt),
                    'price': float(row.price) if row.price else 0.0,
                    'volume': int(row.volume) if row.volume else 0,
                    'bid': float(row.bid) if row.bid else 0.0,
                    'ask': float(row.ask) if row.ask else 0.0,
                    'bidsize': int(row.bidsize) if row.bidsize else 0,
                    'asksize': int(row.asksize) if row.asksize else 0
                })
            return json.dumps(results, ensure_ascii=False)
        
        elif output_format == 'csv':
            lines = ['datetime,symbol,price,volume,bid,ask,bidsize,asksize']
            for row in rows:
                lines.append(f"{row.dt},{row.symbol},{row.price},{row.volume},{row.bid},{row.ask},{row.bidsize},{row.asksize}")
            return '\n'.join(lines)
        
        else:  # text format (legacy compatible)
            lines = []
            for row in rows:
                lines.append(f"{row.dt}\t{row.symbol}\t{row.price}\t{row.volume}\t{row.bid}\t{row.ask}\t{row.bidsize}\t{row.asksize}")
            return '\n'.join(lines)
            
    finally:
        if cluster:
            cluster.shutdown()


def query_minute_bars(symbol, begin_dt, end_dt, output_format='text'):
    """
    Query minute bar data from Cassandra (replaces q1min/q1minsec binaries).
    
    Args:
        symbol (str): Symbol code
        begin_dt (datetime or str): Begin datetime
        end_dt (datetime or str): End datetime
        output_format (str): Output format ('text', 'json', 'csv')
        
    Returns:
        str: Formatted minute bar data
    """
    session, cluster = None, None
    try:
        session, cluster = get_cassandra_session()
        
        # Convert string to datetime if needed
        if isinstance(begin_dt, str):
            begin_dt = datetime.strptime(begin_dt, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_dt, str):
            end_dt = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT symbol, dt, open, high, low, close, volume
            FROM minbar
            WHERE symbol = %s AND dt >= %s AND dt <= %s
            ORDER BY dt ASC
        """
        
        rows = session.execute(query, (symbol, begin_dt, end_dt))
        
        if output_format == 'json':
            results = []
            for row in rows:
                results.append({
                    'symbol': row.symbol,
                    'dt': str(row.dt),
                    'open': float(row.open) if row.open else 0.0,
                    'high': float(row.high) if row.high else 0.0,
                    'low': float(row.low) if row.low else 0.0,
                    'close': float(row.close) if row.close else 0.0,
                    'volume': int(row.volume) if row.volume else 0
                })
            return json.dumps(results, ensure_ascii=False)
        
        elif output_format == 'csv':
            lines = ['datetime,symbol,open,high,low,close,volume']
            for row in rows:
                lines.append(f"{row.dt},{row.symbol},{row.open},{row.high},{row.low},{row.close},{row.volume}")
            return '\n'.join(lines)
        
        else:  # text format (legacy compatible)
            lines = []
            for row in rows:
                lines.append(f"{row.dt}\t{row.symbol}\t{row.open}\t{row.high}\t{row.low}\t{row.close}\t{row.volume}")
            return '\n'.join(lines)
            
    finally:
        if cluster:
            cluster.shutdown()


def query_second_bars(symbol, begin_dt, end_dt, output_format='text'):
    """
    Query second bar data from Cassandra (replaces q1sec binary).
    
    Args:
        symbol (str): Symbol code
        begin_dt (datetime or str): Begin datetime
        end_dt (datetime or str): End datetime
        output_format (str): Output format ('text', 'json', 'csv')
        
    Returns:
        str: Formatted second bar data
    """
    session, cluster = None, None
    try:
        session, cluster = get_cassandra_session()
        
        # Convert string to datetime if needed
        if isinstance(begin_dt, str):
            begin_dt = datetime.strptime(begin_dt, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_dt, str):
            end_dt = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT symbol, dt, open, high, low, close, volume
            FROM secbar
            WHERE symbol = %s AND dt >= %s AND dt <= %s
            ORDER BY dt ASC
        """
        
        rows = session.execute(query, (symbol, begin_dt, end_dt))
        
        if output_format == 'json':
            results = []
            for row in rows:
                results.append({
                    'symbol': row.symbol,
                    'dt': str(row.dt),
                    'open': float(row.open) if row.open else 0.0,
                    'high': float(row.high) if row.high else 0.0,
                    'low': float(row.low) if row.low else 0.0,
                    'close': float(row.close) if row.close else 0.0,
                    'volume': int(row.volume) if row.volume else 0
                })
            return json.dumps(results, ensure_ascii=False)
        
        elif output_format == 'csv':
            lines = ['datetime,symbol,open,high,low,close,volume']
            for row in rows:
                lines.append(f"{row.dt},{row.symbol},{row.open},{row.high},{row.low},{row.close},{row.volume}")
            return '\n'.join(lines)
        
        else:  # text format (legacy compatible)
            lines = []
            for row in rows:
                lines.append(f"{row.dt}\t{row.symbol}\t{row.open}\t{row.high}\t{row.low}\t{row.close}\t{row.volume}")
            return '\n'.join(lines)
            
    finally:
        if cluster:
            cluster.shutdown()


def insert_tick(symbol, dt, price, volume, bid=0.0, ask=0.0, bidsize=0, asksize=0):
    """
    Insert tick data into Cassandra (replaces itick binary).
    
    Args:
        symbol (str): Symbol code
        dt (datetime or str): Tick datetime
        price (float): Price
        volume (int): Volume
        bid (float): Bid price
        ask (float): Ask price
        bidsize (int): Bid size
        asksize (int): Ask size
        
    Returns:
        bool: True if successful
    """
    session, cluster = None, None
    try:
        session, cluster = get_cassandra_session()
        
        # Convert string to datetime if needed
        if isinstance(dt, str):
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        
        query = """
            INSERT INTO tick (symbol, dt, price, volume, bid, ask, bidsize, asksize)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        session.execute(query, (symbol, dt, price, volume, bid, ask, bidsize, asksize))
        return True
        
    finally:
        if cluster:
            cluster.shutdown()


if __name__ == '__main__':
    # Command-line interface for testing
    if len(sys.argv) < 2:
        print("Usage:")
        print("  cassandra_query.py symbol [symbol_name|ALL] [limit]")
        print("  cassandra_query.py tick [symbol] [begin_dt] [end_dt]")
        print("  cassandra_query.py minbar [symbol] [begin_dt] [end_dt]")
        print("  cassandra_query.py secbar [symbol] [begin_dt] [end_dt]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'symbol':
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'ALL'
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
        result = query_symbols(symbol, limit)
        print(result)
    
    elif command == 'tick':
        symbol = sys.argv[2]
        begin_dt = sys.argv[3]
        end_dt = sys.argv[4]
        result = query_ticks(symbol, begin_dt, end_dt)
        print(result)
    
    elif command == 'minbar':
        symbol = sys.argv[2]
        begin_dt = sys.argv[3]
        end_dt = sys.argv[4]
        result = query_minute_bars(symbol, begin_dt, end_dt)
        print(result)
    
    elif command == 'secbar':
        symbol = sys.argv[2]
        begin_dt = sys.argv[3]
        end_dt = sys.argv[4]
        result = query_second_bars(symbol, begin_dt, end_dt)
        print(result)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

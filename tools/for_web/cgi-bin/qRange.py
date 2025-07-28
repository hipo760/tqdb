#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
TQ Database Range Data Query CGI Script

This CGI script provides time-range based price data queries for the TQ Database system.
It retrieves historical trading data (bars, ticks) for specified symbols within date ranges
from the Cassandra database and returns the data in JSON format.

Supported Data Types:
- minbar: Minute-based OHLCV (Open, High, Low, Close, Volume) bars
- secbar: Second-based OHLCV bars  
- tick: Individual trade tick data with price and volume

Author: TQ Database Team
Compatible with: Python 3.x, Cassandra 4.1+, Rocky Linux 9.0+
"""

import sys
import json
import os
from datetime import datetime
from urllib.parse import unquote
from dateutil import tz, parser
from cassandra.cluster import Cluster


def convert_local_datetime_to_epoch(local_dt):
    """
    Convert a local datetime object to epoch float timestamp.
    
    Args:
        local_dt (datetime): Local timezone datetime object
        
    Returns:
        float: Epoch timestamp with microsecond precision
        
    Note:
        Uses strftime('%s.%f') for precise timestamp conversion
    """
    return float(local_dt.strftime('%s.%f'))


def convert_utc_datetime_to_epoch(utc_dt):
    """
    Convert a UTC datetime object to local timezone epoch float timestamp.
    
    Args:
        utc_dt (datetime): UTC timezone datetime object
        
    Returns:
        float: Local timezone epoch timestamp with microsecond precision
        
    Process:
        1. Applies UTC timezone info to naive datetime
        2. Converts to local timezone
        3. Returns epoch timestamp
    """
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()

    # Apply UTC timezone info since datetime objects are 'naive' by default
    utc_dt = utc_dt.replace(tzinfo=from_zone)

    # Convert to local timezone
    local_dt = utc_dt.astimezone(to_zone)

    return float(local_dt.strftime('%s.%f'))


def execute_range_query(keyspace, table, symbol, begin_dt_str, end_dt_str):
    """
    Execute time-range price data query against Cassandra database.
    
    Args:
        keyspace (str): Cassandra keyspace name (e.g., 'tqdb1')
        table (str): Table name ('minbar', 'secbar', or 'tick')
        symbol (str): Trading symbol to query
        begin_dt_str (str): Start date/time string
        end_dt_str (str): End date/time string
        
    Returns:
        dict: Query result containing:
            - range: [start_epoch, end_epoch] timestamps
            - data: List of price/volume records
            - symbol: Queried symbol
            - type: Data type (table name)
            - qcmd: Executed query command
            
    Data Formats:
        - Bar data: {'dt': epoch, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}
        - Tick data: {'dt': epoch, 'c': close, 'v': volume}
    """
    try:
        # Initialize return object with parsed date range
        ret_obj = {
            'range': [
                convert_local_datetime_to_epoch(parser.parse(begin_dt_str)), 
                convert_local_datetime_to_epoch(parser.parse(end_dt_str))
            ], 
            'data': [], 
            'symbol': symbol, 
            'type': table, 
            'qcmd': ''
        }

        # Convert epoch timestamps back to datetime objects for query
        begin_dt = datetime.fromtimestamp(ret_obj['range'][0])
        end_dt = datetime.fromtimestamp(ret_obj['range'][1])

        # Connect to Cassandra cluster and execute query
        cluster = Cluster()
        session = cluster.connect(keyspace)
        
        query_str = (f"SELECT * FROM {keyspace}.{table} "
                    f"WHERE symbol='{symbol}' AND datetime>='{begin_dt}' "
                    f"AND datetime<'{end_dt}' ORDER BY datetime LIMIT 20000;")
        
        ret_obj['qcmd'] = query_str
        
        result = session.execute(query_str)
        
        # Check if query returned results
        if result is None or len(result.current_rows) <= 0:
            return ret_obj

        # Process results based on table type
        if table in ['minbar', 'secbar']:
            # OHLCV bar data processing
            for row in result:
                ret_obj['data'].append({
                    'dt': convert_utc_datetime_to_epoch(row.datetime),
                    'o': row.open,
                    'h': row.high,
                    'l': row.low,
                    'c': row.close,
                    'v': row.vol
                })
        elif table == 'tick':
            # Tick data processing (only type 1 trades)
            for row in result:
                if row.type == 1:
                    ret_obj['data'].append({
                        'dt': convert_utc_datetime_to_epoch(row.datetime),
                        'c': row.keyval['C'],
                        'v': row.keyval['V']
                    })
        
        return ret_obj
        
    except Exception as e:
        # Return error information in response
        return {
            'range': [],
            'data': [],
            'symbol': symbol,
            'type': table,
            'qcmd': '',
            'error': f"Query execution failed: {str(e)}"
        }


def parse_query_parameters():
    """
    Parse CGI query string parameters for range data request.
    
    Returns:
        dict: Parsed parameters containing:
            - symbol: Trading symbol (default: 'XX??')
            - type: Data type - 'minbar', 'secbar', or 'tick' (default: 'minbar')
            - BEG: Begin date string (default: today)
            - END: End date string (default: today)
            
    Query String Format:
        ?symbol=AAPL&type=minbar&BEG=2024-01-01&END=2024-01-02
    """
    query_string = os.environ.get("QUERY_STRING", "NA=NA")
    params = {}
    
    # Parse each parameter from query string
    for qs in query_string.split("&"):
        if qs.find("=") <= 0:
            continue
        key, value = qs.split("=", 1)
        params[key] = unquote(value)
    
    # Set default values for missing parameters
    if 'symbol' not in params:
        params['symbol'] = 'XX??'
    if 'type' not in params:
        params['type'] = 'minbar'
    if 'BEG' not in params:
        params['BEG'] = datetime.now().strftime('%Y-%m-%d')
    if 'END' not in params:
        params['END'] = datetime.now().strftime('%Y-%m-%d')
    
    return params


def main():
    """
    Main CGI execution function for range data queries.
    
    Process:
        1. Parse query string parameters
        2. Execute database query with specified range
        3. Return JSON response with price data
        
    Response Format:
        Content-Type: application/json; charset=UTF-8
        
        {
            "range": [start_epoch, end_epoch],
            "data": [price_records...],
            "symbol": "symbol_name",
            "type": "data_type",
            "qcmd": "executed_query"
        }
    """
    try:
        # Parse CGI parameters
        params = parse_query_parameters()
        
        # Execute range query
        result = execute_range_query(
            'tqdb1', 
            params['type'], 
            params['symbol'], 
            params['BEG'], 
            params['END']
        )
        
        # Output JSON response
        sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        sys.stdout.flush()
        
    except Exception as e:
        # Output error response
        error_response = {
            'range': [],
            'data': [],
            'symbol': 'ERROR',
            'type': 'error',
            'qcmd': '',
            'error': f"CGI execution failed: {str(e)}"
        }
        
        sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(json.dumps(error_response, ensure_ascii=False))
        sys.stdout.flush()


if __name__ == "__main__":
    main()


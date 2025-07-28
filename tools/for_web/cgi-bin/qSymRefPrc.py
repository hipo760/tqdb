#!/usr/bin/python3
# -*- coding: utf-8 -*-   
"""
TQ Database Symbol Reference Price Query CGI Script

This CGI script queries reference price data for financial symbols from the TQ Database.
It provides the last valid price information from tick data, minute bars, and second bars
before a specified datetime.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- cassandra-driver
- Cassandra database with tqdb schema

Usage:
    HTTP GET: /cgi-bin/qSymRefPrc.py?symbol=SYMBOL&qType=QUERY_TYPE&qDatetime=DATETIME
    
Parameters:
    - symbol: Financial symbol code (default: "WTX")
    - qType: Query type (default: "LastValidPrc")
    - qDatetime: Reference datetime in "YYYY-MM-DD HH:MM:SS" format (default: current time)

Query Types:
    - LastValidPrc: Returns the last valid price data before the specified datetime
                   from tick, minute bar, and second bar tables

Returns:
    JSON response containing:
    - Tick: Last tick record before specified datetime
    - MinBar: Last minute bar record before specified datetime  
    - SecBar: Last second bar record before specified datetime
    - queryInfo: Query parameters used (symbol, qType, qDatetime)
"""

import sys
import json
import os
import urllib.parse
from datetime import datetime
from cassandra.cluster import Cluster


def execute_query(cass_session, query_str):
    """
    Execute a Cassandra CQL query and return the results as a list of dictionaries.
    
    Args:
        cass_session: Active Cassandra session object
        query_str (str): CQL query string to execute
        
    Returns:
        dict: Dictionary containing:
            - 'Result': 'OK' on success, error message on failure
            - 'data': List of dictionaries representing query results
    """
    ret_data = []
    
    try:
        # Execute the CQL query
        query_result = cass_session.execute(query_str)
    except Exception as e:
        # Return error information if query execution fails
        return {
            'Result': f'Error! Failed to execute [{query_str}]: {str(e)}',
            'data': ret_data
        }
    
    # Get the actual rows from the result set
    result_rows = query_result.current_rows
    
    # Check if we have any data
    if query_result is None or len(result_rows) <= 0:
        return {
            'Result': 'Error! No Such Data',
            'data': ret_data
        }
    
    # Convert each row to a dictionary format
    for result_row in result_rows:
        row_dict = {}
        # Iterate through each column in the row
        for i in range(len(query_result.column_names)):
            column_name = query_result.column_names[i]
            column_value = result_row[i]
            
            # Convert non-None values to string, keep None as None
            if column_value is not None:
                row_dict[column_name] = str(column_value)
            else:
                row_dict[column_name] = None
                
        ret_data.append(row_dict)
    
    return {'Result': 'OK', 'data': ret_data}

def get_reference_price_data(keyspace, symbol, query_type, query_datetime):
    """
    Retrieve reference price data for a given financial symbol before a specified datetime.
    
    This function connects to the Cassandra database and queries multiple tables
    to find the last valid price information before the specified datetime.
    
    Args:
        keyspace (str): Cassandra keyspace name (e.g., 'tqdb1')
        symbol (str): Financial symbol to query (e.g., 'WTX')
        query_type (str): Type of query to perform (e.g., 'LastValidPrc')
        query_datetime (str): Reference datetime in 'YYYY-MM-DD HH:MM:SS' format
        
    Returns:
        dict: Dictionary containing price data with the following keys:
            - Tick: Last tick record before specified datetime
            - MinBar: Last minute bar record before specified datetime
            - SecBar: Last second bar record before specified datetime
            - queryInfo: Query parameters used
    """
    # Initialize Cassandra cluster connection
    cluster = Cluster()
    session = cluster.connect(keyspace)
    all_data = {}

    try:
        if query_type == "LastValidPrc":
            # Query 1: Get last tick record before specified datetime
            query_str = f"SELECT * FROM {keyspace}.tick WHERE symbol='{symbol}' AND datetime<'{query_datetime}' ORDER BY datetime DESC LIMIT 1;"
            ret_data = execute_query(session, query_str)
            all_data['Tick'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

            # Query 2: Get last minute bar record before specified datetime
            query_str = f"SELECT * FROM {keyspace}.minbar WHERE symbol='{symbol}' AND datetime<'{query_datetime}' ORDER BY datetime DESC LIMIT 1;"
            ret_data = execute_query(session, query_str)
            all_data['MinBar'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

            # Query 3: Get last second bar record before specified datetime
            query_str = f"SELECT * FROM {keyspace}.secbar WHERE symbol='{symbol}' AND datetime<'{query_datetime}' ORDER BY datetime DESC LIMIT 1;"
            ret_data = execute_query(session, query_str)
            all_data['SecBar'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']
        
        # Add query information for debugging and verification
        all_data['queryInfo'] = {
            'symbol': symbol,
            'qType': query_type,
            'qDatetime': query_datetime
        }
        
    finally:
        # Always close the database connection
        cluster.shutdown()
    
    return all_data


def parse_query_string():
    """
    Parse the CGI query string to extract symbol, query type, and datetime parameters.
    
    Returns:
        tuple: (symbol, query_type, query_datetime) with extracted or default values
    """
    # Get query string from environment variable
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    query_params = {}
    
    # Parse each query parameter
    for query_string in query_strings.split("&"):
        if query_string.find("=") <= 0:
            continue
        key, value = query_string.split("=", 1)  # Split only on first '='
        query_params[key] = urllib.parse.unquote(value)
    
    # Set default values
    symbol = "WTX"  # Default symbol
    query_type = "LastValidPrc"  # Default query type
    query_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current time as default
    
    # Override with provided parameters
    if 'symbol' in query_params:
        symbol = query_params['symbol']
    if 'qType' in query_params:
        query_type = query_params['qType']
    if 'qDatetime' in query_params:
        query_datetime = query_params['qDatetime']
    
    return symbol, query_type, query_datetime


def send_json_response(data):
    """
    Send JSON response with proper HTTP headers.
    
    Args:
        data: Python object to serialize as JSON
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    
    # Send JSON data
    sys.stdout.write(json.dumps(data, indent=2))
    sys.stdout.flush()

# Main CGI execution
if __name__ == "__main__":
    try:
        # Parse query string parameters
        symbol, query_type, query_datetime = parse_query_string()
        
        # Get reference price data for the symbol
        result = get_reference_price_data('tqdb1', symbol, query_type, query_datetime)
        
        # Send JSON response
        send_json_response(result)
        
    except Exception as e:
        # Handle any unexpected errors
        error_response = {
            'Result': f'Error! System exception: {str(e)}',
            'Tick': ['Exception!'],
            'MinBar': ['Exception!'],
            'SecBar': ['Exception!'],
            'queryInfo': {
                'symbol': 'Unknown',
                'qType': 'Unknown', 
                'qDatetime': 'Unknown',
                'error': str(e)
            }
        }
        send_json_response(error_response)


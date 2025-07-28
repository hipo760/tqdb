#!/usr/bin/python3
# -*- coding: utf-8 -*-   
"""
TQ Database Symbol Summary CGI Script

This CGI script provides a comprehensive summary of trading data for a given financial symbol.
It queries multiple Cassandra tables to retrieve tick data, second bars, minute bars, and symbol information.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- cassandra-driver
- python-dateutil

Usage:
    HTTP GET: /cgi-bin/qSymSummery.py?symbol=SYMBOL_CODE
    Example: /cgi-bin/qSymSummery.py?symbol=006207.TW

Returns:
    JSON response containing:
    - TickBeg: First 10 tick records (chronological order)
    - TickEnd: Last 10 tick records (reverse chronological order)
    - SecBeg: First 10 second bar records
    - SecEnd: Last 10 second bar records
    - MinBeg: First 10 minute bar records
    - MinEnd: Last 10 minute bar records
    - SymbolInfo: Symbol metadata information
"""

import sys
import json
import os
import urllib.parse
from cassandra.cluster import Cluster


# Default symbol for testing purposes
DEFAULT_SYMBOL = "006207.TW"


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

def get_symbol_summary(keyspace, symbol):
    """
    Retrieve comprehensive trading data summary for a given financial symbol.
    
    This function connects to the Cassandra database and queries multiple tables
    to provide a complete overview of trading data including tick data, second bars,
    minute bars, and symbol information.
    
    Args:
        keyspace (str): Cassandra keyspace name (e.g., 'tqdb1')
        symbol (str): Financial symbol to query (e.g., '006207.TW')
        
    Returns:
        dict: Dictionary containing trading data with the following keys:
            - TickBeg: First 10 tick records (chronological order)
            - TickEnd: Last 10 tick records (reverse chronological order) 
            - SecBeg: First 10 second bar records
            - SecEnd: Last 10 second bar records
            - MinBeg: First 10 minute bar records
            - MinEnd: Last 10 minute bar records
            - SymbolInfo: Symbol metadata information
    """
    # Initialize Cassandra cluster connection
    cluster = Cluster()
    session = cluster.connect(keyspace)
    all_data = {}

    # Query 1: Get first 10 tick records (chronological order)
    query_str = f"SELECT * FROM {keyspace}.tick WHERE symbol='{symbol}' ORDER BY datetime LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['TickBeg'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 2: Get last 10 tick records (reverse chronological order)
    query_str = f"SELECT * FROM {keyspace}.tick WHERE symbol='{symbol}' ORDER BY datetime DESC LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['TickEnd'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 3: Get first 10 second bar records
    query_str = f"SELECT * FROM {keyspace}.secbar WHERE symbol='{symbol}' ORDER BY datetime LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['SecBeg'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 4: Get last 10 second bar records
    query_str = f"SELECT * FROM {keyspace}.secbar WHERE symbol='{symbol}' ORDER BY datetime DESC LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['SecEnd'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 5: Get first 10 minute bar records
    query_str = f"SELECT * FROM {keyspace}.minbar WHERE symbol='{symbol}' ORDER BY datetime LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['MinBeg'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 6: Get last 10 minute bar records
    query_str = f"SELECT * FROM {keyspace}.minbar WHERE symbol='{symbol}' ORDER BY datetime DESC LIMIT 10;"
    ret_data = execute_query(session, query_str)
    all_data['MinEnd'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']

    # Query 7: Get symbol metadata information
    query_str = f"SELECT * FROM {keyspace}.symbol WHERE symbol='{symbol}';"
    ret_data = execute_query(session, query_str)
    all_data['SymbolInfo'] = ret_data['data'] if ret_data['Result'] == 'OK' else ['Exception!']
    
    # Close the database connection
    cluster.shutdown()
    
    return all_data


def parse_query_string():
    """
    Parse the CGI query string to extract the symbol parameter.
    
    Returns:
        str: The symbol parameter from the query string, or default symbol if not found
    """
    # Get query string from environment variable
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    query_params = {}
    
    # Parse each query parameter
    for query_string in query_strings.split("&"):
        if query_string.find("=") <= 0:
            continue
        key, value = query_string.split("=", 1)  # Split only on first '=' to handle values with '='
        query_params[key] = urllib.parse.unquote(value)
    
    # Return symbol parameter or default
    return query_params.get('symbol', DEFAULT_SYMBOL)


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
        # Parse the symbol from query string
        symbol = parse_query_string()
        
        # Get trading data summary for the symbol
        result = get_symbol_summary('tqdb1', symbol)
        
        # Send JSON response
        send_json_response(result)
        
    except Exception as e:
        # Handle any unexpected errors
        error_response = {
            'Result': f'Error! System exception: {str(e)}',
            'Detail': None
        }
        send_json_response(error_response)


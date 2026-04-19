#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TQ Database Symbol Information Query CGI Script

This CGI script retrieves symbol information from the TQ Database using the qsym utility.
It provides detailed symbol configuration data including trading parameters, market times,
and other symbol-specific metadata.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- qsym utility binary in tools directory
- Cassandra database with tqdb schema
- Access to /tmp directory for temporary file operations

Usage:
    HTTP GET: /cgi-bin/qsyminfo.py?symbol=SYMBOL_CODE
    
Parameters:
    - symbol: Financial symbol code to query (default: "ALL" for all symbols)

Examples:
    - /cgi-bin/qsyminfo.py?symbol=WTX (get info for WTX symbol)
    - /cgi-bin/qsyminfo.py?symbol=ALL (get info for all symbols)
    - /cgi-bin/qsyminfo.py (defaults to ALL symbols)

Returns:
    JSON response containing symbol information array with symbol configuration data
"""

import sys
import os
import subprocess
import json
import ast
import time
import datetime
import urllib.parse

# Configuration constants
CASSANDRA_IP = os.environ.get('CASSANDRA_HOST', 'cassandra-node')
CASSANDRA_PORT = os.environ.get('CASSANDRA_PORT', '9042')
CASSANDRA_DB = os.environ.get('CASSANDRA_KEYSPACE', 'tqdb1')
TOOLS_DIR = os.environ.get('TOOLS_DIR', '/opt/tqdb/tools/')

def parse_query_string():
    """
    Parse the CGI query string to extract the symbol parameter.
    
    Returns:
        str: The symbol parameter from the query string, or "ALL" if not specified
    """
    # Get query string from environment variable
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    query_params = {}
    
    # Parse each query parameter
    for query_string in query_strings.split("&"):
        if "=" not in query_string:
            continue
        key, value = query_string.split("=", 1)  # Split only on first '='
        query_params[key] = urllib.parse.unquote(value)
    
    # Return symbol parameter or default to "ALL"
    return query_params.get('symbol', 'ALL')


def query_symbol_info(symbol):
    """
    Query symbol information using the qsym utility and return parsed JSON data.
    
    Args:
        symbol (str): Symbol code to query ("ALL" for all symbols)
        
    Returns:
        list: List of symbol information objects
        
    Raises:
        subprocess.SubprocessError: If qsym command fails
        json.JSONDecodeError: If response is not valid JSON
        FileNotFoundError: If temporary file operations fail
    """
    # Generate unique temporary filename using PID and timestamp
    temp_file = f"/tmp/q1min.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"
    
    try:
        # Construct command to run Python qsym replacement
        # Format: python3 qsym.py <cassandra_ip> <port> <keyspace.table> <mode> <symbol> <limit> > <output_file>
        python_binaries_dir = os.path.join(TOOLS_DIR, '../python-binaries')
        command = f"python3 {python_binaries_dir}/qsym.py {CASSANDRA_IP} {CASSANDRA_PORT} {CASSANDRA_DB}.symbol 0 {symbol} 10000 > {temp_file}"
        
        # Execute the qsym Python script
        result = subprocess.call(
            command,
            shell=True,
            timeout=30  # Add timeout for safety
        )
        
        if result != 0:
            raise subprocess.SubprocessError(f"qsym command failed with return code {result}")
        
        # Read the JSON response from the temporary file
        with open(temp_file, 'r', encoding='utf-8') as fp:
            json_str = fp.read()
        
        # Clean up the temporary file
        os.remove(temp_file)
        
        # Parse response.
        # First, treat output as proper JSON. If legacy tooling returns Python literals,
        # fall back to ast.literal_eval without mutating the original payload.
        try:
            symbol_objects = json.loads(json_str)
        except json.JSONDecodeError:
            symbol_objects = ast.literal_eval(json_str)

        if not isinstance(symbol_objects, list):
            raise json.JSONDecodeError("Top-level symbol payload is not a list", str(symbol_objects), 0)
        
        # Sort symbols alphabetically by symbol name
        symbol_objects.sort(key=lambda x: x.get('symbol', '') if isinstance(x, dict) else '')
        
        return symbol_objects
        
    except subprocess.TimeoutExpired:
        # Clean up temp file on timeout
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise subprocess.SubprocessError("qsym command timed out")
        
    except Exception:
        # Clean up temp file on any other error
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise


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


def send_error_response(error_message, error_details=None):
    """
    Send JSON error response with error details.
    
    Args:
        error_message (str): Main error message
        error_details (str, optional): Additional error details for debugging
    """
    error_response = {
        'error': error_message,
        'status': 'failed'
    }
    
    if error_details:
        error_response['details'] = error_details
    
    send_json_response(error_response)

# Main CGI execution
if __name__ == "__main__":
    try:
        # Parse the symbol from query string
        symbol = parse_query_string()
        
        # Validate symbol parameter (basic security check)
        if not symbol or len(symbol) > 50:  # Reasonable length limit
            send_error_response("Invalid symbol parameter")
            sys.exit(1)
        
        # Query symbol information using qsym utility
        symbol_data = query_symbol_info(symbol)
        
        # Send successful JSON response
        send_json_response(symbol_data)
        
    except subprocess.SubprocessError as e:
        # Handle qsym utility execution errors
        send_error_response(
            "Failed to query symbol information", 
            f"qsym utility error: {str(e)}"
        )
        
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        send_error_response(
            "Invalid response format from symbol query", 
            f"JSON parsing error: {str(e)}"
        )
        
    except FileNotFoundError as e:
        # Handle file operation errors
        send_error_response(
            "File operation failed", 
            f"File error: {str(e)}"
        )
        
    except Exception as e:
        # Handle any other unexpected errors
        send_error_response(
            "System error occurred", 
            f"Unexpected error: {str(e)}"
        )
        
        # Optional: Log error to system log for debugging
        # You can uncomment the following lines if you want to log errors
        # import logging
        # logging.basicConfig(filename='/var/log/tqdb/qsyminfo.log', level=logging.ERROR)
        # logging.error(f"qsyminfo.py error: {str(e)}")

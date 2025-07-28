#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
TQ Database Symbol List Query CGI Script

This CGI script retrieves a complete list of symbols from the TQ Database using the qsym utility.
It provides symbol data in plain text format, typically used for populating dropdown lists,
autocomplete fields, or other symbol selection interfaces.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- qsym utility binary in tools directory
- Cassandra database with tqdb schema
- Access to /tmp directory for temporary file operations

Usage:
    HTTP GET: /cgi-bin/qsymbol.py
    
Parameters:
    None - always returns all symbols

Returns:
    Plain text response containing symbol information, one symbol per line
    Content-Type: text/plain
"""

import sys
import os
import subprocess
import time
import datetime

# Configuration constants
CASSANDRA_IP = "127.0.0.1"
CASSANDRA_PORT = "9042"
CASSANDRA_DB = "tqdb1"
TOOLS_DIR = '/home/tqdb/codes/tqdb/tools/'

def parse_query_string():
    """
    Parse the CGI query string (though this script doesn't use parameters).
    
    This function is kept for consistency with other CGI scripts and potential
    future enhancements that might require parameters.
    
    Returns:
        dict: Empty dictionary (no parameters currently used)
    """
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    query_params = {}
    
    # Parse query parameters (currently not used but kept for future extensibility)
    for query_string in query_strings.split("&"):
        if "=" in query_string:
            key, value = query_string.split("=", 1)
            query_params[key] = value
    
    return query_params


def query_all_symbols():
    """
    Query all symbols from the database using the qsym utility.
    
    This function uses the native qsym utility to efficiently retrieve
    all symbol information from the Cassandra database and returns it
    as raw text data.
    
    Returns:
        str: Raw symbol data as returned by qsym utility
        
    Raises:
        subprocess.SubprocessError: If qsym command fails
        FileNotFoundError: If temporary file operations fail
        IOError: If file read/write operations fail
    """
    # Generate unique temporary filename using PID and timestamp
    temp_file = f"/tmp/q1min.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"
    
    try:
        # Construct command to run qsym utility for all symbols
        # Format: ./qsym <cassandra_ip> <port> <keyspace.table> <mode> <symbol> <limit> > <output_file>
        # Mode 0 = query, Symbol "ALL" = all symbols, Limit 1 = ??? (legacy parameter)
        command = f"./qsym {CASSANDRA_IP} {CASSANDRA_PORT} {CASSANDRA_DB}.symbol 0 ALL 1 > {temp_file}"
        
        # Execute the qsym command in the tools directory
        result = subprocess.call(
            command,
            shell=True,
            cwd=TOOLS_DIR,
            timeout=30  # Add timeout for safety
        )
        
        if result != 0:
            raise subprocess.SubprocessError(f"qsym command failed with return code {result}")
        
        # Read the raw data from the temporary file
        with open(temp_file, 'r', encoding='utf-8') as fp:
            symbol_data = fp.read()
        
        # Clean up the temporary file
        os.remove(temp_file)
        
        return symbol_data
        
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


def send_text_response(data):
    """
    Send plain text response with proper HTTP headers.
    
    Args:
        data (str): Text data to send
    """
    # Send HTTP headers for plain text
    sys.stdout.write("Content-Type: text/plain; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    
    # Send the text data
    sys.stdout.write(data)
    sys.stdout.flush()


def send_error_response(error_message):
    """
    Send plain text error response.
    
    Args:
        error_message (str): Error message to display
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: text/plain; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    
    # Send error message
    sys.stdout.write(f"ERROR: {error_message}\n")
    sys.stdout.flush()


# Main CGI execution
if __name__ == "__main__":
    try:
        # Parse query string (for future extensibility, though not currently used)
        query_params = parse_query_string()
        
        # Query all symbols from the database
        symbol_data = query_all_symbols()
        
        # Send successful plain text response
        send_text_response(symbol_data)
        
    except subprocess.SubprocessError as e:
        # Handle qsym utility execution errors
        send_error_response(f"Failed to query symbols: {str(e)}")
        
    except FileNotFoundError as e:
        # Handle file operation errors
        send_error_response(f"File operation failed: {str(e)}")
        
    except IOError as e:
        # Handle I/O errors
        send_error_response(f"I/O error: {str(e)}")
        
    except Exception as e:
        # Handle any other unexpected errors
        send_error_response(f"System error: {str(e)}")
        
        # Optional: Log error to system log for debugging
        # You can uncomment the following lines if you want to log errors
        # import logging
        # logging.basicConfig(filename='/var/log/tqdb/qsymbol.log', level=logging.ERROR)
        # logging.error(f"qsymbol.py error: {str(e)}")

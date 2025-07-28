#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
TQ Database Symbol Update CGI Script

This CGI script handles symbol configuration updates in the TQ Database system.
It processes form data for symbol parameters and updates the Cassandra database
through the Sym2Cass.py utility script.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- Cassandra database with tqdb schema
- Sym2Cass.py utility script in tools directory

Usage:
    HTTP POST/GET: /cgi-bin/usymbol.py?sym=SYMBOL&desc=DESCRIPTION&bpv=BPV&mko=MKO&mkc=MKC&ssec=SSEC
    
Parameters:
    - sym: Symbol code (required)
    - desc: Symbol description 
    - bpv: Big Point Value (price movement value)
    - mko: Market Open time (seconds since midnight)
    - mkc: Market Close time (seconds since midnight)  
    - ssec: Session seconds (trading session duration)

Returns:
    HTML redirect to /esymbol.html after processing
"""

import sys
import os
import subprocess
import json
import urllib.parse

# Configuration constants for Cassandra connection
CASSANDRA_IP = "127.0.0.1"
CASSANDRA_PORT = "9042" 
CASSANDRA_DB = "tqdb1"

# Path to the tools directory containing Sym2Cass.py
TOOLS_DIR = '/home/tqdb/codes/tqdb/tools/'

def parse_query_string():
    """
    Parse the CGI query string to extract symbol parameters.
    
    Returns:
        tuple: (symbol_code, parameters_dict) where parameters_dict contains
               DESC, BPV, MKO, MKC, SSEC values
    """
    # Get query string from environment variable
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    
    # For testing: uncomment the line below and modify as needed
    # query_strings = "sym=WTX&desc=Taifex&bpv=200&mko=84500&mkc=134500"
    
    query_params = {}
    
    # Parse each query parameter
    for query_string in query_strings.split("&"):
        if query_string.find("=") <= 0:
            continue
        key, value = query_string.split("=", 1)  # Split only on first '='
        query_params[key] = urllib.parse.unquote(value)
    
    # Extract symbol code
    symbol = ''
    if 'sym' in query_params:
        symbol = query_params['sym']
    
    # Initialize default parameters for symbol configuration
    parameters = {
        'DESC': "",      # Symbol description
        'BPV': '0.0',    # Big Point Value (price movement value)
        'MKO': '0',      # Market Open time (seconds since midnight)
        'MKC': '0',      # Market Close time (seconds since midnight)  
        'SSEC': '0'      # Session seconds (trading session duration)
    }
    
    # Update parameters with values from query string
    if 'desc' in query_params:
        parameters['DESC'] = query_params['desc']
    if 'bpv' in query_params:
        parameters['BPV'] = query_params['bpv']
    if 'mko' in query_params:
        parameters['MKO'] = query_params['mko']
    if 'mkc' in query_params:
        parameters['MKC'] = query_params['mkc']
    if 'ssec' in query_params:
        parameters['SSEC'] = query_params['ssec']
    
    return symbol, parameters


def update_symbol_in_database(symbol, parameters):
    """
    Update symbol configuration in Cassandra database using Sym2Cass.py utility.
    
    Args:
        symbol (str): Symbol code to update
        parameters (dict): Dictionary containing symbol parameters
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    if not symbol:
        return False
    
    try:
        # Construct command to run Sym2Cass.py utility
        # Updated for Python 3 compatibility
        command = f"python3 Sym2Cass.py {CASSANDRA_IP} {CASSANDRA_PORT} '{CASSANDRA_DB}' '{symbol}' '{json.dumps(parameters)}' > /dev/null"
        
        # Execute the command in the tools directory
        result = subprocess.call(
            command, 
            shell=True, 
            cwd=TOOLS_DIR,
            timeout=30  # Add timeout for safety
        )
        
        return result == 0  # Return True if command succeeded
        
    except subprocess.TimeoutExpired:
        # Handle timeout case
        return False
    except Exception:
        # Handle other exceptions
        return False


def send_redirect_response():
    """
    Send HTTP redirect response to esymbol.html page.
    This redirects the user back to the symbol editing interface.
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: text/html\r\n")
    sys.stdout.write("\r\n")
    
    # Send HTML with JavaScript redirect
    html_content = """<html>
<head>
    <title>Symbol Update</title>
</head>
<body>
    <script type="text/javascript">
        // Redirect to symbol editing page
        window.location.href = '/esymbol.html';
    </script>
    <noscript>
        <p>Symbol update completed. <a href="/esymbol.html">Click here to continue</a></p>
    </noscript>
</body>
</html>"""
    
    sys.stdout.write(html_content)
    sys.stdout.write("\r\n")
    sys.stdout.flush()


def send_error_response(error_message):
    """
    Send HTTP error response with error details.
    
    Args:
        error_message (str): Error message to display
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: text/html\r\n")
    sys.stdout.write("\r\n")
    
    # Send HTML error page
    html_content = f"""<html>
<head>
    <title>Symbol Update Error</title>
</head>
<body>
    <h2>Error updating symbol</h2>
    <p>{error_message}</p>
    <p><a href="/esymbol.html">Return to symbol editor</a></p>
</body>
</html>"""
    
    sys.stdout.write(html_content)
    sys.stdout.write("\r\n")
    sys.stdout.flush()


# Main CGI execution
if __name__ == "__main__":
    try:
        # Parse query string parameters
        symbol, parameters = parse_query_string()
        
        # Validate that we have a symbol to work with
        if not symbol:
            send_error_response("No symbol specified. Please provide a 'sym' parameter.")
            sys.exit(1)
        
        # Attempt to update the symbol in the database
        success = update_symbol_in_database(symbol, parameters)
        
        if success:
            # Success: redirect to symbol editing page
            send_redirect_response()
        else:
            # Error: show error message
            send_error_response(f"Failed to update symbol '{symbol}' in database. Please check system logs.")
            
    except Exception as e:
        # Handle any unexpected errors
        error_msg = f"System error: {str(e)}"
        send_error_response(error_msg)
        
        # Optional: Log error to system log for debugging
        # You can uncomment the following lines if you want to log errors
        # import logging
        # logging.basicConfig(filename='/var/log/tqdb/usymbol.log', level=logging.ERROR)
        # logging.error(f"usymbol.py error: {str(e)}")

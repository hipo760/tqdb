#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
TQ Database Daily Data Query CGI Script

This CGI script provides daily-level historical trading data retrieval for the TQ Database system.
It generates daily OHLCV (Open, High, Low, Close, Volume) bar data by aggregating minute-level data
for specified symbols and date ranges, with support for market session configurations.

Key Features:
- Daily OHLCV bar data generation from minute-level aggregation
- Market session time configuration (Market Open/Close times)
- Automatic market session detection from symbol metadata
- Flexible output formats: gzipped text or CSV download
- Integration with TQ Database shell scripts and Cassandra queries

Market Session Support:
- MKO (Market Open): Start time for daily aggregation (HHMMSS format)
- MKC (Market Close): End time for daily aggregation (HHMMSS format)
- Automatic detection from symbol configuration in database
- Manual override via query parameters

Output Formats:
- Default: Gzipped text/plain format for web display
- CSV: Downloadable CSV file with headers for data analysis

Author: TQ Database Team
Compatible with: Python 3.x, Rocky Linux 9.0+, TQ Database Tools
"""

import time
import sys
import datetime
import os
import subprocess
import json
from urllib.parse import unquote


# Global configuration constants
CASSANDRA_IP = "127.0.0.1"  # Cassandra cluster IP address
CASSANDRA_PORT = "9042"  # Cassandra CQL port
CASSANDRA_DB = "tqdb1"  # TQ Database keyspace name

BIN_DIR = '/home/tqdb/codes/tqdb/tools/'  # TQ Database tools directory
DEFAULT_SYMBOL = "SIN"  # Default test symbol
DEFAULT_MK_OPEN = 0  # Default market open time (0 = auto-detect)
DEFAULT_MK_CLOSE = 0  # Default market close time (0 = auto-detect)
DEFAULT_TIME_OFFSET = 0  # Time offset for queries
LOCAL_TIME_OFFSET = 480  # Taiwan timezone offset (minutes)
DEFAULT_GZIP = 1  # Enable gzip compression by default
DEFAULT_REMOVE_FILE = 1  # Remove temporary files after processing
DEFAULT_BEGIN_DT = '2016-5-23 11:45:00'  # Default start datetime
DEFAULT_END_DT = '2016-5-23 21:46:00'  # Default end datetime
FILE_TYPE_GZIP = 0  # File type: gzipped text
FILE_TYPE_CSV = 1  # File type: CSV download


def get_market_session_times(symbol):
    """
    Retrieve market session times (open/close) for a symbol from database.
    
    Queries the symbol metadata in Cassandra to extract market session configuration
    including market open (MKO) and market close (MKC) times for daily aggregation.
    
    Args:
        symbol (str): Trading symbol to query for session times
        
    Returns:
        tuple: (market_open_time, market_close_time) as integers in HHMMSS format
               Returns (0, 0) if session times not found or on error
               
    Process:
        1. Creates temporary file for qsym tool output
        2. Executes qsym to query symbol metadata from Cassandra
        3. Parses JSON response for MKO/MKC values in keyval field
        4. Returns session times or defaults if not found
        
    Market Session Format:
        - MKO/MKC are stored as integers in HHMMSS format
        - Example: 084500 = 08:45:00 (8:45 AM)
        - Example: 134500 = 13:45:00 (1:45 PM)
        
    Note:
        Requires qsym binary tool in TQ Database tools directory
    """
    try:
        # Generate temporary file for qsym output
        tmp_file = f"/tmp/qsym.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"
        
        # Execute qsym to query symbol metadata
        cmd = f"./qsym {CASSANDRA_IP} {CASSANDRA_PORT} {CASSANDRA_DB}.symbol 0 '{symbol}' 1 > {tmp_file}"
        
        subprocess.run(
            cmd,
            shell=True,
            cwd=BIN_DIR,
            check=True,
            timeout=30  # 30 second timeout for metadata query
        )
        
        # Read and parse JSON response
        with open(tmp_file, 'rb') as fp:
            json_str = fp.read().decode('utf-8')
            
        # Clean up temporary file
        os.remove(tmp_file)
        
        # Parse JSON (handle single quotes in response)
        all_objs = json.loads(json_str.replace("'", '"'))
        
        # Extract market session times from metadata
        if (len(all_objs) > 0 and 
            'keyval' in all_objs[0] and 
            'MKC' in all_objs[0]['keyval'] and 
            'MKO' in all_objs[0]['keyval']):
            
            mk_open = int(all_objs[0]['keyval']['MKO'])
            mk_close = int(all_objs[0]['keyval']['MKC'])
            
            return (mk_open, mk_close)
        
        return (0, 0)  # No session times found
        
    except subprocess.TimeoutExpired:
        print(f"Warning: Market session query timeout for symbol {symbol}", file=sys.stderr)
        return (0, 0)
    except subprocess.CalledProcessError as e:
        print(f"Warning: Market session query failed for symbol {symbol}: {e}", file=sys.stderr)
        return (0, 0)
    except Exception as e:
        print(f"Warning: Market session detection failed for symbol {symbol}: {e}", file=sys.stderr)
        return (0, 0)


def generate_daily_data(symbol, begin_dt, end_dt, tmp_file, gzip_enabled, mk_open, mk_close):
    """
    Generate daily OHLCV data using TQ Database shell script.
    
    Executes the q1dayall.sh shell script to aggregate minute-level data
    into daily bars for the specified symbol and date range, using
    configured market session times.
    
    Args:
        symbol (str): Trading symbol to process
        begin_dt (str): Start datetime string
        end_dt (str): End datetime string
        tmp_file (str): Temporary file path for output
        gzip_enabled (int): Enable gzip compression (1=yes, 0=no)
        mk_open (int): Market open time in HHMMSS format
        mk_close (int): Market close time in HHMMSS format
        
    Process:
        1. Calls q1dayall.sh script with all parameters
        2. Script aggregates minute-level data within session times
        3. Generates daily OHLCV bars for each trading day
        4. Outputs to temporary file (optionally gzipped)
        
    Market Session Logic:
        - Only data between mk_open and mk_close times is included
        - Each day's open uses first minute's open in session
        - Each day's close uses last minute's close in session
        - High/Low are maximum/minimum within session
        - Volume is sum of all minute volumes in session
        
    Note:
        Requires q1dayall.sh script in BIN_DIR with execute permissions
    """
    try:
        cmd = f"./q1dayall.sh '{symbol}' '{begin_dt}' '{end_dt}' '{tmp_file}' '{gzip_enabled}' '{mk_open}' '{mk_close}'"
        
        subprocess.run(
            cmd,
            shell=True,
            cwd=BIN_DIR,
            check=True,
            timeout=600  # 10 minute timeout for daily aggregation
        )
        
    except subprocess.TimeoutExpired:
        raise Exception("Daily data generation timeout (10 minutes)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Daily data generation failed: {e}")
    except Exception as e:
        raise Exception(f"Daily data generation error: {e}")


def output_response_data(tmp_file, symbol, file_type, gzip_enabled, remove_file):
    """
    Output the generated daily data file as HTTP response.
    
    Sends the processed daily data to the client with appropriate
    HTTP headers for content type, encoding, and disposition.
    
    Args:
        tmp_file (str): Path to temporary data file
        symbol (str): Symbol name for filename
        file_type (int): Output format (0=gzip text, 1=CSV)
        gzip_enabled (int): Gzip compression flag
        remove_file (int): Remove temp file flag (1=yes, 0=no)
        
    HTTP Headers:
        - Content-Type: text/plain or text/csv
        - Content-Encoding: gzip (if enabled)
        - Content-Length: File size
        - Content-Disposition: attachment (for CSV downloads)
        
    Data Format:
        - Text: Raw daily bar data from TQ Database tools
        - CSV: Daily OHLCV data in structured format
        
    Process:
        1. Set appropriate HTTP headers
        2. Stream file contents to stdout
        3. Clean up temporary file if requested
    """
    try:
        # Adjust filename for gzip
        actual_file = f"{tmp_file}.gz" if gzip_enabled == 1 else tmp_file
        
        # Set HTTP headers based on compression and file type
        if gzip_enabled == 1:
            file_size = os.path.getsize(actual_file)
            sys.stdout.write(f"Content-Length: {file_size}\r\n")
            sys.stdout.write("Content-Encoding: gzip\r\n")
        
        if file_type == FILE_TYPE_GZIP:
            sys.stdout.write("Content-Type: text/plain\r\n")
        else:
            sys.stdout.write("Content-Type: text/csv\r\n")
            sys.stdout.write(f"Content-Disposition: attachment; filename=\"{symbol}.1day.csv\"\r\n")
        
        sys.stdout.write("\r\n")
        
        # Stream file contents
        with open(actual_file, 'rb') as fp:
            data = fp.read()
            # Write binary data to stdout buffer
            sys.stdout.buffer.write(data)
            
        sys.stdout.flush()
        
        # Clean up temporary file
        if remove_file == 1:
            if os.path.exists(actual_file):
                os.remove(actual_file)
            # Also remove uncompressed version if it exists
            if gzip_enabled == 1 and os.path.exists(tmp_file):
                os.remove(tmp_file)
                
    except Exception as e:
        # Output error response
        sys.stdout.write("Content-Type: text/plain\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(f"Error outputting data: {e}\r\n")
        sys.stdout.flush()


def parse_query_parameters():
    """
    Parse CGI query string parameters for daily data request.
    
    Returns:
        dict: Parsed parameters containing:
            - symbol: Trading symbol
            - timeoffset: Time offset for queries
            - BEG: Begin datetime string
            - END: End datetime string
            - csv: CSV format flag (1=CSV download, 0=text)
            - MKO: Market open time override (HHMMSS format)
            - MKC: Market close time override (HHMMSS format)
            
    Query String Examples:
        ?symbol=AAPL&BEG=2024-01-01&END=2024-12-31
        ?symbol=SPY&csv=1&MKO=093000&MKC=160000
        ?symbol=QQQ&BEG=2024-01-01&END=2024-01-31&csv=1
        
    Market Session Override:
        - MKO/MKC parameters override database session times
        - Format: HHMMSS (e.g., 093000 = 09:30:00)
        - Useful for custom session analysis
    """
    query_string = os.environ.get("QUERY_STRING", "NA=NA")
    params = {}
    
    # Parse each parameter from query string
    for qs in query_string.split("&"):
        if qs.find("=") <= 0:
            continue
        key, value = qs.split("=", 1)
        params[key] = unquote(value)
    
    return params


def process_daily_data_request():
    """
    Main processing function for daily data CGI requests.
    
    This is the legacy function name maintained for compatibility.
    Handles the complete workflow from parameter parsing to data output.
    
    Process:
        1. Parse market session parameters or detect from database
        2. Generate unique temporary file path
        3. Execute daily data generation
        4. Output HTTP response with data
        
    Global Variables:
        Uses and modifies several global configuration variables
        for backward compatibility with original script structure.
        
    Error Handling:
        - Graceful handling of market session detection failures
        - Timeout protection for data generation
        - Proper cleanup of temporary files
    """
    # Access global variables (legacy structure)
    global mapQS, iMkO, iMkC, iRemoveQfile, szSymbol, begDT, endDT, iGZip, fileType
    
    try:
        # Generate unique temporary file path
        tmp_file = f"/tmp/q1day.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"
        
        # Check for market session time overrides in parameters
        if 'MKO' in mapQS and 'MKC' in mapQS:
            iMkO = int(mapQS['MKO'])
            iMkC = int(mapQS['MKC'])
        
        # Auto-detect market session times if not provided
        if iMkO == 0 and iMkC == 0:
            iMkO, iMkC = get_market_session_times(szSymbol)
        
        # Generate daily data using shell script
        generate_daily_data(szSymbol, begDT, endDT, tmp_file, iGZip, iMkO, iMkC)
        
        # Output response data
        output_response_data(tmp_file, szSymbol, fileType, iGZip, iRemoveQfile)
        
    except Exception as e:
        # Output error response
        sys.stdout.write("Content-Type: text/plain\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(f"Error processing daily data request: {e}\r\n")
        sys.stdout.flush()


def main():
    """
    Main CGI execution function for daily data queries.
    
    Process:
        1. Parse query string parameters
        2. Configure global variables (legacy structure)
        3. Process daily data request
        
    Global Configuration:
        - Maintains original global variable structure for compatibility
        - Applies parameter overrides to global settings
        - Supports both legacy and modern parameter handling
        
    Legacy Support:
        - Preserves original function names and variable structure
        - Maintains backward compatibility with existing clients
        - Uses global variables as in original implementation    """
    # Global variable declarations (legacy structure)
    global mapQS, szSymbol, timeoffset, begDT, endDT, fileType, iGZip, iMkO, iMkC, iRemoveQfile
    
    # Initialize global variables with defaults
    mapQS = {}
    szSymbol = DEFAULT_SYMBOL
    timeoffset = DEFAULT_TIME_OFFSET
    iMkO = DEFAULT_MK_OPEN
    iMkC = DEFAULT_MK_CLOSE
    iGZip = DEFAULT_GZIP
    iRemoveQfile = DEFAULT_REMOVE_FILE
    begDT = DEFAULT_BEGIN_DT
    endDT = DEFAULT_END_DT
    fileType = FILE_TYPE_GZIP
    
    try:
        # Parse CGI parameters
        params = parse_query_parameters()
        mapQS = params  # Store in global for legacy compatibility
        
        # Apply parameter values to global variables
        if 'symbol' in params:
            szSymbol = params['symbol']
        if 'timeoffset' in params:
            # Time offset parameter available for future use
            pass  # Currently not used in processing logic
        if 'BEG' in params:
            begDT = params['BEG']
        if 'END' in params:
            endDT = params['END']
        if 'csv' in params and params['csv'] == '1':
            fileType = FILE_TYPE_CSV
            iGZip = 0  # Disable gzip for CSV downloads
        
        # Process the daily data request
        process_daily_data_request()
        
    except Exception as e:
        # Output error response
        sys.stdout.write("Content-Type: text/plain\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(f"Error in main execution: {e}\r\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

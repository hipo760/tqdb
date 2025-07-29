#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
TQ Database Second-Level Data Query CGI Script

This CGI script provides second-level historical trading data retrieval for the TQ Database system.
It generates second-level bar data (1-second intervals) for specified symbols and date ranges,
supporting both regular symbols and custom multi-leg symbols.

Key Features:
- Second-level OHLCV (Open, High, Low, Close, Volume) bar data generation
- Support for custom multi-leg symbols (prefixed with ^^)
- Flexible output formats: gzipped text or CSV download
- Date range validation with automatic first valid date detection
- Integration with TQ Database shell scripts and tools

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
from urllib.parse import quote, unquote
from urllib.request import urlopen


# Global configuration constants
BIN_DIR = '/home/tqdb/codes/tqdb/tools/'  # TQ Database tools directory
DEFAULT_SYMBOL = "WTF.506"  # Default test symbol
DEFAULT_TIME_OFFSET = 0  # Time offset for queries
LOCAL_TIME_OFFSET = 480  # Taiwan timezone offset (minutes)
DEFAULT_GZIP = 1  # Enable gzip compression by default
DEFAULT_REMOVE_FILE = 1  # Remove temporary files after processing
DEFAULT_BEGIN_DT = '2016-5-23 11:45:00'  # Default start datetime
DEFAULT_END_DT = '2016-5-23 21:46:00'  # Default end datetime
FILE_TYPE_GZIP = 0  # File type: gzipped text
FILE_TYPE_CSV = 1  # File type: CSV download


def get_first_valid_datetime(symbol, begin_dt_str, end_dt_str):
    """
    Retrieve the first valid datetime for a symbol within a date range.
    
    This function queries the qSymRefPrc.py service to find the earliest valid
    trading data for a symbol, ensuring data availability for the requested range.
    
    Args:
        symbol (str): Trading symbol to query
        begin_dt_str (str): Start datetime string (YYYY-MM-DD HH:MM:SS)
        end_dt_str (str): End datetime string (YYYY-MM-DD HH:MM:SS)
        
    Returns:
        str: Validated begin datetime string with first available data
        
    Process:
        1. Query reference price service for begin and end dates
        2. Check if valid data exists in SecBar format
        3. If same reference found for both dates, use that as start
        4. Return original begin date if validation fails
        
    Note:
        Used to ensure queries don't start before data availability
    """
    try:
        target_type = 'SecBar'
        begin_ref_dt, end_ref_dt = (-1, -1)
        
        # Query for begin date reference price
        url = f'http://127.0.0.1/cgi-bin/qSymRefPrc.py?symbol={quote(symbol)}&qType=LastValidPrc&qDatetime={quote(begin_dt_str)}'
        
        with urlopen(url) as response:
            obj = json.loads(response.read().decode('utf-8'))
            
        if obj is not None and target_type in obj and obj[target_type][0] is not None:
            begin_ref_dt = obj[target_type][0]['datetime']
        
        # Query for end date reference price
        url = f'http://127.0.0.1/cgi-bin/qSymRefPrc.py?symbol={quote(symbol)}&qType=LastValidPrc&qDatetime={quote(end_dt_str)}'
        
        with urlopen(url) as response:
            obj = json.loads(response.read().decode('utf-8'))
            
        if obj is not None and target_type in obj and obj[target_type][0] is not None:
            end_ref_dt = obj[target_type][0]['datetime']
        
        # If both dates have same reference, use reference as start
        if begin_ref_dt != -1 and begin_ref_dt == end_ref_dt:
            begin_ref_dt_obj = datetime.datetime.strptime(begin_ref_dt, "%Y-%m-%d %H:%M:%S")
            begin_ref_dt_epoch = (begin_ref_dt_obj - datetime.datetime(1970, 1, 1)).total_seconds()
            dt_first_valid = datetime.datetime.fromtimestamp(begin_ref_dt_epoch)
            begin_dt_str = dt_first_valid.strftime("%Y-%m-%d %H:%M:%S")
            
        return begin_dt_str
        
    except Exception as e:
        # Return original begin date if validation fails
        print(f"Warning: Date validation failed: {e}", file=sys.stderr)
        return begin_dt_str


def download_from_tqdb(symbol, begin_dt, end_dt, tmp_file, gzip_enabled):
    """
    Download second-level data from TQ Database using shell script.
    
    Executes the q1secall.sh shell script to extract second-level bar data
    from the TQ Database for regular trading symbols.
    
    Args:
        symbol (str): Trading symbol to download
        begin_dt (str): Start datetime string
        end_dt (str): End datetime string  
        tmp_file (str): Temporary file path for output
        gzip_enabled (int): Enable gzip compression (1=yes, 0=no)
        
    Process:
        1. Calls q1secall.sh script with parameters
        2. Script queries Cassandra database
        3. Generates second-level OHLCV bars
        4. Outputs to temporary file (optionally gzipped)
        
    Note:
        Requires q1secall.sh script in BIN_DIR with execute permissions
    """
    try:
        cmd = f"./q1secall.sh '{symbol}' '{begin_dt}' '{end_dt}' '{tmp_file}' '{gzip_enabled}'"
        
        subprocess.run(
            cmd,
            shell=True,
            cwd=BIN_DIR,
            check=True,
            timeout=300  # 5 minute timeout
        )
        
    except subprocess.TimeoutExpired:
        raise Exception("TQ Database query timeout (5 minutes)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"TQ Database query failed: {e}")
    except Exception as e:
        raise Exception(f"Download error: {e}")


def process_custom_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled):
    """
    Process custom multi-leg symbol data using specialized tool.
    
    Handles custom symbols (prefixed with ^^) that represent multi-leg
    trading instruments requiring special processing logic.
    
    Args:
        symbol (str): Custom symbol starting with ^^
        begin_dt (str): Start datetime string
        end_dt (str): End datetime string
        tmp_file (str): Temporary file path for output
        gzip_enabled (int): Enable gzip compression (1=yes, 0=no)
        
    Process:
        1. Creates profile name from symbol (removes ^^ prefix)
        2. Calls q1min_multileg.py script in tqdbPlus directory
        3. Processes multi-leg trading data
        4. Outputs second-level aggregated data
        
    Note:
        Requires tqdbPlus directory with q1min_multileg.py script
    """
    try:
        # Create profile name by removing ^^ prefix
        profile = f'profile.ml.{symbol[2:]}'
        
        cmd = f"python ./q1min_multileg.py '{profile}' '{begin_dt}' '{end_dt}' '{tmp_file}' '{gzip_enabled}'"
        custom_dir = f"{BIN_DIR}/../../tqdbPlus/"
        
        subprocess.run(
            cmd,
            shell=True,
            cwd=custom_dir,
            check=True,
            timeout=300  # 5 minute timeout
        )
        
    except subprocess.TimeoutExpired:
        raise Exception("Custom symbol processing timeout (5 minutes)")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Custom symbol processing failed: {e}")
    except Exception as e:
        raise Exception(f"Custom symbol error: {e}")


def output_response_data(tmp_file, symbol, file_type, gzip_enabled, remove_file):
    """
    Output the generated data file as HTTP response.
    
    Sends the processed second-level data to the client with appropriate
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
        
    Process:
        1. Set appropriate HTTP headers
        2. Add CSV header row if CSV format
        3. Stream file contents to stdout
        4. Clean up temporary file if requested
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
            sys.stdout.write(f"Content-Disposition: attachment; filename=\"{symbol}.1sec.csv\"\r\n")
          # CRITICAL: Ensure headers are terminated before any content
        sys.stdout.write("\r\n")
        sys.stdout.flush()
        
        # Add CSV header if CSV format and not gzipped
        if file_type == FILE_TYPE_CSV and gzip_enabled == 0:
            sys.stdout.write("YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol\r\n")
            sys.stdout.flush()
        
        # Stream file contents
        with open(actual_file, 'rb') as fp:
            data = fp.read()
            # Write binary data to stdout buffer
            sys.stdout.buffer.write(data)
            
        sys.stdout.buffer.flush()
        
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
    Parse CGI query string parameters for second-level data request.
    
    Returns:
        dict: Parsed parameters containing:
            - symbol: Trading symbol
            - timeoffset: Time offset for queries
            - BEG: Begin datetime string
            - END: End datetime string  
            - csv: CSV format flag (1=CSV download, 0=text)
            - MUSTHAVEBEG/MOSTHAVEBEG: Date validation flags
            
    Query String Examples:
        ?symbol=AAPL&BEG=2024-01-01%2009:30:00&END=2024-01-01%2016:00:00
        ?symbol=^^CUSTOM&csv=1&BEG=2024-01-01%2009:30:00
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


def normalize_date_format(date_str):
    """
    Normalize date string to ensure proper zero-padding format.
    
    Converts dates like '2025-7-26' to '2025-07-26' format to ensure
    proper parsing by downstream tools and database queries.
    
    Args:
        date_str (str): Date string in various formats
        
    Returns:
        str: Normalized date string with zero-padding
    """
    try:
        # Handle different input formats
        if date_str.count('-') == 2:
            parts = date_str.split()
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            
            # Split date components
            year, month, day = date_part.split('-')
            
            # Zero-pad month and day
            month = month.zfill(2)
            day = day.zfill(2)
            
            # Reconstruct normalized date
            return f"{year}-{month}-{day} {time_part}"
        
        return date_str
        
    except Exception as e:
        print(f"Warning: Date normalization failed: {e}", file=sys.stderr)
        return date_str


def main():
    """
    Main CGI execution function for second-level data queries.
    
    Process:
        1. Parse query string parameters
        2. Configure output format and options
        3. Validate date range (if requested)
        4. Generate temporary file path
        5. Process data (regular or custom symbol)
        6. Output HTTP response with data
        
    Error Handling:
        - Timeout protection for long-running queries
        - Graceful handling of missing data
        - Proper cleanup of temporary files
        
    Global Variables:
        Uses and modifies global configuration variables based on parameters
    """
    # Global configuration variables
    global BIN_DIR, DEFAULT_SYMBOL
      # Initialize default values
    symbol = DEFAULT_SYMBOL
    gzip_enabled = DEFAULT_GZIP
    remove_file = DEFAULT_REMOVE_FILE
    begin_dt = DEFAULT_BEGIN_DT
    end_dt = DEFAULT_END_DT
    file_type = FILE_TYPE_GZIP
    
    try:
        # Parse CGI parameters
        params = parse_query_parameters()
          # Apply parameter values
        if 'symbol' in params:
            symbol = params['symbol']
        if 'timeoffset' in params:
            # Time offset parameter available for future use
            pass  # Currently not used in processing logic        if 'BEG' in params:
            begin_dt = normalize_date_format(params['BEG'])
        if 'END' in params:
            end_dt = normalize_date_format(params['END'])
        if 'csv' in params and params['csv'] == '1':
            file_type = FILE_TYPE_CSV
            gzip_enabled = 0  # Disable gzip for CSV downloads
        
        # Check if symbol is custom (multi-leg)
        is_custom_symbol = symbol.startswith('^^')
        
        # Validate date range for regular symbols (if requested)
        if not is_custom_symbol:
            # Handle typos in parameter names (MOSTHAVEBEG/MUSTHAVEBEG)
            if ('MOSTHAVEBEG' in params and params['MOSTHAVEBEG'] != '0') or \
               ('MUSTHAVEBEG' in params and params['MUSTHAVEBEG'] != '0'):
                begin_dt = get_first_valid_datetime(symbol, begin_dt, end_dt)
        
        # Normalize date format
        begin_dt = normalize_date_format(begin_dt)
        end_dt = normalize_date_format(end_dt)
        
        # Generate unique temporary file path
        tmp_file = f"/tmp/q1sec.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"
        
        # Process data based on symbol type
        if is_custom_symbol:
            process_custom_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled)
        else:
            download_from_tqdb(symbol, begin_dt, end_dt, tmp_file, gzip_enabled)
        
        # Output response data
        output_response_data(tmp_file, symbol, file_type, gzip_enabled, remove_file)
        
    except Exception as e:
        # Output error response
        sys.stdout.write("Content-Type: text/plain\r\n")
        sys.stdout.write("\r\n")
        sys.stdout.write(f"Error processing request: {e}\r\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

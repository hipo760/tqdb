#!/usr/bin/env python3
"""
TQDB 1-Minute Data Import Checker CGI Script

This CGI script processes uploaded CSV files containing 1-minute trading data (OHLCV format),
validates the data format, handles timezone conversion, and prepares the data for import
into a Cassandra database.

The script supports multiple date/time formats and can convert timezones if requested.
It returns either HTML or JSON responses based on query parameters.

Author: TQDB Development Team
Date: 2024
"""

import time
import sys
import os
import stat
import subprocess
import json
import cgi
import cgitb

# Enable CGI error reporting for debugging
cgitb.enable()

# Configuration constants
CASSANDRA_IP = "127.0.0.1"
CASSANDRA_DB = "tqdb1"

# Global parameter storage for request data
param = {
    'Sym': '',         # Trading symbol
    'Lines': [],       # Parsed CSV data lines
    'Log': '',         # Log messages
    'tzFromTo': None   # Timezone conversion parameters
}

# Generate unique import ticket based on timestamp and process ID
import_ticket = f"i1min.{int(time.time())}.{os.getpid()}"
def process_post_data():
    """
    Process POST data from CGI form submission.
    
    Handles:
    - Symbol extraction from form data
    - Timezone conversion settings
    - CSV file upload and parsing
    - Date/time format detection and normalization
    
    Supports multiple date formats:
    - YYYYMMDD (0), YYYY-MM-DD (1), YYYY/MM/DD (2), MM/DD/YYYY (3)
    
    Supports multiple time formats:
    - HHMMSS (0), HH:MM:SS (1), HH:MM (2)
    """
    global param
    form = cgi.FieldStorage()

    # Extract trading symbol from form
    sym = form.getvalue('sym')
    if sym:
        param['Sym'] = sym

    # Handle timezone conversion settings
    tz_conv = form.getvalue('tzConv')
    tz_select = form.getvalue('tzSelect')

    if tz_conv == 'on' and tz_select is not None and tz_select != '':
        param['tzFromTo'] = [tz_select, 'local']
        try:
            # Try to read the system timezone
            with open('/etc/timezone', 'r', encoding='utf-8') as f:
                param['tzFromTo'][1] = f.readline().strip()
        except (IOError, OSError):
            # Use 'local' as fallback if timezone file is not accessible
            pass
    else:
        param['tzFromTo'] = None

    # Process uploaded CSV file
    if 'file' in form:
        fileitem = form['file']
        
        # Date format detection flags
        # 0=YYYYMMDD, 1=YYYY-MM-DD, 2=YYYY/MM/DD, 3=MM/DD/YYYY
        date_format_type = 0
        
        # Time format detection flags  
        # 0=HHMMSS, 1=HH:MM:SS, 2=HH:MM
        time_format_type = 0
        
        while True:
            # Read line from uploaded file (binary mode in Python 3)
            line = fileitem.file.readline()
            if not line:
                break
                
            # Decode bytes to string and split CSV
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            
            onedata = line.strip('\n').strip('\r').split(',')
            
            # Validate minimum required fields (Date, Time, Open, High, Low, Close)
            if len(onedata) >= 6:
                # First field should be date (length > 8 and starts with digit)
                if len(onedata[0]) < 8:
                    continue
                if onedata[0][0] < '0' or onedata[0][0] > '9':
                    continue

                # Auto-detect date and time formats from first valid line
                if len(param['Lines']) == 0:
                    # Detect date format
                    if len(onedata[0].split('-')) == 3:
                        date_format_type = 1  # YYYY-MM-DD
                    elif len(onedata[0].split('/')) == 3:
                        date_format_type = 2  # YYYY/MM/DD or MM/DD/YYYY
                        try:
                            # Check if year is in last position (MM/DD/YYYY format)
                            if int(onedata[0].split('/')[2]) > 1900:
                                date_format_type = 3
                        except ValueError:
                            pass

                    # Detect time format
                    if len(onedata[1].split(':')) == 3:
                        time_format_type = 1  # HH:MM:SS
                    elif len(onedata[1].split(':')) == 2:
                        time_format_type = 2  # HH:MM

                # Normalize date format to YYYYMMDD
                if date_format_type == 1:  # YYYY-MM-DD
                    date_parts = onedata[0].split('-')
                    onedata[0] = f"{int(date_parts[0]):04d}{int(date_parts[1]):02d}{int(date_parts[2]):02d}"
                elif date_format_type == 2:  # YYYY/MM/DD
                    date_parts = onedata[0].split('/')
                    onedata[0] = f"{int(date_parts[0]):04d}{int(date_parts[1]):02d}{int(date_parts[2]):02d}"
                elif date_format_type == 3:  # MM/DD/YYYY
                    date_parts = onedata[0].split('/')
                    onedata[0] = f"{int(date_parts[2]):04d}{int(date_parts[0]):02d}{int(date_parts[1]):02d}"

                # Normalize time format to HHMMSS
                if time_format_type == 1:  # HH:MM:SS
                    time_parts = onedata[1].split(':')
                    onedata[1] = f"{int(time_parts[0]):02d}{int(time_parts[1]):02d}{int(time_parts[2]):02d}"
                elif time_format_type == 2:  # HH:MM
                    time_parts = onedata[1].split(':')
                    onedata[1] = f"{int(time_parts[0]):02d}{int(time_parts[1]):02d}00"

                # Add default volume if missing (6 fields = DTOHLC, need to add V)
                if len(onedata) == 6:
                    onedata.append('0')
                    
                param['Lines'].append(onedata)

    # Handle timezone conversion if requested
    if param['tzFromTo'] is not None:
        # Write data to temporary file for timezone conversion
        tz_from_file = f'/tmp/{import_ticket}.tzFrom'
        with open(tz_from_file, 'w', encoding='utf-8') as csv_file:
            for onedata in param['Lines']:
                csv_file.write(f"{','.join(onedata)}\n")

        # Execute timezone conversion script
        tz_to_file = f'/tmp/{import_ticket}.tzTo'
        run_cmd = (f"/home/tqdb/codes/tqdb/tools/csvtzconv.py "
                  f"'{param['tzFromTo'][0]}' '{param['tzFromTo'][1]}' "
                  f"'{tz_from_file}' > '{tz_to_file}'")
        param['tzConvertCmd'] = run_cmd
        subprocess.call(run_cmd, shell=True)
        
        # Read converted data back
        param['Lines'] = []
        try:
            with open(tz_to_file, 'r', encoding='utf-8') as csv_file:
                for line in csv_file.readlines():
                    param['Lines'].append(line.strip('\n').strip('\r').split(','))
        except (IOError, OSError):
            # Handle file read errors gracefully
            pass

def prepare_import():
    """
    Prepare import scripts and files for Cassandra database import.
    
    Creates:
    1. Shell command file with environment setup and import command
    2. CSV data file with processed trading data
    
    The command file sets up the TQDB environment and calls Min2Cass.py
    to import the data into Cassandra.
    """
    global param
    
    # Generate file paths for command and data files
    cmd_file = f'/tmp/{import_ticket}.cmd'
    csv_file = f'/tmp/{import_ticket}.csv'
    
    # Create shell command file
    with open(cmd_file, 'w', encoding='utf-8') as cmd:
        cmd.write('. /etc/profile.d/profile_tqdb.sh\n')
        cmd.write('TQDB="tqdb1"\n')
        
        # Escape special characters in symbol name
        sym = param['Sym']
        sym = sym.replace('$', '\\$')
        cmd.write(f'SYMBOL="{sym}"\n')
        cmd.write('NDAYAGO=0\n')
        
        # Create import command using Min2Cass.py
        cmd.write(f'CMD="cat /tmp/{import_ticket}.csv | '
                 f'python3 -u $TQDB_DIR/tools/Min2Cass.py '
                 f'$CASS_IP $CASS_PORT $TQDB \'$SYMBOL\'"\n')
        
        # Add logging
        cmd.write(f'echo "Ready to run: "$CMD > /tmp/{import_ticket}.log\n')
        cmd.write(f'eval $CMD >> /tmp/{import_ticket}.log\n')
        cmd.write(f'echo "Importing finish!" >> /tmp/{import_ticket}.log\n')
    
    # Make command file executable
    os.chmod(cmd_file, os.stat(cmd_file).st_mode | stat.S_IEXEC)
    
    # Create CSV data file
    with open(csv_file, 'w', encoding='utf-8') as csv_output:
        for onedata in param['Lines']:
            csv_output.write(','.join(onedata) + '\n')


def build_response_data():
    """
    Build response data structure containing processed trading data.
    
    Returns a dictionary with:
    - symbol: Trading symbol
    - totalCnt: Total number of data rows
    - importTicket: Unique identifier for this import
    - timezone info if conversion was performed
    - first100Rows: First 100 rows of data for preview
    - last100Rows: Last 100 rows of data for preview (if total > 100)
    """
    ret_obj = {
        'symbol': param['Sym'],
        'totalCnt': len(param['Lines']),
        'importTicket': import_ticket,
        'tzFrom': '',
        'tzTo': '',
        'first100Rows': [],
        'last100Rows': [],
        'tzConvertCmd': ''
    }
    
    # Add timezone conversion info if applicable
    if param['tzFromTo'] is not None:
        ret_obj['tzFrom'] = param['tzFromTo'][0]
        ret_obj['tzTo'] = param['tzFromTo'][1]
        ret_obj['tzConvertCmd'] = param.get('tzConvertCmd', '')
    
    # Process data rows for preview (first 100 and last 100)
    cnt = 0
    for onedata in param['Lines']:
        cnt += 1
        if cnt <= 100 or cnt >= ret_obj['totalCnt'] - 100:
            # Create DTOHLCV (Date, Time, Open, High, Low, Close, Volume) record
            dtohlcv = {
                'D': None, 'T': None, 'O': None, 'H': None, 
                'L': None, 'C': None, 'V': 0, 'Idx': cnt
            }
            tags = ['D', 'T', 'O', 'H', 'L', 'C', 'V']
            
            # Map data to DTOHLCV fields
            for i in range(min(len(tags), len(onedata))):
                try:
                    dtohlcv[tags[i]] = onedata[i]
                except IndexError:
                    pass
            
            dtohlcv['Idx'] = cnt
            
            # Add to appropriate preview list
            if cnt <= 100:
                ret_obj['first100Rows'].append(dtohlcv)
            if ret_obj['totalCnt'] > 100 and cnt >= ret_obj['totalCnt'] - 100:
                ret_obj['last100Rows'].append(dtohlcv)
    
    return ret_obj


def parse_query_string():
    """
    Parse URL query string parameters.
    
    Returns:
        dict: Dictionary of query string parameters
    """
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    map_qs = {}
    
    for qs in query_strings.split("&"):
        if '=' in qs:
            key, value = qs.split("=", 1)
            map_qs[key] = value
    
    return map_qs


def output_html_response(ret_obj):
    """
    Generate HTML response for web browser display.
    
    Args:
        ret_obj (dict): Response data containing trading data and metadata
    """
    sys.stdout.write("Content-Type: text/html\r\n")
    sys.stdout.write("\r\n")
    
    if ret_obj['symbol'] == '':
        sys.stdout.write('<html><body>No Symbol specified!</body></html>')
        return
    
    sys.stdout.write('<html><body>')
    sys.stdout.write("<link rel='stylesheet' type='text/css' href='/style.css'>")
    sys.stdout.write(f"Symbol: {ret_obj['symbol']}, "
                    f"Total Lines: {ret_obj['totalCnt']}, "
                    f"Import Ticket: {ret_obj['importTicket']}<br>\n")
    
    # Show timezone conversion info if applicable
    if ret_obj['tzFrom'] != '':
        sys.stdout.write(f'<font color="#f00">Convert Timezone: '
                        f'{ret_obj["tzFrom"]} ---> {ret_obj["tzTo"]}</font><br>\n')
    
    # Create data table
    sys.stdout.write('<table>\n')
    sys.stdout.write('<tr class="grayThing smallfont">'
                    '<td>No</td><td>Date</td><td>Time</td><td>Open</td>'
                    '<td>High</td><td>Low</td><td>Close</td><td>Vol</td></tr>\n')
    
    # Display first 100 rows
    for dtohlcv in ret_obj['first100Rows']:
        sys.stdout.write('<tr onmouseover="this.className=\'yellowThing\';" '
                        'onmouseout="this.className=\'whiteThing\';">')
        sys.stdout.write(f'<td>#{dtohlcv["Idx"]}</td>'
                        f'<td>{dtohlcv["D"]}</td>'
                        f'<td>{dtohlcv["T"]}</td>'
                        f'<td>{dtohlcv["O"]}</td>'
                        f'<td>{dtohlcv["H"]}</td>'
                        f'<td>{dtohlcv["L"]}</td>'
                        f'<td>{dtohlcv["C"]}</td>'
                        f'<td>{dtohlcv["V"]}</td></tr>\n')
    
    # Add separator and last 100 rows if applicable
    if len(ret_obj['last100Rows']) > 0:
        sys.stdout.write('<tr><td colspan="8">...</td></tr>\n')
        for dtohlcv in ret_obj['last100Rows']:
            sys.stdout.write('<tr onmouseover="this.className=\'yellowThing\';" '
                            'onmouseout="this.className=\'whiteThing\';">')
            sys.stdout.write(f'<td>#{dtohlcv["Idx"]}</td>'
                            f'<td>{dtohlcv["D"]}</td>'
                            f'<td>{dtohlcv["T"]}</td>'
                            f'<td>{dtohlcv["O"]}</td>'
                            f'<td>{dtohlcv["H"]}</td>'
                            f'<td>{dtohlcv["L"]}</td>'
                            f'<td>{dtohlcv["C"]}</td>'
                            f'<td>{dtohlcv["V"]}</td></tr>\n')

    sys.stdout.write('</table>\n')
    
    # Add confirmation button
    sys.stdout.write(f'<input type="button" '
                    f'onclick="location.href=\'/cgi-bin/i1min_do.py?importTicket={import_ticket}\'" '
                    f'value="Confirm importing!" />\n')
    sys.stdout.write('</body></html>')


def output_json_response(ret_obj):
    """
    Generate JSON response for API clients.
    
    Args:
        ret_obj (dict): Response data containing trading data and metadata
    """
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(ret_obj, ensure_ascii=False, indent=2))


# Main execution
if __name__ == "__main__":
    # Process the uploaded data and prepare for import
    process_post_data()
    prepare_import()
    
    # Build response data
    response_data = build_response_data()
    
    # Parse query string to determine output format
    query_params = parse_query_string()
    
    # Output appropriate response format
    if 'html' in query_params and query_params['html'] == '1':
        output_html_response(response_data)
    else:
        output_json_response(response_data)
    
    sys.stdout.flush()

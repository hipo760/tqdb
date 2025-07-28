#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
TQ Database Supported Timezone Query CGI Script

This CGI script retrieves a list of supported timezones from the system and returns
them in JSON format. It's used by web interfaces to populate timezone selection
dropdowns and validate timezone parameters for time-based queries.

The script uses the modern `timedatectl` command (systemd) to get the comprehensive
list of available timezones on Rocky Linux 9.0 and other modern Linux distributions.

Author: TQ Database Team
Version: 3.0 (Python 3 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- systemd (timedatectl command)
- Rocky Linux 9.0 or compatible systemd-based distribution

Usage:
    HTTP GET: /cgi-bin/qSupportTZ.py
    
Parameters:
    None - returns all available system timezones

Returns:
    JSON response containing:
    - all: Array of supported timezone strings
    - server: Server's current timezone information
"""

import sys
import subprocess
import json

def run_command(cmd):
    """
    Execute a shell command and return the output lines.
    Updated for Python 3 with proper text handling and error management.
    
    Args:
        cmd (str): Shell command to execute
        
    Returns:
        list: List of output lines from the command (newlines stripped)
    """
    try:
        # Execute the shell command with proper Python 3 text handling
        proc = subprocess.Popen(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Python 3: Handle text instead of bytes
            timeout=10  # Add timeout for safety
        )
        
        ret = []
        # Read output line by line
        while True:
            line = proc.stdout.readline()
            if line:
                ret.append(line.rstrip('\n\r'))  # Remove newlines and carriage returns
            else:
                break
                
        # Wait for process to complete
        proc.wait()
        
        return ret
    except subprocess.TimeoutExpired:
        proc.kill()
        return ["Error: Command timed out"]
    except Exception as e:
        return [f"Error executing command '{cmd}': {str(e)}"]


def get_all_timezones():
    """
    Get all supported timezones from the system using timedatectl.
    
    This function uses the modern systemd timedatectl command which is
    standard on Rocky Linux 9.0 and other systemd-based distributions.
    
    Returns:
        list: List of timezone strings (e.g., ['UTC', 'America/New_York', ...])
    """
    # Use timedatectl which is the modern way to get timezones on systemd systems
    # This replaces the legacy tzconv utility for Rocky Linux 9.0 compatibility
    timezones = run_command("timedatectl list-timezones")
    
    # Filter out any error messages
    valid_timezones = [tz for tz in timezones if not tz.startswith("Error:")]
    
    return valid_timezones


def get_server_timezone_info():
    """
    Get the server's current timezone configuration.
    
    Returns:
        dict: Dictionary containing server timezone information
    """
    server_info = {}
    
    try:
        # Get current timezone using timedatectl
        current_tz = run_command("timedatectl show --property=Timezone --value")
        if current_tz and not current_tz[0].startswith("Error:"):
            server_info['timezone'] = current_tz[0]
        else:
            server_info['timezone'] = 'Unknown'
        
        # Get current time in server timezone
        current_time = run_command("date +'%Y-%m-%d %H:%M:%S %Z'")
        if current_time and not current_time[0].startswith("Error:"):
            server_info['current_time'] = current_time[0]
        else:
            server_info['current_time'] = 'Unknown'
        
        # Get UTC offset
        utc_offset = run_command("date +'%z'")
        if utc_offset and not utc_offset[0].startswith("Error:"):
            server_info['utc_offset'] = utc_offset[0]
        else:
            server_info['utc_offset'] = 'Unknown'
            
    except Exception as e:
        server_info = {
            'timezone': 'Error',
            'current_time': 'Error', 
            'utc_offset': 'Error',
            'error': str(e)
        }
    
    return server_info


def send_json_response(data):
    """
    Send JSON response with proper HTTP headers.
    
    Args:
        data: Python object to serialize as JSON
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    
    # Send JSON data with pretty formatting
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False))
    sys.stdout.flush()


def send_error_response(error_message):
    """
    Send JSON error response.
    
    Args:
        error_message (str): Error message to display
    """
    error_response = {
        'error': error_message,
        'all': [],
        'server': 'Error'
    }
    send_json_response(error_response)

# Main CGI execution
if __name__ == "__main__":
    try:
        # Get all supported timezones from the system
        all_timezones = get_all_timezones()
        
        # Get server's current timezone information
        server_timezone_info = get_server_timezone_info()
        
        # Prepare response data
        timezone_data = {
            'all': all_timezones,
            'server': server_timezone_info
        }
        
        # Send successful JSON response
        send_json_response(timezone_data)
        
    except Exception as e:
        # Handle any unexpected errors
        send_error_response(f"System error: {str(e)}")
        
        # Optional: Log error to system log for debugging
        # You can uncomment the following lines if you want to log errors
        # import logging
        # logging.basicConfig(filename='/var/log/tqdb/qSupportTZ.log', level=logging.ERROR)
        # logging.error(f"qSupportTZ.py error: {str(e)}")

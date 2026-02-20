#!/usr/bin/env python3
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
    Get all supported timezones from the system by reading /usr/share/zoneinfo/.
    
    This function reads timezones directly from the filesystem, which works
    in minimal containers without systemd/timedatectl. This is compatible with
    both full systems and slim Docker containers.
    
    Returns:
        list: List of timezone strings (e.g., ['UTC', 'America/New_York', ...])
    """
    import os
    
    timezones = []
    zoneinfo_path = '/usr/share/zoneinfo'
    
    # Directories to exclude (contain special or duplicate data)
    exclude_dirs = {'posix', 'right'}
    
    # Files to exclude (not timezone definitions)
    exclude_files = {
        'Factory', 'localtime', 'posixrules', 'zone.tab', 'zone1970.tab',
        'iso3166.tab', 'tzdata.zi', 'leap-seconds.list', 'leapseconds'
    }
    
    try:
        # Walk through zoneinfo directory to find all timezone files
        for root, dirs, files in os.walk(zoneinfo_path):
            # Skip excluded directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            # Get relative path from zoneinfo root
            rel_root = os.path.relpath(root, zoneinfo_path)
            
            for filename in files:
                # Skip excluded files and files starting with special characters
                if filename in exclude_files or filename.startswith('+'):
                    continue
                
                # Build timezone name (e.g., "Asia/Taipei")
                if rel_root == '.':
                    tz_name = filename
                else:
                    tz_name = os.path.join(rel_root, filename)
                
                # Only include if it looks like a valid timezone
                # (exclude files with .tab, .list extensions)
                if not any(tz_name.endswith(ext) for ext in ['.tab', '.list', '.zi']):
                    timezones.append(tz_name)
        
        # Sort alphabetically for better user experience
        timezones.sort()
        
    except Exception:
        # Fallback to common timezones if filesystem scan fails
        timezones = [
            'UTC',
            'GMT',
            'Asia/Taipei',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Hong_Kong',
            'Asia/Singapore',
            'America/New_York',
            'America/Chicago',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris'
        ]
    
    return timezones


def get_server_timezone_info():
    """
    Get the server's current timezone configuration.
    Works in containers without timedatectl by reading environment and using date command.
    
    Returns:
        dict: Dictionary containing server timezone information
    """
    import os
    
    server_info = {}
    
    try:
        # Try to get timezone from environment variable (set in container)
        tz_env = os.environ.get('TZ', '')
        if tz_env:
            server_info['timezone'] = tz_env
        else:
            # Try to read from /etc/timezone (Debian/Ubuntu style)
            try:
                with open('/etc/timezone', 'r') as f:
                    server_info['timezone'] = f.read().strip()
            except FileNotFoundError:
                # Try to resolve /etc/localtime symlink (RHEL style)
                try:
                    localtime = os.path.realpath('/etc/localtime')
                    if '/usr/share/zoneinfo/' in localtime:
                        server_info['timezone'] = localtime.split('/usr/share/zoneinfo/')[-1]
                    else:
                        server_info['timezone'] = 'Unknown'
                except Exception:
                    server_info['timezone'] = 'Unknown'
        
        # Get current time in server timezone using date command
        current_time = run_command("date +'%Y-%m-%d %H:%M:%S %Z'")
        if current_time and not current_time[0].startswith("Error:"):
            server_info['current_time'] = current_time[0]
        else:
            server_info['current_time'] = 'Unknown'
        
        # Get UTC offset using date command
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

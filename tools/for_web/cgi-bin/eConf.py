#!/usr/bin/env python3
# -*- coding: utf-8 -*-   
"""
TQDB Configuration Editor CGI Script

This CGI script provides a web interface for managing configuration settings 
stored in the Cassandra database. It supports two main operations:

- UPDATE: Update or create configuration values in the database
- QUERY: Retrieve configuration values from the database

The script handles both GET (query string) and POST (form data) parameters,
with POST data taking precedence. Configuration changes trigger notifications
to the TQAlert system through file-based signaling.

Author: TQDB Development Team
Date: 2024
"""

import sys
import json
import os
import urllib.parse
import cgi
import cgitb
from datetime import datetime
from cassandra.cluster import Cluster

# Enable CGI error reporting for debugging
cgitb.enable()

# Configuration constants
DEFAULT_KEYSPACE = 'tqdb1'
ALERT_SIGNAL_FILE = '/tmp/TQAlert/TQAlert.confchange'


def execute_config_operation(keyspace, conf_key, conf_val, cmd):
    """
    Execute configuration operation (UPDATE or QUERY) on Cassandra database.
    
    Args:
        keyspace (str): Cassandra keyspace name (e.g., 'tqdb1')
        conf_key (str): Configuration key/name to operate on
        conf_val (str): Configuration value (used for UPDATE operations)
        cmd (str): Operation command ('UPDATE' or 'QUERY')
        
    Returns:
        dict: Result dictionary with operation status and data
            - For UPDATE: {'Result': 'OK'} or error message
            - For QUERY: {'Result': 'OK', 'confVal': value} or error message
    """
    cluster = None
    session = None
    
    try:
        # Establish database connection
        cluster = Cluster()
        session = cluster.connect(keyspace)
        
        if cmd == 'UPDATE':
            return handle_update_operation(session, keyspace, conf_key, conf_val)
        elif cmd == 'QUERY':
            return handle_query_operation(session, keyspace, conf_key)
        else:
            return {'Result': f'Error! Invalid command: {cmd}'}
            
    except Exception as e:
        return {'Result': f'Error! Database connection failed: {str(e)}'}
    finally:
        # Ensure proper cleanup of database connections
        if cluster:
            cluster.shutdown()


def handle_update_operation(session, keyspace, conf_key, conf_val):
    """
    Handle UPDATE operation to store/update configuration values.
    
    Args:
        session: Cassandra session object
        keyspace (str): Database keyspace
        conf_key (str): Configuration key
        conf_val (str): Configuration value to store
        
    Returns:
        dict: Result of the update operation
    """
    try:
        # Escape special characters to prevent injection and data corruption
        escaped_val = escape_config_value(conf_val)
        
        # Build and execute CQL update command
        cql_cmd = f"UPDATE {keyspace}.conf SET confVal='{escaped_val}' WHERE confKey='{conf_key}'"
        
        session.execute(cql_cmd)
        
        # Signal TQAlert system about configuration change
        signal_config_change()
        
        return {'Result': 'OK'}
        
    except Exception as e:
        return {'Result': f'Error! Failed to execute UPDATE: {str(e)}'}


def handle_query_operation(session, keyspace, conf_key):
    """
    Handle QUERY operation to retrieve configuration values.
    
    Args:
        session: Cassandra session object
        keyspace (str): Database keyspace
        conf_key (str): Configuration key to query
        
    Returns:
        dict: Result containing the configuration value or error
    """
    try:
        # Build and execute CQL select command
        query_str = f"SELECT confVal FROM {keyspace}.conf WHERE confKey='{conf_key}'"
        
        q_result = session.execute(query_str)
        
        # Validate query results
        if q_result is None or len(q_result.current_rows) <= 0:
            return {'Result': 'Error! No Such Data'}
        
        # Retrieve and unescape the configuration value
        raw_value = q_result[0][0]
        unescaped_val = unescape_config_value(raw_value)
        
        return {'Result': 'OK', 'confVal': unescaped_val}
        
    except Exception as e:
        return {'Result': f'Error! Failed to execute QUERY: {str(e)}'}


def escape_config_value(value):
    """
    Escape special characters in configuration values for safe database storage.
    
    This prevents issues with quotes and backslashes in CQL commands and
    ensures data integrity when storing complex configuration strings.
    
    Args:
        value (str): Raw configuration value
        
    Returns:
        str: Escaped configuration value safe for CQL insertion
    """
    if not isinstance(value, str):
        value = str(value)
    
    return (value
            .replace('\\', '&bsol;')  # Escape backslashes first
            .replace('"', '&quot;')   # Escape double quotes
            .replace("'", '&apos;'))  # Escape single quotes


def unescape_config_value(value):
    """
    Unescape configuration values retrieved from the database.
    
    Reverses the escaping applied during storage to restore original values.
    
    Args:
        value (str): Escaped configuration value from database
        
    Returns:
        str: Original unescaped configuration value
    """
    if not isinstance(value, str):
        value = str(value)
    
    return (value
            .replace('&quot;', '"')   # Unescape double quotes
            .replace('&apos;', "'")   # Unescape single quotes
            .replace('&bsol;', '\\'))  # Unescape backslashes last


def signal_config_change():
    """
    Signal the TQAlert system that configuration has changed.
    
    Creates a timestamp file that TQAlert monitors to detect configuration
    changes and reload settings accordingly. This enables hot-reloading
    of configuration without system restart.
    """
    try:
        # Ensure the alert directory exists
        alert_dir = os.path.dirname(ALERT_SIGNAL_FILE)
        os.makedirs(alert_dir, exist_ok=True)
          # Remove any existing signal file
        if os.path.exists(ALERT_SIGNAL_FILE):
            os.remove(ALERT_SIGNAL_FILE)
        
        # Create new signal file with current timestamp
        with open(ALERT_SIGNAL_FILE, 'w', encoding='utf-8') as f:
            # Write Unix timestamp for when the change occurred
            timestamp = str(int(datetime.now().timestamp()))
            f.write(f'{timestamp}\n')
        
        # Set file permissions (equivalent to chmod 0777)
        os.chmod(ALERT_SIGNAL_FILE, 0o777)
        
    except Exception:
        # Silently ignore errors in signaling - configuration update succeeded
        # but notification failed (non-critical)
        pass


def parse_request_parameters():
    """
    Parse and combine CGI parameters from both query string and form data.
    
    Form data (POST) takes precedence over query string (GET) parameters
    when both are present for the same key.
    
    Returns:
        dict: Combined parameters with default values:
            - confKey: Configuration key name
            - confVal: Configuration value (for UPDATE operations)
            - cmd: Operation command ('UPDATE' or 'QUERY')
    """
    # Initialize parameters with empty defaults
    all_params = {
        'confKey': '',
        'confVal': '', 
        'cmd': ''
    }
    
    # Parse query string parameters first
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    query_params = {}
    
    for qs in query_strings.split("&"):
        if qs.find("=") <= 0:
            continue
        key, value = qs.split("=", 1)
        query_params[key] = urllib.parse.unquote(value)
    
    # Apply query string values
    for key in all_params.keys():
        if key in query_params:
            all_params[key] = query_params[key]
    
    # Parse form data (POST) - these override query string values
    try:
        form = cgi.FieldStorage()
        for key in all_params.keys():
            form_value = form.getvalue(key)
            if form_value is not None:
                all_params[key] = form_value
    except Exception:
        # If form parsing fails, continue with query string values
        pass
    
    return all_params


def output_json_response(result_obj):
    """
    Output JSON response with proper HTTP headers.
    
    Args:
        result_obj (dict): Result object to serialize as JSON response
    """
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(result_obj, ensure_ascii=False, indent=2))
    sys.stdout.flush()


def main():
    """
    Main function that orchestrates the CGI request processing.
    
    Handles the complete workflow:
    1. Parse request parameters from query string and form data
    2. Execute the requested configuration operation
    3. Return JSON response with operation results
    """
    try:
        # Parse all request parameters
        params = parse_request_parameters()
        
        # Validate required parameters
        if not params['confKey']:
            result_obj = {'Result': 'Error! Missing required parameter: confKey'}
            output_json_response(result_obj)
            return
        
        if not params['cmd']:
            result_obj = {'Result': 'Error! Missing required parameter: cmd'}
            output_json_response(result_obj)
            return
        
        # For UPDATE operations, validate that confVal is provided
        if params['cmd'] == 'UPDATE' and not params['confVal']:
            result_obj = {'Result': 'Error! Missing required parameter: confVal for UPDATE operation'}
            output_json_response(result_obj)
            return
        
        # Execute the requested configuration operation
        result_obj = execute_config_operation(
            keyspace=DEFAULT_KEYSPACE,
            conf_key=params['confKey'],
            conf_val=params['confVal'],
            cmd=params['cmd']
        )
        
        # Output the result
        output_json_response(result_obj)
        
    except Exception as e:
        # Handle any unexpected errors
        error_result = {'Result': f'Error! Unexpected error: {str(e)}'}
        output_json_response(error_result)


if __name__ == "__main__":
    main()


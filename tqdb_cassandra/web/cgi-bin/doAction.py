#!/usr/bin/env python3
# -*- coding: utf-8 -*-   
"""
TQDB Action Executor CGI Script

This CGI script provides a web interface for executing various administrative 
actions on the TQAlert system. It supports the following operations:

- TQALERT_MUTE: Mute alert notifications for specified trading symbols
- TQALERT_UNMUTE: Unmute alert notifications for specified trading symbols  
- TQALERT_TESTCMD: Execute test commands for system validation

The script handles both GET (query string) and POST (form data) parameters,
with POST data taking precedence. Actions are performed through file-based
signaling mechanisms that the TQAlert system monitors.

Author: TQDB Development Team
Date: 2024
"""

import sys
import json
import os
import urllib.parse
import cgi
import cgitb

# Enable CGI error reporting for debugging
cgitb.enable()

# Configuration constants
DEFAULT_KEYSPACE = 'tqdb1'
ALERT_BASE_DIR = '/tmp/TQAlert'
SKIP_FILE_PREFIX = 'TQAlert.skip.'
TESTCMD_FILE_PREFIX = 'TQAlert.testcmd.'


def execute_action(keyspace, cmd, params):
    """
    Execute the specified action command with given parameters.
    
    Args:
        keyspace (str): Cassandra keyspace name (currently unused but kept for consistency)
        cmd (str): Action command to execute ('TQALERT_MUTE', 'TQALERT_UNMUTE', 'TQALERT_TESTCMD')
        params (str): Command parameters (symbol list for mute/unmute, test name for testcmd)
        
    Returns:
        dict: Result dictionary containing:
            - Result: 'OK' if successful, error message if failed
            - Detail: Additional details about the operation (for mute/unmute operations)
    """
    result_obj = {'Result': 'Error! Invalid command!', 'Detail': None}
    
    try:
        if cmd in ('TQALERT_MUTE', 'TQALERT_UNMUTE'):
            result_obj = handle_alert_mute_operations(cmd, params)
        elif cmd == 'TQALERT_TESTCMD':
            result_obj = handle_test_command(params)
        else:
            result_obj['Result'] = f'Error! Unsupported command: {cmd}'
            
    except Exception as e:
        result_obj = {'Result': f'Error! Unexpected error: {str(e)}', 'Detail': None}
    
    return result_obj


def handle_alert_mute_operations(cmd, params):
    """
    Handle mute/unmute operations for trading symbol alerts.
    
    Creates or removes skip files that the TQAlert system monitors to determine
    which symbols should have their alerts suppressed.
    
    Args:
        cmd (str): Either 'TQALERT_MUTE' or 'TQALERT_UNMUTE'
        params (str): Comma-separated list of trading symbols
        
    Returns:
        dict: Result with lists of successful and failed symbol operations
    """
    result_obj = {
        'Result': 'OK',
        'Detail': {
            'Succeed': [],
            'Failed': []
        }
    }
    
    # Sanitize parameters to prevent directory traversal attacks
    sanitized_params = sanitize_symbol_params(params)
    symbol_list = [sym.strip() for sym in sanitized_params.split(',') if sym.strip()]
    
    # Ensure the alert directory exists
    ensure_alert_directory()
    
    for symbol in symbol_list:
        if not symbol:  # Skip empty symbols
            continue
            
        try:
            skip_file_path = os.path.join(ALERT_BASE_DIR, f'{SKIP_FILE_PREFIX}{symbol}')
            
            if cmd == 'TQALERT_MUTE':
                create_skip_file(skip_file_path, symbol)
            else:  # TQALERT_UNMUTE
                remove_skip_file(skip_file_path, symbol)
                
            result_obj['Detail']['Succeed'].append(symbol)
            
        except Exception as e:
            result_obj['Detail']['Failed'].append({
                'symbol': symbol,
                'error': str(e)
            })
    
    return result_obj


def handle_test_command(test_name):
    """
    Handle test command execution for system validation.
    
    Creates a test command file that the TQAlert system can monitor
    to trigger specific test scenarios or validation routines.
    
    Args:
        test_name (str): Name/identifier of the test to execute
        
    Returns:
        dict: Result of the test command creation
    """
    try:
        # Sanitize test name to prevent security issues
        sanitized_test_name = sanitize_test_name(test_name)
        
        if not sanitized_test_name:
            return {'Result': 'Error! Invalid test name provided', 'Detail': None}
        
        # Ensure the alert directory exists
        ensure_alert_directory()
        
        # Create test command file
        test_file_path = os.path.join(ALERT_BASE_DIR, f'{TESTCMD_FILE_PREFIX}{sanitized_test_name}')
        
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write('1\n')
        
        # Set file permissions for TQAlert system access
        os.chmod(test_file_path, 0o777)
        
        return {'Result': 'OK', 'Detail': {'testFile': test_file_path}}
        
    except Exception as e:
        return {'Result': f'Error! Failed to create test command: {str(e)}', 'Detail': None}


def sanitize_symbol_params(params):
    """
    Sanitize symbol parameters to prevent security vulnerabilities.
    
    Removes potentially dangerous characters that could be used for
    directory traversal or other security exploits.
    
    Args:
        params (str): Raw parameter string containing symbol names
        
    Returns:
        str: Sanitized parameter string safe for file operations
    """
    if not isinstance(params, str):
        params = str(params)
    
    # Replace forward slashes with underscores to prevent directory traversal
    # Also remove other potentially dangerous characters
    sanitized = (params
                .replace('/', '_')
                .replace('\\', '_')
                .replace('..', '_')
                .replace('\0', '')
                .replace('\n', '')
                .replace('\r', ''))
    
    return sanitized


def sanitize_test_name(test_name):
    """
    Sanitize test command name for safe file operations.
    
    Args:
        test_name (str): Raw test name
        
    Returns:
        str: Sanitized test name safe for file operations
    """
    if not isinstance(test_name, str):
        test_name = str(test_name)
    
    # Allow only alphanumeric characters, hyphens, and underscores
    sanitized = ''.join(c for c in test_name if c.isalnum() or c in '-_')
    
    # Limit length to prevent excessively long filenames
    return sanitized[:100]


def ensure_alert_directory():
    """
    Ensure the TQAlert directory exists with proper permissions.
    
    Creates the directory if it doesn't exist and sets appropriate
    permissions for the TQAlert system to access the files.
    """
    try:
        os.makedirs(ALERT_BASE_DIR, exist_ok=True)
        # Set directory permissions to allow TQAlert system access
        os.chmod(ALERT_BASE_DIR, 0o777)
    except Exception:
        # If directory creation fails, the individual file operations
        # will handle the error appropriately
        pass


def create_skip_file(file_path, symbol):
    """
    Create a skip file to mute alerts for a specific symbol.
    
    Args:
        file_path (str): Full path to the skip file
        symbol (str): Trading symbol being muted
        
    Raises:
        Exception: If file creation fails
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('1\n')
    
    # Set file permissions for TQAlert system access
    os.chmod(file_path, 0o777)


def remove_skip_file(file_path, symbol):
    """
    Remove a skip file to unmute alerts for a specific symbol.
    
    Args:
        file_path (str): Full path to the skip file
        symbol (str): Trading symbol being unmuted
        
    Raises:
        Exception: If file removal fails or file doesn't exist
    """
    if os.path.exists(file_path):
        os.remove(file_path)
    else:
        # Consider this successful since the goal (no skip file) is achieved
        pass


def parse_request_parameters():
    """
    Parse and combine CGI parameters from both query string and form data.
    
    Form data (POST) takes precedence over query string (GET) parameters
    when both are present for the same key.
    
    Returns:
        dict: Combined parameters with defaults:
            - cmd: Action command to execute
            - params: Parameters for the command
    """
    # Initialize parameters with empty defaults
    all_params = {
        'cmd': '',
        'params': ''
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
    2. Execute the requested action
    3. Return JSON response with operation results
    """
    try:
        # Parse all request parameters
        params = parse_request_parameters()
        
        # Validate required parameters
        if not params['cmd']:
            result_obj = {'Result': 'Error! Missing required parameter: cmd', 'Detail': None}
            output_json_response(result_obj)
            return
        
        # Execute the requested action
        result_obj = execute_action(
            keyspace=DEFAULT_KEYSPACE,
            cmd=params['cmd'],
            params=params['params']
        )
        
        # Output the result
        output_json_response(result_obj)
        
    except Exception as e:
        # Handle any unexpected errors
        error_result = {'Result': f'Error! Unexpected error: {str(e)}', 'Detail': None}
        output_json_response(error_result)


if __name__ == "__main__":
    main()


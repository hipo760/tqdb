#!/usr/bin/env python3
# -*- coding: utf-8 -*-   
"""
TQDB Data Editor CGI Script

This CGI script provides a web interface for editing trading data stored in a Cassandra database.
It supports operations on different data types (minbar, secbar, tick) including:
- DELETE: Remove single data record
- DELETERANGE: Remove data records within a time range  
- UPDATE/FUPDATE: Update existing data records

The script accepts query parameters to specify the operation details and returns JSON responses.

Author: TQDB Development Team
Date: 2024
"""

import sys
import json
import os
import urllib.parse
from cassandra.cluster import Cluster


def execute_data_operation(keyspace, table, symbol, epoch_float_beg, epoch_float_end, cmd, data_obj):
    """
    Execute data operation (DELETE, UPDATE, DELETERANGE) on Cassandra database.
    
    Args:
        keyspace (str): Cassandra keyspace name (e.g., 'tqdb1')
        table (str): Table name ('minbar', 'secbar', or 'tick')
        symbol (str): Trading symbol (e.g., 'AAPL', 'SPY')
        epoch_float_beg (float): Start epoch time (seconds since Unix epoch)
        epoch_float_end (float): End epoch time (seconds since Unix epoch)
        cmd (str): Operation command ('DELETE', 'UPDATE', 'FUPDATE', 'DELETERANGE')
        data_obj (dict): Data object containing fields to update
        
    Returns:
        dict: Result dictionary with 'Result' key containing success/error message
    """
    try:
        cluster = Cluster()
        session = cluster.connect(keyspace)
    except Exception as e:
        return {'Result': f'Error! Failed to connect to Cassandra: {str(e)}'}
    
    query_str = ""
    q_result = None
    
    try:
        # Validate and fetch existing data for DELETE/UPDATE operations
        if cmd in ('DELETE', 'UPDATE', 'FUPDATE'):
            if table in ['minbar', 'secbar', 'tick']:
                # Convert epoch float to milliseconds for Cassandra datetime
                query_str = (f"SELECT * FROM {keyspace}.{table} "
                           f"WHERE symbol='{symbol}' AND datetime={int(epoch_float_beg * 1000)}")
            
            try:
                q_result = session.execute(query_str)
            except Exception as e:
                return {'Result': f'Error! Failed to execute [{query_str}]: {str(e)}'}
            
            # Validate that exactly one record exists
            if q_result is None or len(q_result.current_rows) != 1:
                return {'Result': 'Error! No Such Data'}
            
            # Additional validation for tick data
            if table == 'tick' and q_result[0].type != 1:
                return {'Result': 'Error! No Such Tick Data'}
                
        # Validate and fetch existing data for DELETERANGE operation
        elif cmd == 'DELETERANGE':
            if table in ['minbar', 'secbar', 'tick']:
                # Query range of data to be deleted
                query_str = (f"SELECT * FROM {keyspace}.{table} "
                           f"WHERE symbol='{symbol}' "
                           f"AND datetime>={int(epoch_float_beg * 1000)} "
                           f"AND datetime<{int(epoch_float_end * 1000)}")
            
            try:
                q_result = session.execute(query_str)
            except Exception as e:
                return {'Result': f'Error! Failed to execute [{query_str}]: {str(e)}'}
            
            # Validate that data exists in the range
            if q_result is None or len(q_result.current_rows) <= 0:
                return {'Result': 'Error! No Such Data'}
            
            # Additional validation for tick data
            if table == 'tick' and q_result[0].type <= 0:
                return {'Result': 'Error! No Such Tick Data'}

        # Build and execute the appropriate CQL command
        cql_cmd = build_cql_command(keyspace, table, symbol, epoch_float_beg, 
                                   epoch_float_end, cmd, data_obj, q_result)
        
        if not cql_cmd:
            return {'Result': 'Error! Invalid command or parameters'}
        
        try:
            session.execute(cql_cmd)
        except Exception as e:
            return {'Result': f'Error! Failed to execute [{cql_cmd}]: {str(e)}'}
        
        return {'Result': 'OK'}
        
    finally:
        # Ensure cluster connection is properly closed
        if 'cluster' in locals():
            cluster.shutdown()


def build_cql_command(keyspace, table, symbol, epoch_float_beg, epoch_float_end, 
                      cmd, data_obj, q_result=None):
    """
    Build the appropriate CQL command based on operation type.
    
    Args:
        keyspace (str): Cassandra keyspace name
        table (str): Table name
        symbol (str): Trading symbol
        epoch_float_beg (float): Start epoch time
        epoch_float_end (float): End epoch time
        cmd (str): Operation command
        data_obj (dict): Data object for updates
        q_result: Query result for existing data (used in updates)
        
    Returns:
        str: CQL command string, or empty string if invalid
    """
    datetime_ms_beg = int(epoch_float_beg * 1000)
    datetime_ms_end = int(epoch_float_end * 1000)
    
    if cmd == "DELETE":
        return (f"DELETE FROM {keyspace}.{table} "
               f"WHERE symbol='{symbol}' AND datetime={datetime_ms_beg}")
    
    elif cmd == "DELETERANGE":
        return (f"DELETE FROM {keyspace}.{table} "
               f"WHERE symbol='{symbol}' "
               f"AND datetime>={datetime_ms_beg} "
               f"AND datetime<{datetime_ms_end}")
    
    elif cmd in ("UPDATE", "FUPDATE"):
        update_part = build_update_clause(table, data_obj, q_result)
        if not update_part:
            return ""
        
        return (f"UPDATE {keyspace}.{table} SET {update_part} "
               f"WHERE symbol='{symbol}' AND datetime={datetime_ms_beg}")
    
    return ""


def build_update_clause(table, data_obj, q_result):
    """
    Build the SET clause for UPDATE operations based on table type.
    
    Args:
        table (str): Table name ('minbar', 'secbar', or 'tick')
        data_obj (dict): Data object containing fields to update
        q_result: Existing data from database (for tick data merging)
        
    Returns:
        str: SET clause for CQL UPDATE command
    """
    if table in ['minbar', 'secbar']:
        # For bar data, update all provided fields directly
        all_key_val = []
        for key, value in data_obj.items():
            # Properly escape and format values
            if isinstance(value, str):
                all_key_val.append(f"{key}='{value}'")
            else:
                all_key_val.append(f"{key}={str(value)}")
        return ",".join(all_key_val)
    
    elif table == 'tick':
        # For tick data, merge with existing keyval map
        if not q_result or len(q_result.current_rows) == 0:
            return ""
        
        keyval_list = []
        existing_keyval = q_result[0].keyval or {}
        
        # Merge existing data with new data
        for key in existing_keyval.keys():
            if key in data_obj:
                # Use new value from data_obj
                value = data_obj[key]
                if isinstance(value, str):
                    keyval_list.append(f"'{key}':'{value}'")
                else:
                    keyval_list.append(f"'{key}':{str(value)}")
            else:
                # Keep existing value
                existing_value = existing_keyval[key]
                if isinstance(existing_value, str):
                    keyval_list.append(f"'{key}':'{existing_value}'")
                else:
                    keyval_list.append(f"'{key}':{str(existing_value)}")
        
        return f"keyval={{{','.join(keyval_list)}}}"
    
    return ""


def parse_query_parameters():
    """
    Parse CGI query string parameters and set defaults.
    
    Returns:
        dict: Dictionary containing parsed query parameters with defaults
    """
    query_strings = os.environ.get("QUERY_STRING", "NA=NA")
    params = {}
    
    # Parse query string parameters
    for qs in query_strings.split("&"):
        if qs.find("=") <= 0:
            continue
        key, value = qs.split("=", 1)
        params[key] = urllib.parse.unquote(value)
    
    # Set default values for required parameters
    params.setdefault('symbol', 'XX??')
    params.setdefault('type', 'minbar')
    params.setdefault('epochFloatBeg', '0')
    params.setdefault('epochFloatEnd', params['epochFloatBeg'])
    params.setdefault('cmd', 'UPDATE')
    params.setdefault('jsonObj', '{"open":0,"high":0,"low":0,"close":0,"vol":"0"}')
    
    return params


def output_json_response(result_obj):
    """
    Output JSON response with proper headers.
    
    Args:
        result_obj (dict): Result object to serialize as JSON
    """
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    sys.stdout.write(json.dumps(result_obj, ensure_ascii=False, indent=2))
    sys.stdout.flush()


def main():
    """
    Main function that orchestrates the CGI request processing.
    """
    try:
        # Parse query parameters
        params = parse_query_parameters()
        
        # Parse JSON data object
        try:
            data_obj = json.loads(params['jsonObj'])
        except json.JSONDecodeError as e:
            result_obj = {'Result': f'Error! Invalid JSON data: {str(e)}'}
            output_json_response(result_obj)
            return
        
        # Execute the requested operation
        result_obj = execute_data_operation(
            keyspace='tqdb1',
            table=params['type'],
            symbol=params['symbol'],
            epoch_float_beg=float(params['epochFloatBeg']),
            epoch_float_end=float(params['epochFloatEnd']),
            cmd=params['cmd'],
            data_obj=data_obj
        )
        
        # Output the result
        output_json_response(result_obj)
        
    except Exception as e:
        # Handle any unexpected errors
        error_result = {'Result': f'Error! Unexpected error: {str(e)}'}
        output_json_response(error_result)


if __name__ == "__main__":
    main()


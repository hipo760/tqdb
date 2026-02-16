#!/usr/bin/env python3
"""
Sym2Cass.py - Symbol Information Manager for Cassandra Database

This script manages symbol information in a Cassandra database. It can insert, update,
or delete symbol records with their associated metadata.

The symbol information is stored as JSON data containing trading parameters such as:
- DESC: Symbol description
- BPV: Base Point Value (tick value)
- MKO: Market Open time
- MKC: Market Close time
- SSEC: Seconds granularity

Usage:
    python Sym2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol> <action_or_data>

Arguments:
    cassandra_ip:    IP address of the Cassandra cluster
    cassandra_port:  Port number (not used in current connection)
    database_name:   Cassandra keyspace/database name
    symbol:          Symbol name to manage
    action_or_data:  Either 'delete' to remove symbol, or JSON string with symbol data

Examples:
    # Insert/Update symbol with trading parameters
    python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL '{"DESC":"Apple Inc","BPV":"0.01","MKO":"93000","MKC":"160000"}'
    
    # Delete symbol
    python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL delete

Author: AutoTrade System
Date: 2025
"""

import json
import sys
# Note: Requires cassandra-driver package: pip install cassandra-driver
from cassandra.cluster import Cluster

# Global configuration variables
cassandra_ip = ""
cassandra_port = ""
cassandra_db = ""
symbol = ""
symbol_info = {}
def delete_symbol():
    """
    Delete a symbol record from the Cassandra database.
    
    This function connects to the Cassandra database and removes the specified
    symbol from the symbol table.
    
    Raises:
        Exception: If there's an error connecting to Cassandra or executing the query
    """
    try:
        # Connect to Cassandra cluster
        cluster = Cluster([cassandra_ip])
        session = cluster.connect()
        session.set_keyspace(cassandra_db)
        
        # Execute delete query using parameterized query for security
        delete_query = f"DELETE FROM {cassandra_db}.symbol WHERE symbol = ?"
        session.execute(delete_query, [symbol])
        
        print(f"Symbol '{symbol}' deleted successfully.")
        
        # Clean up connections
        session.shutdown()
        cluster.shutdown()
        
    except Exception as e:
        print(f"Error deleting symbol: {e}")
        raise
 
def insert_or_update_symbol():
    """
    Insert a new symbol or update an existing symbol in the Cassandra database.
    
    This function:
    1. Merges provided symbol information with default parameters
    2. Checks if the symbol already exists in the database
    3. Either updates the existing record or inserts a new one
    4. Stores the symbol data as JSON in the keyval column
    
    Default parameters:
    - DESC: Description (empty string)
    - BPV: Base Point Value ("1")
    - MKO: Market Open time ("0")
    - MKC: Market Close time ("0")
    - SSEC: Seconds granularity ("0")
    
    Raises:
        Exception: If there's an error connecting to Cassandra or executing queries
    """
    try:
        # Connect to Cassandra cluster
        cluster = Cluster([cassandra_ip])
        session = cluster.connect()
        session.set_keyspace(cassandra_db)
        
        # Set up default parameters
        default_params = {
            'DESC': "",
            'BPV': "1",
            'MKO': "0",
            'MKC': "0",
            'SSEC': "0"
        }
        
        # Merge user-provided data with defaults
        merged_params = default_params.copy()
        merged_params.update(symbol_info)
        
        # Convert to JSON string with single quotes (Cassandra format)
        json_data = json.dumps(merged_params).replace('"', "'")
        
        # Check if symbol already exists
        select_query = f"SELECT * FROM {cassandra_db}.symbol WHERE symbol = ?"
        result = session.execute(select_query, [symbol])
        
        if result and len(list(result)) > 0:
            # Update existing symbol
            update_query = f"UPDATE {cassandra_db}.symbol SET keyval = ? WHERE symbol = ?"
            session.execute(update_query, [json_data, symbol])
            print(f"Symbol '{symbol}' updated successfully.")
        else:
            # Insert new symbol
            insert_query = f"INSERT INTO {cassandra_db}.symbol (symbol, keyval) VALUES (?, ?)"
            session.execute(insert_query, [symbol, json_data])
            print(f"Symbol '{symbol}' inserted successfully.")
        
        # Clean up connections
        session.shutdown()
        cluster.shutdown()
        
    except Exception as e:
        print(f"Error inserting/updating symbol: {e}")
        raise

def validate_json_data(json_string):
    """
    Validate and parse JSON symbol information.
    
    Args:
        json_string (str): JSON string containing symbol information
        
    Returns:
        dict: Parsed JSON data
        
    Raises:
        ValueError: If JSON is invalid
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")


def main():
    """
    Main function that parses command line arguments and executes the requested operation.
    
    Command line arguments:
    1. Cassandra IP address
    2. Cassandra port (informational, not used in connection)
    3. Cassandra database/keyspace name
    4. Symbol name
    5. Action or JSON data ('delete' to remove symbol, or JSON string with symbol data)
    """
    global cassandra_ip, cassandra_port, cassandra_db, symbol, symbol_info
    
    if len(sys.argv) != 6:
        print("Usage: python Sym2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol> <action_or_data>")
        print("\nExamples:")
        print('  python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL \'{"DESC":"Apple Inc","BPV":"0.01"}\'')
        print("  python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL delete")
        sys.exit(1)
    
    # Parse command line arguments
    cassandra_ip = sys.argv[1]
    cassandra_port = sys.argv[2]
    cassandra_db = sys.argv[3]
    symbol = sys.argv[4]
    action_or_data = sys.argv[5]
    
    print(f"Connecting to Cassandra at {cassandra_ip}:{cassandra_port}")
    print(f"Database: {cassandra_db}")
    print(f"Symbol: {symbol}")
    print("-" * 50)
    
    try:
        if action_or_data.lower() == 'delete':
            # Delete symbol
            print(f"Deleting symbol '{symbol}'...")
            delete_symbol()
        else:
            # Insert or update symbol
            print(f"Processing symbol data for '{symbol}'...")
            symbol_info = validate_json_data(action_or_data)
            
            # Display the parameters being set
            print("Symbol parameters:")
            for key, value in symbol_info.items():
                print(f"  {key}: {value}")
            print()
            
            insert_or_update_symbol()
            
    except ValueError as e:
        print(f"Error parsing symbol information: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

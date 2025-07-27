#!/usr/bin/env python3
"""
Min2Cass.py - Minute Bar Data Importer for Cassandra Database

This script reads minute bar data from stdin and inserts it into a Cassandra database.
The input data is expected to be in CSV or space-separated format with the following columns:
Date, Time, Open, High, Low, Close, Volume

Usage:
    python Min2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol>

Example:
    python Min2Cass.py 192.168.1.217 9042 TQDB AAPL

Author: AutoTrade System
Date: 2025
"""

import sys
import datetime
# Note: Requires cassandra-driver package: pip install cassandra-driver
from cassandra.cluster import Cluster

# Global configuration variables
cassandra_ip = ""
cassandra_port = ""
cassandra_db = ""
cassandra_table = "minbar"
symbol = ""
def parse_date_time(date_str, time_str):
    """
    Parse date and time strings into numeric format.
    
    Args:
        date_str (str): Date string in format YYYY/MM/DD or YYYYMMDD
        time_str (str): Time string in format HH:MM:SS or HHMMSS
        
    Returns:
        tuple: (date_int, time_int) where date_int is YYYYMMDD and time_int is HHMMSS
               Returns (-1, -1) if parsing fails
    """
    try:
        date_int = -1
        time_int = -1
        
        # Parse date
        if '/' in date_str:
            date_parts = date_str.split('/')
            if len(date_parts) == 3:
                date_int = int(date_parts[0]) * 10000 + int(date_parts[1]) * 100 + int(date_parts[2])
        else:
            date_int = int(date_str)
        
        # Parse time
        if ':' in time_str:
            time_parts = time_str.split(':')
            if len(time_parts) == 3:
                time_int = int(time_parts[0]) * 10000 + int(time_parts[1]) * 100 + int(time_parts[2])
        else:
            time_int = int(float(time_str))
            
        return date_int, time_int
    except (ValueError, IndexError):
        return -1, -1


def create_datetime_from_components(date_int, time_int):
    """
    Create a datetime object from integer date and time components.
    
    Args:
        date_int (int): Date in YYYYMMDD format
        time_int (int): Time in HHMMSS format
        
    Returns:
        datetime.datetime: The constructed datetime object
    """
    year = date_int // 10000
    month = (date_int // 100) % 100
    day = date_int % 100
    hour = time_int // 10000
    minute = (time_int // 100) % 100
    second = time_int % 100
    
    return datetime.datetime(year, month, day, hour, minute, second)


def should_show_progress(line_count):
    """
    Determine if progress should be shown based on line count.
    
    Args:
        line_count (int): Current number of processed lines
        
    Returns:
        bool: True if progress should be displayed
    """
    if line_count < 10:
        return True
    elif line_count < 100 and (line_count % 10) == 0:
        return True
    elif line_count < 1000 and (line_count % 100) == 0:
        return True
    elif (line_count % 1000) == 0:
        return True
    return False


def loop_read_from_stdin():
    """
    Main processing loop that reads minute bar data from stdin and inserts into Cassandra.
    
    The function expects input data in CSV or space-separated format with columns:
    Date, Time, Open, High, Low, Close, Volume
    
    Connects to Cassandra using global configuration variables and processes each line
    of input data, converting it to the appropriate format for database insertion.
    """
    # Connect to Cassandra cluster
    cluster = Cluster([cassandra_ip])
    session = cluster.connect()
    session.set_keyspace(cassandra_db)

    line_count = 0
    print("Ready to insert minute bars to database")
    
    for line in sys.stdin:
        # Clean and split the input line
        line = line.replace('\r', '').replace('\n', '')
        line_split = line.split(',')
        
        # If comma separation doesn't work, try space separation
        if len(line_split) < 3:
            line_split = line.split(' ')
        
        # Skip lines that don't have enough fields
        if len(line_split) < 7:
            print(f"Skipping line with insufficient fields: {line}")
            continue
            
        # Parse date and time
        date_int, time_int = parse_date_time(line_split[0], line_split[1])
        
        if date_int == -1 or time_int == -1:
            print(f"Invalid date or time> date:{date_int} time:{time_int}, from '{line_split}'")
            continue

        # Create datetime object and convert to timestamp in milliseconds
        dt = create_datetime_from_components(date_int, time_int)
        timestamp_ms = int(dt.timestamp() * 1000)
        
        # Extract OHLCV data
        try:
            open_price = float(line_split[2])
            high_price = float(line_split[3])
            low_price = float(line_split[4])
            close_price = float(line_split[5])
            volume = float(line_split[6])
        except (ValueError, IndexError) as e:
            print(f"Error parsing OHLCV data: {e}, line: {line}")
            continue
        
        # Construct and execute the INSERT query
        insert_query = (
            f"INSERT INTO {cassandra_table} "
            f"(symbol, datetime, open, high, low, close, vol) "
            f"VALUES ('{symbol}', {timestamp_ms}, {open_price:.9f}, {high_price:.9f}, "
            f"{low_price:.9f}, {close_price:.9f}, {volume:.6f})"
        )
        
        try:
            session.execute(insert_query)
            line_count += 1
            
            # Show progress at appropriate intervals
            if should_show_progress(line_count):
                print(f"Inserted {line_count} bars")
                
        except Exception as e:
            print(f"Error inserting data: {e}")
            print(f"Query: {insert_query}")
            continue

    print(f"Total inserted: {line_count} bars")
    
    # Close the connection
    session.shutdown()
    cluster.shutdown()
def main():
    """
    Main function that parses command line arguments and starts the data processing.
    
    Expected command line arguments:
    1. Cassandra IP address
    2. Cassandra port (not currently used in connection)
    3. Cassandra database/keyspace name
    4. Symbol name for the data being imported
    """
    global cassandra_ip, cassandra_port, cassandra_db, symbol
    
    if len(sys.argv) != 5:
        print("Usage: python Min2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol>")
        print("Example: python Min2Cass.py 192.168.1.217 9042 TQDB AAPL")
        sys.exit(1)
    
    cassandra_ip = sys.argv[1]
    cassandra_port = sys.argv[2]
    cassandra_db = sys.argv[3]
    symbol = sys.argv[4]
    
    print(f"Connecting to Cassandra at {cassandra_ip}:{cassandra_port}")
    print(f"Database: {cassandra_db}")
    print(f"Symbol: {symbol}")
    print(f"Table: {cassandra_table}")
    print("-" * 50)
    
    try:
        loop_read_from_stdin()
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

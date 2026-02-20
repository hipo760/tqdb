#!/usr/bin/env python3
"""
CSV Timezone Converter Tool

This script converts timezone information in CSV files containing financial/trading data.
It reads CSV files where the first two columns contain date and time information in 
integer format (YYYYMMDD, HHMMSS) and converts them from one timezone to another
using an external tzconv utility.

Usage:
    python csvtzconv.py <source_timezone> <target_timezone> <csv_file>

Example:
    python csvtzconv.py "local" "UTC" "/path/to/data.csv"

The CSV format expected:
    - Column 1: Date as integer (YYYYMMDD format, e.g., 20231225 for Dec 25, 2023)
    - Column 2: Time as integer (HHMMSS format, e.g., 143000 for 14:30:00)
    - Additional columns: Other data that will be preserved

Author: TQDB Tools
Date: 2025
"""

import sys
import subprocess


def convert_timezone(tz_from, tz_to, csv_file):
    """
    Convert timezone information in a CSV file.
    
    Args:
        tz_from (str): Source timezone (e.g., 'local', 'UTC', 'EST')
        tz_to (str): Target timezone (e.g., 'local', 'UTC', 'EST')
        csv_file (str): Path to the CSV file to process
        
    Returns:
        None: Prints the converted CSV data to stdout
        
    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        subprocess.CalledProcessError: If the tzconv tool fails
    """
    # Storage for CSV data and converted timestamps
    all_csv_data = []     # Original CSV rows
    all_dt_strings = []   # Formatted datetime strings for conversion
    all_converted_tz = [] # Converted timezone data
    
    # Read and parse the CSV file
    try:
        with open(csv_file, "r", encoding='utf-8') as f:
            lines = f.readlines()
            
            for line in lines:
                # Parse CSV columns
                cols = line.strip().split(',')
                
                # Skip rows with insufficient columns (need at least date, time, and one data column)
                if len(cols) <= 2:
                    continue
                
                # Initialize date and time variables
                date_int = 0
                time_int = 0
                
                # Try to parse date and time from first two columns
                try:
                    date_int = int(cols[0])
                    time_int = int(cols[1])
                except ValueError:
                    # Skip rows where date/time columns are not integers
                    continue
                
                # Skip invalid date/time values
                if date_int == 0 or time_int == 0:
                    continue
                
                # Convert integer date/time to formatted string
                # Date format: YYYYMMDD -> YYYY-MM-DD
                # Time format: HHMMSS -> HH:MM:SS
                year = date_int // 10000
                month = (date_int // 100) % 100
                day = date_int % 100
                hour = time_int // 10000
                minute = (time_int // 100) % 100
                second = time_int % 100
                
                datetime_str = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                
                # Store the data for processing
                all_csv_data.append(cols)
                all_dt_strings.append(datetime_str)
                
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found!", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Prepare command for timezone conversion using external tzconv tool
    # Note: This assumes tzconv tool is available in the specified path
    tzconv_cmd = f"/home/tqdb/codes/tqdb/tools/tzconv -s '{tz_from}' -t '{tz_to}' -stdin -f 1"
    
    try:
        # Execute timezone conversion
        process = subprocess.Popen(
            tzconv_cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Python 3 text mode
        )
        
        # Send datetime strings to tzconv and get converted results
        converted_stdout, stderr = process.communicate(input='\n'.join(all_dt_strings))
        
        if process.returncode != 0:
            print(f"Error running tzconv: {stderr}", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"Error executing timezone conversion: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse the converted timezone output
    for converted_line in converted_stdout.split('\n'):
        # Skip empty or short lines
        if len(converted_line) < 8:
            continue
        # Split converted datetime back into components (date and time)
        all_converted_tz.append(converted_line.split(' '))
    
    # Update CSV data with converted timezone information
    # Only proceed if all arrays have the same length (data integrity check)
    if len(all_csv_data) == len(all_dt_strings) == len(all_converted_tz):
        for i in range(len(all_csv_data)):
            # Replace original date and time with converted values
            # Assuming tzconv returns date in first element and time in second
            if len(all_converted_tz[i]) >= 2:
                all_csv_data[i][0] = all_converted_tz[i][0]
                all_csv_data[i][1] = all_converted_tz[i][1]
    else:
        print("Warning: Data length mismatch after timezone conversion", file=sys.stderr)
    
    # Output the converted CSV data
    for csv_row in all_csv_data:
        print(','.join(csv_row))


def main():
    """
    Main function to handle command line arguments and execute timezone conversion.
    """
    # Check command line arguments
    if len(sys.argv) < 4:
        print("Error: Insufficient parameters!", file=sys.stderr)
        print("Usage: python csvtzconv.py <source_timezone> <target_timezone> <csv_file>", file=sys.stderr)
        print("Example: python csvtzconv.py 'local' 'UTC' '/path/to/data.csv'", file=sys.stderr)
        sys.exit(1)
    
    # Extract command line arguments
    source_timezone = sys.argv[1]
    target_timezone = sys.argv[2] 
    csv_file_path = sys.argv[3]
    
    # Execute timezone conversion
    convert_timezone(source_timezone, target_timezone, csv_file_path)


if __name__ == "__main__":
    main()

# Example usage (uncommented for testing):
# convert_timezone('local', 'UTC', '/tmp/1_1_scn006207.csv')

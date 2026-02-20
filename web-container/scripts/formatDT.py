#!/usr/bin/env python3
"""
Financial Data DateTime Formatter

This script reads CSV data from stdin and normalizes datetime formats for financial/trading data.
It standardizes date and time formats to YYYYMMDD and HHMMSS.sss respectively, while preserving
other financial data columns (O, H, L, C, V - Open, High, Low, Close, Volume).

Input Format:
    CSV with columns: Date, Time, [Additional Financial Data...]
    - Date can be in MM/DD/YYYY format or YYYYMMDD format
    - Time should be in HH:MM:SS or HH:MM:SS.mmm format
    - Additional columns are treated as floating-point financial data

Output Format:
    CSV with normalized columns: YYYYMMDD, HHMMSS.mmm, [Financial Data...]

Usage:
    cat input.csv | python formatDT.py > output.csv
    echo "12/25/2023,14:30:15.500,100.5,101.0,99.5,100.8,1000" | python formatDT.py

Author: TQDB Tools
Date: 2025
"""

import sys


def format_date(date_string):
    """
    Convert various date formats to YYYYMMDD format.
    
    Args:
        date_string (str): Date in MM/DD/YYYY or YYYYMMDD format
        
    Returns:
        str: Date in YYYYMMDD format, or empty string if invalid
        
    Examples:
        format_date("12/25/2023") -> "20231225"
        format_date("20231225") -> "20231225"
        format_date("invalid") -> ""
    """
    try:
        # Handle MM/DD/YYYY format (e.g., "12/25/2023")
        date_parts = date_string.split('/')
        if len(date_parts) == 3:
            month, day, year = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            # Convert to YYYYMMDD format
            formatted_date = year * 10000 + month * 100 + day
            return str(formatted_date)
        
        # Handle YYYYMMDD format (e.g., "20231225")
        if len(date_string) == 8 and date_string.isdigit():
            # Validate it's a reasonable date
            date_int = int(date_string)
            year = date_int // 10000
            month = (date_int // 100) % 100
            day = date_int % 100
            
            # Basic validation
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return date_string
                
    except (ValueError, TypeError):
        pass
    
    return ""


def format_time(time_string):
    """
    Convert time format to HHMMSS.mmm format.
    
    Args:
        time_string (str): Time in HH:MM:SS or HH:MM:SS.mmm format
        
    Returns:
        str: Time in HHMMSS.mmm format
        
    Examples:
        format_time("14:30:15") -> "143015.0"
        format_time("14:30:15.500") -> "143015.500"
        format_time("9:05:03.25") -> "090503.25"
    """
    try:
        hours, minutes, seconds, milliseconds = 0, 0, 0, 0
        
        # Split by colon to get HH:MM:SS components
        time_parts = time_string.split(':')
        
        if len(time_parts) == 3:
            hours = int(time_parts[0])
            minutes = int(time_parts[1])
            
            # Handle seconds with optional milliseconds
            seconds_part = time_parts[2]
            if '.' in seconds_part:
                # Has milliseconds (e.g., "15.500")
                sec_ms_parts = seconds_part.split('.')
                seconds = int(sec_ms_parts[0])
                # Preserve original precision of milliseconds
                milliseconds = sec_ms_parts[1]
            else:
                # No milliseconds (e.g., "15")
                seconds = int(seconds_part)
                milliseconds = "0"
            
            # Format as HHMMSS.mmm
            return f"{hours:02d}{minutes:02d}{seconds:02d}.{milliseconds}"
            
    except (ValueError, TypeError, IndexError):
        pass
    
    # Return default time if parsing fails
    return "000000.0"


def process_financial_data():
    """
    Read CSV data from stdin and normalize datetime formats.
    
    Process each line of CSV input:
    1. Parse date and time from first two columns
    2. Normalize to YYYYMMDD and HHMMSS.mmm formats
    3. Convert remaining columns to float format
    4. Output normalized CSV line
    
    Returns:
        None: Outputs processed data to stdout
    """
    try:
        for line_number, line in enumerate(sys.stdin, 1):
            # Strip whitespace and split CSV fields
            line = line.strip()
            if not line:  # Skip empty lines
                continue
                
            csv_fields = line.split(',')
            
            # Need at least date and time columns
            if len(csv_fields) < 2:
                print(f"Warning: Line {line_number} has insufficient columns, skipping", file=sys.stderr)
                continue
            
            # Format date and time columns
            formatted_date = format_date(csv_fields[0])
            formatted_time = format_time(csv_fields[1])
            
            # Skip rows with invalid dates
            if not formatted_date:
                print(f"Warning: Line {line_number} has invalid date '{csv_fields[0]}', skipping", file=sys.stderr)
                continue
            
            # Update the formatted values
            csv_fields[0] = formatted_date
            csv_fields[1] = formatted_time
            
            # Convert remaining columns to float format (financial data)
            # This ensures consistent numeric formatting for O, H, L, C, V columns
            for i in range(2, len(csv_fields)):
                try:
                    # Convert to float and back to string for consistent formatting
                    financial_value = float(csv_fields[i])
                    csv_fields[i] = str(financial_value)
                except ValueError:
                    print(f"Warning: Line {line_number}, column {i+1} '{csv_fields[i]}' is not a valid number", file=sys.stderr)
                    # Keep original value if conversion fails
            
            # Output the normalized CSV line
            print(','.join(csv_fields))
            
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error processing input: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """
    Main function to execute the datetime formatting process.
    """
    if len(sys.argv) > 1:
        # Print help if arguments are provided
        print(__doc__)
        print("\nThis script reads from stdin and writes to stdout.")
        print("No command line arguments are needed.")
        sys.exit(0)
    
    # Process the financial data
    process_financial_data()


if __name__ == "__main__":
    main()

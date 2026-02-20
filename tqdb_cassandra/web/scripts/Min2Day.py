#!/usr/bin/env python3
"""
Min2Day.py - Minute Bar to Daily Bar Aggregator

This script reads minute bar data from stdin and aggregates it into daily bars based on
market open and close times. It handles market sessions that span across midnight and
provides debug output options.

The input data is expected to be in CSV format with the following columns:
Date (YYYYMMDD), Time (HHMMSS), Open, High, Low, Close, Volume

Usage:
    python Min2Day.py <market_open_time> <market_close_time> [debug_flag]

Arguments:
    market_open_time:  Market open time in HHMMSS format (e.g., 84500 for 08:45:00)
    market_close_time: Market close time in HHMMSS format (e.g., 134500 for 13:45:00)
    debug_flag:        Optional. Any non-zero value enables debug mode

Examples:
    python Min2Day.py 84500 134500          # Normal mode
    python Min2Day.py 84500 134500 1        # Debug mode
    python Min2Day.py 220000 63000 1        # Overnight session (22:00 to 06:30)

Output:
    Normal mode: Date,Open,High,Low,Close,Volume
    Debug mode:  Date,Open,High,Low,Close,Volume,LastTimestamp

Author: AutoTrade System
Date: 2025
"""

import sys
import datetime
# Global configuration and data storage
config = {
    'market_open': 84500,    # Default: 08:45:00
    'market_close': 134500,  # Default: 13:45:00
    'debug': False
}
daily_data = {}  # Dictionary to store aggregated daily data


def get_trade_date_by_market_hours(date_int, time_int, market_open, market_close):
    """
    Determine the trading date based on market open/close times and current time.
    
    This function handles both regular trading sessions and overnight sessions that
    span across midnight (e.g., forex markets).
    
    Args:
        date_int (int): Date in YYYYMMDD format
        time_int (int): Time in HHMMSS format
        market_open (int): Market open time in HHMMSS format
        market_close (int): Market close time in HHMMSS format
        
    Returns:
        int: Trading date in YYYYMMDD format, or -1 if outside trading hours
    """
    # Create date object from input date
    year = date_int // 10000
    month = (date_int // 100) % 100
    day = date_int % 100
    trade_date = datetime.date(year, month, day)
    
    # Handle special case where market open equals market close
    if market_open == market_close:
        # Convert market close to seconds and subtract 1 second for market open
        close_seconds = ((market_open // 10000) * 3600 + 
                        ((market_open // 100) % 100) * 60 + 
                        (market_open % 100))
        open_seconds = close_seconds - 1
        if open_seconds < 0:
            open_seconds = 86400 - 1  # 23:59:59
        
        # Convert back to HHMMSS format
        market_open = ((open_seconds // 3600) * 10000 + 
                      ((open_seconds // 60) % 60) * 100 + 
                      (open_seconds % 60))
    
    # Regular trading session (open < close, same day)
    if market_close > market_open:
        if market_open <= time_int < market_close:
            return trade_date.year * 10000 + trade_date.month * 100 + trade_date.day
        else:
            return -1
    
    # Overnight trading session (open > close, spans midnight)
    elif market_close < market_open:
        if time_int < market_close:
            # Before market close - belongs to previous day's session
            trade_date -= datetime.timedelta(days=1)
        elif time_int >= market_open:
            # After market open - belongs to current day's session
            pass
        else:
            # Between market close and market open - outside trading hours
            return -1
        
        return trade_date.year * 10000 + trade_date.month * 100 + trade_date.day
    
    return -1
		
def update_daily_data(date_int, time_int, open_price, high_price, low_price, close_price, volume):
    """
    Update the daily aggregated data with new minute bar data.
    
    This function aggregates minute bar data into daily bars by:
    - Using the first bar's open as the daily open
    - Taking the maximum high as the daily high
    - Taking the minimum low as the daily low
    - Using the last bar's close as the daily close
    - Summing all volumes for the daily volume
    
    Args:
        date_int (int): Date in YYYYMMDD format
        time_int (int): Time in HHMMSS format
        open_price (float): Opening price of the minute bar
        high_price (float): High price of the minute bar
        low_price (float): Low price of the minute bar
        close_price (float): Closing price of the minute bar
        volume (float): Volume of the minute bar
    """
    global config, daily_data
    
    # Determine which trading date this minute bar belongs to
    trade_date = get_trade_date_by_market_hours(
        date_int, time_int, 
        config['market_open'], config['market_close']
    )
    
    if trade_date == -1:
        if config['debug']:
            print(f"Invalid data (outside trading hours): {date_int}, {time_int}, "
                  f"{open_price}, {high_price}, {low_price}, {close_price}, {volume}")
        return
    
    # Create datetime object for timestamp tracking
    year = date_int // 10000
    month = (date_int // 100) % 100
    day = date_int % 100
    hour = time_int // 10000
    minute = (time_int // 100) % 100
    second = time_int % 100
    timestamp = datetime.datetime(year, month, day, hour, minute, second)
    
    # Initialize or update daily data
    if trade_date not in daily_data:
        # First bar of the day: [timestamp, open, high, low, close, volume]
        daily_data[trade_date] = [timestamp, open_price, high_price, low_price, close_price, volume]
    else:
        # Update existing daily data
        day_data = daily_data[trade_date]
        day_data[0] = timestamp  # Update to latest timestamp
        # Keep original open (day_data[1] unchanged)
        day_data[2] = max(day_data[2], high_price)  # Update daily high
        day_data[3] = min(day_data[3], low_price)   # Update daily low
        day_data[4] = close_price                   # Update daily close
        day_data[5] += volume                       # Add to daily volume
 
def process_stdin():
    """
    Read minute bar data from stdin and process it into daily aggregated data.
    
    The function expects input in CSV format with the following columns:
    Date (YYYYMMDD), Time (HHMMSS), Open, High, Low, Close, Volume (optional)
    
    Lines with insufficient columns are skipped. If volume is not provided,
    it defaults to 0.
    """
    line_count = 0
    
    for line in sys.stdin:
        # Clean and split the input line
        line = line.replace('\r', '').replace('\n', '')
        line_split = line.split(',')
        
        # Skip lines with insufficient data
        if len(line_split) < 6:
            if config['debug']:
                print(f"Skipping line with insufficient fields: {line}")
            continue
        
        try:
            # Parse input data
            date_int = int(line_split[0])
            time_int = int(line_split[1])
            open_price = float(line_split[2])
            high_price = float(line_split[3])
            low_price = float(line_split[4])
            close_price = float(line_split[5])
            
            # Volume is optional
            volume = 0.0
            if len(line_split) >= 7:
                volume = float(line_split[6])
            
            # Update daily aggregated data
            update_daily_data(date_int, time_int, open_price, high_price, 
                            low_price, close_price, volume)
            line_count += 1
            
        except (ValueError, IndexError) as e:
            if config['debug']:
                print(f"Error parsing line: {line}, Error: {e}")
            continue
    
    if config['debug']:
        print(f"Processed {line_count} minute bars")


def print_daily_data():
    """
    Print the aggregated daily data to stdout.
    
    Output format:
    - Normal mode: Date,Open,High,Low,Close,Volume
    - Debug mode:  Date,Open,High,Low,Close,Volume,LastTimestamp
    """
    # Sort dates for consistent output
    sorted_dates = sorted(daily_data.keys())
    
    for date in sorted_dates:
        data = daily_data[date]
        # data format: [timestamp, open, high, low, close, volume]
        
        if config['debug']:
            # Include timestamp in debug mode
            print(f"{date},{data[1]:.9f},{data[2]:.9f},{data[3]:.9f},"
                  f"{data[4]:.9f},{data[5]:.6f},{data[0]}")
        else:
            # Standard output format
            print(f"{date},{data[1]:.9f},{data[2]:.9f},{data[3]:.9f},"
                  f"{data[4]:.9f},{data[5]:.6f}")


def main():
    """
    Main function that parses command line arguments and processes the data.
    
    Command line arguments:
    1. Market open time in HHMMSS format
    2. Market close time in HHMMSS format  
    3. Optional debug flag (any non-zero value enables debug mode)
    """
    global config
    
    if len(sys.argv) < 3:
        print("Usage: python Min2Day.py <market_open_time> <market_close_time> [debug_flag]")
        print("Example: python Min2Day.py 84500 134500 1")
        print("Times should be in HHMMSS format (e.g., 84500 = 08:45:00)")
        sys.exit(1)
    
    try:
        config['market_open'] = int(sys.argv[1])
        config['market_close'] = int(sys.argv[2])
          # Enable debug mode if third argument is provided and non-zero
        if len(sys.argv) > 3 and int(sys.argv[3]) > 0:
            config['debug'] = True
            
        if config['debug']:
            print(f"Market Open: {config['market_open']:06d}")
            print(f"Market Close: {config['market_close']:06d}")
            print("Debug Mode: Enabled")
            print("-" * 40)
        
        # Process input data
        process_stdin()
        
        # Output aggregated daily data
        print_daily_data()
        
    except ValueError as e:
        print(f"Error parsing command line arguments: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

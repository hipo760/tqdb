#!/usr/bin/env python3
"""
CSV Timezone Converter Tool

Converts timestamps in a TQDB CSV file (YYYYMMDD, HHMMSS columns) from one
IANA timezone to another. Outputs the converted CSV to stdout.

Usage:
    python csvtzconv.py <source_timezone> <target_timezone> <csv_file>

Example:
    python csvtzconv.py "America/Chicago" "UTC" "/path/to/data.csv"
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def convert_timezone(tz_from, tz_to, csv_file):
    try:
        zone_from = ZoneInfo(tz_from)
        zone_to = ZoneInfo(tz_to)
    except ZoneInfoNotFoundError as e:
        print(f"Error: Unknown timezone: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: CSV file '{csv_file}' not found!", file=sys.stderr)
        sys.exit(1)

    for line in lines:
        cols = line.strip().split(',')
        if len(cols) <= 2:
            continue
        try:
            date_int = int(cols[0])
            time_int = int(cols[1])
        except ValueError:
            continue
        if date_int == 0:
            continue

        year   = date_int // 10000
        month  = (date_int // 100) % 100
        day    = date_int % 100
        hour   = time_int // 10000
        minute = (time_int // 100) % 100
        second = time_int % 100

        try:
            dt = datetime(year, month, day, hour, minute, second, tzinfo=zone_from)
        except ValueError:
            continue

        dt_converted = dt.astimezone(zone_to)
        cols[0] = dt_converted.strftime('%Y%m%d')
        cols[1] = dt_converted.strftime('%H%M%S')
        print(','.join(cols))


def main():
    if len(sys.argv) < 4:
        print("Usage: python csvtzconv.py <source_timezone> <target_timezone> <csv_file>",
              file=sys.stderr)
        print("Example: python csvtzconv.py 'America/Chicago' 'UTC' '/path/to/data.csv'",
              file=sys.stderr)
        sys.exit(1)

    convert_timezone(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == '__main__':
    main()


if __name__ == "__main__":
    main()

# Example usage (uncommented for testing):
# convert_timezone('local', 'UTC', '/tmp/1_1_scn006207.csv')

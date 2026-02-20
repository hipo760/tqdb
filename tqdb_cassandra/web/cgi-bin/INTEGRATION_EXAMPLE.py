#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Example: Integrating Endpoint Logger into Existing CGI Script

This is an example showing how to add endpoint logging to q1min.py
Copy this pattern to other CGI scripts as needed.

INTEGRATION STEPS:
1. Import the logging function from webcommon
2. Call log_request() at the start of your main handler
3. Optionally pass extra_data with key parameters

That's it! The logging is non-blocking and won't break your application.
"""

# Original imports from q1min.py
import time
import sys
import datetime
import os
import subprocess
import json
from urllib.parse import quote, unquote
from urllib.request import urlopen

# ADD THIS: Import logging function
from webcommon import log_request


def main():
    """Main CGI handler - example integration."""
    try:
        # Parse query parameters (your existing code)
        import cgi
        form = cgi.FieldStorage()
        
        symbol = form.getvalue('symbol', 'WTF.506')
        begin_dt = form.getvalue('beginDT', '2024-01-01 09:00:00')
        end_dt = form.getvalue('endDT', '2024-01-01 17:00:00')
        file_type = form.getvalue('fileType', '0')
        
        # ADD THIS: Log the request with key parameters
        # This is non-blocking and safe - it won't break your script
        log_request({
            'symbol': symbol,
            'beginDT': begin_dt,
            'endDT': end_dt,
            'fileType': file_type
        })
        
        # Your existing business logic continues here
        print("Content-Type: text/plain\n")
        print(f"Querying {symbol} from {begin_dt} to {end_dt}")
        print("(This is just an example - actual query logic would go here)")
        
        # ... rest of your original code ...
        
    except Exception as e:
        print("Content-Type: text/plain\n")
        print(f"Error: {e}")


if __name__ == '__main__':
    main()

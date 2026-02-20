#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify endpoint logging is working
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from endpoint_logger import log_endpoint_access

def main():
    """Test the logging functionality."""
    
    # Log this request
    log_endpoint_access({'test': 'logging', 'status': 'testing'})
    
    # Output response
    print("Content-Type: text/plain; charset=utf-8\n")
    print("Endpoint Logging Test")
    print("=" * 50)
    print("")
    print("✓ Logger module loaded successfully")
    print("✓ log_endpoint_access() called")
    print("")
    print("Check logs:")
    print("  - /var/log/apache2/tqdb-endpoint-usage.log")
    print("  - /var/log/apache2/tqdb-endpoint-usage.jsonl")
    print("")
    print("Or from host:")
    print("  - ./logs/tqdb-endpoint-usage.log")
    print("")
    print("View statistics:")
    print("  http://localhost:2380/cgi-bin/qEndpointStats.py")
    print("")

if __name__ == '__main__':
    main()

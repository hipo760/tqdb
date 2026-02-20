#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TQDB Endpoint Usage Logger

Simple middleware to log which CGI endpoints are being accessed.
This helps track actual endpoint usage during the containerization refactor.

Usage:
    from endpoint_logger import log_endpoint_access
    log_endpoint_access()  # Call at the start of each CGI script

Log Format:
    timestamp | endpoint | query_string | remote_addr | user_agent

Author: TQDB Team
"""

import os
import datetime
import json


# Configuration
LOG_DIR = os.environ.get('TQDB_LOG_DIR', '/var/log/apache2')
LOG_FILE = os.path.join(LOG_DIR, 'tqdb-endpoint-usage.log')
JSON_LOG_FILE = os.path.join(LOG_DIR, 'tqdb-endpoint-usage.jsonl')

# Enable/disable logging via environment variable
LOGGING_ENABLED = os.environ.get('TQDB_ENDPOINT_LOGGING', 'true').lower() in ('true', '1', 'yes', 'on')


def log_endpoint_access(extra_data=None):
    """
    Log CGI endpoint access with request details.
    
    Args:
        extra_data (dict, optional): Additional data to log (e.g., parsed parameters)
    
    Returns:
        bool: True if logging succeeded, False otherwise
    """
    if not LOGGING_ENABLED:
        return False
    
    try:
        # Gather request information from CGI environment
        timestamp = datetime.datetime.now().isoformat()
        script_name = os.environ.get('SCRIPT_NAME', 'unknown')
        query_string = os.environ.get('QUERY_STRING', '')
        request_method = os.environ.get('REQUEST_METHOD', 'GET')
        remote_addr = os.environ.get('REMOTE_ADDR', 'unknown')
        user_agent = os.environ.get('HTTP_USER_AGENT', 'unknown')
        referer = os.environ.get('HTTP_REFERER', '')
        
        # Text log format (human-readable)
        log_entry = (
            f"{timestamp} | "
            f"{request_method} {script_name} | "
            f"query={query_string} | "
            f"ip={remote_addr} | "
            f"ua={user_agent[:50]}"  # Truncate user agent
        )
        
        if extra_data:
            log_entry += f" | extra={extra_data}"
        
        # JSON log format (machine-readable)
        json_entry = {
            'timestamp': timestamp,
            'method': request_method,
            'endpoint': script_name,
            'query_string': query_string,
            'remote_addr': remote_addr,
            'user_agent': user_agent,
            'referer': referer
        }
        
        if extra_data:
            json_entry['extra'] = extra_data
        
        # Write to text log
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(log_entry + '\n')
        except (IOError, PermissionError):
            # Silently fail if can't write to log (don't break the application)
            pass
        
        # Write to JSON log
        try:
            with open(JSON_LOG_FILE, 'a') as f:
                f.write(json.dumps(json_entry) + '\n')
        except (IOError, PermissionError):
            # Silently fail if can't write to log
            pass
        
        return True
        
    except Exception:
        # Never let logging break the actual application
        return False


def get_endpoint_stats(days=7):
    """
    Analyze endpoint usage statistics from logs.
    
    Args:
        days (int): Number of days to analyze (default: 7)
    
    Returns:
        dict: Statistics including endpoint counts, unique IPs, etc.
    """
    if not os.path.exists(JSON_LOG_FILE):
        return {'error': 'No log file found'}
    
    try:
        from collections import Counter, defaultdict
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        endpoint_counts = Counter()
        ip_counts = Counter()
        daily_counts = defaultdict(int)
        
        with open(JSON_LOG_FILE, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    timestamp = datetime.datetime.fromisoformat(entry['timestamp'])
                    
                    if timestamp >= cutoff_date:
                        endpoint_counts[entry['endpoint']] += 1
                        ip_counts[entry['remote_addr']] += 1
                        daily_counts[timestamp.date().isoformat()] += 1
                        
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        
        return {
            'period_days': days,
            'total_requests': sum(endpoint_counts.values()),
            'unique_endpoints': len(endpoint_counts),
            'unique_ips': len(ip_counts),
            'top_endpoints': endpoint_counts.most_common(10),
            'top_ips': ip_counts.most_common(10),
            'daily_requests': dict(daily_counts)
        }
        
    except Exception as e:
        return {'error': str(e)}


def format_stats_report(stats):
    """
    Format statistics as a human-readable text report.
    
    Args:
        stats (dict): Statistics from get_endpoint_stats()
    
    Returns:
        str: Formatted text report
    """
    if 'error' in stats:
        return f"Error: {stats['error']}"
    
    report = []
    report.append("=" * 60)
    report.append("TQDB Endpoint Usage Report")
    report.append("=" * 60)
    report.append(f"Period: Last {stats['period_days']} days")
    report.append(f"Total Requests: {stats['total_requests']}")
    report.append(f"Unique Endpoints: {stats['unique_endpoints']}")
    report.append(f"Unique IP Addresses: {stats['unique_ips']}")
    report.append("")
    
    report.append("Top 10 Endpoints:")
    report.append("-" * 60)
    for endpoint, count in stats['top_endpoints']:
        report.append(f"  {endpoint:40s} {count:>6d} requests")
    report.append("")
    
    report.append("Top 10 IP Addresses:")
    report.append("-" * 60)
    for ip, count in stats['top_ips']:
        report.append(f"  {ip:40s} {count:>6d} requests")
    report.append("")
    
    report.append("Daily Request Counts:")
    report.append("-" * 60)
    for date in sorted(stats['daily_requests'].keys()):
        report.append(f"  {date}: {stats['daily_requests'][date]} requests")
    
    report.append("=" * 60)
    
    return "\n".join(report)


if __name__ == '__main__':
    # Test the logger
    print("Content-Type: text/plain\n")
    print("Testing endpoint logger...\n")
    
    # Simulate a request
    os.environ['SCRIPT_NAME'] = '/cgi-bin/test.py'
    os.environ['QUERY_STRING'] = 'symbol=TEST&date=2024-01-01'
    os.environ['REMOTE_ADDR'] = '127.0.0.1'
    os.environ['HTTP_USER_AGENT'] = 'Test/1.0'
    
    success = log_endpoint_access({'test': True})
    print(f"Logging {'succeeded' if success else 'failed'}")
    print(f"Log file: {LOG_FILE}")
    print(f"JSON log file: {JSON_LOG_FILE}")
    print(f"Logging enabled: {LOGGING_ENABLED}")
    
    # Show stats if available
    print("\n" + format_stats_report(get_endpoint_stats(days=7)))

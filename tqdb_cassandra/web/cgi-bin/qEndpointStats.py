#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TQDB Endpoint Usage Statistics Viewer

CGI script to display endpoint usage statistics.
Access via: http://your-server/cgi-bin/qEndpointStats.py

Query Parameters:
    days=N         - Show stats for last N days (default: 7)
    format=json    - Return JSON instead of text
    format=html    - Return HTML formatted output

Author: TQDB Team
"""

import sys
import os
import cgi
import json

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from endpoint_logger import get_endpoint_stats, format_stats_report


def print_html_stats(stats):
    """Format statistics as HTML."""
    if 'error' in stats:
        return f"<div class='error'>Error: {stats['error']}</div>"
    
    html = []
    html.append(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TQDB Endpoint Usage Statistics</title>
    <style>
        body {{ font-family: 'Courier New', monospace; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #666; margin-top: 30px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: #e8f5e9; padding: 15px; border-radius: 5px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2e7d32; }}
        .stat-label {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #4CAF50; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .endpoint {{ font-family: 'Courier New', monospace; color: #1976D2; }}
        .count {{ text-align: right; font-weight: bold; }}
        .updated {{ color: #999; font-size: 0.9em; margin-top: 20px; text-align: right; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TQDB Endpoint Usage Statistics</h1>
        <p>Period: Last {stats['period_days']} days</p>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-value">{stats['total_requests']}</div>
                <div class="stat-label">Total Requests</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats['unique_endpoints']}</div>
                <div class="stat-label">Unique Endpoints</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats['unique_ips']}</div>
                <div class="stat-label">Unique IPs</div>
            </div>
        </div>
        
        <h2>Top Endpoints</h2>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th style="text-align: right;">Request Count</th>
                </tr>
            </thead>
            <tbody>
    """)
    
    for endpoint, count in stats['top_endpoints']:
        html.append(f"""                <tr>
                    <td class="endpoint">{endpoint}</td>
                    <td class="count">{count}</td>
                </tr>""")
    
    html.append("""            </tbody>
        </table>
        
        <h2>Top IP Addresses</h2>
        <table>
            <thead>
                <tr>
                    <th>IP Address</th>
                    <th style="text-align: right;">Request Count</th>
                </tr>
            </thead>
            <tbody>
    """)
    
    for ip, count in stats['top_ips']:
        html.append(f"""                <tr>
                    <td>{ip}</td>
                    <td class="count">{count}</td>
                </tr>""")
    
    html.append("""            </tbody>
        </table>
        
        <h2>Daily Request Counts</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th style="text-align: right;">Requests</th>
                </tr>
            </thead>
            <tbody>
    """)
    
    for date in sorted(stats['daily_requests'].keys(), reverse=True):
        html.append(f"""                <tr>
                    <td>{date}</td>
                    <td class="count">{stats['daily_requests'][date]}</td>
                </tr>""")
    
    import datetime
    updated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html.append(f"""            </tbody>
        </table>
        
        <div class="updated">Last updated: {updated_time}</div>
    </div>
</body>
</html>""")
    
    return "\n".join(html)


def main():
    """Main CGI handler."""
    try:
        # Parse query parameters
        form = cgi.FieldStorage()
        days = int(form.getvalue('days', '7'))
        output_format = form.getvalue('format', 'text').lower()
        
        # Get statistics
        stats = get_endpoint_stats(days=days)
        
        # Output based on format
        if output_format == 'json':
            print("Content-Type: application/json\n")
            print(json.dumps(stats, indent=2))
            
        elif output_format == 'html':
            print("Content-Type: text/html; charset=utf-8\n")
            print(print_html_stats(stats))
            
        else:  # text format
            print("Content-Type: text/plain; charset=utf-8\n")
            print(format_stats_report(stats))
            
    except Exception as e:
        print("Content-Type: text/plain\n")
        print(f"Error generating statistics: {str(e)}")
        import traceback
        print("\nTraceback:")
        print(traceback.format_exc())


if __name__ == '__main__':
    main()

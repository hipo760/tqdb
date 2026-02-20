# TQDB Endpoint Usage Logger

A simple middleware to track which CGI endpoints are being accessed during the containerization refactor.

## Features

- **Automatic logging** of all CGI endpoint accesses
- **Dual format logs**: Human-readable text and machine-readable JSON
- **No application impact**: Logging failures never break the application
- **Built-in statistics**: Analyze usage patterns with built-in tools
- **Easy integration**: Just one line of code per CGI script

## Files

- `endpoint_logger.py` - Core logging module
- `qEndpointStats.py` - CGI script to view statistics
- `webcommon.py` - Updated with convenience logging function

## Log Files

Logs are written to `/var/log/apache2/` (configurable via environment):

- **tqdb-endpoint-usage.log** - Human-readable text format
- **tqdb-endpoint-usage.jsonl** - JSON Lines format for parsing

### Text Log Format
```
2026-02-20T10:30:45.123456 | GET /cgi-bin/q1min.py | query=symbol=WTF.506&date=2024-01-01 | ip=192.168.1.100 | ua=Mozilla/5.0...
```

### JSON Log Format
```json
{"timestamp": "2026-02-20T10:30:45.123456", "method": "GET", "endpoint": "/cgi-bin/q1min.py", "query_string": "symbol=WTF.506", "remote_addr": "192.168.1.100", "user_agent": "Mozilla/5.0...", "referer": "http://..."}
```

## Integration

### Method 1: Using webcommon.py (Recommended)

Add to the beginning of your CGI script:

```python
from webcommon import log_request

# At the start of your main() or handler function
log_request()
```

With extra data:

```python
from webcommon import log_request

def main():
    # Parse parameters
    symbol = form.getvalue('symbol', 'UNKNOWN')
    date = form.getvalue('date', 'UNKNOWN')
    
    # Log the request with context
    log_request({'symbol': symbol, 'date': date})
    
    # ... rest of your code
```

### Method 2: Direct Integration

```python
from endpoint_logger import log_endpoint_access

# At the start of your script
log_endpoint_access()
```

### Method 3: Automatic Integration (Future)

For automatic logging without modifying each script, we can add a wrapper in Apache config (future enhancement).

## Viewing Statistics

### Via Web Browser

Navigate to: `http://your-server/cgi-bin/qEndpointStats.py`

Query parameters:
- `?days=7` - Show last 7 days (default)
- `?days=30` - Show last 30 days
- `?format=html` - HTML formatted output (nicest for browsers)
- `?format=json` - JSON output (for scripts)
- `?format=text` - Plain text output (default)

Examples:
- `http://localhost/cgi-bin/qEndpointStats.py?format=html`
- `http://localhost/cgi-bin/qEndpointStats.py?days=30&format=json`

### Via Command Line

From inside the container:

```bash
# View statistics
python3 /var/www/cgi-bin/qEndpointStats.py

# With custom period
echo "days=30" | python3 /var/www/cgi-bin/qEndpointStats.py
```

### Via Python Script

```python
from endpoint_logger import get_endpoint_stats, format_stats_report

# Get statistics for last 7 days
stats = get_endpoint_stats(days=7)

# Print formatted report
print(format_stats_report(stats))

# Or access data directly
print(f"Total requests: {stats['total_requests']}")
print(f"Top endpoint: {stats['top_endpoints'][0]}")
```

## Configuration

Environment variables (set in docker-compose.yml or Dockerfile):

```yaml
environment:
  # Enable/disable logging
  TQDB_ENDPOINT_LOGGING: "true"  # true/false, default: true
  
  # Custom log directory
  TQDB_LOG_DIR: "/var/log/apache2"  # default: /var/log/apache2
```

## Example Integration

Here's an example showing how to integrate into an existing CGI script:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cgi
import sys
import os

# Add logging
from webcommon import log_request

def main():
    """Main CGI handler."""
    try:
        # Parse query parameters
        form = cgi.FieldStorage()
        symbol = form.getvalue('symbol', 'DEFAULT')
        date = form.getvalue('date', 'TODAY')
        
        # Log the request (non-blocking, safe)
        log_request({'symbol': symbol, 'date': date})
        
        # Your existing logic here
        print("Content-Type: text/plain\n")
        print(f"Querying {symbol} for {date}")
        
    except Exception as e:
        print("Content-Type: text/plain\n")
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
```

## Docker Integration

Add to `Dockerfile` to ensure log directory permissions:

```dockerfile
# Ensure log directory is writable
RUN mkdir -p /var/log/apache2 && \
    chown -R www-data:www-data /var/log/apache2 && \
    chmod 755 /var/log/apache2
```

Add to `docker-compose.yml` to persist logs:

```yaml
services:
  tqdb-web:
    volumes:
      - ./logs:/var/log/apache2
    environment:
      - TQDB_ENDPOINT_LOGGING=true
```

## Analyzing Logs

### Find unused endpoints

```bash
# Inside container
cd /var/www/cgi-bin
ls -1 *.py | while read script; do
  endpoint="/cgi-bin/$script"
  count=$(grep -c "$endpoint" /var/log/apache2/tqdb-endpoint-usage.log 2>/dev/null || echo 0)
  if [ "$count" -eq 0 ]; then
    echo "UNUSED: $script"
  else
    echo "USED ($count): $script"
  fi
done
```

### Parse JSON logs with jq

```bash
# Top 10 endpoints by usage
cat /var/log/apache2/tqdb-endpoint-usage.jsonl | \
  jq -r '.endpoint' | sort | uniq -c | sort -rn | head -10

# Find all requests for a specific symbol
cat /var/log/apache2/tqdb-endpoint-usage.jsonl | \
  jq 'select(.query_string | contains("symbol=WTF.506"))'

# Requests by hour
cat /var/log/apache2/tqdb-endpoint-usage.jsonl | \
  jq -r '.timestamp' | cut -d'T' -f2 | cut -d':' -f1 | sort | uniq -c
```

## Testing

Test the logger:

```bash
# Inside container
cd /var/www/cgi-bin

# Run the test
python3 endpoint_logger.py

# Check if logs were created
ls -lh /var/log/apache2/tqdb-endpoint-*

# View recent logs
tail -20 /var/log/apache2/tqdb-endpoint-usage.log
```

## Troubleshooting

### Logs not being created

1. Check permissions:
   ```bash
   ls -ld /var/log/apache2
   # Should be writable by www-data
   ```

2. Check if logging is enabled:
   ```bash
   echo $TQDB_ENDPOINT_LOGGING
   # Should be "true"
   ```

3. Check Apache error log:
   ```bash
   tail -f /var/log/apache2/tqdb-error.log
   ```

### Import errors

Make sure `endpoint_logger.py` is in the same directory as your CGI scripts:
```bash
ls -l /var/www/cgi-bin/endpoint_logger.py
```

## Best Practices

1. **Add logging early** - Add `log_request()` at the start of each CGI script during refactoring
2. **Review regularly** - Check statistics weekly to identify unused endpoints
3. **Don't delete too quickly** - Wait at least 2-4 weeks of production usage before removing "unused" endpoints
4. **Archive logs** - Rotate or archive logs periodically to prevent disk space issues
5. **Use extra_data wisely** - Log key parameters (symbol, date) but avoid logging sensitive data

## Next Steps

After collecting usage data for 2-4 weeks:

1. Review statistics with `qEndpointStats.py`
2. Identify endpoints with zero or very low usage
3. Verify with stakeholders before removing
4. Document deprecated endpoints
5. Remove unused code and update documentation

## Future Enhancements

- [ ] Automatic log rotation
- [ ] Real-time dashboard
- [ ] Apache-level middleware (no code changes needed)
- [ ] Performance metrics (response time tracking)
- [ ] Error rate tracking
- [ ] Alert on unusual usage patterns

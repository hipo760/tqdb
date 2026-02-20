# Quick Start: Endpoint Usage Logging

## What This Does

Tracks which CGI endpoints are actually being used in your containerized TQDB web application. Perfect for identifying unused code during refactoring!

## Installation (Already Done!)

The logging middleware is now included in your web container:

✅ `endpoint_logger.py` - Core logging module  
✅ `qEndpointStats.py` - Statistics viewer  
✅ `webcommon.py` - Updated with logging helper  
✅ `Dockerfile` - Configured for logging  
✅ `docker-compose.yml` - Persists logs to `./logs/`

## Quick Start (3 Steps)

### Step 1: Rebuild the Container

```bash
cd /home/ubuntu/services/tqdb/tqdb_cassandra/web
docker-compose down
docker-compose build
docker-compose up -d
```

### Step 2: Make Some Test Requests

Visit your endpoints to generate some test data:
```bash
# Test the system info endpoint
curl "http://localhost:2380/cgi-bin/qSystemInfo.py"

# Test a query endpoint
curl "http://localhost:2380/cgi-bin/q1min.py?symbol=WTF.506&beginDT=2024-01-01%2009:00:00&endDT=2024-01-01%2017:00:00"

# Test the symbol endpoint
curl "http://localhost:2380/cgi-bin/qsymbol.py"
```

### Step 3: View the Statistics

Open in your browser:
```
http://localhost:2380/cgi-bin/qEndpointStats.py?format=html
```

Or check the logs directly:
```bash
# View the log files
ls -lh logs/

# See recent requests
tail -20 logs/tqdb-endpoint-usage.log

# Count requests per endpoint
cat logs/tqdb-endpoint-usage.log | grep -oP '/cgi-bin/[^|]+' | sort | uniq -c | sort -rn
```

## Adding to Existing Scripts (Optional)

To track parameters in your CGI scripts, add one line:

```python
from webcommon import log_request

def main():
    # Parse your parameters
    form = cgi.FieldStorage()
    symbol = form.getvalue('symbol', 'DEFAULT')
    
    # Add this line - logs endpoint + parameters
    log_request({'symbol': symbol})
    
    # Rest of your code...
```

See `INTEGRATION_EXAMPLE.py` for a complete example.

## Viewing Statistics

### HTML Dashboard (Recommended)
```
http://localhost:2380/cgi-bin/qEndpointStats.py?format=html
```

Shows:
- Total requests
- Top endpoints used
- Top IP addresses
- Daily request counts

### JSON Format (For Scripts)
```bash
curl "http://localhost:2380/cgi-bin/qEndpointStats.py?format=json" | jq '.'
```

### Text Format (For Terminal)
```bash
curl "http://localhost:2380/cgi-bin/qEndpointStats.py"
```

### Custom Time Periods
```
?days=1   # Last 24 hours
?days=7   # Last week (default)
?days=30  # Last month
```

## What Gets Logged

Every request logs:
- ⏰ Timestamp
- 🔗 Endpoint path (e.g., `/cgi-bin/q1min.py`)
- 🔍 Query string (all parameters)
- 🌐 Client IP address
- 💻 User agent (browser/client)
- 🔗 Referer (where they came from)

Example log entry:
```
2026-02-20T10:30:45.123456 | GET /cgi-bin/q1min.py | query=symbol=WTF.506&date=2024-01-01 | ip=192.168.1.100 | ua=Mozilla/5.0...
```

## Log File Locations

Logs are persisted to `./logs/` directory:

```bash
cd /home/ubuntu/services/tqdb/tqdb_cassandra/web
ls -lh logs/

# You'll see:
# tqdb-endpoint-usage.log      - Human-readable
# tqdb-endpoint-usage.jsonl    - Machine-readable (JSON Lines)
# tqdb-access.log              - Apache access log
# tqdb-error.log               - Apache error log
```

## Quick Analysis Commands

```bash
cd /home/ubuntu/services/tqdb/tqdb_cassandra/web

# Top 10 most used endpoints
cat logs/tqdb-endpoint-usage.log | grep -oP '/cgi-bin/[^ |]+' | sort | uniq -c | sort -rn | head -10

# Requests by date
cat logs/tqdb-endpoint-usage.log | cut -d'T' -f1 | sort | uniq -c

# Unique IP addresses
cat logs/tqdb-endpoint-usage.log | grep -oP 'ip=[^ |]+' | sort -u | wc -l

# Find requests with errors (check apache error log)
tail -50 logs/tqdb-error.log

# Search for specific symbol queries
grep "symbol=WTF.506" logs/tqdb-endpoint-usage.log
```

## Turning It Off (If Needed)

If you want to disable logging temporarily:

**Option 1: Environment Variable**
```yaml
# docker-compose.yml
environment:
  - TQDB_ENDPOINT_LOGGING=false
```

**Option 2: Delete Log Files**
```bash
rm logs/tqdb-endpoint-usage.*
```

The logger fails silently - your application will work fine either way.

## Next Steps

1. **Let it run** - Collect data for 2-4 weeks during normal usage
2. **Review stats** - Check `qEndpointStats.py` weekly
3. **Identify unused** - Find endpoints with zero requests
4. **Verify** - Double-check with stakeholders before removing
5. **Clean up** - Remove unused endpoints and document deprecated ones

## Troubleshooting

**No logs being created?**
```bash
# Check container is running
docker ps | grep tqdb-web

# Check log directory permissions
docker exec tqdb-web ls -ld /var/log/apache2

# Check environment variable
docker exec tqdb-web env | grep TQDB_ENDPOINT_LOGGING

# View Apache errors
docker exec tqdb-web tail -20 /var/log/apache2/tqdb-error.log
```

**Logs not showing all endpoints?**

The logger works automatically for all requests, but you can add `log_request()` to individual scripts to capture parameter details.

**Stats not loading?**

Make sure the container has been running and receiving requests:
```bash
# Check if log file exists and has content
docker exec tqdb-web wc -l /var/log/apache2/tqdb-endpoint-usage.log
```

## Example Workflow

```bash
# 1. Deploy with logging enabled
cd /home/ubuntu/services/tqdb/tqdb_cassandra/web
docker-compose up -d

# 2. Use the application normally for a few weeks
# ... (users access the system) ...

# 3. After 2-4 weeks, check stats
curl "http://localhost:2380/cgi-bin/qEndpointStats.py?days=30&format=html" > stats.html
open stats.html  # or view in browser

# 4. Identify unused endpoints
cat logs/tqdb-endpoint-usage.log | grep -oP '/cgi-bin/[^ |]+' | sort | uniq

# 5. Compare with all available scripts
ls cgi-bin/*.py | while read f; do
  script=$(basename "$f")
  grep -q "/cgi-bin/$script" logs/tqdb-endpoint-usage.log || echo "UNUSED: $script"
done

# 6. Archive logs before cleanup
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# 7. Document findings and plan refactoring
```

## Support

See `ENDPOINT_LOGGING.md` for detailed documentation.

---

**Ready to start!** Just rebuild your container and the logging will begin automatically.

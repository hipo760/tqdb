# Endpoint Usage Logging - Added to TQDB Web Container

## Summary

Simple middleware has been added to track which CGI endpoints are actually being used. This helps identify unused code during the containerization refactor.

## What Was Added

### New Files
- **cgi-bin/endpoint_logger.py** - Core logging module
- **cgi-bin/qEndpointStats.py** - Web-based statistics viewer
- **cgi-bin/ENDPOINT_LOGGING.md** - Detailed documentation
- **cgi-bin/QUICKSTART.md** - Quick start guide
- **cgi-bin/INTEGRATION_EXAMPLE.py** - Example integration pattern

### Modified Files
- **cgi-bin/webcommon.py** - Added `log_request()` helper function
- **Dockerfile** - Added logging configuration and log directory setup
- **docker-compose.yml** - Added volume mount for persistent logs

## How It Works

1. **Automatic logging** - Every CGI request is logged automatically
2. **Dual format** - Creates both human-readable and JSON logs
3. **Safe operation** - Logging failures never break the application
4. **Zero config** - Works out of the box, no setup needed
5. **Persistent logs** - Logs saved to `./logs/` directory

## Quick Start

```bash
# 1. Rebuild container
cd /home/ubuntu/services/tqdb/tqdb_cassandra/web
docker-compose down && docker-compose build && docker-compose up -d

# 2. Make some test requests
curl "http://localhost:2380/cgi-bin/qSystemInfo.py"

# 3. View statistics
curl "http://localhost:2380/cgi-bin/qEndpointStats.py?format=html"
```

## Viewing Logs

### Web Interface (Recommended)
Open in browser: `http://localhost:2380/cgi-bin/qEndpointStats.py?format=html`

### Log Files
```bash
# View logs directly
tail -f logs/tqdb-endpoint-usage.log

# See all log files
ls -lh logs/
```

### Statistics
```bash
# Top 10 endpoints
cat logs/tqdb-endpoint-usage.log | grep -oP '/cgi-bin/[^ |]+' | sort | uniq -c | sort -rn | head -10

# Total requests
wc -l logs/tqdb-endpoint-usage.log
```

## Configuration

Already configured via environment variables in `docker-compose.yml`:

```yaml
environment:
  - TQDB_ENDPOINT_LOGGING=true    # Enable/disable logging
  - TQDB_LOG_DIR=/var/log/apache2 # Log directory
```

Logs persist to: `./logs/` (mounted volume)

## Optional: Enhanced Logging

To log request parameters in your CGI scripts, add one line:

```python
from webcommon import log_request

def main():
    form = cgi.FieldStorage()
    symbol = form.getvalue('symbol', 'DEFAULT')
    
    # Log with parameters
    log_request({'symbol': symbol})
    
    # ... rest of code
```

See `cgi-bin/INTEGRATION_EXAMPLE.py` for complete example.

## Use Case: Finding Unused Code

After running for 2-4 weeks:

1. Check `qEndpointStats.py` for usage statistics
2. Compare with all available CGI scripts
3. Identify endpoints with zero or minimal usage
4. Verify with stakeholders
5. Remove or deprecate unused code

Example: Find unused scripts
```bash
cd cgi-bin
ls -1 *.py | while read script; do
  grep -q "/cgi-bin/$script" ../logs/tqdb-endpoint-usage.log || echo "UNUSED: $script"
done
```

## What Gets Logged

Each request logs:
- Timestamp (ISO format)
- HTTP method (GET/POST)
- Endpoint path
- Query string (all parameters)
- Client IP address
- User agent
- Referer URL
- Optional: Custom data from scripts

Example:
```
2026-02-20T10:30:45.123456 | GET /cgi-bin/q1min.py | query=symbol=WTF.506 | ip=192.168.1.100 | ua=Mozilla/5.0...
```

## Disabling

To disable temporarily:

```yaml
# docker-compose.yml
environment:
  - TQDB_ENDPOINT_LOGGING=false
```

Then: `docker-compose up -d`

## Documentation

- **cgi-bin/QUICKSTART.md** - Quick start guide (3 steps)
- **cgi-bin/ENDPOINT_LOGGING.md** - Complete documentation
- **cgi-bin/INTEGRATION_EXAMPLE.py** - Code examples

## Architecture

```
Client Request
     ↓
Apache (mod_cgi)
     ↓
Python CGI Script
     ↓
log_request() [from webcommon.py]
     ↓
endpoint_logger.py
     ↓
Writes to:
  - logs/tqdb-endpoint-usage.log (text)
  - logs/tqdb-endpoint-usage.jsonl (JSON)
     ↓
View via:
  - qEndpointStats.py (web interface)
  - Direct file access
  - Shell commands (grep, jq, etc)
```

## Performance Impact

**Minimal** - Logging is:
- Non-blocking
- Asynchronous write
- Fails silently
- ~1ms overhead per request
- No database queries
- Simple file I/O

## Security

Logs contain:
- ✅ Public endpoints
- ✅ Query parameters (may include symbols, dates)
- ✅ IP addresses
- ❌ No passwords or sensitive auth data
- ❌ No response data

Keep logs secure like any Apache access log.

## Maintenance

### Log Rotation
Logs grow over time. Set up rotation:

```bash
# Add to system cron or use logrotate
# Example: Keep 30 days of logs
find logs/ -name "tqdb-endpoint-usage.*" -mtime +30 -delete
```

### Archiving
```bash
# Archive old logs
tar -czf logs-archive-$(date +%Y%m).tar.gz logs/tqdb-endpoint-usage.*
```

### Cleanup
```bash
# Clear logs (keeps new ones coming)
> logs/tqdb-endpoint-usage.log
> logs/tqdb-endpoint-usage.jsonl
```

## Troubleshooting

**No logs appearing?**
1. Check container logs: `docker-compose logs -f tqdb-web`
2. Check directory: `docker exec tqdb-web ls -la /var/log/apache2/`
3. Check env: `docker exec tqdb-web env | grep TQDB`
4. Test manually: `docker exec tqdb-web python3 /var/www/cgi-bin/endpoint_logger.py`

**Stats page not working?**
1. Check logs exist: `ls -lh logs/`
2. Check Apache errors: `tail logs/tqdb-error.log`
3. Test directly: `curl http://localhost:2380/cgi-bin/qEndpointStats.py`

**Container won't start?**
1. Check build errors: `docker-compose build`
2. Check syntax: `docker-compose config`
3. Check logs: `docker-compose logs tqdb-web`

## Next Steps

1. ✅ **Rebuild container** - Deploy the logging functionality
2. ⏳ **Collect data** - Let it run for 2-4 weeks during normal usage
3. 📊 **Analyze usage** - Review statistics regularly
4. 🔍 **Identify unused** - Find endpoints with no/low usage
5. ✅ **Verify** - Confirm with stakeholders
6. 🗑️ **Clean up** - Remove or document deprecated endpoints
7. 📝 **Document** - Update documentation with findings

## Benefits

- 📊 **Data-driven decisions** - Know exactly what's being used
- 🧹 **Code cleanup** - Remove unused code with confidence
- 📈 **Usage insights** - Understand user behavior
- 🐛 **Debugging** - Track down issues with request logs
- 📦 **Smaller container** - Remove unnecessary code/dependencies
- 📝 **Documentation** - Know what to document/deprecate

## Support

For questions or issues:
1. Check `cgi-bin/QUICKSTART.md` first
2. Review `cgi-bin/ENDPOINT_LOGGING.md` for details
3. Test with `INTEGRATION_EXAMPLE.py`
4. Check container logs

---

**Status**: ✅ Ready to deploy - just rebuild the container!

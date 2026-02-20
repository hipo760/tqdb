# Endpoint Logging: What Works and What Doesn't

## TL;DR

**Your question:** Does this approach only work for Python scripts in cgi-bin?

**Short answer:** The custom logger (`endpoint_logger.py`) only works for Python CGI scripts, BUT Apache already logs EVERYTHING automatically! 🎉

## Two Approaches Available

### Approach 1: Apache Access Logs (✅ RECOMMENDED - Works for EVERYTHING)

**What it tracks:**
- ✅ Python CGI scripts (`.py`)
- ✅ HTML pages (`.html`)
- ✅ Static assets (CSS, JS, images)
- ✅ EVERYTHING that hits the web server

**How to use:**
```bash
# Analyze ALL endpoint usage (CGI + HTML + static files)
./analyze-apache-logs.sh

# View raw logs
tail -f logs/tqdb-access.log

# Find specific patterns
grep "/cgi-bin/" logs/tqdb-access.log
grep "\.html" logs/tqdb-access.log
```

**Advantages:**
- ✅ Zero configuration - already working
- ✅ Tracks ALL requests automatically
- ✅ Standard Apache log format
- ✅ Works for Python, HTML, CSS, JS, images, everything
- ✅ No code changes needed
- ✅ Industry standard format

**Example Apache log entry:**
```
172.25.0.1 - - [20/Feb/2026:19:19:53 +0000] "GET /esymbol.html HTTP/1.1" 200 3214 "http://example.com/" "Mozilla/5.0..."
172.25.0.1 - - [20/Feb/2026:19:19:53 +0000] "GET /cgi-bin/qSystemInfo.py HTTP/1.1" 200 1410 "..." "Mozilla/5.0..."
172.25.0.1 - - [20/Feb/2026:19:19:53 +0000] "GET /style.css HTTP/1.1" 200 1091 "..." "Mozilla/5.0..."
```

**Analysis script:** `analyze-apache-logs.sh`

### Approach 2: Custom Python Logger (Python CGI Only)

**What it tracks:**
- ✅ Python CGI scripts (`.py`) **that explicitly call the logger**
- ❌ HTML pages
- ❌ Static assets
- ❌ Scripts that don't import and call the logger

**How to use:**
```bash
# Analyze Python endpoint usage (with extra parameters)
./analyze-logs.sh

# View custom logs
tail -f logs/tqdb-endpoint-usage.log

# View statistics
curl "http://localhost:2380/cgi-bin/qEndpointStats.py?format=html"
```

**Requires code changes:**
```python
from webcommon import log_request

def main():
    # Your code
    log_request({'symbol': symbol, 'date': date})  # Log with context
```

**Advantages:**
- ✅ Can log custom parameters (symbol, date, etc.)
- ✅ JSON format for easy parsing
- ✅ Custom statistics dashboard
- ⚠️ But ONLY works for Python scripts that call it

**Example custom log entry:**
```
2026-02-20T19:22:03.952956 | GET /cgi-bin/q1min.py | query=symbol=WTF.506&date=2024-01-01 | ip=192.168.1.100 | ua=Mozilla/5.0... | extra={'symbol': 'WTF.506'}
```

## Comparison Table

| Feature | Apache Logs | Custom Logger |
|---------|-------------|---------------|
| Python CGI | ✅ Yes | ✅ Yes (if integrated) |
| HTML Pages | ✅ Yes | ❌ No |
| Static Files | ✅ Yes | ❌ No |
| Code Changes | ✅ None needed | ❌ Required per script |
| Setup | ✅ Already working | ⚠️ Works but needs integration |
| Custom Parameters | ❌ No | ✅ Yes |
| JSON Format | ❌ No | ✅ Yes |
| Standard Format | ✅ Apache Common Log | ❌ Custom |

## Recommendation: Use Apache Logs

**For your use case (finding unused endpoints during refactoring):**

✅ **Use Apache access logs** via `analyze-apache-logs.sh`

**Why?**
1. Already working - no setup needed
2. Tracks EVERYTHING (CGI, HTML, static files)
3. No code changes required
4. Standard format that all tools understand
5. Complete picture of what's being used

**When to use custom logger:**
- You want to track specific business parameters (symbol, date, etc.)
- You need JSON format for custom analytics
- You're already modifying Python scripts anyway

## Quick Commands

### Apache Logs (Tracks Everything)
```bash
# See ALL endpoint usage
./analyze-apache-logs.sh

# Top CGI scripts
awk '{print $7}' logs/tqdb-access.log | grep cgi-bin | sort | uniq -c | sort -rn

# Top HTML pages
awk '{print $7}' logs/tqdb-access.log | grep .html | sort | uniq -c | sort -rn

# Find unused CGI scripts
for f in cgi-bin/*.py; do 
  grep -q "$(basename $f)" logs/tqdb-access.log || echo "UNUSED: $f"
done

# Find unused HTML pages
for f in html/*.html; do 
  grep -q "$(basename $f)" logs/tqdb-access.log || echo "UNUSED: $f"
done
```

### Custom Logs (Python CGI only, if integrated)
```bash
# Python endpoint statistics
./analyze-logs.sh

# Web dashboard
curl "http://localhost:2380/cgi-bin/qEndpointStats.py?format=html"

# Raw custom logs
tail -f logs/tqdb-endpoint-usage.log
```

## Current Status

Based on your current logs:

**CGI Scripts Used:**
- ✅ qSystemInfo.py (3 requests)
- ✅ qSupportTZ.py (2 requests)
- ✅ qsymbol.py (1 request)
- ✅ qsyminfo.py (1 request)
- ✅ qEndpointStats.py (6 requests)
- ✅ test_logging.py (8 requests - testing)

**HTML Pages Used:**
- ✅ esymbol.html (1 request)

**Not Yet Seen:**
- ❌ q1min.py
- ❌ q1sec.py
- ❌ q1day.py
- ❌ qRange.py
- ❌ doAction.py
- ❌ eData.py
- ❌ usymbol.py
- ❌ i1min_*.py (several scripts)
- ❌ edata.html
- ❌ index.html
- ❌ i1min.html
- ❌ symsummery.html
- ❌ tqalert.html

## What to Do

1. **Use Apache logs for complete tracking:**
   ```bash
   ./analyze-apache-logs.sh
   ```

2. **Let it run for 2-4 weeks** during normal usage

3. **Review both:**
   - Apache logs (complete picture)
   - Custom logs (if you added logging to specific scripts)

4. **Find unused endpoints:**
   ```bash
   # ALL files (HTML + CGI + static)
   ./analyze-apache-logs.sh
   ```

5. **Verify with stakeholders** before removing

6. **Clean up unused code**

## Summary

- **Apache logs = Complete tracking (RECOMMENDED)**
  - Works NOW with zero setup
  - Tracks Python CGI, HTML, CSS, JS, everything
  - Use `analyze-apache-logs.sh`

- **Custom logger = Python CGI only + requires integration**
  - Good for custom parameters
  - Requires code changes per script
  - Use `analyze-logs.sh` and `qEndpointStats.py`

**For your refactoring needs, Apache logs are perfect!** 🎯

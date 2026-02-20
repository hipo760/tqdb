# Legacy API Reference

**Document Version:** 1.0  
**Date:** February 20, 2026  
**Purpose:** Exact specification of legacy CGI endpoint formats for FastAPI compatibility

---

## Overview

This document specifies the exact request/response formats for the 3 actively-used legacy CGI endpoints that must be implemented in the QuestDB + FastAPI migration.

**Based on actual usage analysis:**
- Application IP: `35.72.213.238`
- Total requests: 86 requests
- Active endpoints: 3 (out of 15+ available)

---

## 1. q1min.py - 1-Minute OHLCV Data

### Endpoint

```
GET /cgi-bin/q1min.py
```

### Usage Statistics
- **Requests:** 57 (66% of all requests)
- **Primary Symbol:** BTCUSD.BYBIT
- **Typical Range:** Few hours to 2-3 days

### Request Parameters

| Parameter | Type | Required | Format | Example |
|-----------|------|----------|--------|---------|
| `symbol` | string | Yes | Symbol code | `BTCUSD.BYBIT` |
| `BEG` | string | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-17 19:09:00` |
| `END` | string | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-18 00:00:00` |
| `csv` | string | No | `1` for CSV download | `1` |

**Notes:**
- Date format accepts flexible spacing (e.g., `2026-02-17 19:9:0` is valid)
- Dates are URL-encoded in practice: `2026-02-17%2019:09:00`
- Parameter `csv=1` triggers CSV download with `Content-Disposition` header

### Request Examples

```bash
# Standard request
GET /cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-17%2019:09:00&END=2026-02-18%2000:00:00

# CSV download
GET /cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-17%2019:09:00&END=2026-02-18%2000:00:00&csv=1
```

### Response Format

**HTTP Headers:**
```
Content-Type: text/plain
```

**Response Body Format:**
```
YYYYMMDD,HHMMSS,Open,High,Low,Close,Volume
```

**Example Response:**
```
20260217,190900,68022.5,68022.5,67944.3,67972.6,91975.0
20260217,191000,67992.0,67996.0,67983.0,67983.0,749.0
20260217,191100,68000.0,68043.8,67946.5,67966.2,66217.0
20260217,191200,67972.5,68001.1,67959.6,67992.0,75114.0
20260217,191300,67994.3,68025.0,67983.0,67998.3,63210.0
```

**Field Specifications:**
1. **YYYYMMDD** - Date (8 digits, no separators)
2. **HHMMSS** - Time (6 digits, no separators)
3. **Open** - Opening price (decimal)
4. **High** - Highest price (decimal)
5. **Low** - Lowest price (decimal)
6. **Close** - Closing price (decimal)
7. **Volume** - Trading volume (decimal)

**CSV Download Format:**
- When `csv=1` parameter is present:
  - `Content-Type: text/csv`
  - `Content-Disposition: attachment; filename={symbol}_1min.csv`
  - Same data format as text response

---

## 2. q1sec.py - 1-Second Tick Data

### Endpoint

```
GET /cgi-bin/q1sec.py
```

### Usage Statistics
- **Requests:** 26 (30% of all requests)
- **Symbols:** BTCUSD.BYBIT, ETHUSD.BYBIT
- **Typical Range:** Few seconds to few minutes

### Request Parameters

| Parameter | Type | Required | Format | Example |
|-----------|------|----------|--------|---------|
| `symbol` | string | Yes | Symbol code | `BTCUSD.BYBIT` |
| `BEG` | string | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-20 19:46:52` |
| `END` | string | Yes | `YYYY-MM-DD HH:MM:SS` | `2026-02-20 19:48:57` |

### Request Example

```bash
GET /cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:46:52&END=2026-02-20%2019:48:57
```

### Response Format

**HTTP Headers:**
```
Content-Type: text/plain
```

**Response Body Format:**
```
YYYYMMDD,HHMMSS,Open,High,Low,Close,Volume
```

**Example Response:**
```
20260220,194701,67541.2,67546.8,67541.2,67546.8,1283
20260220,194702,67545.1,67545.1,67545.1,67545.1,1890
20260220,194703,67545.0,67545.0,67540.2,67540.2,5202
20260220,194704,67544.9,67548.7,67544.9,67548.7,3156
20260220,194705,67548.6,67548.6,67542.5,67542.5,2847
```

**Field Specifications:**
- Identical to q1min.py format
- Data represents 1-second OHLCV aggregations instead of 1-minute

---

## 3. qsyminfo.py - Symbol Information

### Endpoint

```
GET /cgi-bin/qsyminfo.py
```

### Usage Statistics
- **Requests:** 3 (4% of all requests)
- **Query Pattern:** Single symbol or `symbol=ALL`

### Request Parameters

| Parameter | Type | Required | Format | Example |
|-----------|------|----------|--------|---------|
| `symbol` | string | No (default: `ALL`) | Symbol code or `ALL` | `BTCUSD.BYBIT` |
| `_` | string | No | jQuery cache buster | `1645123456789` |

**Notes:**
- `symbol=ALL` returns all available symbols
- `_` parameter is a jQuery-style cache buster timestamp (ignored)

### Request Examples

```bash
# Single symbol
GET /cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT

# All symbols
GET /cgi-bin/qsyminfo.py?symbol=ALL

# With cache buster
GET /cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT&_=1645123456789
```

### Response Format

**HTTP Headers:**
```
Content-Type: application/json; charset=UTF-8
```

**Response Body Format:**
```json
[
  {
    "symbol": "string",
    "name": "string",
    "exchange": "string",
    "asset_type": "string",
    "status": "string",
    "first_trade": "ISO8601 datetime or null",
    "last_trade": "ISO8601 datetime or null"
  }
]
```

**Example Response (Single Symbol):**
```json
[
  {
    "symbol": "BTCUSD.BYBIT",
    "name": "Bitcoin USD Perpetual",
    "exchange": "BYBIT",
    "asset_type": "CRYPTO",
    "status": "ACTIVE",
    "first_trade": "2024-01-01T00:00:00",
    "last_trade": "2026-02-20T23:59:59"
  }
]
```

**Example Response (Multiple Symbols):**
```json
[
  {
    "symbol": "BTCUSD.BYBIT",
    "name": "Bitcoin USD Perpetual",
    "exchange": "BYBIT",
    "asset_type": "CRYPTO",
    "status": "ACTIVE",
    "first_trade": "2024-01-01T00:00:00",
    "last_trade": "2026-02-20T23:59:59"
  },
  {
    "symbol": "ETHUSD.BYBIT",
    "name": "Ethereum USD Perpetual",
    "exchange": "BYBIT",
    "asset_type": "CRYPTO",
    "status": "ACTIVE",
    "first_trade": "2024-01-01T00:00:00",
    "last_trade": "2026-02-20T23:59:59"
  }
]
```

**Field Specifications:**
- **symbol** - Symbol code (string)
- **name** - Full symbol name (string)
- **exchange** - Exchange identifier (string)
- **asset_type** - Asset class (string: `CRYPTO`, `STOCK`, etc.)
- **status** - Trading status (string: `ACTIVE`, `INACTIVE`, etc.)
- **first_trade** - First available data timestamp (ISO8601 or null)
- **last_trade** - Last available data timestamp (ISO8601 or null)

---

## Error Handling

All endpoints should return plain text error messages on failure:

**Error Response Format:**
```
Content-Type: text/plain

Error processing request: <error message>
```

**Common Error Cases:**
- Invalid symbol
- Invalid date format
- Date range too large
- No data available
- Database connection error

---

## Compatibility Requirements

### Critical Requirements
✅ **MUST** preserve exact response format
✅ **MUST** use same parameter names (case-sensitive)
✅ **MUST** return same Content-Type headers
✅ **MUST** handle flexible date parsing
✅ **MUST** return data in same order (chronological)

### Optional Enhancements
✨ Can add gzip compression (with `Content-Encoding: gzip` header)
✨ Can add CORS headers for web clients
✨ Can add rate limiting headers
✨ Can optimize query performance

### Breaking Changes to Avoid
❌ **DO NOT** change endpoint paths
❌ **DO NOT** change parameter names
❌ **DO NOT** change response format
❌ **DO NOT** require authentication (unless legacy also required it)
❌ **DO NOT** add required parameters

---

## Testing Checklist

### Functional Tests
- [ ] q1min.py returns correct format
- [ ] q1sec.py returns correct format
- [ ] qsyminfo.py returns correct JSON structure
- [ ] All endpoints accept URL-encoded parameters
- [ ] Flexible date parsing works (e.g., `19:9:0` vs `19:09:00`)
- [ ] Empty result sets handled gracefully
- [ ] Error messages in plain text format

### Data Validation Tests
- [ ] Date fields match format: `YYYYMMDD`
- [ ] Time fields match format: `HHMMSS`
- [ ] Numeric fields parse as floats
- [ ] JSON response validates against schema
- [ ] Timestamps in chronological order

### Performance Tests
- [ ] 1-day query completes in < 100ms (p50)
- [ ] 1-week query completes in < 500ms (p50)
- [ ] Symbol info query completes in < 10ms
- [ ] Handles 100+ concurrent requests

### Compatibility Tests
- [ ] Existing client application works without changes
- [ ] Byte-for-byte match with legacy for same query (where deterministic)
- [ ] HTTP headers match legacy behavior
- [ ] Error responses handled by client

---

## Implementation Notes

### Date Parsing
```python
# Flexible date parsing to handle various formats
def parse_legacy_date(date_str: str) -> datetime:
    """Parse legacy date format with flexible spacing"""
    # Normalize multiple spaces to single space
    normalized = " ".join(date_str.split())
    return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
```

### Response Formatting
```python
# q1min.py / q1sec.py response formatting
def format_ohlcv_legacy(bars: List[OHLCVBar]) -> str:
    """Format OHLCV data in legacy format"""
    lines = []
    for bar in bars:
        dt_str = bar.timestamp.strftime("%Y%m%d,%H%M%S")
        lines.append(f"{dt_str},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    return "\n".join(lines)
```

### Content-Type Headers
```python
# Ensure exact header match
@router.get("/q1min.py")
async def legacy_1min(...):
    output = format_ohlcv_legacy(data)
    return Response(
        content=output,
        media_type="text/plain"  # Not "text/plain; charset=utf-8"
    )
```

---

## Usage Patterns (From Real Logs)

### q1min.py Usage Pattern
```
Most Common Date Ranges:
- 4-5 hours: 35% of requests
- 1 day: 28% of requests
- 2-3 days: 20% of requests
- < 1 hour: 12% of requests
- > 3 days: 5% of requests

Symbols:
- BTCUSD.BYBIT: 100% of requests
```

### q1sec.py Usage Pattern
```
Most Common Date Ranges:
- < 1 minute: 42% of requests
- 1-5 minutes: 38% of requests
- 5-30 minutes: 15% of requests
- > 30 minutes: 5% of requests

Symbols:
- BTCUSD.BYBIT: 85% of requests
- ETHUSD.BYBIT: 15% of requests
```

### qsyminfo.py Usage Pattern
```
Query Types:
- Single symbol: 67% of requests
- ALL symbols: 33% of requests

Symbols:
- BTCUSD.BYBIT: 2 requests
- ALL: 1 request
```

---

## Migration Validation

### Before Cutover
1. Deploy FastAPI alongside legacy CGI
2. Dual-write to both systems (if applicable)
3. Compare responses from both systems
4. Run client application against FastAPI
5. Monitor for errors/differences

### Validation Script
```bash
#!/bin/bash
# Compare legacy vs new API responses

# Test q1min.py
curl "http://legacy/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2001:00:00" > /tmp/legacy.txt
curl "http://fastapi/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2001:00:00" > /tmp/new.txt
diff /tmp/legacy.txt /tmp/new.txt

# Test q1sec.py
# ... similar tests

# Test qsyminfo.py
# ... similar tests
```

### Acceptance Criteria
- ✅ Response format identical
- ✅ Data values match (within tolerance for timing)
- ✅ HTTP headers match
- ✅ Error handling consistent
- ✅ Client application works without modification

---

## Appendix: Complete cURL Examples

### q1min.py - Various Scenarios

```bash
# Standard query
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2001:00:00"

# With flexible date format
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:9:0&END=2026-02-20%2023:0:0"

# CSV download
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2001:00:00&csv=1" -o btcusd.csv

# Multi-day query
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-17%2000:00:00&END=2026-02-20%2000:00:00"
```

### q1sec.py - Various Scenarios

```bash
# Short range (1 minute)
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:48:00&END=2026-02-20%2019:49:00"

# Extended range (1 hour)
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:00:00&END=2026-02-20%2020:00:00"

# Different symbol
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=ETHUSD.BYBIT&BEG=2026-02-20%2019:48:00&END=2026-02-20%2019:49:00"
```

### qsyminfo.py - Various Scenarios

```bash
# Single symbol
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT"

# All symbols
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=ALL"

# With cache buster (ignored but accepted)
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT&_=1708473600000"

# Default (no parameters)
curl "http://localhost:8000/cgi-bin/qsyminfo.py"
```

---

**Document Version:** 1.0  
**Last Updated:** February 20, 2026  
**Status:** Reference Specification  
**Next Review:** Post-implementation validation

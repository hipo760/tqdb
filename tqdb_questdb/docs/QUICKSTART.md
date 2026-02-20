# TQDB QuestDB + FastAPI - Quick Start Guide

This guide helps you get started with the new QuestDB + FastAPI implementation.

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

## Quick Start (5 minutes)

### 1. Start the Services

```bash
cd /home/ubuntu/services/tqdb/tqdb_questdb/web
docker-compose up -d
```

### 2. Verify Services are Running

```bash
# Check container status
docker-compose ps

# Check QuestDB web console
curl http://localhost:9000

# Check FastAPI health
curl http://localhost:8000/health
```

### 3. Test Legacy Endpoints

```bash
# Test 1-minute endpoint (legacy format)
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2001:00:00"

# Test 1-second endpoint (legacy format)
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:48:00&END=2026-02-20%2019:49:00"

# Test symbol info endpoint
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT"
```

### 4. Explore Modern API

```bash
# Browse interactive API docs
open http://localhost:8000/docs

# Or access ReDoc
open http://localhost:8000/redoc
```

## Legacy Endpoint Usage Patterns

Based on actual usage analysis, here are the real-world query patterns:

### Pattern 1: Intraday 1-Minute Queries (57 requests)

```bash
# Query 1-3 days of 1-minute data
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-17%2019:09:00&END=2026-02-18%2000:00:00"

curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2000:00:00&END=2026-02-20%2019:30:00"

curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2016:00:00&END=2026-02-20%2019:30:00"
```

### Pattern 2: Short-Duration 1-Second Queries (26 requests)

```bash
# Query few seconds to few minutes of tick data
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:48:00&END=2026-02-20%2019:48:57"

curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=ETHUSD.BYBIT&BEG=2026-02-20%2019:47:06&END=2026-02-20%2019:49:11"
```

### Pattern 3: Symbol Info Queries (3 requests)

```bash
# Get symbol information
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=ALL"
```

## Modern API Examples

### RESTful Endpoints (v2)

```bash
# Get 1-minute OHLCV data
curl "http://localhost:8000/api/v2/ohlcv/minute?symbol=BTCUSD.BYBIT&start=2026-02-20T00:00:00Z&end=2026-02-20T01:00:00Z"

# Get 1-second tick data
curl "http://localhost:8000/api/v2/ticks/second?symbol=BTCUSD.BYBIT&start=2026-02-20T19:48:00Z&end=2026-02-20T19:49:00Z"

# Get symbol info (RESTful style)
curl "http://localhost:8000/api/v2/symbols/BTCUSD.BYBIT"

# List all symbols
curl "http://localhost:8000/api/v2/symbols"
```

## QuestDB Console

Access the QuestDB web console at: http://localhost:9000

### Sample Queries

```sql
-- View recent 1-minute data
SELECT * FROM ohlcv_1min 
WHERE symbol = 'BTCUSD.BYBIT' 
ORDER BY timestamp DESC 
LIMIT 100;

-- Check data availability
SELECT 
    symbol,
    min(timestamp) as first_record,
    max(timestamp) as last_record,
    count(*) as total_records
FROM ohlcv_1min
GROUP BY symbol;

-- Get 1-minute bars for specific time range
SELECT 
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM ohlcv_1min
WHERE symbol = 'BTCUSD.BYBIT'
  AND timestamp >= '2026-02-20T00:00:00.000000Z'
  AND timestamp < '2026-02-20T01:00:00.000000Z'
ORDER BY timestamp;
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose logs -f

# Restart services
docker-compose restart

# Rebuild if needed
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### QuestDB Connection Issues

```bash
# Test QuestDB directly
curl http://localhost:9000

# Check QuestDB logs
docker-compose logs questdb

# Restart QuestDB
docker-compose restart questdb
```

### Legacy Endpoint Not Working

```bash
# Check FastAPI logs
docker-compose logs fastapi

# Test health endpoint
curl http://localhost:8000/health

# Verify parameter format
# Legacy format uses: BEG and END (uppercase)
# Date format: YYYY-MM-DD HH:MM:SS (space separated)
```

## Development Setup

### Local Development (without Docker)

```bash
# Install dependencies
cd /home/ubuntu/services/tqdb/tqdb_questdb/web
pip install -r requirements.txt

# Set environment variables
export QUESTDB_HOST=localhost
export QUESTDB_PORT=8812
export LOG_LEVEL=debug

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_legacy.py -v
```

## Configuration

### Environment Variables

```bash
# QuestDB connection
QUESTDB_HOST=questdb
QUESTDB_PORT=8812
QUESTDB_USER=admin
QUESTDB_PASSWORD=quest

# Application settings
LOG_LEVEL=info
MAX_QUERY_LIMIT=50000
ENABLE_LEGACY_ENDPOINTS=true

# CORS settings
CORS_ORIGINS=*
```

### Performance Tuning

```bash
# Increase worker processes
docker-compose up -d --scale fastapi=4

# Adjust QuestDB memory
# Edit docker-compose.yml:
# QDB_CAIRO_SQL_CACHE_BLOCKS=256
# QDB_CAIRO_SQL_CACHE_ROWS=1024
```

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# QuestDB health
curl http://localhost:9000/

# Check metrics (if Prometheus enabled)
curl http://localhost:8000/metrics
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f fastapi
docker-compose logs -f questdb

# View last 100 lines
docker-compose logs --tail=100 fastapi
```

## Migration Checklist

When migrating from legacy system:

- [ ] Deploy QuestDB + FastAPI containers
- [ ] Verify all 3 legacy endpoints work
- [ ] Test with actual client application
- [ ] Migrate historical data from Cassandra
- [ ] Validate data integrity
- [ ] Update DNS/load balancer to point to new system
- [ ] Monitor for errors/performance issues
- [ ] Keep old system running for 2 weeks (rollback safety)
- [ ] Decommission old Cassandra system

## Next Steps

1. Review the full [Migration Plan](./MIGRATION_PLAN.md)
2. Explore the [API Reference](./API_REFERENCE.md)
3. Check [Legacy Compatibility Guide](./LEGACY_COMPATIBILITY.md)
4. Set up monitoring and alerting
5. Plan data migration from Cassandra

## Support

- Documentation: `/tqdb_questdb/docs/`
- FastAPI Docs: http://localhost:8000/docs
- QuestDB Console: http://localhost:9000
- Issues: Create issue in repository

---

**Last Updated:** February 20, 2026

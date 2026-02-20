# QuestDB Deployment

This directory contains Docker Compose configuration for deploying QuestDB for the TQDB project.

## Quick Start

### 1. Start QuestDB

```bash
cd /home/ubuntu/services/tqdb/tqdb_questdb/questdb
docker-compose up -d
```

### 2. Verify Service

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Check health
curl http://localhost:9000/
```

### 3. Access QuestDB

- **Web Console**: http://localhost:9000
- **Postgres Wire Protocol**: `localhost:8812`
- **InfluxDB Line Protocol**: `localhost:9009` (for ingestion)
- **Health Check**: http://localhost:9003

## Configuration

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 9000 | HTTP | Web Console + REST API |
| 9009 | ILP | InfluxDB Line Protocol (ingestion) |
| 8812 | Postgres | SQL queries |
| 9003 | HTTP | Health monitoring |

### Environment Variables

The docker-compose.yml includes optimizations for 5-second update cycle:

```yaml
QDB_CAIRO_MAX_UNCOMMITTED_ROWS=100000  # Buffer for high-frequency updates
QDB_CAIRO_O3_MAX_LAG=60000000          # 60 seconds out-of-order support
QDB_CAIRO_COMMIT_LAG=10000000          # 10 seconds commit lag
```

### Data Persistence

Data is stored in a Docker named volume: `questdb-data`

```bash
# Inspect volume
docker volume inspect tqdb_questdb-data

# Backup volume
docker run --rm -v tqdb_questdb-data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/questdb-backup-$(date +%Y%m%d).tar.gz /data
```

## Schema Initialization

### 1. Access QuestDB Console

Open http://localhost:9000 in your browser

### 2. Create Tables

```sql
-- 1-second OHLCV bars (equivalent to Cassandra secbar)
CREATE TABLE ohlcv_1sec (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG
) timestamp(timestamp) PARTITION BY DAY
  WITH maxUncommittedRows = 100000, o3MaxLag = 60s;

ALTER TABLE ohlcv_1sec DEDUP ENABLE UPSERT KEYS(timestamp, symbol);

-- 1-minute OHLCV bars (equivalent to Cassandra minbar)
CREATE TABLE ohlcv_1min (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG
) timestamp(timestamp) PARTITION BY DAY
  WITH maxUncommittedRows = 100000, o3MaxLag = 60s;

ALTER TABLE ohlcv_1min DEDUP ENABLE UPSERT KEYS(timestamp, symbol);

-- Symbol metadata
CREATE TABLE symbols (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    name STRING,
    exchange STRING,
    asset_type STRING,
    status STRING,
    first_trade TIMESTAMP,
    last_trade TIMESTAMP,
    updated_at TIMESTAMP
) timestamp(updated_at);
```

### 3. Verify Tables

```sql
-- List all tables
SHOW TABLES;

-- Check table structure
SHOW COLUMNS FROM ohlcv_1sec;
SHOW COLUMNS FROM ohlcv_1min;
SHOW COLUMNS FROM symbols;
```

## Testing

### Test Ingestion (InfluxDB Line Protocol)

```bash
# Install QuestDB Python client
pip install questdb

# Test script
python3 << 'EOF'
from questdb.ingress import Sender
from datetime import datetime

# Connect to QuestDB
with Sender('localhost', 9009) as sender:
    # Insert test data
    sender.row(
        'ohlcv_1min',
        symbols={'symbol': 'BTCUSD.BYBIT'},
        columns={
            'open': 68000.0,
            'high': 68100.0,
            'low': 67900.0,
            'close': 68050.0,
            'volume': 1000
        },
        at=datetime.now()
    )
    sender.flush()
    print("Test data inserted successfully!")
EOF
```

### Test Queries (Postgres Wire Protocol)

```bash
# Using psql client
psql -h localhost -p 8812 -U admin -d qdb

# Or using Python
python3 << 'EOF'
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=8812,
    user='admin',
    password='quest',
    database='qdb'
)

cursor = conn.cursor()
cursor.execute("SELECT * FROM ohlcv_1min LIMIT 10")
for row in cursor.fetchall():
    print(row)

conn.close()
EOF
```

## Monitoring

### Check Data Freshness

```sql
SELECT 
    symbol,
    max(timestamp) as last_update,
    count(*) as record_count
FROM ohlcv_1min
GROUP BY symbol
ORDER BY last_update DESC;
```

### Check Table Sizes

```sql
SELECT 
    table_name,
    count() as row_count
FROM tables()
WHERE table_name IN ('ohlcv_1sec', 'ohlcv_1min', 'symbols');
```

### Monitor Performance

```sql
-- Check latest queries
SELECT * FROM telemetry_config;

-- View metrics (if enabled)
curl http://localhost:9003/metrics
```

## Maintenance

### Start/Stop

```bash
# Stop QuestDB
docker-compose stop

# Start QuestDB
docker-compose start

# Restart QuestDB
docker-compose restart

# Stop and remove containers
docker-compose down
```

### Logs

```bash
# View logs
docker-compose logs

# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100
```

### Upgrade QuestDB

```bash
# Stop current instance
docker-compose stop

# Pull new version
docker pull questdb/questdb:9.3.2

# Update docker-compose.yml with new version (if needed)

# Start with new version
docker-compose up -d

# Check logs for upgrade process
docker-compose logs -f
```

### Backup

```bash
# Backup using QuestDB snapshot
curl -G "http://localhost:9000/exec" --data-urlencode "query=BACKUP TABLE ohlcv_1min"

# Or backup the entire volume
docker run --rm \
  -v tqdb_questdb-data:/data \
  -v $(pwd)/backups:/backup \
  ubuntu tar czf /backup/questdb-$(date +%Y%m%d-%H%M%S).tar.gz /data
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Check if ports are already in use
sudo netstat -tlnp | grep -E '(9000|9009|8812|9003)'

# Check volume permissions
docker volume inspect tqdb_questdb-data
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase memory/CPU limits in docker-compose.yml
# See deploy.resources section
```

### Connection Issues

```bash
# Test HTTP endpoint
curl http://localhost:9000/

# Test Postgres wire protocol
psql -h localhost -p 8812 -U admin -d qdb -c "SELECT 1"

# Test InfluxDB line protocol
echo "test_table,symbol=TEST field=1.0" | nc localhost 9009
```

## Configuration Files

### Custom Server Configuration

Create `conf/server.conf`:

```properties
# HTTP configuration
http.bind.to=0.0.0.0:9000
http.net.connection.limit=256

# Postgres wire protocol
pg.enabled=true
pg.net.bind.to=0.0.0.0:8812

# InfluxDB line protocol
line.tcp.enabled=true
line.tcp.net.bind.to=0.0.0.0:9009

# Performance tuning
cairo.max.uncommitted.rows=100000
cairo.o3.max.lag=60000000
cairo.commit.lag=10000000
```

Then mount it in docker-compose.yml:

```yaml
volumes:
  - questdb-data:/var/lib/questdb
  - ./conf:/var/lib/questdb/conf
```

## Resources

- **QuestDB Documentation**: https://questdb.com/docs/
- **Docker Deployment Guide**: https://questdb.com/docs/deployment/docker/
- **Release Notes**: https://questdb.com/release-notes/
- **Community Slack**: https://slack.questdb.com/
- **GitHub**: https://github.com/questdb/questdb

## Next Steps

1. Initialize schema (see Schema Initialization section)
2. Test ingestion and queries
3. Set up data ingestion service (see `../docs/MIGRATION_PLAN.md`)
4. Deploy FastAPI application (see `../web/`)
5. Migrate historical data from Cassandra

---

**Version:** QuestDB 9.3.2  
**Last Updated:** February 20, 2026  
**Status:** Ready for deployment

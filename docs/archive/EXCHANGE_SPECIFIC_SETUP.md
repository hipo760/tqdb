# Exchange-Specific Node Setup Quick Guide

## Overview

This guide shows how to set up a TQDB cluster where:
- **Master Node** stores ALL exchange data (NYSE + NASDAQ + HKEX + ...)
- **Exchange Nodes** store only their specific exchange data (NYSE node only has NYSE, etc.)
- Applications can query any node and get the data they need

## Quick Reference

### Cluster Layout

| Node | IP | Rack | Data Stored | Purpose |
|------|-----|------|-------------|---------|
| Master | 192.168.1.10 | rack_master | ALL exchanges | Analytics, backup, complete dataset |
| NYSE | 192.168.1.11 | rack_nyse | NYSE only | NYSE data ingestion |
| NASDAQ | 192.168.1.12 | rack_nasdaq | NASDAQ only | NASDAQ data ingestion |
| HKEX | 192.168.1.13 | rack_hkex | HKEX only | HKEX data ingestion |

### Keyspace Layout

```
tqdb_nyse   → Replicated to Master + NYSE node    (RF=2)
tqdb_nasdaq → Replicated to Master + NASDAQ node  (RF=2)
tqdb_hkex   → Replicated to Master + HKEX node    (RF=2)
```

## Step-by-Step Setup

### Step 1: Configure Each Node's Rack

**Master Node (192.168.1.10):**
```bash
# .env or docker-compose.cluster.yml
export HOST_IP=192.168.1.10
export CASSANDRA_RACK=rack_master
export CASSANDRA_DC=dc1
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra
```

**NYSE Node (192.168.1.11):**
```bash
export HOST_IP=192.168.1.11
export CASSANDRA_RACK=rack_nyse
export CASSANDRA_DC=dc1
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra
```

**NASDAQ Node (192.168.1.12):**
```bash
export HOST_IP=192.168.1.12
export CASSANDRA_RACK=rack_nasdaq
export CASSANDRA_DC=dc1
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra
```

**HKEX Node (192.168.1.13):**
```bash
export HOST_IP=192.168.1.13
export CASSANDRA_RACK=rack_hkex
export CASSANDRA_DC=dc1
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra
```

### Step 2: Verify Cluster Formation

```bash
# On any node
docker exec tqdb-cassandra-master nodetool status

# Should show:
# UN 192.168.1.10  rack_master
# UN 192.168.1.11  rack_nyse
# UN 192.168.1.12  rack_nasdaq
# UN 192.168.1.13  rack_hkex
```

### Step 3: Create Exchange-Specific Keyspaces

```bash
# Create script: scripts/create-exchange-keyspaces.sh

#!/bin/bash
set -e

# NYSE Keyspace
docker exec tqdb-cassandra-master cqlsh <<EOF
CREATE KEYSPACE IF NOT EXISTS tqdb_nyse 
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
} AND durable_writes = true;

USE tqdb_nyse;

CREATE TABLE IF NOT EXISTS minbar (
  symbol text,
  epoch_float double,
  open float,
  high float,
  low float,
  close float,
  volume bigint,
  PRIMARY KEY (symbol, epoch_float)
) WITH CLUSTERING ORDER BY (epoch_float DESC);

CREATE TABLE IF NOT EXISTS secbar (
  symbol text,
  epoch_float double,
  open float,
  high float,
  low float,
  close float,
  volume bigint,
  PRIMARY KEY (symbol, epoch_float)
) WITH CLUSTERING ORDER BY (epoch_float DESC);

CREATE TABLE IF NOT EXISTS tick (
  symbol text,
  epoch_float double,
  price float,
  volume bigint,
  PRIMARY KEY (symbol, epoch_float)
) WITH CLUSTERING ORDER BY (epoch_float DESC);

CREATE TABLE IF NOT EXISTS day (
  symbol text,
  epoch_date text,
  open float,
  high float,
  low float,
  close float,
  volume bigint,
  PRIMARY KEY (symbol, epoch_date)
) WITH CLUSTERING ORDER BY (epoch_date DESC);

CREATE TABLE IF NOT EXISTS symbol (
  symbol text PRIMARY KEY,
  exchange text,
  name text,
  timezone text,
  config text
);

CREATE TABLE IF NOT EXISTS conf (
  confkey text PRIMARY KEY,
  confval text
);
EOF

# NASDAQ Keyspace (same structure)
docker exec tqdb-cassandra-master cqlsh <<EOF
CREATE KEYSPACE IF NOT EXISTS tqdb_nasdaq
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
};

-- Copy all table definitions from above
USE tqdb_nasdaq;
-- CREATE TABLE minbar ... (same as above)
-- CREATE TABLE secbar ... (same as above)
-- etc.
EOF

# HKEX Keyspace (same structure)
docker exec tqdb-cassandra-master cqlsh <<EOF
CREATE KEYSPACE IF NOT EXISTS tqdb_hkex
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
};

-- Copy all table definitions from above
USE tqdb_hkex;
-- CREATE TABLE minbar ... (same as above)
-- etc.
EOF

echo "Exchange keyspaces created!"
```

Run the script:
```bash
chmod +x scripts/create-exchange-keyspaces.sh
./scripts/create-exchange-keyspaces.sh
```

### Step 4: Verify Data Placement Strategy

```bash
# Check replication strategy
docker exec tqdb-cassandra-master cqlsh -e "DESCRIBE KEYSPACE tqdb_nyse;"
docker exec tqdb-cassandra-master cqlsh -e "DESCRIBE KEYSPACE tqdb_nasdaq;"
docker exec tqdb-cassandra-master cqlsh -e "DESCRIBE KEYSPACE tqdb_hkex;"

# Check which nodes will store which keyspaces
docker exec tqdb-cassandra-master nodetool getendpoints tqdb_nyse minbar 'AAPL'
# Should show: 192.168.1.10 (master) and 192.168.1.11 (NYSE)

docker exec tqdb-cassandra-master nodetool getendpoints tqdb_nasdaq minbar 'AAPL'
# Should show: 192.168.1.10 (master) and 192.168.1.12 (NASDAQ)
```

### Step 5: Configure Application to Use Exchange Keyspaces

**Environment Variables for Web UI:**
```bash
# In docker-compose.yml or .env
CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12,192.168.1.13
CASSANDRA_LOCAL_DC=dc1
CASSANDRA_PORT=9042
# Default keyspace for backward compatibility
CASSANDRA_KEYSPACE=tqdb_nyse

# Exchange mapping (JSON string)
EXCHANGE_KEYSPACES='{"NYSE":"tqdb_nyse","NASDAQ":"tqdb_nasdaq","HKEX":"tqdb_hkex"}'
```

**Application Code (Node.js/SvelteKit):**
```javascript
// web-ui/src/lib/api/cassandra.js
import cassandra from 'cassandra-driver';

const EXCHANGE_KEYSPACES = JSON.parse(
  process.env.EXCHANGE_KEYSPACES || '{}'
);

const client = new cassandra.Client({
  contactPoints: process.env.CASSANDRA_CONTACT_POINTS.split(','),
  localDataCenter: process.env.CASSANDRA_LOCAL_DC,
  keyspace: process.env.CASSANDRA_KEYSPACE
});

function getKeyspace(exchange) {
  return EXCHANGE_KEYSPACES[exchange] || 'tqdb_nyse';
}

export async function queryMinBar(symbol, exchange, startTime, endTime) {
  const keyspace = getKeyspace(exchange);
  const query = `SELECT * FROM ${keyspace}.minbar 
                 WHERE symbol = ? AND epoch_float >= ? AND epoch_float <= ?
                 ORDER BY epoch_float DESC`;
  
  const result = await client.execute(query, 
    [symbol, startTime, endTime], 
    { prepare: true }
  );
  
  return result.rows;
}

export async function insertMinBar(symbol, exchange, data) {
  const keyspace = getKeyspace(exchange);
  const query = `INSERT INTO ${keyspace}.minbar 
                 (symbol, epoch_float, open, high, low, close, volume)
                 VALUES (?, ?, ?, ?, ?, ?, ?)`;
  
  await client.execute(query,
    [symbol, data.epoch_float, data.open, data.high, data.low, data.close, data.volume],
    { prepare: true }
  );
}
```

**Python Import Script:**
```python
# tools/Min2Cass_Exchange.py
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy
import sys

EXCHANGE_KEYSPACES = {
    'NYSE': 'tqdb_nyse',
    'NASDAQ': 'tqdb_nasdaq',
    'HKEX': 'tqdb_hkex'
}

def import_csv(csv_file, exchange):
    keyspace = EXCHANGE_KEYSPACES.get(exchange)
    if not keyspace:
        print(f"Unknown exchange: {exchange}")
        return
    
    # Connect to cluster
    cluster = Cluster(
        contact_points=['192.168.1.10', '192.168.1.11', '192.168.1.12', '192.168.1.13'],
        load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='dc1')
    )
    session = cluster.connect(keyspace)
    
    # Prepare statement
    insert_stmt = session.prepare(
        f"INSERT INTO {keyspace}.minbar (symbol, epoch_float, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    
    # Import data
    with open(csv_file, 'r') as f:
        for line in f:
            # Parse CSV line
            symbol, epoch_float, open, high, low, close, volume = parse_line(line)
            
            # Insert - Cassandra will route to master + exchange node
            session.execute(insert_stmt, 
                (symbol, epoch_float, open, high, low, close, volume))
    
    print(f"Imported {csv_file} to {keyspace}")
    cluster.shutdown()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python Min2Cass_Exchange.py <csv_file> <exchange>")
        print("Example: python Min2Cass_Exchange.py nyse_data.csv NYSE")
        sys.exit(1)
    
    import_csv(sys.argv[1], sys.argv[2])
```

### Step 6: Import Data to Specific Exchanges

```bash
# Import NYSE data (goes to Master + NYSE node)
docker exec tqdb-tools python3 /opt/tqdb/tools/Min2Cass_Exchange.py \
  /data/nyse_20260217.csv NYSE

# Import NASDAQ data (goes to Master + NASDAQ node)
docker exec tqdb-tools python3 /opt/tqdb/tools/Min2Cass_Exchange.py \
  /data/nasdaq_20260217.csv NASDAQ

# Import HKEX data (goes to Master + HKEX node)
docker exec tqdb-tools python3 /opt/tqdb/tools/Min2Cass_Exchange.py \
  /data/hkex_20260217.csv HKEX
```

## Verification

### Check Data Distribution

```bash
# Master node should have all data
docker exec tqdb-cassandra-master cqlsh -e "
SELECT COUNT(*) FROM tqdb_nyse.minbar;
SELECT COUNT(*) FROM tqdb_nasdaq.minbar;
SELECT COUNT(*) FROM tqdb_hkex.minbar;
"

# NYSE node should only have NYSE
docker exec tqdb-cassandra-nyse cqlsh -e "
SELECT COUNT(*) FROM tqdb_nyse.minbar;   -- Should have data
SELECT COUNT(*) FROM tqdb_nasdaq.minbar; -- Should be empty or error
"

# Check storage space per node
docker exec tqdb-cassandra-master nodetool tablestats | grep "Space used"
docker exec tqdb-cassandra-nyse nodetool tablestats | grep "Space used"
```

### Query from Any Node

```bash
# Query NYSE data from NASDAQ node (driver will route to correct node)
docker exec tqdb-web-ui curl -s "http://localhost:3000/api/cgi-bin/q1min.py?symbol=AAPL&exchange=NYSE&BEG=2026-02-01&END=2026-02-17"

# Query NASDAQ data from HKEX node
docker exec tqdb-web-ui curl -s "http://localhost:3000/api/cgi-bin/q1min.py?symbol=GOOGL&exchange=NASDAQ&BEG=2026-02-01&END=2026-02-17"
```

## Maintenance

### Add New Exchange

1. **Add new node:**
```bash
# On new machine (192.168.1.14)
export HOST_IP=192.168.1.14
export CASSANDRA_RACK=rack_lse  # London Stock Exchange
export CASSANDRA_DC=dc1
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra
```

2. **Create keyspace:**
```bash
docker exec tqdb-cassandra-master cqlsh -e "
CREATE KEYSPACE tqdb_lse
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
};
-- Create tables...
"
```

3. **Update application config:**
```bash
# Add to EXCHANGE_KEYSPACES environment variable
EXCHANGE_KEYSPACES='{"NYSE":"tqdb_nyse","NASDAQ":"tqdb_nasdaq","HKEX":"tqdb_hkex","LSE":"tqdb_lse"}'
```

### Backfill Operations

When quote services go down and recover, you need to backfill missing data. See **[BACKFILL_STRATEGY.md](BACKFILL_STRATEGY.md)** for detailed guidance.

**Quick Reference:**

```bash
# Recommended: Backfill on the exchange-specific node
# Example: NYSE quote service was down 10:00-11:30

# SSH to NYSE node
ssh user@192.168.1.11

# Run backfill
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --source /data/nyse_backfill.csv
```

**Why backfill on exchange-specific node?**
- ✅ Efficient: Data written locally + 1 network hop to master
- ✅ Logical: Backfill happens where data belongs
- ✅ Isolated: Doesn't impact other exchanges or master's workload

**Alternative: Backfill on Master Node**
- Use when you want centralized backfill management
- All backfills run from one location
- Slightly more network traffic but often negligible

See [BACKFILL_STRATEGY.md](BACKFILL_STRATEGY.md) for:
- Complete backfill script with examples
- Gap detection automation
- Verification procedures
- Best practices

### Monitor Storage on Master Node

```bash
# Check disk usage
docker exec tqdb-cassandra-master df -h /var/lib/cassandra

# Check per-keyspace size
docker exec tqdb-cassandra-master nodetool cfstats tqdb_nyse
docker exec tqdb-cassandra-master nodetool cfstats tqdb_nasdaq
docker exec tqdb-cassandra-master nodetool cfstats tqdb_hkex
```

### Rebalance if Master Gets Too Full

If master node storage becomes a concern, you can:

1. **Option 1**: Change RF to store data on 2 exchange nodes instead (master + 2 exchange nodes)
2. **Option 2**: Use compression on master's data
3. **Option 3**: Implement time-based TTL to auto-expire old data on master

## Troubleshooting

### Data Not on Expected Node

```bash
# Check which nodes have data for a specific symbol
docker exec tqdb-cassandra-master nodetool getendpoints tqdb_nyse minbar 'AAPL'

# Should return 2 IPs: master + exchange node
```

### Query Performance Issues

```bash
# Check which node the query hit
# Enable query tracing in application

# Or check which nodes are being queried
docker exec tqdb-cassandra-master nodetool proxyhistograms
```

### Master Node Storage Full

```bash
# Check space
docker exec tqdb-cassandra-master nodetool status

# Run cleanup (removes data that doesn't belong on this node)
docker exec tqdb-cassandra-master nodetool cleanup

# Run compaction to reduce space
docker exec tqdb-cassandra-master nodetool compact
```

## Summary

This setup provides:
- ✅ **Efficient storage**: Exchange nodes only store their data
- ✅ **Complete dataset on master**: For analytics and backup
- ✅ **Query from anywhere**: Applications can query any node
- ✅ **Easy to extend**: Add new exchanges by adding nodes + keyspaces
- ✅ **Automatic routing**: Cassandra driver routes queries to correct nodes

**Key Trade-offs:**
- Master node needs more storage (has all data)
- More keyspaces to manage
- Application needs exchange-to-keyspace mapping
- Worth it if you have many exchanges with large datasets

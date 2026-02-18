# TQDB Backfill Strategy for Exchange-Specific Clusters

## Overview

When a quote service for a specific exchange goes down and recovers, you need to backfill the missing data. This document explains where and how to perform backfills in an exchange-specific cluster setup.

## Quick Answer

**Backfill on ANY node** - Cassandra will automatically replicate to the correct nodes based on the keyspace configuration.

However, there are **optimal choices** depending on your goals:
- **Best for network efficiency**: Backfill on the exchange-specific node
- **Best for load distribution**: Backfill on the master node
- **Best for isolation**: Backfill on a dedicated backfill node

## Scenario: NYSE Quote Service Down

### Timeline
```
10:00 AM - NYSE quote service goes down
10:00 AM - 11:30 AM - No data received (90 minutes missing)
11:30 AM - NYSE quote service recovers
11:31 AM - Need to backfill 90 minutes of missing NYSE data
```

### Data Flow During Backfill

Regardless of which node you use for backfill, Cassandra ensures data reaches the correct replicas:

```
Backfill Script
    │
    ▼
INSERT INTO tqdb_nyse.minbar (...)
    │
    ▼
Cassandra determines replicas
(Master + NYSE node)
    │
    ├───────────────┬───────────────┐
    ▼               ▼               ▼
Master Node    NYSE Node      (No other nodes)
✓ Written      ✓ Written
```

## Backfill Options Compared

### Option 1: Backfill on Exchange-Specific Node (RECOMMENDED)

**Example: Backfill NYSE data on NYSE Node (192.168.1.11)**

```bash
# SSH to NYSE node
ssh user@192.168.1.11

# Run backfill script
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00"
```

**Pros:**
- ✅ **Efficient**: Data written locally, only 1 network hop to master
- ✅ **Organized**: Backfill happens where the data "belongs"
- ✅ **Lower latency**: Local write + 1 remote write = fast
- ✅ **Resource isolation**: Master node not impacted by backfill load

**Cons:**
- ❌ Must SSH to specific node (or have remote execution)
- ❌ Node might be busy with real-time ingestion

**Network Traffic:**
```
NYSE Node (backfill origin)
    │
    ├─ Local write: 0ms latency ✓
    │
    └─ Network write to Master: ~1-5ms ✓
    
Total: 1-5ms per write
```

### Option 2: Backfill on Master Node

**Example: Backfill NYSE data on Master Node (192.168.1.10)**

```bash
# SSH to master node
ssh user@192.168.1.10

# Run backfill script
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00"
```

**Pros:**
- ✅ **Centralized**: One place to run all backfills
- ✅ **Consistent**: Same node for all operational tasks
- ✅ **Monitoring**: Easier to track backfill jobs
- ✅ **Data verification**: Can query immediately on same node

**Cons:**
- ❌ **Higher network load**: Master writes locally + sends to NYSE node
- ❌ **Master node load**: CPU/memory for backfill + storage
- ❌ **Not optimal for large backfills**: Double network traffic

**Network Traffic:**
```
Master Node (backfill origin)
    │
    ├─ Local write: 0ms latency ✓
    │
    └─ Network write to NYSE Node: ~1-5ms
    
Total: 1-5ms per write (same as Option 1)
```

**Actually the same performance!** Cassandra replicates to RF=2 nodes regardless.

### Option 3: Backfill on Different Exchange Node

**Example: Backfill NYSE data on NASDAQ Node (192.168.1.12)**

```bash
# SSH to NASDAQ node
ssh user@192.168.1.12

# Run backfill script
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00"
```

**Pros:**
- ✅ **Load distribution**: Spreads backfill load across cluster
- ✅ **Flexibility**: Any available node can handle backfills

**Cons:**
- ❌ **Sub-optimal**: NASDAQ node doesn't store NYSE data
- ❌ **Network overhead**: 2 remote writes (Master + NYSE)
- ❌ **Confusing**: NYSE data backfilled from NASDAQ node

**Network Traffic:**
```
NASDAQ Node (backfill origin)
    │
    ├─ Network write to Master: ~1-5ms
    │
    └─ Network write to NYSE Node: ~1-5ms
    
Total: Higher latency, both writes remote
```

### Option 4: Dedicated Backfill Node (ENTERPRISE)

**Add a dedicated node just for backfill operations**

```
Cluster Layout:
- Master Node (192.168.1.10) - All data
- NYSE Node (192.168.1.11) - NYSE data + real-time ingestion
- NASDAQ Node (192.168.1.12) - NASDAQ data + real-time ingestion
- HKEX Node (192.168.1.13) - HKEX data + real-time ingestion
- Backfill Node (192.168.1.20) - No data storage, backfill only
```

Configuration:
```bash
# Backfill Node - not part of cluster, just client
# Only runs tools container, no Cassandra
# docker-compose.backfill.yml

services:
  backfill-tools:
    build:
      context: .
      dockerfile: ./docker/tools/Dockerfile
    container_name: tqdb-backfill-tools
    environment:
      - CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
      - CASSANDRA_LOCAL_DC=dc1
    volumes:
      - backfill_data:/data
      - ./logs/backfill:/var/log/tqdb
```

**Pros:**
- ✅ **Complete isolation**: Backfills don't impact production nodes
- ✅ **Dedicated resources**: Can be powerful machine for fast backfills
- ✅ **Centralized**: All backfill jobs run here
- ✅ **Scalable**: Can add more backfill nodes if needed

**Cons:**
- ❌ **Extra infrastructure**: Additional machine to maintain
- ❌ **Cost**: Another node to pay for
- ❌ **Overkill**: Unless backfills are frequent and large

## Recommended Strategy

### For Most Use Cases: Exchange-Specific Node

**Run backfills on the node responsible for that exchange's data.**

```bash
# NYSE backfill → NYSE node
ssh user@192.168.1.11
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py NYSE ...

# NASDAQ backfill → NASDAQ node  
ssh user@192.168.1.12
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py NASDAQ ...

# HKEX backfill → HKEX node
ssh user@192.168.1.13
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py HKEX ...
```

**Why?**
- ✅ Logical: Data backfilled where it belongs
- ✅ Efficient: Minimal network traffic
- ✅ Isolated: Each exchange's backfill impacts only its node

### For Centralized Operations: Master Node

**Run all backfills from master node for operational simplicity.**

```bash
# All backfills from master
ssh user@192.168.1.10

docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py NYSE ...
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py NASDAQ ...
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill.py HKEX ...
```

**Why?**
- ✅ Simple: One node for all operations
- ✅ Consistent: Same execution environment
- ✅ Monitoring: Centralized logging and metrics

### For High-Volume Operations: Dedicated Backfill Node

**If backfills are frequent or very large, use a dedicated node.**

## Backfill Script Design

### Exchange-Aware Backfill Script

```python
#!/usr/bin/env python3
# tools/backfill_exchange.py

import sys
import argparse
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy

EXCHANGE_KEYSPACES = {
    'NYSE': 'tqdb_nyse',
    'NASDAQ': 'tqdb_nasdaq',
    'HKEX': 'tqdb_hkex'
}

def backfill(exchange, start_time, end_time, data_source):
    """
    Backfill missing data for a specific exchange.
    
    Args:
        exchange: Exchange code (NYSE, NASDAQ, HKEX)
        start_time: Start of missing data period
        end_time: End of missing data period
        data_source: URL or file path to fetch historical data
    """
    # Determine keyspace
    keyspace = EXCHANGE_KEYSPACES.get(exchange)
    if not keyspace:
        print(f"ERROR: Unknown exchange {exchange}")
        return 1
    
    print(f"Backfilling {exchange} data to keyspace {keyspace}")
    print(f"Period: {start_time} to {end_time}")
    
    # Connect to cluster
    # Note: Contact points should include multiple nodes for redundancy
    cluster = Cluster(
        contact_points=['192.168.1.10', '192.168.1.11', '192.168.1.12'],
        load_balancing_policy=TokenAwarePolicy(
            DCAwareRoundRobinPolicy(local_dc='dc1')
        )
    )
    session = cluster.connect(keyspace)
    
    # Prepare insert statements
    insert_minbar = session.prepare(f"""
        INSERT INTO {keyspace}.minbar 
        (symbol, epoch_float, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """)
    
    insert_secbar = session.prepare(f"""
        INSERT INTO {keyspace}.secbar
        (symbol, epoch_float, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """)
    
    insert_tick = session.prepare(f"""
        INSERT INTO {keyspace}.tick
        (symbol, epoch_float, price, volume)
        VALUES (?, ?, ?, ?)
    """)
    
    # Fetch historical data from source
    print(f"Fetching data from {data_source}...")
    data = fetch_historical_data(data_source, exchange, start_time, end_time)
    
    # Insert data
    print(f"Inserting {len(data)} records...")
    batch_size = 100
    count = 0
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        
        for record in batch:
            if record['type'] == 'minbar':
                session.execute(insert_minbar, (
                    record['symbol'], record['epoch_float'],
                    record['open'], record['high'], record['low'],
                    record['close'], record['volume']
                ))
            elif record['type'] == 'secbar':
                session.execute(insert_secbar, (
                    record['symbol'], record['epoch_float'],
                    record['open'], record['high'], record['low'],
                    record['close'], record['volume']
                ))
            elif record['type'] == 'tick':
                session.execute(insert_tick, (
                    record['symbol'], record['epoch_float'],
                    record['price'], record['volume']
                ))
            
            count += 1
            if count % 1000 == 0:
                print(f"Progress: {count}/{len(data)} records inserted")
    
    print(f"Backfill complete: {count} records inserted to {keyspace}")
    
    # Verify data
    verify_backfill(session, keyspace, start_time, end_time)
    
    cluster.shutdown()
    return 0

def fetch_historical_data(source, exchange, start_time, end_time):
    """
    Fetch historical data from external source.
    Could be:
    - CSV file from data vendor
    - API call to data provider
    - Backup/archive database
    """
    # Implementation depends on your data source
    # Example: read from CSV file
    import csv
    data = []
    
    with open(source, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse and convert to format for insertion
            data.append({
                'type': 'minbar',
                'symbol': row['symbol'],
                'epoch_float': float(row['timestamp']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })
    
    return data

def verify_backfill(session, keyspace, start_time, end_time):
    """
    Verify backfilled data is present and correct.
    """
    # Check record count
    result = session.execute(f"""
        SELECT COUNT(*) FROM {keyspace}.minbar 
        WHERE epoch_float >= {start_time.timestamp()} 
        AND epoch_float <= {end_time.timestamp()}
        ALLOW FILTERING
    """)
    count = result.one()[0]
    print(f"Verification: Found {count} records in backfill period")

def main():
    parser = argparse.ArgumentParser(description='Backfill exchange data')
    parser.add_argument('--exchange', required=True, 
                       choices=['NYSE', 'NASDAQ', 'HKEX'],
                       help='Exchange to backfill')
    parser.add_argument('--start', required=True,
                       help='Start time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', required=True,
                       help='End time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--source', required=True,
                       help='Data source (file path or URL)')
    
    args = parser.parse_args()
    
    start_time = datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S')
    
    return backfill(args.exchange, start_time, end_time, args.source)

if __name__ == '__main__':
    sys.exit(main())
```

### Usage Examples

```bash
# Backfill NYSE data from CSV file
python3 backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --source /data/nyse_backfill_20260217.csv

# Backfill NASDAQ data from API
python3 backfill_exchange.py \
  --exchange NASDAQ \
  --start "2026-02-16 14:30:00" \
  --end "2026-02-16 21:00:00" \
  --source "https://api.dataprovider.com/historical?exchange=NASDAQ"

# Backfill HKEX data from another Cassandra instance
python3 backfill_exchange.py \
  --exchange HKEX \
  --start "2026-02-17 01:00:00" \
  --end "2026-02-17 08:00:00" \
  --source "cassandra://backup-cluster:9042/tqdb_hkex"
```

## Backfill Best Practices

### 1. Check Before Backfill

**Verify what data is actually missing:**

```bash
# Query to find gaps in data
docker exec tqdb-cassandra-nyse cqlsh -e "
SELECT symbol, epoch_float, close 
FROM tqdb_nyse.minbar 
WHERE symbol = 'AAPL' 
  AND epoch_float >= 1645056000.0 
  AND epoch_float <= 1645061400.0
ORDER BY epoch_float ASC;
"

# Look for gaps in timestamps
# Expected: every 60 seconds for 1-minute bars
# If gaps exist, those are periods to backfill
```

### 2. Backfill During Low-Traffic Periods

**Schedule backfills when cluster load is low:**

```bash
# Good times for backfills:
# - After market close
# - During maintenance windows
# - Weekends (for non-24/7 exchanges)

# Bad times:
# - During market hours (competes with real-time ingestion)
# - During peak query times
```

### 3. Use Batch Processing

**Don't insert one record at a time:**

```python
# BAD: One insert per execute
for record in data:
    session.execute(insert_stmt, record)

# GOOD: Use batch statements
from cassandra.query import BatchStatement

batch = BatchStatement()
for record in data[:100]:  # Batch size 100
    batch.add(insert_stmt, record)
session.execute(batch)
```

### 4. Monitor Progress

**Track backfill progress:**

```python
import time

total = len(data)
start_time = time.time()

for i, record in enumerate(data):
    session.execute(insert_stmt, record)
    
    if i % 1000 == 0:
        elapsed = time.time() - start_time
        rate = i / elapsed
        remaining = (total - i) / rate
        print(f"Progress: {i}/{total} ({i/total*100:.1f}%) - "
              f"Rate: {rate:.0f} rec/sec - "
              f"ETA: {remaining/60:.1f} min")
```

### 5. Verify After Backfill

**Always verify data was inserted correctly:**

```bash
# Count records in backfill period
docker exec tqdb-cassandra-nyse cqlsh -e "
SELECT COUNT(*) FROM tqdb_nyse.minbar 
WHERE symbol = 'AAPL' 
  AND epoch_float >= 1645056000.0 
  AND epoch_float <= 1645061400.0
ALLOW FILTERING;
"

# Spot-check specific records
docker exec tqdb-cassandra-nyse cqlsh -e "
SELECT * FROM tqdb_nyse.minbar 
WHERE symbol = 'AAPL' 
  AND epoch_float = 1645056000.0;
"
```

### 6. Handle Duplicates Gracefully

**Cassandra handles duplicates with UPSERT behavior:**

```python
# If backfill overlaps with existing data, Cassandra will:
# - Overwrite existing records (INSERT = UPSERT)
# - Keep the most recent timestamp (if using writetime)

# This is safe! You can re-run backfills without data corruption
```

## Automated Backfill Detection

### Monitoring Script for Data Gaps

```python
#!/usr/bin/env python3
# tools/detect_gaps.py

import time
from datetime import datetime, timedelta
from cassandra.cluster import Cluster

def detect_gaps(exchange, keyspace, lookback_hours=24):
    """
    Detect gaps in time-series data and suggest backfills.
    """
    cluster = Cluster(['192.168.1.10', '192.168.1.11'])
    session = cluster.connect(keyspace)
    
    # Get list of symbols
    symbols = session.execute(f"SELECT symbol FROM {keyspace}.symbol")
    
    gaps = []
    
    for symbol in symbols:
        # Expected interval (60 seconds for 1-minute bars)
        expected_interval = 60.0
        
        # Query recent data
        now = time.time()
        start = now - (lookback_hours * 3600)
        
        result = session.execute(f"""
            SELECT epoch_float FROM {keyspace}.minbar
            WHERE symbol = %s
              AND epoch_float >= %s
            ORDER BY epoch_float ASC
        """, (symbol.symbol, start))
        
        timestamps = [row.epoch_float for row in result]
        
        # Find gaps
        for i in range(len(timestamps) - 1):
            gap = timestamps[i+1] - timestamps[i]
            if gap > expected_interval * 2:  # Missing 2+ intervals
                gaps.append({
                    'exchange': exchange,
                    'symbol': symbol.symbol,
                    'start': datetime.fromtimestamp(timestamps[i]),
                    'end': datetime.fromtimestamp(timestamps[i+1]),
                    'duration_minutes': gap / 60
                })
    
    # Report gaps
    if gaps:
        print(f"Found {len(gaps)} data gaps in {exchange}:")
        for gap in gaps:
            print(f"  {gap['symbol']}: {gap['start']} to {gap['end']} "
                  f"({gap['duration_minutes']:.0f} minutes)")
    else:
        print(f"No gaps found in {exchange} for last {lookback_hours} hours")
    
    cluster.shutdown()
    return gaps

if __name__ == '__main__':
    # Check all exchanges
    for exchange, keyspace in [('NYSE', 'tqdb_nyse'), 
                                 ('NASDAQ', 'tqdb_nasdaq'),
                                 ('HKEX', 'tqdb_hkex')]:
        print(f"\nChecking {exchange}...")
        detect_gaps(exchange, keyspace)
```

### Automated Backfill Trigger

```bash
#!/bin/bash
# tools/auto_backfill.sh

# Detect gaps
python3 /opt/tqdb/tools/detect_gaps.py > /tmp/gaps.log

# If gaps found, trigger backfill
if [ -s /tmp/gaps.log ]; then
    echo "Gaps detected, initiating backfill..."
    
    # Parse gaps and trigger backfills
    # (Implementation depends on your data source)
    
    # Send notification
    echo "Backfill required" | mail -s "TQDB Backfill Alert" admin@example.com
fi
```

## Summary

### Quick Decision Guide

**"Where should I backfill NYSE data?"**

1. **Small backfill (<1 hour)**: NYSE node or Master node - doesn't matter
2. **Large backfill (>1 hour)**: NYSE node - more efficient
3. **Multiple exchanges**: Master node - centralized management
4. **Frequent backfills**: Dedicated backfill node - isolation

### Key Takeaways

✅ **Any node works** - Cassandra routes data to correct replicas  
✅ **Exchange-specific node is optimal** - Efficient, logical, isolated  
✅ **Master node is convenient** - Centralized operations  
✅ **Use Token-Aware policy** - Driver optimizes replica selection  
✅ **Verify after backfill** - Always check data integrity  
✅ **Automate gap detection** - Monitor for missing data  

### The Cassandra Advantage

Because Cassandra handles replication automatically, you have **flexibility** in where you run backfills. The data will always end up on the correct nodes based on your keyspace replication configuration. This is a huge operational advantage!

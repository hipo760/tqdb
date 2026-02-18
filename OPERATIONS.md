# TQDB Operations Guide

Complete operational procedures for TQDB cluster management, backfill operations, monitoring, and troubleshooting.

## Table of Contents

- [1. Daily Operations](#1-daily-operations)
- [2. Backfill Procedures](#2-backfill-procedures)
- [3. Monitoring & Health Checks](#3-monitoring--health-checks)
- [4. Troubleshooting](#4-troubleshooting)
- [5. Maintenance Tasks](#5-maintenance-tasks)
- [6. Emergency Procedures](#6-emergency-procedures)

---

## 1. Daily Operations

### 1.1 Cluster Health Check

**Daily checklist (5 minutes):**

```bash
# Check all nodes are UP
nodetool status

# Expected output:
# UN = Up and Normal (✓ good)
# DN = Down and Normal (✗ investigate)
# UL = Up and Leaving (⚠️ decommission in progress)
# DN = Down and Normal (✗ node failure)

# Check for pending tasks
nodetool tpstats

# Check disk space on all nodes
df -h /var/lib/cassandra

# Check error logs
tail -100 /var/log/cassandra/system.log | grep -i error
```

### 1.2 Real-Time Ingestion Status

```bash
# Check latest data timestamp per exchange
cqlsh -e "SELECT exchange, symbol, MAX(dt) as latest_data 
          FROM tqdb_nyse.minbar 
          GROUP BY exchange, symbol 
          LIMIT 10;"

# Check ingestion rate (inserts per second)
nodetool tablestats tqdb_nyse.minbar | grep "Local write count"
```

### 1.3 Data Verification

```bash
# Verify data consistency across replicas
nodetool repair tqdb_nyse

# Check for data size anomalies
nodetool tablestats | grep "Space used"
```

---

## 2. Backfill Procedures

### 2.1 When to Backfill

**Common scenarios:**
- Quote service downtime (network, service restart, maintenance)
- Data feed interruption from exchange
- Failed real-time ingestion (bug, crash)
- Historical data correction

**Detection:**
```bash
# Check for gaps in minute bars
python3 tools/detect_gaps.py --exchange NYSE --date 2026-02-17
```

### 2.2 Backfill Decision Matrix

| Scenario | Recommended Node | Reason |
|----------|-----------------|---------|
| Single exchange gap | Exchange-specific node | Network efficiency |
| Multiple exchange gaps | Master node | Convenience |
| Large backfill (>1 day) | Dedicated backfill node | Avoid impacting production |
| Real-time still running | Exchange-specific node | Isolation from master |

### 2.3 Quick Backfill Procedure

#### Step 1: Identify Gap

```bash
# Detect missing data
python3 tools/detect_gaps.py \
  --exchange NYSE \
  --start "2026-02-17 00:00:00" \
  --end "2026-02-17 23:59:59"

# Output example:
# Gap found: 2026-02-17 10:00:00 to 2026-02-17 11:30:00 (90 minutes)
```

#### Step 2: Prepare Backfill Data

```bash
# Option A: Download from backup/archive
aws s3 cp s3://tqdb-archive/NYSE/2026-02-17-10-00.csv /tmp/

# Option B: Query from another system
curl -o /tmp/nyse_data.csv "https://archive.example.com/NYSE?start=..."

# Option C: Use market data provider API
python3 tools/fetch_historical.py --exchange NYSE --start "2026-02-17 10:00" ...
```

#### Step 3: Execute Backfill

**Recommended: Backfill on exchange-specific node**

```bash
# SSH to NYSE node
ssh tqdb@192.168.1.11

# Run backfill (minute bars)
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_minbar.py \
  --exchange NYSE \
  --keyspace tqdb_nyse \
  --input /tmp/nyse_data.csv \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --batch-size 1000 \
  --dry-run

# If dry-run looks good, execute for real
docker exec tqdb-tools python3 /opt/tqdb/tools/backfill_minbar.py \
  --exchange NYSE \
  --keyspace tqdb_nyse \
  --input /tmp/nyse_data.csv \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --batch-size 1000
```

#### Step 4: Verify Backfill

```bash
# Check data count
cqlsh -e "SELECT COUNT(*) FROM tqdb_nyse.minbar 
          WHERE symbol='AAPL' 
          AND dt >= '2026-02-17 10:00:00' 
          AND dt <= '2026-02-17 11:30:00';"

# Expected: 90 rows (one per minute)

# Verify data quality (check for NULL values)
cqlsh -e "SELECT * FROM tqdb_nyse.minbar 
          WHERE symbol='AAPL' 
          AND dt >= '2026-02-17 10:00:00' 
          LIMIT 5;"
```

### 2.4 Automated Backfill Script

**Complete Python script** (save as `tools/backfill_minbar.py`):

```python
#!/usr/bin/env python3
"""
Backfill minute bar data to TQDB exchange-specific cluster
"""
import argparse
import csv
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import BatchStatement, SimpleStatement


def parse_args():
    parser = argparse.ArgumentParser(description='Backfill minute bar data')
    parser.add_argument('--exchange', required=True, help='Exchange name (NYSE, NASDAQ, HKEX)')
    parser.add_argument('--keyspace', required=True, help='Keyspace name (tqdb_nyse, tqdb_nasdaq, etc.)')
    parser.add_argument('--input', required=True, help='Input CSV file path')
    parser.add_argument('--start', required=True, help='Start datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', required=True, help='End datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for inserts')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no writes)')
    parser.add_argument('--cassandra-hosts', default='localhost', help='Comma-separated Cassandra hosts')
    return parser.parse_args()


def connect_cassandra(hosts, keyspace):
    """Connect to Cassandra cluster"""
    cluster = Cluster(hosts.split(','))
    session = cluster.connect(keyspace)
    return cluster, session


def backfill_data(session, input_file, start_dt, end_dt, batch_size, dry_run):
    """Backfill data from CSV file"""
    
    # Prepare INSERT statement
    insert_stmt = session.prepare("""
        INSERT INTO minbar (symbol, dt, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """)
    
    start = datetime.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
    end = datetime.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
    
    records = []
    skipped = 0
    
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse datetime
            dt = datetime.strptime(row['datetime'], '%Y-%m-%d %H:%M:%S')
            
            # Filter by time range
            if not (start <= dt <= end):
                skipped += 1
                continue
            
            records.append((
                row['symbol'],
                dt,
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                int(row['volume'])
            ))
    
    print(f"Loaded {len(records)} records from {input_file}")
    print(f"Skipped {skipped} records outside time range")
    
    if dry_run:
        print("DRY RUN - No data written")
        print(f"Would insert {len(records)} records")
        return len(records)
    
    # Insert in batches
    inserted = 0
    for i in range(0, len(records), batch_size):
        batch = BatchStatement()
        chunk = records[i:i+batch_size]
        
        for record in chunk:
            batch.add(insert_stmt, record)
        
        session.execute(batch)
        inserted += len(chunk)
        print(f"Inserted {inserted}/{len(records)} records...")
    
    print(f"✓ Backfill complete: {inserted} records inserted")
    return inserted


def main():
    args = parse_args()
    
    print(f"=== TQDB Backfill ===")
    print(f"Exchange: {args.exchange}")
    print(f"Keyspace: {args.keyspace}")
    print(f"Time range: {args.start} to {args.end}")
    print(f"Input file: {args.input}")
    print(f"Batch size: {args.batch_size}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Connect to Cassandra
    cluster, session = connect_cassandra(args.cassandra_hosts, args.keyspace)
    
    try:
        # Perform backfill
        count = backfill_data(
            session,
            args.input,
            args.start,
            args.end,
            args.batch_size,
            args.dry_run
        )
        
        print(f"\n✓ Success: {count} records processed")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cluster.shutdown()


if __name__ == '__main__':
    main()
```

**Usage examples:**

```bash
# Dry run to test
python3 backfill_minbar.py \
  --exchange NYSE \
  --keyspace tqdb_nyse \
  --input /tmp/nyse_gap.csv \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --dry-run

# Execute backfill
python3 backfill_minbar.py \
  --exchange NYSE \
  --keyspace tqdb_nyse \
  --input /tmp/nyse_gap.csv \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --batch-size 1000

# Backfill from remote node
python3 backfill_minbar.py \
  --exchange NYSE \
  --keyspace tqdb_nyse \
  --input /tmp/nyse_gap.csv \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --cassandra-hosts "192.168.1.10,192.168.1.11"  # Master and NYSE node
```

### 2.5 Automated Gap Detection

**Create `tools/detect_gaps.py`:**

```python
#!/usr/bin/env python3
"""
Detect gaps in minute bar data
"""
import argparse
from datetime import datetime, timedelta
from cassandra.cluster import Cluster


def detect_gaps(session, symbol, start_date, end_date):
    """Detect missing minute bars"""
    query = "SELECT dt FROM minbar WHERE symbol = ? AND dt >= ? AND dt < ?"
    stmt = session.prepare(query)
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    
    # Fetch all existing timestamps
    rows = session.execute(stmt, (symbol, start, end))
    existing_times = set(row.dt for row in rows)
    
    # Generate expected timestamps (market hours: 9:30 AM - 4:00 PM)
    expected_times = []
    current = start.replace(hour=9, minute=30, second=0)
    market_close = current.replace(hour=16, minute=0)
    
    while current < end:
        if current.time() >= datetime.strptime("09:30", "%H:%M").time() and \
           current.time() < datetime.strptime("16:00", "%H:%M").time() and \
           current.weekday() < 5:  # Monday-Friday
            expected_times.append(current)
        current += timedelta(minutes=1)
    
    # Find gaps
    missing_times = sorted(set(expected_times) - existing_times)
    
    return missing_times


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exchange', required=True)
    parser.add_argument('--symbol', default='AAPL')
    parser.add_argument('--date', required=True, help='Date to check (YYYY-MM-DD)')
    parser.add_argument('--keyspace', help='Keyspace (auto-determined from exchange if not provided)')
    args = parser.parse_args()
    
    keyspace = args.keyspace or f"tqdb_{args.exchange.lower()}"
    
    cluster = Cluster(['localhost'])
    session = cluster.connect(keyspace)
    
    gaps = detect_gaps(session, args.symbol, args.date, args.date)
    
    if gaps:
        print(f"✗ Found {len(gaps)} missing minute bars:")
        for gap in gaps[:10]:  # Show first 10
            print(f"  - {gap}")
        if len(gaps) > 10:
            print(f"  ... and {len(gaps)-10} more")
    else:
        print(f"✓ No gaps found for {args.symbol} on {args.date}")
    
    cluster.shutdown()


if __name__ == '__main__':
    main()
```

---

## 3. Monitoring & Health Checks

### 3.1 Cluster Monitoring

**Key metrics to monitor:**

```bash
# Node status
nodetool status

# Disk usage per keyspace
nodetool tablestats tqdb_nyse | grep "Space used"

# Read/write latency
nodetool tablestats tqdb_nyse.minbar | grep "latency"

# Pending compactions
nodetool compactionstats

# Memory usage
nodetool info | grep "Heap Memory"
```

### 3.2 Automated Health Check Script

```bash
#!/bin/bash
# health_check.sh - Run every 5 minutes via cron

ALERT_EMAIL="ops@example.com"
THRESHOLD_DISK=80  # Alert if disk >80% full

# Check Cassandra status
STATUS=$(nodetool status | grep -c "^UN")
TOTAL_NODES=4

if [ "$STATUS" -lt "$TOTAL_NODES" ]; then
  echo "ALERT: Only $STATUS/$TOTAL_NODES nodes are UP" | mail -s "TQDB Alert" $ALERT_EMAIL
fi

# Check disk space
DISK_USAGE=$(df -h /var/lib/cassandra | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt "$THRESHOLD_DISK" ]; then
  echo "ALERT: Disk usage at ${DISK_USAGE}%" | mail -s "TQDB Disk Alert" $ALERT_EMAIL
fi

# Check for errors in logs
ERRORS=$(tail -100 /var/log/cassandra/system.log | grep -c "ERROR")
if [ "$ERRORS" -gt 0 ]; then
  echo "ALERT: $ERRORS errors in last 100 log lines" | mail -s "TQDB Error Alert" $ALERT_EMAIL
fi
```

### 3.3 Performance Monitoring

```bash
# Query performance (run periodically)
time cqlsh -e "SELECT * FROM tqdb_nyse.minbar WHERE symbol='AAPL' AND dt >= '2026-02-17 00:00:00' LIMIT 1000;"

# Throughput monitoring
nodetool tpstats | grep -A 2 "Pool Name"

# Connection monitoring
netstat -an | grep :9042 | wc -l  # Active Cassandra connections
```

---

## 4. Troubleshooting

### 4.1 Common Issues

#### Issue: Node Shows DN (Down Normal)

**Symptoms:**
```bash
nodetool status
# DN  192.168.1.11  ...  rack_nyse
```

**Diagnosis:**
```bash
# Check if Cassandra is running
systemctl status cassandra
# Or for Docker:
docker ps | grep cassandra

# Check logs
tail -50 /var/log/cassandra/system.log

# Check network connectivity
ping 192.168.1.11
telnet 192.168.1.11 9042
```

**Solutions:**
1. Restart Cassandra: `systemctl restart cassandra`
2. Check firewall: `sudo firewall-cmd --list-all`
3. Check memory: `free -h` (Cassandra needs 4GB+ heap)
4. Check disk: `df -h`

#### Issue: Query Timeouts

**Symptoms:**
```
cassandra.OperationTimedOut: errors={...}, last_host=192.168.1.10
```

**Diagnosis:**
```bash
# Check network latency
ping 192.168.1.10

# Check node load
nodetool info | grep "Load"

# Check pending tasks
nodetool tpstats | grep -i read
```

**Solutions:**
1. Increase timeout in application: `request_timeout=30`
2. Add indexes if querying non-partition key
3. Check if node is overloaded
4. Run `nodetool repair` if data is inconsistent

#### Issue: Data Not Replicating

**Symptoms:**
- Data on master but not on exchange node
- `nodetool status` shows different data sizes

**Diagnosis:**
```bash
# Check replication factor
cqlsh -e "DESCRIBE KEYSPACE tqdb_nyse;"

# Check if schema matches on all nodes
nodetool describecluster

# Check for hints (delayed writes)
nodetool geth intedhandoffinfo
```

**Solutions:**
```bash
# Run repair on keyspace
nodetool repair tqdb_nyse

# Rebuild node from another node
nodetool rebuild -- <source_datacenter>
```

#### Issue: Out of Memory

**Symptoms:**
```
java.lang.OutOfMemoryError: Java heap space
```

**Solutions:**
```bash
# Increase heap size in cassandra-env.sh
MAX_HEAP_SIZE="8G"
HEAP_NEWSIZE="2G"

# Or in Docker Compose:
environment:
  - MAX_HEAP_SIZE=8G
  - HEAP_NEWSIZE=2G

# Restart Cassandra
systemctl restart cassandra
```

### 4.2 Emergency Recovery

#### Complete Node Failure

```bash
# 1. Stop failed node
systemctl stop cassandra

# 2. On remaining nodes, run repair
nodetool repair -pr  # Repair primary range only

# 3. Replace failed node
# - Provision new machine
# - Install Cassandra with same cluster config
# - Start with -Dcassandra.replace_address=<failed_node_ip>

# 4. Verify cluster
nodetool status
```

#### Master Node Failure

```bash
# Master node down - queries still work via exchange nodes
# To rebuild master:

# 1. Bring up new master node
# 2. Restore from exchange nodes
nodetool rebuild -- dc1

# 3. Verify data
cqlsh -e "SELECT COUNT(*) FROM tqdb_nyse.minbar;"
```

---

## 5. Maintenance Tasks

### 5.1 Weekly Maintenance

```bash
# Run repair on each keyspace (off-peak hours)
nodetool repair tqdb_nyse
nodetool repair tqdb_nasdaq
nodetool repair tqdb_hkex

# Clean up old snapshots
nodetool clearsnapshot

# Compact SSTables
nodetool compact
```

### 5.2 Monthly Maintenance

```bash
# Check and optimize schema
cqlsh -e "SELECT * FROM system_schema.tables WHERE keyspace_name='tqdb_nyse';"

# Review and archive old data
# Example: Delete data older than 2 years
cqlsh -e "DELETE FROM tqdb_nyse.minbar WHERE dt < '2024-01-01';"

# Vacuum tombstones
nodetool compact
```

### 5.3 Backup Procedures

```bash
# Create snapshot
nodetool snapshot tqdb_nyse -t backup_$(date +%Y%m%d)

# Find snapshot location
find /var/lib/cassandra/data/tqdb_nyse -name "backup_*"

# Copy to backup storage
tar -czf tqdb_nyse_backup.tar.gz /var/lib/cassandra/data/tqdb_nyse/*/snapshots/backup_*
aws s3 cp tqdb_nyse_backup.tar.gz s3://tqdb-backups/

# Clear old snapshots
nodetool clearsnapshot -t backup_20260101
```

---

## 6. Emergency Procedures

### 6.1 Cluster-Wide Emergency

**If entire cluster is unresponsive:**

```bash
# 1. Check all nodes
for node in 192.168.1.10 192.168.1.11 192.168.1.12 192.168.1.13; do
  echo "Checking $node..."
  ssh $node "systemctl status cassandra"
done

# 2. Restart nodes one by one (never all at once!)
ssh 192.168.1.11 "systemctl restart cassandra"
sleep 60
ssh 192.168.1.12 "systemctl restart cassandra"
sleep 60
ssh 192.168.1.13 "systemctl restart cassandra"
sleep 60
ssh 192.168.1.10 "systemctl restart cassandra"

# 3. Verify cluster
nodetool status
```

### 6.2 Data Corruption

```bash
# If you suspect data corruption:

# 1. Stop writes to affected keyspace
# 2. Create snapshot
nodetool snapshot tqdb_nyse -t emergency_backup

# 3. Run scrub to fix corruption
nodetool scrub tqdb_nyse minbar

# 4. Verify data
cqlsh -e "SELECT COUNT(*) FROM tqdb_nyse.minbar;"

# 5. If scrub fails, restore from snapshot
# See backup/restore procedures in DEPLOYMENT_GUIDE.md
```

### 6.3 Emergency Contacts

```
- Primary DBA: [Name] - [Phone] - [Email]
- DevOps Lead: [Name] - [Phone] - [Email]
- On-call Rotation: [PagerDuty/Opsgenie link]
```

---

## Quick Reference

### Essential Commands

```bash
# Cluster status
nodetool status

# Check specific keyspace
nodetool tablestats tqdb_nyse

# Repair keyspace
nodetool repair tqdb_nyse

# Check logs
tail -f /var/log/cassandra/system.log

# Query data
cqlsh -e "SELECT * FROM tqdb_nyse.minbar WHERE symbol='AAPL' LIMIT 10;"

# Backfill (recommended: on exchange node)
python3 tools/backfill_minbar.py --exchange NYSE --keyspace tqdb_nyse --input /tmp/data.csv ...
```

### Health Check Checklist

- [ ] All nodes UN (Up/Normal)
- [ ] Disk usage < 80%
- [ ] No ERROR in recent logs
- [ ] Pending compactions < 10
- [ ] Query latency < 100ms (p95)
- [ ] Real-time ingestion active
- [ ] No data gaps in last 24h

---

**Document Version**: 1.0  
**Last Updated**: February 17, 2026  
**Related Docs**: DEPLOYMENT_GUIDE.md, docs/legacy/

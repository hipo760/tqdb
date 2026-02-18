# Backfill Operations - Visual Quick Reference

## Question: "NYSE quote service was down. Where should I backfill?"

### Answer: **Exchange-specific node (NYSE node) is recommended**

```
┌──────────────────────────────────────────────────────────────┐
│                     Backfill Options                          │
└──────────────────────────────────────────────────────────────┘

Option 1: NYSE Node (RECOMMENDED)
┌────────────────────────────────────────────┐
│  NYSE Node (192.168.1.11)                  │
│  ┌──────────────────────────────────────┐  │
│  │  Backfill Script                     │  │
│  │  INSERT INTO tqdb_nyse.minbar ...    │  │
│  └────────────┬─────────────────────────┘  │
│               │                             │
│         ┌─────┴─────┐                       │
│         ▼           ▼                       │
│    ┌────────┐  ┌────────┐                  │
│    │ Local  │  │Network │                  │
│    │ Write  │  │Write to│                  │
│    │   ✓    │  │ Master │                  │
│    └────────┘  └────────┘                  │
└────────────────────────────────────────────┘
    Efficient: 1 local + 1 remote write


Option 2: Master Node (CENTRALIZED)
┌────────────────────────────────────────────┐
│  Master Node (192.168.1.10)                │
│  ┌──────────────────────────────────────┐  │
│  │  Backfill Script                     │  │
│  │  INSERT INTO tqdb_nyse.minbar ...    │  │
│  └────────────┬─────────────────────────┘  │
│               │                             │
│         ┌─────┴─────┐                       │
│         ▼           ▼                       │
│    ┌────────┐  ┌────────┐                  │
│    │ Local  │  │Network │                  │
│    │ Write  │  │Write to│                  │
│    │   ✓    │  │  NYSE  │                  │
│    └────────┘  └────────┘                  │
└────────────────────────────────────────────┘
    Convenient: Centralized management


Option 3: Other Node (NOT RECOMMENDED)
┌────────────────────────────────────────────┐
│  NASDAQ Node (192.168.1.12)               │
│  ┌──────────────────────────────────────┐  │
│  │  Backfill Script                     │  │
│  │  INSERT INTO tqdb_nyse.minbar ...    │  │
│  └────────────┬─────────────────────────┘  │
│               │                             │
│         ┌─────┴─────┐                       │
│         ▼           ▼                       │
│    ┌────────┐  ┌────────┐                  │
│    │Network │  │Network │                  │
│    │Write to│  │Write to│                  │
│    │ Master │  │  NYSE  │                  │
│    └────────┘  └────────┘                  │
└────────────────────────────────────────────┘
    Inefficient: 2 remote writes
```

## Data Flow During Backfill

```
Backfill Script (Anywhere)
        │
        ▼
INSERT INTO tqdb_nyse.minbar
        │
        ▼
Cassandra Client (Driver)
        │
        ▼
Determines Replicas
(Based on keyspace RF and rack)
        │
        ▼
tqdb_nyse has RF=2, so 2 replicas needed
        │
        ├────────────────┬────────────────┐
        ▼                ▼                ▼
   Master Node      NYSE Node      Other Nodes
   rack_master      rack_nyse      (ignored)
        │                │
        ▼                ▼
   Data written     Data written
        ✓                ✓
```

## Real-World Scenario

```
Timeline:
09:00 - NYSE quote service running normally
10:00 - NYSE quote service CRASHES 💥
10:00-11:30 - NO DATA RECEIVED (90 minutes missing)
11:30 - NYSE quote service RECOVERED ✓
11:31 - Need to backfill 90 minutes


Step 1: Detect Gap
────────────────────────────────────────────────
docker exec tqdb-tools python3 detect_gaps.py

Output:
  Found 1 data gap in NYSE:
    AAPL: 2026-02-17 10:00:00 to 11:30:00 (90 minutes)
    GOOGL: 2026-02-17 10:00:00 to 11:30:00 (90 minutes)
    ... (all NYSE symbols)


Step 2: Get Historical Data
────────────────────────────────────────────────
# Option A: Download from data vendor
curl https://vendor.com/api/nyse?start=10:00&end=11:30 \
  > /data/nyse_backfill_20260217.csv

# Option B: Query from backup Cassandra cluster
# Option C: Pull from internal backup database


Step 3: Run Backfill (on NYSE Node)
────────────────────────────────────────────────
ssh user@192.168.1.11  # NYSE node

docker exec tqdb-tools python3 backfill_exchange.py \
  --exchange NYSE \
  --start "2026-02-17 10:00:00" \
  --end "2026-02-17 11:30:00" \
  --source /data/nyse_backfill_20260217.csv

Output:
  Backfilling NYSE data to keyspace tqdb_nyse
  Period: 2026-02-17 10:00:00 to 2026-02-17 11:30:00
  Fetching data from /data/nyse_backfill_20260217.csv...
  Inserting 5400 records...
  Progress: 1000/5400 (18.5%) - Rate: 250 rec/sec - ETA: 17.6 min
  Progress: 2000/5400 (37.0%) - Rate: 245 rec/sec - ETA: 13.9 min
  Progress: 3000/5400 (55.6%) - Rate: 248 rec/sec - ETA: 9.7 min
  Progress: 4000/5400 (74.1%) - Rate: 246 rec/sec - ETA: 5.7 min
  Progress: 5000/5400 (92.6%) - Rate: 247 rec/sec - ETA: 1.6 min
  Backfill complete: 5400 records inserted to tqdb_nyse
  Verification: Found 5400 records in backfill period ✓


Step 4: Verify Data on Both Nodes
────────────────────────────────────────────────
# Check NYSE node
ssh user@192.168.1.11
docker exec tqdb-cassandra-nyse cqlsh -e \
  "SELECT COUNT(*) FROM tqdb_nyse.minbar 
   WHERE symbol='AAPL' AND epoch_float >= 1645056000 
   ALLOW FILTERING;"

Output: 90 records ✓

# Check Master node  
ssh user@192.168.1.10
docker exec tqdb-cassandra-master cqlsh -e \
  "SELECT COUNT(*) FROM tqdb_nyse.minbar 
   WHERE symbol='AAPL' AND epoch_float >= 1645056000
   ALLOW FILTERING;"

Output: 90 records ✓

SUCCESS! Data replicated to both nodes.
```

## Automated Backfill Workflow

```
┌─────────────────────────────────────────────────────┐
│             Automated Gap Detection                  │
└─────────────────────────────────────────────────────┘
                       │
                       │ Cron job every 15 minutes
                       ▼
        ┌──────────────────────────────┐
        │  detect_gaps.py              │
        │  - Check all exchanges       │
        │  - Look for missing intervals│
        │  - Generate gap report       │
        └──────────────┬───────────────┘
                       │
                       ▼
                  Gap found?
                  /         \
                NO          YES
                │            │
                │            ▼
                │   ┌────────────────────┐
                │   │  Alert Operator    │
                │   │  - Email           │
                │   │  - Slack           │
                │   │  - PagerDuty       │
                │   └────────┬───────────┘
                │            │
                │            ▼
                │   ┌────────────────────┐
                │   │  Fetch Historical  │
                │   │  Data from Source  │
                │   └────────┬───────────┘
                │            │
                │            ▼
                │   ┌────────────────────┐
                │   │  Run Backfill      │
                │   │  (auto or manual)  │
                │   └────────┬───────────┘
                │            │
                │            ▼
                │   ┌────────────────────┐
                │   │  Verify Data       │
                │   │  - Count records   │
                │   │  - Spot check      │
                │   └────────┬───────────┘
                │            │
                └────────────┴───────────►
                       │
                       ▼
                   ┌───────┐
                   │  Done │
                   └───────┘
```

## Common Scenarios

### Scenario 1: Brief Outage (< 1 hour)

```bash
# NYSE down 10:00-10:15 (15 minutes)
# Quick backfill, any node is fine

ssh user@192.168.1.11  # or master
docker exec tqdb-tools python3 backfill_exchange.py \
  --exchange NYSE --start "10:00" --end "10:15" \
  --source /data/nyse_15min.csv
  
# Complete in ~1 minute
```

### Scenario 2: Extended Outage (hours)

```bash
# NASDAQ down 14:00-21:00 (7 hours)
# Large backfill, use exchange-specific node for efficiency

ssh user@192.168.1.12  # NASDAQ node (more efficient)
docker exec tqdb-tools python3 backfill_exchange.py \
  --exchange NASDAQ --start "14:00" --end "21:00" \
  --source /data/nasdaq_7hours.csv
  
# May take 20-30 minutes for large dataset
# Run during low-traffic period (after market close)
```

### Scenario 3: Multiple Exchanges Down

```bash
# Disaster: All exchanges down 02:00-03:00
# Use master node for centralized backfill coordination

ssh user@192.168.1.10  # Master node

# Backfill all exchanges
for exchange in NYSE NASDAQ HKEX; do
  docker exec tqdb-tools python3 backfill_exchange.py \
    --exchange $exchange --start "02:00" --end "03:00" \
    --source /data/${exchange}_backup.csv &
done

wait  # Wait for all backfills to complete
```

### Scenario 4: Partial Symbol Outage

```bash
# Only AAPL data missing from NYSE
# Backfill just that symbol

docker exec tqdb-tools python3 backfill_exchange.py \
  --exchange NYSE --start "10:00" --end "11:30" \
  --symbol AAPL \
  --source /data/aapl_only.csv
```

## Performance Considerations

```
Backfill Node Selection Impact:

Exchange Node (RECOMMENDED):
├─ Write latency: ~1-5ms avg
├─ Network traffic: Minimal (1 hop to master)
├─ Node load: Only exchange node affected
└─ Best for: Most backfills

Master Node (ACCEPTABLE):
├─ Write latency: ~1-5ms avg  
├─ Network traffic: Minimal (1 hop to exchange)
├─ Node load: Master node affected
└─ Best for: Centralized operations

Other Node (AVOID):
├─ Write latency: ~5-10ms avg
├─ Network traffic: Higher (2 remote hops)
├─ Node load: Wrong node impacted
└─ Best for: Never use this
```

## Key Takeaways

✅ **Backfill on exchange-specific node** - Most efficient  
✅ **Master node is acceptable** - Convenient for ops  
✅ **Any node technically works** - Cassandra handles routing  
✅ **Automate gap detection** - Don't wait for users to complain  
✅ **Verify after backfill** - Always check data integrity  
✅ **Schedule during low traffic** - Don't compete with real-time  

## Next Steps

1. ✅ Read [BACKFILL_STRATEGY.md](BACKFILL_STRATEGY.md) - Complete guide
2. ✅ Implement `backfill_exchange.py` - Copy script from docs
3. ✅ Set up `detect_gaps.py` - Automated monitoring
4. ✅ Create runbooks - Document your specific backfill procedures
5. ✅ Test backfill process - Before you need it in production!

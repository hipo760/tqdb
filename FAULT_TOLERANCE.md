# TQDB Cassandra Cluster - Fault Tolerance Guide

## 🎯 Question: Can Exchange Node Work If Main Node Is Down?

**SHORT ANSWER: YES** - The CME exchange node can continue to function if the main node goes down, with some limitations.

## 📊 Failure Scenarios

### Scenario 1: Main Node Goes Down

```
Before:                          After Main Node Failure:
┌──────────────┐                 ┌──────────────┐
│  Main Node   │                 │  Main Node   │
│  (UP)        │◄───────┐        │  (DOWN) ❌   │
└──────────────┘        │        └──────────────┘
                        │
┌──────────────┐        │        ┌──────────────┐
│  CME Node    │────────┘        │  CME Node    │
│  (UP)        │                 │  (UP) ✅     │
└──────────────┘                 └──────────────┘

Result: CME node continues working
```

### What Still Works ✅

1. **Read Operations**
   - All SELECT queries work normally
   - Full access to replicated data
   - No performance degradation

2. **Write Operations** (with consistency adjustments)
   - Writes with `CONSISTENCY ONE` work fine
   - Writes with `CONSISTENCY LOCAL_ONE` work fine
   - Data is written to CME node

3. **Node Operations**
   - CME node stays running
   - Local queries succeed
   - Applications can connect

4. **Automatic Recovery**
   - When main node returns, it syncs automatically
   - No manual intervention needed
   - Data reconciliation via hinted handoff

### What Has Issues ⚠️

1. **Consistency Level Restrictions**
   ```sql
   -- These will FAIL with main node down:
   CONSISTENCY QUORUM;   -- Needs 2 nodes, only 1 available
   CONSISTENCY ALL;      -- Needs all nodes
   
   -- These will WORK:
   CONSISTENCY ONE;      -- Only needs 1 node ✅
   CONSISTENCY LOCAL_ONE;-- Only needs 1 local node ✅
   ```

2. **Reduced Fault Tolerance**
   - No redundancy left (RF=2 but only 1 node)
   - If CME node also fails, data is temporarily unavailable
   - Single point of failure until main recovers

3. **Cluster Management**
   - Can't add new nodes (no seed available)
   - Can't run repairs across cluster
   - Schema changes may have issues

4. **Performance Impact**
   - Writes may be slower (waiting for hints)
   - Increased disk usage (storing hints for main node)

## 🔧 Improved Configuration

### Multiple Seed Nodes (Recommended)

Instead of only using main node as seed, configure **both nodes as seeds**:

#### docker-compose.main.yml
```yaml
environment:
  # Use both nodes as seeds for better fault tolerance
  - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
```

#### docker-compose.cme.yml
```yaml
environment:
  # Use both nodes as seeds
  - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
```

**Benefits:**
- Either node can act as seed for new nodes
- Cluster can function if any single seed is down
- Better resilience during restarts

### Client Configuration

Configure your application with multiple contact points:

```python
# Python example
from cassandra.cluster import Cluster

cluster = Cluster(
    contact_points=['192.168.1.10', '192.168.1.11'],  # Both nodes
    protocol_version=4,
    load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='dc1')
)
```

```java
// Java example
Cluster cluster = Cluster.builder()
    .addContactPoints("192.168.1.10", "192.168.1.11")
    .build();
```

**Benefits:**
- Client automatically tries other node if one fails
- Automatic failover
- Continued operation during node maintenance

## 📈 Testing Fault Tolerance

### Test 1: Stop Main Node

```bash
# On main server
docker-compose -f docker-compose.main.yml down

# On CME server - verify it still works
docker exec -it tqdb-cassandra-cme cqlsh

cqlsh> CONSISTENCY ONE;
cqlsh> SELECT * FROM tqdb_cme.symbol LIMIT 10;  # Should work ✅

cqlsh> CONSISTENCY QUORUM;
cqlsh> SELECT * FROM tqdb_cme.symbol LIMIT 10;  # Will FAIL ❌
# Error: "NoHostAvailable: ('Unable to complete the operation against any hosts')"
```

### Test 2: Insert Data While Main Is Down

```bash
docker exec -it tqdb-cassandra-cme cqlsh

cqlsh> CONSISTENCY ONE;
cqlsh> INSERT INTO tqdb_cme.symbol (symbol, keyval) 
       VALUES ('TEST', {'exchange': 'CME', 'name': 'Test Symbol'});
# Success ✅ - Data written to CME node

# When main node comes back up, data will sync automatically
```

### Test 3: Verify Recovery

```bash
# Start main node again
ssh main-server "cd /opt/tqdb && docker-compose -f docker-compose.main.yml up -d"

# Wait 30 seconds for sync

# Check on main node
docker exec -it tqdb-cassandra-main cqlsh -e "SELECT * FROM tqdb_cme.symbol WHERE symbol='TEST';"
# Should show the data written while it was down ✅
```

## 🎚️ Consistency Level Guide

### Recommended Settings for 2-Node Cluster

| Operation | Both Nodes UP | One Node Down | Notes |
|-----------|---------------|---------------|-------|
| **Reads** | `QUORUM` (strong) | `ONE` (eventual) | Auto-failover needed |
| **Writes** | `QUORUM` (strong) | `ONE` (eventual) | Use hinted handoff |
| **Critical Ops** | `ALL` (strongest) | Will FAIL ❌ | Requires all nodes |

### Application Configuration

```python
# Python with automatic downgrade
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel

cluster = Cluster(['192.168.1.10', '192.168.1.11'])
session = cluster.connect('tqdb_cme')

# Try QUORUM first, fall back to ONE on error
try:
    session.execute(query, consistency_level=ConsistencyLevel.QUORUM)
except Exception:
    session.execute(query, consistency_level=ConsistencyLevel.ONE)
```

## 🔄 Hinted Handoff

Cassandra uses **hinted handoff** to handle temporary node failures:

1. **Main node goes down**
2. **CME node stores "hints"** about writes that main node missed
3. **Main node comes back up**
4. **CME node replays hints** to main node (automatic sync)
5. **Data is consistent again**

### Configuration (already enabled by default)
```yaml
# In cassandra.yaml
hinted_handoff_enabled: true
max_hint_window_in_ms: 10800000  # 3 hours
hinted_handoff_throttle_in_kb: 1024
```

### Checking Hints

```bash
# On CME node, check if hints are being stored
docker exec -it tqdb-cassandra-cme nodetool statushandoff

# Check hint stats
docker exec -it tqdb-cassandra-cme nodetool cfstats system.hints
```

## 🚨 Worst Case: Both Nodes Down

If **both nodes go down**:

1. **Data is NOT lost** - It's stored in Docker volumes
2. **Restart nodes** - Data will be available again
3. **No data recovery needed** - Just start the containers

```bash
# Recovery procedure
# 1. Start main node first
docker-compose -f docker-compose.main.yml up -d
sleep 60

# 2. Then start CME node
docker-compose -f docker-compose.cme.yml up -d
sleep 60

# 3. Verify cluster
docker exec -it tqdb-cassandra-main nodetool status

# 4. Run repair if needed
docker exec -it tqdb-cassandra-main nodetool repair tqdb_cme
```

## 💡 Best Practices

### 1. Use Multiple Seeds
```yaml
CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
```

### 2. Configure Client Failover
```python
contact_points=['192.168.1.10', '192.168.1.11']
```

### 3. Monitor Node Status
```bash
# Regular health checks
docker exec -it tqdb-cassandra-cme nodetool status
```

### 4. Use Appropriate Consistency
- **Normal operations**: `QUORUM` (strong consistency)
- **Degraded mode**: `ONE` (availability over consistency)

### 5. Set Up Monitoring/Alerts
```bash
# Example: Check node status every minute
*/1 * * * * docker exec tqdb-cassandra-cme nodetool status | grep -q 'UN' || alert-admin.sh
```

### 6. Regular Backups
```bash
# Daily snapshots
docker exec -it tqdb-cassandra-cme nodetool snapshot tqdb_cme
```

## 📊 High Availability Recommendations

### For Production

Consider adding a third node for better fault tolerance:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Main Node   │◄──►│  CME Node    │◄──►│  Backup Node │
│  (UP)        │    │  (UP)        │    │  (UP)        │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                  RF=3, QUORUM=2

Benefits:
- Can lose ANY 1 node and maintain QUORUM
- Better fault tolerance
- No service degradation on single failure
```

### Split-Brain Prevention

With proper configuration, Cassandra prevents split-brain:
- Uses gossip protocol for node discovery
- Quorum-based consistency
- No "master" election needed

## 🔍 Monitoring Commands

### Check Cluster Health
```bash
# Node status
docker exec -it tqdb-cassandra-cme nodetool status

# Hint stats (are hints accumulating?)
docker exec -it tqdb-cassandra-cme nodetool tpstats | grep -i hint

# Check if node can reach main
docker exec -it tqdb-cassandra-cme nodetool gossipinfo | grep "192.168.1.10"
```

### Test Connection
```bash
# From CME node, try to connect to main
docker exec -it tqdb-cassandra-cme bash -c "nc -zv 192.168.1.10 7000"
```

## 📝 Summary

| Aspect | Status | Details |
|--------|--------|---------|
| **CME node stays running** | ✅ Yes | Continues to operate independently |
| **Read operations** | ✅ Yes | Full access to replicated data |
| **Write operations (ONE)** | ✅ Yes | Writes succeed locally |
| **Write operations (QUORUM)** | ❌ No | Needs 2 nodes, only 1 available |
| **Automatic recovery** | ✅ Yes | Via hinted handoff |
| **Data loss risk** | ⚠️ Low | But no redundancy until main recovers |
| **Add new nodes** | ❌ No | Needs seed node available |

## 🎯 Recommendation

**The exchange node WILL work if main goes down**, making it suitable for:
- **Short-term outages** (maintenance, restarts)
- **Network partitions** (temporary disconnection)
- **Disaster recovery** (main node failure)

**Configure multiple seeds and client failover for best results!**

---

**Version**: 1.0  
**Last Updated**: February 18, 2026

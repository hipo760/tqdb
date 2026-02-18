# TQDB Exchange-Specific Data Distribution - Visual Guide

## Concept Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         THE GOAL                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Different nodes ingest different exchange data                     │
│  One master node keeps EVERYTHING for analytics                     │
│  Users can query ANY node and get ANY exchange data                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Architecture Comparison

### Before: Full Replication (RF=3)

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Node 1      │  │   Node 2      │  │   Node 3      │
├───────────────┤  ├───────────────┤  ├───────────────┤
│ NYSE: 100GB   │  │ NYSE: 100GB   │  │ NYSE: 100GB   │
│ NASDAQ: 80GB  │  │ NASDAQ: 80GB  │  │ NASDAQ: 80GB  │
│ HKEX: 60GB    │  │ HKEX: 60GB    │  │ HKEX: 60GB    │
├───────────────┤  ├───────────────┤  ├───────────────┤
│ Total: 240GB  │  │ Total: 240GB  │  │ Total: 240GB  │
└───────────────┘  └───────────────┘  └───────────────┘

Cluster Total: 720GB (3x redundancy)
```

**Pros:** Maximum availability  
**Cons:** Expensive storage, each node needs same capacity

### After: Exchange-Specific with Master

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Master      │  │   NYSE Node   │  │  NASDAQ Node  │  │   HKEX Node   │
├───────────────┤  ├───────────────┤  ├───────────────┤  ├───────────────┤
│ NYSE: 100GB   │  │ NYSE: 100GB   │  │ NASDAQ: 80GB  │  │ HKEX: 60GB    │
│ NASDAQ: 80GB  │  │ (No NASDAQ)   │  │ (No NYSE)     │  │ (No NYSE)     │
│ HKEX: 60GB    │  │ (No HKEX)     │  │ (No HKEX)     │  │ (No NASDAQ)   │
├───────────────┤  ├───────────────┤  ├───────────────┤  ├───────────────┤
│ Total: 240GB  │  │ Total: 100GB  │  │ Total: 80GB   │  │ Total: 60GB   │
└───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘

Cluster Total: 480GB (2x redundancy per exchange)
```

**Pros:** 33% storage savings, smaller exchange nodes  
**Cons:** Master node is larger, more complex setup

## How It Works: Cassandra Keyspaces + Racks

### Keyspace = Database

Think of keyspaces as separate databases:

```
tqdb_nyse     ─► Only for NYSE data
tqdb_nasdaq   ─► Only for NASDAQ data
tqdb_hkex     ─► Only for HKEX data
```

Each keyspace has its own replication strategy.

### Rack = Physical Location / Role

```
rack_master  ─► Master node (gets everything)
rack_nyse    ─► NYSE-specific node
rack_nasdaq  ─► NASDAQ-specific node
rack_hkex    ─► HKEX-specific node
```

### Replication Strategy

```cql
CREATE KEYSPACE tqdb_nyse 
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Replicate to 2 nodes in datacenter dc1
};
```

**How Cassandra chooses the 2 nodes:**
1. Hash the partition key (symbol) to get token
2. Find primary replica based on token range
3. Find next replica in different rack (rack-aware)
4. Result: Data lands on 2 nodes in different racks

**With our rack setup:**
- NYSE data → Master (rack_master) + NYSE Node (rack_nyse)
- NASDAQ data → Master (rack_master) + NASDAQ Node (rack_nasdaq)
- HKEX data → Master (rack_master) + HKEX Node (rack_hkex)

Master node is always chosen because it's in a different rack from exchange nodes.

## Data Flow Examples

### Example 1: Importing NYSE Data

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Import script runs on NYSE Node                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: INSERT INTO tqdb_nyse.minbar                       │
│         VALUES ('AAPL', 1645056000.0, ...)                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Cassandra determines replicas                      │
│         - Hashes 'AAPL' to get token: 12345                │
│         - Finds nodes responsible for token 12345          │
│         - Ensures replicas in different racks              │
└─────────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│ Master Node          │    │ NYSE Node            │
│ (rack_master)        │    │ (rack_nyse)          │
│                      │    │                      │
│ AAPL data written ✓  │    │ AAPL data written ✓  │
└──────────────────────┘    └──────────────────────┘

NASDAQ Node and HKEX Node DO NOT receive this data
```

### Example 2: Querying NYSE Data from NASDAQ Node

```
┌─────────────────────────────────────────────────────────────┐
│ User sends request to Web UI on NASDAQ Node                │
│ GET /api/q1min?symbol=AAPL&exchange=NYSE                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Application determines keyspace                             │
│ exchange='NYSE' → keyspace='tqdb_nyse'                      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Cassandra Driver checks topology                            │
│ - Knows which nodes have tqdb_nyse data                     │
│ - Master Node (192.168.1.10) has it                         │
│ - NYSE Node (192.168.1.11) has it                           │
│ - Current node (NASDAQ) does NOT have it                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Driver routes query to Master or NYSE Node                  │
│ (Uses load balancing policy - round-robin or token-aware)  │
└─────────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│ Master Node          │    │ NYSE Node            │
│ Query executed ✓     │ OR │ Query executed ✓     │
│ Returns data         │    │ Returns data         │
└──────────────────────┘    └──────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Data returned to user through NASDAQ Node's Web UI         │
└─────────────────────────────────────────────────────────────┘
```

## Key Insights

### 1. No External Load Balancer Needed

The Cassandra driver is smart:

```
Traditional Architecture (NOT USED):
User → Nginx/HAProxy → Pick random node → Hope it has data

TQDB Architecture (USED):
User → Cassandra Driver → Knows topology → Routes to correct node
```

### 2. Master Node is NOT a Single Point of Failure

```
If Master Node Goes Down:

NYSE query  → Goes to NYSE Node (still has data) ✓
NASDAQ query → Goes to NASDAQ Node (still has data) ✓
HKEX query  → Goes to HKEX Node (still has data) ✓

Cross-exchange analytics → Temporarily unavailable ✗
(But you can rebuild master from exchange nodes)
```

### 3. Flexible Data Placement

```
Option A: Master + Each Exchange (Current Design)
- 2x replication per exchange
- Master has complete dataset

Option B: No Master, Just Exchanges
- 1x replication (no redundancy)
- Maximum storage efficiency
- Higher risk

Option C: Master + 2 Exchange Nodes
- 3x replication per exchange
- Maximum availability
- Highest storage cost
```

## Configuration Cheat Sheet

### Rack Configuration

```bash
# Master Node
CASSANDRA_RACK=rack_master

# NYSE Node  
CASSANDRA_RACK=rack_nyse

# NASDAQ Node
CASSANDRA_RACK=rack_nasdaq

# HKEX Node
CASSANDRA_RACK=rack_hkex
```

### Keyspace Configuration

```cql
-- Each exchange gets its own keyspace
CREATE KEYSPACE tqdb_nyse WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Master + NYSE
};

CREATE KEYSPACE tqdb_nasdaq WITH replication = {
  'class': 'NetworkTopologyStrategy', 
  'dc1': 2  -- Master + NASDAQ
};

CREATE KEYSPACE tqdb_hkex WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Master + HKEX
};
```

### Application Configuration

```javascript
// Exchange to Keyspace Mapping
const EXCHANGE_KEYSPACES = {
  'NYSE': 'tqdb_nyse',
  'NASDAQ': 'tqdb_nasdaq',
  'HKEX': 'tqdb_hkex'
};

// Query function
function query(symbol, exchange) {
  const keyspace = EXCHANGE_KEYSPACES[exchange];
  return session.execute(
    `SELECT * FROM ${keyspace}.minbar WHERE symbol = ?`,
    [symbol]
  );
}
```

## Decision Matrix: Should You Use This Pattern?

### Use Exchange-Specific Distribution If:

✅ **You have many exchanges** (5+ exchanges)  
✅ **Each exchange has large datasets** (50GB+ per exchange)  
✅ **Budget constraints** (want smaller nodes for specific exchanges)  
✅ **Master node can handle combined size** (affordable storage)  
✅ **Willing to manage multiple keyspaces** (acceptable complexity)

### Stick with Full Replication (RF=3) If:

❌ **Few exchanges** (1-3 exchanges)  
❌ **Small datasets** (<20GB per exchange)  
❌ **Need maximum simplicity** (one keyspace to rule them all)  
❌ **Need any-node-down tolerance** (can lose any node and keep running)  
❌ **Master node storage is a concern** (master would be too large)

## Cost Comparison Example

### Scenario: 3 exchanges, 100GB each = 300GB total

**Full Replication (RF=3):**
```
3 nodes × 300GB = 900GB total storage
All nodes must be same size (expensive)
```

**Exchange-Specific:**
```
Master:   300GB (all exchanges)
NYSE:     100GB (NYSE only)
NASDAQ:   100GB (NASDAQ only)
HKEX:     100GB (HKEX only)
───────────────────────────────
Total:    600GB (33% savings)
```

**Benefit:** 
- Smaller nodes cost less
- Can scale individual exchanges independently
- Add new exchange without upgrading all nodes

## Common Questions

### Q: Can I query all exchanges at once?

**A:** Yes, connect to the master node or query each keyspace separately:

```javascript
// Query all exchanges
const results = await Promise.all([
  query('AAPL', 'NYSE'),
  query('GOOGL', 'NASDAQ'),
  query('0700', 'HKEX')
]);
```

### Q: What if master node runs out of space?

**A:** Options:
1. Upgrade master node storage
2. Add TTL to auto-delete old data
3. Use compression on master
4. Switch to sharded-by-exchange only (no master)

### Q: Can I add more replicas later?

**A:** Yes, change replication factor:

```cql
ALTER KEYSPACE tqdb_nyse WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 3  -- Changed from 2 to 3
};

-- Then run repair to create new replicas
nodetool repair tqdb_nyse
```

### Q: How does this affect query performance?

**A:** 
- **Reads:** Same or better (driver routes to closest node with data)
- **Writes:** Same (writes go to RF=2 nodes, same as before)
- **Master node queries:** All exchanges available locally (faster for analytics)

## Next Steps

1. **Review:** Read [CLUSTER_ARCHITECTURE.md](CLUSTER_ARCHITECTURE.md) for general cluster setup
2. **Setup:** Follow [EXCHANGE_SPECIFIC_SETUP.md](EXCHANGE_SPECIFIC_SETUP.md) for step-by-step guide
3. **Test:** Start with 2 exchanges to verify the pattern works
4. **Scale:** Add more exchanges as needed

---

**Remember:** This is a trade-off between storage efficiency and operational complexity. Choose the pattern that fits your needs!

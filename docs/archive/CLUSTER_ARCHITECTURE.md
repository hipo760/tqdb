# TQDB Multi-Node Cluster Architecture

## Overview

This document describes the multi-node Cassandra cluster architecture for TQDB, designed to support high availability while maintaining a simple deployment model where each machine runs one Docker Compose stack with one Cassandra node.

## Key Principles

### 1. One Node Per Machine
- Each physical/virtual machine runs one Docker Compose stack
- Each stack contains one Cassandra node + application services
- No complex orchestration required (Kubernetes optional for later)

### 2. Cassandra-Native Clustering
- Nodes discover each other via Gossip protocol
- No external service discovery needed
- Seed nodes for bootstrapping only

### 3. Application Single Entry Point
- Applications connect using Cassandra driver's built-in load balancing
- **No external load balancer required** (HAProxy, Nginx, etc.)
- Driver automatically discovers all nodes and distributes queries
- Automatic failover when nodes go down

## Data Distribution Patterns

TQDB can be deployed with different data distribution strategies depending on your needs:

1. **Full Replication (RF=3)**: All nodes have all data - best for high availability
2. **Exchange-Specific Nodes with Master**: Each node specializes in exchange data, one master has all
3. **Sharded by Exchange (RF=1)**: Each exchange on different nodes, no replication - highest capacity

See "Advanced: Exchange-Specific Data Distribution" section below for detailed configuration.

## Architecture Diagrams

### Single-Node Deployment
```
┌─────────────────────────────────────┐
│        Single Machine               │
│  ┌──────────────────────────────┐   │
│  │   Docker Compose Stack       │   │
│  │  ┌─────────┐ ┌─────────┐     │   │
│  │  │Cassandra│ │ Web UI  │ ────┼───┼─► Users
│  │  │  (RF=1) │ │  + API  │     │   │
│  │  └─────────┘ └─────────┘     │   │
│  │  ┌─────────┐                 │   │
│  │  │  Tools  │                 │   │
│  │  └─────────┘                 │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘

- Use Case: Development, testing, small production
- High Availability: None
- Replication Factor: 1 (SimpleStrategy)
```

### Three-Node Cluster (Production)
```
┌──────────────────────────────────────────────────────────────────┐
│                    Cassandra Cluster (RF=3)                      │
│                                                                  │
│  Machine 1               Machine 2               Machine 3       │
│  192.168.1.10           192.168.1.11           192.168.1.12      │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐   │
│  │   Docker    │        │   Docker    │        │   Docker    │   │
│  │  Compose    │        │  Compose    │        │  Compose    │   │
│  │             │        │             │        │             │   │
│  │ ┌─────────┐ │        │ ┌─────────┐ │        │ ┌─────────┐ │   │
│  │ │Cassandra│ │◄──────►│ │Cassandra│ │◄──────►│ │Cassandra│ │   │
│  │ │  Seed   │ │ Gossip │ │  Seed   │ │ Gossip │ │  Node   │ │   │
│  │ │  Node   │ │  7000  │ │  Node   │ │  7000  │ │         │ │   │
│  │ └────┬────┘ │        │ └────┬────┘ │        │ └────┬────┘ │   │
│  │      │CQL   │        │      │CQL   │        │      │CQL   │   │
│  │      │9042  │        │      │9042  │        │      │9042  │   │
│  │ ┌────┴────┐ │        │ ┌────┴────┐ │        │ ┌────┴────┐ │   │
│  │ │ Web UI  │ │        │ │ Web UI  │ │        │ │ Web UI  │ │   │
│  │ │   API   │─┼────────┼─┤   API   │─┼────────┼─┤   API   │ │   │
│  │ └─────────┘ │        │ └─────────┘ │        │ └─────────┘ │   │
│  │ ┌─────────┐ │        │ ┌─────────┐ │        │ ┌─────────┐ │   │
│  │ │  Tools  │ │        │ │  Tools  │ │        │ │  Tools  │ │   │
│  │ └─────────┘ │        │ └─────────┘ │        │ └─────────┘ │   │
│  └─────────────┘        └─────────────┘        └─────────────┘   │
│         │                       │                       │        │
│         └───────────────────────┴───────────────────────┘        │
│                                 │                                │
│              Application Driver Discovery                        │
│              Contact Points: [10, 11, 12]                        │
│              Driver auto-discovers topology                      │
│              and load balances queries                           │
└──────────────────────────────────────────────────────────────────┘

- Use Case: Production with high availability
- High Availability: Can tolerate 1 node failure
- Replication Factor: 3 (NetworkTopologyStrategy)
- Load Balancing: Cassandra driver built-in (no external LB)
```

## How Application Load Balancing Works

### Traditional Approach (NOT Used)
```
Users → HAProxy/Nginx → Cassandra Nodes
       (External LB)
```
**Problems:**
- Extra infrastructure to manage
- Single point of failure (need HA LB)
- Doesn't understand Cassandra topology
- Manual configuration of backend nodes

### Cassandra Driver Approach (Used)
```
Application (with Cassandra driver)
    ↓
Contact Points: [192.168.1.10, 192.168.1.11]
    ↓
Driver discovers all nodes via metadata
    ↓
Connection pool to all healthy nodes
    ↓
Queries distributed with load balancing policy
```

**Benefits:**
- ✅ No external load balancer needed
- ✅ Topology-aware (prefers local datacenter)
- ✅ Automatic failover
- ✅ Connection pooling built-in
- ✅ Token-aware routing (optimal performance)

## Configuration Examples

### Cassandra Node Configuration

**Environment Variables (each machine):**
```bash
# Machine 1 (192.168.1.10) - Seed Node
CASSANDRA_CLUSTER_NAME=tqdb_cluster
CASSANDRA_DC=dc1
CASSANDRA_RACK=rack1
CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
CASSANDRA_BROADCAST_ADDRESS=192.168.1.10
CASSANDRA_LISTEN_ADDRESS=0.0.0.0
CASSANDRA_RPC_ADDRESS=0.0.0.0

# Machine 2 (192.168.1.11) - Seed Node
CASSANDRA_CLUSTER_NAME=tqdb_cluster
CASSANDRA_DC=dc1
CASSANDRA_RACK=rack2
CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
CASSANDRA_BROADCAST_ADDRESS=192.168.1.11
CASSANDRA_LISTEN_ADDRESS=0.0.0.0
CASSANDRA_RPC_ADDRESS=0.0.0.0

# Machine 3 (192.168.1.12) - Regular Node
CASSANDRA_CLUSTER_NAME=tqdb_cluster
CASSANDRA_DC=dc1
CASSANDRA_RACK=rack3
CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
CASSANDRA_BROADCAST_ADDRESS=192.168.1.12
CASSANDRA_LISTEN_ADDRESS=0.0.0.0
CASSANDRA_RPC_ADDRESS=0.0.0.0
```

### Application Configuration

**Python (cassandra-driver):**
```python
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy

# Specify 2-3 contact points (seed nodes)
cluster = Cluster(
    contact_points=['192.168.1.10', '192.168.1.11', '192.168.1.12'],
    port=9042,
    load_balancing_policy=TokenAwarePolicy(
        DCAwareRoundRobinPolicy(local_dc='dc1')
    ),
    protocol_version=4
)

session = cluster.connect('tqdb1')

# Driver automatically:
# - Discovers all 3 nodes
# - Maintains connection pools
# - Load balances queries
# - Routes queries to optimal node (token-aware)
# - Fails over if a node goes down
```

**Node.js (cassandra-driver):**
```javascript
const cassandra = require('cassandra-driver');

const client = new cassandra.Client({
  contactPoints: ['192.168.1.10', '192.168.1.11', '192.168.1.12'],
  localDataCenter: 'dc1',
  keyspace: 'tqdb1',
  pooling: {
    coreConnectionsPerHost: {
      [cassandra.types.distance.local]: 2,
      [cassandra.types.distance.remote]: 1
    }
  }
});

await client.connect();

// Check connected hosts
client.getState().getConnectedHosts().forEach(host => {
  console.log('Connected to:', host.address);
});
```

**Environment Variables (for applications):**
```bash
# Same on all machines
CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
CASSANDRA_LOCAL_DC=dc1
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=tqdb1
```

## Keyspace Configuration

### Single-Node
```cql
CREATE KEYSPACE tqdb1 
WITH replication = {
  'class': 'SimpleStrategy', 
  'replication_factor': 1
};
```

### Multi-Node Cluster
```cql
CREATE KEYSPACE tqdb1 
WITH replication = {
  'class': 'NetworkTopologyStrategy', 
  'dc1': 3  -- 3 replicas in datacenter dc1
};
```

## Deployment Steps

### Quick Start (3-Node Cluster)

**Step 1: Start First Seed Node**
```bash
# On Machine 1 (192.168.1.10)
export HOST_IP=192.168.1.10
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
docker-compose -f docker-compose.cluster.yml up -d cassandra

# Wait 2-3 minutes for startup
docker exec tqdb-cassandra-node1 nodetool status
```

**Step 2: Start Second Seed Node**
```bash
# On Machine 2 (192.168.1.11)
export HOST_IP=192.168.1.11
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
docker-compose -f docker-compose.cluster.yml up -d cassandra

# Wait for join
docker exec tqdb-cassandra-node2 nodetool status
```

**Step 3: Start Third Node**
```bash
# On Machine 3 (192.168.1.12)
export HOST_IP=192.168.1.12
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
docker-compose -f docker-compose.cluster.yml up -d cassandra

# Verify cluster
docker exec tqdb-cassandra-node3 nodetool status
```

**Step 4: Create Keyspace**
```bash
# On any node
docker exec -it tqdb-cassandra-node1 cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH replication = {
  'class': 'NetworkTopologyStrategy', 
  'dc1': 3
};"
```

**Step 5: Start Applications**
```bash
# On each machine
docker-compose -f docker-compose.cluster.yml up -d web-ui tools
```

## Health Checks

### Cluster Status
```bash
docker exec tqdb-cassandra-node1 nodetool status

# Expected output:
# Datacenter: dc1
# Status=Up/Down (U/D)
# State=Normal/Leaving/Joining/Moving (N/L/J/M)
# Address         Load       Tokens  Owns    Host ID   Rack
# UN 192.168.1.10 128 KB     256     33.3%   xxx       rack1
# UN 192.168.1.11 125 KB     256     33.3%   yyy       rack2
# UN 192.168.1.12 130 KB     256     33.4%   zzz       rack3
```

### Application Connection Test
```bash
# Python test
docker exec tqdb-tools python3 -c "
from cassandra.cluster import Cluster
cluster = Cluster(['192.168.1.10', '192.168.1.11', '192.168.1.12'])
session = cluster.connect('tqdb1')
print('Connected! Hosts:', [str(h.address) for h in cluster.metadata.all_hosts()])
cluster.shutdown()
"
```

## Failure Scenarios

### Scenario 1: One Node Down (RF=3)
```
Before:  [Node1: UP] [Node2: UP] [Node3: UP]
After:   [Node1: UP] [Node2: UP] [Node3: DOWN]

Result: ✅ Cluster operational
- Driver automatically detects Node3 down
- Queries routed to Node1 and Node2
- Data still available (RF=3 means 2 copies remain)
- No manual intervention needed
```

### Scenario 2: Two Nodes Down (RF=3)
```
Before:  [Node1: UP] [Node2: UP] [Node3: UP]
After:   [Node1: UP] [Node2: DOWN] [Node3: DOWN]

Result: ⚠️ Cluster degraded but operational
- Driver routes all queries to Node1
- Some data may be unavailable (depends on consistency level)
- Performance degraded
- Manual intervention recommended
```

### Scenario 3: Seed Node Down
```
Seed nodes are only for bootstrapping!
If a seed node goes down:
- Existing cluster members continue operating normally
- Only impacts new nodes trying to join
- Applications unaffected (driver already has topology)
```

## Best Practices

1. **Seed Nodes**: Use 2-3 seed nodes (not all nodes)
2. **Replication Factor**: RF=3 for production (can tolerate 1 node failure)
3. **Contact Points**: List 2-3 nodes in application config (not all nodes)
4. **Network Mode**: Use `network_mode: host` for inter-node communication
5. **Rack Awareness**: Use different racks for replica distribution
6. **Monitoring**: Regular `nodetool status` checks
7. **Repairs**: Monthly `nodetool repair` on each node
8. **Time Sync**: Ensure NTP/Chrony on all machines

## Network Requirements

### Required Ports
- **9042**: CQL native protocol (client connections)
- **7000**: Inter-node communication (Gossip)
- **7001**: Inter-node SSL (optional)
- **9160**: Thrift (legacy, optional)

### Firewall Rules
```bash
# Between Cassandra nodes
Allow TCP 7000, 7001, 9042 from cluster IPs

# From application containers
Allow TCP 9042 to all Cassandra nodes

# For monitoring
Allow TCP 7199 (JMX) for nodetool
```

## Troubleshooting

### Nodes not joining cluster
```bash
# Check network connectivity
nc -zv 192.168.1.10 7000
nc -zv 192.168.1.10 9042

# Check logs
docker logs tqdb-cassandra-node1

# Check gossip
docker exec tqdb-cassandra-node1 nodetool gossipinfo
```

### Application connection issues
```bash
# Verify contact points reachable
nc -zv 192.168.1.10 9042
nc -zv 192.168.1.11 9042
nc -zv 192.168.1.12 9042

# Check application environment
echo $CASSANDRA_CONTACT_POINTS

# Test connection
docker exec tqdb-web-ui cqlsh 192.168.1.10 -e "DESCRIBE CLUSTER;"
```

---

## Advanced: Exchange-Specific Data Distribution

### Use Case: Exchange-Specialized Nodes with Master Node

**Scenario**: 
- Different nodes ingest data from different exchanges (NYSE, NASDAQ, HKEX, etc.)
- One "master" node keeps ALL exchange data for centralized queries
- Applications can query ANY node and get the data they need

**Example Setup**:
```
Node1 (Master): ALL exchanges (NYSE + NASDAQ + HKEX + ...)
Node2 (NYSE):   Only NYSE data
Node3 (NASDAQ): Only NASDAQ data
Node4 (HKEX):   Only HKEX data
```

### Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                     Exchange-Specific Cluster                       │
│                                                                     │
│  Master Node          NYSE Node          NASDAQ Node    HKEX Node  │
│  192.168.1.10        192.168.1.11       192.168.1.12   192.168.1.13│
│  ┌─────────────┐     ┌─────────────┐    ┌─────────────┐ ┌────────┐│
│  │  Cassandra  │     │  Cassandra  │    │  Cassandra  │ │Cassandra││
│  │             │     │             │    │             │ │        ││
│  │ ALL Data:   │     │ NYSE only:  │    │NASDAQ only: │ │HKEX only││
│  │ ├─NYSE      │◄────┤ ├─NYSE      │    │ ├─NASDAQ   │ │├─HKEX   ││
│  │ ├─NASDAQ    │     │ └─(empty)   │    │ └─(empty)  │ │└─(empty)││
│  │ ├─HKEX      │◄────┼─────────────┼────┤            │ │        ││
│  │ └─...       │◄────┼─────────────┼────┼────────────┼─┤        ││
│  └─────────────┘     └─────────────┘    └─────────────┘ └────────┘│
│         ▲                  ▲                   ▲            ▲      │
│         │                  │                   │            │      │
│         └──────────────────┴───────────────────┴────────────┘      │
│                  Applications can query any node                   │
│              Driver discovers topology and routes correctly        │
└────────────────────────────────────────────────────────────────────┘
```

### Strategy Options

#### Option 1: Multiple Keyspaces (Recommended)

Create separate keyspaces for each exchange with different replication strategies:

```cql
-- Master node holds everything (RF=1 on master's rack)
-- Exchange nodes hold only their data (RF=1 on their rack)

-- NYSE Keyspace - replicated to Master + NYSE node
CREATE KEYSPACE tqdb_nyse 
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Will be on master (rack1) + NYSE node (rack2)
};

-- NASDAQ Keyspace - replicated to Master + NASDAQ node  
CREATE KEYSPACE tqdb_nasdaq
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Will be on master (rack1) + NASDAQ node (rack3)
};

-- HKEX Keyspace - replicated to Master + HKEX node
CREATE KEYSPACE tqdb_hkex
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Will be on master (rack1) + HKEX node (rack4)
};
```

**Rack Configuration:**
```bash
# Master Node (192.168.1.10)
CASSANDRA_RACK=rack1
CASSANDRA_DC=dc1

# NYSE Node (192.168.1.11)
CASSANDRA_RACK=rack2
CASSANDRA_DC=dc1

# NASDAQ Node (192.168.1.12)
CASSANDRA_RACK=rack3
CASSANDRA_DC=dc1

# HKEX Node (192.168.1.13)
CASSANDRA_RACK=rack4
CASSANDRA_DC=dc1
```

**Pros:**
- ✅ Clean separation of exchange data
- ✅ Easy to manage per-exchange replication
- ✅ Can set different retention policies per exchange
- ✅ Master node gets everything automatically

**Cons:**
- ❌ Application needs to know which keyspace for which exchange
- ❌ More keyspaces to manage

#### Option 2: Single Keyspace with Rack-Aware Writes

Use one keyspace but control which racks get which data through application logic:

```cql
-- Single keyspace with RF=2
CREATE KEYSPACE tqdb1
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2  -- Data replicated to 2 nodes
};

-- Tables have same structure
CREATE TABLE tqdb1.minbar (
  symbol text,
  exchange text,  -- Add exchange column
  epoch_float double,
  open float,
  high float,
  low float,
  close float,
  volume bigint,
  PRIMARY KEY ((symbol, exchange), epoch_float)
);
```

**Application-Level Control:**

When writing data, specify the target racks using consistency level:

```python
from cassandra.cluster import Cluster
from cassandra.policies import WhiteListRoundRobinPolicy

# For NYSE data, write to Master + NYSE node
nyse_nodes = ['192.168.1.10', '192.168.1.11']
cluster = Cluster(
    contact_points=nyse_nodes,
    load_balancing_policy=WhiteListRoundRobinPolicy(nyse_nodes)
)
session = cluster.connect('tqdb1')

# Insert NYSE data - will be on Master + NYSE node
session.execute(
    "INSERT INTO minbar (symbol, exchange, epoch_float, ...) VALUES (%s, %s, %s, ...)",
    ('AAPL', 'NYSE', 1645056000.0, ...)
)
```

**Pros:**
- ✅ Single keyspace, simpler management
- ✅ Flexible data placement

**Cons:**
- ❌ Requires application logic to route writes
- ❌ More complex to ensure master gets all data
- ❌ Not recommended - harder to maintain

#### Option 3: Custom Replication Strategy (Advanced)

Create a custom replication strategy that always includes rack1 (master) plus one other rack.

**Pros:**
- ✅ Automatic master replication
- ✅ Application doesn't need to know about racks

**Cons:**
- ❌ Requires custom Java code
- ❌ Complex to implement and maintain
- ❌ Not recommended for most use cases

### Recommended Implementation: Multiple Keyspaces

**Cluster Configuration:**

```yaml
# docker-compose.cluster.yml (Master Node - 192.168.1.10)
services:
  cassandra:
    environment:
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack_master
      - CASSANDRA_BROADCAST_ADDRESS=192.168.1.10
      # ... other settings

# docker-compose.cluster.yml (NYSE Node - 192.168.1.11)
services:
  cassandra:
    environment:
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack_nyse
      - CASSANDRA_BROADCAST_ADDRESS=192.168.1.11
      # ... other settings

# docker-compose.cluster.yml (NASDAQ Node - 192.168.1.12)
services:
  cassandra:
    environment:
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack_nasdaq
      - CASSANDRA_BROADCAST_ADDRESS=192.168.1.12
      # ... other settings
```

**Keyspace Setup Script:**

```bash
#!/bin/bash
# create-exchange-keyspaces.sh

# Create keyspaces for each exchange
# Each keyspace replicates to master rack + specific exchange rack

# NYSE Keyspace
docker exec tqdb-cassandra-master cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS tqdb_nyse 
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
} AND durable_writes = true;

-- Create tables
CREATE TABLE IF NOT EXISTS tqdb_nyse.minbar (
  symbol text,
  epoch_float double,
  open float, high float, low float, close float,
  volume bigint,
  PRIMARY KEY (symbol, epoch_float)
) WITH CLUSTERING ORDER BY (epoch_float DESC);
"

# NASDAQ Keyspace
docker exec tqdb-cassandra-master cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS tqdb_nasdaq
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
};
-- Same table structure...
"

# HKEX Keyspace
docker exec tqdb-cassandra-master cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS tqdb_hkex
WITH replication = {
  'class': 'NetworkTopologyStrategy',
  'dc1': 2
};
-- Same table structure...
"
```

**Application Configuration:**

```javascript
// web-ui/src/lib/api/cassandra.js

const exchangeKeyspaces = {
  'NYSE': 'tqdb_nyse',
  'NASDAQ': 'tqdb_nasdaq',
  'HKEX': 'tqdb_hkex'
};

function getKeyspaceForExchange(exchange) {
  return exchangeKeyspaces[exchange] || 'tqdb1';
}

// Query function
async function queryMinBar(symbol, exchange, startTime, endTime) {
  const keyspace = getKeyspaceForExchange(exchange);
  const query = `SELECT * FROM ${keyspace}.minbar 
                 WHERE symbol = ? AND epoch_float >= ? AND epoch_float <= ?`;
  
  const result = await session.execute(query, [symbol, startTime, endTime]);
  return result.rows;
}
```

**Python Data Import Script:**

```python
# tools/Min2Cass_MultiExchange.py

EXCHANGE_KEYSPACES = {
    'NYSE': 'tqdb_nyse',
    'NASDAQ': 'tqdb_nasdaq',
    'HKEX': 'tqdb_hkex'
}

def import_data(csv_file, exchange):
    keyspace = EXCHANGE_KEYSPACES.get(exchange, 'tqdb1')
    
    # Connect to cluster (will discover all nodes)
    cluster = Cluster(['192.168.1.10', '192.168.1.11', '192.168.1.12'])
    session = cluster.connect(keyspace)
    
    # Prepare insert statement
    insert_stmt = session.prepare(
        f"INSERT INTO {keyspace}.minbar (symbol, epoch_float, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    
    # Import data - Cassandra will route to correct nodes
    for row in read_csv(csv_file):
        session.execute(insert_stmt, row)
```

### Data Flow Example

**Scenario**: Import NYSE data

```
1. Application on NYSE Node (192.168.1.11) imports NYSE CSV
   ↓
2. Writes to tqdb_nyse keyspace
   ↓
3. Cassandra determines replicas based on token range + rack
   ↓
4. Data written to:
   - Master Node (192.168.1.10, rack_master) ✅
   - NYSE Node (192.168.1.11, rack_nyse) ✅
   
5. NASDAQ Node (192.168.1.12) does NOT receive NYSE data ✅
```

**Query Scenario**: User queries NYSE data from any node

```
User → Web UI on NASDAQ Node (192.168.1.12)
       ↓
Query: SELECT * FROM tqdb_nyse.minbar WHERE symbol='AAPL'
       ↓
Driver recognizes tqdb_nyse keyspace
       ↓
Routes query to nodes with NYSE data:
  - Master Node (192.168.1.10) or
  - NYSE Node (192.168.1.11)
       ↓
Returns data ✅
```

### Monitoring Data Distribution

**Check data distribution per node:**

```bash
# On Master Node - should have all keyspaces
docker exec tqdb-cassandra-master nodetool tablestats tqdb_nyse.minbar
docker exec tqdb-cassandra-master nodetool tablestats tqdb_nasdaq.minbar
docker exec tqdb-cassandra-master nodetool tablestats tqdb_hkex.minbar

# On NYSE Node - should only have NYSE
docker exec tqdb-cassandra-nyse nodetool tablestats tqdb_nyse.minbar
# Should show "Table: tqdb_nasdaq.minbar not found" (good!)

# Check which nodes have which data
docker exec tqdb-cassandra-master cqlsh -e "
SELECT * FROM system.peers;
"
```

**Verify replication:**

```bash
# Show token ownership per keyspace
docker exec tqdb-cassandra-master nodetool status tqdb_nyse
docker exec tqdb-cassandra-master nodetool status tqdb_nasdaq
docker exec tqdb-cassandra-master nodetool status tqdb_hkex
```

### Pros and Cons of Exchange-Specific Distribution

**Pros:**
- ✅ **Storage efficiency**: Exchange-specific nodes only store their data
- ✅ **Ingest performance**: Each node can focus on its exchange
- ✅ **Master for analytics**: One node has complete dataset
- ✅ **Flexible**: Can add new exchanges by adding nodes
- ✅ **Cost-effective**: Smaller nodes for specific exchanges

**Cons:**
- ❌ **Complexity**: More keyspaces to manage
- ❌ **Master is bottleneck**: Master node stores all data
- ❌ **Application logic**: Must know exchange-to-keyspace mapping
- ❌ **Master failure**: If master goes down, no single node has all data

### Alternative: Tag-Based Queries (Future Enhancement)

Instead of multiple keyspaces, keep one keyspace but use MaterializedViews or secondary indexes:

```cql
CREATE KEYSPACE tqdb1 WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 2};

CREATE TABLE tqdb1.minbar (
  symbol text,
  exchange text,
  epoch_float double,
  open float, high float, low float, close float, volume bigint,
  PRIMARY KEY ((symbol, exchange), epoch_float)
);

-- Applications query with exchange filter
SELECT * FROM minbar WHERE symbol = 'AAPL' AND exchange = 'NYSE' AND epoch_float > ...;
```

This keeps implementation simpler but doesn't give you rack-specific data placement control.

---

## Summary

This architecture provides:
- ✅ **Simple deployment**: One Docker Compose per machine
- ✅ **High availability**: Automatic failover with RF=3
- ✅ **No external load balancer**: Driver handles load balancing
- ✅ **Single entry point**: Application uses contact points for discovery
- ✅ **Horizontal scaling**: Add nodes by deploying more machines
- ✅ **Topology awareness**: Driver understands cluster structure

The key insight is that **Cassandra drivers are smart clients** that eliminate the need for external load balancers while providing superior performance and reliability.

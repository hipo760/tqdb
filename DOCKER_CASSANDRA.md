# TQDB Cassandra Docker Setup

This directory contains Docker Compose configurations for deploying TQDB's Cassandra infrastructure.

## 📋 Table of Contents

- [Overview](#overview)
- [Single-Node Setup](#single-node-setup)
- [Multi-Node Cluster Setup](#multi-node-cluster-setup)
- [Schema Details](#schema-details)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

Two deployment options are available:

1. **Single-Node** (`docker-compose.yml`) - For development and testing
2. **Multi-Node Cluster** (`docker-compose.cluster.yml`) - For production with exchange-specific distribution

### Default Tables

All deployments include these 5 core tables:
- `tick` - Raw tick data with bid/ask/last prices
- `symbol` - Symbol metadata and configuration
- `minbar` - One-minute OHLCV bars
- `secbar` - One-second OHLCV bars
- `conf` - System configuration key-value store

## 🚀 Single-Node Setup

### Quick Start

```bash
# Start single-node Cassandra
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f cassandra

# Connect with cqlsh
docker exec -it tqdb-cassandra cqlsh
```

### Architecture

```
┌─────────────────────────┐
│  Single Cassandra Node  │
│  Port: 9042            │
├─────────────────────────┤
│  Keyspace: tqdb1       │
│  - tick                │
│  - symbol              │
│  - minbar              │
│  - secbar              │
│  - conf                │
└─────────────────────────┘
```

### Configuration

- **Keyspace**: `tqdb1`
- **Replication**: SimpleStrategy, RF=1
- **Heap Size**: 2GB max, 512MB new
- **CQL Port**: 9042
- **JMX Port**: 7199

### Usage

```bash
# Query example
docker exec -it tqdb-cassandra cqlsh -e "SELECT * FROM tqdb1.symbol LIMIT 10;"

# Stop
docker-compose down

# Stop and remove data
docker-compose down -v
```

## 🏗️ Multi-Node Cluster Setup

### Quick Start

```bash
# Start multi-node cluster
docker-compose -f docker-compose.cluster.yml up -d

# Check cluster status
docker exec -it tqdb-cassandra-master nodetool status

# View logs
docker-compose -f docker-compose.cluster.yml logs -f
```

### Architecture

```
┌───────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Master Node     │  │   NYSE Node      │  │  NASDAQ Node     │  │   HKEX Node      │
│   172.20.0.10     │  │   172.20.0.11    │  │   172.20.0.12    │  │   172.20.0.13    │
│   Port: 9042      │  │   Port: 9043     │  │   Port: 9044     │  │   Port: 9045     │
├───────────────────┤  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ tqdb_nyse         │  │ tqdb_nyse        │  │ tqdb_nasdaq      │  │ tqdb_hkex        │
│ tqdb_nasdaq       │  │                  │  │                  │  │                  │
│ tqdb_hkex         │  │                  │  │                  │  │                  │
└───────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Node Configuration

| Node | Container Name | IP | CQL Port | JMX Port | Keyspaces |
|------|----------------|-----|----------|----------|-----------|
| Master | tqdb-cassandra-master | 172.20.0.10 | 9042 | 7199 | ALL |
| NYSE | tqdb-cassandra-nyse | 172.20.0.11 | 9043 | 7200 | tqdb_nyse |
| NASDAQ | tqdb-cassandra-nasdaq | 172.20.0.12 | 9044 | 7201 | tqdb_nasdaq |
| HKEX | tqdb-cassandra-hkex | 172.20.0.13 | 9045 | 7202 | tqdb_hkex |

### Replication Strategy

- **Strategy**: NetworkTopologyStrategy
- **Replication Factor**: 2 (dc1:2)
- **Data Distribution**: Exchange-specific
- **Storage Savings**: ~33% vs full replication

### Usage

```bash
# Connect to master node
docker exec -it tqdb-cassandra-master cqlsh

# Connect to specific exchange node
docker exec -it tqdb-cassandra-nyse cqlsh

# Check cluster status
docker exec -it tqdb-cassandra-master nodetool status

# Check ring topology
docker exec -it tqdb-cassandra-master nodetool ring

# Stop cluster
docker-compose -f docker-compose.cluster.yml down

# Stop and remove all data
docker-compose -f docker-compose.cluster.yml down -v
```

## 📊 Schema Details

### Tick Table

```sql
CREATE TABLE tick (
    symbol text,
    datetime timestamp,
    keyval map<text, double>,  -- bid, ask, last, etc.
    type int,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);
```

**Usage**: Store raw tick data with bid/ask/last prices and volumes.

### Symbol Table

```sql
CREATE TABLE symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>  -- metadata: exchange, name, sector, etc.
);
```

**Usage**: Store symbol metadata and configuration.

### MinBar Table

```sql
CREATE TABLE minbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);
```

**Usage**: Store one-minute OHLCV bars.

### SecBar Table

```sql
CREATE TABLE secbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);
```

**Usage**: Store one-second OHLCV bars.

### Conf Table

```sql
CREATE TABLE conf (
    confKey text PRIMARY KEY,
    confVal text
);
```

**Usage**: Store system configuration as key-value pairs.

## 🔧 Operations

### Connecting with cqlsh

```bash
# Single-node
docker exec -it tqdb-cassandra cqlsh

# Multi-node (master)
docker exec -it tqdb-cassandra-master cqlsh

# Multi-node (specific exchange)
docker exec -it tqdb-cassandra-nyse cqlsh
```

### Inspecting Data

```bash
# List keyspaces
docker exec -it tqdb-cassandra cqlsh -e "DESCRIBE KEYSPACES;"

# Describe keyspace
docker exec -it tqdb-cassandra cqlsh -e "DESCRIBE KEYSPACE tqdb1;"

# Count records
docker exec -it tqdb-cassandra cqlsh -e "SELECT COUNT(*) FROM tqdb1.tick;"

# Sample query
docker exec -it tqdb-cassandra cqlsh -e "SELECT * FROM tqdb1.symbol LIMIT 10;"
```

### Monitoring

```bash
# Single-node status
docker exec -it tqdb-cassandra nodetool status

# Cluster status (multi-node)
docker exec -it tqdb-cassandra-master nodetool status

# Check data size
docker exec -it tqdb-cassandra nodetool tablestats tqdb1

# Monitor logs
docker-compose logs -f --tail=100 cassandra
```

### Backup and Restore

```bash
# Create snapshot
docker exec -it tqdb-cassandra nodetool snapshot tqdb1

# List snapshots
docker exec -it tqdb-cassandra nodetool listsnapshots

# Export data (CSV)
docker exec -it tqdb-cassandra cqlsh -e "COPY tqdb1.symbol TO '/tmp/symbol.csv';"
docker cp tqdb-cassandra:/tmp/symbol.csv ./backup/

# Import data (CSV)
docker cp ./backup/symbol.csv tqdb-cassandra:/tmp/
docker exec -it tqdb-cassandra cqlsh -e "COPY tqdb1.symbol FROM '/tmp/symbol.csv';"
```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs cassandra

# Check if port is already in use
netstat -tuln | grep 9042

# Remove old containers and volumes
docker-compose down -v
docker-compose up -d
```

### Schema Initialization Failed

```bash
# Check init container logs
docker-compose logs cassandra-init

# Manually run initialization
docker exec -it tqdb-cassandra cqlsh -f /docker-entrypoint-initdb.d/init-schema.cql

# For cluster setup
docker exec -it tqdb-cassandra-master cqlsh -f /scripts/init-cluster-schema.cql
```

### Cluster Nodes Can't Join

```bash
# Check network connectivity
docker exec -it tqdb-cassandra-nyse ping cassandra-master

# Check seed configuration
docker exec -it tqdb-cassandra-nyse nodetool gossipinfo

# Restart cluster in order
docker-compose -f docker-compose.cluster.yml restart cassandra-master
sleep 30
docker-compose -f docker-compose.cluster.yml restart cassandra-nyse cassandra-nasdaq cassandra-hkex
```

### Connection Refused

```bash
# Check if Cassandra is ready
docker exec -it tqdb-cassandra nodetool status

# Wait for startup (can take 60-90 seconds)
docker exec -it tqdb-cassandra cqlsh --connect-timeout=60

# Check health
docker-compose ps
```

### Slow Performance

```bash
# Check heap usage
docker exec -it tqdb-cassandra nodetool info

# Adjust heap size in docker-compose.yml
# MAX_HEAP_SIZE=4G
# HEAP_NEWSIZE=800M

# Restart with new settings
docker-compose down
docker-compose up -d
```

## 📝 Notes

### Single-Node vs Multi-Node

**Single-Node** (`docker-compose.yml`):
- ✅ Simple setup
- ✅ Development/testing
- ✅ Lower resource usage
- ❌ No high availability
- ❌ Limited scalability

**Multi-Node** (`docker-compose.cluster.yml`):
- ✅ High availability (RF=2)
- ✅ Exchange-specific distribution
- ✅ Storage efficiency (33% savings)
- ✅ Production ready
- ❌ Higher resource usage
- ❌ More complex setup

### Data Persistence

Data is stored in Docker volumes:
- Single-node: `cassandra_data`
- Multi-node: `cassandra_master_data`, `cassandra_nyse_data`, etc.

To completely remove data:
```bash
docker-compose down -v
```

### Resource Requirements

**Single-Node**:
- CPU: 2 cores minimum
- RAM: 4GB minimum (2GB heap + 2GB system)
- Disk: 20GB+ depending on data

**Multi-Node Cluster**:
- Master: 4 cores, 8GB RAM, 100GB+ disk
- Exchange nodes: 2 cores each, 4GB RAM each, 50GB+ disk each

### Network Configuration

The cluster uses a custom bridge network (172.20.0.0/16) with static IPs for stable inter-node communication.

To customize:
1. Edit `docker-compose.cluster.yml`
2. Update `ipv4_address` values
3. Restart cluster

## 🔗 Related Documentation

- [TQDB README](../README.md) - Project overview
- [DEPLOYMENT_GUIDE](../DEPLOYMENT_GUIDE.md) - Full deployment guide
- [OPERATIONS](../OPERATIONS.md) - Daily operations
- [Apache Cassandra Docs](https://cassandra.apache.org/doc/latest/)

---

**Version**: 1.0  
**Last Updated**: February 18, 2026

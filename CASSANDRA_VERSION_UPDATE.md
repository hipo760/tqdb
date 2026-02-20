# Cassandra Docker Configuration Update

## 📦 Version Update Summary

### Updated Version
- **From:** `cassandra:4.1` (generic 4.1 tag)
- **To:** `cassandra:4.1.10` (specific stable release)

### Why Update to 4.1.10?
1. **Stability:** Specific version tag for reproducible deployments
2. **Latest 4.x release:** 4.1.10 is the current stable release in the 4.1 line
3. **Production-ready:** Well-tested and widely used
4. **Security:** Includes latest security patches for 4.1.x

### Available Versions (as of Feb 2026)
```
cassandra:5.0.6   - Latest Cassandra 5.x (bleeding edge)
cassandra:4.1.10  - Latest Cassandra 4.1.x (✅ RECOMMENDED)
cassandra:4.0.19  - Latest Cassandra 4.0.x (older stable)
```

**Note:** We're using 4.1.10 for best balance of stability and features.

## 🔧 Environment Variables Updated

### Added Variables

Based on [Docker Hub Cassandra documentation](https://hub.docker.com/_/cassandra), added:

#### `CASSANDRA_LISTEN_ADDRESS=auto`
- **Purpose:** Controls which IP address Cassandra listens on for connections
- **Value:** `auto` - Automatically detects the container's IP
- **Default behavior:** Best for Docker environments
- **Cassandra config:** Sets `listen_address` in cassandra.yaml

### All Environment Variables Explained

| Variable | Purpose | Value | Required |
|----------|---------|-------|----------|
| `CASSANDRA_CLUSTER_NAME` | Cluster identifier | `tqdb_cluster` | ✅ Yes |
| `CASSANDRA_DC` | Datacenter name | `dc1` | ✅ Yes |
| `CASSANDRA_RACK` | Rack identifier | `rack1`, `rack2`, etc. | ✅ Yes |
| `CASSANDRA_ENDPOINT_SNITCH` | Topology strategy | `GossipingPropertyFileSnitch` | ✅ Yes |
| `CASSANDRA_NUM_TOKENS` | Virtual nodes | `256` | ✅ Yes |
| `CASSANDRA_SEEDS` | Seed node IPs | Comma-separated IPs | ✅ Yes |
| `CASSANDRA_BROADCAST_ADDRESS` | Advertised IP | Node's public IP | ✅ Yes |
| `CASSANDRA_LISTEN_ADDRESS` | Listen IP | `auto` (container IP) | ⭐ Added |
| `MAX_HEAP_SIZE` | JVM max heap | `2G`, `4G` | ⚠️ Recommended |
| `HEAP_NEWSIZE` | JVM new gen | `512M`, `800M` | ⚠️ Recommended |

## 📝 Files Updated

### 1. docker-compose.yml (Single-Node)
```yaml
services:
  cassandra:
    image: cassandra:4.1.10  # ✅ Updated from 4.1
    environment:
      - CASSANDRA_LISTEN_ADDRESS=auto  # ✅ Added
```

### 2. docker-compose.cluster.yml (Multi-Node)
```yaml
services:
  cassandra-master:
    image: cassandra:4.1.10  # ✅ Updated
    environment:
      - CASSANDRA_LISTEN_ADDRESS=auto  # ✅ Added
  
  cassandra-nyse:
    image: cassandra:4.1.10  # ✅ Updated
    environment:
      - CASSANDRA_LISTEN_ADDRESS=auto  # ✅ Added
  
  # ... same for cassandra-nasdaq, cassandra-hkex
```

### 3. docker-compose.main.yml (Two-Node Main)
```yaml
services:
  cassandra-main:
    image: cassandra:4.1.10  # ✅ Updated
    environment:
      - CASSANDRA_LISTEN_ADDRESS=auto  # ✅ Added
```

### 4. docker-compose.cme.yml (Two-Node CME)
```yaml
services:
  cassandra-cme:
    image: cassandra:4.1.10  # ✅ Updated
    environment:
      - CASSANDRA_LISTEN_ADDRESS=auto  # ✅ Added
```

## 🔍 Environment Variables Reference

### Core Configuration Variables

#### CASSANDRA_CLUSTER_NAME
```yaml
CASSANDRA_CLUSTER_NAME=tqdb_cluster
```
- **Purpose:** Identifies the cluster
- **Requirement:** Must be identical on all nodes
- **Cassandra config:** `cluster_name` in cassandra.yaml

#### CASSANDRA_SEEDS
```yaml
CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
```
- **Purpose:** Seed nodes for gossip protocol
- **Format:** Comma-separated IP addresses
- **Best practice:** List 2-3 seed nodes
- **Note:** The node's own broadcast address is automatically added

#### CASSANDRA_BROADCAST_ADDRESS
```yaml
CASSANDRA_BROADCAST_ADDRESS=192.168.1.10
```
- **Purpose:** IP address advertised to other nodes
- **Requirement:** Must be accessible from other nodes
- **Use case:** Essential for multi-machine deployments

#### CASSANDRA_LISTEN_ADDRESS
```yaml
CASSANDRA_LISTEN_ADDRESS=auto
```
- **Purpose:** IP address to listen for connections
- **Values:**
  - `auto` - Automatically detect container IP (recommended)
  - Specific IP - Bind to specific address
- **Default:** `auto` is best for Docker

### Topology Variables

#### CASSANDRA_DC and CASSANDRA_RACK
```yaml
CASSANDRA_DC=dc1
CASSANDRA_RACK=rack1
```
- **Purpose:** Define datacenter and rack topology
- **Requirement:** `CASSANDRA_ENDPOINT_SNITCH` must be `GossipingPropertyFileSnitch`
- **Cassandra config:** Sets in `cassandra-rackdc.properties`

#### CASSANDRA_ENDPOINT_SNITCH
```yaml
CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
```
- **Purpose:** Network topology strategy
- **Value:** `GossipingPropertyFileSnitch` for production clusters
- **Enables:** DC and Rack awareness

#### CASSANDRA_NUM_TOKENS
```yaml
CASSANDRA_NUM_TOKENS=256
```
- **Purpose:** Number of virtual nodes (vnodes)
- **Default:** 256 (recommended)
- **Benefit:** Better load distribution

### Memory Configuration

#### MAX_HEAP_SIZE and HEAP_NEWSIZE
```yaml
MAX_HEAP_SIZE=4G
HEAP_NEWSIZE=800M
```
- **Purpose:** JVM heap memory settings
- **Guideline:**
  - `HEAP_NEWSIZE` ≈ 20-25% of `MAX_HEAP_SIZE`
  - `MAX_HEAP_SIZE` ≤ 8GB (Cassandra recommendation)
  - Reserve 50% of RAM for OS page cache

**Memory Guidelines:**

| Total RAM | MAX_HEAP_SIZE | HEAP_NEWSIZE | Use Case |
|-----------|---------------|--------------|----------|
| 4 GB      | 2G            | 512M         | Dev/Light |
| 8 GB      | 4G            | 800M         | Production |
| 16 GB     | 6-8G          | 1200-1600M   | Heavy Load |

## 🚀 Migration Guide

### For Existing Deployments

#### Option 1: Pull and Restart (No Data Loss)

```bash
# Single-node
docker-compose pull
docker-compose down
docker-compose up -d

# Multi-node cluster
docker-compose -f docker-compose.cluster.yml pull
docker-compose -f docker-compose.cluster.yml down
docker-compose -f docker-compose.cluster.yml up -d

# Two-node (main)
docker-compose -f docker-compose.main.yml pull
docker-compose -f docker-compose.main.yml down
docker-compose -f docker-compose.main.yml up -d

# Two-node (CME)
docker-compose -f docker-compose.cme.yml pull
docker-compose -f docker-compose.cme.yml down
docker-compose -f docker-compose.cme.yml up -d
```

**Note:** Data is preserved in Docker volumes.

#### Option 2: Rolling Update (Zero Downtime)

For multi-node clusters:

```bash
# 1. Update one node at a time
docker-compose -f docker-compose.cluster.yml pull cassandra-nyse
docker-compose -f docker-compose.cluster.yml up -d cassandra-nyse

# 2. Wait for node to be UP
docker exec -it tqdb-cassandra-master nodetool status

# 3. Repeat for other nodes
docker-compose -f docker-compose.cluster.yml pull cassandra-nasdaq
docker-compose -f docker-compose.cluster.yml up -d cassandra-nasdaq

# Continue for remaining nodes...
```

### For New Deployments

Simply use the updated compose files - they're ready to go!

```bash
# Single-node
docker-compose up -d

# Multi-node
docker-compose -f docker-compose.cluster.yml up -d

# Two-node
docker-compose -f docker-compose.main.yml up -d  # On main server
docker-compose -f docker-compose.cme.yml up -d   # On CME server
```

## 🔒 Version Pinning Benefits

### Why Use 4.1.10 Instead of 4.1?

| Tag | Behavior | Pros | Cons |
|-----|----------|------|------|
| `cassandra:4.1` | Tracks latest 4.1.x | Auto-updates | Version drift, unexpected changes |
| `cassandra:4.1.10` | Fixed version | Reproducible, predictable | Manual updates needed |

**Recommendation:** Use specific version (4.1.10) for production.

## 📚 References

### Official Documentation
- **Docker Hub:** https://hub.docker.com/_/cassandra
- **Cassandra Docs:** https://cassandra.apache.org/doc/4.1/
- **GitHub:** https://github.com/docker-library/cassandra

### Environment Variables Reference
- **Listen Address:** https://cassandra.apache.org/doc/latest/cassandra/configuration/cass_yaml_file.html#listen_address
- **Broadcast Address:** https://cassandra.apache.org/doc/latest/cassandra/configuration/cass_yaml_file.html#broadcast_address
- **Seeds:** https://cassandra.apache.org/doc/latest/cassandra/configuration/cass_yaml_file.html#seed_provider

## ✅ Verification

### Check Version After Update

```bash
# Check image version
docker images | grep cassandra

# Check running version
docker exec -it tqdb-cassandra cqlsh -e "SHOW VERSION"
docker exec -it tqdb-cassandra nodetool version

# Check environment
docker exec -it tqdb-cassandra env | grep CASSANDRA
```

### Expected Output

```bash
$ docker images | grep cassandra
cassandra  4.1.10  <image-id>  160MB

$ docker exec -it tqdb-cassandra nodetool version
ReleaseVersion: 4.1.10
```

## 🎯 Summary

### Changes Made
1. ✅ Updated image tag: `cassandra:4.1` → `cassandra:4.1.10`
2. ✅ Added `CASSANDRA_LISTEN_ADDRESS=auto` to all services
3. ✅ Verified all environment variables match Docker Hub documentation
4. ✅ Updated all compose files (single-node, multi-node, two-node)

### Benefits
- 🔒 Version pinning for reproducible deployments
- 📊 Latest stable 4.1.x release
- 🎯 Optimized listen address configuration
- 📚 Fully documented environment variables

### Next Steps
- Review updated compose files
- Test in development environment
- Deploy to production with confidence

---

**Version:** 1.1  
**Last Updated:** February 18, 2026  
**Cassandra Version:** 4.1.10

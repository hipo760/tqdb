# TQDB Two-Node Cassandra Cluster Deployment Guide

## 🎯 Overview

This guide covers deploying a two-node Cassandra cluster across two separate machines:
- **Main Node** - Stores ALL exchange data (seed node)
- **CME Node** - Stores ONLY CME exchange data

## 📋 Architecture

```
┌─────────────────────────────┐          ┌─────────────────────────────┐
│     Main Server             │          │     CME Server              │
│  (e.g., 192.168.1.10)       │          │  (e.g., 192.168.1.11)       │
├─────────────────────────────┤          ├─────────────────────────────┤
│  tqdb-cassandra-main        │◄────────►│  tqdb-cassandra-cme         │
│  Port: 9042 (CQL)           │          │  Port: 9042 (CQL)           │
│  Port: 7000 (Inter-node)    │          │  Port: 7000 (Inter-node)    │
│  Port: 7199 (JMX)           │          │  Port: 7199 (JMX)           │
├─────────────────────────────┤          ├─────────────────────────────┤
│  Keyspace: tqdb_cme         │          │  Keyspace: tqdb_cme         │
│  - tick                     │          │  - tick                     │
│  - symbol                   │          │  - symbol                   │
│  - minbar                   │          │  - minbar                   │
│  - secbar                   │          │  - secbar                   │
│  - conf                     │          │  - conf                     │
└─────────────────────────────┘          └─────────────────────────────┘
    SEED NODE (stores all)                  DATA NODE (stores CME only)
```

## 🔧 Prerequisites

### Both Servers
1. Docker 20.10+ installed
2. Docker Compose 2.0+ installed
3. Network connectivity between servers
4. Open firewall ports (see below)

### Firewall Requirements

On **both servers**, open these ports:

```bash
# CQL native protocol
sudo firewall-cmd --permanent --add-port=9042/tcp

# Inter-node cluster communication
sudo firewall-cmd --permanent --add-port=7000/tcp
sudo firewall-cmd --permanent --add-port=7001/tcp

# JMX monitoring
sudo firewall-cmd --permanent --add-port=7199/tcp

# Thrift (optional, legacy)
sudo firewall-cmd --permanent --add-port=9160/tcp

# Reload firewall
sudo firewall-cmd --reload
```

For Ubuntu/Debian (using ufw):
```bash
sudo ufw allow 9042/tcp
sudo ufw allow 7000/tcp
sudo ufw allow 7001/tcp
sudo ufw allow 7199/tcp
sudo ufw allow 9160/tcp
sudo ufw reload
```

## 📦 Installation Steps

### Step 1: Prepare Main Server

1. **Copy files to main server:**
   ```bash
   # On main server
   cd /opt/tqdb
   
   # Copy these files:
   # - docker-compose.main.yml
   # - cluster-init-scripts/init-main-schema.cql
   ```

2. **Configure environment file (optional):**
   ```bash
   # Create .env file
   cat > .env << 'EOF'
   MAIN_SERVER_IP=192.168.1.10
   CASSANDRA_CLUSTER_NAME=tqdb_cluster
   MAX_HEAP_SIZE=4G
   HEAP_NEWSIZE=800M
   EOF
   ```

3. **Update main node configuration:**
   ```bash
   # Edit docker-compose.main.yml
   # Replace CASSANDRA_SEEDS with actual IPs (both nodes for better fault tolerance)
   sed -i 's/CASSANDRA_SEEDS=cassandra-main/CASSANDRA_SEEDS=192.168.1.10,192.168.1.11/g' docker-compose.main.yml
   sed -i 's/CASSANDRA_BROADCAST_ADDRESS=cassandra-main/CASSANDRA_BROADCAST_ADDRESS=192.168.1.10/g' docker-compose.main.yml
   ```

### Step 2: Prepare CME Server

1. **Copy files to CME server:**
   ```bash
   # On CME server
   cd /opt/tqdb
   
   # Copy these files:
   # - docker-compose.cme.yml
   ```

2. **Update CME node configuration:**
   ```bash
   # Edit docker-compose.cme.yml
   # Replace placeholders with actual IPs (both nodes for better fault tolerance)
   sed -i 's/<MAIN_SERVER_IP>,<CME_SERVER_IP>/192.168.1.10,192.168.1.11/g' docker-compose.cme.yml
   sed -i 's/CASSANDRA_BROADCAST_ADDRESS=cassandra-cme/CASSANDRA_BROADCAST_ADDRESS=192.168.1.11/g' docker-compose.cme.yml
   ```

### Step 3: Deploy Main Node First

```bash
# On main server
cd /opt/tqdb

# Start main node
docker-compose -f docker-compose.main.yml up -d

# Wait for main node to be fully ready (60-90 seconds)
docker-compose -f docker-compose.main.yml logs -f cassandra-main

# Check health
docker exec -it tqdb-cassandra-main nodetool status

# Verify schema initialization
docker-compose -f docker-compose.main.yml logs cassandra-main-init
```

### Step 4: Deploy CME Node

```bash
# On CME server
cd /opt/tqdb

# Start CME node
docker-compose -f docker-compose.cme.yml up -d

# Wait for CME node to join cluster (90-120 seconds)
docker-compose -f docker-compose.cme.yml logs -f cassandra-cme

# Check health
docker exec -it tqdb-cassandra-cme nodetool status
```

### Step 5: Verify Cluster

**On main server:**
```bash
# Check cluster status
docker exec -it tqdb-cassandra-main nodetool status

# Expected output:
# Datacenter: dc1
# ===============
# Status=Up/Down
# |/ State=Normal/Leaving/Joining/Moving
# --  Address         Load       Tokens  Owns    Host ID                               Rack
# UN  192.168.1.10    123.45 KB  256     100.0%  <uuid>                                rack1
# UN  192.168.1.11    98.76 KB   256     100.0%  <uuid>                                rack2

# Check keyspace replication
docker exec -it tqdb-cassandra-main cqlsh -e "DESCRIBE KEYSPACE tqdb_cme;"

# Verify data distribution
docker exec -it tqdb-cassandra-main nodetool ring
```

**On CME server:**
```bash
# Check cluster status from CME node
docker exec -it tqdb-cassandra-cme nodetool status

# Should show both nodes as UN (Up/Normal)
```

## 🔍 Configuration Details

### Main Node Configuration

Key environment variables in `docker-compose.main.yml`:

```yaml
environment:
  - CASSANDRA_CLUSTER_NAME=tqdb_cluster       # Must match on all nodes
  - CASSANDRA_DC=dc1                          # Datacenter name
  - CASSANDRA_RACK=rack1                      # Rack for main node
  - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11 # Both nodes for fault tolerance
  - CASSANDRA_BROADCAST_ADDRESS=192.168.1.10  # IP of main server
  - MAX_HEAP_SIZE=4G                          # Adjust based on RAM
  - HEAP_NEWSIZE=800M                         # ~20% of MAX_HEAP_SIZE
```

### CME Node Configuration

Key environment variables in `docker-compose.cme.yml`:

```yaml
environment:
  - CASSANDRA_CLUSTER_NAME=tqdb_cluster       # Must match on all nodes
  - CASSANDRA_DC=dc1                          # Same datacenter as main
  - CASSANDRA_RACK=rack2                      # Different rack from main
  - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11 # Both nodes for fault tolerance
  - CASSANDRA_BROADCAST_ADDRESS=192.168.1.11  # IP of CME server
  - MAX_HEAP_SIZE=2G                          # Adjust based on RAM
  - HEAP_NEWSIZE=512M                         # ~20% of MAX_HEAP_SIZE
```

### Network Topology Strategy

The cluster uses `NetworkTopologyStrategy` with `replication_factor=2`:
- Data is replicated to both nodes
- Provides high availability
- Allows queries on either node

**Important:** With RF=2, the cluster can tolerate one node failure:
- If main node goes down, CME node continues working (with consistency level ONE)
- If CME node goes down, main node continues working
- See [FAULT_TOLERANCE.md](FAULT_TOLERANCE.md) for detailed behavior

## 📊 Operations

### Starting the Cluster

```bash
# Start main node first
ssh main-server "cd /opt/tqdb && docker-compose -f docker-compose.main.yml up -d"

# Wait 60 seconds, then start CME node
sleep 60
ssh cme-server "cd /opt/tqdb && docker-compose -f docker-compose.cme.yml up -d"
```

### Stopping the Cluster

```bash
# Stop CME node first
ssh cme-server "cd /opt/tqdb && docker-compose -f docker-compose.cme.yml down"

# Then stop main node
ssh main-server "cd /opt/tqdb && docker-compose -f docker-compose.main.yml down"
```

### Restarting a Node

```bash
# Restart main node
ssh main-server "cd /opt/tqdb && docker-compose -f docker-compose.main.yml restart"

# Restart CME node
ssh cme-server "cd /opt/tqdb && docker-compose -f docker-compose.cme.yml restart"
```

### Monitoring

```bash
# Check cluster health (from either node)
docker exec -it tqdb-cassandra-main nodetool status

# Check node info
docker exec -it tqdb-cassandra-main nodetool info

# Monitor logs
docker-compose -f docker-compose.main.yml logs -f --tail=100

# Check data size
docker exec -it tqdb-cassandra-main nodetool tablestats tqdb_cme
```

### Querying Data

```bash
# Connect to main node
docker exec -it tqdb-cassandra-main cqlsh

# Connect to CME node
docker exec -it tqdb-cassandra-cme cqlsh

# Query from either node (Cassandra routes automatically)
cqlsh> SELECT * FROM tqdb_cme.symbol LIMIT 10;
cqlsh> SELECT COUNT(*) FROM tqdb_cme.tick;
```

## 🐛 Troubleshooting

### Nodes Can't See Each Other

1. **Check network connectivity:**
   ```bash
   # From main server
   ping 192.168.1.11
   telnet 192.168.1.11 7000
   
   # From CME server
   ping 192.168.1.10
   telnet 192.168.1.10 7000
   ```

2. **Check firewall:**
   ```bash
   # Verify ports are open
   sudo firewall-cmd --list-ports
   ```

3. **Check Docker network:**
   ```bash
   docker exec -it tqdb-cassandra-cme ping 192.168.1.10
   ```

### CME Node Won't Join Cluster

1. **Check seed configuration:**
   ```bash
   # Verify CASSANDRA_SEEDS points to main server IP
   docker exec -it tqdb-cassandra-cme env | grep CASSANDRA_SEEDS
   ```

2. **Check cluster name:**
   ```bash
   # Must match on both nodes
   docker exec -it tqdb-cassandra-main nodetool describecluster
   docker exec -it tqdb-cassandra-cme nodetool describecluster
   ```

3. **Check logs:**
   ```bash
   docker-compose -f docker-compose.cme.yml logs cassandra-cme | grep -i error
   ```

4. **Restart CME node:**
   ```bash
   docker-compose -f docker-compose.cme.yml down
   sleep 10
   docker-compose -f docker-compose.cme.yml up -d
   ```

### Schema Not Replicating

1. **Check replication settings:**
   ```bash
   docker exec -it tqdb-cassandra-main cqlsh -e "DESCRIBE KEYSPACE tqdb_cme;"
   ```

2. **Verify both nodes are UP:**
   ```bash
   docker exec -it tqdb-cassandra-main nodetool status
   # Both nodes should show UN (Up/Normal)
   ```

3. **Manual repair:**
   ```bash
   docker exec -it tqdb-cassandra-main nodetool repair tqdb_cme
   ```

### Connection Timeout

1. **Increase startup time:**
   ```yaml
   # In docker-compose files, adjust:
   healthcheck:
     start_period: 180s  # Increase from 90s/120s
   ```

2. **Check Cassandra is running:**
   ```bash
   docker exec -it tqdb-cassandra-main nodetool status
   ```

3. **Wait longer:**
   ```bash
   # Cassandra can take 2-3 minutes to fully start
   sleep 180
   ```

## 🔐 Security Considerations

### Production Recommendations

1. **Enable authentication:**
   ```yaml
   environment:
     - CASSANDRA_AUTHENTICATOR=PasswordAuthenticator
   ```

2. **Enable SSL/TLS:**
   - Generate certificates
   - Configure `cassandra.yaml`
   - Mount certificates as volumes

3. **Restrict network access:**
   ```bash
   # Only allow specific IPs
   sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="9042" protocol="tcp" accept'
   ```

4. **Use Docker secrets for sensitive data**

## 📈 Performance Tuning

### Heap Size Guidelines

| RAM Available | MAX_HEAP_SIZE | HEAP_NEWSIZE |
|---------------|---------------|--------------|
| 8 GB          | 2-3 GB        | 512 MB       |
| 16 GB         | 4-6 GB        | 800 MB       |
| 32 GB         | 8-12 GB       | 1.6 GB       |

### Disk Performance

- Use SSD for better performance
- Separate data and commit log to different disks if possible

### Network Optimization

- Use 1 Gbps or faster network
- Minimize network latency between nodes

## 🔄 Adding More Exchange Nodes

To add more exchange nodes (NYSE, NASDAQ, etc.):

1. Create new compose file (e.g., `docker-compose.nyse.yml`)
2. Change hostname and rack (e.g., `rack3`)
3. Point `CASSANDRA_SEEDS` to main server IP
4. Add exchange-specific keyspace to schema
5. Deploy on new server

Example:
```yaml
services:
  cassandra-nyse:
    hostname: cassandra-nyse
    environment:
      - CASSANDRA_RACK=rack3
      - CASSANDRA_SEEDS=192.168.1.10  # Main server
```

## 📝 Maintenance

### Backup

```bash
# Create snapshot on both nodes
docker exec -it tqdb-cassandra-main nodetool snapshot tqdb_cme
docker exec -it tqdb-cassandra-cme nodetool snapshot tqdb_cme

# Copy snapshots
docker cp tqdb-cassandra-main:/var/lib/cassandra/data/tqdb_cme ./backup/main/
docker cp tqdb-cassandra-cme:/var/lib/cassandra/data/tqdb_cme ./backup/cme/
```

### Upgrade

```bash
# Upgrade CME node first
ssh cme-server "cd /opt/tqdb && docker-compose -f docker-compose.cme.yml pull && docker-compose -f docker-compose.cme.yml up -d"

# Wait and verify
sleep 60
docker exec -it tqdb-cassandra-cme nodetool status

# Then upgrade main node
ssh main-server "cd /opt/tqdb && docker-compose -f docker-compose.main.yml pull && docker-compose -f docker-compose.main.yml up -d"
```

## 📚 Related Documentation

- [DOCKER_CASSANDRA.md](DOCKER_CASSANDRA.md) - Single-node setup
- [README.md](README.md) - Project overview
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Full deployment guide
- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/)

---

**Version**: 1.0  
**Last Updated**: February 18, 2026

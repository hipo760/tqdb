# TQDB Two-Node Cluster Setup

## 📁 Files Created

This setup provides a two-node Cassandra cluster that can be deployed across two separate machines:

### Docker Compose Files
- **docker-compose.main.yml** - Main node (seed node, stores all data)
- **docker-compose.cme.yml** - CME exchange node (stores CME data only)

### Schema Files
- **cluster-init-scripts/init-main-schema.cql** - Schema initialization for main node

### Documentation
- **DOCKER_CLUSTER_DEPLOYMENT.md** - Complete deployment guide
- **cluster.env.template** - Configuration template
- **deploy-cluster.sh** - Interactive deployment helper script

## 🚀 Quick Start

### Option 1: Using the Helper Script (Recommended)

```bash
# Make script executable
chmod +x deploy-cluster.sh

# Run interactive deployment
./deploy-cluster.sh
```

The script will guide you through:
1. Configure Main Node
2. Configure CME Node  
3. Deploy Main Node
4. Deploy CME Node
5. Check Cluster Status

### Option 2: Manual Deployment

#### On Main Server (e.g., 192.168.1.10)

```bash
# 1. Update configuration
sed -i 's/CASSANDRA_SEEDS=cassandra-main/CASSANDRA_SEEDS=192.168.1.10,192.168.1.11/g' docker-compose.main.yml
sed -i 's/CASSANDRA_BROADCAST_ADDRESS=cassandra-main/CASSANDRA_BROADCAST_ADDRESS=192.168.1.10/g' docker-compose.main.yml

# 2. Deploy
docker-compose -f docker-compose.main.yml up -d

# 3. Wait for main node to be ready
sleep 60

# 4. Check status
docker exec -it tqdb-cassandra-main nodetool status
```

#### On CME Server (e.g., 192.168.1.11)

```bash
# 1. Update configuration
sed -i 's/<MAIN_SERVER_IP>,<CME_SERVER_IP>/192.168.1.10,192.168.1.11/g' docker-compose.cme.yml
sed -i 's/CASSANDRA_BROADCAST_ADDRESS=cassandra-cme/CASSANDRA_BROADCAST_ADDRESS=192.168.1.11/g' docker-compose.cme.yml

# 2. Deploy
docker-compose -f docker-compose.cme.yml up -d

# 3. Wait for CME node to join cluster
sleep 90

# 4. Check status
docker exec -it tqdb-cassandra-cme nodetool status
```

## 📊 Architecture

```
Main Server (192.168.1.10)          CME Server (192.168.1.11)
┌──────────────────────────┐       ┌──────────────────────────┐
│  tqdb-cassandra-main     │◄─────►│  tqdb-cassandra-cme      │
│  (Seed Node)             │       │                          │
│                          │       │                          │
│  Keyspace: tqdb_cme      │       │  Keyspace: tqdb_cme      │
│  RF=2 (stores all)       │       │  RF=2 (stores CME only)  │
└──────────────────────────┘       └──────────────────────────┘
```

## 🔧 Configuration

### Required Changes Before Deployment

1. **Main Node** (`docker-compose.main.yml`):
   - Replace `cassandra-main` with actual IPs: `192.168.1.10,192.168.1.11`
   - Update `CASSANDRA_SEEDS` (both nodes for fault tolerance)
   - Update `CASSANDRA_BROADCAST_ADDRESS` (this node's IP)

2. **CME Node** (`docker-compose.cme.yml`):
   - Replace `<MAIN_SERVER_IP>,<CME_SERVER_IP>` with: `192.168.1.10,192.168.1.11`
   - Update `CASSANDRA_BROADCAST_ADDRESS` with CME server IP: `192.168.1.11`

### Firewall Ports to Open (Both Servers)

```bash
# Required ports
9042  # CQL native protocol
7000  # Inter-node communication
7001  # TLS inter-node communication
7199  # JMX monitoring
```

## 📋 Tables

Each node has the `tqdb_cme` keyspace with these tables:
- **tick** - Raw tick data
- **symbol** - Symbol metadata
- **minbar** - One-minute OHLCV bars
- **secbar** - One-second OHLCV bars
- **conf** - Configuration key-value store

## 🔍 Verification

```bash
# Check cluster status (run on either node)
docker exec -it tqdb-cassandra-main nodetool status

# Expected output:
# UN  192.168.1.10  (main node)
# UN  192.168.1.11  (CME node)

# Query data (works from either node)
docker exec -it tqdb-cassandra-main cqlsh -e "SELECT * FROM tqdb_cme.symbol LIMIT 10;"
docker exec -it tqdb-cassandra-cme cqlsh -e "SELECT * FROM tqdb_cme.symbol LIMIT 10;"
```

## 🛠️ Common Operations

### Start/Stop

```bash
# Start (main server)
docker-compose -f docker-compose.main.yml up -d

# Start (CME server)
docker-compose -f docker-compose.cme.yml up -d

# Stop (CME server first)
docker-compose -f docker-compose.cme.yml down

# Stop (main server)
docker-compose -f docker-compose.main.yml down
```

### Monitoring

```bash
# View logs
docker-compose -f docker-compose.main.yml logs -f
docker-compose -f docker-compose.cme.yml logs -f

# Check node info
docker exec -it tqdb-cassandra-main nodetool info
docker exec -it tqdb-cassandra-cme nodetool info

# Check data size
docker exec -it tqdb-cassandra-main nodetool tablestats tqdb_cme
```

### Backup

```bash
# Create snapshot
docker exec -it tqdb-cassandra-main nodetool snapshot tqdb_cme
docker exec -it tqdb-cassandra-cme nodetool snapshot tqdb_cme

# Copy snapshot data
docker cp tqdb-cassandra-main:/var/lib/cassandra/data/tqdb_cme ./backup/
```

## 🐛 Troubleshooting

### Nodes Can't Connect

1. Check firewall ports are open
2. Verify IP addresses in configuration
3. Test connectivity: `ping` and `telnet` between servers
4. Check Docker logs: `docker-compose logs -f`

### CME Node Won't Join

1. Ensure main node is fully running first (wait 60-90s)
2. Verify `CASSANDRA_SEEDS` points to main server IP
3. Check cluster name matches on both nodes
4. Restart CME node: `docker-compose -f docker-compose.cme.yml restart`

## 📚 Documentation

- **DOCKER_CLUSTER_DEPLOYMENT.md** - Detailed deployment guide
- **DOCKER_CASSANDRA.md** - Single-node setup documentation
- **README.md** - Project overview

## 💡 Tips

1. **Always deploy main node first**, wait 60-90 seconds
2. **Verify main node is healthy** before deploying CME node
3. **Use static IPs** for production deployments
4. **Adjust heap size** based on available RAM
5. **Monitor logs** during first deployment
6. **Configure both nodes as seeds** for better fault tolerance

## 🛡️ Fault Tolerance

- **Exchange node CAN work if main node is down** (with consistency level ONE)
- **Main node CAN work if exchange node is down**
- Automatic recovery via hinted handoff when nodes rejoin
- See [FAULT_TOLERANCE.md](FAULT_TOLERANCE.md) for detailed analysis

## 🔐 Production Considerations

- Enable authentication (`PasswordAuthenticator`)
- Configure SSL/TLS for inter-node communication
- Use firewall rules to restrict access
- Regular backups using snapshots
- Monitor cluster health with JMX/nodetool

---

**Version**: 1.0  
**Last Updated**: February 18, 2026

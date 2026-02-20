# CHANGELOG - Cassandra Docker Configuration

## [1.1.0] - February 18, 2026

### 🎯 Summary
Updated all Cassandra Docker Compose configurations based on official Docker Hub documentation. Pinned to stable version 4.1.10 and added recommended environment variables.

### 📦 Version Updates

#### Changed
- **Cassandra Image Version**
  - From: `cassandra:4.1` (floating tag - auto-updates to latest 4.1.x)
  - To: `cassandra:4.1.10` (pinned - specific stable release)
  - Reason: Ensures reproducible deployments and prevents unexpected version changes

**All Files Updated:**
- ✅ `docker-compose.yml` - Single-node development setup
- ✅ `docker-compose.cluster.yml` - Multi-node production cluster
- ✅ `docker-compose.main.yml` - Two-node main server
- ✅ `docker-compose.cme.yml` - Two-node CME exchange server

### 🔧 Environment Variables

#### Added
- **`CASSANDRA_LISTEN_ADDRESS=auto`**
  - Purpose: Configures which IP address Cassandra listens on for incoming connections
  - Value: `auto` - Automatically detects container's IP address
  - Benefit: Best practice for Docker deployments
  - Added to: All compose files (main nodes and exchange nodes)

#### Verified Existing Variables
All existing environment variables verified against [Docker Hub documentation](https://hub.docker.com/_/cassandra):

| Variable | Status | Purpose |
|----------|--------|---------|
| `CASSANDRA_CLUSTER_NAME` | ✅ Correct | Cluster identifier |
| `CASSANDRA_DC` | ✅ Correct | Datacenter name |
| `CASSANDRA_RACK` | ✅ Correct | Rack topology |
| `CASSANDRA_ENDPOINT_SNITCH` | ✅ Correct | Topology strategy |
| `CASSANDRA_NUM_TOKENS` | ✅ Correct | Virtual nodes (256) |
| `CASSANDRA_SEEDS` | ✅ Correct | Seed node IPs |
| `CASSANDRA_BROADCAST_ADDRESS` | ✅ Correct | Advertised IP |
| `MAX_HEAP_SIZE` | ✅ Correct | JVM max heap |
| `HEAP_NEWSIZE` | ✅ Correct | JVM new generation |

### 📄 Files Changed

```
docker-compose.yml
├─ cassandra: 4.1 → 4.1.10
└─ cassandra-init: 4.1 → 4.1.10

docker-compose.cluster.yml
├─ cassandra-master: 4.1 → 4.1.10
├─ cassandra-nyse: 4.1 → 4.1.10
├─ cassandra-nasdaq: 4.1 → 4.1.10
├─ cassandra-hkex: 4.1 → 4.1.10
└─ cassandra-cluster-init: 4.1 → 4.1.10

docker-compose.main.yml
├─ cassandra-main: 4.1 → 4.1.10
└─ cassandra-main-init: 4.1 → 4.1.10

docker-compose.cme.yml
└─ cassandra-cme: 4.1 → 4.1.10
```

### 📚 Documentation Added

#### New Documentation Files
- **`CASSANDRA_VERSION_UPDATE.md`**
  - Complete update documentation
  - Environment variables reference
  - Migration guide for existing deployments
  - Version pinning benefits

### 🔍 Breaking Changes
**None** - These are backward-compatible updates:
- Version 4.1.10 is compatible with 4.1.x
- `CASSANDRA_LISTEN_ADDRESS=auto` is the default behavior
- Existing deployments will continue to work

### 🚀 Migration Path

#### For Existing Deployments
```bash
# Pull new images
docker-compose pull

# Restart with new version (data preserved in volumes)
docker-compose down
docker-compose up -d
```

#### For New Deployments
No changes needed - compose files are ready to use!

### 📊 Impact

#### Benefits
1. **Stability**: Pinned version prevents unexpected updates
2. **Reproducibility**: Same version across all environments
3. **Best Practices**: Uses recommended Docker configuration
4. **Documentation**: Comprehensive guide for all variables

#### What Hasn't Changed
- Data model and schema
- Table structures
- Replication strategies
- Network configuration
- Port mappings
- Volume mounts
- Fault tolerance behavior

### 🔗 References

- **Docker Hub Cassandra**: https://hub.docker.com/_/cassandra
- **Cassandra 4.1 Docs**: https://cassandra.apache.org/doc/4.1/
- **Release Notes**: https://cassandra.apache.org/doc/4.1/new/

### 📝 Notes

#### Why Cassandra 4.1.10?
- ✅ Latest stable release in 4.1.x line
- ✅ Production-ready with bug fixes and security patches
- ✅ Well-tested in the community
- ❌ Not using 5.x yet (too new, wait for wider adoption)

#### Environment Variable: CASSANDRA_LISTEN_ADDRESS
- **Default**: `auto` - Best for most Docker deployments
- **Alternative**: Specific IP - Only needed for advanced networking
- **Official Recommendation**: Use `auto` unless you have specific requirements

### ✅ Verification

After updating, verify the configuration:

```bash
# Check image version
docker images | grep cassandra

# Should show: cassandra  4.1.10

# Check running version
docker exec -it tqdb-cassandra nodetool version

# Should show: ReleaseVersion: 4.1.10

# Check environment
docker exec -it tqdb-cassandra env | grep CASSANDRA_LISTEN_ADDRESS

# Should show: CASSANDRA_LISTEN_ADDRESS=auto
```

### 🎯 Compatibility Matrix

| Component | Version | Status |
|-----------|---------|--------|
| Cassandra | 4.1.10 | ✅ Updated |
| Docker Compose | 3.8 | ✅ Current |
| CQL Protocol | 4 | ✅ Supported |
| Python Driver | 3.x | ✅ Compatible |
| Java Driver | 4.x | ✅ Compatible |

---

**Prepared by**: TQDB Infrastructure Team  
**Date**: February 18, 2026  
**Review Status**: ✅ Verified against Docker Hub documentation

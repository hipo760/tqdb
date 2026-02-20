# TQDB Schema Files - Version Guide

## 📁 Schema File Organization

This directory contains CQL schema files for different Cassandra versions.

### Directory Structure

```
init-scripts/
├── init-schema.cql        # Cassandra 5.0 (current/default)
└── init-schema-v4.cql     # Cassandra 4.x (legacy)

cluster-init-scripts/
├── init-cluster-schema.cql     # Cassandra 5.0 (current/default)
├── init-main-schema.cql        # Cassandra 5.0 (current/default)
├── init-cluster-schema-v4.cql  # Cassandra 4.x (legacy)
└── init-main-schema-v4.cql     # Cassandra 4.x (legacy)
```

## 🎯 Which Schema Should I Use?

### For New Deployments (Recommended)
✅ **Use Cassandra 5.0 schemas** (default `.cql` files)
- Better performance
- Modern features
- Future-proof

### For Legacy Systems
⚠️ **Use Cassandra 4.x schemas** (`-v4.cql` files)
- Compatible with existing Rocky Linux 9 installations
- Safe for upgrading from Cassandra 3.x
- Proven stability

## 📊 Schema Comparison

### Cassandra 5.0 Schema Features

| Feature | Cassandra 4.x | Cassandra 5.0 | Benefit |
|---------|---------------|---------------|---------|
| Timestamp Function | `toTimestamp(now())` | `currentTimestamp()` | Modern API |
| TWCS Configuration | Minimal | Explicit params | Better performance |
| gc_grace_seconds | Default (10 days) | 1 day for time-series | Faster cleanup |
| DURABLE_WRITES | Implicit | Explicit | Clear configuration |
| Compaction Details | Basic | Full specification | Optimized for workload |

### Key Differences

#### 1. Timestamp Functions
```cql
-- Cassandra 4.x:
INSERT INTO conf VALUES ('created_at', toTimestamp(now()));

-- Cassandra 5.0:
INSERT INTO conf VALUES ('created_at', currentTimestamp());
```

#### 2. Compaction Strategy
```cql
-- Cassandra 4.x (minimal):
WITH compaction = {'class': 'TimeWindowCompactionStrategy'}

-- Cassandra 5.0 (optimized):
WITH compaction = {
    'class': 'TimeWindowCompactionStrategy',
    'compaction_window_size': '1',
    'compaction_window_unit': 'DAYS',
    'timestamp_resolution': 'MICROSECONDS'
}
```

#### 3. Keyspace Options
```cql
-- Cassandra 4.x:
CREATE KEYSPACE tqdb1 WITH REPLICATION = {...};

-- Cassandra 5.0 (explicit):
CREATE KEYSPACE tqdb1 WITH REPLICATION = {...}
AND DURABLE_WRITES = true;
```

#### 4. Time-Series Tables
```cql
-- Cassandra 5.0 adds:
AND gc_grace_seconds = 86400  -- 1 day instead of 10 days default
```

## 🚀 Usage Instructions

### Single-Node Deployment

#### Using Cassandra 5.0 (Default)
```yaml
# docker-compose.yml
services:
  cassandra:
    image: cassandra:5.0.6
    volumes:
      - ./init-scripts:/docker-entrypoint-initdb.d
```
Will automatically use `init-schema.cql` (Cassandra 5.0)

#### Using Cassandra 4.x (Legacy)
```yaml
# docker-compose.yml
services:
  cassandra:
    image: cassandra:4.1.10
    volumes:
      - ./init-scripts:/docker-entrypoint-initdb.d
    command: >
      bash -c "
        cp /docker-entrypoint-initdb.d/init-schema-v4.cql /docker-entrypoint-initdb.d/init-schema.cql;
        docker-entrypoint.sh cassandra -f
      "
```

### Multi-Node Cluster Deployment

#### Using Cassandra 5.0 (Default)
```yaml
# docker-compose.cluster.yml
services:
  cassandra-master:
    image: cassandra:5.0.6
    volumes:
      - ./cluster-init-scripts:/docker-entrypoint-initdb.d
```
Will automatically use `init-cluster-schema.cql` (Cassandra 5.0)

#### Using Cassandra 4.x (Legacy)
```yaml
# docker-compose.cluster.yml
services:
  cassandra-master:
    image: cassandra:4.1.10
    volumes:
      - ./cluster-init-scripts:/docker-entrypoint-initdb.d
    environment:
      - CASSANDRA_INIT_SCRIPT=init-cluster-schema-v4.cql
```

### Two-Node Deployment (Main + CME)

#### Using Cassandra 5.0 (Default)
```yaml
# docker-compose.main.yml
services:
  cassandra-main:
    image: cassandra:5.0.6
    volumes:
      - ./cluster-init-scripts:/docker-entrypoint-initdb.d
```
Will automatically use `init-main-schema.cql` (Cassandra 5.0)

## 🔄 Migration Guide

### From Cassandra 4.x to 5.0

#### Option 1: Fresh Installation (Recommended)
```bash
# 1. Use Cassandra 5.0 schemas (default)
docker-compose -f docker-compose.yml up -d

# Schema is automatically initialized with Cassandra 5.0
```

#### Option 2: Migrate Existing Data
```bash
# 1. Backup existing data
docker exec tqdb-cassandra nodetool snapshot tqdb1

# 2. Export data
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.tick TO '/backup/tick.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.symbol TO '/backup/symbol.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.minbar TO '/backup/minbar.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.secbar TO '/backup/secbar.csv'"

# 3. Deploy Cassandra 5.0
docker-compose down
# Update docker-compose.yml to use cassandra:5.0.6
docker-compose up -d

# 4. Wait for Cassandra to be ready
sleep 60

# 5. Import data (schema auto-created)
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.tick FROM '/backup/tick.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.symbol FROM '/backup/symbol.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.minbar FROM '/backup/minbar.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.secbar FROM '/backup/secbar.csv'"
```

## 📋 Schema Validation

### Verify Cassandra 5.0 Schema

```bash
# Connect to Cassandra
docker exec -it tqdb-cassandra cqlsh

# Check keyspace
DESCRIBE KEYSPACE tqdb1;

# Verify compaction strategy
SELECT keyspace_name, table_name, compaction 
FROM system_schema.tables 
WHERE keyspace_name='tqdb1';

# Check configuration
SELECT * FROM tqdb1.conf;

# Should show cassandra_version = '5.0'
```

### Verify Cassandra 4.x Schema

```bash
docker exec -it tqdb-cassandra cqlsh

# Check configuration
SELECT * FROM tqdb1.conf;

# Will NOT have cassandra_version field (or will show '4.1')
```

## 🎓 Best Practices

### 1. **Use Cassandra 5.0 for New Projects**
- Better performance
- Modern features
- Future-proof

### 2. **Keep v4 Schemas for Legacy Systems**
- Required for migrating from Cassandra 3.x
- Compatible with Rocky Linux 9 bare-metal installations
- Safe fallback option

### 3. **Don't Mix Versions in a Cluster**
- All nodes must run the same major version
- Use v4 schemas for 4.x clusters
- Use v5 schemas for 5.x clusters

### 4. **Test Migration in Development First**
```bash
# Always test with a copy of production data
docker-compose -f docker-compose.test.yml up -d
# Test schema migration
# Verify application compatibility
# Then deploy to production
```

## 📚 References

- [Cassandra 5.0 Release Notes](https://cassandra.apache.org/doc/5.0/)
- [Cassandra 4.1 Documentation](https://cassandra.apache.org/doc/4.1/)
- [CQL Changes in 5.0](https://cassandra.apache.org/doc/5.0/new/index.html)
- [Migration Guide](https://cassandra.apache.org/doc/latest/operating/upgrade.html)

## 🆘 Troubleshooting

### Error: "Unknown function 'toTimestamp'"
```
InvalidRequest: Error from server: code=2200 [Invalid query] 
message="Unknown function 'toTimestamp'"
```
**Solution:** You're using a v4 schema with Cassandra 5.0. Use the v5 schema instead.

### Error: "Unknown function 'currentTimestamp'"
```
InvalidRequest: Error from server: code=2200 [Invalid query] 
message="Unknown function 'currentTimestamp'"
```
**Solution:** You're using a v5 schema with Cassandra 4.x. Use the v4 schema instead.

### How to Switch Between Versions

#### Switch to Cassandra 4.x
```bash
cd init-scripts
rm init-schema.cql
ln -s init-schema-v4.cql init-schema.cql
```

#### Switch to Cassandra 5.0
```bash
cd init-scripts
# Remove symlink if it exists
rm init-schema.cql
# Recreate with v5 content (already done if you're using default)
```

## ✅ Version Verification

### Check Your Current Schema Version

```bash
# Method 1: Check conf table
docker exec tqdb-cassandra cqlsh -e "SELECT confVal FROM tqdb1.conf WHERE confKey='cassandra_version';"

# Method 2: Check Cassandra version
docker exec tqdb-cassandra nodetool version

# Method 3: Check schema file in use
docker exec tqdb-cassandra ls -la /docker-entrypoint-initdb.d/
```

## 📊 Summary Table

| Schema File | Cassandra Version | Status | Use Case |
|-------------|-------------------|--------|----------|
| `init-schema.cql` | 5.0.6 | ✅ Current | New deployments |
| `init-schema-v4.cql` | 4.1.10 | ⚠️ Legacy | Existing systems |
| `init-cluster-schema.cql` | 5.0.6 | ✅ Current | New clusters |
| `init-cluster-schema-v4.cql` | 4.1.10 | ⚠️ Legacy | Existing clusters |
| `init-main-schema.cql` | 5.0.6 | ✅ Current | New two-node |
| `init-main-schema-v4.cql` | 4.1.10 | ⚠️ Legacy | Existing two-node |

---

**Last Updated:** February 18, 2026  
**Default Version:** Cassandra 5.0.6  
**Legacy Support:** Cassandra 4.1.10

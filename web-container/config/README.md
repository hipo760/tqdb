# Configuration Files

Configuration files for the TQDB web container.

## Files

### `apache.conf`
Apache VirtualHost configuration:
- CGI script execution
- Static file serving
- Environment variable pass-through
- Security headers

Deployed to: `/etc/apache2/sites-available/tqdb.conf`

### `entrypoint.sh`
Container startup script:
- Cassandra health check
- Environment display
- Apache initialization

Deployed to: `/usr/local/bin/entrypoint.sh`

### `init-schema.cql`
Cassandra schema definition:
- Keyspace: `tqdb1`
- Tables: `symbol`, `tick`, `secbar`, `minbar`, `conf`

**Load schema**:
```bash
docker exec -i cassandra-node cqlsh < init-schema.cql
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CASSANDRA_HOST` | `cassandra-node` | Cassandra hostname |
| `CASSANDRA_PORT` | `9042` | CQL port |
| `CASSANDRA_KEYSPACE` | `tqdb1` | Keyspace name |
| `TOOLS_DIR` | `/opt/tqdb/tools` | Tools directory |
| `TZ` | `UTC` | Timezone |

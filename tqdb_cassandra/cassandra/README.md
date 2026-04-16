# TQDB Cassandra Container

Single-node Cassandra setup for TQDB using Cassandra 4.1.10.

## Files

- `docker-compose.yml`: Cassandra service definition
- `init-schema.cql`: Canonical schema for Cassandra 4.1.10
- `cassandra.yaml`: Optional custom Cassandra config
- `data/`: Persistent data directory

## Quick Start

```bash
cd /home/hank/services/tqdb/tqdb_cassandra/cassandra
docker compose up -d
```

## Apply Schema To Existing Running Container

Use this after `docker compose up -d` when the container already exists.

1. Wait for Cassandra to become healthy:

```bash
docker compose ps
```

2. Apply schema from host file into the running container:

```bash
docker exec -i tqdb-cassandra cqlsh -u tqdb -p tqdb1234 < init-schema.cql
```

3. Verify keyspace and tables:

```bash
docker exec -it tqdb-cassandra cqlsh -u tqdb -p tqdb1234 -e "DESCRIBE KEYSPACE tqdb1"
```

Notes:
- The schema uses `IF NOT EXISTS`, so re-applying is safe.
- Default credentials are for development only.
- If you changed container name or credentials in `docker-compose.yml`, update the command accordingly.

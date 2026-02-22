# TQDB Cassandra

The Cassandra-based implementation of TQDB (Time-series Quote Database). Stores and serves financial market data — ticks, second bars, minute bars, and daily bars — using Apache Cassandra as the time-series backend and Apache HTTP Server with Python CGI as the API layer.

## Directory Structure

```
tqdb_cassandra/
├── cassandra/                  # Cassandra database container
│   ├── docker-compose.yml      # Single-node Cassandra service
│   ├── init-schema.cql         # Schema for Cassandra 5.0 (SimpleStrategy)
│   ├── init-schema-v4.cql      # Schema for Cassandra 4.x
│   ├── cassandra.yaml          # Custom Cassandra configuration
│   └── data/                   # Persistent data volume (gitignored)
│
├── web/                        # Web API container
│   ├── Dockerfile              # Container image (Apache + Python 3.11 CGI)
│   ├── docker-compose.yml      # Web service with Cassandra network attachment
│   ├── cgi-bin/                # Python CGI endpoint scripts
│   ├── html/                   # Static HTML/CSS/JS front-end
│   ├── python-binaries/        # Python replacements for legacy C++ binaries
│   ├── scripts/                # Data import and processing scripts
│   └── config/                 # Apache config, entrypoint, and init schema
│
├── tools/                      # Python data management tools
│   ├── transfer_minbar.py      # Migrate minbar data between Cassandra instances
│   ├── example_transfer.sh     # Example migration script
│   └── pyproject.toml          # uv-managed Python 3.11 project
│
└── archive/                    # Historical installation guides
    ├── CENTOS7_INSTALL.md
    └── ROCKY9_INSTALL.md
```

## Components

### 1. Cassandra Database (`cassandra/`)

Single-node Apache Cassandra instance for storing time-series market data.

**Tables:**

| Table | Description |
|-------|-------------|
| `tqdb1.tick` | Raw tick data with bid/ask/last prices |
| `tqdb1.secbar` | 1-second OHLCV bars |
| `tqdb1.minbar` | 1-minute OHLCV bars |
| `tqdb1.daybar` | Daily OHLCV bars |
| `tqdb1.symbol` | Symbol metadata |

**Quick Start:**

```bash
cd cassandra/
docker compose up -d

# Initialize schema (once Cassandra is healthy)
docker exec -i tqdb-cassandra cqlsh -u tqdb -p tqdb1234 < init-schema.cql
```

> ⚠️ **Security Note:** The default credentials (`tqdb` / `tqdb1234`) in `docker-compose.yml` are for development only. Change them before deploying to production and update all downstream services accordingly.

### 2. Web API (`web/`)

Apache 2.4 + Python 3.11 CGI container exposing the TQDB HTTP API on port **2380**.

**Key Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `/cgi-bin/q1min.py` | Query 1-minute OHLCV bars |
| `/cgi-bin/q1sec.py` | Query 1-second bars |
| `/cgi-bin/q1day.py` | Query daily bars |
| `/cgi-bin/qsymbol.py` | List available symbols |
| `/cgi-bin/qsyminfo.py` | Symbol metadata |
| `/cgi-bin/qRange.py` | Query data over a time range |
| `/cgi-bin/eData.py` | Import data |
| `/cgi-bin/eConf.py` | Edit configuration |

See [`web/README.md`](web/README.md) for full endpoint documentation and deployment instructions.

**Quick Start:**

```bash
# Cassandra must be running first (see above)
cd web/
docker compose up -d

# Verify
curl "http://localhost:2380/cgi-bin/qsymbol.py"
```

### 3. Tools (`tools/`)

Python CLI tools for Cassandra data management. Uses [`uv`](https://github.com/astral-sh/uv) for environment management.

**Setup:**

```bash
cd tools/
uv sync
```

**Transfer minbar data between Cassandra instances:**

```bash
# Transfer specific symbols
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --symbols AAPL,GOOGL,MSFT

# Transfer all symbols
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --all-symbols
```

See [`tools/README.md`](tools/README.md) for full usage and options.

## Deployment Order

Services must be started in this order:

```
1. cassandra/    →  docker compose up -d
2. web/          →  docker compose up -d   (waits for Cassandra automatically)
```

Both services share the external Docker network `cassandra_tqdb_network`, created by the Cassandra compose file.

## Archive

The `archive/` directory contains bare-metal installation guides for legacy deployments:

- [`CENTOS7_INSTALL.md`](archive/CENTOS7_INSTALL.md) — CentOS 7 installation
- [`ROCKY9_INSTALL.md`](archive/ROCKY9_INSTALL.md) — Rocky Linux 9 installation

These are kept for reference; **Docker-based deployment is the recommended approach.**

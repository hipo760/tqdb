# TQDB — Time-series Quote Database

TQDB is a financial market data storage and query system. It ingests, stores, and serves tick, second-bar, minute-bar, and daily-bar data for equities, futures, and crypto instruments.

The repository contains two independent backend implementations and a crypto data collector:

| Folder | Description |
|--------|-------------|
| [`tqdb_cassandra/`](#tqdb_cassandra) | **Production** — Apache Cassandra + Apache CGI API |
| [`tqdb_questdb/`](#tqdb_questdb) | **Next-gen** — QuestDB + FastAPI (migration in progress) |
| [`crypto/`](#crypto) | Bybit kline backfill service |

---

## tqdb_cassandra

The original, production-ready implementation.

- **Database**: Apache Cassandra 4.1 / 5.0 (single-node, Docker)
- **API**: Apache 2.4 + Python 3.11 CGI on port **2380**
- **Data model**: `tick`, `secbar`, `minbar`, `daybar`, `symbol` tables in keyspace `tqdb1`

**Sub-components:**

| Path | Purpose |
|------|---------|
| `tqdb_cassandra/cassandra/` | Cassandra Docker container & schema |
| `tqdb_cassandra/web/` | Web API Docker container (CGI endpoints + HTML UI) |
| `tqdb_cassandra/tools/` | Python CLI for data migration between Cassandra instances |
| `tqdb_cassandra/archive/` | Bare-metal install guides (CentOS 7, Rocky 9) |

**Quick start:**

```bash
# 1. Start the database
cd tqdb_cassandra/cassandra
docker compose up -d

# 2. Start the web API (waits for Cassandra automatically)
cd ../web
docker compose up -d

# 3. Verify
curl "http://localhost:2380/cgi-bin/qsymbol.py"
```

See [`tqdb_cassandra/README.md`](tqdb_cassandra/README.md) for full documentation.

---

## tqdb_questdb

A modernised replacement for the Cassandra stack, currently under development.

- **Database**: [QuestDB](https://questdb.io/) (high-performance time-series)
- **API**: FastAPI with OpenAPI docs; **100% backward-compatible** CGI endpoints
- **Performance**: 10–100× faster queries than the Cassandra implementation

See [`tqdb_questdb/README.md`](tqdb_questdb/README.md) and [`tqdb_questdb/docs/MIGRATION_PLAN.md`](tqdb_questdb/docs/MIGRATION_PLAN.md) for the migration guide.

---

## crypto

Bybit cryptocurrency kline backfill service. Keeps the `tqdb1.minbar` Cassandra table up-to-date with Bybit 1-minute OHLCV data.

- Runs two scheduled jobs: **minutely** (patch last 2 min) and **daily** (patch last N days at UTC 00:00)
- Exposes a REST API (`/sync/manual`, `/sync/symbol/:symbol`, etc.) for ad-hoc syncs
- Configuration via `.env` file (see `.env.example`)

**Quick start:**

```bash
cd crypto/bybit
cp .env.example .env
# Edit .env with your Cassandra credentials and symbol API token
docker compose up -d
```

See [`crypto/bybit/backfill/README.md`](crypto/bybit/backfill/README.md) for full API reference.

---

## Repository Layout

```
tqdb/
├── tqdb_cassandra/         # Cassandra-based backend (production)
│   ├── cassandra/          #   Database container & schema
│   ├── web/                #   CGI web API container
│   ├── tools/              #   Data migration CLI
│   └── archive/            #   Legacy bare-metal install guides
│
├── tqdb_questdb/           # QuestDB-based backend (next-gen)
│   ├── questdb/            #   Database container & schema
│   ├── web/                #   FastAPI web container (WIP)
│   └── docs/               #   Migration plan & API reference
│
├── crypto/                 # Crypto data collector
│   └── bybit/              #   Bybit kline backfill service
│       ├── backfill/       #     Backfill worker & API
│       ├── .env.example    #     Configuration template
│       └── docker-compose.yml
│
├── temp/                   # CGI URL compatibility reference files
└── .gitignore
```

---

## Security Notes

- **`crypto/bybit/.env`** and **`crypto/bybit/config.json`** contain API credentials and are excluded from version control via `.gitignore`. Use `.env.example` as a template.
- The default Cassandra credentials (`tqdb` / `tqdb1234`) in the Docker Compose files are intended for **development only**. Replace them with strong credentials before any production deployment.

---

## License

See [LICENSE](LICENSE).

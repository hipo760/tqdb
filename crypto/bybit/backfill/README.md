# Bybit Kline Backfill Service

Containerised service that keeps Cassandra `minbar` table in sync with
Bybit 1-minute kline data.

## Jobs

| Job | Schedule | What it does |
|-----|----------|--------------|
| **minutely** | every minute | Smart-patch the last **2 minutes** for all symbols |
| **daily** | UTC 00:00 | Smart-patch the last **N days** (default 3) for all symbols |

Both jobs use _smart_ mode: they query Cassandra first and only fetch
bars that are genuinely missing (gap-fill).

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness probe |
| `POST` | `/sync/manual` | Trigger a full sync over a custom window |
| `POST` | `/sync/symbol/{symbol}` | Sync a single symbol |
| `POST` | `/sync/minutely` | Manually fire the minutely job |
| `POST` | `/sync/daily` | Manually fire the daily job |

Interactive docs: `http://localhost:8765/docs`

### Example — manual sync

```bash
# Smart patch last 7 days for all symbols
curl -X POST http://localhost:8765/sync/manual \
  -H 'Content-Type: application/json' \
  -d '{"mode": "smart", "days": 7}'

# Override a specific window for one symbol
curl -X POST http://localhost:8765/sync/symbol/BTCUSDT \
  -H 'Content-Type: application/json' \
  -d '{"mode": "override", "start_time": "2026-02-01T00:00:00Z", "end_time": "2026-02-22T00:00:00Z"}'
```

## Configuration

Copy `.env.example` to `.env` and fill in your values.

| Variable | Default | Description |
|----------|---------|-------------|
| `CASSANDRA_HOST` | `cassandra` | Cassandra hostname |
| `CASSANDRA_PORT` | `9042` | Cassandra port |
| `CASSANDRA_USER` | _(empty)_ | Auth username |
| `CASSANDRA_PASSWORD` | _(empty)_ | Auth password |
| `CASSANDRA_KEYSPACE` | `tqdb1` | Keyspace |
| `CASSANDRA_TABLE` | `minbar` | Table name |
| `SYMBOL_SOURCE` | `api` | `api` or `file` |
| `SYMBOL_API_URL` | _(empty)_ | Symbol list endpoint |
| `SYMBOL_API_TOKEN` | _(empty)_ | Bearer token for symbol API |
| `DAILY_BACKFILL_DAYS` | `3` | Days patched by the daily job |
| `BACKFILL_API_PORT` | `8765` | Host port for the API |
| `SYMBOLS_FILE` | _(empty)_ | Host path to `symbols.json` (when `SYMBOL_SOURCE=file`) |

## Running

```bash
cd crypto/bybit

# First time or after dependency changes
docker compose build

# Start
docker compose up -d

# Logs
docker compose logs -f bybit-kline-backfill
```

## File structure

```
crypto/bybit/
├── http_client.py               # Shared HTTP helper (used by backfill)
├── docker-compose.yml
├── .env.example
└── backfill/
    ├── main.py                  # Entrypoint — uvicorn + APScheduler
    ├── api.py                   # FastAPI routes
    ├── jobs.py                  # minutely_job / daily_job
    ├── kline_sync.py            # Core sync logic (gap-fill, override)
    ├── cassandra_client.py      # Session factory (reads env vars)
    ├── symbols.py               # Symbol list fetching
    ├── pyproject.toml
    ├── uv.lock
    ├── Dockerfile
    └── .dockerignore
```

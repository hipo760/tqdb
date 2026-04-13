# Project Guidelines

## Scope
This repository has three independent components:
- `tqdb_cassandra/`: production stack (Cassandra + Apache CGI API)
- `tqdb_questdb/`: next-gen stack (QuestDB + FastAPI, migration in progress)
- `crypto/bybit/`: Bybit kline backfill service writing to Cassandra

When implementing changes, keep work scoped to the relevant component and avoid cross-component assumptions.

## Build and Test
Use component-local commands and run from the component directory.

- Cassandra stack:
  - `cd tqdb_cassandra/cassandra && docker compose up -d`
  - `cd tqdb_cassandra/web && docker compose up -d`
- Cassandra tools:
  - `cd tqdb_cassandra/tools && uv sync`
  - `cd tqdb_cassandra/tools && uv run transfer_minbar.py --help`
- Crypto backfill service:
  - `cd crypto/bybit && docker compose build && docker compose up -d`
- QuestDB stack:
  - `cd tqdb_questdb/web && docker-compose up -d`

If tests exist for a touched area, run the smallest relevant test scope first before broad runs.

## Conventions
- Python 3.11 is the baseline across active services and tools.
- Prefer `uv` workflows where `pyproject.toml` is present (`tqdb_cassandra/tools`, `crypto/bybit/backfill`).
- Legacy API compatibility matters:
  - Existing clients depend heavily on `/cgi-bin/q1min.py`, `/cgi-bin/q1sec.py`, and `/cgi-bin/qsyminfo.py`.
  - Preserve legacy query parameter behavior for `symbol`, `BEG`, and `END` when modifying compatibility layers.
- Keep timestamps/timezone handling in UTC unless a file explicitly requires otherwise.

## Operational Gotchas
- Start order matters for Cassandra stack: start `tqdb_cassandra/cassandra` before `tqdb_cassandra/web`.
- `tqdb_cassandra/web` depends on external Docker network `cassandra_tqdb_network` created by the Cassandra compose project.
- Default credentials in compose files are development defaults only; do not introduce new hardcoded secrets.
- Large symbol migrations can require year partitioning to avoid timeouts. See the linked feature note below.

## Architecture References
Use these docs as source of truth; link to them in discussions/PR notes instead of duplicating details.

- `README.md`
- `tqdb_cassandra/README.md`
- `tqdb_cassandra/web/README.md`
- `tqdb_cassandra/tools/README.md`
- `tqdb_cassandra/tools/YEAR_PARTITION_FEATURE.md`
- `tqdb_cassandra/archive/BUG_FIX_SYMBOL_LIST.md`
- `crypto/bybit/backfill/README.md`
- `tqdb_questdb/README.md`
- `tqdb_questdb/docs/QUICKSTART.md`
- `tqdb_questdb/docs/LEGACY_API_REFERENCE.md`
- `tqdb_questdb/docs/MIGRATION_PLAN.md`

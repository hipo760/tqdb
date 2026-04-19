# Continuous Symbols (TXDT / TXON)

This document explains how the TAIFEX continuous futures symbols are implemented in the Cassandra web stack.

## Overview

Two synthetic symbols are provided:

- `TXDT`: day-session continuous symbol
- `TXON`: overnight-session continuous symbol

These symbols are view-like. No new data is copied into Cassandra. Data is composed at request time from existing TXF contract symbols (for example `TXFE6`).

## Data Source

Continuous composition reads minute bars from table `tqdb1.minbar`.

- Underlying symbol format: `TXF` + month code + year digit
- Example: contract month `202605` maps to `TXFE6`

Month code mapping:

- `A`=01, `B`=02, `C`=03, `D`=04, `E`=05, `F`=06
- `G`=07, `H`=08, `I`=09, `J`=10, `K`=11, `L`=12

## Roll and Schedule Rules

Implementation source file: `tqdb_cassandra/web/cgi-bin/continuous_symbols.py`.

Rules:

- Contract universe is built from year range `Y-1 .. Y`.
- Last trading day is based on the third Wednesday of contract month.
- If third Wednesday is a weekend or holiday, shift forward to next trading day.
- Holidays are loaded from CSV file:
  - `/opt/tqdb/feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv`
  - or path from `TAIFEX_HOLIDAY_CSV` environment variable

Session windows (Taiwan time, UTC+8):

- `TXDT`: `08:45` to `13:45`
- `TXON`: `08:45` to next day `05:00`

Session and rollover comparison:

| Symbol | Meaning | Session (UTC+8) | Cross-day Session | Contract Rollover Point (UTC+8) |
|---|---|---|---|---|
| TXDT | DT = day trade | 08:45 to 13:45 | No | Last trading day 08:45 (old contract ends 08:44, new starts 08:45) |
| TXON | ON = overnight (cross session) | 08:45 to next day 05:00 | Yes | Last trading day 13:45 |

Rollover rule:

- `TXDT` contract switch point is at last trading day `08:45` (UTC+8).
- In code, each TXDT segment starts at previous contract last trading day `08:45` and ends at current contract last trading day `08:44`.
- `TXON` contract switch point is at last trading day `13:45` (UTC+8).
- In code, each TXON segment starts at previous contract last trading day `13:45` and ends at current contract last trading day `13:45`.

API output timestamps are UTC.

## Endpoints

### 1) Metadata endpoint

- `GET /cgi-bin/qContinuousSymbolInfo.py`

Returns available start/end range for `TXON` and `TXDT`, based on actual data found in underlying TXF symbols.

Example response shape:

```json
{
  "symbols": [
    {
      "symbol": "TXON",
      "start": "2026-01-02 07:00:00",
      "end": "2026-04-19 20:59:00"
    },
    {
      "symbol": "TXDT",
      "start": "2026-01-02 00:45:00",
      "end": "2026-04-19 05:45:00"
    }
  ]
}
```

### 2) Minute query endpoint

- `GET /cgi-bin/q1min.py?symbol=TXDT&BEG=...&END=...`
- `GET /cgi-bin/q1min.py?symbol=TXON&BEG=...&END=...`

When `symbol` is `TXDT` or `TXON`, `q1min.py` composes rows from the mapped TXF contracts during query time.

## UI Page

- `GET /csymbol.html`

Page behavior:

- Calls `/cgi-bin/qContinuousSymbolInfo.py` to show range for each symbol.
- Shows `Symbol`, `Start (UTC)`, `End (UTC)`, and query button.
- Query button opens `q1min.py` for last five days ending at the latest available timestamp.

## Operations

### Deploy/refresh

If CGI or HTML files are updated in image build context:

```bash
cd tqdb_cassandra/web
docker compose build
docker compose up -d
```

### Verify holiday CSV in container

```bash
docker compose exec tqdb-web ls -lh /opt/tqdb/feature-custom-symbol/TAIFEX/taifex_holidays_sample.csv
```

### Quick checks

```bash
curl http://localhost:2380/cgi-bin/qContinuousSymbolInfo.py
curl "http://localhost:2380/cgi-bin/q1min.py?symbol=TXDT&BEG=2026-04-14%2000:00:00&END=2026-04-19%2000:00:00"
```

## Troubleshooting

- `start`/`end` is `null`:
  - Check underlying TXF symbols exist in `minbar`.
  - Confirm month symbol format is `TXF<monthCode><yearDigit>`.
- Holiday load failure:
  - Confirm CSV path exists in container.
  - Set `TAIFEX_HOLIDAY_CSV` if using custom path.
- CGI 500 errors:
  - Check Apache error log in container:
    `docker compose exec tqdb-web tail -n 200 /var/log/apache2/error.log`

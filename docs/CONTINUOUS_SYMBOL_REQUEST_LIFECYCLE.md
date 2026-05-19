# Continuous Symbol Request Lifecycle

Detailed walkthrough of the `q1min.py` code path when the requested symbol is a
**continuous future** (e.g. `TXDT`, `NQDT`, `ESDT`, `TXON`).

Continuous symbols are synthetic, view-like instruments. No pre-composed data is
stored in Cassandra. Every request triggers on-the-fly composition from the
underlying monthly contract bars with backward close-to-close price adjustment.

---

## Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant q1min as q1min.py (CGI)
    participant InstrAPI as Instrument API<br/>(INSTRUMENT_API_BASE_URL)
    participant continuous as continuous_symbols.py<br/>compose_continuous_minbars()
    participant Cassandra

    Client->>q1min: HTTP GET /cgi-bin/q1min.py<br/>?symbol=TXDT&BEG=2026-01-02 00:45:00&END=2026-05-19 13:45:00

    activate q1min
    Note over q1min: parse_query_parameters()<br/>normalize_symbol() / normalize_date_format()

    Note over q1min: is_continuous_symbol(symbol)<br/>→ calls fetch_continuous_futures(symbol)

    q1min->>InstrAPI: GET /intra/instrument/continuous_futures?symbol=TXDT
    InstrAPI-->>q1min: [{symbol: "TXDT", symbol_root: "TXF", ...}]

    Note over q1min: bool(rows) == True → is_continuous_symbol = True

    Note over q1min: process_continuous_symbol()<br/>connect Cluster([CASSANDRA_HOST])

    q1min->>continuous: compose_continuous_minbars(<br/>session, keyspace, "TXDT", begin_dt, end_dt)
    activate continuous

    %% Step 1 – resolve symbol_root
    continuous->>InstrAPI: GET /intra/instrument/continuous_futures?symbol=TXDT
    InstrAPI-->>continuous: [{symbol_root: "TXF", ...}]

    %% Step 2 – fetch rollover schedule
    continuous->>InstrAPI: GET /intra/instrument/contract_rollover_dt?symbol=TXDT
    InstrAPI-->>continuous: [{contract: "202601", rollover_date: "2026-01-21",<br/>rollover_time: "08:45", timezone: 8}, ...]

    Note over continuous: _build_rollover_schedule()<br/>_rollover_entry_to_utc() per entry<br/>→ sorted [(switch_utc, "TXFA6"), (switch_utc, "TXFB6"), ...]

    Note over continuous: _schedule_to_raw_segments()<br/>→ [(start, end, "TXFA6"), (start, end, "TXFB6"), ...]<br/>last segment end = FAR_FUTURE

    %% Step 4a – compute per-pair diffs across ALL segments
    Note over continuous: _compute_switch_diffs() — iterate ALL consecutive pairs
    Note over continuous: close_datetimes_utc[i] = rollover_date[i] + close_time<br/>converted from IANA timezone to UTC

    loop for each pair i → i+1 where close_dt ≤ now_utc
        Note over continuous: close_dt = close_datetimes_utc[i+1]<br/>(market close on rollover_date of segment i+1)
        continuous->>Cassandra: SELECT close FROM minbar<br/>WHERE symbol='TXFA6' AND datetime ≤ close_dt<br/>ORDER BY datetime DESC LIMIT 1
        Cassandra-->>continuous: close_before (float or None)
        continuous->>Cassandra: SELECT close FROM minbar<br/>WHERE symbol='TXFB6' AND datetime ≤ close_dt<br/>ORDER BY datetime DESC LIMIT 1
        Cassandra-->>continuous: close_after (float or None)
        Note over continuous: diff[i] = close_after − close_before<br/>(None if either price unavailable)
    end

    Note over continuous: _cumulative_offsets(diffs)<br/>offset[N-1] = 0 (newest segment = reference)<br/>offset[i] = offset[i+1] + diff[i] (backward accumulation)

    %% Step 5 – fetch bars for overlapping segments only
    loop for each segment overlapping [begin_dt, end_dt]
        Note over continuous: query_begin = max(seg_start, begin_dt)<br/>query_end   = min(seg_end,   end_dt)
        continuous->>Cassandra: SELECT datetime, open, high, low, close, vol<br/>FROM minbar WHERE symbol='TXF??' AND<br/>datetime BETWEEN query_begin AND query_end<br/>ORDER BY datetime
        Cassandra-->>continuous: raw OHLCV rows

        Note over continuous: apply price offset shift to all OHLC values<br/>(O+shift, H+shift, L+shift, C+shift)
    end

    Note over continuous: sort all bars by datetime<br/>deduplicate on timestamp

    continuous-->>q1min: []bars (dt, O, H, L, C, V) — price-adjusted, merged
    deactivate continuous

    Note over q1min: write_bars_to_tmp_file()<br/>→ /tmp/q1min.<pid>.<epoch>[.gz]<br/>format: YYYYMMDD,HHMMSS,O,H,L,C,V

    Note over q1min: cluster.shutdown()

    Note over q1min: output_response_data()

    alt gzip mode (default)
        q1min-->>Client: Content-Encoding: gzip<br/>Content-Type: text/plain<br/>[binary .gz body]
    else csv=1
        q1min-->>Client: Content-Type: text/csv<br/>Content-Disposition: attachment<br/>YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol header<br/>[plain text CSV body]
    end

    Note over q1min: remove tmpfile

    deactivate q1min
```

---

## Instrument API calls

| Call | Endpoint | Purpose |
|---|---|---|
| `is_continuous_symbol()` check | `GET /intra/instrument/continuous_futures?symbol=<sym>` | Confirm the symbol is registered as a continuous future |
| Resolve `symbol_root` | `GET /intra/instrument/continuous_futures?symbol=<sym>` | Determine base root (e.g. `TXF`, `NQ`) for contract code construction |
| Fetch rollover schedule | `GET /intra/instrument/contract_rollover_dt?symbol=<sym>` | Full ordered list of contract months + rollover datetimes |

The API is called **twice** for `continuous_futures` (once during the guard check in
`q1min.py`, once inside `compose_continuous_minbars`).

---

## Cassandra query pattern

### Price-adjustment lookback (one pair per settled switch point)

```sql
SELECT close FROM {keyspace}.minbar
WHERE symbol = '<contract>' AND datetime <= '<close_dt>'
ORDER BY datetime DESC LIMIT 1
```

`close_dt` = `rollover_date[i+1]` + `close_time` (HHmm from `continuous_futures`) converted
from the symbol's IANA timezone to UTC.  Run for both `before_symbol` and `after_symbol`
only when `now_utc >= close_dt` (market has closed on rollover day).
Results feed `_compute_switch_diffs()` → `_cumulative_offsets()`.

### Bar data fetch (per overlapping segment)

```sql
SELECT datetime, open, high, low, close, vol FROM {keyspace}.minbar
WHERE symbol = '<contract>' AND datetime >= '<query_begin>' AND datetime <= '<query_end>'
ORDER BY datetime
```

Only segments whose `[seg_start, seg_end]` window intersects `[begin_dt, end_dt]`
are queried. Historical segments outside the request window still contribute to the
price-offset computation but are not fetched for bar data.

---

## Price adjustment algorithm

```
offset[N-1] = 0                          # newest settled segment: reference, no shift
offset[i]   = offset[i+1] + diff[i]     # propagate backward
diff[i]     = close(new_contract, close_dt) − close(old_contract, close_dt)
close_dt    = rollover_date[i+1] + close_time  (HHmm, IANA tz → UTC)
```

- All offsets are computed across **all** segments (not just those in the query range),
  so the price level is always anchored to the latest settled front month.
- A diff is only computed when `now_utc >= close_dt` — the market has definitively
  closed on rollover day. Unsettled pairs keep `diff[i] = None` (treated as `0`).
- When either close price is unavailable (no data), `diff[i]` is treated as `0`
  (no adjustment at that switch point).
- `close_time` and its IANA `timezone` come from the `continuous_futures` API row
  (symbol-level fields, same for all contracts of that symbol).

---

## Segment structure example (TXDT, 3 contracts)

```
Index  Contract  seg_start (UTC)      seg_end (UTC)        offset
  0    TXFA6     2025-12-18 00:45     2026-01-21 00:44     +cumulative
  1    TXFB6     2026-01-21 00:45     2026-02-18 00:44     +smaller
  2    TXFC6     2026-02-18 00:45     FAR_FUTURE (9999)    0 (reference)
```

For a request of `BEG=2026-01-15 … END=2026-03-01`:
- Segments 0, 1, and 2 overlap the range → 3 bar-data queries.
- All 3 lookback diffs are computed (switch points 0→1 and 1→2 are in the past).

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `INSTRUMENT_API_BASE_URL` | *(required)* | Base URL of the Instrument API |
| `INSTRUMENT_API_TOKEN` | `""` | Bearer token for `Authorization` header |
| `CASSANDRA_HOST` | `cassandra-node` | Cassandra contact point |
| `CASSANDRA_PORT` | `9042` | Cassandra native transport port |
| `CASSANDRA_KEYSPACE` | `tqdb1` | Keyspace containing `minbar` table |
| `CASSANDRA_USER` | `""` | Optional auth username |
| `CASSANDRA_PASSWORD` | `""` | Optional auth password |

---

## Error handling

| Failure point | Behaviour |
|---|---|
| `INSTRUMENT_API_BASE_URL` not set | `RuntimeError` → HTTP 200 with `Content-Type: text/plain` error body |
| Instrument API HTTP error / unreachable | `RuntimeError` propagated → same error response |
| No rows from `continuous_futures` | `compose_continuous_minbars` returns `[]` → empty gzip body |
| No rollover entries | Same as above |
| Cassandra lookback query returns no row | `diff[i] = None` → offset treated as 0, composition continues |
| Cassandra bar query returns no rows for a segment | Segment silently skipped |
| Cassandra connection failure | Exception propagated → error body to client |

---

## Related files

| File | Role |
|---|---|
| [tqdb_cassandra/web/cgi-bin/q1min.py](../tqdb_cassandra/web/cgi-bin/q1min.py) | CGI entry point; dispatches to `process_continuous_symbol()` |
| [tqdb_cassandra/web/cgi-bin/continuous_symbols.py](../tqdb_cassandra/web/cgi-bin/continuous_symbols.py) | All composition logic: API client, segment building, price adjustment, Cassandra queries |
| [tqdb_cassandra/web/CONTINUOUS_SYMBOLS.md](../tqdb_cassandra/web/CONTINUOUS_SYMBOLS.md) | Operational overview (session windows, rollover rules, endpoints) |
| [tqdb_cassandra/CONTINUOUS_FUTURES_REFACTOR.md](../tqdb_cassandra/CONTINUOUS_FUTURES_REFACTOR.md) | Refactor history and design rationale |
| [docs/Q1MIN_REQUEST_LIFECYCLE.md](Q1MIN_REQUEST_LIFECYCLE.md) | High-level lifecycle covering all three symbol paths |

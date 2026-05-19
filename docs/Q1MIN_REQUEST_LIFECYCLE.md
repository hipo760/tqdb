# q1min.py — Request Lifecycle

CGI script located at `tqdb_cassandra/web/cgi-bin/q1min.py`.

Serves minute-level OHLCV bar data for three symbol categories:
- **Regular symbols** — delegated to the legacy `q1minall.py` subprocess
- **Continuous symbols** (`TXDT`, `TXON`) — composed on-demand from underlying Taifex monthly contracts via Cassandra
- **Custom multi-leg symbols** (`^^` prefix) — delegated to `q1min_multileg.py`

---

## Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant q1min.py as q1min.py (CGI)
    participant Validator as qSymRefPrc.py<br/>(MUSTHAVEBEG validation)
    participant q1minall as q1minall.py<br/>(regular symbols)
    participant Multileg as q1min_multileg.py<br/>(custom ^^ symbols)
    participant Cassandra
    participant continuous_symbols as continuous_symbols.py<br/>(compose_continuous_minbars)

    Client->>q1min.py: HTTP GET /cgi-bin/q1min.py<br/>?symbol=&BEG=&END=[&csv=1][&MUSTHAVEBEG=1]

    activate q1min.py

    Note over q1min.py: parse_query_parameters()<br/>normalize_symbol() / normalize_date_format()

    alt Regular symbol + MUSTHAVEBEG/MOSTHAVEBEG set
        q1min.py->>Validator: GET /cgi-bin/qSymRefPrc.py<br/>?symbol=&qType=LastValidPrc&qDatetime=BEG
        Validator-->>q1min.py: JSON {MinBar: [{datetime}]}
        q1min.py->>Validator: GET /cgi-bin/qSymRefPrc.py<br/>?symbol=&qType=LastValidPrc&qDatetime=END
        Validator-->>q1min.py: JSON {MinBar: [{datetime}]}
        Note over q1min.py: Adjust BEG if begin == end ref datetime<br/>(get_first_valid_datetime)
    end

    Note over q1min.py: Write to /tmp/q1min.<pid>.<epoch>[.gz]

    alt Custom symbol (^^ prefix)
        q1min.py->>Multileg: subprocess: q1min_multileg.py<br/>'profile.ml.<name>' BEG END tmpfile gzip
        Multileg-->>q1min.py: data written to tmpfile
    else Continuous symbol (TXDT / TXON)
        q1min.py->>Cassandra: Cluster.connect(keyspace)
        activate Cassandra
        q1min.py->>continuous_symbols: compose_continuous_minbars(<br/>session, keyspace, symbol, begin_dt, end_dt)
        continuous_symbols->>Cassandra: SELECT from monthly contract tables
        Cassandra-->>continuous_symbols: raw bars per contract
        continuous_symbols-->>q1min.py: composed []bars (dt, O, H, L, C, V)
        deactivate Cassandra
        Note over q1min.py: write_bars_to_tmp_file()<br/>→ CSV rows: YYYYMMDD,HHMMSS,O,H,L,C,V
    else Regular symbol
        q1min.py->>q1minall: subprocess: q1minall.py<br/>host port keyspace symbol BEG END tmpfile gzip
        q1minall->>Cassandra: query minute bars
        Cassandra-->>q1minall: rows
        q1minall-->>q1min.py: data written to tmpfile
    end

    Note over q1min.py: output_response_data()

    alt gzip mode (default)
        q1min.py-->>Client: Content-Encoding: gzip<br/>Content-Type: text/plain<br/>[binary .gz body]
    else csv=1 mode
        q1min.py-->>Client: Content-Type: text/csv<br/>Content-Disposition: attachment<br/>YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol header<br/>[plain text CSV body]
    end

    Note over q1min.py: Remove tmpfile if remove_file=1

    deactivate q1min.py
```

---

## Key Decision Points

| Condition | Path |
|---|---|
| `symbol.startswith("^^")` | Custom multi-leg via `q1min_multileg.py` subprocess |
| `is_continuous_symbol(symbol)` | Compose via `continuous_symbols.compose_continuous_minbars()` + Cassandra |
| Neither | Regular path via `q1minall.py` subprocess |
| `MUSTHAVEBEG` or `MOSTHAVEBEG` != `"0"` (regular only) | Pre-validate BEG/END via `qSymRefPrc.py` to find first valid datetime |
| `csv=1` param | Disable gzip, emit CSV with header row |

## Query Parameters

| Parameter | Description |
|---|---|
| `symbol` | Instrument symbol (URL-encoded). Passed through `normalize_symbol()`. |
| `BEG` | Begin datetime, `YYYY-M-D HH:MM:SS`. Zero-padded by `normalize_date_format()`. |
| `END` | End datetime, same format. |
| `csv` | Set to `1` to receive plain-text CSV with header instead of gzip. |
| `MUSTHAVEBEG` / `MOSTHAVEBEG` | Non-`"0"` value triggers first-valid-datetime adjustment (regular symbols only). |

## Output Format

Each bar row (plain or inside gzip):

```
YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol
```

CSV mode prepends a header line:

```
YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol
```

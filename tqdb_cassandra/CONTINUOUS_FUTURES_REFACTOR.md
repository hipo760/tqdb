# Continuous Futures Refactor — Tracking Document

## Goal

Replace local holiday/calendar schedule logic with an external Instrument API dependency that pre-computes rollover switch points. Simplify the continuous bar composition pipeline and make the price adjustment definition explicit.

**Scope**: `tqdb_cassandra` only. `tqdb_questdb` is not in scope.

---

## Status

| Area | Status | Notes |
|------|--------|-------|
| `continuous_symbols.py` — core rewrite | ✅ Done | |
| `q1min.py` — remove `holidays` arg | ✅ Done | |
| `qContinuousSwitchPoints.py` — update callers | ✅ Done | |
| `qContinuousSymbolInfo.py` — symbol list from API | ✅ Done | |
| `docker-compose.yml` — add API env vars | ✅ Done | |
| API unreachability — graceful fallback | ⚠️ Partial | See open items below |
| `list_continuous_futures_with_availability` — wire up endpoint | ✅ Done | `qContinuousFuturesAvailability.py` + `csymbol.html` |

---

## Architecture

### Before (self-contained)

```
q1min.py
  └─ compose_continuous_minbars()
       ├─ load_holiday_dates()        ← holiday CSV on disk
       ├─ _build_segments()           ← calendar math (3rd Wed / 3rd Fri)
       └─ price gap = next.open - prev.close  (at segment boundary)
```

### After (API-driven)

```
q1min.py
  └─ compose_continuous_minbars()
       ├─ fetch_continuous_futures()       → GET /intra/instrument/continuous_futures
       ├─ fetch_contract_rollover_dt()     → GET /intra/instrument/contract_rollover_dt
       ├─ _build_rollover_schedule()       ← convert API rows to (switch_utc, tqdb_symbol)
       ├─ _compute_switch_diffs()          ← close(new, switch-30m) - close(old, switch-30m)
       └─ _cumulative_offsets()            ← backward cumulative price adjustment
```

---

## Key Design Decisions

### symbol_root → TQDB contract prefix mapping

The API returns `symbol_root`. The code uses this directly as the symbol prefix:

| API `symbol_root` | TQDB contract example | Month code system |
|---|---|---|
| `TX` | `TXD6` (Apr 2026) | TAIFEX (A–L) |
| `TXF` | `TXFD6` (Apr 2026) | TAIFEX (A–L) |
| `NQ` | `NQM6` (Jun 2026) | Standard (FGHJKMNQUVXZ) |
| `ES` | `ESM6` (Jun 2026) | Standard |
| `HSI` | `HSIM6` (Jun 2026) | Standard |

`TAIFEX_ROOTS = {"TX", "TXF"}` controls which roots use the A–L encoding.

### Price adjustment

- Reference point: last available bar with `datetime ≤ (switch_utc − 30 minutes)` for each contract.
- Formula: `diff = close(incoming_contract, lookback) − close(expiring_contract, lookback)`
- Application: cumulative backward. Oldest segment is shifted by sum of all downstream diffs.
- If either close is unavailable (no data in Cassandra): diff treated as 0, adjustment skipped silently.
- `back_adjustment` field from API is ignored in the current phase; all symbols use close-to-close.

### rollover_date = null

Skipped silently. The segment for that contract is omitted from the schedule entirely.

### Timezone handling

- `timezone` field in the API is an integer UTC offset (e.g. `8` for Taiwan, `-5`/`-6` for Chicago).
- Code constructs a `timezone(timedelta(hours=offset))` for the conversion.
- Chicago symbols use `ZoneInfo("America/Chicago")` for DT-session filtering (DST-aware).
- All bars in Cassandra are stored as UTC+0 naive datetimes.

### DT-session filtering (local, not API-driven)

```python
_DT_SESSION_CONFIG = {
    "TXDT":  (08:45–13:45, TW_TZ),
    "NQDT":  (08:30–15:15, CHICAGO_TZ),
    "ESDT":  (08:30–15:15, CHICAGO_TZ),
    "YMDT":  (08:30–15:15, CHICAGO_TZ),
    "HSIDT": (09:15–16:30, HK_TZ),
}
```
ON symbols pass all bars.

---

## Configuration

In `tqdb_cassandra/web/docker-compose.yml`:

```yaml
- INSTRUMENT_API_BASE_URL=https://mc.dev-tt91.cc
- INSTRUMENT_API_TOKEN=<bearer_token>
```

HTTP timeout for each API call: **15 seconds**.

---

## Open Items

### 1. API unreachability — no graceful fallback ⚠️

**Current behavior when the Instrument API is unreachable:**

| Caller | Effect |
|--------|--------|
| `is_continuous_symbol()` | Returns `False` (silently swallows exception). The request will be treated as a **regular symbol** and routed to the Cassandra direct-query path — returning empty or wrong data, with no error to the client. |
| `compose_continuous_minbars()` | `fetch_continuous_futures()` raises `RuntimeError`. The exception propagates up through `process_continuous_symbol()` in `q1min.py`. The CGI catches it and returns a plain-text error response. Client gets an HTTP 200 with error body text (legacy CGI behavior). |
| `discover_continuous_bounds()` | Returns `{"start": null, "end": null, "note": "Not found in Instrument API"}`. No error surfaced to client. |
| `qContinuousSymbolInfo.py` | If `fetch_continuous_futures()` in the symbol-list step fails, falls back to hardcoded symbol list. Per-symbol `discover_continuous_bounds()` calls will then each fail and return null bounds. |
| `qContinuousSwitchPoints.py` | `discover_contract_switch_points()` raises `ValueError`. CGI catches it and returns `{"status": "failed", "error": "..."}` with HTTP 500. |

**Recommended fix**: add a circuit-breaker or explicit HTTP 503 response when the API is unreachable for `compose_continuous_minbars` and `is_continuous_symbol`.

### 2. `list_continuous_futures_with_availability` — no CGI endpoint

The function exists in `continuous_symbols.py` but is not yet exposed via any CGI script. Needs a new `qContinuousFuturesAvailability.py`.

### 3. `is_continuous_symbol` — silent False on API failure

When the API is unreachable, `is_continuous_symbol("TXON")` returns `False`, causing `q1min.py` to silently fall through to `download_from_tqdb()` which will find no data. Consider raising or caching last-known symbol list.

---

## Files Changed

| File | Change |
|------|--------|
| `tqdb_cassandra/web/cgi-bin/continuous_symbols.py` | Full rewrite — API client, new schedule/segment/adjustment logic |
| `tqdb_cassandra/web/cgi-bin/q1min.py` | Remove `load_holiday_dates`, drop `holidays` arg from `compose_continuous_minbars` |
| `tqdb_cassandra/web/cgi-bin/qContinuousSwitchPoints.py` | Remove `load_holiday_dates`, new `enrich_switch_points_with_gap` using 30-min lookback close-to-close |
| `tqdb_cassandra/web/cgi-bin/qContinuousSymbolInfo.py` | Remove `load_holiday_dates`, symbol list from API with fallback |
| `tqdb_cassandra/web/docker-compose.yml` | Add `INSTRUMENT_API_BASE_URL`, `INSTRUMENT_API_TOKEN` |
| `tqdb_cassandra/web/cgi-bin/qContinuousFuturesAvailability.py` | New — exposes `list_continuous_futures_with_availability` |
| `tqdb_cassandra/web/html/csymbol.html` | Updated — adds collapsible contract availability section |

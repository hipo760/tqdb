# Instrument API — Quick Reference

Base URL: `https://<host>/intra/instrument`

All endpoints require a Bearer token in the `Authorization` header.

```
Authorization: Bearer <token>
```

---

## Endpoints

### 1. GET `/intra/instrument/continuous_futures`

Returns rows from the `continuous_futures` table.

**Query Parameters**

| Name          | Type   | Required | Description                    |
|---------------|--------|----------|--------------------------------|
| `symbol`      | string | No       | Filter by exact symbol name    |
| `symbol_root` | string | No       | Filter by exact symbol root    |

**Response** `200 OK`

```json
[
  {
    "id": 4,
    "symbol": "TXON",
    "rollover_type": "time",
    "symbol_root": "TX",
    "contract": "1",
    "rollover_rule": "X",
    "rollover_day": 0,
    "rollover_time": "1500",
    "back_adjustment": "C"
  }
]
```

---

### 2. GET `/intra/instrument/contract_rollover_dt`

Returns the rollover schedule for continuous futures contracts, computed by `sp_get_contract_rollover_dt`.

> Results are **cached for 24 hours** per `symbol` key. Use the refresh endpoint below to force an update.

**Query Parameters**

| Name     | Type   | Required | Description                       |
|----------|--------|----------|-----------------------------------|
| `symbol` | string | No       | Filter by exact symbol name; omit to get all symbols |

**Response** `200 OK`

```json
[
   {
    "symbol": "TXDT",
    "contract": "200803",
    "rollover_date": "2008-02-20",
    "rollover_time": "08:45",
    "timezone": 8
  }
]
```

**Notes**
- `rollover_date` may be `null` if the date cannot be computed.
- `rollover_time` is formatted as `HH:mm`.
- `timezone` is the UTC offset (integer hours) of the exchange.

---


## Example — Python (`httpx`)

```python
import httpx

BASE_URL = "https://<host>"
HEADERS = {"Authorization": "Bearer <token>"}

# All rollover dates (cached)
r = httpx.get(f"{BASE_URL}/intra/instrument/contract_rollover_dt", headers=HEADERS)
r.raise_for_status()
rollover_list = r.json()

# Single symbol
r = httpx.get(f"{BASE_URL}/intra/instrument/contract_rollover_dt",
              params={"symbol": "ES"}, headers=HEADERS)
r.raise_for_status()
```

## Example — Python (`requests`)

```python
import requests

BASE_URL = "https://<host>"
HEADERS = {"Authorization": "Bearer <token>"}

rollover = requests.get(
    f"{BASE_URL}/intra/instrument/contract_rollover_dt",
    params={"symbol": "NQ"},
    headers=HEADERS,
).json()
```

---
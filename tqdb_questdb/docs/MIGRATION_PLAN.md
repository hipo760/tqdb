# TQDB Migration Plan: QuestDB + FastAPI

**Document Version:** 1.0  
**Date:** February 20, 2026  
**Status:** Planning Phase  
**Author:** TQDB Team

---

## Executive Summary

This document outlines the migration strategy from the legacy TQDB Cassandra + Apache CGI architecture to a modern QuestDB + FastAPI stack, while maintaining backward compatibility with existing client applications.

### Key Objectives

1. **Modernize Architecture**: Replace Cassandra + Python CGI with QuestDB + FastAPI
2. **Maintain Compatibility**: Ensure legacy GET endpoints continue to work
3. **Improve Performance**: Leverage QuestDB's time-series optimizations
4. **Simplify Operations**: Reduce complexity with modern Python framework
5. **Enable Future Growth**: Create foundation for new features and APIs

---

## Current State Analysis

### Usage Analysis Results

Based on Apache access log analysis (IP: 35.72.213.238), the following endpoints are actively used:

#### **Critical Endpoints** (Must Implement)

| Endpoint | Usage Count | Purpose | Parameters |
|----------|-------------|---------|------------|
| `/cgi-bin/q1min.py` | 57 requests | 1-minute OHLCV data | `symbol`, `BEG`, `END` |
| `/cgi-bin/q1sec.py` | 26 requests | 1-second tick data | `symbol`, `BEG`, `END` |
| `/cgi-bin/qsyminfo.py` | 3 requests | Symbol information | `symbol` |

**Symbols Used:**
- BTCUSD.BYBIT (primary)
- ETHUSD.BYBIT (secondary)

**Date Range Pattern:**
- Intraday queries (few hours to 1-2 days)
- Real-time/near-real-time data access

#### **Unused Endpoints** (Not Required)

The following endpoints showed ZERO usage from the application and can be excluded from initial migration:

- ❌ q1day.py - Daily aggregations
- ❌ qRange.py - Range queries
- ❌ qSystemInfo.py - System information
- ❌ qSupportTZ.py - Timezone support
- ❌ doAction.py - Administrative actions
- ❌ eData.py - Edit data
- ❌ usymbol.py - Update symbols
- ❌ i1min_*.py - 1-minute import scripts
- ❌ All HTML pages (application uses API only)

---

## Target Architecture

### Technology Stack

```
┌─────────────────────────────────────────┐
│         Client Application              │
│     (Legacy GET endpoints)              │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  ┌───────────────────────────────────┐  │
│  │  Legacy Compatibility Layer       │  │
│  │  /cgi-bin/q1min.py                │  │
│  │  /cgi-bin/q1sec.py                │  │
│  │  /cgi-bin/qsyminfo.py             │  │
│  └───────────────────────────────────┘  │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│          QuestDB                        │
│    Time-Series Database                 │
│  ┌─────────────────────────────────┐   │
│  │  ohlcv_1sec     (secbar)        │   │
│  │  ohlcv_1min     (minbar)        │   │
│  │  symbols        (metadata)      │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Updates: Every 5 seconds               │
│  Dedup: Enabled (upsert behavior)       │
└─────────────────────────────────────────┘
```

### Component Breakdown

#### 1. **QuestDB** (Database Layer)
- **Role**: Time-series data storage with 5-second update cycle
- **Advantages**: 
  - 10-100x faster than Cassandra for time-series queries
  - Native time-series functions (SAMPLE BY, TIME BUCKET)
  - Columnar storage optimized for OHLCV data
  - Built-in deduplication (matches Cassandra upsert)
  - Out-of-order (O3) support for late data
  - SQL interface (easier migration)

#### 2. **FastAPI** (Application Layer)
- **Role**: REST API server with legacy compatibility
- **Advantages**:
  - High performance (async/await support)
  - Automatic API documentation (OpenAPI/Swagger)
  - Type validation (Pydantic models)
  - Modern Python framework
  - Easy testing and deployment

#### 3. **Compatibility Layer** (Bridge)
- **Role**: Translate legacy CGI endpoints to FastAPI
- **Approach**: Mount legacy paths with query parameter mapping

---

## Implementation Plan

### Phase 1: Foundation Setup (Week 1-2)

#### 1.1 QuestDB Setup

**Schema Design (Matches Cassandra minbar/secbar):**

```sql
-- Table: ohlcv_1sec (Equivalent to Cassandra secbar)
-- Updated every 5 seconds with same key (timestamp, symbol)
CREATE TABLE ohlcv_1sec (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG
) timestamp(timestamp) PARTITION BY DAY
  WITH maxUncommittedRows = 100000, o3MaxLag = 60s;

-- Enable deduplication (matches Cassandra upsert behavior)
ALTER TABLE ohlcv_1sec DEDUP ENABLE UPSERT KEYS(timestamp, symbol);

-- Table: ohlcv_1min (Equivalent to Cassandra minbar)
-- Updated every 5 seconds with same key (timestamp, symbol)
CREATE TABLE ohlcv_1min (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG
) timestamp(timestamp) PARTITION BY DAY
  WITH maxUncommittedRows = 100000, o3MaxLag = 60s;

-- Enable deduplication (matches Cassandra upsert behavior)
ALTER TABLE ohlcv_1min DEDUP ENABLE UPSERT KEYS(timestamp, symbol);

-- Table: symbols (Equivalent to Cassandra symbol table)
CREATE TABLE symbols (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    name STRING,
    exchange STRING,
    asset_type STRING,
    status STRING,
    first_trade TIMESTAMP,
    last_trade TIMESTAMP,
    updated_at TIMESTAMP
) timestamp(updated_at);

-- Indexes for fast lookups (automatic on SYMBOL type)
-- QuestDB automatically indexes SYMBOL columns
```

**Configuration Explanation:**
- `maxUncommittedRows = 100000`: Buffer for high-frequency updates
- `o3MaxLag = 60s`: Accept data up to 60 seconds out of order
- `DEDUP ENABLE UPSERT`: Latest write wins (same as Cassandra)
- `PARTITION BY DAY`: Daily partitions for efficient queries

#### 1.2 FastAPI Project Structure

```
tqdb_questdb/
├── web/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI application entry
│   │   ├── config.py                  # Configuration
│   │   ├── database.py                # QuestDB connection
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── ohlcv.py              # OHLCV data models
│   │   │   ├── tick.py               # Tick data models
│   │   │   └── symbol.py             # Symbol models
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── legacy.py             # Legacy CGI compatibility
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ohlcv_service.py      # OHLCV business logic
│   │   │   ├── tick_service.py       # Tick business logic
│   │   │   └── symbol_service.py     # Symbol business logic
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── formatters.py         # Data formatters
│   │       └── validators.py         # Input validators
│   ├── tests/
│   │   ├── test_legacy.py
│   │   ├── test_v2_api.py
│   │   └── test_services.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── README.md
└── docs/
    ├── MIGRATION_PLAN.md             # This document
    ├── API_REFERENCE.md
    └── LEGACY_COMPATIBILITY.md
```

### Phase 2: Core Implementation (Week 3-4)

#### 2.1 FastAPI Application Core

**File: `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import legacy
from app.database import init_db

app = FastAPI(
    title="TQDB API",
    description="Time-series market data API with legacy CGI compatibility",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup():
    await init_db()

# Mount legacy compatibility routes
app.include_router(legacy.router, prefix="/cgi-bin", tags=["legacy"])

@app.get("/")
async def root():
    return {
        "service": "TQDB API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "legacy": [
                "/cgi-bin/q1min.py",
                "/cgi-bin/q1sec.py",
                "/cgi-bin/qsyminfo.py"
            ]
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

#### 2.2 Legacy Compatibility Layer

**File: `app/routers/legacy.py`**

```python
from fastapi import APIRouter, Query, Response
from datetime import datetime
from typing import Optional
from app.services.ohlcv_service import get_minute_data
from app.services.tick_service import get_second_data
from app.services.symbol_service import get_symbol_info
from app.utils.formatters import format_legacy_output

router = APIRouter()

@router.get("/q1min.py")
async def legacy_1min(
    symbol: str = Query(..., description="Trading symbol (e.g., BTCUSD.BYBIT)"),
    BEG: str = Query(..., description="Begin datetime (YYYY-MM-DD HH:MM:SS)"),
    END: str = Query(..., description="End datetime (YYYY-MM-DD HH:MM:SS)"),
    csv: Optional[str] = Query(None, description="1=CSV download")
):
    """
    Legacy endpoint: /cgi-bin/q1min.py
    Returns 1-minute OHLCV data in legacy format
    
    Response Format (text/plain):
        YYYYMMDD,HHMMSS,Open,High,Low,Close,Volume
        20260217,190900,68022.5,68022.5,67944.3,67972.6,91975.0
        20260217,191000,67992.0,67996.0,67983.0,67983.0,749.0
        ...
    """
    # Parse datetime (flexible format support)
    begin_dt = datetime.strptime(BEG.replace(" ", " ").strip(), "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(END.replace(" ", " ").strip(), "%Y-%m-%d %H:%M:%S")
    
    # Get data from service
    data = await get_minute_data(symbol, begin_dt, end_dt)
    
    # Format as legacy output: YYYYMMDD,HHMMSS,O,H,L,C,V
    lines = []
    for bar in data:
        dt_str = bar.timestamp.strftime("%Y%m%d,%H%M%S")
        lines.append(f"{dt_str},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    
    output = "\n".join(lines)
    
    # Return with appropriate content type
    if csv == "1":
        return Response(
            content=output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={symbol}_1min.csv"}
        )
    else:
        return Response(content=output, media_type="text/plain")

@router.get("/q1sec.py")
async def legacy_1sec(
    symbol: str = Query(..., description="Trading symbol (e.g., BTCUSD.BYBIT)"),
    BEG: str = Query(..., description="Begin datetime (YYYY-MM-DD HH:MM:SS)"),
    END: str = Query(..., description="End datetime (YYYY-MM-DD HH:MM:SS)")
):
    """
    Legacy endpoint: /cgi-bin/q1sec.py
    Returns 1-second tick data in legacy format
    
    Response Format (text/plain):
        YYYYMMDD,HHMMSS,Open,High,Low,Close,Volume
        20260220,194701,67541.2,67546.8,67541.2,67546.8,1283
        20260220,194702,67545.1,67545.1,67545.1,67545.1,1890
        ...
    """
    begin_dt = datetime.strptime(BEG.replace(" ", " ").strip(), "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(END.replace(" ", " ").strip(), "%Y-%m-%d %H:%M:%S")
    
    data = await get_second_data(symbol, begin_dt, end_dt)
    
    # Format as legacy output: YYYYMMDD,HHMMSS,O,H,L,C,V
    lines = []
    for tick in data:
        dt_str = tick.timestamp.strftime("%Y%m%d,%H%M%S")
        lines.append(f"{dt_str},{tick.open},{tick.high},{tick.low},{tick.close},{tick.volume}")
    
    output = "\n".join(lines)
    
    return Response(content=output, media_type="text/plain")

@router.get("/qsyminfo.py")
async def legacy_syminfo(
    symbol: str = Query("ALL", description="Symbol code or ALL for all symbols"),
    _: Optional[str] = Query(None, alias="_", description="jQuery cache buster")
):
    """
    Legacy endpoint: /cgi-bin/qsyminfo.py
    Returns symbol information in legacy JSON format
    
    Response Format (application/json):
        [
          {
            "symbol": "BTCUSD.BYBIT",
            "name": "Bitcoin USD Perpetual",
            "exchange": "BYBIT",
            "asset_type": "CRYPTO",
            ...
          }
        ]
    """
    if symbol == "ALL":
        info_list = await get_all_symbols()
    else:
        info = await get_symbol_info(symbol)
        info_list = [info] if info else []
    
    # Return in legacy JSON format (array of objects)
    return [
        {
            "symbol": info.symbol,
            "name": info.name,
            "exchange": info.exchange,
            "asset_type": info.asset_type,
            "status": info.status,
            "first_trade": info.first_trade.isoformat() if info.first_trade else None,
            "last_trade": info.last_trade.isoformat() if info.last_trade else None
        }
        for info in info_list
    ]
```

#### 2.3 QuestDB Service Layer

**File: `app/services/ohlcv_service.py`**

```python
from datetime import datetime
from typing import List
from app.database import get_questdb_connection
from app.models.ohlcv import OHLCVBar

async def get_minute_data(
    symbol: str,
    begin_dt: datetime,
    end_dt: datetime
) -> List[OHLCVBar]:
    """
    Fetch 1-minute OHLCV data from QuestDB
    """
    conn = get_questdb_connection()
    
    query = """
        SELECT 
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp < $3
        ORDER BY timestamp ASC
    """
    
    result = conn.execute(query, (symbol, begin_dt, end_dt))
    
    bars = []
    for row in result:
        bars.append(OHLCVBar(
            timestamp=row[0],
            open=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5]
        ))
    
    return bars
```

### Phase 3: Testing & Validation (Week 5)

#### 3.1 Test Coverage

```python
# tests/test_legacy.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_legacy_q1min():
    """Test legacy 1-minute endpoint compatibility"""
    response = client.get(
        "/cgi-bin/q1min.py",
        params={
            "symbol": "BTCUSD.BYBIT",
            "BEG": "2026-02-20 00:00:00",
            "END": "2026-02-20 01:00:00"
        }
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    # Verify data format: YYYYMMDD,HHMMSS,O,H,L,C,V
    lines = response.text.strip().split("\n")
    assert len(lines) > 0
    
    # Verify each line has correct format
    for line in lines:
        fields = line.split(",")
        assert len(fields) == 7  # YYYYMMDD, HHMMSS, O, H, L, C, V
        assert len(fields[0]) == 8  # YYYYMMDD
        assert len(fields[1]) == 6  # HHMMSS
        # Verify numeric values
        for i in range(2, 7):
            float(fields[i])  # Should parse as float

def test_legacy_q1sec():
    """Test legacy 1-second endpoint compatibility"""
    response = client.get(
        "/cgi-bin/q1sec.py",
        params={
            "symbol": "BTCUSD.BYBIT",
            "BEG": "2026-02-20 19:48:00",
            "END": "2026-02-20 19:49:00"
        }
    )
    assert response.status_code == 200
    
    # Verify format: YYYYMMDD,HHMMSS,O,H,L,C,V
    lines = response.text.strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        fields = line.split(",")
        assert len(fields) == 7

def test_legacy_qsyminfo():
    """Test legacy symbol info endpoint"""
    response = client.get(
        "/cgi-bin/qsyminfo.py",
        params={"symbol": "BTCUSD.BYBIT"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    
    # Verify JSON array format
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Verify object structure
    symbol_obj = data[0]
    assert "symbol" in symbol_obj
    assert "name" in symbol_obj
    assert "exchange" in symbol_obj
    assert symbol_obj["symbol"] == "BTCUSD.BYBIT"
```

#### 3.2 Performance Benchmarks

**Target Performance:**
- 1-minute query (1 day): < 100ms
- 1-second query (1 hour): < 200ms
- Symbol info query: < 10ms
- Concurrent requests: 100 req/s minimum

### Phase 4: Data Migration (Week 6-7)

#### 4.1 Understanding Cassandra's Update Pattern

**Current Cassandra Implementation:**
- Data ingested every **5 seconds** to save resources
- `minbar` table updated with **same key (time, symbol)** every 5 seconds
- Each update overwrites previous record for that minute
- Uses Cassandra's upsert behavior (INSERT = UPDATE for same primary key)
- Result: Only final state of each minute bar is persisted

**Example:**
```
19:00:00 - First update:  O=100, H=100, L=100, C=100, V=10
19:00:05 - Update:        O=100, H=102, L=99,  C=101, V=25
19:00:10 - Update:        O=100, H=103, L=99,  C=102, V=42
...
19:00:55 - Final update:  O=100, H=105, L=98,  C=103, V=150
(Only final state stored in Cassandra)
```

#### 4.2 QuestDB Update Strategy

**QuestDB Approach:**

QuestDB supports two strategies for handling duplicate timestamps:

**Option 1: Deduplication (Recommended)**
```sql
-- Enable deduplication on timestamp + symbol
ALTER TABLE ohlcv_1min DEDUP ENABLE UPSERT KEYS(timestamp, symbol);
ALTER TABLE ohlcv_1sec DEDUP ENABLE UPSERT KEYS(timestamp, symbol);
```

**Behavior:**
- Newer records with same (timestamp, symbol) **overwrite** older records
- Identical to Cassandra's upsert behavior
- Maintains only final state (matches current system)
- Performance: ~10-20% slower than append-only, still very fast

**Option 2: Out-of-Order (O3) Support**
```sql
-- Allow late-arriving data
ALTER TABLE ohlcv_1min SET PARAM maxUncommittedRows = 100000;
ALTER TABLE ohlcv_1min SET PARAM o3MaxLag = 60s;
```

**Behavior:**
- Accepts data up to 60 seconds out of order
- Automatically handles 5-second update cycle
- No deduplication - latest write wins
- Best performance for time-series ingestion

**Recommended Configuration:**
```sql
-- Combined approach for production
CREATE TABLE ohlcv_1min (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG
) timestamp(timestamp) PARTITION BY DAY
  WITH maxUncommittedRows = 100000, o3MaxLag = 60s;

-- Enable deduplication after table creation
ALTER TABLE ohlcv_1min DEDUP ENABLE UPSERT KEYS(timestamp, symbol);
```

#### 4.3 Data Ingestion Pattern

**5-Second Update Cycle:**

```python
# Ingestion service (replaces current Cassandra writer)
from questdb.ingress import Sender
import time

def ingest_bar_update(symbol: str, timestamp: datetime, ohlcv: dict):
    """
    Update bar every 5 seconds (matches current pattern)
    QuestDB dedup ensures only latest state persists
    """
    with Sender('localhost', 9009) as sender:
        sender.row(
            'ohlcv_1min',
            symbols={'symbol': symbol},
            columns={
                'open': ohlcv['open'],
                'high': ohlcv['high'],
                'low': ohlcv['low'],
                'close': ohlcv['close'],
                'volume': ohlcv['volume']
            },
            at=timestamp
        )
        sender.flush()

# Example: Update same minute bar multiple times
while True:
    current_minute = get_current_minute_bar('BTCUSD.BYBIT')
    ingest_bar_update('BTCUSD.BYBIT', current_minute.timestamp, current_minute.ohlcv)
    time.sleep(5)  # Update every 5 seconds
```

**Key Differences from Cassandra:**
- ✅ Same upsert behavior (dedup enabled)
- ✅ Same final result (only last state stored)
- ✅ Better performance (columnar storage)
- ✅ Simpler queries (standard SQL)
- ⚠️ Need to configure dedup + O3 properly

#### 4.4 Cassandra to QuestDB Migration

**Strategy: Dual-Write Period**

1. **Setup dual-write**: Write to both Cassandra and QuestDB
2. **Backfill historical data**: Migrate existing data in batches
3. **Validation period**: Compare results from both systems
4. **Cutover**: Switch read queries to QuestDB
5. **Decommission**: Remove Cassandra after validation

#### 4.4 Cassandra to QuestDB Migration

**Strategy: Dual-Write Period**

1. **Setup dual-write**: Write to both Cassandra and QuestDB
2. **Backfill historical data**: Migrate existing data in batches
3. **Validation period**: Compare results from both systems
4. **Cutover**: Switch read queries to QuestDB
5. **Decommission**: Remove Cassandra after validation

**Migration Script:**

```python
# scripts/migrate_cassandra_to_questdb.py

from cassandra.cluster import Cluster
import questdb.ingress as qi
from datetime import datetime, timedelta
import logging

def migrate_ohlcv_data(start_date, end_date):
    """
    Migrate OHLCV data from Cassandra to QuestDB
    Note: Cassandra minbar already contains final state (from 5-sec updates)
    """
    
    # Connect to Cassandra
    cassandra = Cluster(['cassandra-node']).connect('tqdb1')
    
    # Connect to QuestDB
    with qi.Sender('localhost', 9009) as sender:
        
        # Query Cassandra minbar table
        query = """
            SELECT symbol, datetime, open, high, low, close, vol
            FROM minbar
            WHERE datetime >= %s AND datetime < %s
            ALLOW FILTERING
        """
        
        rows = cassandra.execute(query, (start_date, end_date))
        
        batch_count = 0
        for row in rows:
            sender.row(
                'ohlcv_1min',
                symbols={'symbol': row.symbol},
                columns={
                    'open': row.open,
                    'high': row.high,
                    'low': row.low,
                    'close': row.close,
                    'volume': row.vol
                },
                at=row.datetime
            )
            
            batch_count += 1
            if batch_count % 10000 == 0:
                sender.flush()
                logging.info(f"Migrated {batch_count} records")
        
        sender.flush()
        logging.info(f"Migration complete: {batch_count} total records")

def migrate_secbar_data(start_date, end_date):
    """
    Migrate second bar data from Cassandra to QuestDB
    """
    cassandra = Cluster(['cassandra-node']).connect('tqdb1')
    
    with qi.Sender('localhost', 9009) as sender:
        query = """
            SELECT symbol, datetime, open, high, low, close, vol
            FROM secbar
            WHERE datetime >= %s AND datetime < %s
            ALLOW FILTERING
        """
        
        rows = cassandra.execute(query, (start_date, end_date))
        
        batch_count = 0
        for row in rows:
            sender.row(
                'ohlcv_1sec',
                symbols={'symbol': row.symbol},
                columns={
                    'open': row.open,
                    'high': row.high,
                    'low': row.low,
                    'close': row.close,
                    'volume': row.vol
                },
                at=row.datetime
            )
            
            batch_count += 1
            if batch_count % 50000 == 0:  # Larger batches for second data
                sender.flush()
                logging.info(f"Migrated {batch_count} second bars")
        
        sender.flush()
        logging.info(f"Second bar migration complete: {batch_count} records")

if __name__ == '__main__':
    # Migrate last 90 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    logging.info("Starting minbar migration...")
    migrate_ohlcv_data(start_date, end_date)
    
    logging.info("Starting secbar migration...")
    migrate_secbar_data(start_date, end_date)
```

### Phase 5: Deployment (Week 8)

#### 5.1 Docker Deployment

**File: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  questdb:
    image: questdb/questdb:7.3.0
    container_name: tqdb-questdb
    ports:
      - "9000:9000"   # Web console
      - "9009:9009"   # InfluxDB line protocol
      - "8812:8812"   # Postgres wire protocol
    environment:
      - QDB_HTTP_ENABLED=true
      - QDB_PG_ENABLED=true
    volumes:
      - questdb-data:/var/lib/questdb
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  fastapi:
    build:
      context: ./web
      dockerfile: Dockerfile
    container_name: tqdb-api
    ports:
      - "8000:8000"
    environment:
      - QUESTDB_HOST=questdb
      - QUESTDB_PORT=8812
      - LOG_LEVEL=info
    depends_on:
      - questdb
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  questdb-data:
```

**File: `web/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**File: `web/requirements.txt`**

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.6.0
pydantic-settings==2.1.0
psycopg2-binary==2.9.9  # QuestDB Postgres wire protocol
questdb==1.1.0           # QuestDB Python client
python-dateutil==2.8.2
pytest==7.4.4
httpx==0.26.0
```

---

## Legacy Endpoint Compatibility Matrix

| Feature | Legacy (CGI) | Modern (FastAPI) | Notes |
|---------|-------------|------------------|-------|
| **Endpoint Path** | `/cgi-bin/q1min.py` | ✅ Supported | Exact path match |
| **Query Parameters** | `symbol`, `BEG`, `END` | ✅ Supported | Parameter names preserved |
| **Response Format** | `YYYYMMDD,HHMMSS,O,H,L,C,V` | ✅ Supported | Exact format match |
| **Date Format** | `YYYY-MM-DD HH:MM:SS` | ✅ Supported | Parsed correctly (flexible spacing) |
| **HTTP Method** | GET | ✅ Supported | GET only (legacy compatible) |
| **Content-Type** | `text/plain` | ✅ Supported | Matches legacy |
| **CSV Download** | `csv=1` | ✅ Supported | CSV download with proper headers |
| **Error Handling** | Text message | ✅ Compatible | Plain text errors for legacy |

---

## Migration Timeline

### Overview

| Phase | Duration | Status | Deliverables |
|-------|----------|--------|--------------|
| Phase 1: Foundation | 2 weeks | 🔵 Planned | QuestDB setup with dedup, FastAPI skeleton |
| Phase 2: Core Implementation | 2 weeks | 🔵 Planned | Legacy endpoints, services |
| Phase 3: Testing | 1 week | 🔵 Planned | Test suite, validation |
| Phase 4: Data Migration | 2 weeks | 🔵 Planned | Cassandra → QuestDB (minbar/secbar) |
| Phase 5: Deployment | 1 week | 🔵 Planned | Production deployment |
| **Total** | **8 weeks** | | |

### Milestones

- ✅ **Week 2**: QuestDB running with schema (dedup enabled)
- ✅ **Week 4**: Legacy endpoints functional
- ✅ **Week 5**: All tests passing
- ✅ **Week 7**: Data migration complete (minbar/secbar)
- ✅ **Week 8**: Production deployment

---

## Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss during migration | 🔴 High | 🟡 Medium | Dual-write period, validation, backups |
| Legacy endpoint incompatibility | 🟡 Medium | 🟡 Medium | Extensive testing, gradual rollout |
| Performance degradation | 🟡 Medium | 🟢 Low | Load testing, QuestDB optimizations |
| Client application breaks | 🔴 High | 🟢 Low | Byte-level compatibility testing |
| Migration timeline overrun | 🟡 Medium | 🟡 Medium | Phased approach, clear milestones |

---

## Success Criteria

### Functional Requirements

- ✅ All 3 legacy endpoints work identically to current system
- ✅ Response format matches byte-for-byte (for same query)
- ✅ All historical data successfully migrated
- ✅ Zero downtime during migration

### Performance Requirements

- ✅ Query latency < 100ms (p50) for typical queries
- ✅ Query latency < 500ms (p99) for typical queries
- ✅ Support 100+ concurrent requests
- ✅ Handle 1M+ records per query efficiently

### Operational Requirements

- ✅ Docker-based deployment
- ✅ Automated health checks
- ✅ Comprehensive logging
- ✅ API documentation (OpenAPI/Swagger)
- ✅ Monitoring and alerting setup

---

## Future Enhancements

### Phase 2 (Post-Migration)

1. **Modern REST API (v2)**: JSON-based API with OpenAPI documentation
2. **WebSocket Support**: Real-time data streaming
3. **Caching Layer**: Redis for frequently accessed data
4. **Rate Limiting**: Protect against abuse
5. **Authentication**: API keys and OAuth

### Long-term

1. **GraphQL API**: Flexible query capabilities
2. **Multi-Exchange Support**: Expand beyond BYBIT
3. **Advanced Analytics**: Technical indicators, pattern recognition
4. **Data Export**: Bulk download capabilities
5. **Admin Dashboard**: Web UI for system management

---

## Appendix

### A. Query Examples

#### Legacy Endpoint Usage

```bash
# 1-minute data (current format)
curl "http://localhost:8000/cgi-bin/q1min.py?symbol=BTCUSD.BYBIT&BEG=2026-02-17%2019:09:00&END=2026-02-18%2000:00:00"
# Response (text/plain):
# 20260217,190900,68022.5,68022.5,67944.3,67972.6,91975.0
# 20260217,191000,67992.0,67996.0,67983.0,67983.0,749.0
# 20260217,191100,68000.0,68043.8,67946.5,67966.2,66217.0
# ...

# 1-second data (current format)
curl "http://localhost:8000/cgi-bin/q1sec.py?symbol=BTCUSD.BYBIT&BEG=2026-02-20%2019:46:52&END=2026-02-20%2019:48:57"
# Response (text/plain):
# 20260220,194701,67541.2,67546.8,67541.2,67546.8,1283
# 20260220,194702,67545.1,67545.1,67545.1,67545.1,1890
# 20260220,194703,67545.0,67545.0,67540.2,67540.2,5202
# ...

# Symbol info (current format)
curl "http://localhost:8000/cgi-bin/qsyminfo.py?symbol=BTCUSD.BYBIT"
# Response (application/json):
# [
#   {
#     "symbol": "BTCUSD.BYBIT",
#     "name": "Bitcoin USD Perpetual",
#     "exchange": "BYBIT",
#     "asset_type": "CRYPTO",
#     "status": "ACTIVE",
#     "first_trade": "2024-01-01T00:00:00",
#     "last_trade": "2026-02-20T23:59:59"
#   }
# ]
```

### B. QuestDB Configuration for 5-Second Updates

**Optimal Settings for 5-Second Update Cycle:**

```sql
-- Configure tables for frequent updates (every 5 seconds)
ALTER TABLE ohlcv_1min SET PARAM maxUncommittedRows = 100000;
ALTER TABLE ohlcv_1min SET PARAM o3MaxLag = 60s;
ALTER TABLE ohlcv_1min SET PARAM commitLag = 10s;

ALTER TABLE ohlcv_1sec SET PARAM maxUncommittedRows = 100000;
ALTER TABLE ohlcv_1sec SET PARAM o3MaxLag = 60s;
ALTER TABLE ohlcv_1sec SET PARAM commitLag = 10s;

-- Enable deduplication (matches Cassandra upsert)
ALTER TABLE ohlcv_1min DEDUP ENABLE UPSERT KEYS(timestamp, symbol);
ALTER TABLE ohlcv_1sec DEDUP ENABLE UPSERT KEYS(timestamp, symbol);
```

**Parameter Explanation:**
- `maxUncommittedRows = 100000`: Buffer up to 100K rows before commit
- `o3MaxLag = 60s`: Accept data up to 60 seconds out of order
- `commitLag = 10s`: Wait 10 seconds before committing (allows for 2 updates per minute)
- `DEDUP ENABLE`: Ensures same (timestamp, symbol) overwrites previous value

**Performance Impact:**
- Deduplication overhead: ~10-20% (acceptable for correctness)
- Update throughput: >100K rows/sec (far exceeds needs)
- Query latency: Still <100ms for typical queries

### C. Monitoring Queries

```sql
-- Check data freshness
SELECT 
    symbol,
    max(timestamp) as last_update,
    count(*) as record_count
FROM ohlcv_1min
GROUP BY symbol
ORDER BY last_update DESC;

-- Monitor query performance
SELECT 
    date_trunc('hour', timestamp) as hour,
    count(*) as queries,
    avg(duration_ms) as avg_duration_ms
FROM query_log
WHERE timestamp >= dateadd('d', -1, now())
GROUP BY hour
ORDER BY hour DESC;
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-20 | TQDB Team | Initial migration plan based on usage analysis |

---

## Contact & Support

For questions or clarifications regarding this migration plan:

- **Project Lead**: [Your Name]
- **Technical Contact**: [Tech Lead]
- **Documentation**: `/tqdb_questdb/docs/`
- **Repository**: `https://github.com/hipo760/tqdb` (branch: feature-container)

---

**End of Document**

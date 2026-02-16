# TQDB Modernization and Containerization Refactor Plan

## Executive Summary

This document outlines a comprehensive refactoring plan to modernize the TQDB (Time-series Quote Database) system by containerizing all components while maintaining backward compatibility with existing API endpoints. The refactor will transform the current monolithic architecture into a lightweight, container-based microservices architecture.

**Current Architecture:**
- Cassandra database (installed on host)
- Apache/Lighttpd web server with CGI-bin scripts
- Shell and Python tool scripts running on host

**Target Architecture:**
- Containerized Cassandra (official Docker image)
- Modern web UI framework in container
- Containerized tool scripts
- API gateway for backward compatibility
- Docker Compose orchestration

---

## Table of Contents

1. [System Analysis](#1-system-analysis)
2. [Containerization Strategy](#2-containerization-strategy)
3. [Web UI Modernization](#3-web-ui-modernization)
4. [API Compatibility Layer](#4-api-compatibility-layer)
5. [Tool Scripts Containerization](#5-tool-scripts-containerization)
6. [Data Migration Strategy](#6-data-migration-strategy)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Development Roadmap](#8-development-roadmap)
9. [Testing Strategy](#9-testing-strategy)
10. [Rollback Plan](#10-rollback-plan)

---

## 1. System Analysis

### 1.1 Current Components

#### Database Layer
- **Cassandra 3.x/4.x**: Time-series data storage
- **Keyspace**: `tqdb1` (default)
- **Tables**: 
  - `minbar` - 1-minute bar data
  - `secbar` - 1-second bar data
  - `tick` - tick-level data
  - `symbol` - symbol metadata
  - `conf` - configuration settings
  - `day` - daily aggregated data

#### Web Interface
- **Server**: Apache httpd with CGI support
- **Technology**: Python 3 CGI scripts
- **Location**: `tools/for_web/cgi-bin/`
- **Frontend**: jQuery + jQuery UI (legacy)
- **Key CGI Endpoints** (23 total):
  - Query: `q1min.py`, `q1sec.py`, `q1day.py`, `qtick.py`, `qquote.py`, `qRange.py`
  - Symbol: `qsyminfo.py`, `qSymSummery.py`, `usymbol.py`
  - Import: `i1min_check.py`, `i1min_do.py`, `i1min_readstatus.py`
  - Edit: `eData.py`, `eConf.py`
  - System: `qSystemInfo.py`, `qSupportTZ.py`
  - Actions: `doAction.py`

#### Tool Scripts
- **Data Processing**:
  - `Min2Cass.py`, `Sec2Cass.py` - Import bar data
  - `Sym2Cass.py` - Symbol management
  - `Min2Day.py` - Daily aggregation
  - `TQAlert.py` - Alert monitoring system
  
- **Data Transformation**:
  - `build1MinFromTick.sh`, `build1SecFromTick.sh`
  - `csvtzconv.py`, `formatDT.py`
  
- **Binary Tools** (C++ compiled):
  - `q1min`, `q1sec`, `q1minsec` - Query tools
  - `qtick`, `qquote`, `qsym` - Data access tools
  - `itick`, `updtick` - Tick data tools

- **Automation**:
  - `autoIns2Cass.sh`, `watchdogAutoIns2Cass.sh`
  - `backfillMinSec.sh`

### 1.2 Dependencies Analysis

#### Python Dependencies
```
cassandra-driver
python-dateutil
```

#### System Dependencies
- Java 8/11 (for Cassandra)
- GCC/G++ (for C++ tools compilation)
- Apache httpd
- netcat (nc)
- chrony/ntp

### 1.3 Current Pain Points

1. **Infrastructure**: Cassandra installation and maintenance complexity
2. **Web UI**: Outdated jQuery-based interface, difficult to maintain
3. **Deployment**: Manual installation process, environment-specific
4. **Scalability**: Monolithic architecture limits horizontal scaling
5. **Development**: Difficult local development setup
6. **Testing**: No containerized test environment

---

## 2. Containerization Strategy

### 2.1 Container Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Cassandra  │  │   Web UI     │  │  API Gateway │      │
│  │  (Official)  │  │  Container   │  │  Container   │      │
│  │              │  │              │  │              │      │
│  │  Port: 9042  │  │  Port: 3000  │  │  Port: 8080  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         └──────────────────┴──────────────────┘               │
│                            │                                   │
│  ┌─────────────────────────┴────────────────────────┐        │
│  │          Tool Scripts Container                   │        │
│  │  - Data import tools                              │        │
│  │  - Alert monitoring (TQAlert)                     │        │
│  │  - Cron jobs for automation                       │        │
│  └───────────────────────────────────────────────────┘        │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │         Shared Volumes                              │      │
│  │  - cassandra_data                                   │      │
│  │  - import_data (CSV files, tick files)             │      │
│  │  - logs                                             │      │
│  │  - tmp (TQAlert signals)                            │      │
│  └────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Cassandra Container

#### Base Image
```yaml
Image: cassandra:4.1
```

#### Configuration Strategy
- Use official Cassandra Docker image (latest stable 4.x)
- Mount custom `cassandra.yaml` for tuning
- Initialize schema using initialization scripts
- Persist data using Docker volumes

#### Container Specifications
```yaml
container_name: tqdb-cassandra
ports:
  - "9042:9042"  # CQL native transport
  - "9160:9160"  # Thrift (if needed for legacy tools)
volumes:
  - cassandra_data:/var/lib/cassandra
  - ./init-scripts:/docker-entrypoint-initdb.d
environment:
  - CASSANDRA_CLUSTER_NAME=tqdb_cluster
  - CASSANDRA_DC=dc1
  - CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
  - MAX_HEAP_SIZE=2G
  - HEAP_NEWSIZE=512M
resources:
  limits:
    memory: 4G
    cpus: '2'
```

#### Schema Initialization
Create CQL scripts in `init-scripts/`:
- `01-create-keyspace.cql` - Create keyspace with replication
- `02-create-tables.cql` - Create all tables (minbar, secbar, tick, symbol, conf, day)
- `03-create-indexes.cql` - Create necessary indexes

#### Health Check
```yaml
healthcheck:
  test: ["CMD-SHELL", "cqlsh -e 'describe cluster'"]
  interval: 30s
  timeout: 10s
  retries: 5
```

---

## 3. Web UI Modernization

### 3.1 Technology Stack Selection

#### Recommended: **SvelteKit** (Lightweight Option)
**Rationale:**
- Extremely lightweight (minimal runtime overhead)
- Fast build times and excellent performance
- Built-in SSR and API routes
- Easy learning curve
- Modern reactive framework

**Alternative Options:**
- **Next.js** (React-based, more ecosystem support)
- **Nuxt 3** (Vue-based, good DX)
- **Astro** (For content-heavy pages)

### 3.2 Web UI Architecture

```
tqdb-web-ui/
├── Dockerfile
├── package.json
├── svelte.config.js
├── vite.config.js
├── src/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── cassandra.js          # Cassandra client wrapper
│   │   │   ├── query.js              # Query functions
│   │   │   ├── symbol.js             # Symbol management
│   │   │   └── import.js             # Data import functions
│   │   ├── components/
│   │   │   ├── DataGrid.svelte       # Data display grid
│   │   │   ├── ChartView.svelte      # Chart visualization
│   │   │   ├── SymbolSearch.svelte   # Symbol search/filter
│   │   │   ├── ImportForm.svelte     # CSV import form
│   │   │   └── AlertConfig.svelte    # Alert configuration
│   │   ├── stores/
│   │   │   ├── session.js            # Session state
│   │   │   └── preferences.js        # User preferences
│   │   └── utils/
│   │       ├── formatting.js         # Date/number formatting
│   │       ├── validation.js         # Input validation
│   │       └── timezone.js           # Timezone utilities
│   ├── routes/
│   │   ├── +page.svelte              # Dashboard
│   │   ├── +layout.svelte            # Main layout
│   │   ├── api/                      # API routes (compatibility layer)
│   │   │   ├── cgi-bin/
│   │   │   │   ├── q1min.py/+server.js
│   │   │   │   ├── q1sec.py/+server.js
│   │   │   │   ├── eData.py/+server.js
│   │   │   │   └── [...all-other-endpoints]/+server.js
│   │   │   └── v2/                   # New REST API
│   │   │       ├── query/+server.js
│   │   │       ├── symbols/+server.js
│   │   │       └── import/+server.js
│   │   ├── query/
│   │   │   ├── +page.svelte          # Query interface
│   │   │   └── [type]/+page.svelte   # Type-specific queries
│   │   ├── symbols/
│   │   │   ├── +page.svelte          # Symbol list
│   │   │   └── [symbol]/+page.svelte # Symbol detail
│   │   ├── import/
│   │   │   └── +page.svelte          # Import interface
│   │   ├── alerts/
│   │   │   └── +page.svelte          # Alert management
│   │   └── system/
│   │       └── +page.svelte          # System info
│   └── app.html                      # HTML template
├── static/
│   └── favicon.png
└── tests/
    ├── unit/
    └── integration/
```

### 3.3 UI Container Specifications

#### Dockerfile
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json ./
RUN npm ci --production
ENV NODE_ENV=production
ENV PORT=3000
EXPOSE 3000
CMD ["node", "build"]
```

#### Container Configuration
```yaml
container_name: tqdb-web-ui
ports:
  - "3000:3000"
environment:
  - CASSANDRA_HOSTS=tqdb-cassandra
  - CASSANDRA_PORT=9042
  - CASSANDRA_KEYSPACE=tqdb1
  - NODE_ENV=production
depends_on:
  - tqdb-cassandra
volumes:
  - ./logs:/app/logs
  - import_data:/app/data
resources:
  limits:
    memory: 512M
    cpus: '1'
```

### 3.4 Key Features

#### Dashboard
- Real-time data overview
- System status monitoring
- Quick access to common queries
- Recent alerts and notifications

#### Query Interface
- Multi-timeframe query (1min, 1sec, 1day, tick)
- Date/time range picker with timezone support
- Symbol search with autocomplete
- Export to CSV/JSON
- Chart visualization (using Chart.js or Lightweight Charts)

#### Symbol Management
- List all symbols with pagination
- Add/edit/delete symbols
- Symbol configuration JSON editor
- Bulk operations

#### Data Import
- CSV file upload with validation
- Progress monitoring
- Error reporting
- History of imports

#### Alert Management
- Configure alert rules
- Mute/unmute symbols
- Test commands
- Alert history

---

## 4. API Compatibility Layer

### 4.1 Compatibility Requirements

All existing CGI-bin endpoints must be preserved to ensure backward compatibility with:
- External integrations
- Legacy clients
- Automated scripts
- Third-party applications

### 4.2 Endpoint Mapping Strategy

#### Implementation Approach: **Dual API System**

1. **Legacy CGI-compatible API** (`/cgi-bin/*`)
   - Exact URL path preservation
   - Same query parameter format
   - Identical response format (JSON/CSV/HTML)
   - Same error handling behavior

2. **Modern REST API** (`/api/v2/*`)
   - RESTful design principles
   - JSON-only responses
   - Better error handling
   - Authentication/authorization ready
   - OpenAPI documentation

### 4.3 API Gateway Container

#### Purpose
- Route legacy CGI requests to modern backend
- Handle authentication/authorization (future)
- Rate limiting and caching
- Request logging and monitoring

#### Technology: **Nginx** (lightweight) or **Traefik** (feature-rich)

#### Nginx Configuration Example
```nginx
# Route legacy CGI paths to web UI API routes
location ~ ^/cgi-bin/(.+)\.py$ {
    proxy_pass http://tqdb-web-ui:3000/api/cgi-bin/$1.py;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Modern API routes
location /api/v2/ {
    proxy_pass http://tqdb-web-ui:3000/api/v2/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# Static web UI
location / {
    proxy_pass http://tqdb-web-ui:3000/;
    proxy_set_header Host $host;
}
```

### 4.4 CGI Endpoint Compatibility Matrix

#### Query Endpoints
| Legacy Endpoint | Method | Parameters | Response | Implementation Priority |
|----------------|--------|------------|----------|------------------------|
| `/cgi-bin/q1min.py` | GET | symbol, BEG, END, csv, timeoffset | JSON/CSV | P0 - Critical |
| `/cgi-bin/q1sec.py` | GET | symbol, BEG, END, csv, timeoffset | JSON/CSV | P0 - Critical |
| `/cgi-bin/q1day.py` | GET | symbol, BEG, END, csv | JSON/CSV | P0 - Critical |
| `/cgi-bin/qtick.py` | GET | symbol, BEG, END, csv | JSON/CSV | P1 - High |
| `/cgi-bin/qquote.py` | GET | symbol | JSON | P1 - High |
| `/cgi-bin/qRange.py` | GET | symbol, BEG, END, table | JSON | P2 - Medium |

#### Symbol Management Endpoints
| Legacy Endpoint | Method | Parameters | Response | Implementation Priority |
|----------------|--------|------------|----------|------------------------|
| `/cgi-bin/qsyminfo.py` | GET | symbol | JSON | P0 - Critical |
| `/cgi-bin/qSymSummery.py` | GET | - | JSON | P1 - High |
| `/cgi-bin/usymbol.py` | POST | symbol, jsonObj | JSON | P1 - High |

#### Data Management Endpoints
| Legacy Endpoint | Method | Parameters | Response | Implementation Priority |
|----------------|--------|------------|----------|------------------------|
| `/cgi-bin/eData.py` | POST | table, symbol, cmd, epochFloatBeg, epochFloatEnd, jsonObj | JSON | P1 - High |
| `/cgi-bin/eConf.py` | POST | confKey, confVal, cmd | JSON | P1 - High |

#### Import Endpoints
| Legacy Endpoint | Method | Parameters | Response | Implementation Priority |
|----------------|--------|------------|----------|------------------------|
| `/cgi-bin/i1min_check.py` | POST | file, sym, tzConv, tzSelect | JSON/HTML | P1 - High |
| `/cgi-bin/i1min_do.py` | POST | importTicket | JSON/HTML | P1 - High |
| `/cgi-bin/i1min_readstatus.py` | GET | importTicket, html | JSON/HTML | P2 - Medium |

#### System Endpoints
| Legacy Endpoint | Method | Parameters | Response | Implementation Priority |
|----------------|--------|------------|----------|------------------------|
| `/cgi-bin/qSystemInfo.py` | GET | - | JSON | P2 - Medium |
| `/cgi-bin/qSupportTZ.py` | GET | - | JSON | P2 - Medium |
| `/cgi-bin/doAction.py` | POST | cmd, params | JSON | P1 - High |

### 4.5 Response Format Compatibility

#### JSON Response Format
Must maintain exact structure:
```javascript
// Success
{
  "Result": "OK",
  "data": [...],
  // other fields as per endpoint
}

// Error
{
  "Result": "Error! <message>"
}
```

#### CSV Response Format
Must maintain:
- Same column order
- Same date/time format
- Same number precision
- Content-Disposition header for downloads

#### HTML Response Format (for import monitoring)
- Meta refresh tags for auto-reload
- Same status message format
- Progress indicators

---

## 5. Tool Scripts Containerization

### 5.1 Tool Scripts Container Architecture

```
tqdb-tools/
├── Dockerfile
├── requirements.txt
├── entrypoint.sh
├── cron/
│   ├── crontab                    # Cron job definitions
│   └── scripts/
│       ├── auto_import.sh         # Wrapper for autoIns2Cass.sh
│       ├── backfill.sh            # Wrapper for backfill jobs
│       └── cleanup.sh             # Data cleanup jobs
├── bin/                           # Compiled C++ tools
│   ├── q1min
│   ├── q1sec
│   ├── q1minsec
│   ├── qtick
│   ├── qquote
│   ├── qsym
│   ├── itick
│   └── updtick
├── python/                        # Python tools
│   ├── Min2Cass.py
│   ├── Sec2Cass.py
│   ├── Sym2Cass.py
│   ├── Min2Day.py
│   ├── TQAlert.py
│   ├── csvtzconv.py
│   ├── formatDT.py
│   └── utils/
│       └── cassandra_helper.py
└── shell/                         # Shell scripts
    ├── autoIns2Cass.sh
    ├── watchdogAutoIns2Cass.sh
    ├── backfillMinSec.sh
    ├── build1MinFromTick.sh
    ├── build1SecFromTick.sh
    ├── dropSymbol.sh
    ├── purgeTick.sh
    └── removeAllBySym.sh
```

### 5.2 Dockerfile for Tools Container

```dockerfile
FROM rockylinux:9 AS builder

# Install build dependencies
RUN dnf install -y gcc-c++ make git \
    cassandra-cpp-driver-devel \
    boost-devel

# Copy and build C++ tools
COPY tools/src /build/src
WORKDIR /build/src
RUN bash _make.sh

FROM rockylinux:9

# Install runtime dependencies
RUN dnf install -y \
    python3 python3-pip \
    cassandra-cpp-driver \
    cronie \
    nc \
    && dnf clean all

# Install Python dependencies
COPY tools/requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy compiled binaries from builder
COPY --from=builder /build/src/q1min /usr/local/bin/
COPY --from=builder /build/src/q1sec /usr/local/bin/
COPY --from=builder /build/src/q1minsec /usr/local/bin/
COPY --from=builder /build/src/qtick /usr/local/bin/
COPY --from=builder /build/src/qquote /usr/local/bin/
COPY --from=builder /build/src/qsym /usr/local/bin/
COPY --from=builder /build/src/itick /usr/local/bin/
COPY --from=builder /build/src/updtick /usr/local/bin/

# Copy tool scripts
COPY tools/*.py /opt/tqdb/tools/
COPY tools/*.sh /opt/tqdb/tools/
COPY tools/cron /opt/tqdb/cron

# Set permissions
RUN chmod +x /opt/tqdb/tools/*.sh \
    && chmod +x /usr/local/bin/*

# Setup cron
RUN crontab /opt/tqdb/cron/crontab

# Create entrypoint
COPY tools/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /opt/tqdb

ENTRYPOINT ["/entrypoint.sh"]
CMD ["crond", "-n"]
```

### 5.3 Container Configuration

```yaml
container_name: tqdb-tools
environment:
  - CASSANDRA_HOST=tqdb-cassandra
  - CASSANDRA_PORT=9042
  - CASSANDRA_KEYSPACE=tqdb1
  - TZ=America/New_York
depends_on:
  tqdb-cassandra:
    condition: service_healthy
volumes:
  - import_data:/data
  - ./oldtick:/oldtick
  - tmp_alerts:/tmp/TQAlert
  - ./logs:/var/log/tqdb
restart: unless-stopped
```

### 5.4 Cron Job Configuration

#### Example Crontab
```cron
# Auto import from CSV files - every 5 minutes
*/5 * * * * /opt/tqdb/cron/scripts/auto_import.sh >> /var/log/tqdb/auto_import.log 2>&1

# Backfill min/sec data - daily at 2 AM
0 2 * * * /opt/tqdb/cron/scripts/backfill.sh >> /var/log/tqdb/backfill.log 2>&1

# Aggregate to daily bars - daily at 3 AM
0 3 * * * python3 /opt/tqdb/tools/Min2Day.py tqdb-cassandra 9042 tqdb1 >> /var/log/tqdb/min2day.log 2>&1

# Cleanup old tick data - weekly on Sunday at 4 AM
0 4 * * 0 /opt/tqdb/tools/purgeTick.sh >> /var/log/tqdb/purge.log 2>&1

# TQAlert monitoring - runs continuously
@reboot python3 /opt/tqdb/tools/TQAlert.py --config /opt/tqdb/config/tqalert.json >> /var/log/tqdb/tqalert.log 2>&1
```

### 5.5 TQAlert Monitoring Service

#### Running as Supervised Process
Use **supervisord** instead of cron for TQAlert:

```ini
[program:tqalert]
command=python3 /opt/tqdb/tools/TQAlert.py --config /opt/tqdb/config/tqalert.json
directory=/opt/tqdb/tools
autostart=true
autorestart=true
stderr_logfile=/var/log/tqdb/tqalert.err.log
stdout_logfile=/var/log/tqdb/tqalert.out.log
```

---

## 6. Data Migration Strategy

### 6.1 Migration Phases

#### Phase 1: Schema Migration
1. Export schema from existing Cassandra
2. Create initialization CQL scripts
3. Validate schema in containerized Cassandra

#### Phase 2: Data Export
```bash
# Export each table using COPY command
cqlsh -e "COPY tqdb1.minbar TO '/backup/minbar.csv'"
cqlsh -e "COPY tqdb1.secbar TO '/backup/secbar.csv'"
cqlsh -e "COPY tqdb1.tick TO '/backup/tick.csv'"
cqlsh -e "COPY tqdb1.symbol TO '/backup/symbol.csv'"
cqlsh -e "COPY tqdb1.conf TO '/backup/conf.csv'"
cqlsh -e "COPY tqdb1.day TO '/backup/day.csv'"
```

#### Phase 3: Data Import
```bash
# Import to containerized Cassandra
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.minbar FROM '/backup/minbar.csv'"
docker exec tqdb-cassandra cqlsh -e "COPY tqdb1.secbar FROM '/backup/secbar.csv'"
# ... continue for all tables
```

#### Phase 4: Data Validation
- Row count comparison
- Sample data verification
- Query performance testing

### 6.2 Zero-Downtime Migration Option

#### Using Dual-Write Strategy
1. Run old and new systems in parallel
2. Write to both systems temporarily
3. Verify data consistency
4. Switch reads to new system
5. Decommission old system

#### Using Cassandra Replication
1. Add containerized Cassandra as new node to cluster
2. Let data replicate naturally
3. Decommission old node
4. Reconfigure application connections

### 6.3 Rollback Strategy

#### Keep Old System Available
- Maintain old Cassandra installation during transition
- Keep backup of exported data
- Document rollback procedures
- Test rollback process before cutover

---

## 7. Deployment Architecture

### 7.1 Docker Compose Configuration

#### Main `docker-compose.yml`

```yaml
version: '3.8'

services:
  cassandra:
    image: cassandra:4.1
    container_name: tqdb-cassandra
    ports:
      - "9042:9042"
      - "9160:9160"
    environment:
      - CASSANDRA_CLUSTER_NAME=tqdb_cluster
      - CASSANDRA_DC=dc1
      - CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
      - MAX_HEAP_SIZE=2G
      - HEAP_NEWSIZE=512M
    volumes:
      - cassandra_data:/var/lib/cassandra
      - ./docker/cassandra/init-scripts:/docker-entrypoint-initdb.d
      - ./docker/cassandra/cassandra.yaml:/etc/cassandra/cassandra.yaml
    healthcheck:
      test: ["CMD-SHELL", "cqlsh -e 'describe cluster'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s
    networks:
      - tqdb-network
    restart: unless-stopped

  web-ui:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
    container_name: tqdb-web-ui
    ports:
      - "3000:3000"
    environment:
      - CASSANDRA_HOSTS=cassandra
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - NODE_ENV=production
      - LOG_LEVEL=info
    depends_on:
      cassandra:
        condition: service_healthy
    volumes:
      - import_data:/app/data
      - ./logs/web-ui:/app/logs
    networks:
      - tqdb-network
    restart: unless-stopped

  api-gateway:
    image: nginx:alpine
    container_name: tqdb-api-gateway
    ports:
      - "8080:80"
      - "8443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/conf.d:/etc/nginx/conf.d
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - web-ui
    networks:
      - tqdb-network
    restart: unless-stopped

  tools:
    build:
      context: .
      dockerfile: ./docker/tools/Dockerfile
    container_name: tqdb-tools
    environment:
      - CASSANDRA_HOST=cassandra
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - TZ=America/New_York
    depends_on:
      cassandra:
        condition: service_healthy
    volumes:
      - import_data:/data
      - ./oldtick:/oldtick
      - tmp_alerts:/tmp/TQAlert
      - ./logs/tools:/var/log/tqdb
      - ./config/tqalert.json:/opt/tqdb/config/tqalert.json
    networks:
      - tqdb-network
    restart: unless-stopped

volumes:
  cassandra_data:
    driver: local
  import_data:
    driver: local
  tmp_alerts:
    driver: local

networks:
  tqdb-network:
    driver: bridge
```

#### Development Override `docker-compose.dev.yml`

```yaml
version: '3.8'

services:
  web-ui:
    build:
      target: development
    environment:
      - NODE_ENV=development
    volumes:
      - ./web-ui/src:/app/src
      - ./web-ui/static:/app/static
    command: npm run dev -- --host
    ports:
      - "3000:3000"
      - "5173:5173"  # Vite HMR

  cassandra:
    environment:
      - MAX_HEAP_SIZE=512M
      - HEAP_NEWSIZE=128M
    deploy:
      resources:
        limits:
          memory: 1G
```

### 7.2 Directory Structure

```
tqdb/
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── .env.example
├── .env
├── Makefile
├── README.md
├── REFACTOR_PLAN.md (this document)
├── docker/
│   ├── cassandra/
│   │   ├── Dockerfile (if custom build needed)
│   │   ├── cassandra.yaml
│   │   └── init-scripts/
│   │       ├── 01-create-keyspace.cql
│   │       ├── 02-create-tables.cql
│   │       └── 03-create-indexes.cql
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── conf.d/
│   │       └── tqdb.conf
│   └── tools/
│       ├── Dockerfile
│       ├── entrypoint.sh
│       └── supervisord.conf
├── web-ui/
│   ├── Dockerfile
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.js
│   ├── src/
│   ├── static/
│   └── tests/
├── config/
│   ├── tqalert.json
│   └── symbols.json
├── scripts/
│   ├── migrate.sh
│   ├── backup.sh
│   ├── restore.sh
│   └── health-check.sh
├── logs/
│   ├── cassandra/
│   ├── web-ui/
│   ├── nginx/
│   └── tools/
├── data/
│   ├── import/
│   └── export/
└── tests/
    ├── integration/
    └── e2e/
```

### 7.3 Environment Configuration

#### `.env` file
```bash
# Cassandra Configuration
CASSANDRA_VERSION=4.1
CASSANDRA_CLUSTER_NAME=tqdb_cluster
CASSANDRA_KEYSPACE=tqdb1
CASSANDRA_REPLICATION_FACTOR=1

# Resource Limits
CASSANDRA_MAX_HEAP=2G
CASSANDRA_HEAP_NEWSIZE=512M

# Web UI Configuration
NODE_ENV=production
WEB_UI_PORT=3000
API_GATEWAY_PORT=8080

# Timezone
TZ=America/New_York

# Logging
LOG_LEVEL=info

# Alert Configuration
TQALERT_ENABLED=true
TQALERT_CONFIG_FILE=/opt/tqdb/config/tqalert.json

# Data Directories
DATA_IMPORT_DIR=/data/import
DATA_EXPORT_DIR=/data/export
OLDTICK_DIR=/oldtick
```

### 7.4 Makefile for Common Operations

```makefile
.PHONY: help build up down restart logs clean migrate backup restore test

help:
	@echo "TQDB Container Management"
	@echo "========================"
	@echo "make build      - Build all containers"
	@echo "make up         - Start all services"
	@echo "make down       - Stop all services"
	@echo "make restart    - Restart all services"
	@echo "make logs       - View logs (ctrl+c to exit)"
	@echo "make clean      - Remove all containers and volumes"
	@echo "make migrate    - Run data migration"
	@echo "make backup     - Backup Cassandra data"
	@echo "make restore    - Restore Cassandra data"
	@echo "make test       - Run integration tests"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf logs/*

migrate:
	./scripts/migrate.sh

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh

test:
	./scripts/test.sh

dev:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 8. Development Roadmap

### 8.1 Phase 1: Foundation (Weeks 1-2)

#### Objectives
- Set up containerized Cassandra
- Create schema initialization scripts
- Establish Docker Compose configuration

#### Tasks
- [ ] Create Docker Compose configuration
- [ ] Write Cassandra initialization scripts
- [ ] Set up volume mounts and networking
- [ ] Test Cassandra connectivity
- [ ] Document setup process
- [ ] Create Makefile for common operations

#### Deliverables
- Working Cassandra container
- Schema initialization automated
- Documentation for local development

### 8.2 Phase 2: Web UI Foundation (Weeks 3-4)

#### Objectives
- Set up SvelteKit project
- Implement Cassandra client wrapper
- Create basic UI layout

#### Tasks
- [ ] Initialize SvelteKit project
- [ ] Set up Cassandra driver integration
- [ ] Create API route structure
- [ ] Implement authentication skeleton (if needed)
- [ ] Create main layout and navigation
- [ ] Set up build and deployment pipeline

#### Deliverables
- Working SvelteKit application
- Cassandra connection established
- Basic UI layout

### 8.3 Phase 3: API Compatibility Layer (Weeks 5-7)

#### Objectives
- Implement all legacy CGI endpoints
- Ensure response format compatibility
- Create comprehensive tests

#### Tasks

**Week 5: Query Endpoints (P0 - Critical)**
- [ ] `/cgi-bin/q1min.py` - 1-minute bar queries
- [ ] `/cgi-bin/q1sec.py` - 1-second bar queries
- [ ] `/cgi-bin/q1day.py` - Daily bar queries
- [ ] `/cgi-bin/qsyminfo.py` - Symbol information
- [ ] Test CSV and JSON output formats
- [ ] Test timezone handling

**Week 6: Management Endpoints (P1 - High)**
- [ ] `/cgi-bin/eData.py` - Data editing
- [ ] `/cgi-bin/eConf.py` - Configuration editing
- [ ] `/cgi-bin/usymbol.py` - Symbol updates
- [ ] `/cgi-bin/doAction.py` - System actions
- [ ] `/cgi-bin/qtick.py` - Tick queries
- [ ] `/cgi-bin/qquote.py` - Quote queries

**Week 7: Import and System Endpoints (P2 - Medium)**
- [ ] `/cgi-bin/i1min_check.py` - Import validation
- [ ] `/cgi-bin/i1min_do.py` - Import execution
- [ ] `/cgi-bin/i1min_readstatus.py` - Import status
- [ ] `/cgi-bin/qSystemInfo.py` - System information
- [ ] `/cgi-bin/qSupportTZ.py` - Timezone support
- [ ] `/cgi-bin/qSymSummery.py` - Symbol summary
- [ ] `/cgi-bin/qRange.py` - Range queries

#### Deliverables
- All legacy endpoints functional
- Integration tests passing
- API documentation

### 8.4 Phase 4: Modern UI Implementation (Weeks 8-10)

#### Objectives
- Build modern user interface
- Implement all features from legacy UI
- Add enhanced features

#### Tasks

**Week 8: Query Interface**
- [ ] Data query form with date/time pickers
- [ ] Symbol search/autocomplete
- [ ] Data grid with sorting/filtering
- [ ] CSV export functionality
- [ ] Chart visualization integration

**Week 9: Management Interfaces**
- [ ] Symbol management page
- [ ] Data editing interface
- [ ] Configuration editor
- [ ] Alert management UI
- [ ] Import wizard

**Week 10: Dashboard and Polish**
- [ ] Dashboard with overview widgets
- [ ] System status monitoring
- [ ] User preferences
- [ ] Responsive design
- [ ] Accessibility improvements

#### Deliverables
- Complete modern UI
- Feature parity with legacy UI
- Enhanced user experience

### 8.5 Phase 5: Tools Containerization (Weeks 11-12)

#### Objectives
- Containerize C++ tools
- Containerize Python scripts
- Set up automation (cron jobs)

#### Tasks

**Week 11: Build and Package Tools**
- [ ] Create multi-stage Dockerfile for C++ tools
- [ ] Build q1min, q1sec, q1minsec
- [ ] Build qtick, qquote, qsym
- [ ] Build itick, updtick
- [ ] Package Python scripts
- [ ] Test all tools in container

**Week 12: Automation Setup**
- [ ] Set up cron jobs in container
- [ ] Configure TQAlert as supervised service
- [ ] Set up logging and monitoring
- [ ] Create health check scripts
- [ ] Test automated workflows

#### Deliverables
- Tools container operational
- All automation working
- Comprehensive logging

### 8.6 Phase 6: Integration and Testing (Weeks 13-14)

#### Objectives
- End-to-end integration testing
- Performance testing
- Load testing

#### Tasks
- [ ] Integration test suite
- [ ] API compatibility tests
- [ ] Performance benchmarking
- [ ] Load testing (concurrent users)
- [ ] Data migration testing
- [ ] Rollback procedure testing

#### Deliverables
- Comprehensive test suite
- Performance baseline established
- Migration procedures validated

### 8.7 Phase 7: Documentation and Migration (Weeks 15-16)

#### Objectives
- Complete documentation
- Execute production migration
- Decommission old system

#### Tasks
- [ ] User documentation
- [ ] API documentation (OpenAPI)
- [ ] Deployment guide
- [ ] Migration runbook
- [ ] Execute production migration
- [ ] Monitor new system
- [ ] Decommission old system

#### Deliverables
- Complete documentation
- Production system migrated
- Old system archived

---

## 9. Testing Strategy

### 9.1 Unit Tests

#### Web UI Components
- Component rendering tests
- API function tests
- Utility function tests
- State management tests

**Framework**: Vitest + Testing Library

#### Python Tools
- Function-level tests
- Data validation tests
- Cassandra interaction mocks

**Framework**: pytest

### 9.2 Integration Tests

#### API Endpoint Tests
- Request/response validation
- Database interaction
- Error handling
- Authentication/authorization

#### Data Flow Tests
- Import workflows
- Query pipelines
- Alert triggers
- Cron job execution

### 9.3 E2E Tests

#### User Workflows
- Login and navigation
- Data query and export
- Symbol management
- Data import
- Alert configuration

**Framework**: Playwright or Cypress

### 9.4 Compatibility Tests

#### Legacy API Tests
- Endpoint URL preservation
- Parameter handling
- Response format matching
- Error message consistency

**Test Data**: Captured requests from production system

### 9.5 Performance Tests

#### Load Testing
- Concurrent user simulation
- Query performance under load
- Import throughput
- Resource utilization

**Tools**: Apache JMeter or k6

#### Benchmark Targets
- Query response time: < 200ms (p95)
- Import throughput: > 1000 rows/sec
- Concurrent users: 50+
- Container memory: < 4GB total

---

## 10. Rollback Plan

### 10.1 Rollback Triggers

Execute rollback if:
- Critical bugs affecting data integrity
- Performance degradation > 50%
- Unrecoverable system failures
- Migration data loss detected

### 10.2 Rollback Procedure

#### Step 1: Stop New System (5 minutes)
```bash
make down
```

#### Step 2: Verify Old System (10 minutes)
```bash
# Check Cassandra status
systemctl status cassandra

# Check httpd status
systemctl status httpd

# Verify data accessibility
cqlsh -e "SELECT COUNT(*) FROM tqdb1.minbar"
```

#### Step 3: Restore Old Configuration (15 minutes)
```bash
# Restore Apache config if modified
sudo cp /backup/httpd.conf /etc/httpd/conf/httpd.conf
sudo systemctl restart httpd

# Restore cron jobs if modified
crontab /backup/crontab.bak
```

#### Step 4: Data Reconciliation (30-60 minutes)
```bash
# If data written to new system during transition
./scripts/sync-data-from-docker.sh
```

#### Step 5: Communication
- Notify stakeholders
- Document rollback reason
- Update status pages

### 10.3 Rollback Testing

- Practice rollback procedures quarterly
- Maintain rollback documentation
- Automate rollback scripts
- Test data synchronization

---

## 11. Risk Assessment and Mitigation

### 11.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss during migration | Critical | Low | Multiple backups, validation scripts, parallel run |
| API compatibility issues | High | Medium | Comprehensive compatibility tests, gradual rollout |
| Performance degradation | High | Medium | Load testing, resource monitoring, optimization |
| Container orchestration complexity | Medium | Low | Use proven tools (Docker Compose), thorough documentation |
| C++ tool build issues | Medium | Medium | Multi-stage builds, tested build scripts |
| Cassandra configuration errors | High | Low | Use official image, tested init scripts |

### 11.2 Operational Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Learning curve for team | Medium | High | Training sessions, comprehensive documentation |
| Deployment complexity | Medium | Medium | Automated deployment scripts, clear runbooks |
| Monitoring gaps | Medium | Medium | Comprehensive logging, health checks, alerts |
| Resource constraints | Medium | Low | Resource limits in Docker Compose, monitoring |

### 11.3 Business Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Downtime during migration | High | Medium | Planned maintenance window, parallel run option |
| External integration breakage | High | Low | API compatibility layer, extensive testing |
| User resistance to new UI | Medium | Medium | Training, feedback loop, gradual rollout |

---

## 12. Success Criteria

### 12.1 Functional Requirements

- ✅ All legacy CGI endpoints operational
- ✅ Data query functionality identical
- ✅ Import workflows functional
- ✅ Alert system operational
- ✅ Automated jobs running
- ✅ All C++ tools working

### 12.2 Performance Requirements

- ✅ Query response time < 200ms (p95)
- ✅ Support 50+ concurrent users
- ✅ Import throughput > 1000 rows/sec
- ✅ Container startup < 2 minutes
- ✅ Total memory usage < 4GB

### 12.3 Operational Requirements

- ✅ One-command deployment (`make up`)
- ✅ Automated backups configured
- ✅ Health checks functional
- ✅ Logging centralized
- ✅ Documentation complete

### 12.4 Quality Requirements

- ✅ Unit test coverage > 80%
- ✅ Integration tests passing
- ✅ E2E tests passing
- ✅ Zero critical bugs
- ✅ Security scan passing

---

## 13. Future Enhancements

### 13.1 Short-term (3-6 months)

- **Authentication/Authorization**: Add user management and access control
- **Real-time Data**: WebSocket support for live data streaming
- **Advanced Charting**: Integration with TradingView or similar
- **Mobile App**: React Native or Flutter mobile client
- **API Rate Limiting**: Protect against abuse
- **Caching Layer**: Redis for frequently accessed data

### 13.2 Medium-term (6-12 months)

- **Kubernetes Deployment**: Migrate from Docker Compose to K8s
- **Multi-node Cassandra**: Cluster setup for high availability
- **GraphQL API**: Modern query language option
- **Machine Learning**: Anomaly detection in data
- **Data Analytics**: Built-in analytics and reporting
- **Backup Automation**: S3/cloud backup integration

### 13.3 Long-term (12+ months)

- **Multi-tenancy**: Support multiple isolated databases
- **Cloud-native**: Deployment on AWS/GCP/Azure
- **Microservices**: Further decomposition for scalability
- **Event Streaming**: Kafka integration for real-time processing
- **Advanced Monitoring**: Prometheus + Grafana dashboards
- **Disaster Recovery**: Multi-region deployment

---

## 14. Conclusion

This refactoring plan transforms TQDB from a traditional monolithic application into a modern, containerized microservices architecture while maintaining complete backward compatibility. The phased approach minimizes risk and allows for iterative improvements.

### Key Benefits

1. **Simplified Deployment**: One-command deployment with Docker Compose
2. **Modern UI**: Better user experience with SvelteKit
3. **Maintainability**: Cleaner code structure, easier to modify
4. **Scalability**: Container-based architecture supports horizontal scaling
5. **Development Efficiency**: Faster local development setup
6. **Backward Compatibility**: Zero disruption to existing integrations

### Next Steps

1. **Review and Approval**: Stakeholder review of this plan
2. **Team Formation**: Assign developers to each phase
3. **Environment Setup**: Prepare development infrastructure
4. **Kickoff**: Begin Phase 1 implementation

### Timeline Summary

- **Total Duration**: 16 weeks (4 months)
- **Team Size**: 2-3 developers recommended
- **Parallel Work**: Web UI and tools containerization can overlap
- **Buffer**: Add 20% contingency for unforeseen issues

---

## Appendix

### A. Reference Documentation

- [Cassandra Docker Official Image](https://hub.docker.com/_/cassandra)
- [SvelteKit Documentation](https://kit.svelte.dev/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Cassandra Driver Python](https://docs.datastax.com/en/developer/python-driver/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)

### B. Contact and Support

- **Project Lead**: TBD
- **Technical Lead**: TBD
- **DevOps Lead**: TBD

### C. Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-16 | GitHub Copilot | Initial refactor plan |

---

**Document Status**: Draft for Review  
**Last Updated**: February 16, 2026  
**Review Cycle**: Quarterly  

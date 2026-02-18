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
- **Cluster-ready**: Each node can join a multi-machine cluster
- **Single entry point**: Applications use Cassandra driver's built-in load balancing

#### Cluster Architecture Options

**Option 1: Single-Node Deployment (Development/Small Production)**
- One machine, one Docker Compose, one Cassandra node
- No high availability, simplest setup
- Suitable for development or low-traffic production

**Option 2: Multi-Node Cluster (Recommended for Production)**
- Multiple machines, each running one Docker Compose with one Cassandra node
- Nodes discover each other via seed nodes
- Applications connect to any node; Cassandra driver handles load balancing
- High availability with configurable replication factor (RF=3 recommended)

#### Container Specifications (Single Node)
```yaml
container_name: tqdb-cassandra
ports:
  - "9042:9042"  # CQL native transport
  - "7000:7000"  # Inter-node communication (cluster)
  - "7001:7001"  # Inter-node communication (SSL, optional)
  - "9160:9160"  # Thrift (if needed for legacy tools)
volumes:
  - cassandra_data:/var/lib/cassandra
  - ./docker/cassandra/cassandra.yaml:/etc/cassandra/cassandra.yaml
  - ./init-scripts:/docker-entrypoint-initdb.d
environment:
  - CASSANDRA_CLUSTER_NAME=tqdb_cluster
  - CASSANDRA_DC=dc1
  - CASSANDRA_RACK=rack1
  - CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
  - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11,192.168.1.12  # Seed node IPs
  - CASSANDRA_BROADCAST_ADDRESS=${HOST_IP}  # This node's external IP
  - CASSANDRA_LISTEN_ADDRESS=0.0.0.0  # Listen on all interfaces
  - MAX_HEAP_SIZE=2G
  - HEAP_NEWSIZE=512M
network_mode: host  # For cross-machine cluster communication
resources:
  limits:
    memory: 4G
    cpus: '2'
```

**Note**: For single-node deployment, remove `CASSANDRA_SEEDS` or set it to the local node IP.

#### Schema Initialization
Create CQL scripts in `init-scripts/`:
- `01-create-keyspace.cql` - Create keyspace with replication strategy
- `02-create-tables.cql` - Create all tables (minbar, secbar, tick, symbol, conf, day)
- `03-create-indexes.cql` - Create necessary indexes

**Single-Node Keyspace Example:**
```cql
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH replication = {
  'class': 'SimpleStrategy', 
  'replication_factor': 1
};
```

**Multi-Node Cluster Keyspace Example:**
```cql
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH replication = {
  'class': 'NetworkTopologyStrategy', 
  'dc1': 3  -- 3 replicas in datacenter dc1
};
```

#### Application Connection Strategy

**Cassandra Driver Configuration (Python/Node.js)**

The key insight is that Cassandra drivers have built-in cluster awareness and load balancing. Applications only need to specify **seed nodes** for initial discovery, then the driver automatically:
- Discovers all cluster nodes
- Load balances queries across healthy nodes
- Handles failover automatically
- Maintains connection pools to all nodes

**Python Example (cassandra-driver):**
```python
from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy

# Specify 2-3 seed nodes for discovery (not all nodes)
cluster = Cluster(
    contact_points=['192.168.1.10', '192.168.1.11', '192.168.1.12'],
    port=9042,
    load_balancing_policy=DCAwareRoundRobinPolicy(local_dc='dc1'),
    protocol_version=4
)
session = cluster.connect('tqdb1')

# Driver automatically discovers all nodes and load balances
# No need for external load balancer!
```

**Node.js Example (cassandra-driver):**
```javascript
const cassandra = require('cassandra-driver');

const client = new cassandra.Client({
  contactPoints: ['192.168.1.10', '192.168.1.11', '192.168.1.12'],
  localDataCenter: 'dc1',
  keyspace: 'tqdb1',
  pooling: {
    coreConnectionsPerHost: {
      [cassandra.types.distance.local]: 2,
      [cassandra.types.distance.remote]: 1
    }
  }
});

await client.connect();
// Client automatically discovers topology and load balances
```

**Environment Variable Configuration:**
```bash
# In docker-compose.yml or .env
CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
CASSANDRA_LOCAL_DC=dc1
CASSANDRA_KEYSPACE=tqdb1
```

This means:
- ✅ **No external load balancer needed** (HAProxy, Nginx, etc.)
- ✅ **Automatic failover** if a node goes down
- ✅ **Query distribution** across all healthy nodes
- ✅ **Topology awareness** (prefers local datacenter)
- ✅ **Connection pooling** built-in

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
  - CASSANDRA_CONTACT_POINTS=cassandra  # Single-node: local cassandra
  # For multi-node cluster, use: 192.168.1.10,192.168.1.11,192.168.1.12
  - CASSANDRA_LOCAL_DC=dc1
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

**Note**: For multi-node clusters, update `CASSANDRA_CONTACT_POINTS` to list 2-3 seed node IPs from different machines.

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

### 7.1 Deployment Patterns

#### Pattern 1: Single-Node Development/Testing

```
┌─────────────────────────────────────┐
│        Single Machine               │
│  ┌──────────────────────────────┐  │
│  │   Docker Compose Stack       │  │
│  │  ┌────────┐  ┌─────────┐    │  │
│  │  │Cassandra│ │ Web UI  │    │  │
│  │  │  (RF=1) │ │  + API  │    │  │
│  │  └────────┘  └─────────┘    │  │
│  │  ┌─────────┐                 │  │
│  │  │  Tools  │                 │  │
│  │  └─────────┘                 │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Use Case**: Development, testing, small deployments  
**High Availability**: None  
**Replication**: RF=1 (SimpleStrategy)

#### Pattern 2: Multi-Node Cluster (Recommended for Production)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Cassandra Cluster (RF=3)                       │
│                                                                    │
│  Machine 1               Machine 2               Machine 3        │
│  192.168.1.10           192.168.1.11           192.168.1.12      │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐  │
│  │   Docker    │        │   Docker    │        │   Docker    │  │
│  │  Compose    │        │  Compose    │        │  Compose    │  │
│  │             │        │             │        │             │  │
│  │ ┌─────────┐ │        │ ┌─────────┐ │        │ ┌─────────┐ │  │
│  │ │Cassandra│ │◄──────►│ │Cassandra│ │◄──────►│ │Cassandra│ │  │
│  │ │  Seed   │ │ Gossip │ │  Seed   │ │ Gossip │ │  Node   │ │  │
│  │ └─────────┘ │        │ └─────────┘ │        │ └─────────┘ │  │
│  │ ┌─────────┐ │        │ ┌─────────┐ │        │ ┌─────────┐ │  │
│  │ │ Web UI  │ │        │ │ Web UI  │ │        │ │ Web UI  │ │  │
│  │ │   API   │ │        │ │   API   │ │        │ │   API   │ │  │
│  │ └─────────┘ │        │ └─────────┘ │        │ └─────────┘ │  │
│  │ ┌─────────┐ │        │ ┌─────────┐ │        │ ┌─────────┐ │  │
│  │ │  Tools  │ │        │ │  Tools  │ │        │ │  Tools  │ │  │
│  │ └─────────┘ │        │ └─────────┘ │        │ └─────────┘ │  │
│  └─────────────┘        └─────────────┘        └─────────────┘  │
│         │                       │                       │         │
│         └───────────────────────┴───────────────────────┘         │
│                                 │                                  │
│                   Application connections use                     │
│                   Cassandra driver's built-in                     │
│                   load balancing (no external LB)                 │
└──────────────────────────────────────────────────────────────────┘
```

**Use Case**: Production with high availability  
**High Availability**: Yes (can lose 1 node with RF=3)  
**Replication**: RF=3 (NetworkTopologyStrategy)  
**Load Balancing**: Built into Cassandra drivers (no HAProxy/Nginx needed)

#### Pattern 3: Hybrid (API on Separate Machines)

```
┌────────────────────────────────────────────────────────────┐
│              Cassandra Data Cluster (RF=3)                 │
│  Machine 1            Machine 2            Machine 3       │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐    │
│  │Cassandra │◄──────►│Cassandra │◄──────►│Cassandra │    │
│  │  + Tools │        │  + Tools │        │  + Tools │    │
│  └──────────┘        └──────────┘        └──────────┘    │
└─────────┬──────────────────┬──────────────────┬───────────┘
          │                  │                  │
          │   Contact Points: 192.168.1.10,11,12│
          │                  │                  │
┌─────────┴──────────────────┴──────────────────┴───────────┐
│              Application/Web UI Cluster                    │
│  Machine 4            Machine 5            Machine 6       │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐    │
│  │  Web UI  │        │  Web UI  │        │  Web UI  │    │
│  │   API    │        │   API    │        │   API    │    │
│  └──────────┘        └──────────┘        └──────────┘    │
│       │                   │                   │            │
│       └───────────────────┴───────────────────┘            │
│                    Load Balancer                           │
│                   (Nginx/HAProxy)                          │
└────────────────────────────────────────────────────────────┘
```

**Use Case**: Separate compute/storage scaling  
**Benefits**: Independent scaling of API and database tiers

### 7.2 Docker Compose Configuration

### 7.2 Docker Compose Configuration

#### Single-Node `docker-compose.yml`

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
      - CASSANDRA_RACK=rack1
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
      - CASSANDRA_CONTACT_POINTS=cassandra
      - CASSANDRA_LOCAL_DC=dc1
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
      - CASSANDRA_CONTACT_POINTS=cassandra
      - CASSANDRA_LOCAL_DC=dc1
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

#### Multi-Node Cluster `docker-compose.cluster.yml`

**Machine 1 (Node 1 - Seed) - 192.168.1.10:**
```yaml
version: '3.8'

services:
  cassandra:
    image: cassandra:4.1
    container_name: tqdb-cassandra-node1
    hostname: cassandra-node1
    environment:
      - CASSANDRA_CLUSTER_NAME=tqdb_cluster
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack1
      - CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
      - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
      - CASSANDRA_BROADCAST_ADDRESS=192.168.1.10
      - CASSANDRA_LISTEN_ADDRESS=0.0.0.0
      - CASSANDRA_RPC_ADDRESS=0.0.0.0
      - MAX_HEAP_SIZE=2G
      - HEAP_NEWSIZE=512M
    volumes:
      - cassandra_data:/var/lib/cassandra
      - ./docker/cassandra/cassandra.yaml:/etc/cassandra/cassandra.yaml
      - ./docker/cassandra/init-scripts:/docker-entrypoint-initdb.d
    network_mode: host
    restart: unless-stopped

  web-ui:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
    container_name: tqdb-web-ui
    ports:
      - "3000:3000"
    environment:
      - CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
      - CASSANDRA_LOCAL_DC=dc1
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - NODE_ENV=production
    restart: unless-stopped

  tools:
    build:
      context: .
      dockerfile: ./docker/tools/Dockerfile
    container_name: tqdb-tools
    environment:
      - CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
      - CASSANDRA_LOCAL_DC=dc1
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - TZ=America/New_York
    volumes:
      - import_data:/data
      - ./oldtick:/oldtick
      - tmp_alerts:/tmp/TQAlert
      - ./logs/tools:/var/log/tqdb
      - ./config/tqalert.json:/opt/tqdb/config/tqalert.json
    restart: unless-stopped

volumes:
  cassandra_data:
  import_data:
  tmp_alerts:
```

**Machine 2 (Node 2 - Seed) - 192.168.1.11:**
```yaml
version: '3.8'

services:
  cassandra:
    image: cassandra:4.1
    container_name: tqdb-cassandra-node2
    hostname: cassandra-node2
    environment:
      - CASSANDRA_CLUSTER_NAME=tqdb_cluster
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack2
      - CASSANDRA_ENDPOINT_SNITCH=GossipingPropertyFileSnitch
      - CASSANDRA_SEEDS=192.168.1.10,192.168.1.11
      - CASSANDRA_BROADCAST_ADDRESS=192.168.1.11
      - CASSANDRA_LISTEN_ADDRESS=0.0.0.0
      - CASSANDRA_RPC_ADDRESS=0.0.0.0
      - MAX_HEAP_SIZE=2G
      - HEAP_NEWSIZE=512M
    volumes:
      - cassandra_data:/var/lib/cassandra
      - ./docker/cassandra/cassandra.yaml:/etc/cassandra/cassandra.yaml
    network_mode: host
    restart: unless-stopped

  web-ui:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
    container_name: tqdb-web-ui
    ports:
      - "3000:3000"
    environment:
      - CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
      - CASSANDRA_LOCAL_DC=dc1
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - NODE_ENV=production
    restart: unless-stopped

  tools:
    build:
      context: .
      dockerfile: ./docker/tools/Dockerfile
    container_name: tqdb-tools
    environment:
      - CASSANDRA_CONTACT_POINTS=192.168.1.10,192.168.1.11,192.168.1.12
      - CASSANDRA_LOCAL_DC=dc1
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - TZ=America/New_York
    volumes:
      - import_data:/data
      - ./oldtick:/oldtick
      - tmp_alerts:/tmp/TQAlert
      - ./logs/tools:/var/log/tqdb
      - ./config/tqalert.json:/opt/tqdb/config/tqalert.json
    restart: unless-stopped

volumes:
  cassandra_data:
  import_data:
  tmp_alerts:
```

**Machine 3 (Node 3 - Regular Node) - 192.168.1.12:**
```yaml
# Similar to Node 2, with:
# - CASSANDRA_BROADCAST_ADDRESS=192.168.1.12
# - CASSANDRA_RACK=rack3
# - Same CASSANDRA_SEEDS as other nodes
```

**Key Configuration Notes:**

1. **network_mode: host** - Required for Cassandra cluster communication across machines
2. **CASSANDRA_SEEDS** - List 2-3 seed nodes (not all nodes)
3. **CASSANDRA_BROADCAST_ADDRESS** - Each node's externally reachable IP
4. **CASSANDRA_RACK** - Different racks for better replica distribution
5. **CASSANDRA_CONTACT_POINTS** - Applications list 2-3 seed nodes for discovery

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
# Deployment Mode: single-node or cluster
DEPLOYMENT_MODE=single-node

# Cassandra Configuration
CASSANDRA_VERSION=4.1
CASSANDRA_CLUSTER_NAME=tqdb_cluster
CASSANDRA_KEYSPACE=tqdb1

# For single-node deployment
CASSANDRA_REPLICATION_STRATEGY=SimpleStrategy
CASSANDRA_REPLICATION_FACTOR=1

# For multi-node cluster deployment
# CASSANDRA_REPLICATION_STRATEGY=NetworkTopologyStrategy
# CASSANDRA_REPLICATION_FACTOR=3

# Cassandra Contact Points (for applications)
# Single-node: cassandra
# Multi-node: 192.168.1.10,192.168.1.11,192.168.1.12
CASSANDRA_CONTACT_POINTS=cassandra
CASSANDRA_LOCAL_DC=dc1

# This node's configuration (for cluster mode)
# HOST_IP=192.168.1.10  # Set on each machine
# CASSANDRA_SEEDS=192.168.1.10,192.168.1.11  # Same on all machines

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

### 7.4 Cassandra Cluster Setup Guide

#### Prerequisites

1. **Network Requirements:**
   - All machines must be able to reach each other on ports 7000, 7001, 9042
   - Firewalls configured to allow inter-node communication
   - Stable, low-latency network connection

2. **Machine Requirements:**
   - Same Cassandra version on all nodes
   - Time synchronization (NTP/Chrony)
   - Sufficient resources (minimum 4GB RAM per node)

#### Step-by-Step Cluster Setup

**Step 1: Prepare Configuration Files**

Create `docker/cassandra/cassandra.yaml` with cluster settings:
```yaml
# Critical settings for clustering
cluster_name: 'tqdb_cluster'
num_tokens: 256
endpoint_snitch: GossipingPropertyFileSnitch

# Will be overridden by environment variables
seed_provider:
  - class_name: org.apache.cassandra.locator.SimpleSeedProvider
    parameters:
      - seeds: "${CASSANDRA_SEEDS}"

listen_address: ${CASSANDRA_LISTEN_ADDRESS}
broadcast_address: ${CASSANDRA_BROADCAST_ADDRESS}
rpc_address: ${CASSANDRA_RPC_ADDRESS}
```

**Step 2: Deploy First Seed Node (192.168.1.10)**

```bash
# On Machine 1
export HOST_IP=192.168.1.10
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra

# Wait for node to be ready (2-3 minutes)
docker exec tqdb-cassandra-node1 nodetool status
```

**Step 3: Deploy Second Seed Node (192.168.1.11)**

```bash
# On Machine 2
export HOST_IP=192.168.1.11
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra

# Wait for node to join cluster
docker exec tqdb-cassandra-node2 nodetool status
```

**Step 4: Deploy Additional Nodes (192.168.1.12, etc.)**

```bash
# On Machine 3
export HOST_IP=192.168.1.12
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra

# Verify cluster
docker exec tqdb-cassandra-node3 nodetool status
```

**Step 5: Create Keyspace with Replication**

```bash
# On any node
docker exec -it tqdb-cassandra-node1 cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH replication = {
  'class': 'NetworkTopologyStrategy', 
  'dc1': 3
};"
```

**Step 6: Deploy Applications**

```bash
# On each machine, start web-ui and tools
docker-compose -f docker-compose.cluster.yml up -d web-ui tools
```

#### Cluster Health Check

```bash
# Check cluster status
docker exec tqdb-cassandra-node1 nodetool status

# Expected output:
# Datacenter: dc1
# Status=Up/Down
# State=Normal/Leaving/Joining/Moving
# Address         Load       Tokens  Owns    Host ID   Rack
# UN 192.168.1.10 128 KB     256     33.3%   xxx       rack1
# UN 192.168.1.11 125 KB     256     33.3%   yyy       rack2
# UN 192.168.1.12 130 KB     256     33.4%   zzz       rack3

# Check replication
docker exec tqdb-cassandra-node1 cqlsh -e "DESCRIBE KEYSPACE tqdb1;"

# Test connectivity from application
docker exec tqdb-web-ui node -e "
  const cassandra = require('cassandra-driver');
  const client = new cassandra.Client({
    contactPoints: ['192.168.1.10', '192.168.1.11', '192.168.1.12'],
    localDataCenter: 'dc1'
  });
  client.connect().then(() => {
    console.log('Connected to cluster!');
    client.getState().getConnectedHosts().forEach(h => 
      console.log('Connected to:', h.address)
    );
    client.shutdown();
  });
"
```

#### Application Load Balancing Verification

The Cassandra driver automatically discovers all nodes and load balances. To verify:

```bash
# Python verification
docker exec tqdb-tools python3 -c "
from cassandra.cluster import Cluster

cluster = Cluster(['192.168.1.10', '192.168.1.11', '192.168.1.12'])
session = cluster.connect('tqdb1')

print('Connected to cluster!')
print('Discovered hosts:')
for host in cluster.metadata.all_hosts():
    print(f'  {host.address} - {host.datacenter}/{host.rack}')

cluster.shutdown()
"
```

### 7.5 Cluster Operations

#### Adding a New Node

```bash
# On new machine (192.168.1.13)
export HOST_IP=192.168.1.13
export CASSANDRA_SEEDS=192.168.1.10,192.168.1.11

docker-compose -f docker-compose.cluster.yml up -d cassandra

# Monitor join progress
docker exec tqdb-cassandra-node4 nodetool status
docker exec tqdb-cassandra-node4 nodetool netstats
```

#### Removing a Node

```bash
# Decommission gracefully
docker exec tqdb-cassandra-node3 nodetool decommission

# Wait for completion, then stop
docker-compose -f docker-compose.cluster.yml down
```

#### Cluster Repair (Recommended Monthly)

```bash
# Run repair on each node
docker exec tqdb-cassandra-node1 nodetool repair -pr tqdb1
docker exec tqdb-cassandra-node2 nodetool repair -pr tqdb1
docker exec tqdb-cassandra-node3 nodetool repair -pr tqdb1
```

#### Monitoring Cluster Health

```bash
# Check status
nodetool status

# Check gossip
nodetool gossipinfo

# Check compaction
nodetool compactionstats

# Check performance
nodetool tpstats
```

### 7.6 Makefile for Common Operations

```makefile
.PHONY: help build up down restart logs clean migrate backup restore test cluster-status

help:
	@echo "TQDB Container Management"
	@echo "========================"
	@echo "Single-Node Commands:"
	@echo "  make build      - Build all containers"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs (ctrl+c to exit)"
	@echo ""
	@echo "Cluster Commands:"
	@echo "  make cluster-up     - Start cluster node"
	@echo "  make cluster-status - Check cluster health"
	@echo "  make cluster-repair - Run repair on this node"
	@echo ""
	@echo "Operations:"
	@echo "  make clean      - Remove all containers and volumes"
	@echo "  make migrate    - Run data migration"
	@echo "  make backup     - Backup Cassandra data"
	@echo "  make restore    - Restore Cassandra data"
	@echo "  make test       - Run integration tests"

# Single-node operations
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

# Cluster operations
cluster-up:
	@echo "Starting cluster node with HOST_IP=${HOST_IP}"
	docker-compose -f docker-compose.cluster.yml up -d

cluster-status:
	docker exec tqdb-cassandra-node1 nodetool status

cluster-repair:
	docker exec tqdb-cassandra-node1 nodetool repair -pr tqdb1

cluster-info:
	@echo "=== Cluster Status ==="
	docker exec tqdb-cassandra-node1 nodetool status
	@echo ""
	@echo "=== Ring ==="
	docker exec tqdb-cassandra-node1 nodetool ring
	@echo ""
	@echo "=== Gossip Info ==="
	docker exec tqdb-cassandra-node1 nodetool gossipinfo

# Data operations
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

This refactoring is divided into **two major phases**:
- **Phase 1: Infrastructure & Data Layer** - Set up containerized Cassandra cluster with exchange-specific data distribution
- **Phase 2: Application Layer** - Modernize web UI and tools while maintaining backward compatibility

This phased approach allows you to:
1. ✅ Deploy the new data infrastructure independently
2. ✅ Migrate data without touching the application
3. ✅ Test cluster operations before application changes
4. ✅ Keep the current application running during Phase 1
5. ✅ Reduce overall risk by separating concerns

---

## PHASE 1: Infrastructure & Data Layer Setup

**Duration:** 4-6 weeks  
**Goal:** Deploy production-ready Cassandra cluster with exchange-specific data distribution  
**Risk:** Low - Can run alongside existing system

### Phase 1.1: Single-Node Development Setup (Week 1)

#### Objectives
- Create basic Docker Compose configuration
- Set up single-node Cassandra for development
- Create schema initialization scripts
- Test basic operations

#### Tasks
- [ ] **Create base directory structure**
  ```bash
  mkdir -p docker/{cassandra,nginx,tools}
  mkdir -p config scripts logs data
  ```

- [ ] **Create single-node `docker-compose.yml`**
  - Cassandra container configuration
  - Volume mounts for data persistence
  - Health checks
  - Resource limits

- [ ] **Create Cassandra initialization scripts**
  - `docker/cassandra/init-scripts/01-create-keyspace.cql`
  - `docker/cassandra/init-scripts/02-create-tables.cql`
  - `docker/cassandra/init-scripts/03-create-indexes.cql`

- [ ] **Create schema for single keyspace (tqdb1)**
  - All existing tables (minbar, secbar, tick, symbol, conf, day)
  - Same structure as current system

- [ ] **Test single-node deployment**
  ```bash
  docker-compose up -d
  docker exec tqdb-cassandra cqlsh -e "DESCRIBE KEYSPACE tqdb1"
  ```

- [ ] **Create Makefile for common operations**
  - `make up`, `make down`, `make logs`
  - `make cluster-status`
  - `make backup`, `make restore`

- [ ] **Document single-node setup**
  - README with quick start guide
  - Environment variables documentation

#### Deliverables
- ✅ Working single-node Cassandra in Docker
- ✅ Schema initialized automatically
- ✅ Makefile for operations
- ✅ Development environment ready

**Success Criteria:**
- Can insert and query data via cqlsh
- Container restarts without data loss
- Health checks passing

---

### Phase 1.2: Exchange-Specific Cluster Design (Week 2)

#### Objectives
- Design exchange-specific keyspace strategy
- Create rack-aware configuration
- Prepare for multi-node deployment
- Design data distribution model

#### Tasks
- [ ] **Design keyspace strategy**
  - Decide: Multiple keyspaces vs. single keyspace
  - Recommended: Multiple keyspaces (tqdb_nyse, tqdb_nasdaq, tqdb_hkex)
  - Document replication strategy (NetworkTopologyStrategy, RF=2)

- [ ] **Create exchange-specific schema scripts**
  - `scripts/create-exchange-keyspaces.sh`
  - Keyspace for each exchange
  - Same table structure across keyspaces

- [ ] **Design rack configuration**
  - rack_master - Master node (all data)
  - rack_nyse - NYSE-specific node
  - rack_nasdaq - NASDAQ-specific node
  - rack_hkex - HKEX-specific node

- [ ] **Create `docker-compose.cluster.yml` template**
  - Per-machine configuration
  - Environment variable templating
  - Seed node configuration
  - Rack assignments

- [ ] **Create cluster deployment scripts**
  - `scripts/deploy-cluster-node.sh` - Deploy on one machine
  - `scripts/init-cluster.sh` - Initialize cluster topology
  - `scripts/verify-cluster.sh` - Health check all nodes

- [ ] **Document cluster architecture**
  - Update CLUSTER_ARCHITECTURE.md
  - Network requirements (ports, firewall)
  - Step-by-step deployment guide

#### Deliverables
- ✅ Exchange-specific keyspace design documented
- ✅ Cluster deployment scripts ready
- ✅ Per-machine docker-compose templates
- ✅ Network and rack configuration documented

**Success Criteria:**
- Design reviewed and approved
- All scripts tested in dev environment
- Documentation complete

---

### Phase 1.3: Multi-Node Cluster Deployment (Weeks 3-4)

#### Objectives
- Deploy 3-4 node Cassandra cluster
- Configure exchange-specific data distribution
- Verify data replication
- Test cluster operations

#### Tasks

**Week 3: Cluster Infrastructure**

- [ ] **Deploy Master Node (192.168.1.10)**
  ```bash
  export HOST_IP=192.168.1.10
  export CASSANDRA_RACK=rack_master
  docker-compose -f docker-compose.cluster.yml up -d
  ```

- [ ] **Deploy NYSE Node (192.168.1.11)**
  ```bash
  export HOST_IP=192.168.1.11
  export CASSANDRA_RACK=rack_nyse
  docker-compose -f docker-compose.cluster.yml up -d
  ```

- [ ] **Deploy NASDAQ Node (192.168.1.12)**
  ```bash
  export HOST_IP=192.168.1.12
  export CASSANDRA_RACK=rack_nasdaq
  docker-compose -f docker-compose.cluster.yml up -d
  ```

- [ ] **Deploy HKEX Node (192.168.1.13)** (if applicable)

- [ ] **Verify cluster formation**
  ```bash
  nodetool status
  nodetool ring
  nodetool gossipinfo
  ```

**Week 4: Exchange Keyspace Setup**

- [ ] **Create exchange-specific keyspaces**
  ```bash
  ./scripts/create-exchange-keyspaces.sh
  ```

- [ ] **Verify replication placement**
  ```bash
  nodetool getendpoints tqdb_nyse minbar 'AAPL'
  # Should return: Master + NYSE node
  ```

- [ ] **Test data distribution**
  - Insert test data to tqdb_nyse
  - Verify data on Master node
  - Verify data on NYSE node
  - Verify data NOT on NASDAQ/HKEX nodes

- [ ] **Configure monitoring**
  - Set up nodetool status checks
  - Configure disk space alerts
  - Set up cluster health dashboard (optional)

- [ ] **Document cluster operations**
  - Adding/removing nodes
  - Running repairs
  - Backup/restore procedures

#### Deliverables
- ✅ 3-4 node production cluster running
- ✅ Exchange-specific keyspaces created
- ✅ Data distribution verified
- ✅ Monitoring in place
- ✅ Operations documentation complete

**Success Criteria:**
- All nodes show UN (Up/Normal) in nodetool status
- Data correctly distributed per exchange
- Can insert to any exchange keyspace from any node
- Cluster survives single node failure

---

### Phase 1.4: Data Migration & Tool Integration (Weeks 5-6)

#### Objectives
- Migrate existing data to new cluster
- Containerize existing tools
- Set up backfill procedures
- Run parallel with old system

#### Tasks

**Week 5: Data Migration**

- [ ] **Export data from existing Cassandra**
  ```bash
  ./scripts/export-data.sh
  # Exports: minbar, secbar, tick, symbol, conf, day
  ```

- [ ] **Import data to exchange-specific keyspaces**
  ```bash
  ./scripts/import-data.sh NYSE /backup/nyse_data.csv
  ./scripts/import-data.sh NASDAQ /backup/nasdaq_data.csv
  ./scripts/import-data.sh HKEX /backup/hkex_data.csv
  ```

- [ ] **Verify data integrity**
  - Row count comparison
  - Sample data verification
  - Query performance testing

- [ ] **Run parallel with old system**
  - Dual-write to old and new clusters (optional)
  - Compare query results
  - Monitor for discrepancies

**Week 6: Tool Containerization**

- [ ] **Create tools container image**
  - Dockerfile for C++ tools compilation
  - Python tools and dependencies
  - Shell scripts

- [ ] **Build C++ tools in container**
  - q1min, q1sec, q1minsec
  - qtick, qquote, qsym
  - itick, updtick

- [ ] **Update Python tools for exchange keyspaces**
  - Min2Cass.py → Min2Cass_Exchange.py
  - Sec2Cass.py → Sec2Cass_Exchange.py
  - Update connection logic for multiple keyspaces

- [ ] **Create backfill scripts**
  - `backfill_exchange.py` - Exchange-aware backfill
  - `detect_gaps.py` - Automated gap detection
  - Test backfill procedures

- [ ] **Deploy tools containers on each node**
  ```bash
  docker-compose -f docker-compose.cluster.yml up -d tools
  ```

- [ ] **Set up automated jobs**
  - Cron jobs for data aggregation
  - TQAlert service (if needed)
  - Automated backfill on detection

#### Deliverables
- ✅ All data migrated to new cluster
- ✅ Tools containerized and running
- ✅ Backfill procedures tested
- ✅ Automated jobs configured
- ✅ Running parallel with old system (optional)

**Success Criteria:**
- 100% data migrated successfully
- All tools functional in containers
- Can import new data to exchange keyspaces
- Backfill tested and working
- Old and new systems can run side-by-side

---

### Phase 1 Completion Checklist

Before moving to Phase 2, ensure:

- ✅ Cluster deployed and healthy (all nodes UN)
- ✅ Exchange-specific keyspaces created and tested
- ✅ Data migrated and verified
- ✅ Tools containerized and operational
- ✅ Backfill procedures documented and tested
- ✅ Monitoring and alerting configured
- ✅ Operations runbooks complete
- ✅ Team trained on cluster operations
- ✅ Old system can remain running (if needed)

**Phase 1 Duration:** 4-6 weeks  
**Phase 1 Risk:** Low (infrastructure changes only)  
**Phase 1 Output:** Production-ready Cassandra cluster with exchange-specific data distribution

---

## PHASE 2: Application Layer Modernization

**Duration:** 10-12 weeks  
**Goal:** Modernize web UI and API while maintaining backward compatibility  
**Dependencies:** Phase 1 must be complete

### Phase 2.1: Web UI Foundation (Weeks 1-2)

#### Objectives
- Set up modern web framework (SvelteKit)
- Implement Cassandra client wrapper
- Create basic UI layout
- Test connection to cluster

#### Tasks
- [ ] **Initialize SvelteKit project**
  ```bash
  npm create svelte@latest web-ui
  cd web-ui && npm install
  ```

- [ ] **Set up Cassandra driver integration**
  - Install cassandra-driver package
  - Create connection wrapper
  - Implement exchange-to-keyspace mapping
  - Test multi-keyspace queries

- [ ] **Create API route structure**
  - `/api/cgi-bin/*` - Legacy compatibility routes
  - `/api/v2/*` - Modern REST API
  - Middleware for error handling

- [ ] **Implement basic authentication (optional)**
  - Session management
  - User authentication
  - Role-based access control

- [ ] **Create main layout and navigation**
  - Header/sidebar/footer
  - Navigation menu
  - Responsive design

- [ ] **Set up build pipeline**
  - Dockerfile for web-ui
  - Build and deployment scripts
  - Development hot-reload configuration

#### Deliverables
- ✅ Working SvelteKit application
- ✅ Cassandra connection established
- ✅ Basic UI layout
- ✅ Can query data from all exchange keyspaces

**Success Criteria:**
- Application connects to cluster
- Can query all exchange keyspaces
- UI renders correctly
- Hot-reload working in development

---

### Phase 2.2: API Compatibility Layer (Weeks 3-5)

#### Objectives
- Implement all legacy CGI endpoints
- Ensure response format compatibility
- Add exchange-awareness to queries
- Create comprehensive tests

#### Tasks

**Week 3: Query Endpoints (P0 - Critical)**
- [ ] `/cgi-bin/q1min.py` - 1-minute bar queries (exchange-aware)
- [ ] `/cgi-bin/q1sec.py` - 1-second bar queries (exchange-aware)
- [ ] `/cgi-bin/q1day.py` - Daily bar queries (exchange-aware)
- [ ] `/cgi-bin/qsyminfo.py` - Symbol information
- [ ] Test CSV and JSON output formats
- [ ] Test timezone handling
- [ ] Add exchange parameter support

**Week 4: Management Endpoints (P1 - High)**
- [ ] `/cgi-bin/eData.py` - Data editing (exchange-aware)
- [ ] `/cgi-bin/eConf.py` - Configuration editing
- [ ] `/cgi-bin/usymbol.py` - Symbol updates (exchange-aware)
- [ ] `/cgi-bin/doAction.py` - System actions
- [ ] `/cgi-bin/qtick.py` - Tick queries (exchange-aware)
- [ ] `/cgi-bin/qquote.py` - Quote queries (exchange-aware)

**Week 5: Import and System Endpoints (P2 - Medium)**
- [ ] `/cgi-bin/i1min_check.py` - Import validation (exchange-aware)
- [ ] `/cgi-bin/i1min_do.py` - Import execution (exchange-aware)
- [ ] `/cgi-bin/i1min_readstatus.py` - Import status
- [ ] `/cgi-bin/qSystemInfo.py` - System information (cluster-aware)
- [ ] `/cgi-bin/qSupportTZ.py` - Timezone support
- [ ] `/cgi-bin/qSymSummery.py` - Symbol summary (all exchanges)
- [ ] `/cgi-bin/qRange.py` - Range queries (exchange-aware)

#### Deliverables
- ✅ All legacy endpoints functional
- ✅ Exchange-awareness added to queries
- ✅ Integration tests passing
- ✅ API documentation updated

**Success Criteria:**
- All 23 legacy CGI endpoints working
- Backward compatible with existing clients
- Can query specific exchanges or all exchanges
- Response formats match exactly

---

### Phase 2.3: Modern UI Implementation (Weeks 6-8)

#### Objectives
- Build modern user interface
- Implement all features from legacy UI
- Add enhanced features
- Add exchange selector to all views

#### Tasks

**Week 6: Query Interface**
- [ ] Data query form with date/time pickers
- [ ] **Exchange selector** (NYSE, NASDAQ, HKEX, All)
- [ ] Symbol search/autocomplete (per exchange)
- [ ] Data grid with sorting/filtering
- [ ] CSV export functionality
- [ ] Chart visualization integration (Chart.js or Lightweight Charts)
- [ ] Multi-exchange comparison view

**Week 7: Management Interfaces**
- [ ] Symbol management page (exchange-grouped)
- [ ] Data editing interface (exchange-aware)
- [ ] Configuration editor
- [ ] Alert management UI
- [ ] Import wizard (exchange selection)
- [ ] Backfill interface

**Week 8: Dashboard and Polish**
- [ ] Dashboard with overview widgets (per exchange + total)
- [ ] Exchange health monitoring
- [ ] System status monitoring (all nodes)
- [ ] User preferences
- [ ] Responsive design
- [ ] Accessibility improvements
- [ ] Dark mode (optional)

#### Deliverables
- ✅ Complete modern UI
- ✅ Feature parity with legacy UI
- ✅ Exchange-aware throughout
- ✅ Enhanced user experience

**Success Criteria:**
- All legacy UI features implemented
- Can filter/view by exchange
- Dashboard shows per-exchange metrics
- Responsive on mobile/tablet
- User feedback positive

---

### Phase 2.4: Deployment & Integration (Weeks 9-10)

#### Objectives
- Deploy web UI to cluster
- Set up API gateway
- Configure load balancing
- Full integration testing

#### Tasks

**Week 9: Deployment Setup**

- [ ] **Create web-ui containers for each node**
  - Build Docker images
  - Push to registry (optional)
  - Configure environment variables

- [ ] **Deploy web-ui on each cluster node**
  ```bash
  # On each node
  docker-compose -f docker-compose.cluster.yml up -d web-ui
  ```

- [ ] **Set up API gateway (Nginx)**
  - Configure reverse proxy
  - SSL/TLS certificates
  - Rate limiting
  - Caching rules

- [ ] **Configure load balancing** (if needed)
  - DNS round-robin, or
  - External load balancer (HAProxy), or
  - Cloud load balancer (ALB/NLB)

- [ ] **Test from each node**
  - Verify web-ui connects to local Cassandra
  - Verify cross-node queries work
  - Test failover scenarios

**Week 10: Integration Testing**

- [ ] **End-to-end testing**
  - Test all user workflows
  - Test all API endpoints
  - Test from multiple browsers
  - Load testing

- [ ] **Backward compatibility testing**
  - Test with existing client applications
  - Verify API responses match exactly
  - Test legacy tools integration

- [ ] **Performance testing**
  - Query response times
  - Concurrent user load
  - Database query optimization

- [ ] **Documentation updates**
  - User guide
  - API documentation
  - Deployment guide
  - Troubleshooting guide

#### Deliverables
- ✅ Web UI deployed on all nodes
- ✅ API gateway configured
- ✅ All tests passing
- ✅ Documentation complete

**Success Criteria:**
- Web UI accessible from all nodes
- API gateway routes traffic correctly
- Performance meets targets (<200ms p95)
- Zero breaking changes to existing clients

---

### Phase 2.5: Cutover & Decommission (Weeks 11-12)

#### Objectives
- Switch production traffic to new system
- Monitor for issues
- Decommission old system
- Post-launch support

#### Tasks

**Week 11: Gradual Cutover**

- [ ] **Start with read-only traffic**
  - Route query traffic to new system
  - Keep writes on old system
  - Compare results

- [ ] **Enable write traffic**
  - Dual-write to both systems (optional)
  - Monitor for discrepancies
  - Verify data consistency

- [ ] **Full cutover**
  - Route 100% traffic to new system
  - Stop old system writes
  - Keep old system as backup

- [ ] **Monitor closely**
  - Application metrics
  - Database performance
  - Error rates
  - User feedback

**Week 12: Decommission & Handoff**

- [ ] **Verify new system stable**
  - Run for 1 week without issues
  - All metrics within targets
  - No critical bugs

- [ ] **Decommission old system**
  - Stop old Cassandra
  - Stop old Apache/CGI
  - Archive old configuration
  - Backup old data (keep for 90 days)

- [ ] **Team handoff**
  - Operations training
  - On-call runbooks
  - Escalation procedures
  - Knowledge transfer

- [ ] **Post-launch review**
  - Lessons learned
  - Performance analysis
  - Future improvements

#### Deliverables
- ✅ New system in full production
- ✅ Old system decommissioned
- ✅ Team trained and confident
- ✅ Post-launch review complete

**Success Criteria:**
- 100% traffic on new system
- Zero production incidents
- Team can operate independently
- Stakeholders satisfied

---

### Phase 2 Completion Checklist

Before declaring project complete:

- ✅ All legacy API endpoints working
- ✅ Modern UI deployed and accessible
- ✅ Backward compatibility verified
- ✅ Performance targets met
- ✅ Security audit passed (if required)
- ✅ Documentation complete
- ✅ Team trained
- ✅ Monitoring and alerting operational
- ✅ Old system decommissioned
- ✅ Stakeholder sign-off

**Phase 2 Duration:** 10-12 weeks  
**Phase 2 Risk:** Medium (application changes, user-facing)  
**Phase 2 Output:** Modern web UI and API running on containerized infrastructure

---

## Timeline Summary

### Total Project Duration: 14-18 weeks (3.5-4.5 months)

```
Phase 1: Infrastructure (Weeks 1-6)
├─ Week 1: Single-node dev setup
├─ Week 2: Cluster design
├─ Week 3-4: Cluster deployment
└─ Week 5-6: Data migration & tools

Phase 2: Application (Weeks 7-18)
├─ Week 7-8: Web UI foundation
├─ Week 9-11: API compatibility layer
├─ Week 12-14: Modern UI implementation
├─ Week 15-16: Deployment & integration
└─ Week 17-18: Cutover & decommission
```

### Resource Requirements

**Phase 1:**
- 1-2 DevOps/Infrastructure engineers
- Part-time: Database administrator
- Minimal disruption to current operations

**Phase 2:**
- 2-3 Full-stack developers
- 1 DevOps engineer
- Part-time: QA engineer
- UX designer (optional)

### Risk Mitigation

**Phase 1 Risks:**
- Data migration issues → Extensive testing, rollback plan
- Cluster stability → Gradual deployment, monitoring
- Network connectivity → Pre-deployment network tests

**Phase 2 Risks:**
- API breaking changes → Comprehensive compatibility tests
- UI bugs → User acceptance testing, beta period
- Performance issues → Load testing, optimization sprints
- User adoption → Training, documentation, support

---

## 9. Testing Strategy
- [ ] `/cgi-bin/q1min.py` - 1-minute bar queries (exchange-aware)
- [ ] `/cgi-bin/q1sec.py` - 1-second bar queries (exchange-aware)
- [ ] `/cgi-bin/q1day.py` - Daily bar queries (exchange-aware)
- [ ] `/cgi-bin/qsyminfo.py` - Symbol information
- [ ] Test CSV and JSON output formats
- [ ] Test timezone handling
- [ ] Add exchange parameter support

**Week 4: Management Endpoints (P1 - High)**
- [ ] `/cgi-bin/eData.py` - Data editing (exchange-aware)
- [ ] `/cgi-bin/eConf.py` - Configuration editing
- [ ] `/cgi-bin/usymbol.py` - Symbol updates
- [ ] `/cgi-bin/doAction.py` - System actions
- [ ] `/cgi-bin/qtick.py` - Tick queries (exchange-aware)
- [ ] `/cgi-bin/qquote.py` - Quote queries (exchange-aware)
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

### Phase 1 Success Criteria (Infrastructure)

**Infrastructure:**
- ✅ 3-4 node Cassandra cluster deployed and healthy
- ✅ Exchange-specific keyspaces created and tested
- ✅ Data correctly distributed (Master + exchange nodes)
- ✅ All nodes show UN (Up/Normal) status
- ✅ Cluster survives single node failure

**Data:**
- ✅ All existing data migrated successfully
- ✅ Data integrity verified (row counts, spot checks)
- ✅ Query performance acceptable

**Tools:**
- ✅ All tools containerized and functional
- ✅ Backfill procedures tested and documented
- ✅ Automated jobs running (cron, TQAlert)

**Operations:**
- ✅ Monitoring and alerting configured
- ✅ Runbooks and documentation complete
- ✅ Team trained on cluster operations
- ✅ Can add/remove nodes safely

### Phase 2 Success Criteria (Application)

**Functional:**
- ✅ All 23 legacy CGI endpoints operational
- ✅ Response formats exactly match legacy system
- ✅ Exchange-aware queries working
- ✅ Import workflows functional
- ✅ Modern UI deployed and accessible

**Performance:**
- ✅ Query response time < 200ms (p95)
- ✅ Support 50+ concurrent users
- ✅ Import throughput > 1000 rows/sec
- ✅ Web UI load time < 2 seconds

**Compatibility:**
- ✅ Zero breaking changes to existing clients
- ✅ Existing integrations continue working
- ✅ Legacy tools can still access data

**Operational:**
- ✅ One-command deployment per node
- ✅ Automated backups configured
- ✅ Health checks functional
- ✅ Centralized logging
- ✅ API documentation complete
- ✅ User documentation complete

**Quality:**
- ✅ Integration tests passing
- ✅ E2E tests passing
- ✅ Zero critical bugs
- ✅ Security review passed

### Overall Project Success Criteria

- ✅ Old system decommissioned
- ✅ 100% traffic on new system
- ✅ Zero production incidents post-cutover
- ✅ Team confident and self-sufficient
- ✅ Stakeholder satisfaction high
- ✅ Project within budget and timeline

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

- **Kubernetes Deployment**: Migrate from Docker Compose to K8s for orchestration
- **Multi-Datacenter Cassandra**: Expand to multiple geographic regions
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

This refactoring plan transforms TQDB from a traditional monolithic application into a modern, containerized cluster architecture with exchange-specific data distribution, while maintaining complete backward compatibility.

### Two-Phase Approach

The plan is deliberately split into two independent phases to minimize risk and allow flexibility:

**Phase 1: Infrastructure (4-6 weeks)**
- Deploy production-ready Cassandra cluster
- Implement exchange-specific data distribution
- Containerize tools and migrate data
- **Can be deployed without touching the application**
- Low risk, infrastructure-only changes

**Phase 2: Application (10-12 weeks)**
- Modernize web UI with SvelteKit
- Maintain backward compatibility with legacy API
- Add exchange-awareness throughout
- Depends on Phase 1 completion

### Key Benefits

**Infrastructure Benefits (Phase 1):**
1. **Storage Efficiency**: Exchange nodes only store their data (~33% savings)
2. **Master Node**: Complete dataset for analytics and backup
3. **High Availability**: Can tolerate single node failure (RF=2 or RF=3)
4. **Flexible Scaling**: Add exchanges by adding nodes
5. **No External Load Balancer**: Cassandra driver handles routing

**Application Benefits (Phase 2):**
1. **Modern UI**: Better user experience with SvelteKit
2. **Exchange-Aware**: Filter and query by specific exchanges
3. **Backward Compatible**: Zero disruption to existing integrations
4. **API Gateway**: Future-ready for authentication, rate limiting
5. **Maintainability**: Cleaner code structure, easier to modify

### Why Two Phases?

1. **Risk Management**: Infrastructure changes separate from application changes
2. **Independent Value**: Phase 1 delivers value without Phase 2
3. **Flexibility**: Can pause between phases or extend Phase 1
4. **Team Coordination**: Different skill sets for each phase
5. **Testing**: Easier to isolate issues
6. **Rollback**: Can rollback one phase without affecting the other

### Phase 1 Standalone Value

Even without Phase 2, Phase 1 provides significant benefits:
- ✅ Modern containerized infrastructure
- ✅ Exchange-specific data distribution
- ✅ Easier operations and maintenance
- ✅ Better scalability and availability
- ✅ Current application continues working unchanged

### Decision Points

**After Phase 1, you can:**
1. **Proceed to Phase 2** - Modernize application (recommended)
2. **Pause** - Run Phase 1 infrastructure, keep legacy UI
3. **Extend Phase 1** - Add more exchanges, tune performance
4. **Evaluate** - Gather feedback before committing to Phase 2

### Timeline Summary

```
Phase 1 (Infrastructure): 4-6 weeks
├─ Week 1: Dev setup
├─ Week 2: Cluster design
├─ Week 3-4: Deployment
└─ Week 5-6: Migration & tools

[Optional Pause & Evaluation]

Phase 2 (Application): 10-12 weeks
├─ Week 1-2: Web UI foundation
├─ Week 3-5: API compatibility
├─ Week 6-8: Modern UI
├─ Week 9-10: Deployment & integration
└─ Week 11-12: Cutover & decommission

Total: 14-18 weeks (3.5-4.5 months)
```

### Resource Requirements

**Phase 1:**
- 1-2 DevOps/Infrastructure engineers
- Part-time DBA
- Minimal disruption to development team

**Phase 2:**
- 2-3 Full-stack developers
- 1 DevOps engineer
- Part-time QA engineer
- UX designer (optional)

### Next Steps

1. ✅ **Review Phase 1**: Stakeholder review of infrastructure plan
2. ✅ **Approve Resources**: Assign Phase 1 team members
3. ✅ **Environment Prep**: Set up development/staging environments
4. ✅ **Phase 1 Kickoff**: Begin Week 1 (single-node dev setup)
5. ⏸️ **Phase 1 Completion Review**: Evaluate before Phase 2
6. ✅ **Phase 2 Planning**: Detail out application work (if approved)
7. ✅ **Phase 2 Kickoff**: Begin application modernization

### Risk Mitigation

**Phase 1 Risks:**
- Data migration issues → Extensive testing, parallel run
- Cluster stability → Gradual deployment, monitoring
- Network issues → Pre-deployment network validation

**Phase 2 Risks:**
- API breaking changes → Comprehensive compatibility tests
- UI bugs → User acceptance testing, beta program
- Performance issues → Load testing, optimization
- User adoption → Training, support, documentation

### Success Metrics

**Phase 1:**
- Cluster deployed and stable
- Data migrated successfully
- Tools operational
- Team confident in operations

**Phase 2:**
- All legacy endpoints working
- Modern UI deployed
- Zero breaking changes
- Performance targets met
- User satisfaction high

---

## 15. Appendix

### A. Phase Comparison Matrix

| Aspect | Phase 1 (Infrastructure) | Phase 2 (Application) |
|--------|--------------------------|----------------------|
| **Duration** | 4-6 weeks | 10-12 weeks |
| **Team Size** | 1-2 engineers | 2-3 developers + 1 DevOps |
| **Risk Level** | Low | Medium |
| **User Impact** | None (backend only) | High (UI changes) |
| **Rollback** | Easy | Moderate |
| **Dependencies** | None | Requires Phase 1 |
| **Value Delivered** | Modern infrastructure | Modern UX |
| **Can Deploy Alone?** | ✅ Yes | ❌ No (needs Phase 1) |

### B. Reference Documentation

- [Cassandra Docker Official Image](https://hub.docker.com/_/cassandra)
- [SvelteKit Documentation](https://kit.svelte.dev/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Cassandra Driver Python](https://docs.datastax.com/en/developer/python-driver/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [CLUSTER_ARCHITECTURE.md](CLUSTER_ARCHITECTURE.md) - Detailed cluster setup
- [EXCHANGE_SPECIFIC_SETUP.md](EXCHANGE_SPECIFIC_SETUP.md) - Exchange distribution guide
- [BACKFILL_STRATEGY.md](BACKFILL_STRATEGY.md) - Backfill procedures

### C. Contact and Support

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

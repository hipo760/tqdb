# TQDB Legacy Web Containerization Plan

## 📋 Overview

This document outlines the complete plan to containerize the legacy web interface located in `tools/for_web/`. The legacy system currently runs on Apache/Lighttpd with CGI scripts and needs to be modernized into a Docker container while maintaining full backward compatibility.

## 🎯 Objectives

1. **Containerize the legacy web interface** - Package Apache + Python CGI into Docker
2. **Maintain backward compatibility** - All existing endpoints and functionality work unchanged
3. **Connect to standalone Cassandra** - Each machine has its own Cassandra container
4. **Simplify deployment** - Replace manual Apache configuration with docker-compose
5. **Prepare for Phase 2** - Modern SvelteKit UI (future work)

## 📁 Current Legacy Web Structure

```
tools/for_web/
├── TQDB.vhost.conf           # Apache virtual host configuration
├── buildApache.sh            # Manual Apache setup script (Rocky Linux)
├── buildLighttpd.sh          # Alternative Lighttpd setup script
├── cgi-bin/                  # Python CGI scripts (main application logic)
│   ├── q1min.py             # Query 1-minute bar data
│   ├── q1sec.py             # Query 1-second bar data
│   ├── q1day.py             # Query daily bar data
│   ├── qsymbol.py           # List all symbols
│   ├── qsyminfo.py          # Symbol metadata query
│   ├── usymbol.py           # Update symbol information
│   ├── doAction.py          # Administrative actions
│   ├── i1min_check.py       # Data import status check
│   ├── i1min_do.py          # Trigger data import
│   ├── qRange.py            # Query date range
│   ├── qSupportTZ.py        # Timezone support query
│   ├── qSymRefPrc.py        # Symbol reference price query
│   ├── qSymSummery.py       # Symbol summary statistics
│   ├── qSystemInfo.py       # System information
│   ├── webcommon.py         # Common web utilities
│   └── eConf.py / eData.py  # Configuration and data editors
├── html/                     # Static HTML files and assets
│   ├── index.html           # Main landing page
│   ├── edata.html           # Data editor interface
│   ├── esymbol.html         # Symbol editor interface
│   ├── i1min.html           # Import interface
│   ├── symsummery.html      # Summary dashboard
│   ├── tqalert.html         # Alert configuration
│   ├── style.css            # Main stylesheet
│   └── js/                  # JavaScript dependencies
├── images/                   # Image assets
└── js/                       # JavaScript libraries (jQuery, jQuery UI, etc.)
```

## 🔍 Key Technical Details

### Current System Architecture

1. **Web Server**: Apache 2.4 (httpd) with CGI module
2. **Programming Language**: Python 3 (CGI scripts)
3. **Database Access**: 
   - Direct Cassandra queries via shell tools (qsym, q1min, q1sec, etc.)
   - Native C++ binaries in `/home/tqdb/codes/tqdb/tools/`
4. **Configuration**:
   - Hardcoded paths: `/home/tqdb/codes/tqdb/tools/`
   - Hardcoded Cassandra: `127.0.0.1:9042`
   - Hardcoded keyspace: `tqdb1`

### CGI Script Dependencies

**All CGI scripts depend on:**
- Shell scripts in `tools/`: `q1minall.sh`, `q1secall.sh`, `q1dayall.sh`
- Binary executables: `qsym`, `q1min`, `q1sec`, `qtick`, etc.
- Python utilities: `csvtzconv.py`, `formatDT.py`
- Cassandra connection: `127.0.0.1:9042`

**Example from `q1min.py`:**
```python
BIN_DIR = '/home/tqdb/codes/tqdb/tools/'  # Hardcoded path
CASSANDRA_IP = "127.0.0.1"
CASSANDRA_PORT = "9042"
CASSANDRA_DB = "tqdb1"

# Calls shell script:
subprocess.call(["./q1minall.sh", symbol, begin_dt_str, end_dt_str], cwd=BIN_DIR)
```

## 📦 Containerization Strategy

### Phase 1: Lift-and-Shift Approach (Recommended)

Keep the existing architecture but package it into containers. This minimizes risk and maintains full compatibility.

### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────────────────────┐  ┌──────────────────────┐│
│  │  tqdb-web                │  │  cassandra-node      ││
│  │  (Apache + CGI)          │  │  (Cassandra 4.1)     ││
│  ├──────────────────────────┤  ├──────────────────────┤│
│  │ - Apache 2.4             │  │ - Port: 9042         ││
│  │ - Python 3               │  │ - Keyspace: tqdb1    ││
│  │ - CGI scripts            │  │ - Standalone mode    ││
│  │ - Native binaries        │  │                      ││
│  │ - Port: 80               │  │                      ││
│  └──────────┬───────────────┘  └─────────┬────────────┘│
│             │                            │             │
│             └────────CQL 9042────────────┘             │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Implementation Steps

### Step 1: Analyze Dependencies
**Goal**: Document all dependencies that CGI scripts require

**Tasks**:
- [x] List all binary executables used by CGI scripts ✅ DONE
  - **C++ Binaries**: `qsym`, `qtick`, `q1minsec` (symlinked as `q1min`/`q1sec`), `tick21min`, `tick21minsec`, `itick`
  - **Source Code Available**: `tools/src/*.cpp` (~2000 lines, can be refactored to Python)
  - **C++ Driver Dependency**: All binaries require `libcassandra.so.2` (DataStax C++ driver)
  - **RECOMMENDATION**: Refactor to Python instead of copying binaries
- [ ] Identify Python dependencies (check if any `import` statements need packages)
  - Check all `*.py` files in `tools/for_web/cgi-bin/`
  - Known requirement: `cassandra-driver` (for Python refactored binaries)
- [ ] Document shell script dependencies
  - `q1minall.sh` - Calls `q1min` and `qtick` binaries, pipes to `tick21min`
  - `q1secall.sh` - Calls `q1sec` and `qtick` binaries, pipes to `tick21minsec`
  - `q1dayall.sh` - Calls daily aggregation
  - All scripts source `/etc/profile.d/profile_tqdb.sh` (environment variables)
- [ ] Map file system paths that need to be mounted or changed
  - `/home/tqdb/codes/tqdb/tools/` → `/opt/tqdb/tools/` (container path)
  - `/tmp/q1min.*` - Temporary query result files
  - `/tmp/qsym.*` - Temporary symbol query files
- [ ] Check for external service dependencies (besides Cassandra)
  - Self-referencing HTTP calls: `http://127.0.0.1/cgi-bin/qSymRefPrc.py` in `q1min.py`
  - No other external dependencies found

**Expected Output**: 
- ✅ **WEB_DEPENDENCIES.md** document (this section serves as it)
- ✅ **List of all binaries** to refactor to Python or copy
- [ ] List of Python packages to install: `cassandra-driver`, others TBD

### Step 2: Create Base Dockerfile
**Goal**: Build container image with Apache + Python CGI environment

**Tasks**:
- [ ] Choose base image (Rocky Linux 9 or CentOS Stream for compatibility)
- [ ] Install Apache with CGI module
- [ ] Install Python 3 and required packages
- [ ] Copy native binaries from `tools/` directory
- [ ] Copy CGI scripts from `tools/for_web/cgi-bin/`
- [ ] Copy static files from `tools/for_web/html/`
- [ ] Configure Apache for CGI execution
- [ ] Set proper file permissions

**Expected Output**: 
- `Dockerfile.web` file
- Build script or make target

### Step 3: Configure Apache in Container
**Goal**: Replace hardcoded paths and make configuration dynamic

**Tasks**:
- [ ] Create Apache configuration template based on `TQDB.vhost.conf`
- [ ] Use environment variables for:
  - `CASSANDRA_HOST` (default: cassandra-node)
  - `CASSANDRA_PORT` (default: 9042)
  - `CASSANDRA_KEYSPACE` (default: tqdb1)
  - `TOOLS_DIR` (internal container path)
- [ ] Set up `/var/www/cgi-bin/` for CGI scripts
- [ ] Set up `/var/www/html/` for static files
- [ ] Enable CGI module and set permissions
- [ ] Configure logging to stdout/stderr for Docker logs

**Expected Output**:
- Apache configuration file for container
- Entrypoint script to start Apache

### Step 4: Update CGI Scripts for Containerization
**Goal**: Make CGI scripts work with containerized paths and config

**Tasks**:
- [ ] Replace hardcoded `/home/tqdb/codes/tqdb/tools/` with environment variable
- [ ] Replace hardcoded `127.0.0.1` Cassandra IP with environment variable
- [ ] Update all CGI scripts to read from environment:
  - `q1min.py`
  - `q1sec.py`
  - `q1day.py`
  - `qsymbol.py`
  - `qsyminfo.py`
  - `usymbol.py`
  - All other `.py` files in `cgi-bin/`
- [ ] Ensure file permissions are correct for CGI execution
- [ ] Test that subprocess calls work in container environment

**Example Change**:
```python
# Before:
BIN_DIR = '/home/tqdb/codes/tqdb/tools/'
CASSANDRA_IP = "127.0.0.1"

# After:
import os
BIN_DIR = os.environ.get('TOOLS_DIR', '/opt/tqdb/tools/')
CASSANDRA_IP = os.environ.get('CASSANDRA_HOST', 'cassandra-node')
```

**Expected Output**:
- Modified CGI scripts (keep originals as backups)
- Testing checklist for each endpoint

### Step 5: Package Native Binaries OR Refactor to Python (RECOMMENDED)
**Goal**: Replace C++ binaries with Python scripts for better containerization

**Option A: Refactor to Python (RECOMMENDED)**

The C++ binaries can be replaced with Python scripts using `cassandra-driver`. This is the **best approach** for Docker containers.

**Tasks**:
- [ ] Create Python replacements for C++ binaries:
  - `qsym.py` - Replace `qsym` binary (query symbols)
  - `qtick.py` - Replace `qtick` binary (query ticks)
  - `q1min.py` - Replace `q1min`/`q1minsec` binary (query minute bars)
  - `q1sec.py` - Replace `q1sec` binary (query second bars)
  - `itick.py` - Replace `itick` binary (insert ticks)
- [ ] Use existing Python examples as templates:
  - `Min2Cass.py` - Shows how to insert minute bars
  - `Sec2Cass.py` - Shows how to insert second bars
  - `Sym2Cass.py` - Shows how to work with symbols
- [ ] Update shell scripts to call Python instead of binaries:
  - `q1minall.sh` calls `qsym.py` and `qtick.py`
  - `q1secall.sh` calls `q1sec.py` and `qtick.py`
- [ ] Test performance comparison (Python vs C++)
- [ ] Add to Dockerfile: `pip install cassandra-driver`

**Benefits**:
- ✅ No binary compatibility issues
- ✅ Simpler container (no `libcassandra.so.2` needed)
- ✅ Easier to debug and maintain
- ✅ Better error messages
- ✅ Cross-platform (works on any OS)

**Option B: Copy Existing Binaries (Fallback)**

Only if Python refactoring is not feasible in the timeline.

**Tasks**:
- [ ] Identify required binaries:
  - `qsym` - Symbol queries
  - `q1min` - 1-minute bar queries (symlink to q1minsec)
  - `q1sec` - 1-second bar queries (symlink to q1minsec)
  - `q1minsec` - Core query engine
  - `qtick` - Tick data queries
  - `tick21min` - Convert ticks to 1-minute bars
  - `tick21minsec` - Convert ticks to 1-second bars
  - `itick` - Tick insertion
- [ ] Copy shell scripts:
  - `q1minall.sh`, `q1secall.sh`, `q1dayall.sh`
  - `q1minfromtick.sh`, `q1secfromtick.sh`
- [ ] Install Cassandra C++ driver in container:
  - Rocky Linux 9: `dnf install cassandra-cpp-driver`
  - From RPM: Copy `3rd/cassandra-cpp-driver-2.6.0-1.el7.remi.x86_64.rpm`
- [ ] Set execute permissions on all scripts and binaries
- [ ] Test binary compatibility in container

**Expected Output**:
- **Option A**: Python scripts that replace binaries (RECOMMENDED)
- **Option B**: List of all binaries included + library dependencies

### Step 6: Create Docker Compose Configuration
**Goal**: Orchestrate web + Cassandra containers

**Tasks**:
- [ ] Create `docker-compose.web.yml`
- [ ] Define `tqdb-web` service:
  - Build from `Dockerfile.web`
  - Expose port 80
  - Environment variables for config
  - Volume mounts if needed (logs, temp files)
  - Depends on `cassandra-node`
  - Health check
- [ ] Update existing `docker-compose.node.yml` to be compatible
- [ ] Create shared network for containers
- [ ] Configure service dependencies (web waits for Cassandra)
- [ ] Add restart policies

**Example Structure**:
```yaml
version: '3.8'

services:
  cassandra-node:
    image: cassandra:4.1.10
    container_name: tqdb-cassandra-node
    # ... existing Cassandra config ...
    networks:
      - tqdb_network

  tqdb-web:
    build:
      context: .
      dockerfile: Dockerfile.web
    container_name: tqdb-web
    environment:
      - CASSANDRA_HOST=cassandra-node
      - CASSANDRA_PORT=9042
      - CASSANDRA_KEYSPACE=tqdb1
      - TOOLS_DIR=/opt/tqdb/tools
    ports:
      - "80:80"
    depends_on:
      cassandra-node:
        condition: service_healthy
    networks:
      - tqdb_network
    restart: unless-stopped

networks:
  tqdb_network:
    driver: bridge
```

**Expected Output**:
- `docker-compose.web.yml` file
- Deployment instructions

### Step 7: Database Schema Initialization
**Goal**: Ensure Cassandra has required schema when web starts

**Tasks**:
- [ ] Document required keyspace and tables:
  - `tqdb1.symbol` - Symbol metadata
  - `tqdb1.minbar` - 1-minute bars
  - `tqdb1.secbar` - 1-second bars
  - `tqdb1.daybar` - Daily bars
  - `tqdb1.tick` - Tick data
  - Others from init-scripts
- [ ] Create init container or startup script to:
  - Wait for Cassandra to be ready
  - Check if schema exists
  - Create keyspace and tables if needed
  - Load from `init-scripts/init-schema-v4.cql`
- [ ] Add to docker-compose startup sequence

**Expected Output**:
- Schema initialization script
- Documentation of all tables

### Step 8: Testing Strategy
**Goal**: Verify all endpoints work correctly in containerized environment

**Tasks**:
- [ ] **Unit Testing**: Test individual CGI scripts
  - Can they connect to Cassandra?
  - Do subprocess calls work?
  - Are file permissions correct?
- [ ] **Integration Testing**: Test complete workflows
  - Load index.html
  - Query symbols via `qsymbol.py`
  - Query minute data via `q1min.py`
  - Query second data via `q1sec.py`
  - Query daily data via `q1day.py`
  - Test data import workflow
  - Test symbol management
- [ ] **Performance Testing**: Compare with legacy system
  - Query response times
  - CPU/memory usage
  - Concurrent user handling
- [ ] **Error Handling**: Test failure scenarios
  - Cassandra connection lost
  - Invalid query parameters
  - Missing data
  - Permission issues

**Testing Checklist**:
```bash
# 1. Container health
docker ps | grep tqdb
docker logs tqdb-web
docker logs cassandra-node

# 2. Apache is running
curl http://localhost/

# 3. CGI scripts work
curl http://localhost/cgi-bin/qsymbol.py
curl "http://localhost/cgi-bin/q1min.py?symbol=TEST&begin=2024-01-01&end=2024-01-02"

# 4. Cassandra connectivity
docker exec tqdb-web curl http://localhost/cgi-bin/qSystemInfo.py

# 5. Binary executables work
docker exec tqdb-web /opt/tqdb/tools/qsym cassandra-node 9042 tqdb1.symbol 0 ALL 1
```

**Expected Output**:
- Test results document
- Known issues list
- Performance comparison

### Step 9: Volume Management
**Goal**: Determine what data needs persistence

**Tasks**:
- [ ] Identify temporary file locations:
  - `/tmp/q1min.*` files generated by queries
  - Log files
  - Cache files
- [ ] Decide on volume strategy:
  - Should temp files be in volumes? (Probably not, use tmpfs)
  - Should logs be persisted? (Yes, mount volume)
  - Should uploaded files be persisted? (Check if web supports uploads)
- [ ] Configure volumes in docker-compose
- [ ] Set cleanup policy for temp files

**Expected Output**:
- Volume configuration
- Cleanup cron job if needed

### Step 10: Security Hardening
**Goal**: Ensure container follows security best practices

**Tasks**:
- [ ] Run container as non-root user
- [ ] Set read-only root filesystem where possible
- [ ] Limit container capabilities
- [ ] Scan for vulnerabilities (e.g., `docker scan`)
- [ ] Configure Apache security headers
- [ ] Disable unnecessary Apache modules
- [ ] Set up proper file ownership and permissions
- [ ] Review CGI script security (input validation, SQL injection prevention)

**Expected Output**:
- Security checklist
- Vulnerability scan report

### Step 11: Documentation
**Goal**: Create comprehensive deployment and operations documentation

**Tasks**:
- [ ] Create `WEB_DEPLOYMENT.md`:
  - Prerequisites
  - Build instructions
  - Configuration options
  - Deployment steps
  - Verification tests
- [ ] Create `WEB_OPERATIONS.md`:
  - Starting/stopping containers
  - Viewing logs
  - Troubleshooting common issues
  - Updating the container
  - Backup and restore
- [ ] Update main `README.md` with web container info
- [ ] Create architecture diagram
- [ ] Document all environment variables
- [ ] Create troubleshooting FAQ

**Expected Output**:
- Complete documentation set
- Quick start guide
- Troubleshooting guide

### Step 12: Migration Guide
**Goal**: Help users migrate from legacy to containerized setup

**Tasks**:
- [ ] Document migration steps:
  1. Backup existing data
  2. Export Cassandra schema and data
  3. Stop legacy Apache
  4. Start containerized system
  5. Import data to containerized Cassandra
  6. Verify functionality
  7. Update DNS/load balancer
- [ ] Create migration scripts:
  - Export script for legacy system
  - Import script for containerized system
- [ ] Test rollback procedure
- [ ] Document differences between legacy and containerized

**Expected Output**:
- `WEB_MIGRATION.md` guide
- Migration scripts
- Rollback procedure

## 🛠️ Technical Specifications

### Dockerfile Requirements

**Base Image Options**:
1. **`python:3.11-slim`** (Recommended for Python refactor approach)
   - Lightweight Python base
   - Easy to add Apache
   - Best for refactored Python binaries
2. `rockylinux:9` (Only if keeping C++ binaries)
   - Closest to current Rocky Linux 9 system
   - Needed for binary compatibility
   - Requires C++ driver installation
3. `centos:stream9` (Alternative for C++ binaries)
4. `httpd:2.4` (Not recommended - too much work)

**Required Packages**:

**For Python Refactor (Recommended):**
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    apache2 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install cassandra-driver
```

**For C++ Binary Approach:**
```dockerfile
FROM rockylinux:9
RUN dnf install -y httpd python3 python3-pip cassandra-cpp-driver
RUN pip3 install cassandra-driver
```

**Directory Structure in Container**:
```
/opt/tqdb/
├── tools/              # Native binaries and shell scripts
│   ├── qsym*
│   ├── q1min*
│   ├── q1sec*
│   ├── q1minall.sh*
│   ├── q1secall.sh*
│   ├── csvtzconv.py
│   └── formatDT.py
└── web/
    ├── cgi-bin/        # CGI scripts
    └── html/           # Static files

/var/www/              # Apache default paths
├── cgi-bin/           -> /opt/tqdb/web/cgi-bin/
└── html/              -> /opt/tqdb/web/html/
```

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `CASSANDRA_HOST` | Cassandra hostname | `cassandra-node` | `192.168.1.10` |
| `CASSANDRA_PORT` | Cassandra CQL port | `9042` | `9042` |
| `CASSANDRA_KEYSPACE` | Default keyspace | `tqdb1` | `tqdb1` |
| `TOOLS_DIR` | Path to tools directory | `/opt/tqdb/tools` | `/opt/tqdb/tools` |
| `APACHE_LOG_LEVEL` | Apache log verbosity | `warn` | `debug` |
| `TZ` | Timezone | `Asia/Taipei` | `UTC` |

### Port Mappings

| Container Port | Host Port | Purpose |
|----------------|-----------|---------|
| 80 | 80 | HTTP web interface |
| 443 (optional) | 443 | HTTPS web interface |

### Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost/cgi-bin/qSystemInfo.py"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

## 📊 Success Criteria

### Functional Requirements
- ✅ All existing CGI endpoints work without modification to client code
- ✅ Can query all data types (tick, second, minute, daily bars)
- ✅ Symbol management (add, update, delete) works
- ✅ Data import functionality works
- ✅ Static HTML pages load correctly
- ✅ JavaScript and CSS assets load

### Non-Functional Requirements
- ✅ Container starts within 30 seconds
- ✅ Query performance matches or exceeds legacy system
  - **Python vs C++**: Initial testing needed, but Python with cassandra-driver should be comparable
  - **Expected**: < 10% performance difference for typical queries
- ✅ Container size under 500MB (Python base ~200MB, Rocky Linux ~250MB)
- ✅ Resource usage: < 512MB RAM, < 1 CPU under normal load
- ✅ All logs accessible via `docker logs`
- ✅ Zero-downtime deployment possible

### Quality Requirements
- ✅ Complete documentation for deployment and operations
- ✅ All tests pass
- ✅ Security scan shows no high/critical vulnerabilities
- ✅ Container can be deployed on any Docker-capable machine
- ✅ Works with standalone Cassandra (no cluster dependencies)
- ✅ **Python code is maintainable** (if refactored)

## 🚨 Known Challenges & Considerations

### Challenge 1: Binary Compatibility ⚠️ RESOLVED - Use Python Instead!
**Issue**: Native C++ binaries compiled on Rocky Linux 9 may not work in container base image

**✅ RECOMMENDED SOLUTION: Refactor to Python**

The C++ binaries (~2000 lines of code in `tools/src/`) can and should be replaced with Python using the `cassandra-driver` package. This is the **best approach** for containerization:

**Why Python is Better:**
- ✅ **No binary compatibility issues** - Pure Python works everywhere
- ✅ **Easier to maintain** - Python is more maintainable than C++
- ✅ **Already have Python examples** - `Min2Cass.py`, `Sec2Cass.py`, `Sym2Cass.py` show the pattern
- ✅ **Simpler container** - No need for `libcassandra.so.2` shared library
- ✅ **Better error handling** - Python exceptions vs C++ crashes
- ✅ **Container-friendly** - Single dependency: `pip install cassandra-driver`

**C++ Source Code Available:**
```
tools/src/
├── qsym.cpp         (164 lines) - Query symbols from Cassandra
├── qtick.cpp        (206 lines) - Query tick data
├── q1minsec.cpp     (175 lines) - Query minute/second bars
├── itick.cpp        - Insert tick data
├── common.cpp       - Shared utilities
└── Total: ~2000 lines
```

**Python Refactoring Pattern:**
```python
# Example: qsym.py (replaces qsym binary)
from cassandra.cluster import Cluster
import sys
import json

def query_symbols(host, port, keyspace, symbol):
    cluster = Cluster([host], port=int(port))
    session = cluster.connect(keyspace)
    
    if symbol == "ALL":
        query = f"SELECT * FROM symbol"
    else:
        query = f"SELECT * FROM symbol WHERE symbol = '{symbol}'"
    
    rows = session.execute(query)
    results = []
    for row in rows:
        results.append(dict(row._asdict()))
    
    print(json.dumps(results))
    session.shutdown()
    cluster.shutdown()

if __name__ == "__main__":
    # Usage: python qsym.py 127.0.0.1 9042 tqdb1 ALL 1
    query_symbols(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[5])
```

**Fallback Options (Not Recommended):**
- Option A: Use Rocky Linux 9 base image + copy binaries
- Option B: Recompile binaries during Docker build (slow)
- Option C: Use static binaries (if available)

**Decision**: **Refactor to Python** - Best long-term solution

### Challenge 2: File Permissions
**Issue**: CGI scripts need execute permissions, Apache needs correct user/group

**Solutions**:
- Set proper permissions in Dockerfile
- Run Apache as appropriate user
- Test CGI execution thoroughly

**Best Practice**: Follow principle of least privilege

### Challenge 3: Temporary File Cleanup
**Issue**: CGI scripts create temp files in `/tmp/q1min.*` pattern

**Solutions**:
- Option A: Use tmpfs for `/tmp` (automatic cleanup on restart)
- Option B: Add cron job in container to clean old files
- Option C: Modify CGI scripts to clean up after themselves

**Recommendation**: Start with tmpfs, add cleanup if needed

### Challenge 4: Hardcoded Paths
**Issue**: Many CGI scripts have hardcoded paths to `/home/tqdb/codes/tqdb/tools/`

**Solutions**:
- Update all scripts to use environment variable
- Create comprehensive test suite to verify all paths work
- Consider using symbolic links as fallback

**Status**: Must be addressed in Step 4

### Challenge 5: Cassandra Connectivity
**Issue**: Scripts expect Cassandra on localhost, but it's now in separate container

**Solutions**:
- Use Docker networking (service discovery)
- Update all scripts to use `CASSANDRA_HOST` environment variable
- Add retry logic for initial connection

**Note**: Test with Cassandra temporarily unavailable

### Challenge 6: Shell Script Dependencies
**Issue**: Many CGI scripts call shell scripts that call other shell scripts

**Solutions**:
- Map entire dependency chain
- Ensure all scripts are executable
- Test each script independently
- Consider refactoring deeply nested calls

**Risk**: High complexity, thorough testing essential

## 🔄 Rollback Plan

If containerization fails or issues are found:

1. **Immediate Rollback**: Keep legacy system running during transition
2. **Data Safety**: Cassandra data is separate, no risk of data loss
3. **Gradual Migration**: Can run both systems in parallel
4. **DNS/Load Balancer**: Easy to switch traffic between systems

## 📈 Future Enhancements (Phase 2)

After successful containerization of legacy web:

1. **Modern API Layer**: FastAPI or Flask REST API
2. **New Frontend**: SvelteKit or React SPA
3. **GraphQL**: Alternative to REST for complex queries
4. **WebSocket**: Real-time data streaming
5. **Authentication**: JWT-based auth system
6. **Rate Limiting**: API usage controls
7. **Caching**: Redis for query result caching
8. **Monitoring**: Prometheus + Grafana
9. **CI/CD**: Automated testing and deployment
10. **Multi-tenancy**: Support multiple customers

## ✅ Deliverables Checklist

### Core Deliverables
- [ ] `Dockerfile.web` - Web container image definition
- [ ] `docker-compose.web.yml` - Orchestration configuration
- [ ] `WEB_DEPENDENCIES.md` - Complete dependency documentation
- [ ] `WEB_DEPLOYMENT.md` - Deployment guide
- [ ] `WEB_OPERATIONS.md` - Operations manual
- [ ] `WEB_MIGRATION.md` - Migration from legacy guide

### Code Changes
- [ ] **Python Binaries (RECOMMENDED)**:
  - [ ] `qsym.py` - Query symbols (replaces C++ `qsym`)
  - [ ] `qtick.py` - Query ticks (replaces C++ `qtick`)
  - [ ] `q1min.py` - Query minute bars (replaces C++ `q1min`)
  - [ ] `q1sec.py` - Query second bars (replaces C++ `q1sec`)
  - [ ] `itick.py` - Insert ticks (replaces C++ `itick`)
- [ ] Updated CGI scripts with environment variable support
- [ ] Updated shell scripts to call Python instead of C++ binaries
- [ ] Apache configuration template
- [ ] Container entrypoint script

### Testing & Documentation
- [ ] Schema initialization script
- [ ] Test suite and results
- [ ] Performance comparison (Python vs C++ binaries)
- [ ] Security scan report
- [ ] Architecture diagram
- [ ] Performance benchmark results

### Alternative (If Not Refactoring)
- [ ] Copy C++ binaries and `libcassandra.so.2` dependency

## 📞 Next Steps

1. **Review this plan** - Ensure all stakeholders agree
2. **Start with Step 1** - Analyze dependencies
3. **Create proof of concept** - Build basic container
4. **Iterate and refine** - Test and improve
5. **Deploy to staging** - Full testing environment
6. **Production deployment** - Gradual rollout

## 🤝 Team Responsibilities

| Role | Responsibilities |
|------|------------------|
| **Developer** | Write Dockerfile, update scripts, testing |
| **DevOps** | Docker infrastructure, CI/CD pipeline |
| **DBA** | Cassandra schema, data migration |
| **QA** | Test all endpoints, performance testing |
| **Product Owner** | Prioritize features, accept deliverables |

## 📚 References

- Current System: `tools/for_web/`
- Cassandra Config: `docker-compose.node.yml`
- Legacy Docs: `docs/legacy/ROCKY9_INSTALL.md`
- Schema: `init-scripts/init-schema-v4.cql`
- Project README: `README.md`
- Deployment Guide: `DEPLOYMENT_GUIDE.md`

---

**Document Version**: 1.0  
**Created**: 2026-02-18  
**Author**: TQDB Team  
**Status**: Planning Phase

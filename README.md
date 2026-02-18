# TQDB - Time-Series Quote Database

A high-performance containerized time-series database system for financial market data, built on Apache Cassandra with exchange-specific data distribution.

## 🚀 Quick Start

### Current System (Legacy)
```bash
# See docs/legacy/ for Rocky Linux 9 and CentOS 7 installation guides
```

### Modern Deployment (Recommended)
```bash
# Single-node development setup
docker-compose up -d

# Multi-node cluster with exchange-specific distribution
# See DEPLOYMENT_GUIDE.md for complete setup
```

## 📚 Documentation

### Core Documentation (3 files)
1. **[README.md](README.md)** (this file) - Project overview and quick start
2. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide
   - Two-phase modernization plan
   - Multi-node cluster architecture
   - Exchange-specific data distribution
   - Docker setup and configuration
3. **[OPERATIONS.md](OPERATIONS.md)** - Daily operations
   - Backfill procedures
   - Monitoring and troubleshooting
   - Maintenance tasks

### Legacy Documentation
- **[docs/legacy/ROCKY9_INSTALL.md](docs/legacy/ROCKY9_INSTALL.md)** - Rocky Linux 9 installation
- **[docs/legacy/CENTOS7_INSTALL.md](docs/legacy/CENTOS7_INSTALL.md)** - CentOS 7 installation

### Tools Documentation
- **[tools/](tools/)** - Processing tools and utilities

## 🎯 Features

### Current System
- Real-time ingestion (tick, second, minute bars)
- Multiple exchange support (NYSE, NASDAQ, HKEX)
- C++ and Python data processing tools
- Web-based query interface

### Modern System (In Progress)
- **Containerized deployment** - Docker Compose orchestration
- **Exchange-specific distribution** - 33% storage savings
- **High availability** - Multi-node cluster with RF=2
- **Modern web UI** - SvelteKit interface (Phase 2)
- **RESTful API** - Backward compatible (Phase 2)

## 🏗️ Architecture

### Exchange-Specific Data Distribution

```
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Master      │  │   NYSE Node   │  │  NASDAQ Node  │  │   HKEX Node   │
├───────────────┤  ├───────────────┤  ├───────────────┤  ├───────────────┤
│ NYSE: 100GB   │  │ NYSE: 100GB   │  │ NASDAQ: 80GB  │  │ HKEX: 60GB    │
│ NASDAQ: 80GB  │  │               │  │               │  │               │
│ HKEX: 60GB    │  │               │  │               │  │               │
├───────────────┤  ├───────────────┤  ├───────────────┤  ├───────────────┤
│ Total: 240GB  │  │ Total: 100GB  │  │ Total: 80GB   │  │ Total: 60GB   │
└───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘

Cluster Total: 480GB (33% savings vs 720GB full replication)
```

**Key Benefits:**
- Master node maintains complete dataset for analytics
- Exchange nodes store only their market data
- Query any node to access any exchange data (driver routing)
- No external load balancer needed

## 📦 Project Structure

```
tqdb/
├── README.md                    # This file - project overview
├── DEPLOYMENT_GUIDE.md          # Complete deployment guide
├── OPERATIONS.md                # Operational procedures
├── Demo.ipynb                   # Jupyter notebook demo
│
├── docker-compose.yml           # Development setup (future)
├── docker-compose.cluster.yml   # Cluster setup (future)
│
├── docs/                        
│   └── legacy/                  # Legacy installation guides
│       ├── ROCKY9_INSTALL.md
│       └── CENTOS7_INSTALL.md
│
├── tools/                       # Data processing tools
│   ├── q1min, q1sec            # Query tools
│   ├── Min2Cass.py, Sec2Cass.py # Importers
│   └── for_web/                # Web interface
│
└── script_for_sys/              # System scripts
```

## 🔧 Technology Stack

### Current
- **Database**: Apache Cassandra 3.x
- **Backend**: C++, Python 2.7
- **Web**: Apache httpd, CGI
- **OS**: Rocky Linux 9, CentOS 7

### Target (Modern)
- **Database**: Cassandra 4.1 / ScyllaDB
- **Backend**: Python 3.11+, Node.js
- **Web**: SvelteKit, Nginx
- **Deploy**: Docker, Docker Compose
- **OS**: Any Linux (containerized)

## 🚦 Getting Started

### For New Deployments

1. **Read the deployment guide**
   ```bash
   cat DEPLOYMENT_GUIDE.md
   ```

2. **Choose your approach**
   - **Phase 1 Only**: Modern infrastructure, keep legacy UI (4-6 weeks)
   - **Phase 1 + 2**: Full modernization (16-22 weeks)

3. **Start with single-node dev setup** (Phase 1.1)

### For Existing Installations

1. **Assess current system**
   ```bash
   nodetool status
   du -sh /var/lib/cassandra/data/tqdb
   ```

2. **Plan migration** - See DEPLOYMENT_GUIDE.md Section 5

3. **Execute** - See OPERATIONS.md for procedures

## 📊 Data Model

### Keyspaces (Exchange-Specific)
- `tqdb_nyse` - NYSE market data
- `tqdb_nasdaq` - NASDAQ market data
- `tqdb_hkex` - Hong Kong Exchange
- *One keyspace per exchange*

### Tables
- `minbar` - Minute bars (OHLCV)
- `secbar` - Second bars
- `tick` - Tick data
- `sym` - Symbol metadata
- `quote` - Latest quotes

## 🎓 Documentation Flow

```
Start Here (README.md)
    ↓
Want to deploy? → DEPLOYMENT_GUIDE.md
    ↓
Need to operate? → OPERATIONS.md
    ↓
Legacy system? → docs/legacy/
```

## 🤝 Contributing

Private/enterprise project. See internal documentation.

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE)

## 🆘 Support

- **Deployment**: See DEPLOYMENT_GUIDE.md Troubleshooting
- **Operations**: See OPERATIONS.md
- **Legacy**: See docs/legacy/

## 🗺️ Roadmap

### ✅ Completed
- Legacy system on Rocky Linux 9
- Two-phase deployment plan
- Documentation consolidation

### 🚧 Phase 1 (Next)
- Single-node Docker setup
- Multi-node cluster templates
- Data migration scripts
- Tool containerization

### 📅 Phase 2 (Future)
- SvelteKit web UI
- RESTful API
- Modern query interface

### 🔮 Beyond
- ScyllaDB evaluation
- Kubernetes deployment
- Multi-datacenter

## 📈 Status

**Current**: Legacy system in production  
**Active**: Phase 1 preparation  
**Target**: Phase 1 (Q2 2026), Phase 2 (Q4 2026)

---

**Version**: 2.0  
**Last Updated**: February 17, 2026

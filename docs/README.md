# TQDB Documentation

This directory contains additional documentation for the TQDB project.

## Directory Structure

```
docs/
├── README.md (this file)
├── legacy/                      # Legacy installation guides
│   ├── ROCKY9_INSTALL.md       # Rocky Linux 9 installation
│   └── CENTOS7_INSTALL.md      # CentOS 7 installation
└── archive/                     # Detailed architecture documents
    ├── REFACTOR_PLAN.md        # Detailed refactor plan
    ├── REFACTOR_PLAN_OVERVIEW.md # Executive summary
    ├── CLUSTER_ARCHITECTURE.md # Multi-node architecture details
    ├── EXCHANGE_SPECIFIC_SETUP.md # Setup procedures
    ├── EXCHANGE_DISTRIBUTION_GUIDE.md # Visual guide
    ├── BACKFILL_STRATEGY.md    # Detailed backfill procedures
    └── BACKFILL_QUICK_REF.md   # Backfill quick reference
```

## Primary Documentation (Top Level)

The top-level directory contains the **essential 3 documents**:

1. **[../README.md](../README.md)** - Project overview and quick start
2. **[../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)** - Complete deployment guide
3. **[../OPERATIONS.md](../OPERATIONS.md)** - Daily operations and procedures

**Start with these 3 files** - they contain everything you need for deployment and operations.

## Archive Documents

The `archive/` directory contains the original detailed documentation that was used to create the consolidated guides. These are kept for reference but are not needed for daily use:

- **REFACTOR_PLAN.md** - Original detailed refactor plan (85KB, comprehensive)
- **CLUSTER_ARCHITECTURE.md** - Detailed multi-node cluster architecture
- **EXCHANGE_DISTRIBUTION_GUIDE.md** - Visual guide with extensive diagrams
- **BACKFILL_STRATEGY.md** - Complete backfill strategy with all options

**When to use archive docs:**
- Need more detailed architecture explanations
- Want to understand design decisions
- Researching alternative approaches
- Training new team members on architecture concepts

## Legacy Documents

The `legacy/` directory contains installation guides for the current production system:

- **ROCKY9_INSTALL.md** - Step-by-step Rocky Linux 9 installation (659 lines)
- **CENTOS7_INSTALL.md** - Step-by-step CentOS 7 installation (316 lines)

**When to use legacy docs:**
- Installing on bare metal Rocky Linux 9 or CentOS 7
- Troubleshooting legacy production systems
- Understanding current system configuration

## Documentation Flow

```
New User / Quick Start
    ↓
README.md (5 min read)
    ↓
Want to deploy?
    ↓
DEPLOYMENT_GUIDE.md (30-60 min read)
    ↓
Need details? → docs/archive/REFACTOR_PLAN.md
    ↓
Daily operations?
    ↓
OPERATIONS.md (15-30 min read)
    ↓
Need backfill details? → docs/archive/BACKFILL_STRATEGY.md
```

## Document Sizes

**Top Level (Streamlined):**
- README.md: 7KB (~300 lines)
- DEPLOYMENT_GUIDE.md: 85KB (~2,000 lines)
- OPERATIONS.md: 19KB (~700 lines)
- **Total**: 111KB

**Archive (Detailed):**
- All archive docs: ~200KB
- (Available for reference, not needed for daily use)

## Migration Notes

This documentation structure was created on **February 17, 2026** to consolidate and streamline the documentation:

**Before:**
- 7 top-level markdown files (confusing)
- Duplicated information
- Hard to find what you need

**After:**
- 3 top-level essential files (clear)
- Consolidated information
- Easy navigation
- Archives preserved for reference

## Contributing

When updating documentation:

1. **Update top-level docs first** (README, DEPLOYMENT_GUIDE, OPERATIONS)
2. **Archive docs are frozen** (historical reference only)
3. **Keep it concise** - top-level docs should be scannable
4. **Link to archives** when more detail is needed

## Questions?

- **General questions**: Start with README.md
- **Deployment questions**: See DEPLOYMENT_GUIDE.md
- **Operations questions**: See OPERATIONS.md
- **Architecture deep-dive**: See docs/archive/
- **Legacy system**: See docs/legacy/

---

**Last Updated**: February 17, 2026  
**Documentation Version**: 2.0 (Consolidated)

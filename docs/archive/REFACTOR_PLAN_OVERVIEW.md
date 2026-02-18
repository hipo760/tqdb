# TQDB Refactor Plan - Two-Phase Overview

## Executive Summary

The TQDB refactoring is structured as **two independent phases** to minimize risk and provide flexibility:

1. **Phase 1: Infrastructure** (4-6 weeks) - Containerized Cassandra cluster with exchange-specific distribution
2. **Phase 2: Application** (10-12 weeks) - Modern web UI and API

**Key Insight:** Phase 1 can be deployed independently and provides immediate value without Phase 2.

---

## Phase Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│                         PHASE 1                                   │
│                  Infrastructure & Data Layer                      │
├──────────────────────────────────────────────────────────────────┤
│ Duration: 4-6 weeks                                              │
│ Risk: LOW                                                         │
│ Team: 1-2 DevOps/Infrastructure engineers                        │
│ User Impact: NONE (backend only)                                 │
│ Can Deploy Alone: ✅ YES                                          │
│                                                                   │
│ Deliverables:                                                    │
│ • 3-4 node Cassandra cluster deployed                            │
│ • Exchange-specific keyspaces (tqdb_nyse, tqdb_nasdaq, etc.)   │
│ • Data migrated and distributed correctly                        │
│ • Tools containerized and operational                            │
│ • Backfill procedures tested                                     │
│                                                                   │
│ Value Delivered:                                                 │
│ • Modern containerized infrastructure                            │
│ • Storage efficiency (~33% savings)                              │
│ • High availability (RF=2/3)                                     │
│ • Easier operations and maintenance                              │
│ • Current application continues working unchanged                │
└──────────────────────────────────────────────────────────────────┘

                              ↓
                    [Optional Pause & Evaluate]
                              ↓

┌──────────────────────────────────────────────────────────────────┐
│                         PHASE 2                                   │
│                   Application Modernization                       │
├──────────────────────────────────────────────────────────────────┤
│ Duration: 10-12 weeks                                            │
│ Risk: MEDIUM                                                      │
│ Team: 2-3 Full-stack developers + 1 DevOps                       │
│ User Impact: HIGH (UI changes)                                   │
│ Can Deploy Alone: ❌ NO (requires Phase 1)                        │
│                                                                   │
│ Deliverables:                                                    │
│ • Modern SvelteKit web UI                                        │
│ • All 23 legacy API endpoints (backward compatible)             │
│ • Exchange-aware UI and queries                                  │
│ • API gateway with Nginx                                         │
│ • Comprehensive testing                                          │
│                                                                   │
│ Value Delivered:                                                 │
│ • Better user experience                                         │
│ • Exchange filtering and views                                   │
│ • Maintainable codebase                                          │
│ • Modern tech stack                                              │
│ • Zero breaking changes to existing integrations                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 Detailed Breakdown

### Week 1: Single-Node Development Setup
```
Goals:
• Create base Docker Compose configuration
• Set up single-node Cassandra for development
• Create schema initialization scripts
• Test basic operations

Deliverables:
✅ Working single-node Cassandra in Docker
✅ Schema initialized automatically
✅ Makefile for operations
✅ Development environment ready
```

### Week 2: Exchange-Specific Cluster Design
```
Goals:
• Design exchange-specific keyspace strategy
• Create rack-aware configuration
• Prepare for multi-node deployment
• Design data distribution model

Deliverables:
✅ Exchange-specific keyspace design documented
✅ Cluster deployment scripts ready
✅ Per-machine docker-compose templates
✅ Network and rack configuration documented
```

### Week 3-4: Multi-Node Cluster Deployment
```
Goals:
• Deploy 3-4 node Cassandra cluster
• Configure exchange-specific data distribution
• Verify data replication
• Test cluster operations

Deliverables:
✅ 3-4 node production cluster running
✅ Exchange-specific keyspaces created
✅ Data distribution verified
✅ Monitoring in place
```

### Week 5-6: Data Migration & Tool Integration
```
Goals:
• Migrate existing data to new cluster
• Containerize existing tools
• Set up backfill procedures
• Run parallel with old system

Deliverables:
✅ All data migrated to new cluster
✅ Tools containerized and running
✅ Backfill procedures tested
✅ Automated jobs configured
```

---

## Phase 2 Detailed Breakdown

### Week 1-2: Web UI Foundation
```
Goals:
• Set up SvelteKit project
• Implement Cassandra client wrapper
• Create basic UI layout
• Test connection to cluster

Deliverables:
✅ Working SvelteKit application
✅ Cassandra connection established
✅ Basic UI layout
✅ Can query all exchange keyspaces
```

### Week 3-5: API Compatibility Layer
```
Goals:
• Implement all 23 legacy CGI endpoints
• Ensure response format compatibility
• Add exchange-awareness to queries
• Create comprehensive tests

Deliverables:
✅ All legacy endpoints functional
✅ Exchange-awareness added
✅ Integration tests passing
✅ API documentation updated
```

### Week 6-8: Modern UI Implementation
```
Goals:
• Build modern user interface
• Implement all features from legacy UI
• Add enhanced features
• Add exchange selector to all views

Deliverables:
✅ Complete modern UI
✅ Feature parity with legacy UI
✅ Exchange-aware throughout
✅ Enhanced user experience
```

### Week 9-10: Deployment & Integration
```
Goals:
• Deploy web UI to cluster
• Set up API gateway
• Configure load balancing
• Full integration testing

Deliverables:
✅ Web UI deployed on all nodes
✅ API gateway configured
✅ All tests passing
✅ Documentation complete
```

### Week 11-12: Cutover & Decommission
```
Goals:
• Switch production traffic to new system
• Monitor for issues
• Decommission old system
• Post-launch support

Deliverables:
✅ New system in full production
✅ Old system decommissioned
✅ Team trained and confident
✅ Post-launch review complete
```

---

## Why Two Phases?

### 1. Risk Management
- **Separate concerns**: Infrastructure vs Application
- **Isolate issues**: Easier to debug and fix
- **Independent rollback**: Can rollback one phase without affecting the other

### 2. Independent Value
- **Phase 1 delivers value alone**: Modern infrastructure without app changes
- **Current app keeps working**: No disruption during Phase 1
- **Flexibility**: Can pause between phases if needed

### 3. Team Coordination
- **Different skill sets**: DevOps for Phase 1, Developers for Phase 2
- **Resource allocation**: Can overlap with other projects
- **Learning curve**: Team learns cluster operations before app changes

### 4. Flexibility
- **After Phase 1, you can**:
  - Proceed to Phase 2 immediately
  - Pause and evaluate for weeks/months
  - Extend Phase 1 (add more exchanges, tune performance)
  - Keep legacy UI permanently (if desired)
  - Wait for budget/resources for Phase 2

### 5. Reduced Risk of Big Bang
- **No "big bang" deployment**: Each phase is incremental
- **Easier stakeholder approval**: Smaller commitments
- **Budget flexibility**: Can secure Phase 2 budget after Phase 1 success

---

## Decision Points

### After Phase 1 Completion

```
Phase 1 Complete ✓
        │
        ▼
    Evaluate:
    • Infrastructure stable?
    • Team comfortable with operations?
    • Data distribution working as expected?
    • Backfill procedures effective?
        │
        ├─── YES → Decision Point
        │         │
        │         ├─ Option A: Proceed to Phase 2 (Recommended)
        │         │   • Modernize UI and API
        │         │   • Full stack modernization
        │         │
        │         ├─ Option B: Pause & Extend Phase 1
        │         │   • Add more exchanges
        │         │   • Tune performance
        │         │   • Monitor longer before Phase 2
        │         │
        │         └─ Option C: Keep Legacy UI
        │             • Phase 1 infrastructure only
        │             • Legacy UI continues working
        │             • Defer Phase 2 indefinitely
        │
        └─── NO → Fix Phase 1 issues before proceeding
```

---

## Resource Planning

### Phase 1 Team (4-6 weeks)

```
DevOps Engineer 1:
├─ Week 1: Docker Compose setup, Cassandra config
├─ Week 2: Cluster design, scripts
├─ Week 3-4: Deployment, monitoring
└─ Week 5-6: Data migration, tools

DevOps Engineer 2 (Part-time):
├─ Week 2: Network setup, firewall rules
├─ Week 3-4: Deployment support
└─ Week 5-6: Testing, verification

DBA (Part-time):
├─ Week 1: Schema design review
├─ Week 2: Keyspace strategy
├─ Week 4: Replication verification
└─ Week 5-6: Data migration support
```

### Phase 2 Team (10-12 weeks)

```
Full-Stack Developer 1:
├─ Week 1-2: SvelteKit setup, Cassandra client
├─ Week 3-5: Query API endpoints
└─ Week 6-8: Query UI components

Full-Stack Developer 2:
├─ Week 1-2: API route structure
├─ Week 3-5: Management API endpoints
└─ Week 6-8: Management UI components

Full-Stack Developer 3:
├─ Week 3-5: System/import endpoints
├─ Week 6-8: Dashboard, polish
└─ Week 9-10: Testing, bug fixes

DevOps Engineer:
├─ Week 9-10: Deployment, API gateway
└─ Week 11-12: Cutover, monitoring

QA Engineer (Part-time):
├─ Week 8-10: Testing
└─ Week 11: Verification
```

---

## Budget Considerations

### Phase 1 Cost

```
Personnel:
├─ DevOps Engineer (1 FTE × 6 weeks) = 1.5 person-months
├─ DevOps Engineer 2 (0.5 FTE × 6 weeks) = 0.75 person-months
└─ DBA (0.25 FTE × 6 weeks) = 0.38 person-months
Total: ~2.6 person-months

Infrastructure:
├─ 4 VMs/servers (master + 3 exchanges)
├─ Storage (depends on data size)
└─ Network bandwidth

Estimated: $15,000 - $30,000 (varies by company)
```

### Phase 2 Cost

```
Personnel:
├─ Full-Stack Developers (3 FTE × 3 months) = 9 person-months
├─ DevOps Engineer (0.5 FTE × 3 months) = 1.5 person-months
└─ QA Engineer (0.25 FTE × 3 months) = 0.75 person-months
Total: ~11.3 person-months

Infrastructure:
└─ Same as Phase 1 (already deployed)

Estimated: $50,000 - $100,000 (varies by company)
```

### Total Project Cost

```
Phase 1: $15,000 - $30,000
Phase 2: $50,000 - $100,000
──────────────────────────
Total:   $65,000 - $130,000
```

---

## Success Metrics

### Phase 1 KPIs

- ✅ All nodes show UN (Up/Normal) status
- ✅ Data distribution verified (Master + exchange nodes)
- ✅ Query performance within 10% of baseline
- ✅ Zero data loss during migration
- ✅ Cluster survives single node failure
- ✅ Team can perform common operations independently

### Phase 2 KPIs

- ✅ All 23 legacy API endpoints functional
- ✅ Query response time < 200ms (p95)
- ✅ Support 50+ concurrent users
- ✅ Zero breaking changes for existing clients
- ✅ User satisfaction score > 8/10
- ✅ Zero critical bugs in first month

---

## Risk Matrix

| Phase | Risk | Probability | Impact | Mitigation |
|-------|------|-------------|--------|------------|
| 1 | Data loss during migration | Low | Critical | Multiple backups, validation, parallel run |
| 1 | Cluster instability | Medium | High | Gradual deployment, monitoring, rollback plan |
| 1 | Network issues | Medium | High | Pre-deployment validation, firewall config |
| 1 | Performance degradation | Medium | Medium | Load testing, tuning, benchmarking |
| 2 | API breaking changes | Low | High | Comprehensive compatibility tests |
| 2 | UI bugs | Medium | Medium | User acceptance testing, beta program |
| 2 | Performance issues | Medium | High | Load testing, optimization |
| 2 | User resistance | High | Medium | Training, support, gradual rollout |

---

## Recommended Approach

### For Most Organizations

1. ✅ **Complete Phase 1 first** (4-6 weeks)
2. ⏸️ **Evaluate and stabilize** (2-4 weeks)
3. ✅ **Proceed to Phase 2** (10-12 weeks)
4. ✅ **Total**: 16-22 weeks (4-5.5 months)

### For Resource-Constrained Organizations

1. ✅ **Complete Phase 1** (4-6 weeks)
2. ⏸️ **Pause** (indefinite)
3. ✅ **Phase 2 when ready** (future)

### For Aggressive Timeline

1. ✅ **Phase 1 & 2 Overlap** (start Phase 2 planning during Phase 1)
2. ✅ **Total**: 12-14 weeks (3-3.5 months)
3. ⚠️ **Higher risk**: Less time to stabilize Phase 1

---

## Next Steps

### Immediate (This Week)

1. ✅ Review this plan with stakeholders
2. ✅ Get approval for Phase 1
3. ✅ Assign Phase 1 team members
4. ✅ Set up development environment

### Phase 1 Start (Week 1)

1. ✅ Kickoff meeting
2. ✅ Create project repository
3. ✅ Begin single-node dev setup
4. ✅ Daily standups

### Phase 1 Completion Review (Week 6-7)

1. ✅ Infrastructure audit
2. ✅ Team retrospective
3. ✅ Stakeholder demo
4. ✅ Go/No-Go decision for Phase 2

### Phase 2 Start (Week 8-9)

1. ✅ Phase 2 kickoff
2. ✅ Onboard development team
3. ✅ Begin UI foundation work
4. ✅ Sprint planning

---

**Document Version**: 2.0 (Two-Phase Approach)  
**Last Updated**: February 17, 2026  
**Status**: Ready for Review

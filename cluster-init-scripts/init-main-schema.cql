-- TQDB Main Node Schema Initialization
-- Optimized for Cassandra 5.0
-- Creates exchange-specific keyspaces with NetworkTopologyStrategy
-- Main node stores ALL exchange keyspaces

-- =============================================================================
-- CME Exchange Keyspace
-- =============================================================================
CREATE KEYSPACE IF NOT EXISTS tqdb_cme 
WITH REPLICATION = { 
    'class' : 'NetworkTopologyStrategy',
    'dc1' : 2
}
AND DURABLE_WRITES = true;

-- CME: Tick data table
CREATE TABLE IF NOT EXISTS tqdb_cme.tick (
    symbol text,
    datetime timestamp,
    keyval map<text, double>,
    type int,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC)
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_size': '1',
      'compaction_window_unit': 'DAYS',
      'timestamp_resolution': 'MICROSECONDS'
  }
  AND gc_grace_seconds = 86400
  AND comment = 'CME raw tick data';

-- CME: Symbol metadata
CREATE TABLE IF NOT EXISTS tqdb_cme.symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'CME symbol metadata';

-- CME: Minute bars
CREATE TABLE IF NOT EXISTS tqdb_cme.minbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC)
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_size': '1',
      'compaction_window_unit': 'DAYS',
      'timestamp_resolution': 'MICROSECONDS'
  }
  AND gc_grace_seconds = 86400
  AND comment = 'CME one-minute bars';

-- CME: Second bars
CREATE TABLE IF NOT EXISTS tqdb_cme.secbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC)
  AND compaction = {
      'class': 'TimeWindowCompactionStrategy',
      'compaction_window_size': '1',
      'compaction_window_unit': 'DAYS',
      'timestamp_resolution': 'MICROSECONDS'
  }
  AND gc_grace_seconds = 86400
  AND comment = 'CME one-second bars';

-- CME: Configuration
CREATE TABLE IF NOT EXISTS tqdb_cme.conf (
    confKey text PRIMARY KEY,
    confVal text
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'CME configuration';

-- =============================================================================
-- Insert Initial Configuration for CME Exchange
-- =============================================================================

-- CME configuration
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('schema_version', '1.0');
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('exchange', 'CME');
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('deployment_type', 'cluster');
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('replication_factor', '2');
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('cassandra_version', '5.0');
INSERT INTO tqdb_cme.conf (confKey, confVal) VALUES ('created_at', currentTimestamp());

-- =============================================================================
-- Verify Schema Creation
-- =============================================================================
DESCRIBE KEYSPACES;
DESCRIBE KEYSPACE tqdb_cme;

-- Display configuration
SELECT * FROM tqdb_cme.conf;

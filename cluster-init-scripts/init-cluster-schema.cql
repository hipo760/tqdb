-- TQDB Multi-Node Cluster Schema Initialization
-- Optimized for Cassandra 5.0
-- Creates exchange-specific keyspaces with NetworkTopologyStrategy
-- Main node stores ALL exchange keyspaces

-- =============================================================================
-- NYSE Exchange Keyspace
-- =============================================================================
CREATE KEYSPACE IF NOT EXISTS tqdb_nyse 
WITH REPLICATION = { 
    'class' : 'NetworkTopologyStrategy',
    'dc1' : 2
}
AND DURABLE_WRITES = true;

-- NYSE: Tick data table
CREATE TABLE IF NOT EXISTS tqdb_nyse.tick (
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
  AND comment = 'NYSE raw tick data';

-- NYSE: Symbol metadata
CREATE TABLE IF NOT EXISTS tqdb_nyse.symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'NYSE symbol metadata';

-- NYSE: Minute bars
CREATE TABLE IF NOT EXISTS tqdb_nyse.minbar (
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
  AND comment = 'NYSE one-minute bars';

-- NYSE: Second bars
CREATE TABLE IF NOT EXISTS tqdb_nyse.secbar (
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
  AND comment = 'NYSE one-second bars';

-- NYSE: Configuration
CREATE TABLE IF NOT EXISTS tqdb_nyse.conf (
    confKey text PRIMARY KEY,
    confVal text
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'NYSE configuration';

-- =============================================================================
-- NASDAQ Exchange Keyspace
-- =============================================================================
CREATE KEYSPACE IF NOT EXISTS tqdb_nasdaq 
WITH REPLICATION = { 
    'class' : 'NetworkTopologyStrategy',
    'dc1' : 2
}
AND DURABLE_WRITES = true;

-- NASDAQ: Tick data table
CREATE TABLE IF NOT EXISTS tqdb_nasdaq.tick (
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
  AND comment = 'NASDAQ raw tick data';

-- NASDAQ: Symbol metadata
CREATE TABLE IF NOT EXISTS tqdb_nasdaq.symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'NASDAQ symbol metadata';

-- NASDAQ: Minute bars
CREATE TABLE IF NOT EXISTS tqdb_nasdaq.minbar (
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
  AND comment = 'NASDAQ one-minute bars';

-- NASDAQ: Second bars
CREATE TABLE IF NOT EXISTS tqdb_nasdaq.secbar (
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
  AND comment = 'NASDAQ one-second bars';

-- NASDAQ: Configuration
CREATE TABLE IF NOT EXISTS tqdb_nasdaq.conf (
    confKey text PRIMARY KEY,
    confVal text
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'NASDAQ configuration';

-- =============================================================================
-- HKEX Exchange Keyspace
-- =============================================================================
CREATE KEYSPACE IF NOT EXISTS tqdb_hkex 
WITH REPLICATION = { 
    'class' : 'NetworkTopologyStrategy',
    'dc1' : 2
}
AND DURABLE_WRITES = true;

-- HKEX: Tick data table
CREATE TABLE IF NOT EXISTS tqdb_hkex.tick (
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
  AND comment = 'HKEX raw tick data';

-- HKEX: Symbol metadata
CREATE TABLE IF NOT EXISTS tqdb_hkex.symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'HKEX symbol metadata';

-- HKEX: Minute bars
CREATE TABLE IF NOT EXISTS tqdb_hkex.minbar (
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
  AND comment = 'HKEX one-minute bars';

-- HKEX: Second bars
CREATE TABLE IF NOT EXISTS tqdb_hkex.secbar (
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
  AND comment = 'HKEX one-second bars';

-- HKEX: Configuration
CREATE TABLE IF NOT EXISTS tqdb_hkex.conf (
    confKey text PRIMARY KEY,
    confVal text
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'HKEX configuration';

-- =============================================================================
-- Insert Initial Configuration for Each Exchange
-- =============================================================================

-- NYSE configuration
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('schema_version', '1.0');
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('exchange', 'NYSE');
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('deployment_type', 'cluster');
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('replication_factor', '2');
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('cassandra_version', '5.0');
INSERT INTO tqdb_nyse.conf (confKey, confVal) VALUES ('created_at', currentTimestamp());

-- NASDAQ configuration
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('schema_version', '1.0');
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('exchange', 'NASDAQ');
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('deployment_type', 'cluster');
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('replication_factor', '2');
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('cassandra_version', '5.0');
INSERT INTO tqdb_nasdaq.conf (confKey, confVal) VALUES ('created_at', currentTimestamp());

-- HKEX configuration
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('schema_version', '1.0');
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('exchange', 'HKEX');
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('deployment_type', 'cluster');
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('replication_factor', '2');
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('cassandra_version', '5.0');
INSERT INTO tqdb_hkex.conf (confKey, confVal) VALUES ('created_at', currentTimestamp());

-- =============================================================================
-- Verify Schema Creation
-- =============================================================================
DESCRIBE KEYSPACES;
DESCRIBE KEYSPACE tqdb_nyse;
DESCRIBE KEYSPACE tqdb_nasdaq;
DESCRIBE KEYSPACE tqdb_hkex;

-- Display configuration
SELECT * FROM tqdb_nyse.conf;
SELECT * FROM tqdb_nasdaq.conf;
SELECT * FROM tqdb_hkex.conf;

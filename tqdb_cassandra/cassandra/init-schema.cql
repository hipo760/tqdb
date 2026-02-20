-- TQDB Single-Node Schema Initialization
-- Optimized for Cassandra 5.0
-- Creates a single keyspace with all tables
-- For development and single-node deployments

-- Create keyspace with SimpleStrategy (single node)
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH REPLICATION = { 
    'class' : 'SimpleStrategy', 
    'replication_factor' : 1 
}
AND DURABLE_WRITES = true;

-- Tick data table
-- Stores raw tick data with bid/ask/last prices
CREATE TABLE IF NOT EXISTS tqdb1.tick (
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
  AND comment = 'Raw tick data with bid/ask/last prices';

-- Symbol metadata table
CREATE TABLE IF NOT EXISTS tqdb1.symbol (
    symbol text PRIMARY KEY,
    keyval map<text, text>
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'Symbol metadata and configuration';

-- Minute bar OHLCV data
CREATE TABLE IF NOT EXISTS tqdb1.minbar (
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
  AND comment = 'One-minute OHLCV bars';

-- Second bar OHLCV data
CREATE TABLE IF NOT EXISTS tqdb1.secbar (
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
  AND comment = 'One-second OHLCV bars';

-- Configuration table
CREATE TABLE IF NOT EXISTS tqdb1.conf (
    confKey text PRIMARY KEY,
    confVal text
) WITH compaction = {
      'class': 'SizeTieredCompactionStrategy'
  }
  AND comment = 'System configuration key-value store';

-- Insert initial configuration
-- Using currentTimestamp() (Cassandra 5.0 compatible)
INSERT INTO tqdb1.conf (confKey, confVal) VALUES ('schema_version', '1.0');
INSERT INTO tqdb1.conf (confKey, confVal) VALUES ('deployment_type', 'single-node');
INSERT INTO tqdb1.conf (confKey, confVal) VALUES ('cassandra_version', '5.0');
INSERT INTO tqdb1.conf (confKey, confVal) VALUES ('created_at', currentTimestamp());

-- Verify schema
DESCRIBE KEYSPACE tqdb1;

-- Display configuration
SELECT * FROM tqdb1.conf;

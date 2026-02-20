-- TQDB QuestDB Schema Initialization
-- Version: 1.0
-- Date: 2026-02-20
-- 
-- This script creates the QuestDB schema equivalent to Cassandra tqdb1 keyspace
-- Tables are optimized for 5-second update cycles with deduplication enabled

-- ============================================================================
-- Table: ohlcv_1sec (1-second OHLCV bars)
-- Equivalent to: Cassandra tqdb1.secbar
-- Purpose: Store 1-second aggregated OHLCV data
-- Update Pattern: Updated every 5 seconds, same key (timestamp, symbol) overwrites
-- ============================================================================

CREATE TABLE IF NOT EXISTS ohlcv_1sec (
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

COMMENT ON TABLE ohlcv_1sec IS 'One-second OHLCV bars updated every 5 seconds';


-- ============================================================================
-- Table: ohlcv_1min (1-minute OHLCV bars)
-- Equivalent to: Cassandra tqdb1.minbar
-- Purpose: Store 1-minute aggregated OHLCV data
-- Update Pattern: Updated every 5 seconds, same key (timestamp, symbol) overwrites
-- ============================================================================

CREATE TABLE IF NOT EXISTS ohlcv_1min (
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

COMMENT ON TABLE ohlcv_1min IS 'One-minute OHLCV bars updated every 5 seconds';


-- ============================================================================
-- Table: symbols (Symbol metadata)
-- Equivalent to: Cassandra tqdb1.symbol
-- Purpose: Store trading symbol metadata and configuration
-- Update Pattern: Infrequent updates (when new symbols added or info changes)
-- ============================================================================

CREATE TABLE IF NOT EXISTS symbols (
    symbol SYMBOL CAPACITY 256 CACHE INDEX,
    name STRING,
    exchange STRING,
    asset_type STRING,
    status STRING,
    first_trade TIMESTAMP,
    last_trade TIMESTAMP,
    updated_at TIMESTAMP
) timestamp(updated_at);

COMMENT ON TABLE symbols IS 'Symbol metadata and configuration';


-- ============================================================================
-- Verification Queries
-- ============================================================================

-- List all tables
-- SHOW TABLES;

-- Show table structures
-- SHOW COLUMNS FROM ohlcv_1sec;
-- SHOW COLUMNS FROM ohlcv_1min;
-- SHOW COLUMNS FROM symbols;

-- Check table parameters
-- SELECT * FROM tables() WHERE name IN ('ohlcv_1sec', 'ohlcv_1min', 'symbols');


-- ============================================================================
-- Sample Data Insertion (for testing)
-- ============================================================================

-- Insert test symbol
-- INSERT INTO symbols VALUES(
--     'BTCUSD.BYBIT',
--     'Bitcoin USD Perpetual',
--     'BYBIT',
--     'CRYPTO',
--     'ACTIVE',
--     '2024-01-01T00:00:00.000000Z',
--     '2026-02-20T23:59:59.000000Z',
--     systimestamp()
-- );

-- Insert test 1-minute bar
-- INSERT INTO ohlcv_1min VALUES(
--     'BTCUSD.BYBIT',
--     '2026-02-20T19:00:00.000000Z',
--     68000.0,
--     68100.0,
--     67900.0,
--     68050.0,
--     1000
-- );

-- Insert test 1-second bar
-- INSERT INTO ohlcv_1sec VALUES(
--     'BTCUSD.BYBIT',
--     '2026-02-20T19:00:00.000000Z',
--     68000.0,
--     68010.0,
--     67995.0,
--     68005.0,
--     100
-- );


-- ============================================================================
-- End of Schema Initialization
-- ============================================================================

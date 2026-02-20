-- TQDB Cassandra Schema Initialization
-- Version: 4.0
-- Compatible with: Cassandra 4.1+

-- Create keyspace if not exists
CREATE KEYSPACE IF NOT EXISTS tqdb1 
WITH replication = {
    'class': 'SimpleStrategy',
    'replication_factor': 1
};

USE tqdb1;

-- Symbol metadata table
CREATE TABLE IF NOT EXISTS symbol (
    symbol text PRIMARY KEY,
    name text,
    exchange text,
    currency text,
    timezone text,
    session_begin text,
    session_end text,
    lot_size int,
    tick_size double,
    created_at timestamp,
    updated_at timestamp
);

-- Tick data table (time-series)
CREATE TABLE IF NOT EXISTS tick (
    symbol text,
    datetime timestamp,
    epid int,
    price double,
    volume int,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);

-- 1-second bar data table
CREATE TABLE IF NOT EXISTS secbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);

-- 1-minute bar data table
CREATE TABLE IF NOT EXISTS minbar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);

-- Daily bar data table
CREATE TABLE IF NOT EXISTS daybar (
    symbol text,
    datetime timestamp,
    open double,
    high double,
    low double,
    close double,
    vol double,
    PRIMARY KEY (symbol, datetime)
) WITH CLUSTERING ORDER BY (datetime DESC);

-- Configuration table (for web interface settings)
CREATE TABLE IF NOT EXISTS config (
    key text PRIMARY KEY,
    value text,
    description text,
    updated_at timestamp
);

-- Alert configuration table
CREATE TABLE IF NOT EXISTS alert_config (
    symbol text,
    alert_type text,
    threshold double,
    enabled boolean,
    created_at timestamp,
    PRIMARY KEY (symbol, alert_type)
);

-- Insert sample configuration
INSERT INTO config (key, value, description, updated_at) 
VALUES ('version', '4.0', 'Schema version', toTimestamp(now())) 
IF NOT EXISTS;

INSERT INTO config (key, value, description, updated_at) 
VALUES ('timezone', 'Asia/Taipei', 'Default timezone', toTimestamp(now())) 
IF NOT EXISTS;

-- Create indexes for common queries
-- Note: Secondary indexes on high-cardinality columns should be used carefully
-- CREATE INDEX IF NOT EXISTS idx_symbol_exchange ON symbol(exchange);

DESCRIBE KEYSPACE tqdb1;

# CGI Scripts

Python CGI endpoints for the TQDB web interface (18 scripts).

## Symbol Management
- `qsymbol.py` - List all symbols
- `qsyminfo.py` - Query symbol metadata
- `usymbol.py` - Update symbol
- `qSymRefPrc.py` - Query reference prices
- `qSymSummery.py` - Symbol summary statistics

## Data Queries
- `q1min.py` - Query minute bars
- `q1sec.py` - Query second bars
- `q1day.py` - Query daily bars (aggregated from minutes)
- `qRange.py` - Query available date ranges

## Data Import
- `i1min_check.py` - Generate import commands
- `i1min_do.py` - Execute data import
- `i1min_readstatus.py` - Check import status

## Configuration & Editing
- `eConf.py` - Edit configuration
- `eData.py` - Edit/import data

## System & Utilities
- `qSystemInfo.py` - System information
- `qSupportTZ.py` - List available timezones (484 zones)
- `webcommon.py` - Common utility functions
- `cassandra_query.py` - Cassandra query helpers

## Environment Variables

All scripts use environment variables for configuration:
- `CASSANDRA_HOST` - Database host
- `CASSANDRA_PORT` - Database port
- `CASSANDRA_KEYSPACE` - Keyspace name
- `TOOLS_DIR` - Tools directory path

Scripts are executed by Apache as user `www-data`.

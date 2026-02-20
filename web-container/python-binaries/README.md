# Python Binaries

Python replacements for legacy C++ binaries.

## Files

### Query Scripts
- `qsym.py` - Query symbols from Cassandra
- `qtick.py` - Query tick data
- `qquote.py` - Query quote data

### Insert Scripts
- `itick.py` - Insert tick data
- `updtick.py` - Update tick data

### Common Library
- `cassandra_query.py` - Shared Cassandra utilities

## Usage

All binaries accept command-line arguments and use the cassandra-driver package:

```bash
# Query symbols
python3 qsym.py <host> <port> <keyspace> [symbol_pattern]

# Query ticks
python3 qtick.py <host> <port> <keyspace> <symbol> <begin_dt> <end_dt>

# Insert ticks
python3 itick.py <host> <port> <keyspace> <symbol> <csv_file>
```

These scripts are called by CGI scripts and shell scripts instead of C++ binaries.

# Scripts Directory

Data processing and query scripts for TQDB.

## Query Scripts (Python)

### Bar Data Queries
- `q1minall.py` - Query minute bars from Cassandra
- `q1secall.py` - Query second bars from Cassandra
- `q1dayall.py` - Aggregate daily bars from minute bars

### Usage
```bash
python3 q1minall.py <host> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip>
python3 q1secall.py <host> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip>
python3 q1dayall.py <host> <port> <keyspace> <symbol> <begin_dt> <end_dt> <output_file> <gzip> <mk_open> <mk_close>
```

## Data Import Scripts (Python)

- `Sym2Cass.py` - Import symbols to Cassandra
- `Min2Cass.py` - Import minute bars to Cassandra
- `Sec2Cass.py` - Import second bars to Cassandra
- `Min2Day.py` - Aggregate minute bars to daily bars
- `TQAlert.py` - Alert management

### Usage
```bash
python3 Sym2Cass.py <host> <port> <keyspace> <symbol> <keyval_json>
python3 Min2Cass.py <host> <port> <keyspace> <symbol> <csv_file>
python3 Sec2Cass.py <host> <port> <keyspace> <symbol> <csv_file>
```

## Utility Scripts

- `csvtzconv.py` - Convert CSV timezone
- `formatDT.py` - Format datetime strings

All scripts use environment variables or command-line parameters for Cassandra connection.

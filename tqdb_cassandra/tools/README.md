# TQDB Cassandra Tools

Python tools for managing TQDB Cassandra data transfers.

## Setup

This project uses `uv` for Python package management (Python 3.11+).

### Prerequisites

- `uv` package manager installed
- Access to source and target Cassandra instances
- Network connectivity between machines

### Install Dependencies

Dependencies are already configured in `pyproject.toml`. Just sync:

```bash
cd /home/ubuntu/services/tqdb/tqdb_cassandra/tools
uv sync
```

## Tools

### transfer_minbar.py

Transfers `tqdb1.minbar` table data from a source Cassandra instance to a target instance.

**Key Features:**
- ✅ **Symbol filtering**: Transfer specific symbols or all symbols
- ✅ **Sequential transfer**: Processes one symbol at a time (prevents memory issues)
- ✅ **Progress tracking**: Real-time progress bars with tqdm
- ✅ **Batch inserts**: Configurable batch size for performance tuning
- ✅ **Transfer statistics**: Detailed summary with rates and durations
- ✅ **Error handling**: Graceful error handling with detailed error messages
- ✅ **Authentication support**: Optional username/password for both source and target

## Usage

### Quick Start with Example Script

Edit `example_transfer.sh` and set your source host and symbols:

```bash
# Edit the script
nano example_transfer.sh

# Set SOURCE_HOST, TARGET_HOST, and SYMBOLS
# Then run:
./example_transfer.sh
```

### Direct Usage

**Transfer specific symbols:**
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --symbols AAPL,GOOGL,MSFT
```

**Transfer all symbols:**
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --all-symbols
```

**With custom batch size (for performance tuning):**
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --symbols AAPL \
    --batch-size 5000
```

**For large crypto symbols with lots of data:**
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --symbols BTCUSD.BYBIT,ETHUSD.BYBIT \
    --year-partition
```

**With authentication:**
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --source-user cassandra \
    --source-password mypassword \
    --target-host localhost \
    --target-user cassandra \
    --target-password mypassword \
    --symbols AAPL,GOOGL
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--source-host` | Source Cassandra IP/hostname (required) | - |
| `--source-port` | Source Cassandra port | 9042 |
| `--source-user` | Source username (optional) | - |
| `--source-password` | Source password (optional) | - |
| `--target-host` | Target Cassandra IP/hostname (required) | - |
| `--target-port` | Target Cassandra port | 9042 |
| `--target-user` | Target username (optional) | - |
| `--target-password` | Target password (optional) | - |
| `--symbols` | Comma-separated symbol list | - |
| `--all-symbols` | Transfer all symbols (mutually exclusive with --symbols) | - |
| `--batch-size` | Batch size for inserts | 1000 |
| `--timeout` | Query timeout in seconds (use higher for crypto symbols) | 120 |
| `--year-partition` | Use year-based partitioning (recommended for crypto) | False |

## How It Works

1. **Connection**: Establishes connections to both source and target Cassandra instances with configurable timeouts
2. **Symbol Discovery**: Fetches list of symbols (all or filtered)
3. **Sequential Processing**: Processes one symbol at a time to avoid memory issues
4. **Year-Based Partitioning** (optional): For large datasets, processes data year by year
   - Gets min/max year range for each symbol
   - Counts and transfers data one year at a time
   - Avoids timeout issues with large crypto symbols
5. **Row Counting**: Counts rows per symbol (or per year) for accurate progress tracking
6. **Streaming Transfer**: Uses fetch_size to stream large datasets without loading all data into memory
7. **Batch Transfer**: Reads data and inserts in configurable batches
8. **Progress Display**: Shows real-time progress bar for each symbol (and year if partitioned)
9. **Statistics**: Provides detailed transfer summary with rates and durations

## Special Considerations for Crypto Symbols

Cryptocurrency symbols (e.g., BTCUSD.BYBIT, ETHUSD.BYBIT) typically have:
- **24/7 trading data** (much more data than stock symbols)
- **Higher data volume** (can have millions of rows)
- **Longer transfer times**

For these symbols, use **year-based partitioning**:
```bash
uv run transfer_minbar.py \
    --source-host 192.168.1.100 \
    --target-host localhost \
    --symbols BTCUSD.BYBIT,ETHUSD.BYBIT,MBTCUSD.BYBIT,METHUSD.BYBIT \
    --year-partition \
    --batch-size 5000
```

**Benefits of year-based partitioning:**
- ✅ Avoids timeout on large COUNT queries
- ✅ Processes manageable chunks of data
- ✅ Better progress tracking (per year)
- ✅ Can resume from specific years if interrupted
- ✅ Works with Cassandra's partition key structure

## Example Output

### Standard Transfer
```
Connecting to source Cassandra at 192.168.1.100:9042...
✓ Connected to source
Connecting to target Cassandra at localhost:9042...
✓ Connected to target

Starting transfer of 3 symbols...
======================================================================

[1/3] Processing AAPL
  Counting rows for AAPL...
  Found 50,000 rows for AAPL
  AAPL: 100%|████████████████████| 50000/50000 [00:25<00:00, 1962.50rows/s]
  ✓ Completed AAPL: 50,000 rows in 25.48s

[2/3] Processing GOOGL
  Counting rows for GOOGL...
  Found 45,000 rows for GOOGL
  GOOGL: 100%|███████████████████| 45000/45000 [00:22<00:00, 2000.00rows/s]
  ✓ Completed GOOGL: 45,000 rows in 22.50s

[3/3] Processing MSFT
  Counting rows for MSFT...
  Found 48,000 rows for MSFT
  MSFT: 100%|████████████████████| 48000/48000 [00:24<00:00, 2000.00rows/s]
  ✓ Completed MSFT: 48,000 rows in 24.00s

======================================================================
TRANSFER SUMMARY
======================================================================
Symbols processed: 3
Total rows read:   143,000
Total rows written: 143,000
Total errors:      0
Total duration:    71.98s
Average rate:      1987.22 rows/sec

Per-symbol breakdown:
Symbol       Rows         Duration     Rate (rows/s)  
----------------------------------------------------------------------
AAPL         50,000       25.48        1,962.50       
GOOGL        45,000       22.50        2,000.00       
MSFT         48,000       24.00        2,000.00       
```

### Year-Partitioned Transfer (for crypto symbols)
```
Connecting to source Cassandra at 192.168.1.100:9042...
✓ Connected to source
Connecting to target Cassandra at localhost:9042...
✓ Connected to target

Starting transfer of 2 symbols...
Using year-based partitioning for large datasets
======================================================================

[1/2] Processing BTCUSD.BYBIT
  Getting year range for BTCUSD.BYBIT...
  Data spans 2020 to 2024
    Processing year 2020...
    Found 1,250,000 rows for 2020
    BTCUSD.BYBIT (2020): 100%|███| 1250000/1250000 [03:20<00:00, 6250.00rows/s]
    ✓ Completed 2020: 1,250,000 rows
    Processing year 2021...
    Found 1,500,000 rows for 2021
    BTCUSD.BYBIT (2021): 100%|███| 1500000/1500000 [04:00<00:00, 6250.00rows/s]
    ✓ Completed 2021: 1,500,000 rows
    Processing year 2022...
    Found 1,500,000 rows for 2022
    BTCUSD.BYBIT (2022): 100%|███| 1500000/1500000 [04:00<00:00, 6250.00rows/s]
    ✓ Completed 2022: 1,500,000 rows
    Processing year 2023...
    Found 1,500,000 rows for 2023
    BTCUSD.BYBIT (2023): 100%|███| 1500000/1500000 [04:00<00:00, 6250.00rows/s]
    ✓ Completed 2023: 1,500,000 rows
    Processing year 2024...
    Found 300,000 rows for 2024
    BTCUSD.BYBIT (2024): 100%|███| 300000/300000 [00:48<00:00, 6250.00rows/s]
    ✓ Completed 2024: 300,000 rows
  ✓ Completed BTCUSD.BYBIT: 6,050,000 rows in 16m08s

[2/2] Processing ETHUSD.BYBIT
  Getting year range for ETHUSD.BYBIT...
  Data spans 2020 to 2024
  ...

======================================================================
TRANSFER SUMMARY
======================================================================
Symbols processed: 2
Total rows read:   12,100,000
Total rows written: 12,100,000
Total errors:      0
Total duration:    32m16s
Average rate:      6250.00 rows/sec
```

## Performance Tuning

- **Year Partitioning**: Use `--year-partition` for crypto symbols or any symbol with millions of rows
- **Batch Size**: Increase `--batch-size` for faster transfers (try 5000-10000 for large datasets)
- **Timeout**: Increase `--timeout` for symbols with millions of rows (default 120s, try 300-600s)
  - Note: With `--year-partition`, timeout is less critical since queries are smaller
- **Network**: Ensure good network connectivity between source and target
- **Target Container**: Make sure target Cassandra has sufficient memory and CPU
- **Sequential Processing**: The tool processes one symbol at a time to prevent memory issues
- **Streaming**: The tool uses fetch_size to stream results, preventing memory overload for large datasets

## Troubleshooting

### Connection Failed
- Verify source/target hosts are accessible
- Check firewall rules for port 9042
- Verify Cassandra is running on both instances

### Slow Transfer
- Increase `--batch-size` (default 1000, try 5000-10000)
- Check network latency between machines
- Verify target Cassandra has sufficient resources

### Timeout Errors
- **Crypto symbols**: Use `--year-partition` to avoid timeouts on large datasets
- **Large datasets**: Alternatively, increase timeout value with `--timeout 300` or higher
- Year-based partitioning is the recommended solution as it divides the work into manageable chunks

### Memory Issues
- The tool processes one symbol at a time to avoid this
- If still occurring, reduce `--batch-size`

## Dependencies

- `cassandra-driver>=3.29.3` - Cassandra Python driver
- `tqdm>=4.67.3` - Progress bars

Managed with `uv` (see `pyproject.toml`).

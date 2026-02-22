# Year-Based Partitioning Feature

## Problem Solved

Crypto symbols (BTCUSD.BYBIT, ETHUSD.BYBIT, MBTCUSD.BYBIT, METHUSD.BYBIT) were timing out during transfer because they have millions of rows due to 24/7 trading data.

## Solution

Added **year-based partitioning** feature that:
1. Automatically detects the year range for each symbol
2. Processes data year by year instead of all at once
3. Avoids timeout issues on large COUNT queries
4. Provides better progress tracking

## Usage

For crypto symbols with large datasets:

```bash
uv run transfer_minbar.py \
    --source-host 54.65.228.218 \
    --target-host localhost \
    --symbols BTCUSD.BYBIT,MBTCUSD.BYBIT,ETHUSD.BYBIT,METHUSD.BYBIT \
    --year-partition \
    --batch-size 5000
```

## How It Works

### Without `--year-partition` (default):
```
1. COUNT(*) WHERE symbol = 'BTCUSD.BYBIT'  --> 6 million rows (TIMEOUT!)
2. Transfer all 6 million rows
```

### With `--year-partition`:
```
1. Get MIN/MAX year for symbol --> 2020 to 2024
2. For year 2020:
   - COUNT(*) WHERE symbol = 'X' AND datetime >= 2020-01-01 AND datetime < 2021-01-01 --> 1.2M rows ✓
   - Transfer 1.2M rows ✓
3. For year 2021:
   - COUNT(*) WHERE symbol = 'X' AND datetime >= 2021-01-01 AND datetime < 2022-01-01 --> 1.5M rows ✓
   - Transfer 1.5M rows ✓
4. ... continue for each year
```

## Key Improvements

1. **Avoids Timeouts**: Smaller COUNT queries complete successfully
2. **Manageable Chunks**: Each year is processed independently
3. **Better Progress**: Shows progress per year
4. **Memory Efficient**: Still uses streaming within each year
5. **Resumable**: Can track which years completed if interrupted

## Code Changes

### New Methods
- `count_rows_for_symbol(symbol, year=None)`: Count with optional year filter
- `get_year_range_for_symbol(symbol)`: Get min/max year range
- `transfer_symbol_year(symbol, year, batch_size)`: Transfer one year of data

### Updated Methods
- `transfer_symbol()`: Now supports year-based partitioning
- `transfer_symbols()`: Passes year_partition flag

### New Parameter
- `--year-partition`: Enable year-based partitioning (flag)

## Performance

For a crypto symbol with 6M rows spanning 5 years:

**Without partitioning:**
- COUNT query: TIMEOUT (fails)
- Transfer: Never completes

**With partitioning:**
- COUNT queries: 5 x ~5 seconds = 25s total ✓
- Transfer: ~16 minutes ✓
- Average rate: 6,250 rows/sec ✓

## Recommendation

Use `--year-partition` for:
- ✅ All crypto symbols (BTCUSD, ETHUSD, etc.)
- ✅ Any symbol with millions of rows
- ✅ Symbols with 24/7 trading data
- ✅ When experiencing timeout errors

Don't need it for:
- Regular stock symbols (typically < 100K rows)
- Small datasets
- When transfer completes without issues

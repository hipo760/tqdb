#!/usr/bin/env python3
"""
TQDB Cassandra Data Transfer Tool
Transfers minbar data from source Cassandra to target Cassandra container
with symbol filtering and progress tracking.

Usage:
    python transfer_minbar.py --source-host SOURCE_IP --target-host TARGET_IP --symbols SYMBOL1,SYMBOL2
    python transfer_minbar.py --source-host 192.168.1.100 --target-host localhost --symbols AAPL,GOOGL,MSFT
    python transfer_minbar.py --source-host 192.168.1.100 --target-host localhost --all-symbols
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from tqdm import tqdm
import time


class MinbarTransfer:
    """Handles transfer of minbar data between Cassandra instances."""
    
    def __init__(self, source_host: str, target_host: str, 
                 source_port: int = 9042, target_port: int = 9042,
                 source_user: Optional[str] = None, source_password: Optional[str] = None,
                 target_user: Optional[str] = None, target_password: Optional[str] = None,
                 timeout: int = 60):
        """Initialize connection parameters."""
        self.source_host = source_host
        self.target_host = target_host
        self.source_port = source_port
        self.target_port = target_port
        self.timeout = timeout
        
        # Authentication
        self.source_auth = None
        if source_user and source_password:
            self.source_auth = PlainTextAuthProvider(username=source_user, password=source_password)
        
        self.target_auth = None
        if target_user and target_password:
            self.target_auth = PlainTextAuthProvider(username=target_user, password=target_password)
        
        self.source_session = None
        self.target_session = None

    @staticmethod
    def is_transfer_symbol_allowed(symbol: str) -> bool:
        """Allow only symbols that pass transfer-time safety guards."""
        return not symbol.startswith("D_") and "'" not in symbol

    def filter_symbols_for_transfer(self, symbols: List[str]) -> List[str]:
        """Filter and report blocked symbols for transfer-only validation."""
        blocked = [s for s in symbols if not self.is_transfer_symbol_allowed(s)]
        if blocked:
            preview = ', '.join(blocked[:20])
            suffix = '' if len(blocked) <= 20 else ', ...'
            print(
                f"Skipping {len(blocked)} symbol(s) blocked by transfer guard "
                f"(prefix 'D_' or contains apostrophe): {preview}{suffix}"
            )
        return [s for s in symbols if self.is_transfer_symbol_allowed(s)]

    def ensure_symbol_exists(self, symbol: str) -> bool:
        """Ensure symbol metadata exists in target symbol table."""
        try:
            # Fast path: symbol already exists in target.
            exists_query = "SELECT symbol FROM tqdb1.symbol WHERE symbol = %s"
            target_row = self.target_session.execute(exists_query, [symbol], timeout=self.timeout).one()
            if target_row:
                return True

            # Try to copy metadata from source if available.
            source_keyval = None
            try:
                source_query = "SELECT keyval FROM tqdb1.symbol WHERE symbol = %s"
                source_row = self.source_session.execute(source_query, [symbol], timeout=self.timeout).one()
                if source_row and hasattr(source_row, 'keyval') and source_row.keyval:
                    source_keyval = dict(source_row.keyval)
            except Exception:
                # Source may not have symbol table or keyval column in older schemas.
                source_keyval = None

            if source_keyval is None:
                source_keyval = {
                    'DESC': '',
                    'BPV': '1',
                    'MKO': '0',
                    'MKC': '0',
                    'SSEC': '0'
                }

            try:
                insert_with_keyval = "INSERT INTO tqdb1.symbol (symbol, keyval) VALUES (%s, %s)"
                self.target_session.execute(insert_with_keyval, [symbol, source_keyval], timeout=self.timeout)
            except Exception:
                # Fallback for schemas without keyval column.
                insert_symbol_only = "INSERT INTO tqdb1.symbol (symbol) VALUES (%s)"
                self.target_session.execute(insert_symbol_only, [symbol], timeout=self.timeout)

            return True
        except Exception as e:
            print(f"  Warning: failed to ensure symbol metadata for {symbol}: {e}")
            return False
        
    def connect(self):
        """Establish connections to source and target Cassandra."""
        print(f"Connecting to source Cassandra at {self.source_host}:{self.source_port}...")
        try:
            source_cluster = Cluster(
                [self.source_host],
                port=self.source_port,
                auth_provider=self.source_auth,
                control_connection_timeout=self.timeout,
                connect_timeout=self.timeout
            )
            self.source_session = source_cluster.connect('tqdb1')
            # Set default timeout for all queries
            self.source_session.default_timeout = self.timeout
            print("✓ Connected to source")
        except Exception as e:
            print(f"✗ Failed to connect to source: {e}")
            sys.exit(1)
        
        print(f"Connecting to target Cassandra at {self.target_host}:{self.target_port}...")
        try:
            target_cluster = Cluster(
                [self.target_host],
                port=self.target_port,
                auth_provider=self.target_auth,
                control_connection_timeout=self.timeout,
                connect_timeout=self.timeout
            )
            self.target_session = target_cluster.connect('tqdb1')
            # Set default timeout for all queries
            self.target_session.default_timeout = self.timeout
            print("✓ Connected to target")
        except Exception as e:
            print(f"✗ Failed to connect to target: {e}")
            sys.exit(1)
    
    def get_all_symbols(self) -> List[str]:
        """Retrieve all unique symbols from source minbar table."""
        print("Fetching all symbols from source...")
        query = "SELECT DISTINCT symbol FROM tqdb1.minbar"
        rows = self.source_session.execute(query)
        symbols = sorted([row.symbol for row in rows])
        print(f"Found {len(symbols)} symbols")

        filtered_symbols = self.filter_symbols_for_transfer(symbols)
        if len(filtered_symbols) != len(symbols):
            print(f"Transfer symbol list after guard: {len(filtered_symbols)}")
        return filtered_symbols
    
    def count_rows_for_symbol(self, symbol: str, year: Optional[int] = None) -> int:
        """Count number of rows for a specific symbol, optionally filtered by year."""
        if year:
            query = "SELECT COUNT(*) FROM tqdb1.minbar WHERE symbol = %s AND datetime >= %s AND datetime < %s"
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            result = self.source_session.execute(query, [symbol, start_date, end_date], timeout=self.timeout * 2)
        else:
            query = "SELECT COUNT(*) FROM tqdb1.minbar WHERE symbol = %s"
            result = self.source_session.execute(query, [symbol], timeout=self.timeout * 2)
        return result.one().count
    
    def get_year_range_for_symbol(self, symbol: str) -> tuple:
        """Get the min and max year for a symbol's data."""
        query = "SELECT MIN(datetime) as min_dt, MAX(datetime) as max_dt FROM tqdb1.minbar WHERE symbol = %s"
        result = self.source_session.execute(query, [symbol], timeout=self.timeout * 2)
        row = result.one()
        if row.min_dt and row.max_dt:
            return (row.min_dt.year, row.max_dt.year)
        return (None, None)

    def get_last_bar_datetime(self, session, symbol: str):
        """Get latest minbar datetime for a symbol from the provided session."""
        query = "SELECT MAX(datetime) as max_dt FROM tqdb1.minbar WHERE symbol = %s"
        result = session.execute(query, [symbol], timeout=self.timeout * 2)
        row = result.one()
        return row.max_dt if row and row.max_dt else None

    def count_rows_for_symbol_range(self, symbol: str, start_dt, end_dt) -> int:
        """Count rows for a symbol between start/end datetime (inclusive)."""
        if start_dt is None:
            query = "SELECT COUNT(*) FROM tqdb1.minbar WHERE symbol = %s AND datetime <= %s"
            result = self.source_session.execute(query, [symbol, end_dt], timeout=self.timeout * 2)
        else:
            query = "SELECT COUNT(*) FROM tqdb1.minbar WHERE symbol = %s AND datetime >= %s AND datetime <= %s"
            result = self.source_session.execute(query, [symbol, start_dt, end_dt], timeout=self.timeout * 2)
        return result.one().count
    
    def transfer_symbol(self, symbol: str, batch_size: int = 1000, use_year_partition: bool = False,
                        avoid_repeat: bool = False) -> dict:
        """Transfer all data for a single symbol from source to target."""
        stats = {
            'symbol': symbol,
            'rows_read': 0,
            'rows_written': 0,
            'errors': 0,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        try:
            if avoid_repeat:
                source_last = self.get_last_bar_datetime(self.source_session, symbol)
                if not source_last:
                    print(f"  No source data found for {symbol}")
                    stats['end_time'] = datetime.now()
                    return stats

                target_last = self.get_last_bar_datetime(self.target_session, symbol)
                print(f"  Source last 1min bar: {source_last}")
                print(f"  Target last 1min bar: {target_last if target_last else 'None'}")

                if target_last and target_last > source_last:
                    print(f"  Target is ahead of source for {symbol}, skipping")
                    stats['end_time'] = datetime.now()
                    return stats

                range_start = target_last
                range_end = source_last
                total_rows = self.count_rows_for_symbol_range(symbol, range_start, range_end)
                if total_rows == 0:
                    print(f"  No incremental rows needed for {symbol}")
                    stats['end_time'] = datetime.now()
                    return stats

                self.ensure_symbol_exists(symbol)
                print(f"  Incremental transfer rows for {symbol}: {total_rows:,} ({range_start} -> {range_end})")
                range_stats = self.transfer_symbol_range(symbol, range_start, range_end, batch_size, total_rows)
                stats['rows_read'] = range_stats['rows_read']
                stats['rows_written'] = range_stats['rows_written']
                stats['errors'] = range_stats['errors']
                stats['end_time'] = datetime.now()

                duration = (stats['end_time'] - stats['start_time']).total_seconds()
                print(f"  ✓ Completed {symbol}: {stats['rows_written']:,} rows in {duration:.2f}s")
                return stats

            self.ensure_symbol_exists(symbol)

            if use_year_partition:
                # Get year range for this symbol
                print(f"  Getting year range for {symbol}...")
                min_year, max_year = self.get_year_range_for_symbol(symbol)
                
                if not min_year or not max_year:
                    print(f"  No data found for {symbol}")
                    stats['end_time'] = datetime.now()
                    return stats
                
                print(f"  Data spans {min_year} to {max_year}")
                
                # Transfer year by year
                for year in range(min_year, max_year + 1):
                    year_stats = self.transfer_symbol_year(symbol, year, batch_size)
                    stats['rows_read'] += year_stats['rows_read']
                    stats['rows_written'] += year_stats['rows_written']
                    stats['errors'] += year_stats['errors']
                
                stats['end_time'] = datetime.now()
                duration = (stats['end_time'] - stats['start_time']).total_seconds()
                print(f"  ✓ Completed {symbol}: {stats['rows_written']:,} rows in {duration:.2f}s")
            else:
                # Original method - transfer all at once
                # Count total rows (with extended timeout for large datasets)
                print(f"  Counting rows for {symbol}...")
                total_rows = self.count_rows_for_symbol(symbol)
                if total_rows == 0:
                    print(f"  No data found for {symbol}")
                    stats['end_time'] = datetime.now()
                    return stats
                
                print(f"  Found {total_rows:,} rows for {symbol}")
                
                year_stats = self.transfer_symbol_year(symbol, None, batch_size, total_rows)
                stats['rows_read'] = year_stats['rows_read']
                stats['rows_written'] = year_stats['rows_written']
                stats['errors'] = year_stats['errors']
                stats['end_time'] = datetime.now()
                
                duration = (stats['end_time'] - stats['start_time']).total_seconds()
                print(f"  ✓ Completed {symbol}: {stats['rows_written']:,} rows in {duration:.2f}s")
            
        except Exception as e:
            print(f"  ✗ Error transferring {symbol}: {e}")
            stats['end_time'] = datetime.now()
            stats['errors'] += 1
        
        return stats

    def transfer_symbol_range(self, symbol: str, start_dt, end_dt, batch_size: int,
                              total_rows: Optional[int] = None) -> dict:
        """Transfer data for a symbol from start_dt to end_dt (inclusive)."""
        stats = {
            'rows_read': 0,
            'rows_written': 0,
            'errors': 0
        }

        try:
            insert_query = """
                INSERT INTO tqdb1.minbar (symbol, datetime, open, high, low, close, vol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            prepared_insert = self.target_session.prepare(insert_query)

            if start_dt is None:
                select_query = """SELECT symbol, datetime, open, high, low, close, vol
                                 FROM tqdb1.minbar
                                 WHERE symbol = ? AND datetime <= ?"""
                statement = self.source_session.prepare(select_query)
                statement.fetch_size = 5000
                rows = self.source_session.execute(statement, [symbol, end_dt], timeout=None)
            else:
                select_query = """SELECT symbol, datetime, open, high, low, close, vol
                                 FROM tqdb1.minbar
                                 WHERE symbol = ? AND datetime >= ? AND datetime <= ?"""
                statement = self.source_session.prepare(select_query)
                statement.fetch_size = 5000
                rows = self.source_session.execute(statement, [symbol, start_dt, end_dt], timeout=None)

            desc = f"  {symbol} incremental"
            batch = []
            with tqdm(total=total_rows, desc=desc, unit="rows", leave=True) as pbar:
                for row in rows:
                    stats['rows_read'] += 1
                    try:
                        batch.append((
                            row.symbol,
                            row.datetime,
                            row.open,
                            row.high,
                            row.low,
                            row.close,
                            row.vol
                        ))

                        if len(batch) >= batch_size:
                            for record in batch:
                                self.target_session.execute(prepared_insert, record, timeout=self.timeout)
                            stats['rows_written'] += len(batch)
                            pbar.update(len(batch))
                            batch = []
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"\n    Warning: Error inserting row: {e}")

                if batch:
                    for record in batch:
                        self.target_session.execute(prepared_insert, record, timeout=self.timeout)
                    stats['rows_written'] += len(batch)
                    pbar.update(len(batch))

        except Exception as e:
            print(f"    ✗ Error transferring incremental range: {e}")
            stats['errors'] += 1

        return stats
    
    def transfer_symbol_year(self, symbol: str, year: Optional[int], batch_size: int, 
                            total_rows: Optional[int] = None) -> dict:
        """Transfer data for a symbol for a specific year (or all data if year is None)."""
        stats = {
            'rows_read': 0,
            'rows_written': 0,
            'errors': 0
        }
        
        try:
            # If year is specified, count rows for that year
            if year is not None:
                print(f"    Processing year {year}...")
                total_rows = self.count_rows_for_symbol(symbol, year)
                if total_rows == 0:
                    print(f"    No data for {year}")
                    return stats
                print(f"    Found {total_rows:,} rows for {year}")
            
            # Prepare insert statement
            insert_query = """
                INSERT INTO tqdb1.minbar (symbol, datetime, open, high, low, close, vol)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            prepared_insert = self.target_session.prepare(insert_query)
            
            # Fetch and transfer data with streaming (fetch_size limits memory usage)
            if year is not None:
                # Filter by year
                start_date = datetime(year, 1, 1)
                end_date = datetime(year + 1, 1, 1)
                select_query = """SELECT symbol, datetime, open, high, low, close, vol 
                                 FROM tqdb1.minbar 
                                 WHERE symbol = ? AND datetime >= ? AND datetime < ?"""
                statement = self.source_session.prepare(select_query)
                statement.fetch_size = 5000
                rows = self.source_session.execute(statement, [symbol, start_date, end_date], timeout=None)
            else:
                # No year filter
                select_query = "SELECT symbol, datetime, open, high, low, close, vol FROM tqdb1.minbar WHERE symbol = ?"
                statement = self.source_session.prepare(select_query)
                statement.fetch_size = 5000
                rows = self.source_session.execute(statement, [symbol], timeout=None)
            
            # Process rows with progress bar
            desc = f"    {symbol} ({year})" if year else f"  {symbol}"
            batch = []
            with tqdm(total=total_rows, desc=desc, unit="rows", leave=True) as pbar:
                for row in rows:
                    stats['rows_read'] += 1
                    
                    try:
                        # Add to batch
                        batch.append((
                            row.symbol,
                            row.datetime,
                            row.open,
                            row.high,
                            row.low,
                            row.close,
                            row.vol
                        ))
                        
                        # Execute batch when full
                        if len(batch) >= batch_size:
                            for record in batch:
                                self.target_session.execute(prepared_insert, record, timeout=self.timeout)
                            stats['rows_written'] += len(batch)
                            pbar.update(len(batch))
                            batch = []
                    
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"\n    Warning: Error inserting row: {e}")
                
                # Execute remaining batch
                if batch:
                    for record in batch:
                        self.target_session.execute(prepared_insert, record, timeout=self.timeout)
                    stats['rows_written'] += len(batch)
                    pbar.update(len(batch))
            
            if year is not None:
                print(f"    ✓ Completed {year}: {stats['rows_written']:,} rows")
            
        except Exception as e:
            if year:
                print(f"    ✗ Error transferring year {year}: {e}")
            else:
                print(f"    ✗ Error transferring data: {e}")
            stats['errors'] += 1
        
        return stats
    
    def transfer_symbols(self, symbols: List[str], batch_size: int = 1000,
                         use_year_partition: bool = False, avoid_repeat: bool = False) -> List[dict]:
        """Transfer data for multiple symbols sequentially."""
        symbols = self.filter_symbols_for_transfer(symbols)
        all_stats = []
        
        print(f"\nStarting transfer of {len(symbols)} symbols...")
        if avoid_repeat:
            print("Using avoid-repeat mode (tail incremental by last 1min bar)")
        if use_year_partition:
            print("Using year-based partitioning for large datasets")
        print("=" * 70)
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Processing {symbol}")
            stats = self.transfer_symbol(symbol, batch_size, use_year_partition, avoid_repeat)
            all_stats.append(stats)
            
            # Small delay between symbols
            if i < len(symbols):
                time.sleep(0.1)
        
        return all_stats
    
    def print_summary(self, all_stats: List[dict]):
        """Print transfer summary statistics."""
        print("\n" + "=" * 70)
        print("TRANSFER SUMMARY")
        print("=" * 70)
        
        total_rows_read = sum(s['rows_read'] for s in all_stats)
        total_rows_written = sum(s['rows_written'] for s in all_stats)
        total_errors = sum(s['errors'] for s in all_stats)
        
        print(f"Symbols processed: {len(all_stats)}")
        print(f"Total rows read:   {total_rows_read:,}")
        print(f"Total rows written: {total_rows_written:,}")
        print(f"Total errors:      {total_errors}")
        
        if all_stats:
            start_time = min(s['start_time'] for s in all_stats)
            end_time = max(s['end_time'] for s in all_stats if s['end_time'])
            total_duration = (end_time - start_time).total_seconds()
            print(f"Total duration:    {total_duration:.2f}s")
            
            if total_duration > 0:
                rate = total_rows_written / total_duration
                print(f"Average rate:      {rate:.2f} rows/sec")
        
        print("\nPer-symbol breakdown:")
        print(f"{'Symbol':<12} {'Rows':<12} {'Duration':<12} {'Rate (rows/s)':<15}")
        print("-" * 70)
        
        for stats in all_stats:
            if stats['end_time']:
                duration = (stats['end_time'] - stats['start_time']).total_seconds()
                rate = stats['rows_written'] / duration if duration > 0 else 0
                print(f"{stats['symbol']:<12} {stats['rows_written']:<12,} {duration:<12.2f} {rate:<15.2f}")
    
    def close(self):
        """Close connections."""
        if self.source_session:
            self.source_session.cluster.shutdown()
        if self.target_session:
            self.target_session.cluster.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description='Transfer minbar data between Cassandra instances',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transfer specific symbols
  python transfer_minbar.py --source-host 192.168.1.100 --target-host localhost --symbols AAPL,GOOGL,MSFT
  
  # Transfer all symbols
  python transfer_minbar.py --source-host 192.168.1.100 --target-host localhost --all-symbols
  
  # With authentication
  python transfer_minbar.py --source-host 192.168.1.100 --source-user cassandra --source-password pass \\
                            --target-host localhost --symbols AAPL,GOOGL
        """
    )
    
    # Connection parameters
    parser.add_argument('--source-host', required=True, help='Source Cassandra host IP/hostname')
    parser.add_argument('--source-port', type=int, default=9042, help='Source Cassandra port (default: 9042)')
    parser.add_argument('--source-user', help='Source Cassandra username')
    parser.add_argument('--source-password', help='Source Cassandra password')
    
    parser.add_argument('--target-host', required=True, help='Target Cassandra host IP/hostname')
    parser.add_argument('--target-port', type=int, default=9042, help='Target Cassandra port (default: 9042)')
    parser.add_argument('--target-user', help='Target Cassandra username')
    parser.add_argument('--target-password', help='Target Cassandra password')
    
    # Symbol filtering
    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument('--symbols', help='Comma-separated list of symbols to transfer')
    symbol_group.add_argument('--all-symbols', action='store_true', help='Transfer all symbols')
    
    # Performance tuning
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for inserts (default: 1000)')
    parser.add_argument('--timeout', type=int, default=120, help='Query timeout in seconds (default: 120, use higher for large datasets)')
    parser.add_argument('--year-partition', action='store_true', help='Use year-based partitioning for large datasets (recommended for crypto symbols)')
    parser.add_argument('--avoid-repeat', action='store_true',
                        help='Incremental mode: compare last 1min bar on target/source and transfer from target_last to source_last')
    
    args = parser.parse_args()
    
    # Initialize transfer
    transfer = MinbarTransfer(
        source_host=args.source_host,
        target_host=args.target_host,
        source_port=args.source_port,
        target_port=args.target_port,
        source_user=args.source_user,
        source_password=args.source_password,
        target_user=args.target_user,
        target_password=args.target_password,
        timeout=args.timeout
    )
    
    try:
        # Connect to both instances
        transfer.connect()
        
        # Get symbols to transfer
        if args.all_symbols:
            symbols = transfer.get_all_symbols()
        else:
            requested_symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
            symbols = transfer.filter_symbols_for_transfer(requested_symbols)
        
        if not symbols:
            print("No symbols to transfer")
            return
        
        # Perform transfer
        if args.avoid_repeat and args.year_partition:
            print("Warning: --avoid-repeat ignores year partition flow and uses direct datetime range transfer")

        all_stats = transfer.transfer_symbols(
            symbols, 
            batch_size=args.batch_size,
            use_year_partition=args.year_partition,
            avoid_repeat=args.avoid_repeat
        )
        
        # Print summary
        transfer.print_summary(all_stats)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Transfer interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        transfer.close()


if __name__ == '__main__':
    main()

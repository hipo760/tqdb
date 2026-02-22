# Bug Fix: Symbol List Not Showing All Symbols

## Issue
The `esymbol.html` page was only showing 1 symbol instead of all 27 symbols in the database. Additionally, symbols were not sorted alphabetically.

## Root Cause
In `/tqdb_cassandra/web/cgi-bin/qsyminfo.py` at line 93, the command to query symbols had a hardcoded limit of `1`:

```python
command = f"python3 {python_binaries_dir}/qsym.py {CASSANDRA_IP} {CASSANDRA_PORT} {CASSANDRA_DB}.symbol 0 {symbol} 1 > {temp_file}"
                                                                                                                           ↑
                                                                                                                    This should be 10000
```

## Fix
1. Changed the limit from `1` to `10000` to allow fetching all symbols:

```python
command = f"python3 {python_binaries_dir}/qsym.py {CASSANDRA_IP} {CASSANDRA_PORT} {CASSANDRA_DB}.symbol 0 {symbol} 10000 > {temp_file}"
```

2. Added sorting by symbol name alphabetically (A-Z):

```python
# Sort symbols alphabetically by symbol name
symbol_objects.sort(key=lambda x: x.get('symbol', ''))
```

## Verification
Before fix:
```bash
curl -s "http://localhost:2380/cgi-bin/qsyminfo.py?symbol=ALL" | python3 -c "import json, sys; data=json.load(sys.stdin); print(f'Found {len(data)} symbols')"
# Output: Found 1 symbols
```

After fix:
```bash
curl -s "http://localhost:2380/cgi-bin/qsyminfo.py?symbol=ALL" | python3 -c "import json, sys; data=json.load(sys.stdin); print(f'Found {len(data)} symbols')"
# Output: Found 27 symbols (sorted A-Z: BTCUSD, BTCUSD.BYBIT, BTCUSD.BYBIT.BYBIT, ...)
```

## Files Changed
1. `/tqdb_cassandra/web/cgi-bin/qsyminfo.py` - Fixed the limit parameter
2. `/tqdb_cassandra/web/html/esymbol.html` - Added console logging for debugging

## Deployment Notes
Since the files are baked into the Docker image, you need to either:

1. **Quick fix (temporary)**: Copy files into running container:
   ```bash
   docker cp tqdb_cassandra/web/cgi-bin/qsyminfo.py tqdb-web:/var/www/cgi-bin/qsyminfo.py
   docker cp tqdb_cassandra/web/html/esymbol.html tqdb-web:/var/www/html/esymbol.html
   ```

2. **Permanent fix**: Rebuild and restart the container:
   ```bash
   cd tqdb_cassandra/web
   docker-compose down
   docker-compose build
   docker-compose up -d
   ```

3. **Development setup**: Add volume mounts in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./logs:/var/log/apache2
     - ./cgi-bin:/var/www/cgi-bin      # Add this for CGI scripts
     - ./html:/var/www/html             # Add this for HTML files
   ```

## Date
February 21, 2026

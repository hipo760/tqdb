# TQDB Tools - Python 3 Refactored Scripts

This directory contains refactored Python 3 versions of the TQDB data processing tools.

## Refactored Scripts

### 1. Min2Cass.py
- **Purpose**: Imports minute bar data into Cassandra database
- **Table**: `minbar`
- **Input Format**: Date,Time,Open,High,Low,Close,Volume
- **Usage**: `python Min2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol>`

### 2. Sec2Cass.py
- **Purpose**: Imports second bar data into Cassandra database
- **Table**: `secbar`
- **Input Format**: Date,Time,Open,High,Low,Close,Volume
- **Usage**: `python Sec2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol>`

### 3. Min2Day.py
- **Purpose**: Aggregates minute bar data into daily bars
- **Input Format**: Date,Time,Open,High,Low,Close,Volume
- **Output Format**: Date,Open,High,Low,Close,Volume[,LastTimestamp] (debug mode)
- **Usage**: `python Min2Day.py <market_open_time> <market_close_time> [debug_flag]`

### 4. Sym2Cass.py
- **Purpose**: Manages symbol information in Cassandra database (insert/update/delete)
- **Table**: `symbol`
- **Data Format**: JSON with trading parameters (DESC, BPV, MKO, MKC, SSEC)
- **Usage**: `python Sym2Cass.py <cassandra_ip> <cassandra_port> <database_name> <symbol> <json_data_or_delete>`

### 5. TQAlert.py
- **Purpose**: Monitors trading data streams and sends alerts for missing ticks/quotes
- **Configuration**: Stored in Cassandra as JSON with time rules and alert commands
- **Features**: Market hours awareness, alert throttling, test mode, hot config reload
- **Usage**: `python TQAlert.py` (runs as daemon)

## Key Differences Between Scripts

### Min2Cass.py vs Sec2Cass.py
The main differences are:
1. **Target Table**: `minbar` vs `secbar`
2. **Time Parsing**: Min2Cass converts float time values, Sec2Cass uses integer time values
3. **Data Granularity**: Minute-level vs second-level data

### Sym2Cass.py - Symbol Management
- **Purpose**: Manages trading symbol metadata and configuration
- **Operations**: Insert, Update, Delete symbol information
- **Data Storage**: JSON format with trading parameters
- **Key Features**: Parameterized queries for security, comprehensive error handling

### TQAlert.py - Trading Data Monitor
- **Purpose**: Real-time monitoring of trading data streams for missing ticks/quotes
- **Operations**: Continuous monitoring with configurable time rules and alert commands  
- **Key Features**: Market hours awareness, weekday scheduling, alert throttling, configuration hot-reload

### Python 3 Improvements Made
1. **Compatibility**: Updated to Python 3 syntax and features
2. **Error Handling**: Replaced bare `except:` with specific exception handling
3. **Code Structure**: Broke down monolithic functions into smaller, focused functions
4. **Documentation**: Added comprehensive docstrings and comments
5. **Type Safety**: Improved variable naming and type consistency
6. **F-strings**: Used modern string formatting
7. **Resource Management**: Added proper connection cleanup

## Dependencies

All scripts require the `cassandra-driver` package:
```bash
pip install -r requirements.txt
```

## Examples

### Import minute bars:
```bash
cat minute_data.csv | python Min2Cass.py 192.168.1.217 9042 TQDB AAPL
```

### Import second bars:
```bash
cat second_data.csv | python Sec2Cass.py 192.168.1.217 9042 TQDB AAPL
```

### Convert minutes to daily bars:
```bash
cat minute_data.csv | python Min2Day.py 84500 134500 1
```

### Manage symbols:
```bash
# Insert/update symbol with trading parameters
python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL '{"DESC":"Apple Inc","BPV":"0.01","MKO":"93000","MKC":"160000"}'

### Monitor trading data streams:
```bash
# Start the alert monitoring daemon
python TQAlert.py

# Test alert commands
touch /tmp/TQAlert/TQAlert.testcmd.0

# Temporarily mute symbol alerts
touch /tmp/TQAlert/TQAlert.skip.AAPL
```

## Legacy Versions

The original Python 2 versions are preserved in the `python_legacy/` directory.

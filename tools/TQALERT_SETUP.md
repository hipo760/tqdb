# TQAlert Setup and Testing Guide

## Prerequisites
1. Python 3.6+ with cassandra-driver package
2. Cassandra database with configuration table
3. Required directories and permissions

## Installation
```bash
# Install dependencies
pip install cassandra-driver

# Create required directories
mkdir -p /tmp/TQAlert
mkdir -p /tmp/lastTQ

# Set permissions (if needed)
chmod 755 /tmp/TQAlert /tmp/lastTQ
```

## Initial Configuration

### 1. Insert Configuration into Cassandra
```sql
-- Create configuration if it doesn't exist
INSERT INTO tqdb1.conf (confKey, confVal) VALUES (
    'tqconf',
    '{"TimeRule":{"TEST":[["1111111",90000,180000,60,30]]},"AlertCMD":["echo \"{HEADER}: {BODY}\""]}'
);
```

### 2. Create Test Timestamp Files
```bash
# Create test symbol timestamp files
echo $(date +%s) > /tmp/lastTQ/TEST.LastT
echo $(date +%s) > /tmp/lastTQ/TEST.LastQ
```

## Running TQAlert
```bash
# Start the monitoring system
python TQAlert.py
```

The system will:
1. Load configuration from Cassandra
2. Start monitoring based on time rules
3. Log all activities with timestamps
4. Send alerts when thresholds are exceeded

## Testing

### Test 1: Basic Functionality
```bash
# 1. Start TQAlert
python TQAlert.py

# 2. In another terminal, simulate missing data by not updating timestamps
# Wait for the configured threshold (60 seconds for ticks, 30 for quotes)

# 3. Observe alert generation in TQAlert logs
```

### Test 2: Command Testing
```bash
# Test alert command #0 without real alert condition
touch /tmp/TQAlert/TQAlert.testcmd.0

# Check TQAlert logs for test command execution
```

### Test 3: Symbol Muting
```bash
# Mute alerts for TEST symbol
touch /tmp/TQAlert/TQAlert.skip.TEST

# Verify no alerts are generated (check logs)

# Remove mute file
rm /tmp/TQAlert/TQAlert.skip.TEST
```

### Test 4: Configuration Reload
```bash
# Update configuration in Cassandra (change thresholds, add symbols, etc.)

# Trigger configuration reload
echo $(date +%s) > /tmp/TQAlert/TQAlert.confchange

# Verify new configuration is loaded (check logs)
```

## Troubleshooting

### Common Issues:

1. **"No configuration data found"**
   - Check Cassandra connectivity
   - Verify configuration exists in conf table
   - Check keyspace name (default: tqdb1)

2. **"Could not create directory"**
   - Check filesystem permissions
   - Ensure /tmp is writable
   - May need to adjust directory paths for Windows

3. **Commands not executing**
   - Check command syntax and escaping
   - Verify commands are not commented out (#)
   - Check shell environment and PATH

4. **No alerts generated**
   - Verify timestamp files exist and are being updated
   - Check time rule configuration (weekdays, hours)
   - Ensure current time is within monitoring window
   - Check for skip files

### Log Analysis:
- Look for "Time Rules:" section showing loaded configuration
- Monitor "Current WeekVal" messages for time/day status
- Watch for "Q-->" and "T-->" messages showing timestamp checks
- Alert generation shows "!!!No Tick Alert!!!" or "!!!No Quote Alert!!!"

### Performance Monitoring:
- Memory usage should be minimal (configuration + tracking data)
- CPU usage spikes only during alert command execution
- Network usage depends on configured alert commands

## Production Deployment

### Systemd Service (Linux)
```ini
[Unit]
Description=TQAlert Trading Monitor
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/tqdb/tools
ExecStart=/usr/bin/python3 TQAlert.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### Windows Service
Use NSSM or similar service wrapper:
```cmd
nssm install TQAlert "C:\Python3\python.exe" "C:\dev\AutoTrade\tqdb\tools\TQAlert.py"
nssm set TQAlert AppDirectory "C:\dev\AutoTrade\tqdb\tools"
nssm start TQAlert
```

### Monitoring
- Set up log rotation for output
- Monitor process health
- Consider alerting on TQAlert itself (meta-monitoring)
- Regular testing of alert delivery mechanisms

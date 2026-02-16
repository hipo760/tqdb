# TQAlert Configuration Documentation

## Overview
TQAlert is a monitoring system that watches trading data streams and alerts when symbols stop receiving ticks or quotes for configured time periods.

## Configuration Storage
Configuration is stored in Cassandra in the `conf` table:
- Key: `tqconf`
- Value: JSON configuration with `TimeRule` and `AlertCMD` sections

## Configuration Format

### Complete Example:
```json
{
    "TimeRule": {
        "AAPL": [
            [1111100, 93000, 160000, 60, 30],
            [1111100, 200000, 230000, 120, 60]
        ],
        "EURUSD": [
            [1111111, 220000, 220000, 30, 15]
        ]
    },
    "AlertCMD": [
        "echo '{HEADER}: {BODY}' | mail -s 'TQAlert' admin@example.com",
        "curl -X POST http://alerts.example.com/webhook -d '{\"msg\":\"{BODY}\"}'",
        "#echo 'Disabled command: {HEADER}'"
    ]
}
```

## TimeRule Format
Each symbol can have multiple time rules as arrays:
`[WeekVal, BeginTime, EndTime, TickSeconds, QuoteSeconds]`

### Parameters:
- **WeekVal**: Weekday bitmap (7 digits)
  - `1111100` = Monday-Friday (Mon=1000000, Tue=0100000, ..., Sun=0000001)
  - `1111111` = All days including weekend
  - `0000011` = Saturday-Sunday only

- **BeginTime/EndTime**: Market hours in HHMMSS format
  - `93000` = 09:30:00 (9:30 AM)
  - `160000` = 16:00:00 (4:00 PM)
  - For 24-hour markets: Set BeginTime = EndTime (e.g., `220000, 220000`)

- **TickSeconds**: Alert if no ticks received for this many seconds (0 = disabled)
- **QuoteSeconds**: Alert if no quotes received for this many seconds (0 = disabled)

## Alert Commands
Commands are shell commands with placeholder substitution:
- `{HEADER}`: Alert type ("No Tick Alert" or "No Quote Alert")
- `{BODY}`: Detailed message (e.g., "AAPL has no tick for 60 seconds!")
- Commands starting with `#` are disabled/commented out

## Control Files

### Skip Files (Temporary Muting)
Create files to temporarily mute alerts for specific symbols:
```bash
# Mute AAPL alerts
touch /tmp/TQAlert/TQAlert.skip.AAPL

# Mute EURUSD alerts
touch /tmp/TQAlert/TQAlert.skip.EURUSD
```
Files are automatically cleaned up after 24 hours.

### Test Commands
Test alert commands without real alerts:
```bash
# Test command #0 (first command in AlertCMD array)
touch /tmp/TQAlert/TQAlert.testcmd.0

# Test command #1 (second command)
touch /tmp/TQAlert/TQAlert.testcmd.1
```

### Configuration Reload
Force configuration reload:
```bash
# Update timestamp to trigger reload
echo $(date +%s) > /tmp/TQAlert/TQAlert.confchange
```

## Timestamp Files
The system reads last activity timestamps from:
- `/tmp/lastTQ/{SYMBOL}.LastT` - Last tick time
- `/tmp/lastTQ/{SYMBOL}.LastQ` - Last quote time

These files should contain Unix timestamps and are typically updated by data feed processes.

## Example Configurations

### Stock Market (9:30 AM - 4:00 PM, Mon-Fri)
```json
"AAPL": [
    [1111100, 93000, 160000, 60, 30]
]
```

### Forex (24/5 trading, Sun 5PM - Fri 5PM)
```json
"EURUSD": [
    [1111100, 170000, 170000, 30, 15],
    [0000001, 170000, 235959, 30, 15],
    [1000000, 0, 170000, 30, 15]
]
```

### Futures (Extended hours)
```json
"ES": [
    [1111100, 84500, 84500, 45, 30]
]
```

## Monitoring and Logs
- All activities are logged with timestamps
- Log messages include rule matching, alert generation, and command execution
- Current rules are displayed when weekday changes
- Status information shows current time and active monitoring state

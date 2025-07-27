# Symbol Configuration Documentation

## Symbol Parameters

The following parameters can be configured for each symbol:

### Core Parameters:
- **DESC**: Symbol description/name (string)
- **BPV**: Base Point Value - the monetary value of one tick/pip (string)
- **MKO**: Market Open time in HHMMSS format (string)
- **MKC**: Market Close time in HHMMSS format (string)  
- **SSEC**: Seconds granularity flag (string, "0" or "1")

### Default Values:
```json
{
    "DESC": "",
    "BPV": "1",
    "MKO": "0",
    "MKC": "0",
    "SSEC": "0"
}
```

## Usage Examples:

### Stock Symbol (AAPL):
```bash
python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL '{"DESC":"Apple Inc","BPV":"0.01","MKO":"93000","MKC":"160000"}'
```

### Forex Pair (EURUSD):
```bash
python Sym2Cass.py 192.168.1.217 9042 TQDB EURUSD '{"DESC":"Euro/US Dollar","BPV":"0.0001","MKO":"220000","MKC":"220000","SSEC":"1"}'
```

### Futures Contract (ES):
```bash
python Sym2Cass.py 192.168.1.217 9042 TQDB ES '{"DESC":"E-mini S&P 500","BPV":"12.50","MKO":"84500","MKC":"160500"}'
```

### Delete Symbol:
```bash
python Sym2Cass.py 192.168.1.217 9042 TQDB AAPL delete
```

## Market Hours Format:
- Time format: HHMMSS (6 digits)
- Examples:
  - 93000 = 09:30:00 (9:30 AM)
  - 160000 = 16:00:00 (4:00 PM)
  - 220000 = 22:00:00 (10:00 PM)

## Special Cases:
- **24-hour markets**: Set MKO = MKC (e.g., "220000")
- **Overnight sessions**: MKO > MKC (e.g., MKO="220000", MKC="060000")

# Python 2 to Python 3 Migration Guide for TQDB Tools

## Overview
All TQDB tools have been successfully refactored from Python 2 to Python 3 with significant improvements in functionality, security, and maintainability.

## Refactored Scripts Summary

### 1. Min2Cass.py ✅
**Purpose**: Import minute bar data into Cassandra  
**Key Changes**:
- Python 3 compatibility (f-strings, integer division, timestamp handling)
- Modular function design with proper error handling
- Parameterized database queries for security
- Comprehensive input validation and progress reporting

### 2. Sec2Cass.py ✅  
**Purpose**: Import second bar data into Cassandra  
**Key Changes**:
- Same improvements as Min2Cass.py but optimized for second-level data
- Targets `secbar` table instead of `minbar`
- Enhanced time parsing for second precision

### 3. Min2Day.py ✅
**Purpose**: Aggregate minute bars into daily bars  
**Key Changes**:
- Market hours handling with overnight session support
- Improved date/time parsing and validation
- Clean separation of concerns with helper functions
- Enhanced debug output and error reporting

### 4. Sym2Cass.py ✅
**Purpose**: Manage symbol information in Cassandra  
**Key Changes**:
- Secure parameterized queries (prevents SQL injection)
- JSON validation and error handling
- Default parameter merging for symbol configuration
- Comprehensive command-line argument validation

### 5. TQAlert.py ✅
**Purpose**: Monitor trading data streams and send alerts  
**Key Changes**:
- Complete restructure with modular design
- Enhanced configuration management with hot-reload
- Robust error recovery and logging
- Cross-platform compatibility improvements

## Breaking Changes

### Command Line Interface
All scripts maintain backward compatibility for command-line arguments, but error messages and output formatting have improved.

### Dependencies
- **Required**: Python 3.6+
- **Required**: `cassandra-driver>=3.25.0`
- **Removed**: `urllib2`, `cgi`, `cgitb` (Python 2 specific)

### File Paths
Scripts now use cross-platform path handling, but temporary file locations remain the same for compatibility:
- `/tmp/TQAlert/` - Alert system files
- `/tmp/lastTQ/` - Timestamp tracking files

## Migration Steps

### 1. Environment Setup
```powershell
# Install Python 3 dependencies
pip install -r requirements.txt

# Verify Python 3 is being used
python --version  # Should show Python 3.6+
```

### 2. Backup Existing Scripts
```powershell
# Scripts are already backed up in python_legacy/ directory
# Original functionality is preserved
```

### 3. Test New Scripts
```powershell
# Test basic functionality
python Min2Cass.py --help
python Sym2Cass.py 192.168.1.217 9042 TQDB TEST '{"DESC":"Test Symbol"}'
```

### 4. Update Service/Cron Jobs
Replace Python 2 script calls with Python 3 versions:
```powershell
# Old: python2 Min2Cass.py ...
# New: python Min2Cass.py ...
```

## New Features

### Enhanced Error Handling
- Specific exception handling instead of bare `except:`
- Detailed error messages with context
- Graceful degradation and recovery

### Improved Logging
- Timestamp-based logging in TQAlert
- Progress reporting in data import scripts
- Debug modes with verbose output

### Security Improvements
- Parameterized database queries
- Input validation and sanitization
- Protected against injection attacks

### Better Configuration
- JSON validation in Sym2Cass and TQAlert
- Default value handling
- Configuration hot-reload in TQAlert

## Testing

### Data Import Scripts
```powershell
# Test with sample data
echo "20250127,084500,100.0,101.0,99.5,100.5,1000" | python Min2Cass.py 192.168.1.217 9042 TQDB TEST
```

### Symbol Management
```powershell
# Test symbol operations
python Sym2Cass.py 192.168.1.217 9042 TQDB TEST '{"DESC":"Test","BPV":"0.01"}'
python Sym2Cass.py 192.168.1.217 9042 TQDB TEST delete
```

### Alert System
```powershell
# Test alert monitoring (requires configuration in Cassandra)
python TQAlert.py
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```
   Solution: pip install cassandra-driver
   ```

2. **Path Issues (Windows)**
   ```
   # Temp directories need to be created manually on Windows
   mkdir C:\tmp\TQAlert
   mkdir C:\tmp\lastTQ
   ```

3. **Permission Errors**
   ```
   Solution: Run with appropriate permissions or adjust temp directory paths
   ```

4. **Database Connection Issues**
   ```
   Solution: Verify Cassandra connectivity and keyspace existence
   ```

## Performance Improvements

### Memory Usage
- More efficient string handling with f-strings
- Better resource management with context managers
- Reduced memory leaks through proper cleanup

### Error Recovery
- Automatic reconnection handling
- Graceful degradation on errors
- Better exception propagation

### Code Maintainability
- Modular function design
- Comprehensive documentation
- Type hints and clear variable naming

## Rollback Plan

If issues arise, the original Python 2 scripts are preserved in the `python_legacy/` directory:

```powershell
# Emergency rollback (temporarily)
cp python_legacy\Min2Cass_copy.py Min2Cass.py
# Use python2 command if available
```

## Support

### Documentation Files
- `REFACTORED_README.md` - Overview of all refactored scripts
- `SYMBOL_CONFIG.md` - Symbol configuration guide
- `TQALERT_CONFIG.md` - Alert system configuration
- `TQALERT_SETUP.md` - Alert system setup guide

### Getting Help
- Check error messages and logs for specific issues
- Verify configuration format matches documentation
- Test with minimal examples before full deployment
- Review the comprehensive docstrings in each script

## Future Enhancements

The refactored codebase is now ready for:
- Type hints for better IDE support
- Async/await for improved performance
- Configuration file support (YAML/TOML)
- Enhanced monitoring and metrics
- Docker containerization
- Unit test coverage

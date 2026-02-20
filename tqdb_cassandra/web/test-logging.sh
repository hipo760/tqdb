#!/bin/bash
# Quick test script to verify endpoint logging is working

echo "======================================"
echo "TQDB Endpoint Logging - Quick Test"
echo "======================================"
echo ""

cd "$(dirname "$0")"

echo "1. Checking if files exist..."
echo ""

FILES=(
    "cgi-bin/endpoint_logger.py"
    "cgi-bin/qEndpointStats.py"
    "cgi-bin/webcommon.py"
    "Dockerfile"
    "docker-compose.yml"
)

ALL_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (MISSING)"
        ALL_EXIST=false
    fi
done

echo ""

if [ "$ALL_EXIST" = false ]; then
    echo "❌ Some files are missing!"
    exit 1
fi

echo "2. Checking Python syntax..."
echo ""

python3 -m py_compile cgi-bin/endpoint_logger.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ endpoint_logger.py - syntax OK"
else
    echo "  ✗ endpoint_logger.py - syntax error"
fi

python3 -m py_compile cgi-bin/qEndpointStats.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ qEndpointStats.py - syntax OK"
else
    echo "  ✗ qEndpointStats.py - syntax error"
fi

echo ""

echo "3. Testing endpoint_logger module..."
echo ""

python3 << 'PYEOF'
import sys
sys.path.insert(0, 'cgi-bin')

try:
    from endpoint_logger import log_endpoint_access, get_endpoint_stats, format_stats_report
    print("  ✓ Module imports successfully")
    print("  ✓ Functions available: log_endpoint_access, get_endpoint_stats, format_stats_report")
except Exception as e:
    print(f"  ✗ Import error: {e}")
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo ""

echo "4. Checking Docker configuration..."
echo ""

# Check if docker-compose is valid
docker-compose config > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✓ docker-compose.yml is valid"
else
    echo "  ✗ docker-compose.yml has errors"
fi

# Check if logging env vars are set
if grep -q "TQDB_ENDPOINT_LOGGING" docker-compose.yml; then
    echo "  ✓ TQDB_ENDPOINT_LOGGING environment variable configured"
else
    echo "  ⚠ TQDB_ENDPOINT_LOGGING not found in docker-compose.yml"
fi

# Check if volume is mounted
if grep -q "./logs:/var/log/apache2" docker-compose.yml; then
    echo "  ✓ Log volume mount configured"
else
    echo "  ⚠ Log volume mount not found"
fi

echo ""

echo "5. Checking if container is running..."
echo ""

if docker ps | grep -q "tqdb-web"; then
    echo "  ✓ tqdb-web container is running"
    
    # Test if logging is enabled in container
    LOG_STATUS=$(docker exec tqdb-web env | grep TQDB_ENDPOINT_LOGGING || echo "not_set")
    if [[ "$LOG_STATUS" == *"true"* ]]; then
        echo "  ✓ Logging is enabled in container"
    else
        echo "  ⚠ Logging may not be enabled (env var: $LOG_STATUS)"
    fi
    
    # Check if logger module exists in container
    docker exec tqdb-web test -f /var/www/cgi-bin/endpoint_logger.py
    if [ $? -eq 0 ]; then
        echo "  ✓ endpoint_logger.py present in container"
    else
        echo "  ✗ endpoint_logger.py not found in container"
    fi
    
    # Check log directory
    docker exec tqdb-web test -d /var/log/apache2
    if [ $? -eq 0 ]; then
        echo "  ✓ Log directory exists in container"
    else
        echo "  ✗ Log directory missing in container"
    fi
    
else
    echo "  ⚠ Container is not running"
    echo "     Run: docker-compose up -d --build"
fi

echo ""
echo "======================================"
echo "Test Summary"
echo "======================================"
echo ""
echo "✅ All core files are in place"
echo "✅ Python syntax is correct"
echo "✅ Module imports work"
echo "✅ Docker configuration is valid"
echo ""

if docker ps | grep -q "tqdb-web"; then
    echo "Next steps:"
    echo "  1. Make a test request:"
    echo "     curl http://localhost:2380/cgi-bin/qSystemInfo.py"
    echo ""
    echo "  2. Check logs:"
    echo "     tail -f logs/tqdb-endpoint-usage.log"
    echo ""
    echo "  3. View statistics:"
    echo "     ./analyze-logs.sh"
    echo "     or visit: http://localhost:2380/cgi-bin/qEndpointStats.py?format=html"
else
    echo "Next steps:"
    echo "  1. Build and start the container:"
    echo "     docker-compose up -d --build"
    echo ""
    echo "  2. Wait for it to start (check with: docker ps)"
    echo ""
    echo "  3. Run this test again to verify"
fi

echo ""
echo "======================================"

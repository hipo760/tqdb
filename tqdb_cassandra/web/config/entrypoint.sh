#!/bin/bash
# TQDB Web Container Entrypoint Script
# This script runs when the container starts

set -e

echo "=========================================="
echo "TQDB Web Container Starting..."
echo "=========================================="

# Display configuration
echo "Configuration:"
echo "  CASSANDRA_HOST: ${CASSANDRA_HOST}"
echo "  CASSANDRA_PORT: ${CASSANDRA_PORT}"
echo "  CASSANDRA_KEYSPACE: ${CASSANDRA_KEYSPACE}"
echo "  TOOLS_DIR: ${TOOLS_DIR}"
echo "  TZ: ${TZ}"
echo ""

# Wait for Cassandra to be ready (optional, with timeout)
if [ "${WAIT_FOR_CASSANDRA:-true}" = "true" ]; then
    echo "Waiting for Cassandra at ${CASSANDRA_HOST}:${CASSANDRA_PORT}..."
    TIMEOUT=60
    COUNTER=0
    
    until python3 -c "from cassandra.cluster import Cluster; Cluster(['${CASSANDRA_HOST}'], port=${CASSANDRA_PORT}).connect()" 2>/dev/null; do
        COUNTER=$((COUNTER + 1))
        if [ $COUNTER -ge $TIMEOUT ]; then
            echo "WARNING: Cassandra not available after ${TIMEOUT} seconds. Starting anyway..."
            break
        fi
        echo "  Waiting... (${COUNTER}/${TIMEOUT})"
        sleep 1
    done
    
    if [ $COUNTER -lt $TIMEOUT ]; then
        echo "✓ Cassandra is ready!"
    fi
fi

# Test Python binary availability
echo ""
echo "Checking Python binaries..."
if [ -f "${TOOLS_DIR}/qsym.py" ]; then
    echo "  ✓ qsym.py found"
else
    echo "  ⚠ qsym.py not found (will be created later)"
fi

# Check CGI scripts
echo ""
echo "Checking CGI scripts..."
CGI_COUNT=$(find /var/www/cgi-bin -name "*.py" 2>/dev/null | wc -l)
echo "  Found ${CGI_COUNT} CGI scripts"

# Check static files
echo ""
echo "Checking static files..."
if [ -f "/var/www/html/index.html" ]; then
    echo "  ✓ index.html found"
else
    echo "  ⚠ index.html not found (will be added later)"
fi

# Create temp directory for queries
mkdir -p /tmp/tqdb
chown www-data:www-data /tmp/tqdb

echo ""
echo "=========================================="
echo "Starting Apache HTTP Server..."
echo "=========================================="

# Execute the command passed to the entrypoint
exec "$@"

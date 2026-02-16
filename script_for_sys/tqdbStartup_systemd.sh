#!/bin/bash
# TQDB Startup Script - Systemd Compatible Version
# This script is designed to work with systemd services

# Enable strict error handling
set -euo pipefail

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Function to wait for service to be ready
wait_for_service() {
    local service=$1
    local port=$2
    local timeout=${3:-30}
    local count=0
    
    log "Waiting for $service to be ready on port $port..."
    while ! nc -z localhost $port 2>/dev/null; do
        if [ $count -ge $timeout ]; then
            log "ERROR: $service failed to start within $timeout seconds"
            return 1
        fi
        sleep 1
        ((count++))
    done
    log "$service is ready"
}

# Load environment variables
if [ -f /etc/profile.d/profile_tqdb.sh ]; then
    source /etc/profile.d/profile_tqdb.sh
    log "Environment variables loaded"
else
    log "ERROR: /etc/profile.d/profile_tqdb.sh not found"
    exit 1
fi

# Validate required environment variables
for var in CASS_IP CASS_PORT D2TQ_IP D2TQ_PORT TQDB_DIR; do
    if [ -z "${!var:-}" ]; then
        log "ERROR: Required environment variable $var is not set"
        exit 1
    fi
done

log "Starting TQDB services..."

# Create necessary directories
mkdir -p /tmp/TQAlert
chmod 777 /tmp/TQAlert
log "Created TQAlert directory"

# Create info files for services
echo "$CASS_IP:$CASS_PORT" > /tmp/cass.info
echo "$D2TQ_IP:$D2TQ_PORT" > /tmp/d2tq.info
log "Created service info files"

# Check if Cassandra is running
if ! wait_for_service "Cassandra" "$CASS_PORT" 60; then
    log "ERROR: Cassandra is not available"
    exit 1
fi

# Start demo data server
log "Starting demo data server..."
cd "$TQDB_DIR/script_for_sys"
if [ -x "./demo_d2tq_server.sh" ]; then
    nohup ./demo_d2tq_server.sh > /tmp/demo_d2tq_server.log 2>&1 &
    echo $! > /tmp/demo_d2tq_server.pid
    log "Demo data server started (PID: $!)"
else
    log "WARNING: demo_d2tq_server.sh not found or not executable"
fi

# Start TQAlert service
log "Starting TQAlert service..."
cd "$TQDB_DIR/tools"
if [ -f "TQAlert.py" ]; then
    nohup python3 -u TQAlert.py > /tmp/TQAlert.py.log 2>&1 &
    echo $! > /tmp/TQAlert.pid
    log "TQAlert service started (PID: $!)"
else
    log "WARNING: TQAlert.py not found"
fi

# Wait for demo server to be ready
if [ -f /tmp/demo_d2tq_server.pid ]; then
    wait_for_service "Demo server" "4568" 30 || log "WARNING: Demo server may not be ready"
fi

# Start auto insertion to Cassandra
log "Starting auto insertion to Cassandra..."
if [ -x "./autoIns2Cass.sh" ]; then
    nohup ./autoIns2Cass.sh > /tmp/autoIns2Cass.log 2>&1 &
    echo $! > /tmp/autoIns2Cass.pid
    log "Auto insertion service started (PID: $!)"
else
    log "WARNING: autoIns2Cass.sh not found or not executable"
fi

# Start watchdog for auto insertion
log "Starting watchdog for auto insertion..."
if [ -x "./watchdogAutoIns2Cass.sh" ]; then
    nohup ./watchdogAutoIns2Cass.sh > /tmp/watchdogAutoIns2Cass.log 2>&1 &
    echo $! > /tmp/watchdogAutoIns2Cass.pid
    log "Watchdog service started (PID: $!)"
else
    log "WARNING: watchdogAutoIns2Cass.sh not found or not executable"
fi

# Start Jupyter notebook (optional - only if running as tqdb user)
if [ "$USER" = "tqdb" ] || [ "$EUID" -eq 0 ]; then
    log "Starting Jupyter notebook..."
    if command -v jupyter >/dev/null 2>&1; then
        cd /home/tqdb
        # Start Jupyter as tqdb user if running as root
        if [ "$EUID" -eq 0 ]; then
            nohup su - tqdb -c "cd /home/tqdb && jupyter notebook --no-browser --ip=0.0.0.0 --port=8888" > /tmp/jupyter.log 2>&1 &
        else
            nohup jupyter notebook --no-browser --ip=0.0.0.0 --port=8888 > /tmp/jupyter.log 2>&1 &
        fi
        echo $! > /tmp/jupyter.pid
        log "Jupyter notebook started (PID: $!)"
    else
        log "WARNING: Jupyter not found in PATH"
    fi
fi

# Create status file
cat > /tmp/tqdb_status.info << EOF
TQDB_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
CASSANDRA_ENDPOINT=$CASS_IP:$CASS_PORT
DATA_SOURCE_ENDPOINT=$D2TQ_IP:$D2TQ_PORT
TQDB_DIRECTORY=$TQDB_DIR
EOF

log "TQDB startup completed successfully"

# Keep the script running for systemd (Type=forking)
exit 0

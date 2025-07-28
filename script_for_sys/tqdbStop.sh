#!/bin/bash
# TQDB Stop Script - Systemd Compatible Version
# This script gracefully stops all TQDB services

# Enable strict error handling
set -euo pipefail

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Function to safely kill a process
safe_kill() {
    local pidfile=$1
    local service_name=$2
    local timeout=${3:-10}
    
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "Stopping $service_name (PID: $pid)..."
            kill -TERM "$pid" 2>/dev/null || true
            
            # Wait for graceful shutdown
            local count=0
            while kill -0 "$pid" 2>/dev/null && [ $count -lt $timeout ]; do
                sleep 1
                ((count++))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                log "Force killing $service_name (PID: $pid)..."
                kill -KILL "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pidfile"
        log "$service_name stopped"
    else
        log "No PID file found for $service_name"
    fi
}

# Function to kill processes by pattern
kill_by_pattern() {
    local pattern=$1
    local service_name=$2
    
    local pids=$(pgrep -f "$pattern" 2>/dev/null || echo "")
    if [ -n "$pids" ]; then
        log "Stopping $service_name processes..."
        echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
        sleep 2
        # Force kill if still running
        local remaining_pids=$(pgrep -f "$pattern" 2>/dev/null || echo "")
        if [ -n "$remaining_pids" ]; then
            echo "$remaining_pids" | xargs -r kill -KILL 2>/dev/null || true
        fi
        log "$service_name processes stopped"
    fi
}

log "Stopping TQDB services..."

# Stop services using PID files
safe_kill "/tmp/jupyter.pid" "Jupyter notebook"
safe_kill "/tmp/watchdogAutoIns2Cass.pid" "Watchdog service"
safe_kill "/tmp/autoIns2Cass.pid" "Auto insertion service"
safe_kill "/tmp/TQAlert.pid" "TQAlert service"
safe_kill "/tmp/demo_d2tq_server.pid" "Demo data server"

# Stop any remaining processes by pattern (fallback)
kill_by_pattern "jupyter notebook" "Jupyter"
kill_by_pattern "watchdogAutoIns2Cass" "Watchdog"
kill_by_pattern "autoIns2Cass" "Auto insertion"
kill_by_pattern "TQAlert.py" "TQAlert"
kill_by_pattern "demo_d2tq_server" "Demo server"

# Clean up temporary files
log "Cleaning up temporary files..."
rm -f /tmp/cass.info /tmp/d2tq.info /tmp/tqdb_status.info
rm -f /tmp/*.pid

log "TQDB services stopped successfully"

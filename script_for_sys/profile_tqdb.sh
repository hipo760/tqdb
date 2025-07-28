#!/bin/bash
# TQDB Environment Configuration for Rocky Linux 9
# This file sets up environment variables for TQDB services

# Cassandra Configuration
export CASS_IP=${CASS_IP:-127.0.0.1}
export CASS_PORT=${CASS_PORT:-9042}

# Data Source Configuration
export D2TQ_IP=${D2TQ_IP:-192.168.56.1}
export D2TQ_PORT=${D2TQ_PORT:-14568}

# TQDB Installation Directory
export TQDB_DIR=${TQDB_DIR:-/home/tqdb/codes/tqdb}

# Additional TQDB Configuration
export TQDB_LOG_LEVEL=${TQDB_LOG_LEVEL:-INFO}
export TQDB_MAX_MEMORY=${TQDB_MAX_MEMORY:-2G}

# Python Configuration (Rocky 9 uses Python 3 by default)
export PYTHON_BIN=${PYTHON_BIN:-python3}

# Add TQDB tools to PATH
if [ -d "$TQDB_DIR/tools" ]; then
    export PATH="$TQDB_DIR/tools:$PATH"
fi

# Jupyter Configuration (if used)
export JUPYTER_CONFIG_DIR=${JUPYTER_CONFIG_DIR:-/home/tqdb/.jupyter}
export JUPYTER_DATA_DIR=${JUPYTER_DATA_DIR:-/home/tqdb/.local/share/jupyter}

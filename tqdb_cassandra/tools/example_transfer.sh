#!/bin/bash
# Example usage of transfer_minbar.py
# Edit the variables below and run this script

# Configuration - EDIT THESE VALUES
SOURCE_HOST="192.168.1.100"  # Replace with your source Cassandra IP
TARGET_HOST="localhost"       # Target is usually localhost for container
SYMBOLS="AAPL,GOOGL,MSFT"    # Symbols to transfer, or use --all-symbols flag below

# Set to "true" to transfer all symbols, "false" to use SYMBOLS list above
TRANSFER_ALL_SYMBOLS="false"

# Optional authentication (uncomment and set if needed)
# SOURCE_USER="cassandra"
# SOURCE_PASSWORD="cassandra"
# TARGET_USER="cassandra"
# TARGET_PASSWORD="cassandra"

# Performance tuning
BATCH_SIZE="1000"  # Increase for better performance (e.g., 5000)

# ============================================================================
# No need to edit below this line
# ============================================================================

echo "TQDB Minbar Data Transfer"
echo "=========================="
echo "Source: $SOURCE_HOST"
echo "Target: $TARGET_HOST"
if [ "$TRANSFER_ALL_SYMBOLS" = "true" ]; then
    echo "Mode: Transfer ALL symbols"
else
    echo "Symbols: $SYMBOLS"
fi
echo "Batch size: $BATCH_SIZE"
echo ""

# Build command
CMD="uv run transfer_minbar.py --source-host $SOURCE_HOST --target-host $TARGET_HOST"

# Add symbol selection
if [ "$TRANSFER_ALL_SYMBOLS" = "true" ]; then
    CMD="$CMD --all-symbols"
else
    CMD="$CMD --symbols $SYMBOLS"
fi

# Add batch size
CMD="$CMD --batch-size $BATCH_SIZE"

# Add authentication if set
if [ ! -z "$SOURCE_USER" ]; then
    CMD="$CMD --source-user $SOURCE_USER --source-password $SOURCE_PASSWORD"
fi

if [ ! -z "$TARGET_USER" ]; then
    CMD="$CMD --target-user $TARGET_USER --target-password $TARGET_PASSWORD"
fi

echo "Running: $CMD"
echo ""

# Execute
eval $CMD

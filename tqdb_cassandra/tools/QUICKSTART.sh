#!/bin/bash
# Quick Start Guide for transfer_minbar.py

cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════╗
║                  TQDB MINBAR TRANSFER - QUICK START                      ║
╚══════════════════════════════════════════════════════════════════════════╝

📋 SETUP (First time only)
────────────────────────────────────────────────────────────────────────────
  cd /home/ubuntu/services/tqdb/tqdb_cassandra/tools
  uv sync

📦 USAGE EXAMPLES
────────────────────────────────────────────────────────────────────────────
1. Transfer specific symbols:
   
   uv run transfer_minbar.py \
     --source-host 192.168.1.100 \
     --target-host localhost \
     --symbols AAPL,GOOGL,MSFT

2. Transfer all symbols:
   
   uv run transfer_minbar.py \
     --source-host 192.168.1.100 \
     --target-host localhost \
     --all-symbols

3. Use the example script (edit variables first):
   
   nano example_transfer.sh
   ./example_transfer.sh

⚡ PERFORMANCE TIPS
────────────────────────────────────────────────────────────────────────────
  • Increase batch size for faster transfers:
    --batch-size 5000
  
  • Default batch size is 1000 (good for most cases)
  
  • Larger batches = faster, but use more memory

🔐 WITH AUTHENTICATION
────────────────────────────────────────────────────────────────────────────
  Add these flags if Cassandra requires authentication:
  
  --source-user cassandra --source-password yourpass
  --target-user cassandra --target-password yourpass

📊 WHAT YOU'LL SEE
────────────────────────────────────────────────────────────────────────────
  ✓ Connection status
  ✓ Progress bar for each symbol
  ✓ Transfer rate (rows/sec)
  ✓ Summary statistics

🛠️ NEED HELP?
────────────────────────────────────────────────────────────────────────────
  uv run transfer_minbar.py --help
  cat README.md

EOF

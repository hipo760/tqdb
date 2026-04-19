#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

uv run rename_symbols.py \
  --host localhost \
  --map TXON:TXON_D \
  --map TXDT:TXDT_D

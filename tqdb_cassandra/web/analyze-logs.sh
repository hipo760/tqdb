#!/bin/bash
# TQDB Endpoint Usage Log Analyzer
# Helper script to analyze endpoint usage logs

set -e

LOG_DIR="./logs"
LOG_FILE="${LOG_DIR}/tqdb-endpoint-usage.log"
JSON_LOG_FILE="${LOG_DIR}/tqdb-endpoint-usage.jsonl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TQDB Endpoint Usage Log Analyzer${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if logs exist
if [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}Error: Log file not found: $LOG_FILE${NC}"
    echo "Have you made any requests yet?"
    exit 1
fi

# Get total requests
TOTAL_REQUESTS=$(wc -l < "$LOG_FILE")
echo -e "${GREEN}Total Requests:${NC} $TOTAL_REQUESTS"
echo ""

# Get date range
if [ $TOTAL_REQUESTS -gt 0 ]; then
    FIRST_DATE=$(head -1 "$LOG_FILE" | cut -d'|' -f1 | xargs)
    LAST_DATE=$(tail -1 "$LOG_FILE" | cut -d'|' -f1 | xargs)
    echo -e "${GREEN}Date Range:${NC}"
    echo "  First request: $FIRST_DATE"
    echo "  Last request:  $LAST_DATE"
    echo ""
fi

# Top 10 endpoints
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Top 10 Most Used Endpoints:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
grep -oP '/cgi-bin/[^ |]+' "$LOG_FILE" | sort | uniq -c | sort -rn | head -10 | while read count endpoint; do
    printf "  %5d  %s\n" "$count" "$endpoint"
done
echo ""

# Unique IP addresses
UNIQUE_IPS=$(grep -oP 'ip=[^ |]+' "$LOG_FILE" | sort -u | wc -l)
echo -e "${GREEN}Unique IP Addresses:${NC} $UNIQUE_IPS"
echo ""

# Top 5 IP addresses
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Top 5 IP Addresses:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
grep -oP 'ip=[^ |]+' "$LOG_FILE" | sort | uniq -c | sort -rn | head -5 | while read count ip; do
    printf "  %5d  %s\n" "$count" "${ip#ip=}"
done
echo ""

# Requests by date
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Requests by Date:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cut -d'T' -f1 "$LOG_FILE" | sort | uniq -c | while read count date; do
    printf "  %5d  %s\n" "$count" "$date"
done
echo ""

# Find unused endpoints
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Checking for Unused CGI Scripts:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

UNUSED_COUNT=0
USED_COUNT=0

if [ -d "./cgi-bin" ]; then
    for script in ./cgi-bin/*.py; do
        if [ -f "$script" ]; then
            script_name=$(basename "$script")
            
            # Skip our logging scripts
            if [[ "$script_name" == "endpoint_logger.py" ]] || \
               [[ "$script_name" == "qEndpointStats.py" ]] || \
               [[ "$script_name" == "INTEGRATION_EXAMPLE.py" ]]; then
                continue
            fi
            
            if grep -q "/cgi-bin/$script_name" "$LOG_FILE" 2>/dev/null; then
                count=$(grep -c "/cgi-bin/$script_name" "$LOG_FILE")
                printf "  ${GREEN}✓${NC} %-30s (%d requests)\n" "$script_name" "$count"
                ((USED_COUNT++))
            else
                printf "  ${RED}✗${NC} %-30s ${RED}(UNUSED)${NC}\n" "$script_name"
                ((UNUSED_COUNT++))
            fi
        fi
    done
    
    echo ""
    echo -e "${GREEN}Used Scripts:${NC} $USED_COUNT"
    echo -e "${RED}Unused Scripts:${NC} $UNUSED_COUNT"
    echo ""
    
    if [ $UNUSED_COUNT -gt 0 ]; then
        echo -e "${YELLOW}Note:${NC} Unused scripts may be legacy code or recently added."
        echo "      Verify with stakeholders before removing."
    fi
else
    echo "  ${YELLOW}Warning:${NC} cgi-bin directory not found"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Analysis Complete!${NC}"
echo ""
echo "For detailed statistics, visit:"
echo "  http://localhost:2380/cgi-bin/qEndpointStats.py?format=html"
echo ""
echo "To export JSON data:"
echo "  curl 'http://localhost:2380/cgi-bin/qEndpointStats.py?format=json&days=30'"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

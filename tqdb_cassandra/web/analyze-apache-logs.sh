#!/bin/bash
# Analyze Apache access logs to find ALL endpoint usage
# This works for Python CGI, HTML pages, and everything else

set -e

LOG_FILE="./logs/tqdb-access.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Apache Access Log Analyzer (ALL Endpoints)${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}Error: Apache access log not found: $LOG_FILE${NC}"
    exit 1
fi

TOTAL_REQUESTS=$(wc -l < "$LOG_FILE")
echo -e "${GREEN}Total Requests:${NC} $TOTAL_REQUESTS"
echo ""

# Extract all unique endpoints (both CGI and static files)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Top 20 Endpoints (ALL types):${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Extract method and path from access log, count occurrences
awk '{print $6, $7}' "$LOG_FILE" | sed 's/"//g' | awk '{
    # Remove query string for grouping
    split($2, parts, "?")
    path = parts[1]
    if (path != "") {
        print $1, path
    }
}' | sort | uniq -c | sort -rn | head -20 | while read count method path; do
    # Color code by type
    if [[ "$path" == "/cgi-bin/"* ]]; then
        color="${GREEN}"
        type="[CGI]"
    elif [[ "$path" == *".html" ]]; then
        color="${YELLOW}"
        type="[HTML]"
    elif [[ "$path" == "/" ]]; then
        color="${BLUE}"
        type="[ROOT]"
    else
        color="${NC}"
        type="[STATIC]"
    fi
    
    printf "  ${color}%5d${NC}  %-6s %-50s %s\n" "$count" "$method" "$path" "$type"
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}CGI Scripts Only:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

awk '{print $7}' "$LOG_FILE" | grep "^/cgi-bin/" | sed 's/?.*$//' | sort | uniq -c | sort -rn | while read count path; do
    script=$(basename "$path")
    printf "  %5d  %-40s\n" "$count" "$script"
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}HTML Pages Only:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

awk '{print $7}' "$LOG_FILE" | grep "\.html" | sed 's/?.*$//' | sort | uniq -c | sort -rn | while read count path; do
    page=$(basename "$path")
    printf "  %5d  %-40s\n" "$count" "$page"
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Checking for Unused Files:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo ""
echo -e "${GREEN}Python CGI Scripts:${NC}"
UNUSED_CGI=0
USED_CGI=0

if [ -d "./cgi-bin" ]; then
    for script in ./cgi-bin/*.py; do
        if [ -f "$script" ]; then
            script_name=$(basename "$script")
            
            # Skip utility scripts
            if [[ "$script_name" == "endpoint_logger.py" ]] || \
               [[ "$script_name" == "webcommon.py" ]] || \
               [[ "$script_name" == "test_logging.py" ]] || \
               [[ "$script_name" == "INTEGRATION_EXAMPLE.py" ]]; then
                continue
            fi
            
            if grep -q "/cgi-bin/$script_name" "$LOG_FILE" 2>/dev/null; then
                count=$(grep -c "/cgi-bin/$script_name" "$LOG_FILE")
                printf "  ${GREEN}✓${NC} %-40s (%d requests)\n" "$script_name" "$count"
                ((USED_CGI++))
            else
                printf "  ${RED}✗${NC} %-40s ${RED}(UNUSED)${NC}\n" "$script_name"
                ((UNUSED_CGI++))
            fi
        fi
    done
fi

echo ""
echo -e "${GREEN}HTML Pages:${NC}"
UNUSED_HTML=0
USED_HTML=0

if [ -d "./html" ]; then
    for page in ./html/*.html; do
        if [ -f "$page" ]; then
            page_name=$(basename "$page")
            
            if grep -q "/$page_name" "$LOG_FILE" 2>/dev/null; then
                count=$(grep -c "/$page_name" "$LOG_FILE")
                printf "  ${GREEN}✓${NC} %-40s (%d requests)\n" "$page_name" "$count"
                ((USED_HTML++))
            else
                printf "  ${RED}✗${NC} %-40s ${RED}(UNUSED)${NC}\n" "$page_name"
                ((UNUSED_HTML++))
            fi
        fi
    done
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Summary:${NC}"
echo "  Used CGI scripts:    $USED_CGI"
echo "  Unused CGI scripts:  $UNUSED_CGI"
echo "  Used HTML pages:     $USED_HTML"
echo "  Unused HTML pages:   $UNUSED_HTML"
echo ""
echo "Note: This analysis uses Apache access logs which track ALL requests"
echo "      (CGI scripts, HTML pages, CSS, JS, images, etc.)"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

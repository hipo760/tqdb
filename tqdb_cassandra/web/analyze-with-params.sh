#!/bin/bash
# Analyze Apache access logs with IP filtering and parameter display
# Shows what parameters are being used with each endpoint

set -e

LOG_FILE="./logs/tqdb-access.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Parse command line arguments
FILTER_IP=""
EXCLUDE_IP=""
SHOW_IPS=false
SHOW_PARAMS=false

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -i, --ip IP          Filter requests from specific IP address"
    echo "  -e, --exclude IP     Exclude requests from specific IP address"
    echo "  -p, --params         Show query parameters for each endpoint"
    echo "  -l, --list-ips       List all unique IP addresses in logs"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                              # Show all requests"
    echo "  $0 --ip 13.113.222.129         # Show only requests from specific IP"
    echo "  $0 --ip 13.113.222.129 --params # Show requests with parameters"
    echo "  $0 --exclude 127.0.0.1         # Exclude localhost requests"
    echo "  $0 --list-ips                  # List all unique IPs"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--ip)
            FILTER_IP="$2"
            shift 2
            ;;
        -e|--exclude)
            EXCLUDE_IP="$2"
            shift 2
            ;;
        -p|--params)
            SHOW_PARAMS=true
            shift
            ;;
        -l|--list-ips)
            SHOW_IPS=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}Error: Apache access log not found: $LOG_FILE${NC}"
    exit 1
fi

# Function to filter logs by IP
filter_logs() {
    if [ -n "$FILTER_IP" ]; then
        grep "^$FILTER_IP " "$LOG_FILE"
    elif [ -n "$EXCLUDE_IP" ]; then
        grep -v "^$EXCLUDE_IP " "$LOG_FILE"
    else
        cat "$LOG_FILE"
    fi
}

# Function to URL decode
urldecode() {
    local url_encoded="${1//+/ }"
    printf '%b' "${url_encoded//%/\\x}"
}

# List unique IPs if requested
if [ "$SHOW_IPS" = true ]; then
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Unique IP Addresses in Logs${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    awk '{print $1}' "$LOG_FILE" | sort | uniq -c | sort -rn | while read count ip; do
        if [[ "$ip" == "127.0.0.1" ]] || [[ "$ip" == "172."* ]]; then
            color="${YELLOW}"
            type="[LOCAL]"
        else
            color="${GREEN}"
            type="[EXTERNAL]"
        fi
        printf "  ${color}%6d${NC}  %-20s %s\n" "$count" "$ip" "$type"
    done
    
    echo ""
    echo -e "${CYAN}Tip: Use --ip <IP> to filter by specific IP${NC}"
    echo -e "${CYAN}     Use --exclude <IP> to exclude an IP${NC}"
    echo -e "${CYAN}     Use --params to see query parameters${NC}"
    exit 0
fi

# Show filter info
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Apache Access Log Analyzer${NC}"
if [ -n "$FILTER_IP" ]; then
    echo -e "${CYAN}  Filtering by IP: $FILTER_IP${NC}"
elif [ -n "$EXCLUDE_IP" ]; then
    echo -e "${CYAN}  Excluding IP: $EXCLUDE_IP${NC}"
else
    echo -e "${CYAN}  Showing all requests${NC}"
fi
if [ "$SHOW_PARAMS" = true ]; then
    echo -e "${CYAN}  Parameter display: ENABLED${NC}"
fi
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Get filtered logs
FILTERED_LOGS=$(filter_logs)
if [ -z "$FILTERED_LOGS" ]; then
    echo -e "${RED}No requests found matching filter${NC}"
    exit 1
fi

TOTAL_REQUESTS=$(echo "$FILTERED_LOGS" | wc -l)
echo -e "${GREEN}Total Requests:${NC} $TOTAL_REQUESTS"
echo ""

# Get unique IPs
UNIQUE_IPS=$(echo "$FILTERED_LOGS" | awk '{print $1}' | sort -u | wc -l)
echo -e "${GREEN}Unique IP Addresses:${NC} $UNIQUE_IPS"
echo ""

# Show top endpoints
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Top 20 Endpoints:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "$FILTERED_LOGS" | awk '{print $6, $7}' | sed 's/"//g' | awk '{
    split($2, parts, "?")
    path = parts[1]
    if (path != "") {
        print $1, path
    }
}' | sort | uniq -c | sort -rn | head -20 | while read count method path; do
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

# Show detailed parameter analysis
if [ "$SHOW_PARAMS" = true ]; then
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}CGI Scripts with Parameters:${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Get unique CGI scripts
    CGI_SCRIPTS=$(echo "$FILTERED_LOGS" | awk '{print $7}' | grep "^/cgi-bin/" | sed 's/?.*$//' | sort -u)
    
    if [ -n "$CGI_SCRIPTS" ]; then
        while IFS= read -r cgi_path; do
            script_name=$(basename "$cgi_path")
            count=$(echo "$FILTERED_LOGS" | grep -c "$cgi_path")
            
            echo -e "${GREEN}$script_name${NC} ${MAGENTA}($count requests)${NC}"
            
            # Get unique query strings
            echo "$FILTERED_LOGS" | grep "$cgi_path" | awk '{print $7}' | grep "?" | while read full_url; do
                query_string="${full_url#*\?}"
                query_string="${query_string%% *}"
                
                # Try to decode
                decoded=$(urldecode "$query_string" 2>/dev/null || echo "$query_string")
                echo -e "    ${CYAN}?${decoded}${NC}"
            done | sort -u | head -10
            
            echo ""
        done <<< "$CGI_SCRIPTS"
    else
        echo "  No CGI scripts found"
    fi
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}CGI Scripts Summary:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

CGI_STATS=$(echo "$FILTERED_LOGS" | awk '{print $7}' | grep "^/cgi-bin/" | sed 's/?.*$//' | sort | uniq -c | sort -rn)
if [ -n "$CGI_STATS" ]; then
    echo "$CGI_STATS" | while read count path; do
        script=$(basename "$path")
        printf "  %5d  %-40s\n" "$count" "$script"
    done
else
    echo "  No CGI requests found"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}HTML Pages:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

HTML_STATS=$(echo "$FILTERED_LOGS" | awk '{print $7}' | grep "\.html" | sed 's/?.*$//' | sort | uniq -c | sort -rn)
if [ -n "$HTML_STATS" ]; then
    echo "$HTML_STATS" | while read count path; do
        page=$(basename "$path")
        printf "  %5d  %-40s\n" "$count" "$page"
    done
else
    echo "  No HTML pages found"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Unused Files:${NC}"
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
               [[ "$script_name" == "qEndpointStats.py" ]] || \
               [[ "$script_name" == "INTEGRATION_EXAMPLE.py" ]]; then
                continue
            fi
            
            if echo "$FILTERED_LOGS" | grep -q "/cgi-bin/$script_name"; then
                count=$(echo "$FILTERED_LOGS" | grep -c "/cgi-bin/$script_name")
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
            
            if echo "$FILTERED_LOGS" | grep -q "/$page_name"; then
                count=$(echo "$FILTERED_LOGS" | grep -c "/$page_name")
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
if [ "$SHOW_PARAMS" = false ]; then
    echo -e "${CYAN}Tip: Use --params to see query parameters for each endpoint${NC}"
fi
if [ -z "$FILTER_IP" ] && [ -z "$EXCLUDE_IP" ]; then
    echo -e "${CYAN}     Use --list-ips to see all unique IP addresses${NC}"
    echo -e "${CYAN}     Use --ip <IP> to filter by specific application IP${NC}"
fi
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

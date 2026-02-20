#!/bin/bash
# Debug helper script for TQDB web container

echo "=== TQDB Web Container Debug Helper ==="
echo ""

case "$1" in
  error)
    echo "Showing Apache error log (last 50 lines):"
    docker exec tqdb-web tail -50 /var/log/apache2/error.log
    ;;
  
  error-live)
    echo "Following Apache error log (Ctrl+C to exit):"
    docker exec tqdb-web tail -f /var/log/apache2/error.log
    ;;
  
  access)
    echo "Showing Apache access log (last 50 lines):"
    docker exec tqdb-web tail -50 /var/log/apache2/access.log
    ;;
  
  access-live)
    echo "Following Apache access log (Ctrl+C to exit):"
    docker exec tqdb-web tail -f /var/log/apache2/access.log
    ;;
  
  container)
    echo "Showing container logs:"
    docker logs --tail 100 tqdb-web
    ;;
  
  container-live)
    echo "Following container logs (Ctrl+C to exit):"
    docker logs -f tqdb-web
    ;;
  
  traceback)
    echo "Searching for Python tracebacks in error log:"
    docker exec tqdb-web grep -B 2 -A 10 "Traceback" /var/log/apache2/error.log | tail -50
    ;;
  
  shell)
    echo "Opening bash shell in container..."
    docker exec -it tqdb-web bash
    ;;
  
  test-cgi)
    if [ -z "$2" ]; then
      echo "Usage: $0 test-cgi <script-name>"
      echo "Example: $0 test-cgi qsyminfo.py"
      exit 1
    fi
    echo "Testing CGI script: $2"
    docker exec tqdb-web python3 /var/www/cgi-bin/$2
    ;;
  
  test-query)
    if [ -z "$2" ] || [ -z "$3" ]; then
      echo "Usage: $0 test-query <script-name> <query-string>"
      echo "Example: $0 test-query qsyminfo.py 'symbol=ALL'"
      exit 1
    fi
    echo "Testing CGI script: $2 with query: $3"
    docker exec -e QUERY_STRING="$3" tqdb-web python3 /var/www/cgi-bin/$2
    ;;
  
  cassandra)
    echo "Testing Cassandra connectivity from web container:"
    docker exec tqdb-web python3 -c "
from cassandra.cluster import Cluster
import os
host = os.environ.get('CASSANDRA_HOST', 'cassandra-node')
port = int(os.environ.get('CASSANDRA_PORT', '9042'))
print(f'Connecting to {host}:{port}...')
cluster = Cluster([host], port=port)
session = cluster.connect()
print('✓ Connected successfully')
rows = session.execute('SELECT cluster_name, release_version FROM system.local')
for row in rows:
    print(f'Cluster: {row.cluster_name}, Version: {row.release_version}')
cluster.shutdown()
"
    ;;
  
  env)
    echo "Showing container environment variables:"
    docker exec tqdb-web env | grep -E "CASSANDRA|TOOLS_DIR|TZ"
    ;;
  
  clear)
    echo "Clearing all logs..."
    docker exec tqdb-web bash -c "truncate -s 0 /var/log/apache2/error.log"
    docker exec tqdb-web bash -c "truncate -s 0 /var/log/apache2/access.log"
    echo "✓ Logs cleared"
    ;;
  
  restart)
    echo "Restarting web container..."
    docker restart tqdb-web
    echo "✓ Container restarted"
    ;;
  
  status)
    echo "Container status:"
    docker ps --filter name=tqdb-web
    echo ""
    echo "Recent errors (last 10):"
    docker exec tqdb-web tail -10 /var/log/apache2/error.log
    ;;
  
  *)
    echo "Usage: $0 <command>"
    echo ""
    echo "Available commands:"
    echo "  error          - Show last 50 lines of Apache error log"
    echo "  error-live     - Follow Apache error log in real-time"
    echo "  access         - Show last 50 lines of Apache access log"
    echo "  access-live    - Follow Apache access log in real-time"
    echo "  container      - Show container logs"
    echo "  container-live - Follow container logs in real-time"
    echo "  traceback      - Search for Python tracebacks"
    echo "  shell          - Open bash shell in container"
    echo "  test-cgi       - Test a CGI script directly"
    echo "  test-query     - Test a CGI script with query string"
    echo "  cassandra      - Test Cassandra connectivity"
    echo "  env            - Show container environment variables"
    echo "  clear          - Clear all Apache logs"
    echo "  restart        - Restart the web container"
    echo "  status         - Show container status and recent errors"
    echo ""
    echo "Examples:"
    echo "  $0 error-live                    # Watch errors in real-time"
    echo "  $0 test-cgi qsyminfo.py          # Test a CGI script"
    echo "  $0 test-query q1min.py 'symbol=TEST.BTC&BEG=2026-2-18&END=2026-2-19'"
    echo "  $0 traceback                     # Find Python errors"
    exit 1
    ;;
esac

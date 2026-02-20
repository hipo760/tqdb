#!/bin/bash

# TQDB Cluster Deployment Helper Script
# This script helps configure and deploy the two-node Cassandra cluster

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_info "Prerequisites OK"

# Main menu
echo ""
echo "===================================="
echo "  TQDB Cluster Deployment Helper"
echo "===================================="
echo ""
echo "1. Configure Main Node"
echo "2. Configure CME Node"
echo "3. Deploy Main Node"
echo "4. Deploy CME Node"
echo "5. Check Cluster Status"
echo "6. Stop Main Node"
echo "7. Stop CME Node"
echo "8. View Main Node Logs"
echo "9. View CME Node Logs"
echo "0. Exit"
echo ""
read -p "Select option: " option

case $option in
    1)
        print_info "Configuring Main Node..."
        read -p "Enter Main Server IP address: " main_ip
        read -p "Enter Main Server Heap Size (default: 4G): " heap_size
        heap_size=${heap_size:-4G}
        
        # Update docker-compose.main.yml
        if [ -f "docker-compose.main.yml" ]; then
            cp docker-compose.main.yml docker-compose.main.yml.bak
            sed -i "s/cassandra-main/$main_ip/g" docker-compose.main.yml
            sed -i "s/CASSANDRA_BROADCAST_ADDRESS=.*$/CASSANDRA_BROADCAST_ADDRESS=$main_ip/g" docker-compose.main.yml
            sed -i "s/MAX_HEAP_SIZE=.*$/MAX_HEAP_SIZE=$heap_size/g" docker-compose.main.yml
            print_info "Main node configuration updated successfully"
        else
            print_error "docker-compose.main.yml not found"
            exit 1
        fi
        ;;
        
    2)
        print_info "Configuring CME Node..."
        read -p "Enter Main Server IP address (seed): " main_ip
        read -p "Enter CME Server IP address: " cme_ip
        read -p "Enter CME Server Heap Size (default: 2G): " heap_size
        heap_size=${heap_size:-2G}
        
        # Update docker-compose.cme.yml
        if [ -f "docker-compose.cme.yml" ]; then
            cp docker-compose.cme.yml docker-compose.cme.yml.bak
            sed -i "s/<MAIN_SERVER_IP>/$main_ip/g" docker-compose.cme.yml
            sed -i "s/CASSANDRA_BROADCAST_ADDRESS=.*$/CASSANDRA_BROADCAST_ADDRESS=$cme_ip/g" docker-compose.cme.yml
            sed -i "s/MAX_HEAP_SIZE=.*$/MAX_HEAP_SIZE=$heap_size/g" docker-compose.cme.yml
            print_info "CME node configuration updated successfully"
        else
            print_error "docker-compose.cme.yml not found"
            exit 1
        fi
        ;;
        
    3)
        print_info "Deploying Main Node..."
        docker-compose -f docker-compose.main.yml up -d
        print_info "Main node deployed. Waiting for it to be ready..."
        sleep 10
        print_info "Checking main node status..."
        docker-compose -f docker-compose.main.yml ps
        print_warn "Wait 60-90 seconds before deploying CME node"
        ;;
        
    4)
        print_info "Deploying CME Node..."
        print_warn "Make sure Main Node is fully running first!"
        read -p "Continue? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            docker-compose -f docker-compose.cme.yml up -d
            print_info "CME node deployed. Waiting for it to join cluster..."
            sleep 10
            print_info "Checking CME node status..."
            docker-compose -f docker-compose.cme.yml ps
        fi
        ;;
        
    5)
        print_info "Checking Cluster Status..."
        echo ""
        print_info "Main Node Status:"
        docker exec -it tqdb-cassandra-main nodetool status 2>/dev/null || print_warn "Main node not running or not accessible"
        echo ""
        print_info "CME Node Status:"
        docker exec -it tqdb-cassandra-cme nodetool status 2>/dev/null || print_warn "CME node not running or not accessible"
        ;;
        
    6)
        print_info "Stopping Main Node..."
        read -p "This will stop the main node. Continue? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            docker-compose -f docker-compose.main.yml down
            print_info "Main node stopped"
        fi
        ;;
        
    7)
        print_info "Stopping CME Node..."
        docker-compose -f docker-compose.cme.yml down
        print_info "CME node stopped"
        ;;
        
    8)
        print_info "Viewing Main Node Logs..."
        docker-compose -f docker-compose.main.yml logs -f --tail=100
        ;;
        
    9)
        print_info "Viewing CME Node Logs..."
        docker-compose -f docker-compose.cme.yml logs -f --tail=100
        ;;
        
    0)
        print_info "Exiting..."
        exit 0
        ;;
        
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

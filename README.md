# TQDB Rocky Linux 9 Installation Guide

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
  - [User Setup](#user-setup)
- [Installation Steps](#installation-steps)
  - [1. System Preparation](#1-system-preparation)
    - [Network Configuration](#network-configuration)
    - [Install Required Packages](#install-required-packages)
    - [Hostname Configuration (Optional)](#hostname-configuration-optional)
  - [2. Security Configuration](#2-security-configuration)
  - [3. Source Code Setup](#3-source-code-setup)
  - [4. Java Installation](#4-java-installation)
  - [5. Cassandra Installation and Configuration](#5-cassandra-installation-and-configuration)
    - [Install Cassandra](#install-cassandra)
    - [Verify Cassandra Installation](#verify-cassandra-installation)
    - [Create Legacy-Style Directory Structure](#create-legacy-style-directory-structure)
    - [Install Cassandra C++ Driver](#install-cassandra-c-driver)
  - [6. Apache HTTP Server (httpd) Configuration](#6-apache-http-server-httpd-configuration)
  - [7. System Configuration](#7-system-configuration)
    - [Timezone Setup](#timezone-setup)
    - [Boot-time Configuration](#boot-time-configuration)
    - [Additional Tools Installation](#additional-tools-installation)
    - [Cron Job Configuration](#cron-job-configuration)
  - [8. Final Setup and Reboot](#8-final-setup-and-reboot)
- [Database Schema Setup](#database-schema-setup)
  - [Cassandra KeySpace and Tables](#cassandra-keyspace-and-tables)
- [System Verification](#system-verification)
  - [Post-Installation Checks](#post-installation-checks)
    - [1. Verify Demo Data Service](#1-verify-demo-data-service)
    - [2. Verify Cassandra Data Insertion](#2-verify-cassandra-data-insertion)
- [Alternative Platforms](#alternative-platforms)
  - [Non-RedHat/Rocky Systems](#non-redhatrocky-systems)
- [Additional Resources](#additional-resources)
  - [VirtualBox VM Download](#virtualbox-vm-download)
- [Rocky 9 Specific Notes](#rocky-9-specific-notes)
- [Security Considerations for Production](#security-considerations-for-production)
- [Notes](#notes)

## Overview
This guide provides step-by-step instructions for installing and configuring TQDB (Time-series Quote Database) on Rocky Linux 9.

## Prerequisites

### User Setup
**Important:** All steps below must be executed as user 'tqdb'. Create and configure this user first:

```bash
# Create the tqdb user
sudo useradd -m tqdb
sudo passwd tqdb  # Set password for user 'tqdb'
sudo usermod -aG wheel tqdb  # Add to wheel group for sudo privileges
```

## Installation Steps

### 1. System Preparation

#### Network Configuration
```bash
# Configure network using nmtui
sudo nmtui
```

#### Install Required Packages
```bash
# Enable EPEL repository
sudo dnf install -y epel-release

# Install essential packages
sudo dnf install -y wget git nc python3-pip python3-dateutil net-tools httpd chrony
sudo systemctl enable chronyd && sudo systemctl start chronyd
sudo dnf update -y

# Create symbolic links
sudo ln -sf /usr/bin/nc /usr/bin/netcat

# Upgrade pip and install Python packages
sudo python3 -m pip install --upgrade pip
sudo python3 -m pip install cassandra-driver
```

#### Hostname Configuration (Optional)
```bash
# Check current hostname
hostnamectl

# Set new hostname (replace TQDBXXXX with desired name)
sudo hostnamectl set-hostname TQDBXXXX
```

### 2. Security Configuration

```bash
# Configure firewall (Rocky 9 uses firewalld by default)
# Configure firewall rules for required services
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=9042/tcp  # Cassandra
sudo firewall-cmd --permanent --add-port=4568/tcp  # Demo server
sudo firewall-cmd --reload

# Configure SELinux (recommended: keep enabled for security)
# Set SELinux to permissive mode for TQDB compatibility (safer than disabled)
sudo setenforce 0
sudo sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config

# Alternative: For development/testing only - disable SELinux completely (NOT recommended for production)
# sudo sed -i 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config

# Configure SSH security
sudo sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Reboot to apply changes
sudo reboot
```

### 3. Source Code Setup

```bash
# Create necessary directories
mkdir /home/tqdb/codes 
mkdir /home/tqdb/oldtick

# Clone TQDB repository
git clone https://github.com/wldtw2008/tqdb.git /home/tqdb/codes/tqdb
```

### 4. Java Installation

```bash
# Install Java 11 (recommended for Rocky 9)
sudo dnf install -y java-11-openjdk java-11-openjdk-devel

# Verify installation
java -version

# Set JAVA_HOME environment variable
echo 'export JAVA_HOME=/usr/lib/jvm/java-11-openjdk' | sudo tee -a /etc/environment
source /etc/environment
```

### 5. Cassandra Installation and Configuration

#### Install Cassandra
Reference: [Apache Cassandra Installation Guide](https://cassandra.apache.org/doc/latest/getting_started/installing.html)

```bash
# Add Apache Cassandra repository
cat << 'EOF' | sudo tee /etc/yum.repos.d/cassandra.repo
[cassandra]
name=Apache Cassandra 4.1
baseurl=https://redhat.cassandra.apache.org/41x/
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://downloads.apache.org/cassandra/KEYS
EOF

# Install Cassandra
sudo dnf install -y cassandra

# Enable and start Cassandra service
sudo systemctl enable cassandra
sudo systemctl start cassandra
```

#### Verify Cassandra Installation
```bash
# Check if Cassandra is running
sudo systemctl status cassandra
```

#### Create Legacy-Style Directory Structure
```bash
# Create compatibility directories and symlinks
sudo mkdir -p /var/cassandra-oldverlike
sudo ln -sf /var/cassandra-oldverlike /var/cassandra
sudo mkdir -p /var/cassandra/bin
sudo ln -sf /usr/bin/nodetool /var/cassandra/bin/
sudo ln -sf /usr/bin/cqlsh /var/cassandra/bin/
sudo ln -sf /usr/bin/cqlsh.py /var/cassandra/bin/
sudo ln -sf /var/lib/cassandra/ /var/cassandra/data
sudo ln -sf /etc/cassandra/ /var/cassandra/conf
```

#### Install Cassandra C++ Driver
```bash
# Install basic dependencies
sudo dnf install -y wget

# Download and install DataStax C++ driver packages for Rocky Linux
cd /tmp

# Download the main driver package
wget https://datastax.jfrog.io/artifactory/cpp-php-drivers/cpp-driver/builds/2.17.1/e05897d/rocky/9.2/cassandra/v2.17.1/cassandra-cpp-driver-2.17.1-1.el9.x86_64.rpm

# Download the development package
wget https://datastax.jfrog.io/artifactory/cpp-php-drivers/cpp-driver/builds/2.17.1/e05897d/rocky/9.2/cassandra/v2.17.1/cassandra-cpp-driver-devel-2.17.1-1.el9.x86_64.rpm

# Download dependencies (libuv)
wget https://datastax.jfrog.io/artifactory/cpp-php-drivers/cpp-driver/builds/2.17.1/e05897d/rocky/9.2/dependencies/libuv/v1.34.0/libuv-1.34.0-1.el9.x86_64.rpm
wget https://datastax.jfrog.io/artifactory/cpp-php-drivers/cpp-driver/builds/2.17.1/e05897d/rocky/9.2/dependencies/libuv/v1.34.0/libuv-devel-1.34.0-1.el9.x86_64.rpm

# Install the packages in correct order (dependencies first)
sudo rpm -ivh libuv-1.34.0-1.el9.x86_64.rpm
sudo rpm -ivh libuv-devel-1.34.0-1.el9.x86_64.rpm
sudo rpm -ivh cassandra-cpp-driver-2.17.1-1.el9.x86_64.rpm
sudo rpm -ivh cassandra-cpp-driver-devel-2.17.1-1.el9.x86_64.rpm

# Update library cache
sudo ldconfig

# Verify installation
echo "Checking installed packages..."
rpm -qa | grep -E "(cassandra|libuv)"

echo "Checking library files..."
ldconfig -p | grep cassandra
ls -la /usr/lib64/libcassandra*

echo "Checking header files..."
ls -la /usr/include/cassandra*
```


#### Test the C++ driver installation
```bash
echo "Testing C++ driver compilation..."
cat > /tmp/test_cassandra.cpp << 'EOF'
#include <cassandra.h>
#include <iostream>

int main() {
    std::cout << "Cassandra C++ Driver test - basic functionality check" << std::endl;
    
    // Test basic cluster creation
    CassCluster* cluster = cass_cluster_new();
    if (cluster) {
        std::cout << "✓ Successfully created Cassandra cluster object" << std::endl;
        
        // Test session creation
        CassSession* session = cass_session_new();
        if (session) {
            std::cout << "✓ Successfully created Cassandra session object" << std::endl;
            cass_session_free(session);
        } else {
            std::cout << "✗ Failed to create session object" << std::endl;
        }
        
        cass_cluster_free(cluster);
    } else {
        std::cout << "✗ Failed to create cluster object" << std::endl;
        return 1;
    }
    
    std::cout << "✓ Cassandra C++ Driver is working correctly" << std::endl;
    return 0;
}
EOF

# Compile and run test
g++ -o /tmp/test_cassandra /tmp/test_cassandra.cpp -lcassandra
/tmp/test_cassandra

# Clean up test files and downloads
rm -f /tmp/test_cassandra /tmp/test_cassandra.cpp
rm -f /tmp/*.rpm

# Final verification with TQDB tools
echo "Testing with TQDB tools..."
/home/tqdb/codes/tqdb/tools/itick  # Run this to verify cpp-driver works with TQDB
```

### 6. Apache HTTP Server (httpd) Configuration

```bash
# Configure web-related settings
cd /home/tqdb/codes/tqdb/tools/for_web && sudo ./buildApache.sh

# Enable and start Apache
sudo systemctl enable httpd && sudo systemctl restart httpd
```

### 7. System Configuration

#### Timezone Setup
```bash
# Check current timezone
timedatectl status

# Set timezone to UTC (or your preferred timezone)
sudo timedatectl set-timezone UTC
```

#### Boot-time Configuration

**Rocky 9 Modern Approach (Recommended):**
```bash
# 1. Set up environment profile (system-wide configuration)
sudo ln -sf /home/tqdb/codes/tqdb/script_for_sys/profile_tqdb.sh /etc/profile.d/

# 2. Create systemd-compatible environment file
sudo cp /home/tqdb/codes/tqdb/script_for_sys/tqdb.env /etc/systemd/system/tqdb.env

# 3. Create systemd service for TQDB (modern Rocky 9 approach)
sudo tee /etc/systemd/system/tqdb.service > /dev/null << 'EOF'
[Unit]
Description=TQDB Time-series Quote Database Service
Documentation=https://github.com/wldtw2008/tqdb
After=network-online.target cassandra.service
Wants=network-online.target
Requires=cassandra.service

[Service]
Type=forking
User=tqdb
Group=tqdb
Environment=HOME=/home/tqdb
Environment=USER=tqdb
EnvironmentFile=/etc/systemd/system/tqdb.env
ExecStartPre=/bin/mkdir -p /tmp/TQAlert
ExecStartPre=/bin/chmod 777 /tmp/TQAlert
ExecStart=/home/tqdb/codes/tqdb/script_for_sys/tqdbStartup.sh
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
TimeoutStartSec=60
TimeoutStopSec=30
Restart=on-failure
RestartSec=10

# Security settings (Rocky 9 hardening)
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/tmp /var/log /home/tqdb

[Install]
WantedBy=multi-user.target
EOF

# 3. Enable and configure the service
sudo systemctl daemon-reload
sudo systemctl enable tqdb.service

# 4. Configure environment variables in the systemd environment file
sudo nano /etc/systemd/system/tqdb.env
# Update the following variables as needed:
# - CASS_IP (Cassandra IP address)
# - CASS_PORT (default: 9042)
# - D2TQ_IP (Data source IP)
# - D2TQ_PORT (Data source port)
# - TQDB_DIR (TQDB installation directory)

# 5. Also configure shell environment (for manual script execution)
sudo nano /etc/profile.d/profile_tqdb.sh
# This file is used when running scripts manually or in shell sessions

# 5. Create systemd override for custom configuration (optional)
sudo mkdir -p /etc/systemd/system/tqdb.service.d
sudo tee /etc/systemd/system/tqdb.service.d/override.conf > /dev/null << 'EOF'
[Service]
# Add custom environment variables or override service settings here
# Example:
# Environment=CUSTOM_VAR=value
EOF

# 6. Verify service configuration
sudo systemctl daemon-reload
sudo systemctl status tqdb.service

# 7. Test the service (optional - for immediate testing)
# sudo systemctl start tqdb.service
# sudo systemctl status tqdb.service
```

**Environment File Configuration:**

The systemd service uses two environment configuration approaches:

1. **For systemd service** (`/etc/systemd/system/tqdb.env`): 
   - Simple `KEY=VALUE` format without shell expansions
   - Used by systemd when running the service

2. **For shell sessions** (`/etc/profile.d/profile_tqdb.sh`):
   - Standard bash script with exports and parameter expansions
   - Used when running scripts manually or in shell sessions

**To modify environment variables:**
```bash
# Edit systemd environment file
sudo nano /etc/systemd/system/tqdb.env

# Edit shell environment file  
sudo nano /etc/profile.d/profile_tqdb.sh

# Apply changes
sudo systemctl daemon-reload
sudo systemctl restart tqdb.service
```

**Legacy Compatibility (Fallback for older systems):**
```bash
# For systems that still require SysV init compatibility
sudo ln -sf /home/tqdb/codes/tqdb/script_for_sys/tqdbStartup.sh /etc/init.d/tqdbStartup
sudo chmod +x /etc/rc.d/rc.local
echo '/etc/init.d/tqdbStartup' | sudo tee -a /etc/rc.d/rc.local

# Enable rc.local service (disabled by default in Rocky 9)
sudo systemctl enable rc-local
```

**Service Management Commands:**
```bash
# Start TQDB service
sudo systemctl start tqdb.service

# Stop TQDB service
sudo systemctl stop tqdb.service

# Restart TQDB service
sudo systemctl restart tqdb.service

# Check service status
sudo systemctl status tqdb.service

# View service logs
sudo journalctl -u tqdb.service -f

# Disable service (if needed)
sudo systemctl disable tqdb.service
```

**Enhanced Systemd Scripts (Optional):**

For better reliability, enhanced startup/stop scripts are available:

```bash
# Make enhanced scripts executable
chmod +x /home/tqdb/codes/tqdb/script_for_sys/tqdbStartup_systemd.sh
chmod +x /home/tqdb/codes/tqdb/script_for_sys/tqdbStop.sh

# These scripts provide:
# - Better error handling and logging
# - Service dependency checking
# - Graceful shutdown procedures
# - Health monitoring capabilities
```

#### Additional Tools Installation
```bash
# Install ucspi-tcp and daemontools (build from source for Rocky 9)
# Note: The old RPM packages may not be compatible with Rocky 9

# Install daemontools from source
cd /tmp
wget http://cr.yp.to/daemontools/daemontools-0.76.tar.gz
tar -xzf daemontools-0.76.tar.gz
cd admin/daemontools-0.76
sudo dnf install -y gcc make
package/install

# Install ucspi-tcp from source
cd /tmp
wget http://cr.yp.to/ucspi-tcp/ucspi-tcp-0.88.tar.gz
tar -xzf ucspi-tcp-0.88.tar.gz
cd ucspi-tcp-0.88
make
sudo make setup check

# Alternative: Use the provided RPM files if they work
# sudo rpm -ivh /home/tqdb/codes/tqdb/3rd/daemontools-0.76-1.el6.art.x86_64.rpm
# sudo rpm -ivh /home/tqdb/codes/tqdb/3rd/ucspi-tcp-0.88-2.2.x86_64.rpm
```

#### Cron Job Configuration
```bash
# Edit system crontab
sudo vi /etc/crontab
```

Add the following cron jobs:
```cron
# Build yesterday 1Min from Tick at every 2:15
15 2    * * 1,2,3,4,5,6,7   root   cd /home/tqdb/codes/tqdb/tools && ./build1MinFromTick.sh ALL 0
30 2    * * 1,2,3,4,5,6,7   root   cd /home/tqdb/codes/tqdb/tools && ./build1SecFromTick.sh @ALL_SSEC@ 0
02 5    * * 7   root    cd /home/tqdb/codes/tqdb/tools && ./purgeTick.sh && reboot
# Chrony time sync (replaced NTP)
30 3    * * *   root    chrony sources -v
# TimeZone database update
0 12    1 * *   root    dnf update -y tzdata
```

### 8. Final Setup and Reboot

```bash
# Reboot to confirm automatic data reception from server
sudo reboot
```

## Database Schema Setup

### Cassandra KeySpace and Tables

1. **Connect to Cassandra:**
   ```bash
   /var/cassandra/bin/cqlsh
   ```

2. **Create KeySpace and Tables:**
   ```sql
   CREATE KEYSPACE tqdb1 WITH REPLICATION = { 'class' : 'SimpleStrategy', 'replication_factor' : 3 };

   CREATE TABLE tqdb1.tick (
       symbol text,
       datetime timestamp,
       keyval map<text, double>,
       type int,
       PRIMARY KEY (symbol, datetime)
   );

   CREATE TABLE tqdb1.symbol (
       symbol text PRIMARY KEY,
       keyval map<text, text>
   );

   CREATE TABLE tqdb1.minbar (
       symbol text,
       datetime timestamp,
       close double,
       high double,
       low double,
       open double,
       vol double,
       PRIMARY KEY (symbol, datetime)
   );

   CREATE TABLE tqdb1.secbar (
       symbol text,
       datetime timestamp,
       close double,
       high double,
       low double,
       open double,
       vol double,
       PRIMARY KEY (symbol, datetime)
   );

   CREATE TABLE tqdb1.conf (
       confKey text PRIMARY KEY,
       confVal text
   );
   ```
## System Verification

### Post-Installation Checks

#### 1. Verify Demo Data Service
```bash
# Check if demo server is running
ps -ef | grep demo_d2tq_server.sh

# Test demo data connection
netcat 127.0.0.1 4568
```

#### 2. Verify Cassandra Data Insertion
```bash
# Check if auto-insertion service is running
ps -ef | grep autoIns2Cass.sh

# Check insertion logs
cat /tmp/autoIns2Cass.log

# Manual test of tick insertion
stdbuf -i0 -o0 -e0 netcat $D2TQ_IP $D2TQ_PORT | $TQDB_DIR/tools/itick $CASS_IP $CASS_PORT tqdb1 0 0
```

### Troubleshooting

#### Common systemd Environment Issues
If you see errors like "Ignoring invalid environment assignment" in systemd logs:

1. **Check environment file format:**
   ```bash
   # Verify systemd environment file uses simple KEY=VALUE format
   cat /etc/systemd/system/tqdb.env
   ```

2. **Fix invalid environment file:**
   ```bash
   # Remove export statements and shell expansions from systemd env file
   sudo sed -i 's/^export //g' /etc/systemd/system/tqdb.env
   sudo sed -i 's/\${[^}]*:-\([^}]*\)}/\1/g' /etc/systemd/system/tqdb.env
   ```

3. **Reload and restart service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart tqdb.service
   sudo systemctl status tqdb.service
   ```

4. **Check service logs:**
   ```bash
   sudo journalctl -u tqdb.service -f
   ```

## Additional Resources

### VirtualBox VM Download
Pre-configured VirtualBox VM available at:
- **Download Link:** https://drive.google.com/open?id=16ZawNAWJNDcGV2jGirviIWzd_EwXlNfe
- **VM Credentials:**
  - Username: `tqdb`
  - Password: `tqdb@888`
  - Root Password: `tqdb@888`
- **Note:** This VM is based on CentOS 7. For Rocky 9, follow this updated guide instead.

## Rocky 9 Specific Notes
- **Package Manager:** Rocky 9 uses `dnf` instead of `yum` (though `yum` is aliased to `dnf`)
- **Python:** Default Python is Python 3.9+ (use `python3` and `pip3` commands)
- **Time Sync:** Uses `chronyd` instead of `ntpd` for time synchronization
- **Java:** Recommended to use Java 11 or newer instead of Java 8
- **Systemd:** Prefer systemd services over SysV init scripts
- **Firewall:** `firewalld` is enabled by default and should be configured properly
- **SELinux:** Enabled by default in enforcing mode (consider keeping it enabled for security)

## Security Considerations for Production
For production environments, consider:
1. **Keep SELinux enabled** and configure appropriate policies
2. **Configure firewalld** instead of disabling it completely
3. **Use specific firewall rules** for required ports only
4. **Regular security updates** with `dnf update`
5. **Proper SSL/TLS certificates** for web services

## Notes
- Ensure all commands are executed as the `tqdb` user unless specified otherwise
- The system must be rebooted after installation to confirm automatic data reception
- Configuration files in `/etc/profile.d/profile_tqdb.sh` must be updated with correct IPs and ports
- For Cassandra KeySpace and Table creation, refer to the Database Schema Setup section above
- Some legacy RPM packages may need to be rebuilt or replaced for Rocky 9 compatibility

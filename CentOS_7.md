# TQDB CentOS 7 Installation Guide

## Overview
This guide provides step-by-step instructions for installing and configuring TQDB (Time-series Quote Database) on CentOS 7.

## Prerequisites

### User Setup
**Important:** All steps below must be executed as user 'tqdb'. Create and configure this user first:

```bash
# Create the tqdb user
sudo adduser tqdb
sudo passwd tqdb  # Set password for user 'tqdb'
sudo vi /etc/sudoers  # Grant root privileges to user 'tqdb'
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
# Install essential packages
sudo yum install -y epel-release wget git nc python-pip python-dateutil net-tools httpd ntp ntpd
sudo systemctl enable ntpd && sudo systemctl start ntpd
sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7
sudo yum update

# Create symbolic links and upgrade pip
sudo ln -s /usr/bin/nc /usr/bin/netcat
sudo yum install -y python-pip && sudo pip install --upgrade pip
sudo pip install --upgrade cassandra-driver
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
# Disable SELinux
sudo setenforce 0
sudo vi /etc/sysconfig/selinux  # Set to 'disabled'

# Disable firewall
sudo systemctl disable firewalld
sudo systemctl stop firewalld

# Configure SSH (disable root login)
sudo vi /etc/ssh/sshd_config  # Set 'PermitRootLogin no'

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
```### 4. Java Installation

```bash
# Install Java 8
sudo yum install java-1.8.0-openjdk

# Verify installation
java -version
```

### 5. Cassandra Installation and Configuration

#### Install Cassandra
Reference: [DataStax Cassandra Installation Guide](http://docs.datastax.com/en/cassandra/3.x/cassandra/install/installRHEL.html)

```bash
# Configure DataStax repository
sudo vi /etc/yum.repos.d/datastax.repo
```

Add the following content to the repository file:
```ini
[datastax-ddc] 
name = DataStax Repo for Apache Cassandra
baseurl = http://rpm.datastax.com/datastax-ddc/3.2
enabled = 1
gpgcheck = 0
```

```bash
# Install Cassandra
sudo yum install -y datastax-ddc

# Enable and start Cassandra service
sudo systemctl enable cassandra && sudo systemctl restart cassandra
```

#### Verify Cassandra Installation
```bash
# Check if Cassandra is running
ps -ef | grep cassandra
nodetool status
```

#### Create Legacy-Style Directory Structure
```bash
# Create compatibility directories and symlinks
sudo mkdir /var/cassandra-oldverlike
sudo ln -s /var/cassandra-oldverlike /var/cassandra
sudo mkdir /var/cassandra/bin
sudo ln -s /usr/bin/nodetool /var/cassandra/bin/
sudo ln -s /usr/bin/cqlsh /var/cassandra/bin/
sudo ln -s /usr/bin/cqlsh.py /var/cassandra/bin/
sudo ln -s /var/lib/cassandra/ /var/cassandra/data
sudo ln -s /etc/cassandra/ /var/cassandra/conf
```

#### Install Cassandra C++ Driver
```bash
# Download and install C++ driver
wget downloads.datastax.com/cpp-driver/centos/7/cassandra/v2.4.3/cassandra-cpp-driver-2.4.3-1.el7.centos.x86_64.rpm
sudo yum install -y libuv
sudo rpm -ivh cassandra-cpp-driver-2.4.3-1.el7.centos.x86_64.rpm

# Test the C++ driver
/home/tqdb/codes/tqdb/tools/itick  # Run this to verify cpp-driver works
```

### 6. Apache HTTP Server (httpd) Configuration

```bash
# Configure web-related settings
cd /home/tqdb/codes/tqdb/tools/for_web && sudo ./buildApache.sh

# Enable and start Apache
sudo systemctl enable httpd && sudo systemctl restart httpd
```### 7. System Configuration

#### Timezone Setup
```bash
# Check current timezone
ls -lrt /etc/localtime

# Set timezone to UTC (or your preferred timezone)
sudo rm /etc/localtime && sudo ln -s /usr/share/zoneinfo/UTC /etc/localtime && echo "UTC" | sudo tee /etc/timezone
```

#### Boot-time Configuration
```bash
# Setup startup scripts
sudo ln -s /home/tqdb/codes/tqdb/script_for_sys/tqdbStartup.sh /etc/init.d
sudo vi /etc/rc.d/rc.local  # Add '/etc/init.d/tqdbStartup.sh' to the last line
sudo chmod +x /etc/rc.d/rc.local
sudo ln -s /home/tqdb/codes/tqdb/script_for_sys/profile_tqdb.sh /etc/profile.d/

# Configure IPs and Ports
sudo vi /etc/profile.d/profile_tqdb.sh  # Update relevant IPs & Ports
```

#### Additional Tools Installation
```bash
# Install ucspi-tcp (from 3rd directory)
sudo rpm -ivh daemontools-0.76-1.el6.art.x86_64.rpm
sudo rpm -ivh ucspi-tcp-0.88-2.2.x86_64.rpm
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
# NTP Update
30 3    * * *   root    ntpdate clock.stdtime.gov.tw
# TimeZone database update
0 12    1 * *   root    yum update -y tzdata
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

## Alternative Platforms

### Non-RedHat/CentOS Systems
For systems other than RedHat/CentOS, use the following commands:

```bash
# Create symbolic links
sudo ln -s /home/tqdb/codes/tqdb/script_for_sys/profile_tqdb.sh /etc/profile.d/profile_tqdb.sh
sudo ln -s /home/tqdb/codes/tqdb/script_for_sys/tqdbStartup.sh /etc/init.d/tqdbStartup.sh

# Configure startup service
cd /etc/init.d && sudo update-rc.d tqdbStartup.sh defaults
```

## Additional Resources

### VirtualBox VM Download
Pre-configured VirtualBox VM available at:
- **Download Link:** https://drive.google.com/open?id=16ZawNAWJNDcGV2jGirviIWzd_EwXlNfe
- **VM Credentials:**
  - Username: `tqdb`
  - Password: `tqdb@888`
  - Root Password: `tqdb@888`

## Notes
- Ensure all commands are executed as the `tqdb` user unless specified otherwise
- The system must be rebooted after installation to confirm automatic data reception
- Configuration files in `/etc/profile.d/profile_tqdb.sh` must be updated with correct IPs and ports
- For Cassandra KeySpace and Table creation, refer to the Database Schema Setup section above

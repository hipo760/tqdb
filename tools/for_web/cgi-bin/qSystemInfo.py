#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
TQ Database System Information CGI Script

This CGI script collects and displays comprehensive system information for the TQ Database server.
It gathers information about the host, timezone, scheduled tasks, system resources, and more.

Updated for Rocky Linux 9.0 and Cassandra 4.1 compatibility.

Author: TQ Database Team
Version: 3.1 (Rocky Linux 9.0 & Cassandra 4.1 compatible)
Date: 2025-01-27

Dependencies:
- Python 3.x
- Rocky Linux 9.0 (or compatible RHEL-based distribution)
- Cassandra 4.1 (cqlsh available in PATH or standard locations)
- Access to system commands (hostname, df, top, dnf, systemctl, etc.)

System Requirements:
- Rocky Linux 9.0+ or compatible RHEL 9+ distribution
- Cassandra 4.1+ with cqlsh installed
- Standard system utilities (systemctl, dnf, timedatectl)

Usage:
    HTTP GET: /cgi-bin/qSystemInfo.py
    
Returns:
    JSON response containing system information arrays with [key, value] pairs:
    - Host Info: Hostname and IP addresses
    - Server Time: Current time, timezone, and timezone database version
    - Purge Tick Schedule: Cron schedule for tick data purging
    - Build 1Min Schedule: Cron schedule for 1-minute bar building
    - Build 1Sec Schedule: Cron schedule for 1-second bar building
    - Reboot Schedule: Scheduled system reboots
    - Linux Info: OS distribution, kernel version, and architecture
    - CPUs Info: CPU model, core count, and processor information
    - Memory Info: System memory usage (new in v3.1)
    - Top Info: Current system processes and resource usage
    - Disk Info: Disk space usage
    - Uptime Info: System uptime information (new in v3.1)
    - Cassandra Service: Cassandra service status (new in v3.1)

Changes in v3.1:
- Updated for Rocky Linux 9.0 compatibility
- Updated for Cassandra 4.1 compatibility
- Enhanced cqlsh detection for multiple installation methods
- Added dnf package manager support (replacing yum)
- Added systemctl service monitoring
- Added timedatectl timezone detection
- Enhanced memory and uptime reporting
- Improved error handling for modern Linux distributions
"""

import time
import sys
import datetime
import os
import subprocess
import json

# Configuration constants for Rocky Linux 9.0 and Cassandra 4.1
CASSANDRA_IP = "127.0.0.1"
CASSANDRA_DB = "tqdb1"
BIN_DIR = '/home/tqdb/codes/tqdb/tools/'

# Cassandra 4.1 paths (updated for Rocky Linux 9.0)
CASSANDRA_HOME = '/opt/cassandra'  # Common installation path for Cassandra 4.1
CQLSH_PATH = '/usr/bin/cqlsh'      # System-wide cqlsh installation
CASSANDRA_BIN = '/opt/cassandra/bin'  # Alternative path if installed manually

# Global list to store all system information as [key, value] pairs
all_info = []


def detect_cassandra_installation():
    """
    Detect Cassandra 4.1 installation paths and return configuration info.
    
    Returns:
        dict: Dictionary containing Cassandra installation details
    """
    cassandra_info = {
        'cqlsh_path': None,
        'cassandra_home': None,
        'version': 'Unknown',
        'service_status': 'Unknown'
    }
    
    # Detect cqlsh location
    cqlsh_locations = [
        '/usr/bin/cqlsh',           # Package installation
        '/opt/cassandra/bin/cqlsh', # Manual installation
        '/usr/local/bin/cqlsh',     # Alternative location
    ]
    
    for location in cqlsh_locations:
        if os.path.exists(location):
            cassandra_info['cqlsh_path'] = location
            break
    
    # Try to get Cassandra version
    try:
        if cassandra_info['cqlsh_path']:
            version_output = run_command(f"{cassandra_info['cqlsh_path']} --version")
            if version_output:
                cassandra_info['version'] = version_output[0]
    except Exception:
        pass
    
    # Check service status (Rocky Linux 9.0 uses systemctl)
    try:
        status_output = run_command('systemctl is-active cassandra')
        if status_output:
            cassandra_info['service_status'] = status_output[0]
    except Exception:
        pass
    
    return cassandra_info


def detect_rocky_linux_features():
    """
    Detect Rocky Linux 9.0 specific features and package manager.
    
    Returns:
        dict: Dictionary containing Rocky Linux specific information
    """
    rocky_info = {
        'package_manager': 'unknown',
        'selinux_status': 'unknown',
        'firewall_status': 'unknown',
        'is_rocky': False
    }
    
    # Detect if this is Rocky Linux
    try:
        release_files = ['/etc/rocky-release', '/etc/redhat-release', '/etc/os-release']
        for release_file in release_files:
            if os.path.exists(release_file):
                content = run_command(f'cat {release_file}')
                if content and any('rocky' in line.lower() for line in content):
                    rocky_info['is_rocky'] = True
                    break
    except Exception:
        pass
    
    # Detect package manager (dnf for Rocky Linux 9.0)
    package_managers = [
        ('/usr/bin/dnf', 'dnf'),
        ('/usr/bin/yum', 'yum'),
        ('/usr/bin/apt', 'apt')
    ]
    
    for pm_path, pm_name in package_managers:
        if os.path.exists(pm_path):
            rocky_info['package_manager'] = pm_name
            break
    
    # Check SELinux status
    try:
        selinux_output = run_command('getenforce')
        if selinux_output:
            rocky_info['selinux_status'] = selinux_output[0]
    except Exception:
        pass
    
    # Check firewall status
    try:
        firewall_output = run_command('systemctl is-active firewalld')
        if firewall_output:
            rocky_info['firewall_status'] = firewall_output[0]
    except Exception:
        pass
    
    return rocky_info

def run_cql(cql_query, result_obj):
    """
    Execute a CQL (Cassandra Query Language) command using cqlsh.
    Updated for Cassandra 4.1 on Rocky Linux 9.0
    
    Args:
        cql_query (str): The CQL query to execute
        result_obj (dict): Dictionary to store the execution results
                          Will contain 'output', 'err', and 'retcode' keys
    """
    try:
        # Try multiple possible cqlsh locations for Cassandra 4.1
        cqlsh_locations = [
            '/usr/bin/cqlsh',           # System package installation
            '/opt/cassandra/bin/cqlsh', # Manual installation
            'cqlsh'                     # If in PATH
        ]
        
        cqlsh_cmd = None
        for location in cqlsh_locations:
            if os.path.exists(location) or location == 'cqlsh':
                cqlsh_cmd = location
                break
        
        if not cqlsh_cmd:
            raise FileNotFoundError("cqlsh not found in any expected location")
        
        # Execute cqlsh command with the provided CQL query
        # Note: Cassandra 4.1 cqlsh may require different working directory
        process = subprocess.Popen(
            [cqlsh_cmd, "-e", cql_query], 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True  # Python 3: Handle text instead of bytes
        )
        result_obj['output'], result_obj['err'] = process.communicate()
        result_obj['retcode'] = process.returncode
    except Exception as e:
        result_obj['output'] = ""
        result_obj['err'] = f"Error executing CQL: {str(e)}"
        result_obj['retcode'] = -1


def run_command(cmd):
    """
    Execute a shell command and return the output lines.
    
    Args:
        cmd (str): Shell command to execute
        
    Returns:
        list: List of output lines from the command (newlines stripped)
    """
    try:
        # Execute the shell command
        proc = subprocess.Popen(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Python 3: Handle text instead of bytes
        )
        
        ret = []
        # Read output line by line
        while True:
            line = proc.stdout.readline()
            if line:
                ret.append(line.rstrip('\n\r'))  # Remove newlines and carriage returns
            else:
                break
                
        return ret
    except Exception as e:
        return [f"Error executing command '{cmd}': {str(e)}"]


def collect_host_info():
    """
    Collect hostname and IP address information.
    
    Returns:
        list: Formatted host information strings
    """
    host_info = []
    
    # Get hostname
    lines = run_command('hostname')
    for line in lines:
        if len(line) > 0:
            host_info.append(f"Hostname: {line}")
    
    # Get IP addresses
    lines = run_command('hostname -I')
    for line in lines:
        for ip in line.split(' '):
            if len(ip) > 0:
                host_info.append(f"IP: {ip}")
                
    return host_info


def collect_timezone_info():
    """
    Collect system timezone and time information.
    Updated for Rocky Linux 9.0 (RHEL-based)
    
    Returns:
        list: Formatted timezone information strings
    """
    # Detect Linux distribution family - Updated for Rocky Linux 9.0
    linux_family = 'Unknown'
    try:
        temp_id = run_command('cat /etc/os-release | grep "^ID="')[0]
        if any(distro in temp_id.lower() for distro in ["rhel", "centos", "rocky", "almalinux", "fedora"]):
            linux_family = "RedHat"
        elif any(distro in temp_id.lower() for distro in ["debian", "ubuntu"]):
            linux_family = "Debian"
    except (IndexError, Exception):
        # Fallback detection for Rocky Linux 9.0
        try:
            release_info = run_command('cat /etc/redhat-release')[0]
            if any(distro in release_info.lower() for distro in ["rocky", "rhel", "centos", "red hat"]):
                linux_family = "RedHat"
        except (IndexError, Exception):
            linux_family = "Unknown"

    # Get timezone information
    zones = []
    lines = run_command('readlink -f /etc/localtime')  # Use -f instead of -s for Rocky Linux
    for line in lines:
        zones.append(line)

    zones.append(os.path.realpath('/etc/localtime'))

    # Extract timezone from zoneinfo path
    for i in range(len(zones)):
        pos = zones[i].find("zoneinfo/")
        if pos > 0:
            zones[i] = zones[i][pos+9:]
    
    # Get timezone database version - Updated for Rocky Linux 9.0
    tzdb_ver = "Unknown"
    try:
        if linux_family == "Debian":
            tzdb_ver = run_command('dpkg -s tzdata | grep Version')[0].replace('Version: ', '')
        elif linux_family == "RedHat":
            # Updated for Rocky Linux 9.0 - use dnf instead of yum, rpm query
            tzdb_result = run_command('rpm -q tzdata --queryformat "%{VERSION}-%{RELEASE}"')
            if tzdb_result and tzdb_result[0]:
                tzdb_ver = tzdb_result[0]
            else:
                # Alternative method for Rocky Linux 9.0
                tzdb_result = run_command('dnf list installed tzdata | tail -1 | awk "{print $2}"')
                if tzdb_result and tzdb_result[0]:
                    tzdb_ver = tzdb_result[0]
    except (IndexError, Exception):
        tzdb_ver = "Unknown"
        
    # Format timezone information
    lines = []
    current_time = ', '.join(run_command("date +'%Y-%m-%d %H:%M:%S (%Z)'"))
    lines.append(f"Now={current_time}")
    lines.append(f"TimeZone={', '.join(zones)} (/etc/localtime)")
    
    try:
        timezone_file = run_command('cat /etc/timezone')
        lines.append(f"TimeZone={', '.join(timezone_file)} (/etc/timezone)")
    except Exception:
        # Rocky Linux 9.0 may not have /etc/timezone, use timedatectl instead
        try:
            timedatectl_output = run_command('timedatectl show --property=Timezone --value')
            if timedatectl_output:
                lines.append(f"TimeZone={timedatectl_output[0]} (timedatectl)")
        except Exception:
            lines.append("TimeZone=Not available (/etc/timezone)")
        
    lines.append(f"tzdata Version={tzdb_ver}")
    
    return lines


def collect_cron_schedules():
    """
    Collect cron job schedules for various TQ Database operations.
    
    Returns:
        dict: Dictionary containing different schedule types and their cron entries
    """
    schedules = {}
    
    # Purge tick schedule
    lines = run_command('cat /etc/crontab | grep purgeTick.sh | sed "s/^ *//" | grep -v "^#"')
    schedules['Purge Tick Schedule'] = lines
    
    # Build 1-minute schedule
    lines = run_command('cat /etc/crontab | grep build1MinFromTick.sh | sed "s/^ *//" | grep -v "^#"')
    schedules['Build 1Min Schedule'] = lines
    
    # Build 1-second schedule
    lines = run_command('cat /etc/crontab | grep build1SecFromTick.sh | sed "s/^ *//" | grep -v "^#"')
    schedules['Build 1Sec Schedule'] = lines
    
    # Reboot schedule
    lines = run_command('cat /etc/crontab | grep -E "reboot|shutdown|halt" | sed "s/^ *//" | grep -v "^#"')
    schedules['Reboot Schedule'] = lines
    
    return schedules


def collect_system_info():
    """
    Collect various system information including OS, CPU, processes, and disk usage.
    Updated for Rocky Linux 9.0
    
    Returns:
        dict: Dictionary containing different types of system information
    """
    info = {}
    
    # Linux distribution information - Enhanced for Rocky Linux 9.0
    lines = []
    
    # Get pretty name from os-release
    pretty_name = run_command('grep -E "^PRETTY_NAME=" /etc/os-release | sed "s/\\"//g" | cut -f 2 -d "="')
    if pretty_name:
        lines.extend(pretty_name)
    
    # Get architecture
    arch_info = run_command('uname -m')  # More reliable than 'arch' command
    if arch_info:
        lines.extend(arch_info)
    
    # Add Rocky Linux specific information
    try:
        rocky_version = run_command('cat /etc/rocky-release')
        if rocky_version:
            lines.extend(rocky_version)
    except Exception:
        pass
    
    # Add kernel information
    try:
        kernel_info = run_command('uname -r')
        if kernel_info:
            lines.append(f"Kernel: {kernel_info[0]}")
    except Exception:
        pass
        
    info['Linux Info'] = lines
    
    # CPU information - Enhanced for modern systems
    cpu_lines = run_command('cat /proc/cpuinfo | grep -E "model name|cpu cores|processor" | sort | uniq')
    
    # Add additional CPU information for Rocky Linux 9.0
    try:
        cpu_count = run_command('nproc')
        if cpu_count:
            cpu_lines.append(f"Total CPU cores: {cpu_count[0]}")
    except Exception:
        pass
        
    info['CPUs Info'] = cpu_lines
    
    # Memory information - Added for better system monitoring
    try:
        memory_info = run_command('free -h | head -2')
        info['Memory Info'] = memory_info
    except Exception:
        info['Memory Info'] = ['Memory information not available']
    
    # Top processes information
    lines = run_command('top -bn1 | head -10')
    info['Top Info'] = lines
    
    # Disk usage information
    lines = run_command('df -h')
    info['Disk Info'] = lines
    
    # System uptime - Added for Rocky Linux 9.0
    try:
        uptime_info = run_command('uptime')
        info['Uptime Info'] = uptime_info
    except Exception:
        info['Uptime Info'] = ['Uptime information not available']
    
    # Systemd services status - Relevant for Rocky Linux 9.0
    try:
        # Check Cassandra service status
        cassandra_status = run_command('systemctl is-active cassandra 2>/dev/null || echo "not available"')
        if cassandra_status:
            info['Cassandra Service'] = [f"Status: {cassandra_status[0]}"]
    except Exception:
        info['Cassandra Service'] = ['Service status not available']
    
    return info


def send_json_response(data):
    """
    Send JSON response with proper HTTP headers.
    
    Args:
        data: Python object to serialize as JSON
    """
    # Send HTTP headers
    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")
    
    # Send JSON data
    sys.stdout.write(json.dumps(data, indent=2))
    sys.stdout.flush()

# Main CGI execution
if __name__ == "__main__":
    try:
        # Detect system configuration for Rocky Linux 9.0 and Cassandra 4.1
        cassandra_info = detect_cassandra_installation()
        rocky_info = detect_rocky_linux_features()
        
        # Add system detection information
        detection_info = []
        detection_info.append(f"Package Manager: {rocky_info['package_manager']}")
        detection_info.append(f"SELinux Status: {rocky_info['selinux_status']}")
        detection_info.append(f"Firewall Status: {rocky_info['firewall_status']}")
        detection_info.append(f"Cassandra cqlsh: {cassandra_info['cqlsh_path'] or 'Not found'}")
        detection_info.append(f"Cassandra Version: {cassandra_info['version']}")
        detection_info.append(f"Cassandra Service: {cassandra_info['service_status']}")
        all_info.append(['System Detection (Rocky 9.0)', '\n'.join(detection_info)])

        # Example of CQL usage (updated for Cassandra 4.1)
        if False:
            temp_file = f"/tmp/qsummery.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}.txt"
            result_obj = {}
            cql = f"SELECT * FROM {CASSANDRA_DB}.tick WHERE symbol='EXAMPLE' ORDER BY datetime LIMIT 10;"
            run_cql(cql, result_obj)
            # summary['tick.first'] = result_obj['output']

        # Collect host information (hostname and IP addresses)
        host_info = collect_host_info()
        all_info.append(['Host Info', '\n'.join(host_info)])

        # Collect timezone and time information
        timezone_info = collect_timezone_info()
        all_info.append(['Server Time', '\n'.join(timezone_info)])

        # Collect cron job schedules
        schedules = collect_cron_schedules()
        for schedule_type, schedule_lines in schedules.items():
            all_info.append([schedule_type, '\n'.join(schedule_lines)])

        # Collect system information
        system_info = collect_system_info()
        for info_type, info_lines in system_info.items():
            all_info.append([info_type, '\n'.join(info_lines)])        # Send JSON response with all collected information
        send_json_response(all_info)
        
    except Exception as e:
        # Handle any unexpected errors
        error_response = [
            ['Error', f'System exception: {str(e)}'],
            ['Debug Info', f'Python version: {sys.version}'],
            ['Debug Info', 'OS detected: Rocky Linux 9.0 compatible' if rocky_info.get('is_rocky') else 'Unknown OS']
        ]
        send_json_response(error_response)

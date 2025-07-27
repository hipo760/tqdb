#!/usr/bin/env python3
# -*- coding: utf-8 -*-   
"""
TQAlert.py - Trading Quote Alert Monitor

This script monitors trading data streams (ticks and quotes) for configured symbols
and sends alerts when data feed issues are detected. It can detect:
- Missing ticks (price updates) for specified time periods
- Missing quotes (bid/ask updates) for specified time periods
- Market hours-based monitoring with weekday scheduling

The system reads configuration from Cassandra database and monitors timestamp files
to detect when symbols haven't received updates within configured thresholds.

Key Features:
- Configurable monitoring rules per symbol and time period
- Market hours awareness with weekday scheduling
- Alert throttling to prevent spam
- Command execution for notifications
- Hot configuration reloading
- Test mode for alert commands

Configuration Format:
The configuration is stored in Cassandra as JSON with:
- TimeRule: Per-symbol rules with [WeekVal, BeginTime, EndTime, TickSeconds, QuoteSeconds]
- AlertCMD: List of shell commands to execute on alerts

Usage:
    python TQAlert.py

The script runs as a daemon and continuously monitors the configured symbols.

Dependencies:
- cassandra-driver: For database connectivity
- dateutil: For date/time handling

Author: AutoTrade System
Date: 2025
"""

import json
import os
import math
import time
import subprocess
from datetime import datetime
# Note: Requires cassandra-driver package: pip install cassandra-driver
from cassandra.cluster import Cluster

# Global configuration
DEFAULT_KEYSPACE = 'tqdb1'
TEMP_DIR = '/tmp/TQAlert'
LASTQ_DIR = '/tmp/lastTQ'
SLEEP_INTERVAL = 5
MIN_ALERT_INTERVAL = 30  # Minimum seconds between alerts for same symbol

def log_message(message):
    """
    Log a message with timestamp.
    
    Args:
        message (str): The message to log
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def read_config_from_cassandra(keyspace, time_rules, alert_commands):
    """
    Read alert configuration from Cassandra database.
    
    This function:
    1. Connects to Cassandra and retrieves the configuration
    2. Parses the JSON configuration containing time rules and alert commands
    3. Converts rule lists to dictionaries for easier access
    4. Calculates begin offset times for precise scheduling
    
    Args:
        keyspace (str): Cassandra keyspace name
        time_rules (dict): Dictionary to store time-based monitoring rules
        alert_commands (list): List to store alert command templates
        
    Configuration Format:
        TimeRule: {
            "SYMBOL": [
                [WeekVal, BeginTime, EndTime, TickSeconds, QuoteSeconds],
                ...
            ]
        }
        AlertCMD: ["command template with {HEADER} and {BODY}", ...]
    
    Time Rule Parameters:
        - WeekVal: Bitmap for weekdays (1000000=Mon, 0100000=Tue, etc.)
        - BeginTime/EndTime: Market hours in HHMMSS format
        - TickSeconds: Alert if no ticks received for this many seconds
        - QuoteSeconds: Alert if no quotes received for this many seconds
    """
    time_rules.clear()
    alert_commands.clear()
    
    try:
        cluster = Cluster()
        session = cluster.connect(keyspace)
        
        # Query configuration from database
        query = f"SELECT confVal FROM {keyspace}.conf WHERE confKey='tqconf'"
        result = session.execute(query)
        
        if not result or len(list(result)) == 0:
            log_message('Error! No configuration data found')
            return
            
        # Parse JSON configuration (handle HTML entities)
        config_json = list(result)[0][0]
        config_json = config_json.replace('&quot;', '"').replace('&apos;', "'").replace('&bsol;', '\\')
        config = json.loads(config_json)
        
        # Load time rules and convert to structured format
        for symbol, rules in config['TimeRule'].items():
            time_rules[symbol] = rules
            
        # Load alert commands
        for cmd in config['AlertCMD']:
            alert_commands.append(cmd)
        
        # Convert rule lists to dictionaries and calculate offsets
        _process_time_rules(time_rules)
        
        # Log loaded configuration
        _log_configuration(time_rules, alert_commands)
        
        session.shutdown()
        cluster.shutdown()
        
    except Exception as e:
        log_message(f'Error reading configuration: {e}')


def _process_time_rules(time_rules):
    """
    Process and enhance time rules with calculated offsets.
    
    This function converts rule parameter lists to dictionaries and calculates
    the BegOffset time, which is the begin time plus the minimum of tick/quote intervals.
    
    Args:
        time_rules (dict): Time rules to process in-place
    """
    for symbol in time_rules:
        for i, rule_params in enumerate(time_rules[symbol]):
            # Convert list to dictionary
            rule_dict = {
                'WeekVal': rule_params[0],
                'Beg': rule_params[1],
                'End': rule_params[2],
                'TickSec': rule_params[3],
                'QuoteSec': rule_params[4],
                'BegOffset': rule_params[1]
            }
            
            # Calculate begin offset (begin time + minimum alert interval)
            min_interval = 86400  # Max seconds in a day
            
            if rule_dict['TickSec'] > 0 and rule_dict['TickSec'] < min_interval:
                min_interval = rule_dict['TickSec']
            if rule_dict['QuoteSec'] > 0 and rule_dict['QuoteSec'] < min_interval:
                min_interval = rule_dict['QuoteSec']
                
            if min_interval == 86400:
                min_interval = 0
                
            # Convert begin time to seconds and add offset
            begin_time = rule_dict['Beg']
            total_seconds = (min_interval + 
                           (begin_time // 10000) * 3600 + 
                           ((begin_time // 100) % 100) * 60 + 
                           (begin_time % 100))
            
            # Convert back to HHMMSS format
            hours = total_seconds // 3600
            minutes = (total_seconds // 60) % 60
            seconds = total_seconds % 60
            rule_dict['BegOffset'] = int(f"{hours:02d}{minutes:02d}{seconds:02d}")
            
            time_rules[symbol][i] = rule_dict


def _log_configuration(time_rules, alert_commands):
    """
    Log the loaded configuration for debugging.
    
    Args:
        time_rules (dict): Time rules to log
        alert_commands (list): Alert commands to log
    """
    log_message("Time Rules:")
    for symbol in time_rules:
        log_message(f"    Symbol: {symbol}")
        for i, rule in enumerate(time_rules[symbol]):
            log_message(f"        Rule#{i+1}: {rule}")
    
    log_message("-" * 80)
    log_message("Alert Commands:")
    for i, cmd in enumerate(alert_commands):
        log_message(f"    Cmd#{i+1}: [{cmd}]")

def read_last_timestamp(symbol, data_type):
    """
    Read the last timestamp for a symbol's data type from filesystem.
    
    The timestamp files are stored in /tmp/lastTQ/ directory with naming
    convention: {symbol}.{type} (e.g., "AAPL.LastT" for last tick time)
    
    Args:
        symbol (str): Trading symbol name
        data_type (str): Data type ('LastT' for ticks, 'LastQ' for quotes)
        
    Returns:
        int: Unix timestamp of last data, or 0 if file doesn't exist
    """
    filename = f'{LASTQ_DIR}/{symbol}.{data_type}'
    try:
        with open(filename, 'r') as f:
            line = f.readline().strip()
            return int(line)
    except (FileNotFoundError, ValueError, IOError):
        return 0


def execute_alert_command(command_template, header, body):
    """
    Execute an alert command with header and body substitution.
    
    Args:
        command_template (str): Command template with {HEADER} and {BODY} placeholders
        header (str): Alert header text
        body (str): Alert body text
    """
    # Substitute placeholders in command template
    final_command = command_template.replace('{HEADER}', header).replace('{BODY}', body)
    
    log_message(f"Alert Cmd: [{command_template}] --> [{final_command}]")
    
    # Skip commands that start with # (commented out)
    if final_command.strip().startswith('#'):
        log_message("    Skip run!")
    else:
        try:
            subprocess.call(final_command, shell=True)
            log_message("    Ran!")
        except Exception as e:
            log_message(f"    Error running command: {e}")


def get_weekday_bitmap(weekday):
    """
    Convert ISO weekday to bitmap format used by the system.
    
    Args:
        weekday (int): ISO weekday (1=Monday, 7=Sunday)
        
    Returns:
        int: Bitmap value (1000000=Monday, 0100000=Tuesday, etc.)
    """
    return int(math.pow(10, 7 - weekday))


def is_within_time_range(current_time, begin_time, end_time):
    """
    Check if current time is within the specified range.
    
    Args:
        current_time (int): Current time in HHMMSS format
        begin_time (int): Begin time in HHMMSS format
        end_time (int): End time in HHMMSS format
        
    Returns:
        bool: True if current time is within range
    """
    return begin_time <= current_time < end_time


def should_skip_symbol(symbol, last_alert_times, current_time):
    """
    Check if symbol should be skipped due to recent alert or skip file.
    
    Args:
        symbol (str): Symbol name
        last_alert_times (dict): Dictionary tracking last alert times
        current_time (int): Current unix timestamp
        
    Returns:
        tuple: (should_skip, reason) where reason explains why to skip
    """
    # Check for skip file
    skip_file = f'{TEMP_DIR}/TQAlert.skip.{symbol}'
    if os.path.isfile(skip_file):
        return True, f"Skip file {skip_file} exists"
    
    # Check for recent alert
    if (symbol in last_alert_times and 
        current_time < last_alert_times[symbol] + MIN_ALERT_INTERVAL):
        return True, f"Symbol alerted in past {MIN_ALERT_INTERVAL} seconds"
    
    return False, ""


def cleanup_old_files():
    """
    Clean up old skip files (older than 1 day).
    
    This prevents accumulation of skip files that might have been created
    for temporary muting of alerts.
    """
    try:
        # Use PowerShell command for Windows compatibility
        cleanup_cmd = f'Get-ChildItem "{TEMP_DIR}" -Filter "TQAlert.skip.*" | Where-Object {{$_.LastWriteTime -lt (Get-Date).AddDays(-1)}} | Remove-Item'
        subprocess.call(['powershell', '-Command', cleanup_cmd], shell=False)
    except Exception as e:
        log_message(f"Failed to cleanup old files: {e}")
    

def check_config_change(current_time):
    """
    Check if configuration has changed by reading timestamp file.
    
    Args:
        current_time (int): Current unix timestamp
        
    Returns:
        bool: True if configuration should be reloaded
    """
    try:
        config_change_file = f'{TEMP_DIR}/TQAlert.confchange'
        with open(config_change_file, 'r') as f:
            last_change_time = int(f.readline().strip())
            # Reload if change happened within last sleep interval * 1.5
            return current_time < last_change_time + SLEEP_INTERVAL * 1.5
    except (FileNotFoundError, ValueError, IOError):
        return False


def process_test_commands(alert_commands):
    """
    Process test command files if they exist.
    
    Test files are named: /tmp/TQAlert/TQAlert.testcmd.{index}
    When these files exist, the corresponding alert command is executed
    with test data and the file is removed.
    
    Args:
        alert_commands (list): List of alert commands
    """
    try:
        for cmd_idx in range(len(alert_commands)):
            test_cmd_file = f'{TEMP_DIR}/TQAlert.testcmd.{cmd_idx}'
            if os.path.isfile(test_cmd_file):
                test_message = f'Hello, this is test of TQAlert#{cmd_idx + 1}.'
                execute_alert_command(alert_commands[cmd_idx], '!!TEST!!', test_message)
                os.remove(test_cmd_file)
    except Exception as e:
        log_message(f"Failed to run test command: {e}")


def get_matching_rules(time_rules, current_weekday_bitmap):
    """
    Get rules that match the current weekday.
    
    Args:
        time_rules (dict): All time rules
        current_weekday_bitmap (int): Current weekday as bitmap
        
    Returns:
        list: List of matching rules with symbol and rule information
    """
    matching_rules = []
    
    for symbol, rules in time_rules.items():
        for rule_idx, rule in enumerate(rules):
            # Check if rule applies to current weekday
            if int((rule['WeekVal']) / current_weekday_bitmap) % 10 == 1:
                matching_rules.append({
                    'Symbol': symbol,
                    'RuleIdx': rule_idx,
                    'Rule': rule
                })
    
    return matching_rules


def check_symbol_alerts(rule, current_time, last_alert_times):
    """
    Check if a symbol needs to generate alerts based on missing data.
    
    Args:
        rule (dict): Rule configuration for the symbol
        current_time (int): Current unix timestamp
        last_alert_times (dict): Dictionary tracking last alert times
        
    Returns:
        tuple: (header, body) for alert, or ("", "") if no alert needed
    """
    symbol = rule['Symbol']
    rule_config = rule['Rule']
    
    header = ""
    body = ""
    
    # Check for missing quotes
    if rule_config['QuoteSec'] > 0:
        last_quote_time = read_last_timestamp(symbol, 'LastQ')
        log_message(f"Q--> {symbol} Rule#{rule['RuleIdx']} {rule_config} "
                   f"Current:{current_time} Last:{last_quote_time} Threshold:{rule_config['QuoteSec']}")
        
        if current_time > last_quote_time + rule_config['QuoteSec']:
            header = "No Quote Alert"
            body = f"{symbol} has no quote for {rule_config['QuoteSec']} seconds!"
    
    # Check for missing ticks
    if rule_config['TickSec'] > 0:
        last_tick_time = read_last_timestamp(symbol, 'LastT')
        log_message(f"T--> {symbol} Rule#{rule['RuleIdx']} {rule_config} "
                   f"Current:{current_time} Last:{last_tick_time} Threshold:{rule_config['TickSec']}")
        
        if current_time > last_tick_time + rule_config['TickSec']:
            header = "No Tick Alert"
            body = f"{symbol} has no tick for {rule_config['TickSec']} seconds!"
    
    return header, body


def monitor_symbols():
    """
    Main monitoring loop that checks symbols and generates alerts.
    
    This function:
    1. Loads configuration from Cassandra
    2. Continuously monitors symbols based on time rules
    3. Detects missing ticks/quotes and sends alerts
    4. Handles configuration reloading and test commands
    5. Manages alert throttling and skip files
    """
    last_alert_times = {}  # Track last alert time per symbol
    time_rules = {}
    alert_commands = []
    
    # Initial configuration load
    read_config_from_cassandra(DEFAULT_KEYSPACE, time_rules, alert_commands)
    
    last_check_weekday = 0
    matching_rules = []
    loop_count = 0
    
    log_message("Starting TQAlert monitoring...")
    
    while True:
        loop_count += 1
        
        # Cleanup old files every 10 loops
        if (loop_count % 10) == 0:
            cleanup_old_files()
        
        # Process test commands
        process_test_commands(alert_commands)
        
        # Get current time information
        current_time_str = datetime.now().strftime('%H%M%S')
        current_time = int(current_time_str)
        current_timestamp = int(datetime.now().timestamp())
        current_weekday = datetime.today().isoweekday()
        current_weekday_bitmap = get_weekday_bitmap(current_weekday)
        
        # Check for configuration changes
        if check_config_change(current_timestamp):
            log_message("=" * 20 + ">Config change<" + "=" * 20)
            read_config_from_cassandra(DEFAULT_KEYSPACE, time_rules, alert_commands)
            last_check_weekday = 999  # Force rule refresh
        
        # Refresh matching rules if day changed
        if last_check_weekday != current_weekday_bitmap:
            matching_rules = get_matching_rules(time_rules, current_weekday_bitmap)
            last_check_weekday = current_weekday_bitmap
            
            log_message("-" * 80)
            log_message("Detected day change...")
            log_message(f"Current rules (count={len(matching_rules)}):")
            for rule in matching_rules:
                log_message(f"    {rule}")
        
        # Log current status
        log_message(f"Current WeekVal:{current_weekday_bitmap:07d}, "
                   f"HHMMSS:{current_time}, TimeS:{current_timestamp}")
        
        # Check each matching rule
        for rule in matching_rules:
            symbol = rule['Symbol']
            rule_config = rule['Rule']
            
            # Check if current time is within monitoring window
            if not is_within_time_range(current_time, rule_config['BegOffset'], rule_config['End']):
                continue
            
            # Check if symbol should be skipped
            should_skip, skip_reason = should_skip_symbol(symbol, last_alert_times, current_timestamp)
            if should_skip:
                log_message(skip_reason)
                continue
            
            # Check for alerts
            header, body = check_symbol_alerts(rule, current_timestamp, last_alert_times)
            
            if header:
                # Record alert time and send notifications
                last_alert_times[symbol] = current_timestamp
                log_message(f"!!!{header}!!! {body}")
                
                # Execute all alert commands
                for cmd in alert_commands:
                    execute_alert_command(cmd, header, body)
        
        time.sleep(SLEEP_INTERVAL)

def ensure_directories():
    """
    Ensure required directories exist for the alert system.
    """
    directories = [TEMP_DIR, LASTQ_DIR]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            log_message(f"Warning: Could not create directory {directory}: {e}")


def main():
    """
    Main entry point for the TQAlert monitoring system.
    
    This function sets up the monitoring environment and starts the
    continuous monitoring loop with error recovery.
    """
    log_message("TQAlert - Trading Quote Alert Monitor Starting")
    log_message(f"Configuration: Keyspace={DEFAULT_KEYSPACE}")
    log_message(f"Directories: Temp={TEMP_DIR}, LastTQ={LASTQ_DIR}")
    log_message(f"Intervals: Sleep={SLEEP_INTERVAL}s, MinAlert={MIN_ALERT_INTERVAL}s")
    log_message("-" * 80)
    
    # Ensure required directories exist
    ensure_directories()
    
    # Start monitoring with error recovery
    while True:
        try:
            monitor_symbols()
        except KeyboardInterrupt:
            log_message("TQAlert monitoring stopped by user")
            break
        except Exception as e:
            log_message(f"Exception in monitoring loop: {e}")
            log_message("Restarting monitoring in 30 seconds...")
            time.sleep(30)


if __name__ == "__main__":
    main()


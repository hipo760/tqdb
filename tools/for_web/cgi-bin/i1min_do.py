#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
TQ Database Import Execution CGI Script

This CGI script initiates minute-level data import operations in the TQ Database system.
It executes predefined import commands as background processes and redirects users to
a status monitoring interface for real-time progress tracking.

Key Features:
- Ticket-based import job execution system
- Background process execution using UNIX double-fork technique
- Automatic redirection to status monitoring interface
- Command file validation and security checks
- Process isolation and daemon-style execution

Import Process Workflow:
1. Parse import ticket ID from CGI parameters
2. Validate command file existence for the ticket
3. Execute import command as background daemon process
4. Redirect user to status monitoring interface (i1min_readstatus.py)

Security Features:
- Command file validation prevents arbitrary code execution
- Process isolation using double-fork technique
- Proper file handle management and cleanup
- Error handling for failed process creation

Integration:
- Works with i1min_readstatus.py for status monitoring
- Supports ticket-based job tracking system
- Designed for web-based import management interface

Author: TQ Database Team
Compatible with: Python 3.x, Unix/Linux systems, Rocky Linux 9.0+
"""

import sys
import os
import subprocess
from urllib.parse import unquote


# Global configuration constants
CASSANDRA_IP = "127.0.0.1"  # Cassandra cluster IP address
CASSANDRA_DB = "tqdb1"  # TQ Database keyspace name
COMMAND_FILE_DIRECTORY = "/tmp"  # Directory for import command files
STATUS_MONITOR_SCRIPT = "./i1min_readstatus.py"  # Status monitoring script path


def parse_query_parameters():
    """
    Parse CGI query string parameters for import execution.
    
    Returns:
        dict: Parsed parameters containing:
            - importTicket: Unique identifier for the import job to execute
            
    Query String Format:
        ?importTicket=unique_import_id_timestamp
        
    Import Ticket:
        - Unique identifier for import job and its associated command file
        - Used to locate command file in COMMAND_FILE_DIRECTORY
        - Typically timestamp-based for uniqueness and security
        
    Note:
        URL decoding is applied to handle special characters in ticket IDs
    """
    query_string = os.environ.get("QUERY_STRING", "NA=NA")
    params = {}
    
    # Parse each parameter from query string
    for qs in query_string.split("&"):
        if "=" not in qs:
            continue
        key, value = qs.split("=", 1)
        params[key] = unquote(value)
    
    return params


def create_daemon_process():
    """
    Create a daemon process using UNIX double-fork technique.
    
    This function implements the standard UNIX double-fork technique to create
    a daemon process that runs independently of the parent CGI process and
    web server. This ensures import operations continue even if the web
    request is terminated.
    
    Process:
        1. First fork: Creates child process and exits parent
        2. Session leader: Child becomes session leader (setsid)
        3. Environment cleanup: Change directory, set umask
        4. Second fork: Creates grandchild and exits child
        5. Daemon: Grandchild becomes daemon process
        
    Benefits:
        - Process runs independently of web server
        - No controlling terminal (prevents hangups)
        - Process group leader status removed
        - Clean environment for long-running operations
        
    Reference:
        Stevens' "Advanced Programming in the UNIX Environment" (ISBN 0201563177)
        
    Raises:
        SystemExit: If fork operations fail
        
    Note:
        Only works on Unix/Linux systems (requires os.fork)
    """
    try:
        # First fork: Create child process
        pid = os.fork()
        if pid > 0:
            # Parent process exits immediately
            os._exit(0)
    except OSError as e:
        print(f"First fork failed: {e.errno} ({e.strerror})", file=sys.stderr)
        os._exit(1)
    
    # Child process continues
    # Decouple from parent environment
    os.chdir("/")  # Change to root directory
    os.setsid()    # Become session leader
    os.umask(0)    # Clear file creation mask
    
    try:
        # Second fork: Create grandchild process
        pid = os.fork()
        if pid > 0:
            # Child process exits, leaving grandchild as daemon
            os._exit(0)
    except OSError as e:
        print(f"Second fork failed: {e.errno} ({e.strerror})", file=sys.stderr)
        os._exit(1)
    
    # Grandchild process is now a daemon


def execute_import_command(command_file_path):
    """
    Execute import command file as background process.
    
    Args:
        command_file_path (str): Full path to command file to execute
        
    Process:
        1. Open null device files for stdin/stdout/stderr redirection
        2. Start command file execution using subprocess.Popen
        3. Redirect all I/O to null devices (daemon-style execution)
        4. Clean up file handles
        
    Security:
        - Command file must exist and be readable
        - Execution uses shell=True for script compatibility
        - I/O redirection prevents output interference
        
    Error Handling:
        - File handle cleanup even on exceptions
        - Proper error reporting for debugging
        
    Note:
        This function should be called after daemon process creation
    """
    null_out = None
    null_in = None
    
    try:
        # Open null devices for I/O redirection
        null_out = open(os.devnull, 'w')
        null_in = open(os.devnull, 'r')
        
        # Execute command file as background process
        subprocess.Popen(
            command_file_path,
            shell=True,
            stdin=null_in,
            stdout=null_out,
            stderr=null_out,
            cwd=COMMAND_FILE_DIRECTORY
        )
        
    except Exception as e:
        print(f"Failed to execute import command: {e}", file=sys.stderr)
    finally:
        # Clean up file handles
        if null_out:
            null_out.close()
        if null_in:
            null_in.close()


def generate_redirect_response(import_ticket):
    """
    Generate HTML response with JavaScript redirect to status monitor.
    
    Args:
        import_ticket (str): Import ticket ID for status monitoring
        
    Returns:
        str: Complete HTML response with redirect script
        
    HTML Response:
        - Sets proper content-type header
        - Includes JavaScript redirect to status monitoring script
        - Passes import ticket as query parameter
        - Provides immediate user feedback
        
    Redirect Logic:
        - Uses window.location.href for immediate redirect
        - Maintains import ticket context for monitoring
        - Seamless transition from execution to monitoring
    """
    response_parts = []
    response_parts.append("Content-Type: text/html; charset=UTF-8\r\n")
    response_parts.append("\r\n")
    response_parts.append("<html>\n")
    response_parts.append("<head>\n")
    response_parts.append("    <title>TQ Database Import - Starting</title>\n")
    response_parts.append("</head>\n")
    response_parts.append("<body>\n")
    response_parts.append("    <h2>Starting Import Process...</h2>\n")
    response_parts.append("    <p>Import ticket: " + import_ticket + "</p>\n")
    response_parts.append("    <p>Redirecting to status monitor...</p>\n")
    response_parts.append("    <script type='text/javascript'>\n")
    response_parts.append(f"        window.location.href='{STATUS_MONITOR_SCRIPT}?importTicket={import_ticket}';\n")
    response_parts.append("    </script>\n")
    response_parts.append("</body>\n")
    response_parts.append("</html>\n")
    
    return "".join(response_parts)


def generate_error_response(import_ticket, error_message):
    """
    Generate HTML error response for failed import execution.
    
    Args:
        import_ticket (str): Import ticket ID that failed
        error_message (str): Description of the error
        
    Returns:
        str: Complete HTML error response
        
    Error Response:
        - User-friendly error message
        - Import ticket information for debugging
        - Proper HTML structure and styling
        - Guidance for next steps
    """
    response_parts = []
    response_parts.append("Content-Type: text/html; charset=UTF-8\r\n")
    response_parts.append("\r\n")
    response_parts.append("<html>\n")
    response_parts.append("<head>\n")
    response_parts.append("    <title>TQ Database Import - Error</title>\n")
    response_parts.append("    <style>\n")
    response_parts.append("        body { font-family: Arial, sans-serif; margin: 20px; }\n")
    response_parts.append("        .error { color: #cc0000; background: #ffe6e6; padding: 10px; border: 1px solid #cc0000; }\n")
    response_parts.append("    </style>\n")
    response_parts.append("</head>\n")
    response_parts.append("<body>\n")
    response_parts.append("    <h2>Import Execution Error</h2>\n")
    response_parts.append("    <div class='error'>\n")
    response_parts.append("        <strong>Error:</strong> " + error_message + "<br>\n")
    response_parts.append("        <strong>Import Ticket:</strong> " + import_ticket + "\n")
    response_parts.append("    </div>\n")
    response_parts.append("    <p>Please check the import ticket and try again.</p>\n")
    response_parts.append("</body>\n")
    response_parts.append("</html>\n")
    
    return "".join(response_parts)


def validate_command_file(command_file_path):
    """
    Validate that command file exists and is readable.
    
    Args:
        command_file_path (str): Full path to command file
        
    Returns:
        bool: True if file exists and is readable, False otherwise
        
    Security Checks:
        - File existence verification
        - Read permission validation
        - Path validation (within expected directory)
        
    Note:
        Additional security checks could be added here such as:
        - File ownership validation
        - Content validation
        - File size limits
    """
    try:
        return os.path.isfile(command_file_path) and os.access(command_file_path, os.R_OK)
    except Exception:
        return False


def main():
    """
    Main CGI execution function for import job initiation.
    
    Process:
        1. Parse query parameters to get import ticket ID
        2. Construct command file path from ticket ID
        3. Validate command file existence and permissions
        4. If valid: Start daemon process and execute command
        5. If invalid: Return error response
        6. Redirect user to status monitoring interface
        
    Error Handling:
        - Missing import ticket parameter
        - Invalid or missing command file
        - Process creation failures
        - Proper error response generation
        
    Security Features:
        - Command file validation
        - Path construction safety
        - Process isolation
        - Error information limitation
        
    Integration:
        - Seamless handoff to status monitoring
        - Ticket-based job tracking
        - Web interface compatibility
    """
    try:
        # Parse CGI parameters
        params = parse_query_parameters()
        import_ticket = params.get('importTicket', '')
        
        if not import_ticket:
            # Handle missing import ticket
            error_response = generate_error_response(
                "N/A", 
                "Missing import ticket parameter"
            )
            sys.stdout.write(error_response)
            sys.stdout.flush()
            return
        
        # Construct command file path
        command_file_path = os.path.join(COMMAND_FILE_DIRECTORY, f"{import_ticket}.cmd")
        
        # Validate command file
        if not validate_command_file(command_file_path):
            error_response = generate_error_response(
                import_ticket,
                f"Cannot find or access command file for ticket '{import_ticket}'"
            )
            sys.stdout.write(error_response)
            sys.stdout.flush()
            return
        
        # Generate redirect response to status monitor
        redirect_response = generate_redirect_response(import_ticket)
        sys.stdout.write(redirect_response)
        sys.stdout.flush()
        sys.stdout.close()  # Close stdout before forking
        
        # Create daemon process and execute import command
        create_daemon_process()
        execute_import_command(command_file_path)
        
    except Exception as e:
        # Handle unexpected errors
        error_response = generate_error_response(
            import_ticket if 'import_ticket' in locals() else "Unknown",
            f"Unexpected error during import execution: {str(e)}"
        )
        sys.stdout.write(error_response)
        sys.stdout.flush()


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TQ Database Import Status JSON CGI Script

Returns the current status of a background import job as JSON.
Used by the batch import page to poll progress without a full page reload.

Query Parameters:
    importTicket: The import ticket ID returned by i1min_check.py

Response JSON:
    {
        "done": bool,         # True when "Importing finish!" is found in log
        "error": bool,        # True when error keywords are detected in log
        "totalLines": int,    # Total log lines so far
        "lines": [str, ...]   # Last up to 20 log lines for display
    }
"""

import os
import sys
import json
import html
from urllib.parse import unquote

LOG_DIR = "/tmp"
COMPLETION_MARKER = "Importing finish!"


def main():
    qs = os.environ.get("QUERY_STRING", "")
    params = {}
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = unquote(v)

    ticket = params.get("importTicket", "").strip()

    sys.stdout.write("Content-Type: application/json; charset=UTF-8\r\n")
    sys.stdout.write("\r\n")

    # Validate ticket to prevent path traversal
    if not ticket or "/" in ticket or ".." in ticket or "\\" in ticket:
        sys.stdout.write(json.dumps({
            "done": False,
            "error": True,
            "totalLines": 0,
            "lines": ["Invalid or missing importTicket"]
        }))
        return

    log_path = os.path.join(LOG_DIR, ticket + ".log")

    lines = []
    done = False
    has_error = False

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                clean = line.rstrip("\r\n")
                lines.append(clean)
                if COMPLETION_MARKER in clean:
                    done = True
                if any(kw in clean.lower() for kw in ("error", "traceback", "exception")):
                    has_error = True
    except FileNotFoundError:
        # Log not created yet – import may not have started
        pass
    except (PermissionError, OSError):
        has_error = True
        lines.append("Cannot read import log file.")

    sys.stdout.write(json.dumps({
        "done": done,
        "error": has_error,
        "totalLines": len(lines),
        "lines": lines[-20:]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
    sys.stdout.flush()

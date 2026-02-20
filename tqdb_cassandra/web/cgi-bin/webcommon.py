#!/usr/bin/python
import time
import sys
import time
import datetime
import os
import urllib

# Import endpoint logger for usage tracking
try:
    from endpoint_logger import log_endpoint_access
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False


def log_request(extra_data=None):
    """
    Log endpoint access for usage tracking.
    Safe to call - will not break if logging fails.
    
    Args:
        extra_data (dict, optional): Additional data to log
    """
    if LOGGER_AVAILABLE:
        try:
            log_endpoint_access(extra_data)
        except Exception:
            # Never let logging break the application
            pass


def getQueryStringDict(querystrings):
    mapQS = {}
    for qs in querystrings.split("&"):
        if qs.find("=") <= 0:
            continue
        mapQS[qs.split("=")[0]] = urllib.unquote(qs.split("=")[1])
    return mapQS

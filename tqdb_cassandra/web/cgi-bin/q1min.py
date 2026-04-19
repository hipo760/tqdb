#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""TQ Database minute-level data query CGI script.

Regular symbols are queried through existing toolchain.
Continuous symbols (TXDT/TXON) are composed on demand from underlying
TAIFEX monthly contracts, behaving like SQL views.
"""

import datetime
import gzip
import json
import os
import subprocess
import sys
import time
from urllib.parse import quote, unquote
from urllib.request import urlopen

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

from continuous_symbols import (
    compose_continuous_minbars,
    is_continuous_symbol,
    load_holiday_dates,
    normalize_symbol,
)


# Global configuration constants
BIN_DIR = os.environ.get("TOOLS_DIR", "/opt/tqdb/tools/")
DEFAULT_SYMBOL = "WTF.506"
DEFAULT_GZIP = 1
DEFAULT_REMOVE_FILE = 1
DEFAULT_BEGIN_DT = "2030-5-23 11:45:00"
DEFAULT_END_DT = "2030-5-23 21:46:00"
FILE_TYPE_GZIP = 0
FILE_TYPE_CSV = 1


def get_first_valid_datetime(symbol, begin_dt_str, end_dt_str):
    """Retrieve first valid datetime for regular symbols."""
    try:
        target_type = "MinBar"
        begin_ref_dt, end_ref_dt = (-1, -1)

        url = (
            "http://localhost/cgi-bin/qSymRefPrc.py?symbol="
            f"{quote(symbol)}&qType=LastValidPrc&qDatetime={quote(begin_dt_str)}"
        )
        with urlopen(url) as response:
            obj = json.loads(response.read().decode("utf-8"))

        if obj is not None and target_type in obj and obj[target_type][0] is not None:
            begin_ref_dt = obj[target_type][0]["datetime"]

        url = (
            "http://localhost/cgi-bin/qSymRefPrc.py?symbol="
            f"{quote(symbol)}&qType=LastValidPrc&qDatetime={quote(end_dt_str)}"
        )
        with urlopen(url) as response:
            obj = json.loads(response.read().decode("utf-8"))

        if obj is not None and target_type in obj and obj[target_type][0] is not None:
            end_ref_dt = obj[target_type][0]["datetime"]

        if begin_ref_dt != -1 and begin_ref_dt == end_ref_dt:
            begin_ref_dt_obj = datetime.datetime.strptime(begin_ref_dt, "%Y-%m-%d %H:%M:%S")
            begin_ref_dt_epoch = (begin_ref_dt_obj - datetime.datetime(1970, 1, 1)).total_seconds()
            dt_first_valid = datetime.datetime.fromtimestamp(begin_ref_dt_epoch)
            begin_dt_str = dt_first_valid.strftime("%Y-%m-%d %H:%M:%S")

        return begin_dt_str

    except Exception as exc:
        print(f"Warning: Date validation failed: {exc}", file=sys.stderr)
        return begin_dt_str


def download_from_tqdb(symbol, begin_dt, end_dt, tmp_file, gzip_enabled):
    """Download minute-level data from TQ Database existing script."""
    try:
        cassandra_host = os.environ.get("CASSANDRA_HOST", "cassandra-node")
        cassandra_port = os.environ.get("CASSANDRA_PORT", "9042")
        cassandra_keyspace = os.environ.get("CASSANDRA_KEYSPACE", "tqdb1")

        scripts_dir = os.path.join(BIN_DIR, "scripts")
        cmd = (
            f"python3 {scripts_dir}/q1minall.py {cassandra_host} {cassandra_port} "
            f"{cassandra_keyspace} '{symbol}' '{begin_dt}' '{end_dt}' '{tmp_file}' '{gzip_enabled}'"
        )

        subprocess.run(cmd, shell=True, check=True, timeout=300)

    except subprocess.TimeoutExpired:
        raise Exception("TQ Database query timeout (5 minutes)")
    except subprocess.CalledProcessError as exc:
        raise Exception(f"TQ Database query failed: {exc}")
    except Exception as exc:
        raise Exception(f"Download error: {exc}")


def process_custom_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled):
    """Process multi-leg custom symbols (^^ prefix) via legacy flow."""
    try:
        profile = f"profile.ml.{symbol[2:]}"
        cmd = f"python ./q1min_multileg.py '{profile}' '{begin_dt}' '{end_dt}' '{tmp_file}' '{gzip_enabled}'"
        custom_dir = f"{BIN_DIR}/../../tqdbPlus/"
        subprocess.run(cmd, shell=True, cwd=custom_dir, check=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise Exception("Custom symbol processing timeout (5 minutes)")
    except subprocess.CalledProcessError as exc:
        raise Exception(f"Custom symbol processing failed: {exc}")
    except Exception as exc:
        raise Exception(f"Custom symbol error: {exc}")


def _format_minute_bar(dt, open_val, high_val, low_val, close_val, volume):
    date_str = dt.strftime("%Y%m%d")
    time_str = dt.strftime("%H%M%S")
    return f"{date_str},{time_str},{open_val},{high_val},{low_val},{close_val},{volume}"


def write_bars_to_tmp_file(bars, tmp_file, gzip_enabled):
    """Write composed bars to temp file matching q1minall output format."""
    if gzip_enabled == 1:
        with gzip.open(f"{tmp_file}.gz", "wt", encoding="utf-8") as fp:
            for bar in bars:
                fp.write(_format_minute_bar(*bar) + "\n")
    else:
        with open(tmp_file, "w", encoding="utf-8") as fp:
            for bar in bars:
                fp.write(_format_minute_bar(*bar) + "\n")


def process_continuous_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled):
    """Compose TXON/TXDT minute bars on read (view-like)."""
    cassandra_host = os.environ.get("CASSANDRA_HOST", "cassandra-node")
    cassandra_port = int(os.environ.get("CASSANDRA_PORT", "9042"))
    cassandra_keyspace = os.environ.get("CASSANDRA_KEYSPACE", "tqdb1")
    cassandra_user = os.environ.get("CASSANDRA_USER", "")
    cassandra_password = os.environ.get("CASSANDRA_PASSWORD", "")

    auth_provider = None
    if cassandra_user and cassandra_password:
        auth_provider = PlainTextAuthProvider(username=cassandra_user, password=cassandra_password)

    begin_dt_obj = datetime.datetime.strptime(begin_dt, "%Y-%m-%d %H:%M:%S")
    end_dt_obj = datetime.datetime.strptime(end_dt, "%Y-%m-%d %H:%M:%S")

    cluster = Cluster([cassandra_host], port=cassandra_port, auth_provider=auth_provider)
    session = cluster.connect(cassandra_keyspace)
    session.default_timeout = 120

    try:
        holidays = load_holiday_dates()
        bars = compose_continuous_minbars(
            session=session,
            keyspace=cassandra_keyspace,
            symbol=symbol,
            begin_dt=begin_dt_obj,
            end_dt=end_dt_obj,
            holidays=holidays,
        )
        write_bars_to_tmp_file(bars, tmp_file, gzip_enabled)
    finally:
        cluster.shutdown()


def output_response_data(tmp_file, symbol, file_type, gzip_enabled, remove_file):
    """Output generated data file as HTTP response."""
    try:
        actual_file = f"{tmp_file}.gz" if gzip_enabled == 1 else tmp_file

        if gzip_enabled == 1:
            file_size = os.path.getsize(actual_file)
            sys.stdout.write(f"Content-Length: {file_size}\r\n")
            sys.stdout.write("Content-Encoding: gzip\r\n")

        if file_type == FILE_TYPE_GZIP:
            sys.stdout.write("Content-Type: text/plain\r\n")
        else:
            sys.stdout.write("Content-Type: text/csv\r\n")
            sys.stdout.write(f"Content-Disposition: attachment; filename=\"{symbol}.1min.csv\"\r\n")

        sys.stdout.write("\r\n")
        sys.stdout.flush()

        if file_type == FILE_TYPE_CSV and gzip_enabled == 0:
            sys.stdout.write("YYYYMMDD,HHMMSS,Open,High,Low,Close,Vol\r\n")
            sys.stdout.flush()

        with open(actual_file, "rb") as fp:
            sys.stdout.buffer.write(fp.read())

        sys.stdout.buffer.flush()

        if remove_file == 1:
            if os.path.exists(actual_file):
                os.remove(actual_file)
            if gzip_enabled == 1 and os.path.exists(tmp_file):
                os.remove(tmp_file)

    except Exception as exc:
        sys.stdout.write("Content-Type: text/plain\r\n\r\n")
        sys.stdout.write(f"Error outputting data: {exc}\r\n")
        sys.stdout.flush()


def parse_query_parameters():
    query_string = os.environ.get("QUERY_STRING", "NA=NA")
    params = {}

    for qs in query_string.split("&"):
        if qs.find("=") <= 0:
            continue
        key, value = qs.split("=", 1)
        params[key] = unquote(value)

    return params


def normalize_date_format(date_str):
    """Normalize date string into YYYY-MM-DD HH:MM:SS where possible."""
    try:
        if date_str.count("-") == 2:
            parts = date_str.split()
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            year, month, day = date_part.split("-")
            return f"{year}-{month.zfill(2)}-{day.zfill(2)} {time_part}"
        return date_str
    except Exception as exc:
        print(f"Warning: Date normalization failed: {exc}", file=sys.stderr)
        return date_str


def main():
    symbol = DEFAULT_SYMBOL
    gzip_enabled = DEFAULT_GZIP
    remove_file = DEFAULT_REMOVE_FILE
    begin_dt = DEFAULT_BEGIN_DT
    end_dt = DEFAULT_END_DT
    file_type = FILE_TYPE_GZIP

    try:
        params = parse_query_parameters()

        if "symbol" in params:
            symbol = normalize_symbol(params["symbol"])
        if "BEG" in params:
            begin_dt = normalize_date_format(params["BEG"])
        if "END" in params:
            end_dt = normalize_date_format(params["END"])
        if "csv" in params and params["csv"] == "1":
            file_type = FILE_TYPE_CSV
            gzip_enabled = 0

        is_custom_symbol = symbol.startswith("^^")
        is_cont_symbol = is_continuous_symbol(symbol)

        if not is_custom_symbol and not is_cont_symbol:
            if ("MOSTHAVEBEG" in params and params["MOSTHAVEBEG"] != "0") or (
                "MUSTHAVEBEG" in params and params["MUSTHAVEBEG"] != "0"
            ):
                begin_dt = get_first_valid_datetime(symbol, begin_dt, end_dt)

        tmp_file = f"/tmp/q1min.{os.getpid()}.{int(time.mktime(datetime.datetime.now().timetuple()))}"

        if is_custom_symbol:
            process_custom_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled)
        elif is_cont_symbol:
            process_continuous_symbol(symbol, begin_dt, end_dt, tmp_file, gzip_enabled)
        else:
            download_from_tqdb(symbol, begin_dt, end_dt, tmp_file, gzip_enabled)

        output_response_data(tmp_file, symbol, file_type, gzip_enabled, remove_file)

    except Exception as exc:
        sys.stdout.write("Content-Type: text/plain\r\n\r\n")
        sys.stdout.write(f"Error processing request: {exc}\r\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

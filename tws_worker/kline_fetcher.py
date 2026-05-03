#!/usr/bin/env python3
"""
TWS Worker — kbar fetcher
==========================
Connects to IBKR TWS / IB Gateway and fetches 1-min historical bars
for one or more futures contracts.

Modes
-----
Continuous (default):
    Every <interval_seconds> fetches the most recent <duration> of bars
    for all configured contracts.  Runs until interrupted (Ctrl-C / SIGTERM).

One-shot:
    When config.fetch.start_time AND config.fetch.end_time are both set,
    fetches that exact time window for all contracts once, then exits.

All contract requests within a cycle are fired in parallel; total wait
time is bounded by the slowest response, not the sum of all responses.

Config
------
Reads from CONFIG_PATH env-var (default: /config/config.yaml).
"""

import logging
import os
import signal
import sys
import threading
from datetime import datetime, timezone

import yaml
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

# ── logging setup (adjusted later from config) ────────────────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("tws_worker")

# TWS informational error codes that are not real errors
_INFO_CODES = {2104, 2106, 2107, 2108, 2119, 2158}


# ── App (EWrapper + EClient) ──────────────────────────────────────────────────

class TWSApp(EWrapper, EClient):
    """Thin ibapi wrapper that exposes a synchronous fetch_kbars() method."""

    def __init__(self) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self._connected = threading.Event()
        self._lock = threading.Lock()
        # reqId -> {"bars": list, "event": Event, "error": str|None}
        self._pending: dict[int, dict] = {}
        self._next_id = 1

    # ── EWrapper callbacks ────────────────────────────────────────────────────

    def nextValidId(self, orderId: int) -> None:
        logger.info("Connected to TWS (nextValidId=%d)", orderId)
        self._connected.set()

    def historicalData(self, reqId: int, bar) -> None:
        with self._lock:
            req = self._pending.get(reqId)
            if req is not None:
                req["bars"].append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        logger.debug("historicalDataEnd reqId=%d start=%s end=%s", reqId, start, end)
        with self._lock:
            req = self._pending.get(reqId)
            if req is not None:
                req["event"].set()

    def error(
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        if errorCode in _INFO_CODES:
            logger.debug("TWS info [%d]: %s", errorCode, errorString)
            return
        if reqId == -1:
            logger.warning("TWS system [%d]: %s", errorCode, errorString)
            return
        logger.error("TWS error reqId=%d [%d]: %s", reqId, errorCode, errorString)
        with self._lock:
            req = self._pending.get(reqId)
            if req is not None:
                req["error"] = f"[{errorCode}] {errorString}"
                req["event"].set()

    # ── Public API ────────────────────────────────────────────────────────────

    def wait_until_connected(self, timeout: float = 30) -> bool:
        return self._connected.wait(timeout=timeout)

    def fetch_kbars_multi(
        self,
        contracts: list[Contract],
        end_datetime: str,
        duration: str,
        bar_size: str,
        what_to_show: str,
        use_rth: int,
        timeout: int = 60,
    ) -> list[tuple[Contract, list]]:
        """
        Fire historical-data requests for all contracts simultaneously,
        then wait for each response.  Total wall-clock time ≈ slowest response.

        Returns a list of (Contract, bars) pairs in the same order as input.
        """
        # 1. Fire all requests
        rids: list[tuple[int, Contract]] = []
        for contract in contracts:
            rid = self._alloc_req()
            self.reqHistoricalData(
                rid,
                contract,
                end_datetime,
                duration,
                bar_size,
                what_to_show,
                use_rth,
                1,      # formatDate=1 → "YYYYMMDD  HH:mm:ss"
                False,  # keepUpToDate=False → one-shot
                [],     # chartOptions
            )
            rids.append((rid, contract))

        # 2. Wait for each response (events are set by callbacks)
        results: list[tuple[Contract, list]] = []
        for rid, contract in rids:
            with self._lock:
                event = self._pending[rid]["event"]
            completed = event.wait(timeout=timeout)
            req = self._pop_req(rid)
            if not completed:
                logger.warning("reqId=%d (%s) timed out after %ds", rid, contract.symbol, timeout)
            if req["error"]:
                logger.error("reqId=%d (%s) error: %s", rid, contract.symbol, req["error"])
            results.append((contract, req["bars"]))

        return results

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _alloc_req(self) -> int:
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            self._pending[rid] = {
                "bars": [],
                "event": threading.Event(),
                "error": None,
            }
        return rid

    def _pop_req(self, rid: int) -> dict:
        with self._lock:
            return self._pending.pop(rid, {"bars": [], "error": None})


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_contract(cfg: dict) -> Contract:
    c = Contract()
    c.symbol = cfg["symbol"]
    c.secType = cfg["sec_type"]
    c.exchange = cfg["exchange"]
    c.currency = cfg["currency"]
    c.lastTradeDateOrContractMonth = cfg.get("last_trade_date", "")
    return c


def compute_end_and_duration(fetch_cfg: dict) -> tuple[str, str]:
    """
    Returns (endDateTime, durationStr) for reqHistoricalData.
    - If end_time is set: use it as endDateTime.
    - If both start_time and end_time are set: compute duration between them.
    - Otherwise: endDateTime="" (TWS uses now) with configured duration.
    """
    start_str: str = fetch_cfg.get("start_time", "").strip()
    end_str: str = fetch_cfg.get("end_time", "").strip()

    if end_str and start_str:
        fmt = "%Y%m%d %H:%M:%S"
        start_dt = datetime.strptime(start_str, fmt)
        end_dt = datetime.strptime(end_str, fmt)
        delta_secs = int((end_dt - start_dt).total_seconds())
        if delta_secs <= 0:
            raise ValueError(f"start_time must be before end_time: {start_str} >= {end_str}")
        return end_str, f"{delta_secs} S"

    if end_str:
        return end_str, fetch_cfg["duration"]

    return "", fetch_cfg["duration"]


def print_bars(bars: list, contract: Contract) -> None:
    if not bars:
        logger.warning("No bars returned for %s", contract.symbol)
        return

    logger.info(
        "Received %d bar(s) for %s [%s %s]",
        len(bars),
        contract.symbol,
        contract.exchange,
        contract.lastTradeDateOrContractMonth,
    )
    print(f"{'Date/Time':<25} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>12}")
    print("-" * 80)
    for bar in bars:
        print(
            f"{bar.date:<25} {bar.open:>10.4f} {bar.high:>10.4f} "
            f"{bar.low:>10.4f} {bar.close:>10.4f} {bar.volume!s:>12}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    config_path = os.environ.get("CONFIG_PATH", "/config/config.yaml")
    cfg = load_config(config_path)

    # Configure logging level from config
    log_level = cfg.get("logging", {}).get("level", "INFO").upper()
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)

    tws_cfg = cfg["tws"]
    contracts = [build_contract(c) for c in cfg["contracts"]]
    if not contracts:
        logger.error("No contracts defined in config — add at least one entry under 'contracts:'")
        sys.exit(1)
    fetch_cfg = cfg["fetch"]

    start_str: str = fetch_cfg.get("start_time", "").strip()
    end_str: str = fetch_cfg.get("end_time", "").strip()
    one_shot = bool(start_str and end_str)

    app = TWSApp()

    # Graceful shutdown on SIGTERM (Docker stop)
    stop_event = threading.Event()

    def _handle_signal(signum, frame):
        logger.info("Received signal %d, shutting down…", signum)
        stop_event.set()
        app.disconnect()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Connecting to TWS at %s:%d (clientId=%d)…",
        tws_cfg["host"],
        tws_cfg["port"],
        tws_cfg["client_id"],
    )
    app.connect(tws_cfg["host"], tws_cfg["port"], tws_cfg["client_id"])

    # EClient.run() is blocking; run it in a daemon thread
    reader_thread = threading.Thread(target=app.run, daemon=True, name="tws-reader")
    reader_thread.start()

    if not app.wait_until_connected(timeout=30):
        logger.error("Timed out waiting for TWS connection — check host/port/clientId")
        app.disconnect()
        sys.exit(1)

    symbols = ", ".join(
        f"{c.symbol} {c.lastTradeDateOrContractMonth or ''}" for c in contracts
    ).strip()
    mode_desc = (
        f"one-shot from {start_str} to {end_str}"
        if one_shot
        else f"continuous every {fetch_cfg['interval_seconds']}s"
    )
    logger.info("Starting %s | contracts: [%s]", mode_desc, symbols)

    def do_fetch() -> None:
        end_dt, duration = compute_end_and_duration(fetch_cfg)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(
            "[%s] Fetching %s bars (%s) for %d contract(s)…",
            ts, fetch_cfg["bar_size"], duration, len(contracts),
        )
        results = app.fetch_kbars_multi(
            contracts=contracts,
            end_datetime=end_dt,
            duration=duration,
            bar_size=fetch_cfg["bar_size"],
            what_to_show=fetch_cfg["what_to_show"],
            use_rth=fetch_cfg["use_rth"],
            timeout=fetch_cfg.get("request_timeout", 60),
        )
        for contract, bars in results:
            print_bars(bars, contract)

    if one_shot:
        do_fetch()
        app.disconnect()
    else:
        interval = fetch_cfg["interval_seconds"]
        while not stop_event.is_set():
            do_fetch()
            stop_event.wait(timeout=interval)

    logger.info("Worker stopped.")


if __name__ == "__main__":
    main()

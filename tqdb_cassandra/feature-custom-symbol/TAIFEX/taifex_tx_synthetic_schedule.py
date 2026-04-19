"""Generate TAIFEX synthetic futures roll schedule (TXDT/TXON) from holiday calendar only.

This standalone version uses only calendar logic:
- Last trading day is estimated from contract month third Wednesday.
- If third Wednesday is a weekend/holiday, it is adjusted forward.

Contract range rule:
- If today is in year Y, include contracts from (Y-1)-01 to Y-12.

All output timestamps are normalized to UTC+0 for quote-data alignment.
Session boundaries are defined in Taiwan time and converted to UTC.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_HOLIDAY_CSV = "docs/taifex_holidays_sample.csv"  # exchange-prefixed holiday file
DEFAULT_OUTPUT = "logs/taifex_tx_synthetic_schedule.json"
TC_PREFIX = "TC.F.TWF.FITX"
BROKER_PREFIX = "TXF"
MONTH_CODES = "ABCDEFGHIJKL"
YMD_RE = re.compile(r"^(\d{8})$")
TW_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc


@dataclass(frozen=True)
class ContractInfo:
	tc_symbol: str
	taifex_symbol: str
	contract_month: str
	last_trading_day: date


@dataclass(frozen=True)
class ContractWindow:
	start: date
	end: date


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate TXDT/TXON switching schedule for TAIFEX FITX (holiday-only mode).",
	)
	parser.add_argument(
		"--holiday-csv",
		default=DEFAULT_HOLIDAY_CSV,
		help=(
			"Holiday CSV file used for third-Wednesday adjustment to next trading day. "
			"Supported date formats: YYYYMMDD, YYYY-MM-DD, YYYY/MM/DD"
		),
	)
	parser.add_argument(
		"--output",
		default=DEFAULT_OUTPUT,
		help="Output JSON file path",
	)
	return parser.parse_args()


def parse_yyyymmdd(text: str) -> date | None:
	if not YMD_RE.match(text):
		return None
	try:
		return datetime.strptime(text, "%Y%m%d").date()
	except ValueError:
		return None


def parse_date_flexible(text: str) -> date | None:
	value = text.strip()
	if not value:
		return None
	parsed = parse_yyyymmdd(value)
	if parsed is not None:
		return parsed
	for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
		try:
			return datetime.strptime(value, fmt).date()
		except ValueError:
			continue
	return None


def load_holiday_dates(csv_path: str) -> set[date]:
	path = Path(csv_path)
	if not path.exists():
		raise FileNotFoundError(f"Holiday CSV not found: {path}")

	content = path.read_text(encoding="utf-8").splitlines()
	holiday_dates: set[date] = set()
	for line in content:
		row = line.strip()
		if not row or row.startswith("#"):
			continue
		parts = [p.strip() for p in row.split(",")]
		for part in parts:
			parsed = parse_date_flexible(part)
			if parsed is not None:
				holiday_dates.add(parsed)
				break
	return holiday_dates


def _third_weekday_of_month(year: int, month: int, weekday: int) -> date:
	# weekday: Monday=0 ... Sunday=6
	first = date(year, month, 1)
	delta = (weekday - first.weekday()) % 7
	first_target = first + timedelta(days=delta)
	return first_target + timedelta(days=14)


def _adjust_to_next_trading_day(candidate: date, holidays: set[date]) -> date:
	day = candidate
	while day.weekday() >= 5 or day in holidays:
		day = day + timedelta(days=1)
	return day


def estimate_last_trading_day(contract_month: str, holidays: set[date]) -> date:
	year = int(contract_month[:4])
	month = int(contract_month[4:6])
	third_wed = _third_weekday_of_month(year, month, 2)
	return _adjust_to_next_trading_day(third_wed, holidays)


def build_contract_months(today: date) -> list[str]:
	start_year = today.year - 1
	end_year = today.year
	months: list[str] = []
	for year in range(start_year, end_year + 1):
		for month in range(1, 13):
			months.append(f"{year}{month:02d}")
	return months


def build_taifex_symbol(contract_month: str) -> str:
	year = int(contract_month[:4])
	month = int(contract_month[4:6])
	month_code = MONTH_CODES[month - 1]
	return f"{BROKER_PREFIX}{month_code}{year % 10}"


def build_contracts(today: date, holidays: set[date]) -> tuple[list[ContractInfo], ContractWindow]:
	contracts: list[ContractInfo] = []
	for contract_month in build_contract_months(today):
		last_day = estimate_last_trading_day(contract_month, holidays)
		contracts.append(
			ContractInfo(
				tc_symbol=f"{TC_PREFIX}.{contract_month}",
				taifex_symbol=build_taifex_symbol(contract_month),
				contract_month=contract_month,
				last_trading_day=last_day,
			)
		)

	window_start = date(today.year - 1, 1, 1)
	window_end = date(today.year, 12, 31)
	filtered = [
		c
		for c in contracts
		if window_start <= c.last_trading_day <= window_end
	]
	filtered.sort(key=lambda c: (c.contract_month, c.last_trading_day))
	return filtered, ContractWindow(start=window_start, end=window_end)


def utc_datetime_from_tw(day: date, hhmm: str) -> str:
	hour = int(hhmm[:2])
	minute = int(hhmm[2:])
	local_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=TW_TZ)
	utc_dt = local_dt.astimezone(UTC_TZ)
	return utc_dt.isoformat(timespec="seconds")


def build_txdt_schedule(contracts: list[ContractInfo], window: ContractWindow) -> dict[str, Any]:
	segments: list[dict[str, str]] = []
	for idx, contract in enumerate(contracts):
		prev = contracts[idx - 1] if idx > 0 else None
		start_day = prev.last_trading_day if prev else window.start
		end_dt_utc = datetime.fromisoformat(utc_datetime_from_tw(contract.last_trading_day, "0845")) - timedelta(minutes=1)
		segments.append(
			{
				"tc_symbol": contract.tc_symbol,
				"taifex_symbol": contract.taifex_symbol,
				"start": utc_datetime_from_tw(start_day, "0845"),
				"end": end_dt_utc.isoformat(timespec="seconds"),
			}
		)

	return {
		"synthetic_symbol": "TXDT",
		"session_local": "08:45-13:45 (UTC+8)",
		"time_basis": "UTC+0 (converted from UTC+8)",
		"segments": segments,
		"overall_start": segments[0]["start"] if segments else None,
		"overall_end": segments[-1]["end"] if segments else None,
	}


def build_txon_schedule(contracts: list[ContractInfo], window: ContractWindow) -> dict[str, Any]:
	segments: list[dict[str, str]] = []
	for idx, contract in enumerate(contracts):
		prev = contracts[idx - 1] if idx > 0 else None
		start_day = prev.last_trading_day if prev else window.start
		segments.append(
			{
				"tc_symbol": contract.tc_symbol,
				"taifex_symbol": contract.taifex_symbol,
				"start": utc_datetime_from_tw(start_day, "1345"),
				"end": utc_datetime_from_tw(contract.last_trading_day, "1345"),
			}
		)

	return {
		"synthetic_symbol": "TXON",
		"sessions_local": [
			"T: 08:45-13:45 (UTC+8)",
			"T to T+1: 08:45-05:00 (UTC+8)",
		],
		"time_basis": "UTC+0 (converted from UTC+8)",
		"segments": segments,
		"overall_start": segments[0]["start"] if segments else None,
		"overall_end": segments[-1]["end"] if segments else None,
		"assumption": "Contract switch point is last trading day 13:45 (UTC+8).",
	}


def build_output(contracts: list[ContractInfo], window: ContractWindow) -> dict[str, Any]:
	return {
		"synthetic": {
			"TXDT": build_txdt_schedule(contracts, window),
			"TXON": build_txon_schedule(contracts, window),
		}
	}


def main() -> None:
	args = parse_args()
	today = date.today()
	holiday_dates = load_holiday_dates(args.holiday_csv)
	contracts, window = build_contracts(today, holiday_dates)
	if not contracts:
		raise RuntimeError("No contracts generated for configured year window.")

	payload = build_output(contracts, window)
	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

	print(f"Wrote schedule JSON: {output_path}")
	print(f"Holiday count: {len(holiday_dates)}")
	print(f"Contracts used: {len(contracts)}")
	print(f"TXDT range: {payload['synthetic']['TXDT']['overall_start']} -> {payload['synthetic']['TXDT']['overall_end']}")
	print(f"TXON range: {payload['synthetic']['TXON']['overall_start']} -> {payload['synthetic']['TXON']['overall_end']}")


if __name__ == "__main__":
	main()

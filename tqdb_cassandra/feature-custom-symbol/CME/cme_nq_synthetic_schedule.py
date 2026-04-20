"""Generate CME synthetic futures roll schedule (NQDT/NQON) from holiday calendar.

Assumptions:
- Last trading day is estimated as contract month third Friday.
- If third Friday is a weekend/holiday, move backward to previous trading day.
- Contract range follows Y-1..Y based on current date.
- NQDT switches at 08:30 America/Chicago.
- NQON switches at 15:15 America/Chicago, with next contract starting at 15:16.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_HOLIDAY_CSV = "cme_holidays_sample.csv"
DEFAULT_OUTPUT = "cme_nq_synthetic_schedule.json"
MONTH_CODES = "FGHJKMNQUVXZ"
NQ_PREFIX = "NQ"
YMD_RE = re.compile(r"^(\d{8})$")
UTC_TZ = timezone.utc
try:
	CHICAGO_TZ = ZoneInfo("America/Chicago")
except Exception:
	CHICAGO_TZ = timezone(timedelta(hours=-6))


@dataclass(frozen=True)
class ContractInfo:
	symbol: str
	contract_month: str
	last_trading_day: date


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate NQDT/NQON switching schedule for CME NQ.",
	)
	parser.add_argument(
		"--holiday-csv",
		default=DEFAULT_HOLIDAY_CSV,
		help="Holiday CSV file. Supported date formats: YYYYMMDD, YYYY-MM-DD, YYYY/MM/DD",
	)
	parser.add_argument(
		"--output",
		default=DEFAULT_OUTPUT,
		help="Output JSON file path",
	)
	return parser.parse_args()


def _parse_yyyymmdd(text: str) -> date | None:
	if not YMD_RE.match(text):
		return None
	try:
		return datetime.strptime(text, "%Y%m%d").date()
	except ValueError:
		return None


def _parse_date_flexible(text: str) -> date | None:
	value = text.strip()
	if not value:
		return None

	parsed = _parse_yyyymmdd(value)
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

	holiday_dates: set[date] = set()
	for line in path.read_text(encoding="utf-8").splitlines():
		row = line.strip()
		if not row or row.startswith("#"):
			continue
		parts = [part.strip() for part in row.split(",")]
		for part in parts:
			parsed = _parse_date_flexible(part)
			if parsed is not None:
				holiday_dates.add(parsed)
				break

	return holiday_dates


def _third_weekday_of_month(year: int, month: int, weekday: int) -> date:
	first = date(year, month, 1)
	delta = (weekday - first.weekday()) % 7
	return first + timedelta(days=delta + 14)


def _adjust_to_prev_trading_day(candidate: date, holidays: set[date]) -> date:
	day = candidate
	while day.weekday() >= 5 or day in holidays:
		day -= timedelta(days=1)
	return day


def estimate_last_trading_day(contract_month: str, holidays: set[date]) -> date:
	year = int(contract_month[:4])
	month = int(contract_month[4:6])
	third_fri = _third_weekday_of_month(year, month, 4)
	return _adjust_to_prev_trading_day(third_fri, holidays)


def _quarter_months(today: date) -> list[str]:
	start_year = today.year - 1
	end_year = today.year
	out: list[str] = []
	for year in range(start_year, end_year + 1):
		for month in (3, 6, 9, 12):
			out.append(f"{year}{month:02d}")
	return out


def _contract_symbol(contract_month: str) -> str:
	year = int(contract_month[:4])
	month = int(contract_month[4:6])
	return f"{NQ_PREFIX}{MONTH_CODES[month - 1]}{year % 10}"


def _utc_from_local(day: date, hhmm: str) -> str:
	hour = int(hhmm[:2])
	minute = int(hhmm[2:])
	local_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=CHICAGO_TZ)
	utc_dt = local_dt.astimezone(UTC_TZ)
	return utc_dt.isoformat(timespec="seconds")


def build_contracts(today: date, holidays: set[date]) -> list[ContractInfo]:
	contracts: list[ContractInfo] = []
	for contract_month in _quarter_months(today):
		contracts.append(
			ContractInfo(
				symbol=_contract_symbol(contract_month),
				contract_month=contract_month,
				last_trading_day=estimate_last_trading_day(contract_month, holidays),
			)
		)
	contracts.sort(key=lambda c: c.contract_month)
	return contracts


def build_schedule(today: date, contracts: list[ContractInfo]) -> dict[str, Any]:
	if not contracts:
		return {"NQDT": {"segments": []}, "NQON": {"segments": []}}

	window_start = date(today.year - 1, 1, 1)
	nqdt_segments: list[dict[str, str]] = []
	nqon_segments: list[dict[str, str]] = []

	for idx, contract in enumerate(contracts):
		prev = contracts[idx - 1] if idx > 0 else None
		start_day = prev.last_trading_day if prev else window_start

		nqdt_end = datetime.fromisoformat(_utc_from_local(contract.last_trading_day, "0830")) - timedelta(minutes=1)
		nqdt_segments.append(
			{
				"symbol": contract.symbol,
				"start": _utc_from_local(start_day, "0830"),
				"end": nqdt_end.isoformat(timespec="seconds"),
			}
		)

		nqon_segments.append(
			{
				"symbol": contract.symbol,
				"start": _utc_from_local(start_day, "1516"),
				"end": _utc_from_local(contract.last_trading_day, "1515"),
			}
		)

	return {
		"NQDT": {
			"synthetic_symbol": "NQDT",
			"session_local": "08:30-15:15 (America/Chicago)",
			"time_basis": "UTC+0 (converted from America/Chicago)",
			"segments": nqdt_segments,
			"overall_start": nqdt_segments[0]["start"],
			"overall_end": nqdt_segments[-1]["end"],
		},
		"NQON": {
			"synthetic_symbol": "NQON",
			"session_local": "15:16-15:15 next day (America/Chicago)",
			"time_basis": "UTC+0 (converted from America/Chicago)",
			"segments": nqon_segments,
			"overall_start": nqon_segments[0]["start"],
			"overall_end": nqon_segments[-1]["end"],
		},
	}


def main() -> None:
	args = parse_args()
	today = date.today()
	holidays = load_holiday_dates(args.holiday_csv)
	contracts = build_contracts(today, holidays)
	payload = {
		"today": today.isoformat(),
		"holiday_count": len(holidays),
		"contracts": [
			{
				"symbol": c.symbol,
				"contract_month": c.contract_month,
				"last_trading_day": c.last_trading_day.isoformat(),
			}
			for c in contracts
		],
		"synthetic": build_schedule(today, contracts),
	}

	output_path = Path(args.output)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

	print(f"Wrote schedule JSON: {output_path}")
	print(f"Contracts used: {len(contracts)}")


if __name__ == "__main__":
	main()

"""Symbol list fetching.

Supports two sources:
  - API  (HTTP GET, bearer token optional)
  - File (symbols.json next to this service)

Environment variables:
    SYMBOL_API_URL    HTTP endpoint that returns a JSON array of symbol objects
    SYMBOL_API_TOKEN  Bearer token for the above endpoint (optional)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from http_client import get_json

logger = logging.getLogger(__name__)


def _normalise(items: list[dict]) -> list[dict]:
    """Add derived fields expected by kline_sync (is_mark_price, category)."""
    for item in items:
        item["is_mark_price"] = bool(item.get("is_mark_price", 0))
        margin_type = item.get("margin_type", "").upper()
        item["category"] = (
            "linear" if margin_type == "USDT"
            else "inverse" if margin_type == "COIN"
            else margin_type
        )
    return items


async def fetch_from_api(
    *,
    retries: int = 5,
    timeout_sec: int = 5,
) -> list[dict[str, Any]]:
    url = os.environ.get("SYMBOL_API_URL", "")
    token = os.environ.get("SYMBOL_API_TOKEN", "")

    if not url:
        logger.warning("SYMBOL_API_URL not set — skipping API symbol fetch")
        return []

    try:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            data = await get_json(
                client,
                url,
                headers=headers,
                timeout=timeout_sec,
                retries=retries,
                backoff_factor=1.0,
            )
        return _normalise(data)
    except Exception:
        logger.exception("Failed to fetch symbols from API (%s)", url)
        return []


async def fetch_from_file(path: str = "symbols.json") -> list[dict[str, Any]]:
    try:
        with open(path) as f:
            return _normalise(json.load(f))
    except Exception:
        logger.exception("Failed to load symbols from file (%s)", path)
        return []

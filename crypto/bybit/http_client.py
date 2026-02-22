"""Small shared HTTP client helpers.

This repo standardizes on httpx only.

Contract:
- `get_json(...)` performs an HTTP GET, raises on non-2xx, returns parsed JSON.
- Supports retries with exponential backoff and (optional) API-level validation.

All functions are async and intended to be used with `httpx.AsyncClient`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Mapping, MutableMapping, Optional

import httpx


JsonValidator = Callable[[Any], None]


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float | httpx.Timeout | None = None,
    retries: int = 3,
    backoff_factor: float = 1.0,
    validate_json: Optional[JsonValidator] = None,
) -> Any:
    """GET JSON with retries.

    Raises:
        httpx.HTTPError: network/protocol errors or non-2xx responses (via raise_for_status).
        ValueError/TypeError/etc: if JSON parsing/validation fails.
    """

    if retries < 1:
        raise ValueError("retries must be >= 1")

    last_exc: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if validate_json is not None:
                validate_json(data)
            return data
        except BaseException as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            wait_time = backoff_factor * (2 ** (attempt - 1))
            await asyncio.sleep(wait_time)

    # Should be unreachable, but keeps type-checkers happy.
    assert last_exc is not None
    raise last_exc


def validate_bybit_payload(data: Any) -> None:
    """Raises if a Bybit v5 payload indicates an API-level error."""

    if not isinstance(data, MutableMapping):
        raise TypeError("Expected Bybit response to be a JSON object")

    ret_code = data.get("retCode")
    if ret_code != 0:
        raise RuntimeError(f"Bybit API Error: {data.get('retMsg', 'unknown error')}")

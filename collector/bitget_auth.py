"""Signed, read-only Bitget account metadata: permission type and fee rates.

Only two GET endpoints are permitted. No order, position, leverage, transfer or
withdrawal route exists in this module.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

BASE_URL = "https://api.bitget.com"
AUTH_ALLOWED = frozenset({
    "/api/v3/account/info",
    "/api/v3/account/all-fee-rate",
})
CATEGORY = "USDT-FUTURES"


class AuthError(RuntimeError):
    """Sanitised authentication or permission failure."""


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def credentials() -> tuple[str, str, str]:
    return (
        _first_env("BITGET_API_KEY", "BITGET_KEY"),
        _first_env("BITGET_API_SECRET", "BITGET_SECRET_KEY", "BITGET_SECRET"),
        _first_env(
            "BITGET_API_PASSPHRASE", "BITGET_PASSPHRASE",
            "BITGET_API_PASSWORD", "BITGET_PASSWORD",
        ),
    )


def sign(secret: str, timestamp: str, method: str, path: str, query: str = "") -> str:
    suffix = f"?{query}" if query else ""
    message = f"{timestamp}{method.upper()}{path}{suffix}"
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def auth_headers(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    *,
    key: str | None = None,
    secret: str | None = None,
    passphrase: str | None = None,
    timestamp: str | None = None,
) -> tuple[dict[str, str], str]:
    if method.upper() != "GET":
        raise ValueError("Only GET is permitted for read-only account metadata")
    if path not in AUTH_ALLOWED:
        raise ValueError(f"Path is not allowlisted: {path}")
    if key is None or secret is None or passphrase is None:
        key, secret, passphrase = credentials()
    if not all((key, secret, passphrase)):
        raise RuntimeError("Bitget API credentials are not configured")
    query = urlencode(sorted((params or {}).items()))
    stamp = timestamp or str(int(time.time() * 1000))
    signature = sign(secret, stamp, "GET", path, query)
    return {
        "ACCESS-KEY": key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": stamp,
        "ACCESS-PASSPHRASE": passphrase,
        "locale": "en-US",
        "Content-Type": "application/json",
    }, query


async def _get(
    session: Any,
    path: str,
    headers: dict[str, str],
    query: str,
    *,
    timeout: float = 20.0,
    attempts: int = 3,
    sleep: Any = asyncio.sleep,
) -> dict[str, Any]:
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with session.get(url, params=None, headers=headers, timeout=timeout) as response:
                status = int(getattr(response, "status", 0))
                if status == 429 or status >= 500:
                    raise RuntimeError(f"HTTP {status}")
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}")
                payload = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts:
                await sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))
                continue
            raise RuntimeError(f"AUTH_FAILED: {type(exc).__name__}") from exc
        code = str(payload.get("code", ""))
        if code != "00000":
            raise AuthError(f"Bitget {code}")
        return payload
    raise RuntimeError(f"AUTH_FAILED: {type(last_error).__name__ if last_error else 'unknown'}")


async def load_fee_map(session: Any, *, sleep: Any = asyncio.sleep) -> tuple[dict[str, dict[str, Any]], str]:
    """Return ``(fee_map, status)``. Never returns or logs credentials."""
    key, secret, passphrase = credentials()
    if not all((key, secret, passphrase)):
        return {}, "NOT_CONFIGURED"
    try:
        info_headers, info_query = auth_headers("GET", "/api/v3/account/info")
        info = await _get(session, "/api/v3/account/info", info_headers, info_query, sleep=sleep)
        account = info.get("data", {}) or {}
        permission = account.get("permType", "unknown")

        fee_headers, fee_query = auth_headers(
            "GET", "/api/v3/account/all-fee-rate", {"category": CATEGORY}
        )
        fees = await _get(session, "/api/v3/account/all-fee-rate", fee_headers, fee_query, sleep=sleep)
        data = fees.get("data", [])
        if isinstance(data, dict):
            data = data.get("list", [])
        fee_map = {
            row.get("symbol"): row
            for row in data
            if isinstance(row, dict) and row.get("symbol")
        }
        status = "OK_READ_ONLY_KEY" if permission == "read-only" else f"KEY_PERMISSION_{permission}"
        return fee_map, status
    except AuthError as exc:
        return {}, f"AUTH_FAILED: {exc}"
    except Exception as exc:
        # Deliberately omit headers, signed URLs and passphrases.
        return {}, f"AUTH_FAILED: {type(exc).__name__}"

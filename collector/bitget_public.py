"""Rate-limited, read-only client for Bitget public market endpoints."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

import aiohttp

BASE_URL = "https://api.bitget.com"
ALLOWED_PREFIXES = ("/api/v3/market/",)
DEFAULT_RATE_PER_SEC = 20.0
DEFAULT_BURST = 40
REDUCED_RATE_PER_SEC = 10.0
RATE_LIMIT_TOLERANCE = 0.01


class ForbiddenEndpoint(RuntimeError):
    """Raised when code attempts a non-market or non-GET endpoint."""


class BitgetAPIError(RuntimeError):
    def __init__(self, code: str, message: str, path: str):
        super().__init__(f"Bitget {code} on {path}: {message}")
        self.code = code
        self.message = message
        self.path = path


class _Retryable(RuntimeError):
    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class TokenBucket:
    """Simple async token bucket with injectable clock and sleep for tests."""

    def __init__(
        self,
        rate_per_sec: float = DEFAULT_RATE_PER_SEC,
        burst: int = DEFAULT_BURST,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.rate_per_sec = float(rate_per_sec)
        self.burst = int(burst)
        self._tokens = float(burst)
        self._clock = clock
        self._sleep = sleep
        self._updated = clock()

    def set_rate(self, rate_per_sec: float) -> None:
        self.rate_per_sec = float(rate_per_sec)

    async def acquire(self) -> None:
        while True:
            now = self._clock()
            elapsed = max(0.0, now - self._updated)
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate_per_sec)
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            await self._sleep((1.0 - self._tokens) / self.rate_per_sec)


@dataclass
class ClientStats:
    requests: int = 0
    attempts: int = 0
    retries: int = 0
    errors: int = 0
    rate_limit_events: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    rate_policy: dict[str, Any] = field(default_factory=lambda: {
        "rate_per_sec": DEFAULT_RATE_PER_SEC,
        "burst": DEFAULT_BURST,
        "adapted": False,
        "reason": None,
    })

    def summary(self) -> dict[str, Any]:
        latencies = sorted(self.latencies_ms)
        p95 = latencies[int(0.95 * (len(latencies) - 1))] if latencies else None
        return {
            "requests": self.requests,
            "attempts": self.attempts,
            "retries": self.retries,
            "errors": self.errors,
            "rate_limit_events": self.rate_limit_events,
            "p95_latency_ms": round(p95, 3) if p95 is not None else None,
            "rate_policy": dict(self.rate_policy),
        }


class PublicClient:
    def __init__(
        self,
        session: Any,
        *,
        base_url: str = BASE_URL,
        limiter: TokenBucket | None = None,
        timeout: float = 20.0,
        max_attempts: int = 3,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rand: Callable[[], float] = random.random,
    ):
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.limiter = limiter or TokenBucket()
        self.timeout = timeout
        self.max_attempts = max(1, int(max_attempts))
        self._sleep = sleep
        self._rand = rand
        self.stats = ClientStats()

    def _validate_path(self, path: str) -> None:
        if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            raise ForbiddenEndpoint(f"Public client only allows {ALLOWED_PREFIXES}: {path}")

    def _maybe_adapt(self) -> None:
        policy = self.stats.rate_policy
        if policy["adapted"] or self.stats.attempts < 50:
            return
        ratio = self.stats.rate_limit_events / max(1, self.stats.attempts)
        if ratio > RATE_LIMIT_TOLERANCE:
            self.limiter.set_rate(REDUCED_RATE_PER_SEC)
            policy.update({
                "rate_per_sec": REDUCED_RATE_PER_SEC,
                "adapted": True,
                "reason": f"429 ratio {ratio:.3f} > {RATE_LIMIT_TOLERANCE}",
            })

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._validate_path(path)
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self.stats.attempts += 1
            await self.limiter.acquire()
            started = time.perf_counter()
            try:
                async with self.session.get(url, params=params, timeout=self.timeout) as response:
                    status = int(getattr(response, "status", 0))
                    if status == 429:
                        self.stats.rate_limit_events += 1
                        raise _Retryable("HTTP 429", status)
                    if status >= 500:
                        raise _Retryable(f"HTTP {status}", status)
                    if status >= 400:
                        text = ""
                        try:
                            text = (await response.text())[:200]
                        except Exception:
                            pass
                        raise BitgetAPIError(str(status), text or "request failed", path)
                    payload = await response.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                self.stats.retries += 1
                if attempt >= self.max_attempts:
                    self.stats.errors += 1
                    raise RuntimeError(f"GET {path} failed after {attempt} attempts: {type(exc).__name__}") from exc
                await self._sleep(min(0.5 * (2 ** (attempt - 1)) + self._rand() * 0.1, 4.0))
                continue
            except _Retryable as exc:
                last_error = exc
                self.stats.retries += 1
                if attempt >= self.max_attempts:
                    self.stats.errors += 1
                    raise RuntimeError(f"GET {path} failed after {attempt} attempts: {exc.reason}") from exc
                await self._sleep(min(0.5 * (2 ** (attempt - 1)) + self._rand() * 0.1, 4.0))
                continue
            else:
                self.stats.requests += 1
                self.stats.latencies_ms.append((time.perf_counter() - started) * 1000.0)
                self._maybe_adapt()
                code = str(payload.get("code", ""))
                if code != "00000":
                    raise BitgetAPIError(code, str(payload.get("msg", "")), path)
                return payload
        raise RuntimeError(f"GET {path} failed: {type(last_error).__name__ if last_error else 'unknown'}")

    async def gather(
        self,
        calls: Iterable[tuple[str, dict[str, Any] | None]],
        *,
        concurrency: int = 6,
    ) -> list[dict[str, Any] | Exception]:
        semaphore = asyncio.Semaphore(max(1, concurrency))
        items = list(calls)

        async def run(path: str, params: dict[str, Any] | None):
            async with semaphore:
                try:
                    return await self.get(path, params)
                except Exception as exc:  # returned per call; the cycle decides severity
                    return exc

        return await asyncio.gather(*(run(path, params) for path, params in items))

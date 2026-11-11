from __future__ import annotations

import asyncio
import time

class TokenBucket:
    def __init__(self, rate: float, burst: float | None = None) -> None:
        self.rate = max(rate, 0.1)
        self.capacity = burst if burst else max(1.0, self.rate)
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float = 1.0) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                wait = (n - self.tokens) / self.rate
            await asyncio.sleep(wait)

class ExchangeLimiter:
    def __init__(self, rps: float, scan_fraction: float = 0.7) -> None:
        self.scan = TokenBucket(rps * scan_fraction)
        self.live = TokenBucket(rps * (1.0 - scan_fraction))
        self.blocked_until = 0.0
        self.fail_streak = 0

    @property
    def available(self) -> bool:
        return time.monotonic() >= self.blocked_until

    @property
    def cooldown_left(self) -> float:
        return max(0.0, self.blocked_until - time.monotonic())

    async def acquire(self, priority: str) -> None:
        while True:
            left = self.blocked_until - time.monotonic()
            if left <= 0:
                break
            await asyncio.sleep(min(left, 5.0))
        await (self.live if priority == "live" else self.scan).acquire()

    def on_success(self) -> None:
        self.fail_streak = 0

    def on_rate_limited(self) -> None:
        backoff = min(300.0, 5.0 * 2 ** min(self.fail_streak, 6))
        self.fail_streak += 1
        self.blocked_until = time.monotonic() + backoff

    def on_error(self) -> None:
        self.fail_streak += 1
        if self.fail_streak >= 5:
            self.blocked_until = time.monotonic() + 30.0

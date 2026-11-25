"""Small deterministic test doubles. No network and no real sleeping."""
from __future__ import annotations

from typing import Any, Callable


class FakeResponse:
    def __init__(self, status: int = 200, payload: Any = None, text: str = ""):
        self.status = status
        self.payload = payload if payload is not None else {"code": "00000", "data": []}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return self._text


class FakeSession:
    """Sequential responses. An Exception instance is raised on access."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None, **kwargs):
        self.calls.append((url, params))
        if not self.responses:
            raise AssertionError(f"Unexpected request: {url}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeStats:
    def __init__(self):
        self.requests = 0
        self.retries = 0
        self.errors = 0
        self.rate_limit_events = 0
        self.latencies_ms = []
        self.rate_policy = {"rate_per_sec": 20.0, "burst": 40, "adapted": False, "reason": None}

    def summary(self):
        return {
            "requests": self.requests,
            "retries": self.retries,
            "errors": self.errors,
            "rate_limit_events": self.rate_limit_events,
            "rate_policy": dict(self.rate_policy),
        }


class FakeClient:
    """Route by path. Values may be payloads, Exceptions, or callables(params)."""

    def __init__(self, routes: dict[str, Any], session: Any = None):
        self.routes = routes
        self.session = session
        self.calls = []
        self.stats = FakeStats()

    def _resolve(self, path: str, params: dict[str, Any] | None):
        self.calls.append((path, params))
        self.stats.requests += 1
        category = (params or {}).get("category")
        value = None
        found = False
        for key in ((path, category), path):
            if key in self.routes:
                value = self.routes[key]
                found = True
                break
        if not found:
            return {"code": "00000", "data": []}
        if callable(value):
            return value(params or {})
        return value

    async def get(self, path: str, params: dict[str, Any] | None = None):
        value = self._resolve(path, params)
        if isinstance(value, Exception):
            raise value
        return value

    async def gather(self, calls, concurrency: int = 6):
        results = []
        for path, params in calls:
            try:
                results.append(await self.get(path, params))
            except Exception as exc:
                results.append(exc)
        return results


class FakeClock:
    def __init__(self, start: float = 1_000.0):
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_sleep(clock: FakeClock) -> Callable[[float], Any]:
    async def _sleep(seconds: float) -> None:
        clock.advance(max(0.0, seconds))
    return _sleep

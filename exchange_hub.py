from __future__ import annotations

import asyncio
import logging
import re

import ccxt.async_support as ccxt

from config import (ORDERBOOK_LIMITS, QUOTES, STABLES, Config, credentials)
from models import Venue
from ratelimit import ExchangeLimiter

log = logging.getLogger("hub")
_MULT = re.compile(r"^10{2,}")

def norm_base(base: str) -> str:
    return _MULT.sub("", base)

class ExchangeHub:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.ex: dict[str, ccxt.Exchange] = {}
        self.symbols: dict[str, dict[str, Venue]] = {}
        self.limiters: dict[str, ExchangeLimiter] = {}
        self.exec_key = f"{cfg.exec_exchange}:exec"
        self.exec_map: dict[str, Venue] = {}
        self.last_error: dict[str, str] = {}

    @property
    def scan_ids(self) -> list[str]:
        return list(self.symbols)

    def _limiter(self, eid: str) -> ExchangeLimiter:
        if eid not in self.limiters:
            self.limiters[eid] = ExchangeLimiter(self.cfg.rps.get(eid, 5), self.cfg.scan_budget_fraction)
        return self.limiters[eid]

    @staticmethod
    def _spot_or_linear_map(ex) -> dict[str, Venue]:
        best: dict[str, tuple] = {}
        for sym, m in ex.markets.items():
            if m.get("active") is False:
                continue
            if m.get("spot"):
                kind = 0
            elif m.get("swap") and m.get("linear"):
                kind = 1
            else:
                continue
            quote = m.get("quote")
            if quote not in QUOTES:
                continue
            base = norm_base(m.get("base") or "")
            if not base or base in STABLES:
                continue
            rank = (kind, QUOTES.index(quote))
            cs = float(m.get("contractSize") or 1.0) if kind == 1 else 1.0
            if base not in best or rank < best[base][0]:
                best[base] = (rank, Venue(sym, cs))
        return {b: v for b, (_, v) in best.items()}

    @staticmethod
    def _perp_map(ex) -> dict[str, Venue]:
        best: dict[str, tuple] = {}
        for sym, m in ex.markets.items():
            if m.get("active") is False or not (m.get("swap") and m.get("linear")):
                continue
            quote = m.get("quote")
            if quote not in QUOTES:
                continue
            base = norm_base(m.get("base") or "")
            rank = QUOTES.index(quote)
            if base and base not in STABLES and (base not in best or rank < best[base][0]):
                best[base] = (rank, Venue(sym, float(m.get("contractSize") or 1.0)))
        return {b: v for b, (_, v) in best.items()}

    async def start(self) -> None:
        async def init_scan(eid: str) -> None:
            try:
                inst = getattr(ccxt, eid)({"enableRateLimit": True, "timeout": int(self.cfg.request_timeout_s * 1000)})
                await inst.load_markets()
                self.ex[eid] = inst
                self.symbols[eid] = self._spot_or_linear_map(inst)
                self._limiter(eid)
                log.info("%s ready: %d tradable bases", eid, len(self.symbols[eid]))
            except Exception as e:
                log.warning("%s disabled (init failed): %s", eid, e)
                try:
                    await inst.close()
                except Exception:
                    pass

        await asyncio.gather(*(init_scan(e) for e in self.cfg.exchanges))
        if not self.symbols:
            raise RuntimeError("no exchange could be initialised")

        eid = self.cfg.exec_exchange
        params = {"enableRateLimit": True, "timeout": int(self.cfg.request_timeout_s * 1000),
                  "options": {"defaultType": "swap"}}
        params.update(credentials(eid))
        inst = getattr(ccxt, eid)(params)
        if self.cfg.sandbox:
            inst.set_sandbox_mode(True)
        await inst.load_markets()
        self.ex[self.exec_key] = inst
        self.exec_map = self._perp_map(inst)
        self._limiter(eid)
        log.info("exec exchange %s: %d linear perps", eid, len(self.exec_map))

    async def close(self) -> None:
        await asyncio.gather(*(e.close() for e in self.ex.values()), return_exceptions=True)

    async def call(self, key: str, method: str, *args, priority: str = "scan", **kwargs):
        inst = self.ex.get(key)
        lim = self.limiters.get(key.split(":")[0])
        if inst is None or lim is None:
            return None
        if priority == "scan" and not lim.available:
            return None
        await lim.acquire(priority)
        try:
            res = await asyncio.wait_for(getattr(inst, method)(*args, **kwargs), timeout=self.cfg.request_timeout_s)
            lim.on_success()
            return res
        except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as e:
            lim.on_rate_limited()
            self._err(key, method, e, level=logging.WARNING)
        except (ccxt.NetworkError, asyncio.TimeoutError) as e:
            lim.on_error()
            self._err(key, method, e)
        except ccxt.BaseError as e:
            self._err(key, method, e)
        except Exception as e:
            log.exception("unexpected error %s.%s", key, method)
            self.last_error[key] = repr(e)
        return None

    def _err(self, key: str, method: str, e: Exception, level: int = logging.DEBUG) -> None:
        self.last_error[key] = f"{method}: {type(e).__name__}: {str(e)[:160]}"
        log.log(level, "%s %s", key, self.last_error[key])

    async def book(self, key: str, symbol: str, priority: str = "scan"):
        limit = ORDERBOOK_LIMITS.get(key.split(":")[0], 100)
        if limit is None:
            return await self.call(key, "fetch_order_book", symbol, priority=priority)
        return await self.call(key, "fetch_order_book", symbol, limit, priority=priority)

    async def ohlcv(self, key: str, symbol: str, timeframe: str, limit: int, priority: str = "scan"):
        return await self.call(key, "fetch_ohlcv", symbol, timeframe, None, limit, priority=priority)

    def status(self) -> str:
        cooling = [f"{e}({l.cooldown_left:.0f}s)" for e, l in self.limiters.items() if not l.available]
        return f"{len(self.symbols)} scan venues up" + (f", cooling down: {', '.join(cooling)}" if cooling else "")

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Optional

from config import Config
from models import Coin, CoinImbalance

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("scanner")

def depth_within(book: Optional[dict], pct: float, contract_size: float = 1.0):
    if not book:
        return None
    bids, asks = book.get("bids") or [], book.get("asks") or []
    if not bids or not asks:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2.0
    if mid <= 0:
        return None
    lo, hi = mid * (1 - pct), mid * (1 + pct)
    bid_usd = sum(l[0] * l[1] for l in bids if l[0] >= lo) * contract_size
    ask_usd = sum(l[0] * l[1] for l in asks if l[0] <= hi) * contract_size
    return bid_usd, ask_usd

async def build_universe(hub: "ExchangeHub", cfg: Config) -> list[Coin]:
    ids = hub.scan_ids
    tickers = await asyncio.gather(*(hub.call(e, "fetch_tickers", priority="scan") for e in ids))
    vol: dict[str, float] = defaultdict(float)
    for eid, tk in zip(ids, tickers):
        if not tk:
            continue
        rev = {v.symbol: b for b, v in hub.symbols[eid].items()}
        for sym, t in tk.items():
            base = rev.get(sym)
            if base is None:
                continue
            qv = t.get("quoteVolume")
            if qv is None and t.get("baseVolume") and t.get("last"):
                qv = t["baseVolume"] * t["last"]
            vol[base] += float(qv or 0.0)

    coins = []
    for base, v in sorted(vol.items(), key=lambda kv: kv[1], reverse=True):
        if v < cfg.min_agg_volume_usd or base not in hub.exec_map:
            continue
        venues = {e: hub.symbols[e][base] for e in ids if base in hub.symbols[e]}
        if len(venues) >= 1:
            coins.append(Coin(base, v, venues))
        if len(coins) >= cfg.max_scan_coins:
            break
    log.info("universe: %d coins >= $%.0f volume and tradable on %s", len(coins), cfg.min_agg_volume_usd, cfg.exec_exchange)
    return coins

def prefilter(coins: list[Coin], agg: Optional[dict], cfg: Config) -> list[Coin]:
    if not agg:
        return coins
    scored = []
    for c in coins:
        pair = agg.get(c.base)
        if pair and sum(pair) > 0:
            scored.append((max(pair) / sum(pair), c))
    if len(scored) < cfg.top_n:
        return coins
    scored.sort(key=lambda t: t[0], reverse=True)
    keep = [c for _, c in scored[: cfg.prefilter_keep]]
    log.info("CoinGlass prefilter: %d -> %d coins", len(coins), len(keep))
    return keep

async def measure(hub: "ExchangeHub", coin: Coin, cfg: Config, priority: str = "scan") -> Optional[CoinImbalance]:
    items = list(coin.venues.items())
    books = await asyncio.gather(*(hub.book(eid, v.symbol, priority) for eid, v in items))
    bid = ask = 0.0
    n = 0
    for (_, v), bk in zip(items, books):
        d = depth_within(bk, cfg.depth_pct, v.contract_size)
        if d:
            bid, ask, n = bid + d[0], ask + d[1], n + 1
    if n < cfg.min_venues or bid + ask < cfg.min_book_usd:
        return None
    return CoinImbalance(coin.base, bid, ask, n)

async def stage1(hub: "ExchangeHub", cfg: Config, coins: list[Coin]):
    sem = asyncio.Semaphore(cfg.scan_concurrency)
    async def one(c: Coin):
        async with sem:
            try:
                return await measure(hub, c, cfg, "scan")
            except Exception:
                log.exception("measure failed for %s", c.base)
                return None
    res = [r for r in await asyncio.gather(*(one(c) for c in coins)) if r]
    res.sort(key=lambda r: r.strength, reverse=True)
    return res[: cfg.top_n], len(res)

async def stage2(hub: "ExchangeHub", cfg: Config, top: list[CoinImbalance]):
    async def score(ci: CoinImbalance):
        v = hub.exec_map.get(ci.base)
        if v is None:
            return ci.base, None
        c = await hub.ohlcv(hub.exec_key, v.symbol, "1m", cfg.candle_minutes + 1, "scan")
        if not c:
            return ci.base, None
        c = c[-cfg.candle_minutes:]
        hi, lo = max(x[2] for x in c), min(x[3] for x in c)
        return ci.base, ((hi - lo) / lo if lo > 0 else None)

    scores = {b: s for b, s in await asyncio.gather(*(score(ci) for ci in top)) if s is not None}
    if not scores:
        return None, {}
    best = max(scores, key=scores.get)
    return next(ci for ci in top if ci.base == best), scores

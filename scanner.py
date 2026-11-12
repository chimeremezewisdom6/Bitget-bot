from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import aiohttp

from config import STABLES, Config
from models import Coin, CoinImbalance

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("scanner")

MIN_VOLUME_USD = 1_000_000
COINLORE_TICKERS = "https://api.coinlore.net/api/tickers/"
COINPAPRIKA_TICKERS = "https://api.coinpaprika.com/v1/tickers"
CRYPTOCOMPARE_HISTO = "https://min-api.cryptocompare.com/data/v2/histominute"
HTTP_HEADERS = {"User-Agent": "BitgetBot/1.0", "Accept": "application/json"}

_PAPRIKA_IDS: dict[str, str] = {}
_CANDLES: dict[str, list] = {}
_CHANGES: dict[str, float] = {}


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
    return [c for _, c in scored[: cfg.prefilter_keep]]


def _venues_for(hub: "ExchangeHub", base: str) -> dict:
    venues = {e: hub.symbols[e][base] for e in hub.scan_ids if base in hub.symbols.get(e, {})}
    if not venues and base in hub.exec_map:
        venues = {hub.cfg.exec_exchange: hub.exec_map[base]}
    return venues


async def _get_json(session: aiohttp.ClientSession, url: str, params: Optional[dict] = None):
    try:
        async with session.get(url, params=params, headers=HTTP_HEADERS) as resp:
            if resp.status != 200:
                return None
            return await resp.json(content_type=None)
    except Exception:
        return None


async def _fetch_coinlore(session: aiohttp.ClientSession) -> list[tuple[str, float, Optional[str]]]:
    out: dict[str, tuple[str, float, Optional[str]]] = {}
    for start in range(0, 1500, 100):
        data = await _get_json(session, COINLORE_TICKERS, {"start": start, "limit": 100})
        rows = (data or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            break
        for row in rows:
            try:
                sym = str(row.get("symbol") or "").upper()
                vol = float(row.get("volume24") or 0)
            except (TypeError, ValueError):
                continue
            if not sym or vol < MIN_VOLUME_USD or sym in STABLES:
                continue
            prev = out.get(sym)
            if prev is None or vol > prev[1]:
                out[sym] = (sym, vol, None)
        if len(rows) < 100:
            break
    return list(out.values())


async def _fetch_coinpaprika(session: aiohttp.ClientSession) -> list[tuple[str, float, Optional[str]]]:
    out: dict[str, tuple[str, float, Optional[str]]] = {}
    for page in range(1, 16):
        data = await _get_json(session, COINPAPRIKA_TICKERS, {"page": page, "quotes": "USD"})
        if not isinstance(data, list) or not data:
            break
        for row in data:
            try:
                quotes = (row.get("quotes") or {}).get("USD") or {}
                sym = str(row.get("symbol") or "").upper()
                vol = float(quotes.get("volume_24h") or 0)
                cid = row.get("id")
            except (TypeError, ValueError):
                continue
            if not sym or vol < MIN_VOLUME_USD or sym in STABLES:
                continue
            prev = out.get(sym)
            if prev is None or vol > prev[1]:
                out[sym] = (sym, vol, cid)
        if len(data) != 100:
            break
    return list(out.values())


async def _fetch_global_volume() -> list[tuple[str, float, Optional[str]]]:
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        rows = await _fetch_coinlore(session)
        paprika = await _fetch_coinpaprika(session)
        ids = {sym: cid for sym, _, cid in paprika if cid}
        if rows:
            merged = []
            for sym, vol, _ in rows:
                merged.append((sym, vol, ids.get(sym)))
            return merged
        return paprika


async def _cryptocompare_candles(session: aiohttp.ClientSession, symbol: str) -> Optional[list]:
    data = await _get_json(session, CRYPTOCOMPARE_HISTO, {
        "fsym": symbol, "tsym": "USD", "limit": 60, "aggregate": 1, "e": "CCCAGG",
    })
    if not isinstance(data, dict) or data.get("Response") == "Error":
        return None
    rows = ((data.get("Data") or {}).get("Data") or [])
    candles = []
    for r in rows:
        try:
            close = float(r.get("close") or 0)
            vol = float(r.get("volumeto") or r.get("volumefrom") or 0)
        except (TypeError, ValueError):
            continue
        candles.append({"close": close, "volume": vol, "time": r.get("time")})
    return candles if len(candles) >= 11 else None


def _as_ts(value) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


async def _paprika_candles(session: aiohttp.ClientSession, coin_id: Optional[str]) -> Optional[list]:
    if not coin_id:
        return None
    start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    data = None
    for interval in ("1m", "5m"):
        data = await _get_json(
            session,
            f"https://api.coinpaprika.com/v1/tickers/{coin_id}/historical",
            {"start": start, "interval": interval},
        )
        if isinstance(data, list) and data:
            break
    if not isinstance(data, list) or not data:
        return None
    candles = []
    for r in data:
        try:
            close = float(r.get("price") or 0)
            vol = float(r.get("volume_24h") or 0)
        except (TypeError, ValueError):
            continue
        candles.append({"close": close, "volume": vol, "time": _as_ts(r.get("timestamp"))})
    return candles if len(candles) >= 3 else None


async def _candles_for(session: aiohttp.ClientSession, symbol: str) -> Optional[list]:
    rows = await _cryptocompare_candles(session, symbol)
    if rows:
        return rows
    return await _paprika_candles(session, _PAPRIKA_IDS.get(symbol))


def _price_change_pct(candles: list) -> Optional[float]:
    if not candles or len(candles) < 2:
        return None
    last = candles[-1]
    last_close = last["close"]
    last_ts = last.get("time")
    ago_close = None
    if isinstance(last_ts, (int, float)):
        target_ts = last_ts - 600
        best, best_dt = None, None
        for c in candles[:-1]:
            t = c.get("time")
            if not isinstance(t, (int, float)):
                continue
            dt = abs(t - target_ts)
            if best is None or dt < best_dt:
                best, best_dt = c, dt
        if best is not None:
            ago_close = best["close"]
    if ago_close is None:
        idx = -11 if len(candles) >= 11 else 0
        ago_close = candles[idx]["close"]
    if ago_close <= 0 or last_close <= 0:
        return None
    return (last_close - ago_close) / ago_close * 100.0


def _volume_surge(candles: list) -> float:
    times = [c.get("time") for c in candles]
    end = times[-1] if times else None
    last, prev = [], []
    if isinstance(end, (int, float)):
        last = [c for c, t in zip(candles, times) if isinstance(t, (int, float)) and end - 600 <= t <= end]
        prev = [c for c, t in zip(candles, times) if isinstance(t, (int, float)) and end - 3600 <= t < end - 600]
    if not last or not prev:
        n = len(candles)
        if n >= 60:
            last, prev = candles[-10:], candles[-60:-10]
        elif n >= 12:
            last, prev = candles[-10:], candles[:-10]
        else:
            mid = max(1, n // 2)
            last, prev = candles[-mid:], candles[:-mid]
    if not last or not prev:
        return 1.0
    last_avg = sum(c["volume"] for c in last) / len(last)
    prev_avg = sum(c["volume"] for c in prev) / len(prev)
    if prev_avg <= 0:
        return 1.0
    return last_avg / prev_avg


def _forced_imbalance(base: str, change_pct: float, n_venues: int) -> CoinImbalance:
    n = max(1, n_venues)
    if change_pct >= 0:
        return CoinImbalance(base, 100.0, 10.0, n)
    return CoinImbalance(base, 10.0, 100.0, n)


async def build_universe(hub: "ExchangeHub", cfg: Config) -> list[Coin]:
    global _PAPRIKA_IDS
    _PAPRIKA_IDS = {}
    _CANDLES.clear()
    _CHANGES.clear()
    rows = await _fetch_global_volume()
    coins: list[Coin] = []
    for sym, vol, cid in sorted(rows, key=lambda r: r[1], reverse=True):
        if cid:
            _PAPRIKA_IDS[sym] = cid
        if sym not in hub.exec_map:
            continue
        venues = _venues_for(hub, sym)
        if not venues:
            continue
        coins.append(Coin(sym, vol, venues))
        if len(coins) >= cfg.max_scan_coins:
            break
    return coins


async def stage1(hub: "ExchangeHub", cfg: Config, coins: list[Coin]):
    _CANDLES.clear()
    _CHANGES.clear()
    sem = asyncio.Semaphore(5)
    timeout = aiohttp.ClientTimeout(total=20)

    async def one(session: aiohttp.ClientSession, c: Coin):
        async with sem:
            try:
                candles = await _candles_for(session, c.base)
                if not candles:
                    return None
                change = _price_change_pct(candles)
                if change is None:
                    return None
                _CANDLES[c.base] = candles
                _CHANGES[c.base] = change
                return c, change
            except Exception:
                log.exception("candle fetch failed for %s", c.base)
                return None

    async with aiohttp.ClientSession(timeout=timeout) as session:
        rows = [r for r in await asyncio.gather(*(one(session, c) for c in coins)) if r]
    rows.sort(key=lambda t: abs(t[1]), reverse=True)
    top_rows = rows[: cfg.top_n]
    top = [_forced_imbalance(c.base, change, len(c.venues)) for c, change in top_rows]
    return top, len(rows)


async def stage2(hub: "ExchangeHub", cfg: Config, top: list[CoinImbalance]):
    scores: dict[str, float] = {}
    best = None
    best_score = float("-inf")
    for ci in top:
        candles = _CANDLES.get(ci.base)
        change = _CHANGES.get(ci.base)
        if candles is None or change is None:
            continue
        surge = _volume_surge(candles)
        momentum = abs(change) * surge
        scores[ci.base] = abs(change) / 100.0
        if momentum > best_score:
            best_score = momentum
            best = ci
    if best is None:
        return None, scores
    return best, scores

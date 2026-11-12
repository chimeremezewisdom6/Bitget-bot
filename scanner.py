from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Optional

import aiohttp
import ccxt.async_support as ccxt

from config import QUOTES, STABLES, Config
from models import Coin, CoinImbalance, Venue

if TYPE_CHECKING:
    from exchange_hub import ExchangeHub

log = logging.getLogger("scanner")
_MULT = re.compile(r"^10{2,}")
_QUOTE_SUFFIXES = (
    "/USDT:USDT", "/USDC:USDC", "/USD:USD", "/USDT:USD",
    "/USDT", "/USDC", "/USD", "-USDT", "-USDC", "-USD", "_USDT", "_USDC", "_USD",
)

MIN_VOLUME_USD = 1_000_000
COINLORE_TICKERS = "https://api.coinlore.net/api/tickers/"
COINPAPRIKA_TICKERS = "https://api.coinpaprika.com/v1/tickers"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_KLINES = "https://fapi.binance.com/fapi/v1/klines"
BYBIT_KLINES = "https://api.bybit.com/v5/market/kline"
OKX_CANDLES = "https://www.okx.com/api/v5/market/candles"
HTTP_HEADERS = {"User-Agent": "BitgetBot/1.0", "Accept": "application/json"}

_PAPRIKA_IDS: dict[str, str] = {}
_CANDLES: dict[str, list] = {}
_CHANGES: dict[str, float] = {}
_BITGET_BY_BASE: dict[str, str] = {}
_BITGET_VENUES: dict[str, Venue] = {}


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
    try:
        items = list(coin.venues.items())
        if not items:
            print(f"FAILED to fetch {coin.base}: no venues mapped", flush=True)
            return None
        books = await asyncio.gather(*(hub.book(eid, v.symbol, priority) for eid, v in items), return_exceptions=True)
        bid = ask = 0.0
        n = 0
        errors = []
        for (eid, v), bk in zip(items, books):
            if isinstance(bk, Exception):
                errors.append(f"{eid}:{v.symbol} {bk}")
                continue
            d = depth_within(bk, cfg.depth_pct, v.contract_size)
            if d:
                bid, ask, n = bid + d[0], ask + d[1], n + 1
            elif bk is None:
                err = hub.last_error.get(eid) or hub.last_error.get(hub.exec_key) or "empty book"
                errors.append(f"{eid}:{v.symbol} {err}")
        if n < cfg.min_venues or bid + ask < cfg.min_book_usd:
            print(f"FAILED to fetch {coin.base}: book n={n} usd={bid+ask:.0f} {' | '.join(errors)}", flush=True)
            return None
        return CoinImbalance(coin.base, bid, ask, n)
    except Exception as e:
        print(f"FAILED to fetch {coin.base}: {e}", flush=True)
        return None


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


def _clean_base(raw: str) -> str:
    s = str(raw or "").upper().strip()
    for suf in _QUOTE_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    s = s.split("/")[0].split(":")[0].split("-")[0].split("_")[0]
    for q in ("USDT", "USDC", "BUSD", "USD"):
        if s.endswith(q) and len(s) > len(q):
            s = s[: -len(q)]
            break
    return s.strip()


def _norm_base(base: str) -> str:
    return _MULT.sub("", _clean_base(base))


def get_bitget_symbol(base_coin: str) -> Optional[str]:
    raw = str(base_coin or "").upper().strip()
    base = _clean_base(raw)
    stripped = _norm_base(base)
    candidates = [raw, base, stripped, f"{base}USDT", f"{stripped}USDT"]
    for prefix in ("1000", "10000", "100000", "1000000"):
        candidates.append(prefix + stripped)
        candidates.append(f"{prefix}{stripped}USDT")
    for key in candidates:
        if key and key in _BITGET_BY_BASE:
            return _BITGET_BY_BASE[key]
    compact = re.sub(r"[^A-Z0-9]", "", stripped)
    if not compact:
        return None
    for key, sym in _BITGET_BY_BASE.items():
        key_c = re.sub(r"[^A-Z0-9]", "", key)
        prefix = key_c[:-len(compact)] if key_c.endswith(compact) else ""
        if key_c == compact or (prefix and prefix.rstrip("0") == "1"):
            return sym
        sym_c = re.sub(r"[^A-Z0-9]", "", str(sym).upper())
        if sym_c.startswith(compact + "USDT") or compact + "USDT" in sym_c:
            return sym
    return None


def _index_bitget_markets(markets: dict) -> None:
    ranked: dict[str, tuple] = {}
    venues: dict[str, Venue] = {}
    for sym, m in (markets or {}).items():
        if m.get("active") is False:
            continue
        if not (m.get("swap") and m.get("linear")):
            continue
        quote = m.get("quote")
        if quote not in QUOTES:
            continue
        raw_base = str(m.get("base") or "").upper()
        if not raw_base or raw_base in STABLES:
            continue
        rank = QUOTES.index(quote)
        cs = float(m.get("contractSize") or 1.0)
        venue = Venue(sym, cs)
        keys = {raw_base, _norm_base(raw_base), _clean_base(raw_base), _clean_base(sym), str(sym).upper()}
        if m.get("id"):
            keys.add(str(m.get("id")).upper())
        keys.add(raw_base + "USDT")
        keys.add(_norm_base(raw_base) + "USDT")
        for key in keys:
            if not key:
                continue
            prev = ranked.get(key)
            if prev is None or rank < prev[0]:
                ranked[key] = (rank, sym)
                venues[key] = venue
    _BITGET_BY_BASE.clear()
    _BITGET_BY_BASE.update({k: v[1] for k, v in ranked.items()})
    _BITGET_VENUES.clear()
    _BITGET_VENUES.update(venues)


async def _ensure_bitget_markets(hub: Optional["ExchangeHub"] = None) -> None:
    if _BITGET_BY_BASE:
        return
    markets = None
    if hub is not None:
        inst = hub.ex.get(getattr(hub, "exec_key", ""), None) or hub.ex.get("bitget")
        if inst is not None and inst.markets:
            markets = inst.markets
        if not markets and hub.exec_map:
            _BITGET_BY_BASE.update({b: v.symbol for b, v in hub.exec_map.items()})
            _BITGET_VENUES.update(hub.exec_map)
            if _BITGET_BY_BASE:
                return
    if not markets:
        ex = ccxt.bitget({"enableRateLimit": True, "timeout": 15000, "options": {"defaultType": "swap"}})
        try:
            await ex.load_markets()
            markets = ex.markets
        finally:
            await ex.close()
    _index_bitget_markets(markets or {})
    if hub is not None:
        for base, venue in hub.exec_map.items():
            _BITGET_BY_BASE.setdefault(base, venue.symbol)
            _BITGET_BY_BASE.setdefault(_norm_base(base), venue.symbol)
            _BITGET_VENUES.setdefault(base, venue)
            _BITGET_VENUES.setdefault(_norm_base(base), venue)


def _venues_for(hub: "ExchangeHub", base: str, bitget_symbol: str) -> dict:
    venue = _BITGET_VENUES.get(base) or _BITGET_VENUES.get(_norm_base(base))
    if venue is None or venue.symbol != bitget_symbol:
        for v in hub.exec_map.values():
            if v.symbol == bitget_symbol:
                venue = v
                break
        else:
            venue = Venue(bitget_symbol, 1.0)
    venues = {"bitget": venue}
    for e in hub.scan_ids:
        mapped = hub.symbols.get(e, {})
        if base in mapped:
            venues[e] = mapped[base]
        elif _norm_base(base) in mapped:
            venues[e] = mapped[_norm_base(base)]
    return venues


async def _get_json(session: aiohttp.ClientSession, url: str, params: Optional[dict] = None):
    last_err = None
    for attempt in range(2):
        try:
            async with session.get(url, params=params, headers=HTTP_HEADERS) as resp:
                body = await resp.text()
                if resp.status == 429:
                    last_err = RuntimeError(f"HTTP 429 {url} {body[:180]}")
                    await asyncio.sleep(0.5)
                    continue
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} {url} {body[:180]}")
                return json.loads(body)
        except Exception as e:
            last_err = e
            if attempt == 0 and "429" in str(e):
                await asyncio.sleep(0.5)
                continue
            raise RuntimeError(str(e)) from e
    raise RuntimeError(str(last_err))


async def _fetch_coinlore(session: aiohttp.ClientSession) -> list[tuple[str, float, Optional[str]]]:
    out: dict[str, tuple[str, float, Optional[str]]] = {}
    for start in range(0, 1500, 100):
        try:
            data = await _get_json(session, COINLORE_TICKERS, {"start": start, "limit": 100})
        except Exception as e:
            print(f"FAILED to fetch CoinLore tickers start={start}: {e}", flush=True)
            break
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
        try:
            data = await _get_json(session, COINPAPRIKA_TICKERS, {"page": page, "quotes": "USD"})
        except Exception as e:
            print(f"FAILED to fetch CoinPaprika tickers page={page}: {e}", flush=True)
            break
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


def _klines_to_rows(raw, ts_ms: bool = True) -> Optional[list]:
    if not isinstance(raw, list) or not raw:
        return None
    candles = []
    for r in raw:
        try:
            ts_raw = float(r[0])
            close = float(r[4])
            vol = float(r[5] if len(r) > 5 else 0)
            ts = ts_raw / 1000.0 if ts_ms or ts_raw > 10_000_000_000 else ts_raw
        except (TypeError, ValueError, IndexError):
            continue
        candles.append({"close": close, "volume": vol, "time": ts})
    candles.sort(key=lambda c: c["time"] or 0)
    return candles if len(candles) >= 11 else None


def _spot_pair(base: str) -> str:
    return f"{_clean_base(base)}USDT"


async def _binance_candles(session: aiohttp.ClientSession, base: str) -> Optional[list]:
    pair = _spot_pair(base)
    errors = []
    for url in (BINANCE_KLINES, BINANCE_FUTURES_KLINES):
        try:
            data = await _get_json(session, url, {"symbol": pair, "interval": "1m", "limit": 60})
            rows = _klines_to_rows(data, True)
            if rows:
                return rows
            errors.append(f"{url} empty/short payload")
        except Exception as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError(" | ".join(errors) if errors else "binance no data")


async def _bybit_candles(session: aiohttp.ClientSession, base: str) -> Optional[list]:
    pair = _spot_pair(base)
    errors = []
    for category in ("spot", "linear"):
        try:
            data = await _get_json(session, BYBIT_KLINES, {
                "category": category, "symbol": pair, "interval": "1", "limit": 60,
            })
            if not isinstance(data, dict):
                errors.append(f"bybit {category} unexpected payload")
                continue
            if str(data.get("retCode")) not in ("0", "None"):
                errors.append(f"bybit {category} retCode={data.get('retCode')} {data.get('retMsg')}")
                continue
            klines = ((data.get("result") or {}).get("list") or [])
            rows = _klines_to_rows(klines, True)
            if rows:
                return rows
            errors.append(f"bybit {category} empty/short payload")
        except Exception as e:
            errors.append(f"bybit {category}: {e}")
    raise RuntimeError(" | ".join(errors) if errors else "bybit no data")


async def _okx_candles(session: aiohttp.ClientSession, base: str) -> Optional[list]:
    inst = f"{_clean_base(base)}-USDT"
    errors = []
    for inst_id in (inst, f"{inst}-SWAP"):
        try:
            data = await _get_json(session, OKX_CANDLES, {"instId": inst_id, "bar": "1m", "limit": "60"})
            if not isinstance(data, dict):
                errors.append(f"okx {inst_id} unexpected payload")
                continue
            if str(data.get("code")) not in ("0", "None"):
                errors.append(f"okx {inst_id} code={data.get('code')} {data.get('msg')}")
                continue
            rows = _klines_to_rows(data.get("data") or [], True)
            if rows:
                return rows
            errors.append(f"okx {inst_id} empty/short payload")
        except Exception as e:
            errors.append(f"okx {inst_id}: {e}")
    raise RuntimeError(" | ".join(errors) if errors else "okx no data")


async def _candles_for(session: aiohttp.ClientSession, base: str, bitget_symbol: Optional[str],
                       hub: Optional["ExchangeHub"] = None) -> Optional[list]:
    errors = []
    for name, fn in (("binance", _binance_candles), ("bybit", _bybit_candles), ("okx", _okx_candles)):
        try:
            rows = await fn(session, base)
            if rows:
                return rows
            errors.append(f"{name}: empty")
        except Exception as e:
            errors.append(f"{name}: {e}")
    print(f"FAILED to fetch {bitget_symbol or base}: {' | '.join(errors)}", flush=True)
    return None


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
    await _ensure_bitget_markets(hub)
    rows = await _fetch_global_volume()
    coins: list[Coin] = []
    skipped = 0
    for raw_sym, vol, cid in sorted(rows, key=lambda r: r[1], reverse=True):
        base = _clean_base(raw_sym)
        if not base or base in STABLES:
            continue
        if cid:
            _PAPRIKA_IDS[base] = cid
        bitget_symbol = get_bitget_symbol(base)
        if bitget_symbol is None:
            skipped += 1
            log.warning("Skipping %s: no tradable market on Bitget", base)
            continue
        exec_base = base
        for k, v in hub.exec_map.items():
            if v.symbol == bitget_symbol:
                exec_base = k
                break
        if cid:
            _PAPRIKA_IDS[exec_base] = cid
        venues = _venues_for(hub, exec_base, bitget_symbol)
        coins.append(Coin(exec_base, vol, venues))
        if len(coins) >= cfg.max_scan_coins:
            break
    log.warning("universe: %d Bitget-tradable coins, skipped %d without a swap market", len(coins), skipped)
    return coins


async def stage1(hub: "ExchangeHub", cfg: Config, coins: list[Coin]):
    _CANDLES.clear()
    _CHANGES.clear()
    await _ensure_bitget_markets(hub)
    timeout = aiohttp.ClientTimeout(total=20)
    rows = []
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for c in coins:
            bitget_symbol = get_bitget_symbol(c.base)
            if bitget_symbol is None:
                print(f"FAILED to fetch {c.base}: no tradable market on Bitget", flush=True)
                log.warning("Skipping %s: no tradable market on Bitget", c.base)
                await asyncio.sleep(0.1)
                continue
            try:
                candles = await _candles_for(session, c.base, bitget_symbol, hub)
                if not candles:
                    print(f"FAILED to fetch {bitget_symbol}: no 1m candles from binance/bybit/okx", flush=True)
                    await asyncio.sleep(0.1)
                    continue
                change = _price_change_pct(candles)
                if change is None:
                    print(f"FAILED to fetch {bitget_symbol}: could not compute 10m change", flush=True)
                    await asyncio.sleep(0.1)
                    continue
                _CANDLES[c.base] = candles
                _CHANGES[c.base] = change
                rows.append((c, change))
            except Exception as e:
                print(f"FAILED to fetch {bitget_symbol}: {e}", flush=True)
            await asyncio.sleep(0.1)
    rows.sort(key=lambda t: abs(t[1]), reverse=True)
    top_rows = rows[: cfg.top_n]
    top = [_forced_imbalance(c.base, change, max(1, len(c.venues))) for c, change in top_rows]
    print(f"Successfully measured {len(rows)}/{len(coins)} coins", flush=True)
    log.warning("Successfully measured %d/%d coins", len(rows), len(coins))
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

#!/usr/bin/env python3
"""
bot.py
======
Accelerated Weakness Runner | Bitget UTA V3 | Render Free Tier.

Pipeline every PULSE_SEC (4s):
  - if position open -> manage_*_position (4s watchdog)
  - else             -> scan_candidates() over the last-ranked top 10

Background:
  - refresh_universe every 5 min
  - rank_candidates every 5 min
  - refresh_contracts every 15 min
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

import aiohttp

import market_math as mm

# =============================================================================
# CONFIG
# =============================================================================
API_BASE = "https://api.bitget.com"
PORT = 10000
PRODUCT_TYPE = "USDT-FUTURES"
LEVERAGE = 5
PULSE_SEC = 4.0
UNIVERSE_REFRESH_SEC = 300
CONTRACTS_REFRESH_SEC = 900
UNIVERSE_MIN_VOL_USD = 1_000_000.0
TOP_CANDIDATE_COUNT = 10
RANKER_BATCH = 15
RANKER_BATCH_SLEEP = 0.10
HEARTBEAT_SEC = 60.0
SYMBOL_COOLDOWN_SEC = 60.0
STREAK_FILE = "streak.json"
PAPER_WINS_REQUIRED = 8
CANDLE_COUNT = 16

_EXPECTED_MM_VERSION = "2026.11.10"

_STOCK_TOKENS = {
    "AAPLUSDT", "MSFTUSDT", "METAUSDT", "AMZNUSDT", "GOOGUSDT",
    "GOOGLUSDT", "TSLAUSDT", "NVDAUSDT", "AVGOUSDT", "ORCLUSDT",
    "PLTRUSDT", "COINUSDT", "XLKUSDT", "SPYUSDT", "QQQUSDT",
    "IWMUSDT", "MSTRUSDT", "HOODUSDT", "SQQQUSDT", "TQQQUSDT",
    "OPENAIUSDT",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("weak")


# =============================================================================
# CREDENTIALS
# =============================================================================
def _env(*names: str) -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    raise RuntimeError(f"Missing credential env var: {names}")


API_KEY = _env("BITGET_API_KEY", "API_KEY")
SECRET_KEY = _env("BITGET_API_SECRET", "SECRET_KEY")
PASSPHRASE = _env("BITGET_API_PASSPHRASE", "PASSPHRASE")


# =============================================================================
# KEEP-ALIVE
# =============================================================================
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def _start_keepalive() -> None:
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Keep-alive listening on :%d", PORT)


# =============================================================================
# BITGET UTA V3 SIGNED CLIENT
# =============================================================================
def _sign(timestamp: str, method: str, request_path: str, body: str) -> str:
    msg = timestamp + method.upper() + request_path + body
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


async def _request(session, method, path, *, query=None, body=None,
                   signed=True, retries=4):
    query = query or {}
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    path_with_q = path + ("?" + qs if qs else "")
    body_str = ""
    if method.upper() == "POST" and body:
        body_str = json.dumps(body, separators=(",", ":"))

    for attempt in range(retries):
        ts = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/json", "locale": "en-US"}
        if signed:
            headers.update({
                "ACCESS-KEY": API_KEY,
                "ACCESS-SIGN": _sign(ts, method, path_with_q, body_str),
                "ACCESS-TIMESTAMP": ts,
                "ACCESS-PASSPHRASE": PASSPHRASE,
            })

        url = API_BASE + path_with_q
        try:
            async with session.request(
                method, url,
                headers=headers,
                data=body_str if body_str else None,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                if resp.status == 429 or resp.status >= 500:
                    await asyncio.sleep((2 ** attempt) + 1)
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    log.error("Non-JSON [%s %s] %s: %s",
                              method, path, resp.status, text[:160])
                    return {"code": "JSON_ERROR", "msg": text[:160]}
                if str(data.get("code", "")) == "30011":
                    await asyncio.sleep((2 ** attempt) + 1)
                    continue
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Net err [%s %s]: %s", method, path, exc)
            await asyncio.sleep((2 ** attempt) + 1)

    return {"code": "RETRY_EXHAUSTED", "msg": "max retries"}


async def _get_public_json(session, url, timeout=10.0):
    try:
        async with session.get(
            url,
            headers={"User-Agent": "weak-bot/1.0"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception as exc:
        log.debug("Public fetch fail %s: %s", url, exc)
        return None


# =============================================================================
# STATE
# =============================================================================
_contracts: Dict[str, dict] = {}
_universe = []
_top_candidates = []
_last_rank_ts = 0.0
_cooldown_until: Dict[str, float] = {}
_active_pos = None
_paper_pos = None
_last_heartbeat = 0.0
_streak = {"wins": 0, "losses": 0, "live_activated": False, "trades": 0}

_diag = {
    "range_rej": 0,
    "accel_weak": 0,
    "accel_slow": 0,
    "vol_rej": 0,
    "breakdown_rej": 0,
    "chase_rej": 0,
    "early_rej": 0,
    "spread_rej": 0,
    "frag_rej": 0,
    "candle_fail": 0,
    "depth_fail": 0,
    "entered": 0,
}


# =============================================================================
# HELPERS
# =============================================================================
def _extract_positions(d):
    payload = d.get("data")
    if isinstance(payload, dict):
        return (payload.get("list")
                or payload.get("rows")
                or payload.get("positions")
                or [])
    if isinstance(payload, list):
        return payload
    return []


def _env_int_or_none(name: str) -> Optional[int]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _env_bool_or_none(name: str) -> Optional[bool]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return None
    return v.strip().lower() in ("1", "true", "yes", "on")


# =============================================================================
# STREAK PERSISTENCE
# =============================================================================
def _load_streak():
    try:
        with open(STREAK_FILE, "r") as f:
            d = json.load(f)
        _streak["wins"] = int(d.get("wins", 0))
        _streak["losses"] = int(d.get("losses", 0))
        _streak["live_activated"] = bool(d.get("live_activated", False))
        _streak["trades"] = int(d.get("trades", 0))
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        pass

    v = _env_int_or_none("STREAK_WINS")
    if v is not None:
        _streak["wins"] = v
    v = _env_int_or_none("STREAK_LOSSES")
    if v is not None:
        _streak["losses"] = v
    v = _env_int_or_none("STREAK_TRADES")
    if v is not None:
        _streak["trades"] = v
    v = _env_bool_or_none("STREAK_LIVE")
    if v is not None:
        _streak["live_activated"] = v


def _save_streak():
    try:
        with open(STREAK_FILE, "w") as f:
            json.dump(_streak, f)
    except OSError as exc:
        log.error("Failed to persist streak: %s", exc)


def _record_result(net_pnl, exit_reason):
    _streak["trades"] += 1
    if exit_reason == "BREAKEVEN_SHIELD":
        pass
    elif net_pnl > 0:
        _streak["wins"] += 1
        _streak["losses"] = 0
    elif net_pnl < 0:
        _streak["losses"] += 1
        _streak["wins"] = 0

    if not _streak["live_activated"] and _streak["wins"] >= PAPER_WINS_REQUIRED:
        _streak["live_activated"] = True
        log.info("*** PAPER GAUNTLET PASSED — LIVE TRADING UNLOCKED ***")

    _save_streak()
    log.info(
        "STREAK | W=%d L=%d live=%s trades=%d | net=%.3f%% | %s",
        _streak["wins"], _streak["losses"], _streak["live_activated"],
        _streak["trades"], net_pnl, exit_reason,
    )


# =============================================================================
# UTA V3 POSITION MODE
# =============================================================================
async def enforce_one_way(session):
    settings = await _request(session, "GET", "/api/v3/account/settings")
    if settings.get("code") == "00000":
        data = settings.get("data") or {}
        current = data.get("holdMode") if isinstance(data, dict) else None
        if current == "one_way_mode":
            log.info("Account already in one-way mode.")
            return
        if current:
            log.info("Current holdMode=%s — switching to one_way_mode.", current)
    else:
        log.warning("Could not read account settings (%s).",
                    settings.get("msg"))

    res = await _request(
        session, "POST", "/api/v3/account/set-hold-mode",
        body={"holdMode": "one_way_mode"},
    )
    if res.get("code") == "00000":
        log.info("One-way mode enforced.")
        return

    msg = str(res.get("msg") or "")
    lower = msg.lower()
    if "position" in lower or "order" in lower:
        log.info("Could not switch to one-way mode (open positions/orders): %s",
                 msg)
    else:
        log.warning("set-hold-mode rejected: code=%s msg=%s",
                    res.get("code"), msg)


# =============================================================================
# CONTRACT RULES
# =============================================================================
async def refresh_contracts(session):
    d = await _request(
        session, "GET", "/api/v2/mix/market/contracts",
        query={"productType": PRODUCT_TYPE}, signed=False,
    )
    if d.get("code") != "00000":
        log.warning("Contract refresh failed: %s", d.get("msg"))
        return
    new_cache = {}
    for c in d.get("data", []) or []:
        sym = c.get("symbol", "")
        if not sym or not sym.endswith("USDT"):
            continue
        try:
            new_cache[sym] = {
                "volumePlace": int(float(c.get("volumePlace") or 0)),
                "pricePlace": int(float(c.get("pricePlace") or 0)),
                "minOrderVolume": float(c.get("minTradeNum") or 0),
                "minNotional": float(c.get("minTradeUSDT") or 5.0),
                "is_stock": sym in _STOCK_TOKENS,
            }
        except (TypeError, ValueError):
            continue
    _contracts.clear()
    _contracts.update(new_cache)
    stock_n = sum(1 for v in _contracts.values() if v["is_stock"])
    log.info("Contracts cached: %d symbols (%d stock)",
             len(_contracts), stock_n)


# =============================================================================
# UNIVERSE (8-exchange aggregation)
# =============================================================================
def _norm(sym):
    s = (sym or "").upper().replace("-", "").replace("_", "").replace("/", "")
    if s.startswith("XBT"):
        s = "BTC" + s[3:]
    if s.endswith("USDTM"):
        s = s[:-1]
    if s.endswith("SWAP"):
        s = s[:-4]
    if s.endswith("PERP"):
        s = s[:-4]
    return s


async def _vol_bitget(session):
    out = {}
    d = await _get_public_json(
        session, API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}",
    )
    if not isinstance(d, dict) or d.get("code") != "00000":
        return out
    for t in d.get("data", []) or []:
        sym = t.get("symbol", "")
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("usdtVolume") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_binance(session):
    out = {}
    d = await _get_public_json(session, "https://fapi.binance.com/fapi/v1/ticker/24hr")
    if not isinstance(d, list):
        return out
    for t in d:
        sym = _norm(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("quoteVolume") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_bybit(session):
    out = {}
    d = await _get_public_json(
        session, "https://api.bybit.com/v5/market/tickers?category=linear",
    )
    if not isinstance(d, dict) or d.get("retCode") != 0:
        return out
    for t in d.get("result", {}).get("list", []) or []:
        sym = _norm(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("turnover24h") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_okx(session):
    out = {}
    d = await _get_public_json(
        session, "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
    )
    if not isinstance(d, dict) or d.get("code") != "0":
        return out
    for t in d.get("data", []) or []:
        inst = t.get("instId", "")
        if "USDT-SWAP" not in inst:
            continue
        sym = _norm(inst)
        try:
            out[sym] = (out.get(sym, 0.0)
                        + float(t.get("volCcy24h") or 0) * float(t.get("last") or 0))
        except (TypeError, ValueError):
            pass
    return out


async def _vol_gate(session):
    out = {}
    d = await _get_public_json(
        session, "https://api.gateio.ws/api/v4/futures/usdt/tickers",
    )
    if not isinstance(d, list):
        return out
    for t in d:
        sym = _norm(t.get("contract", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("volume_24h_quote") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_kucoin(session):
    out = {}
    d = await _get_public_json(
        session, "https://api-futures.kucoin.com/api/v1/contracts/active",
    )
    if not isinstance(d, dict) or d.get("code") != "200000":
        return out
    for t in d.get("data", []) or []:
        sym = _norm(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("turnoverOf24h") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_mexc(session):
    out = {}
    d = await _get_public_json(
        session, "https://contract.mexc.com/api/v1/contract/ticker",
    )
    if not isinstance(d, dict) or not d.get("success"):
        return out
    for t in d.get("data", []) or []:
        sym = _norm(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("amount24") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_htx(session):
    out = {}
    d = await _get_public_json(
        session, "https://api.hbdm.com/linear-swap-ex/market/tickers?business_type=swap",
    )
    if not isinstance(d, dict) or d.get("status") != "ok":
        return out
    for t in d.get("data", []) or []:
        sym = _norm(t.get("contract_code", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("trade_turnover") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def refresh_universe(session):
    results = await asyncio.gather(
        _vol_bitget(session), _vol_binance(session), _vol_bybit(session),
        _vol_okx(session), _vol_gate(session), _vol_kucoin(session),
        _vol_mexc(session), _vol_htx(session),
        return_exceptions=True,
    )
    agg = {}
    ok = 0
    for r in results:
        if isinstance(r, dict) and r:
            ok += 1
            for sym, vol in r.items():
                agg[sym] = agg.get(sym, 0.0) + vol

    filtered = []
    excluded_stock = 0
    excluded_vol = 0
    for s, v in agg.items():
        contract = _contracts.get(s)
        if not contract:
            continue
        if contract.get("is_stock"):
            excluded_stock += 1
            continue
        if v < UNIVERSE_MIN_VOL_USD:
            excluded_vol += 1
            continue
        filtered.append(s)

    filtered.sort(key=lambda s: agg[s], reverse=True)
    _universe.clear()
    _universe.extend(filtered)
    log.info(
        "Universe: %d symbols (>= $%.1fM, %d/8 exchanges) | excluded: %d stock, %d low-vol",
        len(_universe), UNIVERSE_MIN_VOL_USD / 1e6, ok,
        excluded_stock, excluded_vol,
    )


# =============================================================================
# CANDLES / DEPTH
# =============================================================================
def _normalize_candle(row):
    return [row[0], row[1], row[2], row[3], row[4], row[5]]


async def fetch_candles(session, symbol, limit=CANDLE_COUNT):
    d = await _request(
        session, "GET", "/api/v2/mix/market/candles",
        query={
            "symbol": symbol, "productType": PRODUCT_TYPE,
            "granularity": "1m", "limit": str(limit),
        },
        signed=False,
    )
    if d.get("code") != "00000":
        return None
    raw = d.get("data")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    out = []
    for r in raw:
        try:
            out.append(_normalize_candle(r))
        except (IndexError, TypeError):
            return None
    return out


async def fetch_depth(session, symbol):
    d = await _request(
        session, "GET", "/api/v2/mix/market/merge-depth",
        query={"symbol": symbol, "productType": PRODUCT_TYPE, "limit": "20"},
        signed=False,
    )
    if d.get("code") != "00000":
        return None
    data = d.get("data", {}) or {}
    bids = data.get("bids") or []
    asks = data.get("asks") or []
    if not bids or not asks:
        return None
    try:
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
    except (IndexError, TypeError, ValueError):
        return None
    if best_bid <= 0 or best_ask <= 0:
        return None
    mid = (best_bid + best_ask) / 2.0
    return bids, asks, mid


# =============================================================================
# ACCOUNT / POSITION
# =============================================================================
async def get_usdt_balance(session):
    d = await _request(session, "GET", "/api/v3/account/assets")
    if d.get("code") == "00000":
        data = d.get("data") or {}
        assets = data.get("assets") if isinstance(data, dict) else None
        if isinstance(assets, list):
            for a in assets:
                if a.get("coin") == "USDT":
                    try:
                        return float(a.get("available") or 0)
                    except (TypeError, ValueError):
                        return 0.0
    d2 = await _request(session, "GET", "/api/v2/account/all-account-balance")
    if d2.get("code") == "00000":
        for a in d2.get("data", []) or []:
            if a.get("coin") == "USDT":
                try:
                    return float(a.get("available") or 0)
                except (TypeError, ValueError):
                    return 0.0
    return 0.0


async def get_position(session, symbol):
    d = await _request(
        session, "GET", "/api/v3/position/current-position",
        query={"category": PRODUCT_TYPE, "symbol": symbol},
    )
    if d.get("code") != "00000":
        return None
    for p in _extract_positions(d):
        if not isinstance(p, dict):
            continue
        size = 0.0
        for k in ("total", "size", "available"):
            try:
                v = float(p.get(k) or 0)
            except (TypeError, ValueError):
                v = 0.0
            if v > 0:
                size = v
                break
        if size > 0:
            try:
                entry = float(p.get("entryPrice") or p.get("averageOpenPrice") or 0)
            except (TypeError, ValueError):
                entry = 0.0
            return {"total": size, "entryPrice": entry,
                    "posSide": p.get("posSide", "")}
    return None


async def adopt_orphan_positions(session):
    global _active_pos
    d = await _request(
        session, "GET", "/api/v3/position/current-position",
        query={"category": PRODUCT_TYPE},
    )
    if d.get("code") != "00000":
        log.warning("Orphan scan failed: %s", d.get("msg"))
        return
    for p in _extract_positions(d):
        if not isinstance(p, dict):
            continue
        try:
            total_raw = float(p.get("total") or p.get("size") or 0)
        except (TypeError, ValueError):
            continue
        if total_raw == 0:
            continue
        sym = p.get("symbol", "")
        if not sym:
            continue
        try:
            entry = float(p.get("entryPrice") or p.get("averageOpenPrice") or 0)
        except (TypeError, ValueError):
            entry = 0.0
        side = (p.get("posSide") or p.get("holdSide") or "").lower()
        if side in ("long", "buy"):
            direction = "LONG"
        elif side in ("short", "sell"):
            direction = "SHORT"
        else:
            direction = "SHORT" if total_raw > 0 else "LONG"

        _active_pos = {
            "symbol": sym, "direction": direction, "entry": entry,
            "breakdown_level": 0.0,
            "opened_at": time.time(),
            "peak_net": -999.0, "peak_gross": -999.0,
            "paper": False, "adopted": True,
        }
        log.warning(
            "ADOPTED orphan | %s %s | entry=%.6f | size=%.8f",
            sym, direction, entry, abs(total_raw),
        )
        return


# =============================================================================
# ORDER PLACEMENT (UTA V3 + tradeSide)
# =============================================================================
async def place_short_order(session, symbol, qty_str):
    body = {
        "category": PRODUCT_TYPE,
        "symbol": symbol,
        "side": "sell",
        "orderType": "market",
        "tradeSide": "open",
        "qty": qty_str,
        "reduceOnly": "no",
    }
    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        oid = (res.get("data") or {}).get("orderId")
        log.info("SHORT OPEN OK | %s qty=%s | id=%s", symbol, qty_str, oid)
        return oid
    log.error("SHORT OPEN FAIL | %s | %s", symbol, res.get("msg"))
    return None


async def place_close_order(session, symbol, qty_str):
    body = {
        "category": PRODUCT_TYPE,
        "symbol": symbol,
        "side": "buy",
        "orderType": "market",
        "tradeSide": "close",
        "qty": qty_str,
        "reduceOnly": "yes",
    }
    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        oid = (res.get("data") or {}).get("orderId")
        log.info("SHORT CLOSE OK | %s qty=%s | id=%s", symbol, qty_str, oid)
        return oid
    log.error("SHORT CLOSE FAIL | %s | %s", symbol, res.get("msg"))
    return None


async def cancel_open_orders(session, symbol):
    res = await _request(
        session, "POST", "/api/v3/trade/cancel-all-orders",
        body={"category": PRODUCT_TYPE, "symbol": symbol},
    )
    if res.get("code") == "00000":
        return
    await _request(
        session, "POST", "/api/v2/mix/order/cancel-all-orders",
        body={"productType": PRODUCT_TYPE, "symbol": symbol, "marginCoin": "USDT"},
    )


async def close_live_position(session, pos, reason):
    symbol = pos["symbol"]
    live = await get_position(session, symbol)
    if not live or live["total"] <= 0:
        log.info("No live position for %s (already gone)", symbol)
        return True
    await cancel_open_orders(session, symbol)
    vp = _contracts.get(symbol, {}).get("volumePlace", 0)
    qty_str = f"{live['total']:.{vp}f}"
    oid = await place_close_order(session, symbol, qty_str)
    if oid:
        log.info("CLOSE OK | %s | %s | size=%s", symbol, reason, qty_str)
        return True
    log.error("CLOSE FAIL | %s | %s", symbol, reason)
    return False


# =============================================================================
# RANKER
# =============================================================================
async def rank_candidates(session):
    global _top_candidates, _last_rank_ts

    symbols = list(_universe)
    if not symbols:
        log.info("Rank skipped: empty universe")
        return

    results = {}
    for i in range(0, len(symbols), RANKER_BATCH):
        chunk = symbols[i:i + RANKER_BATCH]
        tasks = [fetch_candles(session, s, limit=16) for s in chunk]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        for sym, c in zip(chunk, chunk_results):
            if isinstance(c, list) and len(c) >= 16:
                results[sym] = c[-16:]
        await asyncio.sleep(RANKER_BATCH_SLEEP)

    scored = []
    for sym, candles in results.items():
        try:
            p_old = float(candles[0][4])
            p_now = float(candles[-1][4])
            if p_old <= 0:
                continue
            pct = (p_now - p_old) / p_old * 100.0
            if pct < mm.PCT_15M_MIN_DROP or pct > mm.PCT_15M_MAX_DROP:
                continue
            scored.append({"symbol": sym, "pct_15m": pct})
        except (IndexError, TypeError, ValueError):
            continue

    scored.sort(key=lambda x: x["pct_15m"])
    _top_candidates = scored[:TOP_CANDIDATE_COUNT]
    _last_rank_ts = time.time()

    if _top_candidates:
        log.info(
            "Ranked top %d (of %d in range): %s",
            len(_top_candidates), len(scored),
            " ".join(f"{c['symbol']}={c['pct_15m']:.2f}%"
                     for c in _top_candidates),
        )
    else:
        log.info(
            "Ranked: 0 candidates in sweet-spot range [%.1f%%, %.1f%%] "
            "(%d symbols scanned)", mm.PCT_15M_MIN_DROP, mm.PCT_15M_MAX_DROP,
            len(results),
        )


# =============================================================================
# SCANNER
# =============================================================================
def _bump_diag(reason):
    if reason == "RANGE":
        _diag["range_rej"] += 1
    elif reason == "ACCEL_WEAK":
        _diag["accel_weak"] += 1
    elif reason == "ACCEL_SLOW":
        _diag["accel_slow"] += 1
    elif reason == "VOLUME":
        _diag["vol_rej"] += 1
    elif reason == "BREAKDOWN":
        _diag["breakdown_rej"] += 1
    elif reason == "CHASE":
        _diag["chase_rej"] += 1
    elif reason == "EARLY":
        _diag["early_rej"] += 1


async def scan_candidates(session):
    if not _top_candidates:
        return
    now = time.time()
    for cand in _top_candidates:
        symbol = cand["symbol"]
        if now < _cooldown_until.get(symbol, 0):
            continue

        candles = await fetch_candles(session, symbol, limit=16)
        if not candles or len(candles) < 16:
            _diag["candle_fail"] += 1
            continue
        candles = candles[-16:]

        try:
            p_old = float(candles[0][4])
            p_now = float(candles[-1][4])
            if p_old <= 0:
                continue
            pct_15m = (p_now - p_old) / p_old * 100.0
        except (IndexError, TypeError, ValueError):
            continue

        result = mm.evaluate_sweet_spot(candles, pct_15m)
        if not result["is_valid"]:
            _bump_diag(result["reason"])
            continue

        depth = await fetch_depth(session, symbol)
        if depth is None:
            _diag["depth_fail"] += 1
            continue
        bids, asks, mid = depth

        spread = mm.evaluate_spread(bids, asks)
        if not spread["is_ok"]:
            _diag["spread_rej"] += 1
            continue

        frag = mm.evaluate_book_fragility(bids, asks, mid)
        if not frag["is_fragile"]:
            _diag["frag_rej"] += 1
            log.info(
                "REJECT frag | %s | ratio=%.2f d_bid=%.0f d_ask=%.0f | pct15=%.2f%%",
                symbol, frag["depth_ratio"], frag["d_bid"], frag["d_ask"],
                pct_15m,
            )
            continue

        log.info(
            "SWEET SPOT | %s | pct15=%.2f%% drop3=%.2f%% drop6=%.2f%% "
            "vol=%.2fx ratio=%.2f d_bid=%.0f | close=%.6f low10=%.6f",
            symbol, pct_15m, result["drop_3m"], result["drop_6m"],
            result["vol_ratio"], frag["depth_ratio"], frag["d_bid"],
            result["live_close"], result["low_10m"],
        )

        entered = await enter_short(
            session, symbol, result["live_close"], result["low_10m"], pct_15m,
        )
        if entered:
            return


async def enter_short(session, symbol, entry_price, breakdown_level, pct_15m):
    global _active_pos, _paper_pos

    if not _streak["live_activated"]:
        _diag["entered"] += 1
        _paper_pos = {
            "symbol": symbol, "direction": "SHORT",
            "entry": entry_price, "breakdown_level": breakdown_level,
            "pct_15m_at_entry": pct_15m,
            "opened_at": time.time(),
            "peak_net": -999.0, "peak_gross": -999.0,
            "paper": True,
        }
        log.info("PAPER OPEN | %s SHORT @ %.6f | W=%d/%d",
                 symbol, entry_price, _streak["wins"], PAPER_WINS_REQUIRED)
        return True

    contract = _contracts.get(symbol)
    if not contract:
        log.warning("No contract rules for %s", symbol)
        return False

    balance = await get_usdt_balance(session)
    qty_str = mm.calculate_order_qty(
        balance=balance, price=entry_price, leverage=LEVERAGE,
        volume_place=contract["volumePlace"],
        min_order_volume=contract["minOrderVolume"],
        min_notional=contract["minNotional"],
    )
    if not qty_str:
        log.warning("Sizing rejected | %s | balance=%.4f | price=%.6f",
                    symbol, balance, entry_price)
        return False

    oid = await place_short_order(session, symbol, qty_str)
    if not oid:
        return False

    _diag["entered"] += 1
    _active_pos = {
        "symbol": symbol, "direction": "SHORT",
        "entry": entry_price, "breakdown_level": breakdown_level,
        "pct_15m_at_entry": pct_15m,
        "opened_at": time.time(),
        "peak_net": -999.0, "peak_gross": -999.0,
        "paper": False, "order_id": oid,
    }
    log.info("LIVE OPEN | %s SHORT @ %.6f | qty=%s",
             symbol, entry_price, qty_str)
    return True


# =============================================================================
# WATCHDOG
# =============================================================================
async def _latest_close(session, symbol):
    d = await _request(
        session, "GET", "/api/v2/mix/market/ticker",
        query={"symbol": symbol, "productType": PRODUCT_TYPE},
        signed=False,
    )
    if d.get("code") != "00000":
        return None
    data = d.get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None
    try:
        return float(data.get("lastPr") or data.get("last") or 0)
    except (TypeError, ValueError):
        return None


async def manage_live_position(session):
    global _active_pos
    pos = _active_pos
    symbol = pos["symbol"]

    live = await get_position(session, symbol)
    if live is None or live["total"] <= 0:
        log.info("Live position %s vanished externally", symbol)
        _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
        _active_pos = None
        return

    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return

    elapsed = time.time() - pos["opened_at"]
    state = mm.evaluate_ratchet(
        entry_price=live["entryPrice"] or pos["entry"],
        current_price=current,
        breakdown_level=pos["breakdown_level"],
        peak_net=pos["peak_net"],
        peak_gross=pos["peak_gross"],
        elapsed_seconds=elapsed,
    )
    pos["peak_net"] = state["updated_peak_net"]
    pos["peak_gross"] = state["updated_peak_gross"]

    if not state["should_exit"]:
        return

    closed = await close_live_position(session, pos, state["exit_reason"])
    if closed:
        _record_result(state["net_pnl"], state["exit_reason"])
        _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
        _active_pos = None


async def manage_paper_position(session):
    global _paper_pos
    pos = _paper_pos
    symbol = pos["symbol"]

    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return

    elapsed = time.time() - pos["opened_at"]
    state = mm.evaluate_ratchet(
        entry_price=pos["entry"], current_price=current,
        breakdown_level=pos["breakdown_level"],
        peak_net=pos["peak_net"],
        peak_gross=pos["peak_gross"],
        elapsed_seconds=elapsed,
    )
    pos["peak_net"] = state["updated_peak_net"]
    pos["peak_gross"] = state["updated_peak_gross"]

    if not state["should_exit"]:
        return

    log.info(
        "PAPER EXIT | %s SHORT | %s | gross=%.3f%% net=%.3f%% peak_net=%.3f%%",
        symbol, state["exit_reason"], state["gross_pnl"],
        state["net_pnl"], state["updated_peak_net"],
    )
    _record_result(state["net_pnl"], state["exit_reason"])
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _paper_pos = None


# =============================================================================
# BACKGROUND LOOPS
# =============================================================================
async def contracts_refresh_loop(session):
    while True:
        await asyncio.sleep(CONTRACTS_REFRESH_SEC)
        try:
            await refresh_contracts(session)
        except Exception as exc:
            log.warning("Contract refresh error: %s", exc)


async def ranker_loop(session):
    while True:
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)
        try:
            await refresh_universe(session)
        except Exception as exc:
            log.warning("Universe refresh error: %s", exc)
        try:
            await rank_candidates(session)
        except Exception as exc:
            log.warning("Rank error: %s", exc)


# =============================================================================
# HEARTBEAT
# =============================================================================
def _heartbeat():
    global _last_heartbeat
    if time.time() - _last_heartbeat < HEARTBEAT_SEC:
        return
    _last_heartbeat = time.time()
    log.info(
        "HEARTBEAT | universe=%d ranked=%d active=%s paper=%s | "
        "funnel: rng=%d aw=%d as=%d vol=%d bd=%d chs=%d early=%d "
        "spr=%d frg=%d cf=%d df=%d ent=%d | "
        "streak W=%d L=%d live=%s trades=%d",
        len(_universe), len(_top_candidates),
        _active_pos is not None, _paper_pos is not None,
        _diag["range_rej"], _diag["accel_weak"], _diag["accel_slow"],
        _diag["vol_rej"], _diag["breakdown_rej"], _diag["chase_rej"],
        _diag["early_rej"], _diag["spread_rej"], _diag["frag_rej"],
        _diag["candle_fail"], _diag["depth_fail"], _diag["entered"],
        _streak["wins"], _streak["losses"], _streak["live_activated"],
        _streak["trades"],
    )
    for k in _diag:
        _diag[k] = 0


# =============================================================================
# MAIN
# =============================================================================
async def main():
    _start_keepalive()

    if getattr(mm, "__version__", "UNKNOWN") != _EXPECTED_MM_VERSION:
        log.critical(
            "market_math.py version mismatch: expected %s, got %s. "
            "Clear Render build cache & redeploy.",
            _EXPECTED_MM_VERSION, getattr(mm, "__version__", "UNKNOWN"),
        )
        raise SystemExit(1)

    for _name in ("PCT_15M_MIN_DROP", "PCT_15M_MAX_DROP",
                  "VOLUME_EXPANSION_MIN", "BREAKDOWN_BUFFER_PCT",
                  "ANTI_CHASE_MAX_PCT", "MIN_SIDE_DEPTH_USD",
                  "FRAGILITY_RATIO_MIN", "MAX_SPREAD_PCT"):
        if not hasattr(mm, _name):
            log.critical("market_math.py missing %s — stale.", _name)
            raise SystemExit(1)

    _load_streak()
    log.info(
        "Startup | mode=%s | streak W=%d L=%d trades=%d | "
        "pct15 in [%.1f%%, %.1f%%] | vol>=%.1fx | bd<%.2f%% | "
        "chase<=%.2f%% | frag>=%.2f | minBid=$%.0f",
        "LIVE" if _streak["live_activated"] else "PAPER",
        _streak["wins"], _streak["losses"], _streak["trades"],
        mm.PCT_15M_MIN_DROP, mm.PCT_15M_MAX_DROP,
        mm.VOLUME_EXPANSION_MIN, mm.BREAKDOWN_BUFFER_PCT,
        mm.ANTI_CHASE_MAX_PCT, mm.FRAGILITY_RATIO_MIN,
        mm.MIN_SIDE_DEPTH_USD,
    )

    connector = aiohttp.TCPConnector(limit=30, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector,
                                     timeout=timeout) as session:
        await asyncio.gather(
            enforce_one_way(session),
            refresh_contracts(session),
        )
        await refresh_universe(session)
        await rank_candidates(session)
        await adopt_orphan_positions(session)

        asyncio.create_task(contracts_refresh_loop(session))
        asyncio.create_task(ranker_loop(session))

        log.info("Main loop started | universe=%d ranked=%d",
                 len(_universe), len(_top_candidates))

        while True:
            loop_start = time.time()

            try:
                if _active_pos is not None:
                    await manage_live_position(session)
                elif _paper_pos is not None:
                    await manage_paper_position(session)
                else:
                    await scan_candidates(session)
            except Exception as exc:
                log.error("Loop error: %s", exc, exc_info=True)

            _heartbeat()
            elapsed = time.time() - loop_start
            await asyncio.sleep(max(0.0, PULSE_SEC - elapsed))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested.")
    except SystemExit:
        raise
    except Exception as exc:
        log.critical("Fatal: %s", exc, exc_info=True)

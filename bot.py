#!/usr/bin/env python3
"""
bot.py
======
Coiled Spring Ignition | Bitget UTA V3 | Render Free Tier.

Runtime tuning tips:
    - Too few candidates: loosen BOX_RANGE_MAX_PCT in market_math.py (0.70 -> 0.85)
    - Too many candidates: tighten BOX_RANGE_MAX_PCT (0.70 -> 0.55)
    - Fragility dominates logs: lower DEPTH_FRAGILITY_MIN (1.35 -> 1.20)
    - Wide-spread entries: tighten MAX_SPREAD_PCT (0.15 -> 0.10)
    - New stock tokens appear: add to _STOCK_TOKENS below
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
from typing import Dict

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
UNIVERSE_MIN_VOL_USD = 1_000_000.0
UNIVERSE_BATCH = 6
HOT_LIST_BATCH = 6
HOT_LIST_MAX = 25
HOT_LIST_TTL_SEC = 300.0
HEARTBEAT_SEC = 60.0
SYMBOL_COOLDOWN_SEC = 60.0
STREAK_FILE = "streak.json"
PAPER_WINS_REQUIRED = 8
CANDLE_COUNT = 31

# Bitget tokenized equities / ETFs — not crypto, exclude from universe.
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
log = logging.getLogger("coil")


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
# KEEP-ALIVE SERVER
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
# BITGET UTA V3 AUTHENTICATOR
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
                    return json.loads(text)
                except json.JSONDecodeError:
                    log.error("Non-JSON [%s %s] %s: %s",
                              method, path, resp.status, text[:160])
                    return {"code": "JSON_ERROR", "msg": text[:160]}
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Net err [%s %s]: %s", method, path, exc)
            await asyncio.sleep((2 ** attempt) + 1)

    return {"code": "RETRY_EXHAUSTED", "msg": "max retries"}


async def _get_public_json(session, url, timeout=10.0):
    try:
        async with session.get(
            url,
            headers={"User-Agent": "coil-bot/1.0"},
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
_universe_idx = 0
_hot_list: Dict[str, dict] = {}
_cooldown_until: Dict[str, float] = {}
_last_logged_rejection: Dict[str, int] = {}
_active_pos = None
_paper_pos = None
_last_heartbeat = 0.0
_streak = {
    "wins": 0,
    "losses": 0,
    "live_activated": False,
    "trades": 0,
}


def _load_streak():
    try:
        with open(STREAK_FILE, "r") as f:
            d = json.load(f)
        _streak["wins"] = int(d.get("wins", 0))
        _streak["losses"] = int(d.get("losses", 0))
        _streak["live_activated"] = bool(d.get("live_activated", False))
        _streak["trades"] = int(d.get("trades", 0))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def _save_streak():
    try:
        with open(STREAK_FILE, "w") as f:
            json.dump(_streak, f)
    except OSError as exc:
        log.error("Failed to persist streak: %s", exc)


# =============================================================================
# ONE-WAY MODE (single_hold)
# =============================================================================
async def enforce_one_way(session):
    res = await _request(
        session, "POST", "/api/v2/mix/account/set-position-mode",
        body={"productType": PRODUCT_TYPE, "posMode": "single_hold"},
    )
    if res.get("code") == "00000":
        log.info("One-way mode enforced (single_hold).")
    else:
        log.warning("set-position-mode response: %s", res.get("msg"))


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
            }
        except (TypeError, ValueError):
            continue
    _contracts.clear()
    _contracts.update(new_cache)
    log.info("Contracts cached: %d symbols", len(_contracts))


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
            out[sym] = out.get(sym, 0.0) + float(t.get("volCcy24h") or 0) * float(t.get("last") or 0)
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

    tradeable = set(_contracts.keys())
    filtered = []
    excluded_stock = 0
    excluded_vol = 0
    for s, v in agg.items():
        if s not in tradeable:
            continue
        if s in _STOCK_TOKENS:
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
        "Universe refreshed: %d symbols (>= $%.1fM, %d/8 exchanges) | "
        "excluded: %d stock, %d low-vol",
        len(_universe), UNIVERSE_MIN_VOL_USD / 1e6, ok,
        excluded_stock, excluded_vol,
    )


# =============================================================================
# MARKET DATA
# =============================================================================
def _normalize_candle(row):
    """Bitget: [ts, o, h, l, c, baseVol, quoteVol] -> [ts, o, h, l, c, baseVol]"""
    return [row[0], row[1], row[2], row[3], row[4], row[5]]


def _candle_ts(candle):
    try:
        return int(candle[0])
    except (IndexError, TypeError, ValueError):
        return 0


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
    for p in d.get("data") or []:
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
            return {"total": size, "entryPrice": entry, "posSide": p.get("posSide", "")}
    return None


# =============================================================================
# ORDER EXECUTION
# =============================================================================
async def place_market_order(session, symbol, side, qty_str, reduce_only=False):
    body = {
        "category": PRODUCT_TYPE,
        "symbol": symbol,
        "side": side,
        "orderType": "market",
        "qty": qty_str,
        "reduceOnly": "yes" if reduce_only else "no",
    }
    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        oid = (res.get("data") or {}).get("orderId")
        log.info("ORDER OK | %s %s %s | id=%s", symbol, side, qty_str, oid)
        return oid
    log.error("ORDER FAIL | %s %s | %s", symbol, side, res.get("msg"))
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
    close_side = "sell" if pos["direction"] == "LONG" else "buy"

    oid = await place_market_order(session, symbol, close_side, qty_str, reduce_only=True)
    if oid:
        log.info("CLOSE OK | %s | %s | size=%s", symbol, reason, qty_str)
        return True
    log.error("CLOSE FAIL | %s | %s", symbol, reason)
    return False


# =============================================================================
# STREAK
# =============================================================================
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
# ENTRY PIPELINE
# =============================================================================
async def try_enter(session, symbol, direction, live_candle, box_high, box_low):
    global _active_pos, _paper_pos

    if time.time() < _cooldown_until.get(symbol, 0):
        return False

    try:
        live_close = float(live_candle[4])
    except (IndexError, TypeError, ValueError):
        return False
    candle_ts = _candle_ts(live_candle)

    depth = await fetch_depth(session, symbol)
    if depth is None:
        return False
    bids, asks, mid = depth

    # 1) Spread sanity
    spread = mm.evaluate_spread(bids, asks)
    if not spread["is_ok"]:
        log.debug("REJECT spread | %s %s | %.3f%%",
                  symbol, direction, spread["spread_pct"])
        return False

    # 2) Fragility
    frag = mm.evaluate_book_fragility(bids, asks, mid, direction)
    if not frag["is_fragile"]:
        if _last_logged_rejection.get(symbol) != candle_ts:
            log.info(
                "REJECT fragility | %s %s | ratio=%.2f | d_bid=%.0f d_ask=%.0f | spread=%.3f%%",
                symbol, direction, frag["depth_ratio"],
                frag["d_bid"], frag["d_ask"], spread["spread_pct"],
            )
            _last_logged_rejection[symbol] = candle_ts
        return False

    log.info(
        "IGNITION PASS | %s %s | close=%.6f | box=[%.6f, %.6f] | "
        "depth=%.2f | spread=%.3f%% | d_bid=%.0f d_ask=%.0f",
        symbol, direction, live_close, box_low, box_high,
        frag["depth_ratio"], spread["spread_pct"], frag["d_bid"], frag["d_ask"],
    )

    # 3) Paper mode
    if not _streak["live_activated"]:
        _paper_pos = {
            "symbol": symbol, "direction": direction, "entry": live_close,
            "box_high": box_high, "box_low": box_low,
            "opened_at": time.time(), "peak_net": -999.0, "paper": True,
        }
        log.info("PAPER OPEN | %s %s @ %.6f | streak W=%d/%d",
                 symbol, direction, live_close, _streak["wins"], PAPER_WINS_REQUIRED)
        return True

    # 4) Live mode
    contract = _contracts.get(symbol)
    if not contract:
        log.warning("No contract rules for %s", symbol)
        return False

    balance = await get_usdt_balance(session)
    qty_str = mm.calculate_order_qty(
        balance=balance, price=live_close, leverage=LEVERAGE,
        volume_place=contract["volumePlace"],
        min_order_volume=contract["minOrderVolume"],
        min_notional=contract["minNotional"],
    )
    if not qty_str:
        log.warning("Sizing rejected | %s | balance=%.4f | price=%.6f",
                    symbol, balance, live_close)
        return False

    side = "buy" if direction == "LONG" else "sell"
    oid = await place_market_order(session, symbol, side, qty_str, reduce_only=False)
    if not oid:
        return False

    _active_pos = {
        "symbol": symbol, "direction": direction, "entry": live_close,
        "box_high": box_high, "box_low": box_low,
        "opened_at": time.time(), "peak_net": -999.0,
        "paper": False, "order_id": oid,
    }
    log.info("LIVE OPEN | %s %s @ %.6f | qty=%s",
             symbol, direction, live_close, qty_str)
    return True


# =============================================================================
# SCANNERS
# =============================================================================
async def scan_universe_batch(session):
    global _universe_idx
    if not _universe:
        return
    n = len(_universe)
    now = time.time()

    for _ in range(min(UNIVERSE_BATCH, n)):
        symbol = _universe[_universe_idx % n]
        _universe_idx += 1

        if now < _cooldown_until.get(symbol, 0):
            continue
        if symbol in _hot_list and _hot_list[symbol]["expiry"] > now:
            continue

        try:
            candles = await fetch_candles(session, symbol, limit=CANDLE_COUNT)
        except Exception as exc:
            log.debug("candles fail %s: %s", symbol, exc)
            continue
        if not candles or len(candles) < 2:
            continue

        closed = candles[:-1]
        live = candles[-1]

        box = mm.calculate_compression_box(closed)
        if not box["is_compressed"]:
            continue

        log.debug("COMPRESSION | %s | range=%.3f%% | baseVol=%.2f",
                  symbol, box["box_range_pct"], box["base_volume"])

        trig = mm.evaluate_ignition_trigger(
            live, box["box_high"], box["box_low"], box["base_volume"],
        )
        if not trig["is_ignition"]:
            _add_to_hot_list(symbol, box)
            continue

        entered = await try_enter(session, symbol, trig["direction"], live,
                                  box["box_high"], box["box_low"])
        if entered:
            return


def _add_to_hot_list(symbol, box):
    if len(_hot_list) >= HOT_LIST_MAX and symbol not in _hot_list:
        oldest = min(_hot_list.keys(), key=lambda s: _hot_list[s]["expiry"])
        _hot_list.pop(oldest, None)
    _hot_list[symbol] = {
        "box_high": box["box_high"],
        "box_low": box["box_low"],
        "base_volume": box["base_volume"],
        "expiry": time.time() + HOT_LIST_TTL_SEC,
    }
    log.debug("HOT+ | %s | range=%.3f%% | baseVol=%.2f",
              symbol, box["box_range_pct"], box["base_volume"])


async def scan_hot_list(session):
    now = time.time()
    expired = [s for s, v in _hot_list.items() if v["expiry"] < now]
    for s in expired:
        _hot_list.pop(s, None)

    count = 0
    for symbol, box in list(_hot_list.items()):
        if count >= HOT_LIST_BATCH:
            break
        if now < _cooldown_until.get(symbol, 0):
            continue
        count += 1

        try:
            candles = await fetch_candles(session, symbol, limit=2)
        except Exception as exc:
            log.debug("hot candles fail %s: %s", symbol, exc)
            continue
        if not candles:
            continue

        live = candles[-1]
        trig = mm.evaluate_ignition_trigger(
            live, box["box_high"], box["box_low"], box["base_volume"],
        )
        if not trig["is_ignition"]:
            continue

        entered = await try_enter(session, symbol, trig["direction"], live,
                                  box["box_high"], box["box_low"])
        if entered:
            return


# =============================================================================
# WATCHDOG
# =============================================================================
async def _latest_close(session, symbol):
    candles = await fetch_candles(session, symbol, limit=2)
    if not candles:
        return None
    try:
        return float(candles[-1][4])
    except (IndexError, TypeError, ValueError):
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
        current_price=current, direction=pos["direction"],
        peak_net=pos["peak_net"], elapsed_seconds=elapsed,
        box_high=pos["box_high"], box_low=pos["box_low"],
    )
    pos["peak_net"] = state["updated_peak_net"]

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
        direction=pos["direction"], peak_net=pos["peak_net"],
        elapsed_seconds=elapsed,
        box_high=pos["box_high"], box_low=pos["box_low"],
    )
    pos["peak_net"] = state["updated_peak_net"]

    if not state["should_exit"]:
        return

    log.info(
        "PAPER EXIT | %s %s | %s | net=%.3f%% | peak=%.3f%%",
        symbol, pos["direction"], state["exit_reason"],
        state["net_pnl"], state["updated_peak_net"],
    )
    _record_result(state["net_pnl"], state["exit_reason"])
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _paper_pos = None


# =============================================================================
# BACKGROUND REFRESH
# =============================================================================
async def background_refresh(session):
    while True:
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)
        try:
            await refresh_contracts(session)
            await refresh_universe(session)
        except Exception as exc:
            log.warning("Background refresh error: %s", exc)


# =============================================================================
# HEARTBEAT
# =============================================================================
def _heartbeat():
    global _last_heartbeat
    if time.time() - _last_heartbeat < HEARTBEAT_SEC:
        return
    _last_heartbeat = time.time()
    log.info(
        "HEARTBEAT | universe=%d hot=%d active=%s paper=%s | streak W=%d L=%d live=%s | trades=%d",
        len(_universe), len(_hot_list),
        _active_pos is not None, _paper_pos is not None,
        _streak["wins"], _streak["losses"], _streak["live_activated"],
        _streak["trades"],
    )


# =============================================================================
# MAIN
# =============================================================================
async def main():
    _start_keepalive()
    _load_streak()
    log.info(
        "Startup | mode=%s | streak W=%d L=%d trades=%d | "
        "box<=%.2f%% | frag>=%.2f | spread<=%.2f%% | minSideDepth=$%.0f",
        "LIVE" if _streak["live_activated"] else "PAPER",
        _streak["wins"], _streak["losses"], _streak["trades"],
        mm.BOX_RANGE_MAX_PCT, mm.DEPTH_FRAGILITY_MIN,
        mm.MAX_SPREAD_PCT, mm.MIN_SIDE_DEPTH_USD,
    )

    connector = aiohttp.TCPConnector(limit=30, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        await enforce_one_way(session)
        await refresh_contracts(session)
        await refresh_universe(session)

        asyncio.create_task(background_refresh(session))

        log.info("Main loop started | universe=%d", len(_universe))

        while True:
            loop_start = time.time()

            try:
                if _active_pos is not None:
                    await manage_live_position(session)
                elif _paper_pos is not None:
                    await manage_paper_position(session)
                else:
                    await scan_hot_list(session)
                    if _active_pos is None and _paper_pos is None:
                        await scan_universe_batch(session)
            except Exception as exc:
                log.error("Loop error: %s", exc)

            _heartbeat()
            elapsed = time.time() - loop_start
            await asyncio.sleep(max(0.0, PULSE_SEC - elapsed))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested.")
    except Exception as exc:
        log.critical("Fatal: %s", exc, exc_info=True)

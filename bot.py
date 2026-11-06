#!/usr/bin/env python3
"""
bot.py
======
Coiled Spring Breakout | Bitget UTA V3 | Render Free Tier.

Architecture:
    - Daemonized keep-alive HTTP server on :10000
    - Bitget UTA V3 signed HTTP client (HMAC-SHA256 / Base64)
    - Background 8-exchange 24h volume cache refreshed every 300 s
    - Rotating, rate-limited candidate scanner
    - 4-second watchdog applying the asymmetric risk ladder
    - Persistent paper-gauntlet streak (streak.json) gates live capital

Dependencies: aiohttp>=3.9.0 and the Python standard library only.
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
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

import market_math as mm

# =============================================================================
# CONFIG
# =============================================================================
API_BASE = "https://api.bitget.com"
PORT = 10000
PRODUCT_TYPE = "USDT-FUTURES"
LEVERAGE = 5
MIN_NOTIONAL = 5.0
MARGIN_USE_RATIO = 0.90

BOX_CANDLES = 30
PULSE_SEC = 4
UNIVERSE_REFRESH_SEC = 300
UNIVERSE_MIN_VOL_USD = 1_000_000.0

SCAN_BATCH = 12
SCAN_MIN_INTERVAL_SEC = 60.0

STREAK_FILE = "streak.json"
PAPER_WINS_REQUIRED = 8

DEFAULT_HEADERS = {"User-Agent": "coil-bot/1.0"}

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
    raise RuntimeError(f"Missing required environment variable: {names}")


API_KEY = _env("BITGET_API_KEY", "API_KEY")
SECRET_KEY = _env("BITGET_API_SECRET", "SECRET_KEY")
PASSPHRASE = _env("BITGET_API_PASSPHRASE", "PASSPHRASE")


# =============================================================================
# KEEP-ALIVE HTTP SERVER
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
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("Keep-alive HTTP server listening on :%d", PORT)


# =============================================================================
# BITGET SIGNING + HTTP
# =============================================================================
def _sign(timestamp: str, method: str, path: str, query: str, body: str) -> str:
    msg = timestamp + method.upper() + path
    if query:
        msg += "?" + query
    msg += body
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


async def _request(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    *,
    query: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    signed: bool = True,
    retries: int = 4,
) -> Dict[str, Any]:
    query = query or {}
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    body_str = ""
    if method.upper() == "POST" and body:
        body_str = json.dumps(body, separators=(",", ":"))

    for attempt in range(retries):
        ts = str(int(time.time() * 1000))
        headers = {"Content-Type": "application/json", "locale": "en-US"}
        if signed:
            headers.update({
                "ACCESS-KEY": API_KEY,
                "ACCESS-SIGN": _sign(ts, method, path, qs, body_str),
                "ACCESS-TIMESTAMP": ts,
                "ACCESS-PASSPHRASE": PASSPHRASE,
            })

        url = API_BASE + path + (f"?{qs}" if qs else "")
        try:
            async with session.request(
                method,
                url,
                headers=headers,
                data=body_str if body_str else None,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                if resp.status == 429:
                    await asyncio.sleep((2 ** attempt) + 1)
                    continue
                if resp.status >= 500:
                    await asyncio.sleep((2 ** attempt) + 1)
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    log.error("Non-JSON response [%s %s] status=%s body=%s",
                              method, path, resp.status, text[:160])
                    return {"code": "JSON_ERROR", "msg": text[:160]}
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("Network error [%s %s]: %s", method, path, exc)
            await asyncio.sleep((2 ** attempt) + 1)

    return {"code": "RETRY_EXHAUSTED", "msg": "max retries exceeded"}


async def _get_json(session: aiohttp.ClientSession, url: str,
                    timeout: float = 10.0) -> Any:
    """Unauthenticated GET helper for third-party exchange tickers."""
    try:
        async with session.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception as exc:
        log.debug("External fetch fail %s: %s", url, exc)
        return None


# =============================================================================
# STATE
# =============================================================================
_contracts: Dict[str, Dict[str, Any]] = {}
_universe: List[str] = []
_last_scan: Dict[str, float] = {}
_scan_idx = 0
_streak: Dict[str, Any] = {
    "wins": 0,
    "losses": 0,
    "live_activated": False,
    "trades": 0,
}


def _load_streak() -> None:
    try:
        with open(STREAK_FILE, "r") as f:
            data = json.load(f)
        _streak["wins"] = int(data.get("wins", 0))
        _streak["losses"] = int(data.get("losses", 0))
        _streak["live_activated"] = bool(data.get("live_activated", False))
        _streak["trades"] = int(data.get("trades", 0))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def _save_streak() -> None:
    try:
        with open(STREAK_FILE, "w") as f:
            json.dump(_streak, f)
    except OSError as exc:
        log.error("Failed to persist streak: %s", exc)


def _record_paper_trade(net_pct: float) -> None:
    _streak["trades"] += 1
    if net_pct > 0:
        _streak["wins"] += 1
        _streak["losses"] = 0
    elif net_pct < 0:
        _streak["losses"] += 1
        _streak["wins"] = 0
    # net_pct == 0.0 (breakeven) preserves the streak

    if not _streak["live_activated"] and _streak["wins"] >= PAPER_WINS_REQUIRED:
        _streak["live_activated"] = True
        log.info("*** PAPER GAUNTLET PASSED — LIVE CAPITAL ACTIVATED ***")

    _save_streak()
    log.info(
        "PAPER | net=%.3f%% | wins=%d losses=%d live=%s trades=%d",
        net_pct, _streak["wins"], _streak["losses"],
        _streak["live_activated"], _streak["trades"],
    )


# =============================================================================
# ONE-WAY POSITION MODE (startup)
# =============================================================================
async def enforce_one_way(session: aiohttp.ClientSession) -> None:
    res = await _request(
        session, "POST", "/api/v3/account/set-hold-mode",
        body={"holdMode": "one_way_mode"},
    )
    if res.get("code") == "00000":
        log.info("One-way mode confirmed via V3 set-hold-mode.")
        return

    log.warning("V3 set-hold-mode failed (%s) — trying V2 fallback",
                res.get("msg"))
    for mode in ("single_hold", "one_way_mode"):
        res = await _request(
            session, "POST", "/api/v2/mix/account/set-position-mode",
            body={"productType": PRODUCT_TYPE, "posMode": mode},
        )
        if res.get("code") == "00000":
            log.info("One-way mode set via V2 fallback (posMode=%s).", mode)
            return
        log.warning("V2 posMode=%s failed: %s", mode, res.get("msg"))

    log.warning("Could not enforce one-way mode — continuing anyway "
                "(may cause Error 40774).")


# =============================================================================
# CONTRACT RULES CACHE
# =============================================================================
async def refresh_contracts(session: aiohttp.ClientSession) -> None:
    data = await _request(
        session, "GET", "/api/v2/mix/market/contracts",
        query={"productType": PRODUCT_TYPE},
        signed=False,
    )
    if data.get("code") != "00000":
        log.warning("Contract refresh failed: %s", data.get("msg"))
        return

    new_cache: Dict[str, Dict[str, Any]] = {}
    for c in data.get("data", []):
        sym = c.get("symbol", "")
        if not sym or not sym.endswith("USDT"):
            continue
        try:
            new_cache[sym] = {
                "volumePlace": int(float(c.get("volumePlace") or 0)),
                "pricePlace": int(float(c.get("pricePlace") or 0)),
                "sizeMultiplier": float(c.get("sizeMultiplier") or 0),
                "minOrderVolume": float(c.get("minTradeNum") or 0),
                "minNotional": float(c.get("minTradeUSDT") or 5.0),
                "maxLever": int(float(c.get("maxLever") or 1)),
            }
        except (TypeError, ValueError):
            continue

    _contracts.clear()
    _contracts.update(new_cache)
    log.info("Contract cache refreshed: %d USDT symbols", len(_contracts))


# =============================================================================
# 8-EXCHANGE VOLUME AGGREGATION
# =============================================================================
def _norm_symbol(sym: str) -> str:
    """Normalise exchange-specific symbols to the canonical BTCUSDT form."""
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


async def _vol_bitget(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session,
        API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}",
    )
    if not isinstance(d, dict) or d.get("code") != "00000":
        return out
    for t in d.get("data", []):
        sym = t.get("symbol", "")
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("usdtVolume") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_binance(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(session, "https://fapi.binance.com/fapi/v1/ticker/24hr")
    if not isinstance(d, list):
        return out
    for t in d:
        sym = _norm_symbol(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("quoteVolume") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_bybit(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session, "https://api.bybit.com/v5/market/tickers?category=linear",
    )
    if not isinstance(d, dict) or d.get("retCode") != 0:
        return out
    for t in d.get("result", {}).get("list", []):
        sym = _norm_symbol(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("turnover24h") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_okx(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session, "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
    )
    if not isinstance(d, dict) or d.get("code") != "0":
        return out
    for t in d.get("data", []):
        inst = t.get("instId", "")
        if "USDT-SWAP" not in inst:
            continue
        sym = _norm_symbol(inst)
        try:
            base_vol = float(t.get("volCcy24h") or 0)
            last = float(t.get("last") or 0)
            usd = base_vol * last
            out[sym] = out.get(sym, 0.0) + usd
        except (TypeError, ValueError):
            pass
    return out


async def _vol_gate(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session, "https://api.gateio.ws/api/v4/futures/usdt/tickers",
    )
    if not isinstance(d, list):
        return out
    for t in d:
        sym = _norm_symbol(t.get("contract", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("volume_24h_quote") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_kucoin(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session, "https://api-futures.kucoin.com/api/v1/contracts/active",
    )
    if not isinstance(d, dict) or d.get("code") != "200000":
        return out
    for t in d.get("data", []):
        sym = _norm_symbol(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("turnoverOf24h") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_mexc(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session, "https://contract.mexc.com/api/v1/contract/ticker",
    )
    if not isinstance(d, dict) or not d.get("success"):
        return out
    for t in d.get("data", []):
        sym = _norm_symbol(t.get("symbol", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("amount24") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_htx(session: aiohttp.ClientSession) -> Dict[str, float]:
    out: Dict[str, float] = {}
    d = await _get_json(
        session,
        "https://api.hbdm.com/linear-swap-ex/market/tickers?business_type=swap",
    )
    if not isinstance(d, dict) or d.get("status") != "ok":
        return out
    for t in d.get("data", []):
        sym = _norm_symbol(t.get("contract_code", ""))
        if sym.endswith("USDT"):
            try:
                out[sym] = out.get(sym, 0.0) + float(t.get("trade_turnover") or 0)
            except (TypeError, ValueError):
                pass
    return out


async def refresh_universe(session: aiohttp.ClientSession) -> None:
    tasks = [
        _vol_bitget(session),
        _vol_binance(session),
        _vol_bybit(session),
        _vol_okx(session),
        _vol_gate(session),
        _vol_kucoin(session),
        _vol_mexc(session),
        _vol_htx(session),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    agg: Dict[str, float] = {}
    exchanges_ok = 0
    for r in results:
        if isinstance(r, dict) and r:
            exchanges_ok += 1
            for sym, vol in r.items():
                agg[sym] = agg.get(sym, 0.0) + vol

    tradeable = set(_contracts.keys())
    filtered = [
        s for s, v in agg.items()
        if s in tradeable and v >= UNIVERSE_MIN_VOL_USD
    ]
    filtered.sort(key=lambda s: agg[s], reverse=True)

    _universe.clear()
    _universe.extend(filtered)
    log.info("Universe refreshed: %d symbols (>= $%.1fM across %d/8 exchanges)",
             len(_universe), UNIVERSE_MIN_VOL_USD / 1e6, exchanges_ok)


# =============================================================================
# ACCOUNT / POSITION
# =============================================================================
async def get_usdt_available(session: aiohttp.ClientSession) -> float:
    d = await _request(session, "GET", "/api/v3/account/assets")
    if d.get("code") == "00000":
        for a in d.get("data", {}).get("assets", []) or []:
            if a.get("coin") == "USDT":
                try:
                    return float(a.get("available") or 0)
                except (TypeError, ValueError):
                    return 0.0
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


async def get_position(session: aiohttp.ClientSession,
                       symbol: str) -> Optional[Dict[str, Any]]:
    d = await _request(
        session, "GET", "/api/v3/position/current-position",
        query={"category": PRODUCT_TYPE, "symbol": symbol},
    )
    if d.get("code") != "00000":
        return None
    for p in d.get("data") or []:
        try:
            total = float(p.get("total") or 0)
        except (TypeError, ValueError):
            total = 0.0
        if total > 0:
            try:
                entry = float(p.get("entryPrice") or 0)
            except (TypeError, ValueError):
                entry = 0.0
            try:
                upnl = float(p.get("unrealizedPnl") or 0)
            except (TypeError, ValueError):
                upnl = 0.0
            return {
                "total": total,
                "posSide": p.get("posSide", ""),
                "entryPrice": entry,
                "unrealizedPnl": upnl,
            }
    return None


# =============================================================================
# MARKET DATA
# =============================================================================
async def fetch_candles_bitget(session: aiohttp.ClientSession,
                               symbol: str) -> Optional[List[List[str]]]:
    d = await _request(
        session, "GET", "/api/v2/mix/market/candles",
        query={
            "symbol": symbol,
            "productType": PRODUCT_TYPE,
            "granularity": "1m",
            "limit": str(BOX_CANDLES + 1),
        },
        signed=False,
    )
    if d.get("code") != "00000":
        return None
    candles = d.get("data")
    if not isinstance(candles, list) or len(candles) < BOX_CANDLES + 1:
        return None
    return candles


async def fetch_candles_binance(session: aiohttp.ClientSession,
                                symbol: str) -> Optional[List[List[str]]]:
    try:
        async with session.get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={"symbol": symbol, "interval": "1m", "limit": BOX_CANDLES + 1},
            headers=DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception as exc:
        log.debug("Binance candles fail %s: %s", symbol, exc)
        return None

    if not isinstance(data, list) or len(data) < BOX_CANDLES + 1:
        return None

    out: List[List[str]] = []
    for k in data:
        try:
            out.append([
                str(k[0]),       # ts
                k[1],            # open
                k[2],            # high
                k[3],            # low
                k[4],            # close
                k[5],            # base volume
                k[7],            # quote volume
            ])
        except (IndexError, TypeError):
            return None
    return out


async def fetch_candles(session: aiohttp.ClientSession,
                        symbol: str) -> Optional[List[List[str]]]:
    c = await fetch_candles_bitget(session, symbol)
    if c:
        return c
    return await fetch_candles_binance(session, symbol)


async def fetch_depth(session: aiohttp.ClientSession, symbol: str
                      ) -> Optional[Tuple[List[List[str]], List[List[str]], float]]:
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
    except (TypeError, ValueError, IndexError):
        return None
    if best_bid <= 0 or best_ask <= 0:
        return None
    mid = (best_bid + best_ask) / 2.0
    return bids, asks, mid


# =============================================================================
# ORDER EXECUTION
# =============================================================================
async def place_order(session: aiohttp.ClientSession,
                      symbol: str, side: str, qty_str: str,
                      reduce_only: bool = False) -> Optional[str]:
    body: Dict[str, Any] = {
        "category": PRODUCT_TYPE,
        "symbol": symbol,
        "qty": qty_str,
        "side": side,
        "orderType": "market",
        "reduceOnly": "yes" if reduce_only else "no",
    }
    if not reduce_only:
        body["tradeSide"] = "open"

    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        oid = (res.get("data") or {}).get("orderId")
        log.info("ORDER OK | %s %s %s | id=%s",
                 symbol, side, qty_str, oid)
        return oid
    log.error("ORDER FAIL | %s %s | %s", symbol, side, res.get("msg"))
    return None


async def cancel_open_orders(session: aiohttp.ClientSession, symbol: str) -> None:
    """Best-effort cancellation before close (market orders should be a no-op)."""
    try:
        await _request(
            session, "POST", "/api/v3/trade/cancel-all-orders",
            body={"category": PRODUCT_TYPE, "symbol": symbol},
        )
    except Exception as exc:
        log.debug("cancel-all-orders fail %s: %s", symbol, exc)


async def open_position(session: aiohttp.ClientSession,
                        signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = signal["symbol"]
    contract = _contracts.get(symbol)
    if not contract:
        log.warning("Missing contract rules for %s", symbol)
        return None

    balance = await get_usdt_available(session)
    if balance <= 0:
        log.warning("No USDT balance available for %s", symbol)
        return None

    price = signal["live_close"]
    sizing = mm.calculate_order_qty(
        balance=balance,
        price=price,
        leverage=LEVERAGE,
        volume_place=contract["volumePlace"],
        min_order_volume=contract["minOrderVolume"],
        min_notional=MIN_NOTIONAL,
        margin_use_ratio=MARGIN_USE_RATIO,
    )
    if not sizing["valid"]:
        log.warning("Sizing rejected | %s | reason=%s | notional=%.4f",
                    symbol, sizing["reason"], sizing["notional"])
        return None

    side = "buy" if signal["direction"] == "long" else "sell"
    oid = await place_order(session, symbol, side, sizing["qty_str"],
                            reduce_only=False)
    if not oid:
        return None

    log.info("OPEN | %s %s @ %.6f | qty=%s | notional=%.4f USDT",
             symbol, signal["direction"].upper(), price,
             sizing["qty_str"], sizing["notional"])

    return {
        "symbol": symbol,
        "direction": signal["direction"],
        "entry": price,
        "qty_str": sizing["qty_str"],
        "qty_float": sizing["qty_float"],
        "box_high": signal["box_high"],
        "box_low": signal["box_low"],
        "opened_at": time.time(),
        "peak_net": -999.0,
        "paper": False,
        "order_id": oid,
    }


async def close_position(session: aiohttp.ClientSession,
                         pos: Dict[str, Any], reason: str) -> bool:
    symbol = pos["symbol"]
    live = await get_position(session, symbol)
    if not live or live["total"] <= 0:
        log.info("No live position for %s (already closed)", symbol)
        return True

    await cancel_open_orders(session, symbol)

    vp = _contracts.get(symbol, {}).get("volumePlace", 0)
    qty_str = f"{live['total']:.{vp}f}"
    close_side = "sell" if pos["direction"] == "long" else "buy"

    oid = await place_order(session, symbol, close_side, qty_str,
                            reduce_only=True)
    if oid:
        log.info("CLOSE OK | %s | reason=%s | size=%s",
                 symbol, reason, qty_str)
        return True

    log.error("CLOSE FAIL | %s | reason=%s", symbol, reason)
    return False


# =============================================================================
# SIGNAL SCANNING
# =============================================================================
def _should_scan(symbol: str, min_interval: float = SCAN_MIN_INTERVAL_SEC) -> bool:
    now = time.time()
    if now - _last_scan.get(symbol, 0.0) < min_interval:
        return False
    _last_scan[symbol] = now
    return True


async def scan_symbol(session: aiohttp.ClientSession,
                      symbol: str) -> Optional[Dict[str, Any]]:
    candles = await fetch_candles(session, symbol)
    if not candles:
        return None

    box = candles[:-1]
    live = candles[-1]

    comp = mm.calculate_box_compression(box)
    if not comp["is_compressed"]:
        return None

    trig = mm.check_ignite_trigger(
        candles,
        comp["box_high"],
        comp["box_low"],
        comp["base_volume"],
    )
    if not trig["is_valid"]:
        return None

    depth = await fetch_depth(session, symbol)
    if depth is None:
        return None
    bids, asks, mid = depth
    imb = mm.calculate_depth_imbalance(bids, asks, mid)

    direction = trig["direction"]
    if direction == "long":
        if not imb["favorable"]:
            return None
    else:  # short
        if imb["ratio"] <= 0:
            return None
        if (1.0 / imb["ratio"]) < 1.5:
            return None

    try:
        live_close = float(live[4])
    except (TypeError, ValueError, IndexError):
        return None

    return {
        "symbol": symbol,
        "direction": direction,
        "box_high": comp["box_high"],
        "box_low": comp["box_low"],
        "box_range_pct": comp["box_range_pct"],
        "base_volume": comp["base_volume"],
        "live_close": live_close,
        "volume_ratio": trig["volume_ratio"],
        "breakout_price": trig["breakout_price"],
        "chase_pct": trig["chase_distance_pct"],
        "depth_ratio": imb["ratio"],
        "ts": time.time(),
    }


async def scan_batch(session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """Rotate through the universe in small batches, honouring rate limits."""
    global _scan_idx
    if not _universe:
        return None

    n = len(_universe)
    batch: List[str] = []
    for _ in range(min(SCAN_BATCH, n)):
        batch.append(_universe[_scan_idx % n])
        _scan_idx += 1

    for symbol in batch:
        if not _should_scan(symbol):
            continue
        try:
            signal = await scan_symbol(session, symbol)
            if signal:
                return signal
        except Exception as exc:
            log.debug("scan_symbol error %s: %s", symbol, exc)
    return None


# =============================================================================
# WATCHDOG (4-SECOND PULSE)
# =============================================================================
async def manage_position(session: aiohttp.ClientSession,
                          pos: Dict[str, Any]) -> bool:
    """
    Returns True if the position was closed (or no longer exists),
    False if it should remain open.
    """
    symbol = pos["symbol"]

    if pos["paper"]:
        candles = await fetch_candles(session, symbol)
        if not candles:
            return False
        try:
            current = float(candles[-1][4])
        except (TypeError, ValueError, IndexError):
            return False
        entry = pos["entry"]
    else:
        live = await get_position(session, symbol)
        if not live or live["total"] <= 0:
            log.info("Live position for %s is gone", symbol)
            return True
        entry = live["entryPrice"] if live["entryPrice"] > 0 else pos["entry"]
        candles = await fetch_candles(session, symbol)
        current = entry
        if candles:
            try:
                current = float(candles[-1][4])
            except (TypeError, ValueError, IndexError):
                current = entry

    if current <= 0 or entry <= 0:
        return False

    elapsed = time.time() - pos["opened_at"]
    state = mm.evaluate_ratchet_state(
        entry_price=entry,
        current_price=current,
        direction=pos["direction"],
        peak_net=pos["peak_net"],
        elapsed_seconds=elapsed,
        box_high=pos["box_high"],
        box_low=pos["box_low"],
    )

    pos["peak_net"] = state["peak_net"]
    action = state["action"]

    if action == "HOLD":
        return False

    if pos["paper"]:
        log.info(
            "PAPER EXIT | %s %s | action=%s | net=%.3f%% | peak=%.3f%%",
            symbol, pos["direction"].upper(), action,
            state["net_pct"], state["peak_net"],
        )
        _record_paper_trade(state["net_pct"])
        return True

    closed = await close_position(session, pos, action)
    if closed:
        log.info(
            "LIVE EXIT | %s %s | action=%s | net=%.3f%% | peak=%.3f%%",
            symbol, pos["direction"].upper(), action,
            state["net_pct"], state["peak_net"],
        )
    return closed


# =============================================================================
# BACKGROUND REFRESH WORKER
# =============================================================================
async def background_refresh(session: aiohttp.ClientSession) -> None:
    while True:
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)
        try:
            await refresh_contracts(session)
            await refresh_universe(session)
        except Exception as exc:
            log.warning("Background refresh error: %s", exc)


# =============================================================================
# MAIN
# =============================================================================
async def main() -> None:
    _start_keepalive()
    _load_streak()
    log.info(
        "Streak loaded | wins=%d losses=%d live=%s trades=%d",
        _streak["wins"], _streak["losses"],
        _streak["live_activated"], _streak["trades"],
    )

    connector = aiohttp.TCPConnector(limit=30, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, headers=DEFAULT_HEADERS,
    ) as session:
        await enforce_one_way(session)

        # Prime the caches once, synchronously, before main loop starts.
        await refresh_contracts(session)
        await refresh_universe(session)

        bg_task = asyncio.create_task(background_refresh(session))

        if not _contracts:
            log.warning("No contracts cached — universe will be empty until "
                        "the background task succeeds.")
        log.info("Main loop started | universe=%d", len(_universe))

        open_positions: List[Dict[str, Any]] = []

        while True:
            loop_start = time.time()

            # ----- 1) Manage open positions on every pulse -----
            still_open: List[Dict[str, Any]] = []
            for pos in open_positions:
                try:
                    closed = await manage_position(session, pos)
                    if not closed:
                        still_open.append(pos)
                except Exception as exc:
                    log.error("Manage error %s: %s", pos.get("symbol"), exc)
                    still_open.append(pos)
            open_positions = still_open

            # ----- 2) Scan for new signals (single-slot concurrency) -----
            if len(open_positions) < 1:
                try:
                    signal = await scan_batch(session)
                except Exception as exc:
                    log.error("scan_batch error: %s", exc)
                    signal = None

                if signal:
                    log.info(
                        "SIGNAL | %s %s | box=%.3f%% | vol=%.2fx | "
                        "chase=%.3f%% | depth=%.2f",
                        signal["symbol"], signal["direction"].upper(),
                        signal["box_range_pct"], signal["volume_ratio"],
                        signal["chase_pct"], signal["depth_ratio"],
                    )

                    if _streak["live_activated"]:
                        new_pos = await open_position(session, signal)
                        if new_pos:
                            open_positions.append(new_pos)
                    else:
                        paper_pos: Dict[str, Any] = {
                            "symbol": signal["symbol"],
                            "direction": signal["direction"],
                            "entry": signal["live_close"],
                            "box_high": signal["box_high"],
                            "box_low": signal["box_low"],
                            "opened_at": time.time(),
                            "peak_net": -999.0,
                            "paper": True,
                        }
                        open_positions.append(paper_pos)
                        log.info(
                            "PAPER OPEN | %s %s @ %.6f | wins=%d/%d",
                            paper_pos["symbol"], paper_pos["direction"].upper(),
                            paper_pos["entry"],
                            _streak["wins"], PAPER_WINS_REQUIRED,
                        )

            # ----- 3) Sleep to maintain the 4-second pulse -----
            elapsed = time.time() - loop_start
            await asyncio.sleep(max(0.0, PULSE_SEC - elapsed))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested.")
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)

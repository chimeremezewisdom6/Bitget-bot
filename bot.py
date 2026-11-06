#!/usr/bin/env python3
"""
bot.py — Momentum Learning Engine | Bitget UTA V3 | Render Free Tier.

v2026.11.20
  Phase 1 (first 2h): OBSERVE every coin spike, measure reversal quietness.
  Phase 2 (after):    TRADE only coins with proven asymmetry >= 4:1.
  Exit: momentum death or symmetric reversal. No stop loss. No profit target.
  Report: copy-pasteable profile summary every 15 min.
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
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

import aiohttp

import market_math as mm

API_BASE = "https://api.bitget.com"
PORT = 10000
PRODUCT_TYPE = "USDT-FUTURES"
LEVERAGE = 5
PULSE_SEC = 4.0
VELOCITY_SWEEP_SEC = 10.0
VELOCITY_HISTORY_KEEP_SEC = 600.0

UNIVERSE_REFRESH_SEC = 300
CONTRACTS_REFRESH_SEC = 900
UNIVERSE_MIN_VOL_USD = 1_000_000.0

LEARNING_PHASE_SEC = 7200.0
REPORT_INTERVAL_SEC = 900.0
HEARTBEAT_SEC = 60.0
SYMBOL_COOLDOWN_SEC = 120.0
PAPER_WINS_REQUIRED = 8

STREAK_FILE = "streak.json"
PROFILES_FILE = "momentum_profiles.json"

_EXPECTED_MM_VERSION = "2026.11.20"

_STOCK_TOKENS = {
    "AAPLUSDT", "MSFTUSDT", "METAUSDT", "AMZNUSDT", "GOOGUSDT",
    "GOOGLUSDT", "TSLAUSDT", "NVDAUSDT", "AVGOUSDT", "ORCLUSDT",
    "PLTRUSDT", "COINUSDT", "MSTRUSDT", "HOODUSDT", "OPENAIUSDT",
    "LLYUSDT", "MELIUSDT", "METUSDT",
    "SPYUSDT", "QQQUSDT", "IWMUSDT",
    "TQQQUSDT", "SPXLUSDT", "TNAUSDT", "FNGUUSDT", "TSLLUSDT",
    "LABUUSDT", "YINNUSDT",
    "SQQQUSDT", "SOXSUSDT", "SPXSUSDT", "SDOWUSDT", "TZAUSDT",
    "FNGDUSDT", "TSLSUSDT", "LABDUSDT", "YANGUSDT",
    "UVXYUSDT", "VXXUSDT", "UVIXUSDT",
    "XLKUSDT", "SOXLUSDT", "SMHUSDT",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("momentum")


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
# BITGET API CLIENT
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
            headers={"User-Agent": "momentum-bot/1.0"},
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
_last_universe_exchange_count = 0

# Learning state
_coin_profiles: Dict[str, dict] = {}
_price_history: Dict[str, list] = {}
_active_spikes: Dict[str, dict] = {}
_learning_started_at = time.time()
_trading_enabled = False

# Trading state
_active_pos = None
_paper_pos = None
_cooldown_until: Dict[str, float] = {}
_streak = {"wins": 0, "losses": 0, "live_activated": False, "trades": 0}

_last_heartbeat = 0.0
_last_report = 0.0

_diag = {
    "spikes_detected": 0,
    "spikes_finalized": 0,
    "sweep_fails": 0,
    "tradable_skips_book": 0,
    "tradable_skips_spread": 0,
    "entries": 0,
    "exit_momentum_dead": 0,
    "exit_symmetric": 0,
    "exit_hard": 0,
    "exit_time": 0,
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
# STREAK / PROFILES PERSISTENCE
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
        log.error("Streak save failed: %s", exc)


def _record_result(net_pnl, exit_reason):
    _streak["trades"] += 1
    if net_pnl > 0:
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


def _load_profiles():
    global _coin_profiles, _learning_started_at
    try:
        with open(PROFILES_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _coin_profiles = data.get("coins", {}) or {}
            _learning_started_at = float(data.get("learning_started_at",
                                                   time.time()))
            log.info("Loaded %d coin profiles from %s (learning started %.0fs ago)",
                     len(_coin_profiles), PROFILES_FILE,
                     time.time() - _learning_started_at)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        _coin_profiles = {}
        _learning_started_at = time.time()


def _save_profiles():
    tmp = PROFILES_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump({
                "learning_started_at": _learning_started_at,
                "last_updated": time.time(),
                "coins": _coin_profiles,
            }, f, indent=2)
        os.replace(tmp, PROFILES_FILE)
    except OSError as exc:
        log.error("Profiles save failed: %s", exc)


# =============================================================================
# SPIKE WINDOW TRACKING
# =============================================================================
def _new_spike_window(price, vel, ts):
    return {
        "start_ts": ts,
        "start_price": price,
        "peak_velocity": vel["velocity_multiple"],
        "peak_price": price,
        "peak_ts": ts,
        "peak_baseline": vel["baseline_pct_per_min"],
        "max_reversal_velocity": 0.0,
        "max_reversal_price": 0.0,
        "settled_streak": 0,
        "last_update_ts": ts,
    }


def _update_spike_window(window, price, vel, ts):
    if vel["reason"] != "OK":
        return window

    # New peak?
    if vel["direction"] < 0 and vel["velocity_multiple"] > window["peak_velocity"]:
        window["peak_velocity"] = vel["velocity_multiple"]
        window["peak_price"] = price
        window["peak_ts"] = ts
        window["peak_baseline"] = vel["baseline_pct_per_min"]
        window["settled_streak"] = 0
    # Reversal phase?
    elif vel["direction"] > 0 and vel["velocity_multiple"] > window["max_reversal_velocity"]:
        window["max_reversal_velocity"] = vel["velocity_multiple"]
        window["max_reversal_price"] = price
        # Reset settle streak since price is moving again
        window["settled_streak"] = 0
    # Settled?
    elif vel["velocity_multiple"] < mm.SPIKE_SETTLED_RATIO:
        window["settled_streak"] += 1
    else:
        window["settled_streak"] = 0

    window["last_update_ts"] = ts
    return window


def _should_finalize(window, ts):
    # Hard timeout
    if ts - window["start_ts"] >= mm.SPIKE_WINDOW_SEC:
        return True
    # Settled (velocity back below 2x for N consecutive checks, min 60s after peak)
    if (ts - window["peak_ts"] >= mm.SPIKE_MIN_SETTLE_AFTER_PEAK_SEC
            and window["settled_streak"] >= mm.SPIKE_SETTLED_CONSECUTIVE):
        return True
    return False


def _finalize_spike(symbol):
    window = _active_spikes.pop(symbol, None)
    if not window:
        return

    if window["peak_velocity"] < mm.SPIKE_VELOCITY_THRESHOLD:
        return

    reversal_vel = window["max_reversal_velocity"]
    if reversal_vel <= 0.01:
        reversal_vel = 0.01

    asymmetry = window["peak_velocity"] / reversal_vel

    giveback_pct = 0.0
    if window["max_reversal_price"] > 0 and window["peak_price"] > 0:
        giveback_pct = (
            (window["max_reversal_price"] - window["peak_price"])
            / window["peak_price"] * 100.0
        )

    event = {
        "ts_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(window["start_ts"])),
        "peak_velocity_multiple": round(window["peak_velocity"], 2),
        "peak_baseline_pct_per_min": round(window["peak_baseline"], 3),
        "peak_price": window["peak_price"],
        "spike_duration_sec": int(window["peak_ts"] - window["start_ts"]),
        "reversal_velocity_multiple": round(reversal_vel, 2),
        "reversal_giveback_pct": round(giveback_pct, 2),
        "reversal_duration_sec": int(
            window["last_update_ts"] - window["peak_ts"]),
        "asymmetry": round(asymmetry, 2),
        "verdict": mm.verdict_for(asymmetry),
    }

    profile = _coin_profiles.setdefault(symbol, {
        "events": [], "median_asymmetry": 0.0, "verdict": "NO_DATA",
    })
    profile["events"].append(event)

    asyms = sorted(e["asymmetry"] for e in profile["events"])
    n = len(asyms)
    if n % 2 == 1:
        median = asyms[n // 2]
    else:
        median = (asyms[n // 2 - 1] + asyms[n // 2]) / 2.0
    profile["median_asymmetry"] = round(median, 2)
    profile["verdict"] = mm.verdict_for(median)

    _diag["spikes_finalized"] += 1

    log.info(
        "SPIKE_DONE | %s | peak_vel=%.1fx | rev_vel=%.1fx | asym=%.2f "
        "| verdict=%s | events=%d",
        symbol, window["peak_velocity"], reversal_vel, asymmetry,
        event["verdict"], len(profile["events"]),
    )


def _is_tradable(symbol):
    if not _trading_enabled:
        return False
    profile = _coin_profiles.get(symbol)
    if not profile:
        return False
    if profile["verdict"] != "MOMENTUM":
        return False
    if len(profile["events"]) < 1:
        return False
    return True


# =============================================================================
# UNIVERSE / CONTRACTS
# =============================================================================
async def enforce_one_way(session):
    settings = await _request(session, "GET", "/api/v3/account/settings")
    if settings.get("code") == "00000":
        data = settings.get("data") or {}
        current = data.get("holdMode") if isinstance(data, dict) else None
        if current == "one_way_mode":
            log.info("Account already in one-way mode.")
            return
    res = await _request(
        session, "POST", "/api/v3/account/set-hold-mode",
        body={"holdMode": "one_way_mode"},
    )
    if res.get("code") == "00000":
        log.info("One-way mode enforced.")
    else:
        log.warning("set-hold-mode rejected: %s", res.get("msg"))


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
    log.info("Contracts cached: %d", len(_contracts))


async def _prices_bitget(session):
    out = {}
    d = await _get_public_json(
        session,
        API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}",
    )
    if not isinstance(d, dict) or d.get("code") != "00000":
        return out
    for t in d.get("data", []) or []:
        sym = t.get("symbol", "")
        if sym.endswith("USDT"):
            try:
                p = t.get("lastPr") or t.get("last")
                if p:
                    out[sym] = float(p)
            except (TypeError, ValueError):
                pass
    return out


async def _vol_bitget(session):
    out = {}
    d = await _get_public_json(
        session,
        API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}",
    )
    if not isinstance(d, dict) or d.get("code") != "00000":
        return out
    for t in d.get("data", []) or []:
        sym = t.get("symbol", "")
        if sym.endswith("USDT"):
            try:
                out[sym] = float(t.get("usdtVolume") or 0)
            except (TypeError, ValueError):
                pass
    return out


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
    global _last_universe_exchange_count
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

    if (_last_universe_exchange_count > 0
            and ok < _last_universe_exchange_count - 1):
        log.warning("Universe refresh SKIPPED: %d/8 exchanges", ok)
        return

    filtered = []
    excluded_stock = 0
    excluded_vol = 0
    for s, v in agg.items():
        c = _contracts.get(s)
        if not c:
            continue
        if c.get("is_stock"):
            excluded_stock += 1
            continue
        if v < UNIVERSE_MIN_VOL_USD:
            excluded_vol += 1
            continue
        filtered.append(s)

    filtered.sort(key=lambda s: agg[s], reverse=True)
    _universe.clear()
    _universe.extend(filtered)
    _last_universe_exchange_count = ok
    log.info("Universe: %d symbols (>= $%.1fM, %d/8 exchanges) "
             "| excluded: %d stock, %d low-vol",
             len(_universe), UNIVERSE_MIN_VOL_USD / 1e6, ok,
             excluded_stock, excluded_vol)


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
        _active_pos = {
            "symbol": sym, "direction": "SHORT", "entry": entry,
            "opened_at": time.time(),
            "peak_price": entry, "peak_net": -999.0,
            "peak_gross": -999.0,
            "price_history": [(time.time(), entry)],
            "momentum_dead_streak": 0,
            "reversal_streak": 0,
            "paper": False, "adopted": True,
        }
        log.warning("ADOPTED orphan | %s | entry=%.6f", sym, entry)
        return


async def place_short_order(session, symbol, qty_str):
    body = {
        "category": PRODUCT_TYPE, "symbol": symbol,
        "side": "sell", "orderType": "market",
        "tradeSide": "open", "qty": qty_str, "reduceOnly": "no",
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
        "category": PRODUCT_TYPE, "symbol": symbol,
        "side": "buy", "orderType": "market",
        "tradeSide": "close", "qty": qty_str, "reduceOnly": "yes",
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
        log.info("No live position for %s", symbol)
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
# ENTRY
# =============================================================================
async def try_enter_momentum(session, symbol, entry_price, vel):
    global _active_pos, _paper_pos

    if time.time() < _cooldown_until.get(symbol, 0):
        return False

    depth = await fetch_depth(session, symbol)
    if depth is None:
        _diag["tradable_skips_book"] += 1
        return False
    bids, asks, mid = depth

    book = mm.evaluate_book(bids, asks, mid)
    if not book["is_valid"]:
        _diag["tradable_skips_book"] += 1
        log.info("SKIP book | %s | %s ratio=%.2f d_bid=%.0f",
                 symbol, book["reason"], book["depth_ratio"], book["d_bid"])
        return False

    spread = mm.evaluate_spread(bids, asks)
    if not spread["is_ok"]:
        _diag["tradable_skips_spread"] += 1
        return False

    profile = _coin_profiles.get(symbol, {})
    asym = profile.get("median_asymmetry", 0.0)

    log.info(
        "MOMENTUM ENTRY | %s | vel=%.1fx | baseline=%.2f%%/m | asym=%.2f "
        "| peak_v=%.1fx | price=%.6f",
        symbol, vel["velocity_multiple"], vel["baseline_pct_per_min"],
        asym, profile.get("events", [{}])[-1].get("peak_velocity_multiple", 0.0),
        entry_price,
    )

    if not _streak["live_activated"]:
        _diag["entries"] += 1
        _paper_pos = {
            "symbol": symbol, "direction": "SHORT",
            "entry": entry_price,
            "opened_at": time.time(),
            "peak_price": entry_price,
            "peak_net": -999.0, "peak_gross": -999.0,
            "price_history": [(time.time(), entry_price)],
            "momentum_dead_streak": 0,
            "reversal_streak": 0,
            "paper": True,
        }
        log.info("PAPER OPEN | %s SHORT @ %.6f | W=%d/%d",
                 symbol, entry_price, _streak["wins"], PAPER_WINS_REQUIRED)
        return True

    contract = _contracts.get(symbol)
    if not contract:
        return False
    balance = await get_usdt_balance(session)
    qty_str = mm.calculate_order_qty(
        balance=balance, price=entry_price, leverage=LEVERAGE,
        volume_place=contract["volumePlace"],
        min_order_volume=contract["minOrderVolume"],
        min_notional=contract["minNotional"],
    )
    if not qty_str:
        log.warning("Sizing rejected | %s | balance=%.4f", symbol, balance)
        return False

    oid = await place_short_order(session, symbol, qty_str)
    if not oid:
        return False

    _diag["entries"] += 1
    _active_pos = {
        "symbol": symbol, "direction": "SHORT",
        "entry": entry_price,
        "opened_at": time.time(),
        "peak_price": entry_price,
        "peak_net": -999.0, "peak_gross": -999.0,
        "price_history": [(time.time(), entry_price)],
        "momentum_dead_streak": 0,
        "reversal_streak": 0,
        "paper": False, "order_id": oid,
    }
    log.info("LIVE OPEN | %s SHORT @ %.6f | qty=%s",
             symbol, entry_price, qty_str)
    return True


# =============================================================================
# VELOCITY SWEEPER — THE CORE LOOP
# =============================================================================
async def velocity_sweeper_loop(session):
    global _trading_enabled, _learning_started_at

    while True:
        try:
            ts = time.time()

            # Enable trading after learning phase
            if not _trading_enabled:
                if ts - _learning_started_at >= LEARNING_PHASE_SEC:
                    _trading_enabled = True
                    log.info(
                        "*** LEARNING COMPLETE — TRADING ENABLED *** "
                        "(%d coin profiles, %d spike events)",
                        len(_coin_profiles),
                        sum(len(p.get("events", []))
                            for p in _coin_profiles.values()),
                    )

            prices = await _prices_bitget(session)
            if not prices:
                _diag["sweep_fails"] += 1
                await asyncio.sleep(VELOCITY_SWEEP_SEC)
                continue

            cutoff = ts - VELOCITY_HISTORY_KEEP_SEC

            # Update price histories
            for sym, price in prices.items():
                if sym not in _price_history:
                    _price_history[sym] = []
                _price_history[sym].append((ts, price))
                _price_history[sym] = [
                    (t, p) for t, p in _price_history[sym] if t >= cutoff
                ]

            # Compute velocity + detect spikes
            for sym in list(_price_history.keys()):
                history = _price_history[sym]
                if len(history) < mm.MIN_SAMPLES_FOR_VELOCITY:
                    continue

                vel = mm.compute_ticker_velocity(history, ts)
                current_price = history[-1][1]

                if mm.is_spike(vel):
                    if sym not in _active_spikes:
                        _active_spikes[sym] = _new_spike_window(
                            current_price, vel, ts
                        )
                        _diag["spikes_detected"] += 1
                        log.info(
                            "SPIKE_START | %s | vel=%.1fx | baseline=%.2f%%/m "
                            "| price=%.6f",
                            sym, vel["velocity_multiple"],
                            vel["baseline_pct_per_min"], current_price,
                        )
                    else:
                        _active_spikes[sym] = _update_spike_window(
                            _active_spikes[sym], current_price, vel, ts
                        )

                    # Try to enter (if tradable and no position)
                    if (_is_tradable(sym)
                            and _active_pos is None
                            and _paper_pos is None):
                        await try_enter_momentum(
                            session, sym, current_price, vel
                        )
                elif sym in _active_spikes:
                    _active_spikes[sym] = _update_spike_window(
                        _active_spikes[sym], current_price, vel, ts
                    )

            # Finalize expired/settled spikes
            for sym in list(_active_spikes.keys()):
                if _should_finalize(_active_spikes[sym], ts):
                    _finalize_spike(sym)

            # Persist periodically
            if int(ts) % 60 < VELOCITY_SWEEP_SEC:
                _save_profiles()

        except Exception as exc:
            log.warning("Sweeper error: %s", exc)
            _diag["sweep_fails"] += 1

        await asyncio.sleep(VELOCITY_SWEEP_SEC)


# =============================================================================
# POSITION MANAGEMENT — VELOCITY-BASED EXIT
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


def _update_position_and_check_exit(pos, current_price, ts):
    entry = pos["entry"]
    pos["price_history"].append((ts, current_price))
    cutoff = ts - mm.VELOCITY_HISTORY_SEC
    pos["price_history"] = [
        (t, p) for t, p in pos["price_history"] if t >= cutoff
    ]

    if current_price < pos["peak_price"]:
        pos["peak_price"] = current_price

    gross = (entry - current_price) / entry * 100.0
    net = gross - mm.FEE_ROUND_TRIP_PCT
    if net > pos["peak_net"]:
        pos["peak_net"] = net
    if gross > pos["peak_gross"]:
        pos["peak_gross"] = gross

    elapsed = ts - pos["opened_at"]

    # Hard safety
    if net <= -mm.HARD_STOP_PCT:
        return "HARD_STOP", net

    # Time cap
    if elapsed >= mm.MAX_HOLD_SEC:
        return "TIME_EXIT", net

    # Velocity checks (only after min hold)
    if elapsed >= mm.MIN_HOLD_FOR_EXIT_CHECK_SEC:
        vel = mm.compute_ticker_velocity(pos["price_history"], ts)

        # Momentum death
        if mm.check_momentum_death(vel):
            pos["momentum_dead_streak"] += 1
            if pos["momentum_dead_streak"] >= mm.MOMENTUM_DEATH_CONSECUTIVE:
                return "MOMENTUM_DEAD", net
        else:
            pos["momentum_dead_streak"] = 0

        # Symmetric reversal
        if mm.check_symmetric_reversal(vel):
            pos["reversal_streak"] += 1
            if pos["reversal_streak"] >= mm.SYMMETRIC_REVERSAL_CONSECUTIVE:
                return "SYMMETRIC_REVERSAL", net
        else:
            pos["reversal_streak"] = 0

    return None, net


async def manage_live_position(session):
    global _active_pos
    if _active_pos is None:
        return
    pos = _active_pos
    symbol = pos["symbol"]

    live = await get_position(session, symbol)
    if live is None or live["total"] <= 0:
        log.info("Position %s vanished", symbol)
        _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
        _active_pos = None
        return

    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return

    reason, net = _update_position_and_check_exit(pos, current, time.time())
    if not reason:
        return

    log.info(
        "EXIT SIGNAL | %s | %s | net=%.2f%% | peak_net=%.2f%%",
        symbol, reason, net, pos["peak_net"],
    )
    if reason == "MOMENTUM_DEAD":
        _diag["exit_momentum_dead"] += 1
    elif reason == "SYMMETRIC_REVERSAL":
        _diag["exit_symmetric"] += 1
    elif reason == "HARD_STOP":
        _diag["exit_hard"] += 1
    elif reason == "TIME_EXIT":
        _diag["exit_time"] += 1

    closed = await close_live_position(session, pos, reason)
    if closed:
        _record_result(net, reason)
        _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
        _active_pos = None


async def manage_paper_position(session):
    global _paper_pos
    if _paper_pos is None:
        return
    pos = _paper_pos
    symbol = pos["symbol"]

    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return

    reason, net = _update_position_and_check_exit(pos, current, time.time())
    if not reason:
        return

    log.info(
        "PAPER EXIT | %s | %s | gross=%.2f%% net=%.2f%% peak_net=%.2f%%",
        symbol, reason, pos["peak_gross"], net, pos["peak_net"],
    )
    if reason == "MOMENTUM_DEAD":
        _diag["exit_momentum_dead"] += 1
    elif reason == "SYMMETRIC_REVERSAL":
        _diag["exit_symmetric"] += 1
    elif reason == "HARD_STOP":
        _diag["exit_hard"] += 1
    elif reason == "TIME_EXIT":
        _diag["exit_time"] += 1

    _record_result(net, reason)
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _paper_pos = None


# =============================================================================
# REPORT LOOP — COPY-PASTEABLE
# =============================================================================
def _report_profiles():
    now = time.time()
    runtime = now - _learning_started_at
    phase = "LEARNING" if not _trading_enabled else "TRADING"

    momentum_coins = []
    noise_coins = []
    middle_coins = []
    no_data = 0

    for sym, profile in _coin_profiles.items():
        verdict = profile.get("verdict", "NO_DATA")
        events = profile.get("events", [])
        if not events:
            no_data += 1
            continue
        if verdict == "MOMENTUM":
            momentum_coins.append((sym, profile))
        elif verdict == "NOISE":
            noise_coins.append((sym, profile))
        else:
            middle_coins.append((sym, profile))

    momentum_coins.sort(key=lambda x: -x[1]["median_asymmetry"])
    noise_coins.sort(key=lambda x: x[1]["median_asymmetry"])

    total_events = sum(len(p.get("events", []))
                       for p in _coin_profiles.values())

    log.info("========== MOMENTUM LEARNING REPORT ==========")
    log.info("Phase: %s | Runtime: %.1fh | Events: %d | Coins: %d",
             phase, runtime / 3600.0, total_events, len(_coin_profiles))
    log.info("MOMENTUM: %d | MIDDLE: %d | NOISE: %d | NO_DATA: %d",
             len(momentum_coins), len(middle_coins),
             len(noise_coins), no_data)

    if momentum_coins:
        log.info("--- MOMENTUM COINS (tradable) ---")
        for sym, prof in momentum_coins[:15]:
            last = prof["events"][-1]
            log.info(
                "MOMENTUM | %s | n=%d | asym=%.2f | peak_v=%.1fx "
                "| rev_v=%.1fx | baseline=%.2f%%/m | giveback=%.1f%% "
                "| spike_dur=%ds",
                sym, len(prof["events"]), prof["median_asymmetry"],
                last["peak_velocity_multiple"],
                last["reversal_velocity_multiple"],
                last["peak_baseline_pct_per_min"],
                last["reversal_giveback_pct"],
                last["spike_duration_sec"],
            )

    if noise_coins:
        log.info("--- NOISE COINS (do not trade) ---")
        for sym, prof in noise_coins[:10]:
            last = prof["events"][-1]
            log.info(
                "NOISE | %s | n=%d | asym=%.2f | peak_v=%.1fx | rev_v=%.1fx",
                sym, len(prof["events"]), prof["median_asymmetry"],
                last["peak_velocity_multiple"],
                last["reversal_velocity_multiple"],
            )

    if _active_spikes:
        log.info("--- WATCHING (spike in progress) ---")
        for sym, w in list(_active_spikes.items())[:10]:
            age = time.time() - w["start_ts"]
            log.info(
                "WATCH | %s | peak_v=%.1fx | rev_v=%.1fx | age=%.0fs",
                sym, w["peak_velocity"], w["max_reversal_velocity"], age,
            )

    log.info("========== END REPORT ==========")


async def report_loop():
    global _last_report
    while True:
        try:
            if time.time() - _last_report >= REPORT_INTERVAL_SEC:
                _last_report = time.time()
                _report_profiles()
        except Exception as exc:
            log.warning("Report error: %s", exc)
        await asyncio.sleep(30.0)


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


async def universe_refresh_loop(session):
    while True:
        try:
            await refresh_universe(session)
        except Exception as exc:
            log.warning("Universe refresh error: %s", exc)
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)


def _heartbeat():
    global _last_heartbeat
    if time.time() - _last_heartbeat < HEARTBEAT_SEC:
        return
    _last_heartbeat = time.time()
    total_events = sum(len(p.get("events", []))
                       for p in _coin_profiles.values())
    log.info(
        "HEARTBEAT | phase=%s | uni=%d profiles=%d events=%d watching=%d "
        "| pos=%s | diag[det=%d fin=%d book=%d spr=%d ent=%d "
        "dead=%d sym=%d hard=%d time=%d] | streak W=%d L=%d tr=%d",
        "TRADING" if _trading_enabled else "LEARNING",
        len(_universe), len(_coin_profiles), total_events,
        len(_active_spikes),
        "open" if (_active_pos or _paper_pos) else "none",
        _diag["spikes_detected"], _diag["spikes_finalized"],
        _diag["tradable_skips_book"], _diag["tradable_skips_spread"],
        _diag["entries"],
        _diag["exit_momentum_dead"], _diag["exit_symmetric"],
        _diag["exit_hard"], _diag["exit_time"],
        _streak["wins"], _streak["losses"], _streak["trades"],
    )


# =============================================================================
# MAIN
# =============================================================================
async def main():
    _start_keepalive()

    if getattr(mm, "__version__", "UNKNOWN") != _EXPECTED_MM_VERSION:
        log.critical(
            "market_math.py version mismatch: expected %s, got %s.",
            _EXPECTED_MM_VERSION, getattr(mm, "__version__", "UNKNOWN"),
        )
        raise SystemExit(1)

    _load_streak()
    _load_profiles()

    log.info(
        "Startup | mode=%s | streak W=%d L=%d trades=%d | "
        "spike>=%.1fx | asym>=%.2f | learn=%.0fh | "
        "exit: dead<%.1fx*%d OR rev>%.1fx*%d OR hard<=-%.1f%% OR time>%.0fs",
        "LIVE" if _streak["live_activated"] else "PAPER",
        _streak["wins"], _streak["losses"], _streak["trades"],
        mm.SPIKE_VELOCITY_THRESHOLD, mm.MIN_ASYMMETRY_RATIO,
        LEARNING_PHASE_SEC / 3600.0,
        mm.MOMENTUM_DEATH_RATIO, mm.MOMENTUM_DEATH_CONSECUTIVE,
        mm.SYMMETRIC_REVERSAL_MULTIPLE, mm.SYMMETRIC_REVERSAL_CONSECUTIVE,
        mm.HARD_STOP_PCT, mm.MAX_HOLD_SEC,
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
        await adopt_orphan_positions(session)

        asyncio.create_task(contracts_refresh_loop(session))
        asyncio.create_task(universe_refresh_loop(session))
        asyncio.create_task(velocity_sweeper_loop(session))
        asyncio.create_task(report_loop())

        log.info("Main loop started | universe=%d", len(_universe))

        while True:
            loop_start = time.time()
            try:
                if _active_pos is not None:
                    await manage_live_position(session)
                elif _paper_pos is not None:
                    await manage_paper_position(session)
            except Exception as exc:
                log.error("Loop error: %s", exc, exc_info=True)

            _heartbeat()
            elapsed = time.time() - loop_start
            await asyncio.sleep(max(0.0, PULSE_SEC - elapsed))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown.")
    except SystemExit:
        raise
    except Exception as exc:
        log.critical("Fatal: %s", exc, exc_info=True)

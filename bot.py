#!/usr/bin/env python3
"""
bot.py — Clean-Move Momentum Engine | Bitget UTA V3 | Render Free Tier.

v2026.11.21
  No velocity math. Pure price movement.
  Qualify: 8%+ move in <30 min with no >2% interim reversal.
  Learn: measure reversal speed, compute asymmetry.
  Trade: only on coins with prior 4:1+ asymmetry event.
  Exit: 2% retrace from low, -3% hard stop, 30 min cap.
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

API_BASE = "https://api.bitget.com"
PORT = 10000
PRODUCT_TYPE = "USDT-FUTURES"
LEVERAGE = 5
PULSE_SEC = 4.0
PRICE_SWEEP_SEC = 4.0

UNIVERSE_REFRESH_SEC = 300
CONTRACTS_REFRESH_SEC = 900
UNIVERSE_MIN_VOL_USD = 1_000_000.0

LEARNING_PHASE_SEC = 7200.0
REPORT_INTERVAL_SEC = 900.0
HEARTBEAT_SEC = 60.0
SYMBOL_COOLDOWN_SEC = 300.0
MAX_EVENTS_PER_HOUR = 3
STUCK_TRACKING_SEC = 3600.0

PAPER_WINS_REQUIRED = 8
STREAK_FILE = "streak.json"

_EXPECTED_MM_VERSION = "2026.11.21"

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
# BITGET API
# =============================================================================
def _sign(timestamp, method, request_path, body):
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
                method, url, headers=headers,
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
            await asyncio.sleep((2 ** attempt) + 1)
    return {"code": "RETRY_EXHAUSTED", "msg": "max retries"}


async def _get_public_json(session, url, timeout=10.0):
    try:
        async with session.get(
            url, headers={"User-Agent": "momentum-bot/1.0"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None


# =============================================================================
# STATE
# =============================================================================
_contracts: Dict[str, dict] = {}
_universe = []
_last_universe_exchange_count = 0

_coin_state: Dict[str, dict] = {}
_learning_started_at = time.time()
_trading_enabled = False

_active_pos = None
_paper_pos = None
_cooldown_until: Dict[str, float] = {}
_streak = {"wins": 0, "losses": 0, "live_activated": False, "trades": 0}

_last_heartbeat = 0.0
_last_report = 0.0

_diag = {
    "sweep_fails": 0,
    "qualified_moves": 0,
    "interim_rejects": 0,
    "events_finalized": 0,
    "trades_entered": 0,
    "exits_reversal": 0,
    "exits_hard": 0,
    "exits_time": 0,
    "skips_no_profile": 0,
    "skips_book": 0,
    "skips_spread": 0,
}


# =============================================================================
# HELPERS
# =============================================================================
def _extract_positions(d):
    payload = d.get("data")
    if isinstance(payload, dict):
        return payload.get("list") or []
    if isinstance(payload, list):
        return payload
    return []


def _env_int_or_none(name):
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _env_bool_or_none(name):
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return None
    return v.strip().lower() in ("1", "true", "yes", "on")


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


def _save_streak():
    try:
        with open(STREAK_FILE, "w") as f:
            json.dump(_streak, f)
    except OSError:
        pass


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


# =============================================================================
# COIN STATE
# =============================================================================
def _get_state(symbol):
    if symbol not in _coin_state:
        _coin_state[symbol] = {
            "price_history": [],
            "phase": "SCANNING",     # SCANNING | TRACKING | MEASURING
            "tracking": None,
            "measuring": None,
            "profile": {
                "events": [],
                "median_asymmetry": 0.0,
                "verdict": "NO_DATA",
                "recent_event_ts": [],
            },
        }
    return _coin_state[symbol]


def _profile_is_tradable(profile):
    if not profile:
        return False
    if profile["verdict"] != "MOMENTUM":
        return False
    if not profile["events"]:
        return False
    return True


def _events_within_hour(profile, now_ts):
    recent = [t for t in profile.get("recent_event_ts", [])
              if now_ts - t < 3600]
    return len(recent)


def _add_event(profile, event, now_ts):
    profile["events"].append(event)
    profile.setdefault("recent_event_ts", []).append(now_ts)
    profile["recent_event_ts"] = [
        t for t in profile["recent_event_ts"] if now_ts - t < 3600
    ]
    asyms = sorted(e["asymmetry"] for e in profile["events"]
                   if e["asymmetry"] > 0)
    if not asyms:
        profile["median_asymmetry"] = 0.0
    else:
        n = len(asyms)
        median = asyms[n // 2] if n % 2 else (asyms[n // 2 - 1] + asyms[n // 2]) / 2.0
        profile["median_asymmetry"] = round(median, 2)
    profile["verdict"] = mm.classify_asymmetry(profile["median_asymmetry"])


# =============================================================================
# STATE MACHINE — called every sweep
# =============================================================================
def _advance_state(symbol, state, current_price, now_ts):
    history = state["price_history"]
    history.append((now_ts, current_price))
    cutoff = now_ts - mm.PRICE_WINDOW_SEC
    state["price_history"] = [(t, p) for t, p in history if t >= cutoff]

    if state["phase"] == "SCANNING":
        _advance_scanning(symbol, state, current_price, now_ts)
    elif state["phase"] == "TRACKING":
        _advance_tracking(symbol, state, current_price, now_ts)
    elif state["phase"] == "MEASURING":
        _advance_measuring(symbol, state, now_ts)


def _advance_scanning(symbol, state, current_price, now_ts):
    move = mm.find_qualifying_move(state["price_history"], now_ts)
    if not move["qualified"]:
        if move["reason"].startswith("INTERIM_REVERSAL"):
            _diag["interim_rejects"] += 1
        return

    _diag["qualified_moves"] += 1
    log.info(
        "MOVE_QUALIFIED | %s | dir=%s | pct=%.2f%% | dur=%ds | "
        "speed=%.3f%%/min | start=%.6f peak=%.6f",
        symbol, move["direction"], move["move_pct"],
        move["move_duration_sec"], move["move_speed_pct_per_min"],
        move["start_price"], move["peak_price"],
    )

    state["phase"] = "TRACKING"
    state["tracking"] = {
        "direction": move["direction"],
        "start_price": move["start_price"],
        "start_ts": move["start_ts"],
        "peak_price": move["peak_price"],
        "peak_ts": move["peak_ts"],
        "move_pct": move["move_pct"],
        "move_duration_sec": move["move_duration_sec"],
        "move_speed_pct_per_min": move["move_speed_pct_per_min"],
        "reversal_start_ts": 0,
    }


def _advance_tracking(symbol, state, current_price, now_ts):
    tracking = state["tracking"]
    if tracking is None:
        state["phase"] = "SCANNING"
        return

    direction = tracking["direction"]

    if direction == "down" and current_price < tracking["peak_price"]:
        tracking["peak_price"] = current_price
        tracking["peak_ts"] = now_ts
        tracking["reversal_start_ts"] = 0
    elif direction == "up" and current_price > tracking["peak_price"]:
        tracking["peak_price"] = current_price
        tracking["peak_ts"] = now_ts
        tracking["reversal_start_ts"] = 0

    retrace, started, new_ts = mm.check_reversal_started(
        direction, tracking["peak_price"], current_price,
        tracking["reversal_start_ts"], now_ts,
    )
    tracking["reversal_start_ts"] = new_ts

    if started:
        log.info(
            "MOVE_PEAKED | %s | dir=%s | peak=%.6f | retrace=%.2f%% | "
            "final_pct=%.2f%%",
            symbol, direction, tracking["peak_price"],
            retrace, tracking["move_pct"],
        )
        state["phase"] = "MEASURING"
        state["measuring"] = {
            "direction": direction,
            "start_price": tracking["start_price"],
            "start_ts": tracking["start_ts"],
            "peak_price": tracking["peak_price"],
            "peak_ts": tracking["peak_ts"],
            "move_pct": (tracking["start_price"] - tracking["peak_price"])
                        / tracking["start_price"] * 100.0
                        if direction == "down"
                        else (tracking["peak_price"] - tracking["start_price"])
                             / tracking["start_price"] * 100.0,
            "move_duration_sec": tracking["peak_ts"] - tracking["start_ts"],
            "move_speed_pct_per_min": 0.0,
        }
        m = state["measuring"]
        if m["move_duration_sec"] > 0:
            m["move_speed_pct_per_min"] = m["move_pct"] / (m["move_duration_sec"] / 60.0)
        state["tracking"] = None
        return

    if now_ts - tracking["start_ts"] > STUCK_TRACKING_SEC:
        log.warning("STUCK_TRACKING | %s | clearing", symbol)
        state["tracking"] = None
        state["phase"] = "SCANNING"


def _advance_measuring(symbol, state, now_ts):
    measuring = state["measuring"]
    if measuring is None:
        state["phase"] = "SCANNING"
        return

    reversal = mm.measure_reversal(
        state["price_history"], measuring["direction"],
        measuring["peak_ts"], measuring["peak_price"], now_ts,
    )
    if not reversal["complete"]:
        return

    asym = mm.compute_asymmetry(
        measuring["move_speed_pct_per_min"],
        reversal["reversal_speed_pct_per_min"],
    )
    verdict = mm.classify_asymmetry(asym)

    event = {
        "ts_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(measuring["start_ts"])),
        "direction": measuring["direction"],
        "move_pct": round(measuring["move_pct"], 2),
        "move_duration_sec": measuring["move_duration_sec"],
        "move_speed_pct_per_min": round(measuring["move_speed_pct_per_min"], 4),
        "reversal_pct": round(reversal["reversal_pct"], 2),
        "reversal_duration_sec": reversal["reversal_duration_sec"],
        "reversal_speed_pct_per_min": round(reversal["reversal_speed_pct_per_min"], 4),
        "asymmetry": round(asym, 2),
        "verdict": verdict,
    }

    profile = state["profile"]
    _add_event(profile, event, now_ts)
    _diag["events_finalized"] += 1

    log.info(
        "EVENT_DONE | %s | dir=%s | move=%.2f%%@%.3f%%/m | "
        "rev=%.2f%%@%.3f%%/m | asym=%.2f | verdict=%s | median=%.2f | n=%d",
        symbol, measuring["direction"], measuring["move_pct"],
        measuring["move_speed_pct_per_min"], reversal["reversal_pct"],
        reversal["reversal_speed_pct_per_min"], asym, verdict,
        profile["median_asymmetry"], len(profile["events"]),
    )

    state["measuring"] = None
    state["phase"] = "SCANNING"


# =============================================================================
# UNIVERSE / CONTRACTS
# =============================================================================
async def enforce_one_way(session):
    settings = await _request(session, "GET", "/api/v3/account/settings")
    if settings.get("code") == "00000":
        data = settings.get("data") or {}
        if isinstance(data, dict) and data.get("holdMode") == "one_way_mode":
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


async def _prices_bitget(session):
    out = {}
    d = await _get_public_json(
        session, API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}")
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
        session, API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}")
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
        session, "https://api.bybit.com/v5/market/tickers?category=linear")
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
        session, "https://www.okx.com/api/v5/market/tickers?instType=SWAP")
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
        session, "https://api.gateio.ws/api/v4/futures/usdt/tickers")
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
        session, "https://api-futures.kucoin.com/api/v1/contracts/active")
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
        session, "https://contract.mexc.com/api/v1/contract/ticker")
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
        session,
        "https://api.hbdm.com/linear-swap-ex/market/tickers?business_type=swap")
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
    log.info("Universe: %d symbols | excluded: %d stock, %d low-vol",
             len(_universe), excluded_stock, excluded_vol)


# =============================================================================
# MARKET DATA / POSITION
# =============================================================================
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
    return bids, asks, (best_bid + best_ask) / 2.0


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
            "symbol": sym, "entry": entry,
            "opened_at": time.time(),
            "extreme_since_entry": entry,
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
# TRADE ENTRY
# =============================================================================
async def try_enter_momentum(session, symbol, state, current_price, now_ts):
    global _active_pos, _paper_pos

    if time.time() < _cooldown_until.get(symbol, 0):
        return False
    if _active_pos is not None or _paper_pos is not None:
        return False
    if not _trading_enabled:
        return False

    profile = state.get("profile")
    if not _profile_is_tradable(profile):
        _diag["skips_no_profile"] += 1
        return False
    if _events_within_hour(profile, now_ts) >= MAX_EVENTS_PER_HOUR:
        return False

    depth = await fetch_depth(session, symbol)
    if depth is None:
        _diag["skips_book"] += 1
        return False
    bids, asks, mid = depth

    book = mm.evaluate_book(bids, asks, mid)
    if not book["is_valid"]:
        _diag["skips_book"] += 1
        return False

    spread = mm.evaluate_spread(bids, asks)
    if not spread["is_ok"]:
        _diag["skips_spread"] += 1
        return False

    tracking = state["tracking"]
    asym = profile["median_asymmetry"]

    log.info(
        "MOMENTUM ENTRY | %s | dir=%s | asym=%.2f | move=%.2f%% | "
        "price=%.6f",
        symbol, tracking["direction"], asym, tracking["move_pct"],
        current_price,
    )

    if not _streak["live_activated"]:
        _diag["trades_entered"] += 1
        _paper_pos = {
            "symbol": symbol, "entry": current_price,
            "opened_at": time.time(),
            "extreme_since_entry": current_price,
            "is_panic": True, "paper": True,
        }
        log.info("PAPER OPEN | %s SHORT @ %.6f | W=%d/%d",
                 symbol, current_price, _streak["wins"], PAPER_WINS_REQUIRED)
        return True

    contract = _contracts.get(symbol)
    if not contract:
        return False
    balance = await get_usdt_balance(session)
    qty_str = mm.calculate_order_qty(
        balance=balance, price=current_price, leverage=LEVERAGE,
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

    _diag["trades_entered"] += 1
    _active_pos = {
        "symbol": symbol, "entry": current_price,
        "opened_at": time.time(),
        "extreme_since_entry": current_price,
        "is_panic": True, "paper": False, "order_id": oid,
    }
    log.info("LIVE OPEN | %s SHORT @ %.6f | qty=%s",
             symbol, current_price, qty_str)
    return True


# =============================================================================
# PRICE SWEEPER — THE CORE LOOP
# =============================================================================
async def price_sweeper_loop(session):
    global _trading_enabled

    while True:
        try:
            now_ts = time.time()

            if not _trading_enabled and (now_ts - _learning_started_at) >= LEARNING_PHASE_SEC:
                _trading_enabled = True
                tradable = sum(1 for s in _coin_state.values()
                               if _profile_is_tradable(s.get("profile")))
                log.info(
                    "*** LEARNING COMPLETE — TRADING ENABLED *** "
                    "(%d profiles, %d tradable)",
                    len(_coin_state), tradable,
                )

            prices = await _prices_bitget(session)
            if not prices:
                _diag["sweep_fails"] += 1
                await asyncio.sleep(PRICE_SWEEP_SEC)
                continue

            for sym, price in prices.items():
                if sym not in _contracts:
                    continue
                if _contracts[sym].get("is_stock"):
                    continue
                state = _get_state(sym)
                _advance_state(sym, state, price, now_ts)

                if (state["phase"] == "TRACKING"
                        and _trading_enabled
                        and _profile_is_tradable(state.get("profile"))
                        and _active_pos is None
                        and _paper_pos is None):
                    await try_enter_momentum(session, sym, state, price, now_ts)

        except Exception as exc:
            log.warning("Sweeper error: %s", exc)
            _diag["sweep_fails"] += 1

        await asyncio.sleep(PRICE_SWEEP_SEC)


# =============================================================================
# POSITION MANAGEMENT
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

    if current < pos["extreme_since_entry"]:
        pos["extreme_since_entry"] = current

    elapsed = time.time() - pos["opened_at"]
    state = mm.compute_exit_signal(
        pos["entry"], pos["extreme_since_entry"], current, elapsed,
    )
    if not state["should_exit"]:
        return

    reason = state["exit_reason"]
    if reason == "REVERSAL_CONFIRMED":
        _diag["exits_reversal"] += 1
    elif reason == "HARD_STOP":
        _diag["exits_hard"] += 1
    elif reason == "TIME_EXIT":
        _diag["exits_time"] += 1

    log.info(
        "EXIT | %s | %s | gross=%.2f%% net=%.2f%% | retrace=%.2f%% | "
        "extreme=%.6f",
        symbol, reason, state["gross_pnl"], state["net_pnl"],
        state["retrace_from_low_pct"], pos["extreme_since_entry"],
    )

    closed = await close_live_position(session, pos, reason)
    if closed:
        _record_result(state["net_pnl"], reason)
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

    if current < pos["extreme_since_entry"]:
        pos["extreme_since_entry"] = current

    elapsed = time.time() - pos["opened_at"]
    state = mm.compute_exit_signal(
        pos["entry"], pos["extreme_since_entry"], current, elapsed,
    )
    if not state["should_exit"]:
        return

    reason = state["exit_reason"]
    if reason == "REVERSAL_CONFIRMED":
        _diag["exits_reversal"] += 1
    elif reason == "HARD_STOP":
        _diag["exits_hard"] += 1
    elif reason == "TIME_EXIT":
        _diag["exits_time"] += 1

    log.info(
        "PAPER EXIT | %s | %s | gross=%.2f%% net=%.2f%% | retrace=%.2f%% | "
        "extreme=%.6f",
        symbol, reason, state["gross_pnl"], state["net_pnl"],
        state["retrace_from_low_pct"], pos["extreme_since_entry"],
    )
    _record_result(state["net_pnl"], reason)
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _paper_pos = None


# =============================================================================
# REPORT
# =============================================================================
def _report():
    now = time.time()
    runtime = now - _learning_started_at
    phase = "TRADING" if _trading_enabled else "LEARNING"

    momentum = []
    middle = []
    noise = []
    no_data = 0

    for sym, st in _coin_state.items():
        p = st.get("profile")
        if not p or not p["events"]:
            no_data += 1
            continue
        if p["verdict"] == "MOMENTUM":
            momentum.append((sym, p))
        elif p["verdict"] == "NOISE":
            noise.append((sym, p))
        else:
            middle.append((sym, p))

    momentum.sort(key=lambda x: -x[1]["median_asymmetry"])
    noise.sort(key=lambda x: x[1]["median_asymmetry"])

    log.info("========== MOMENTUM REPORT ==========")
    log.info("Phase: %s | Runtime: %.1fh | Coins: %d | Total events: %d",
             phase, runtime / 3600.0, len(_coin_state),
             sum(len(s.get("profile", {}).get("events", []))
                 for s in _coin_state.values()))
    log.info("MOMENTUM: %d | MIDDLE: %d | NOISE: %d | NO_DATA: %d",
             len(momentum), len(middle), len(noise), no_data)

    if momentum:
        log.info("--- MOMENTUM COINS (tradable) ---")
        for sym, p in momentum[:15]:
            last = p["events"][-1]
            log.info(
                "MOMENTUM | %s | n=%d | median_asym=%.2f | last: "
                "move=%.2f%%@%.3f%%/m rev=%.2f%%@%.3f%%/m asym=%.2f",
                sym, len(p["events"]), p["median_asymmetry"],
                last["move_pct"], last["move_speed_pct_per_min"],
                last["reversal_pct"], last["reversal_speed_pct_per_min"],
                last["asymmetry"],
            )

    if noise:
        log.info("--- NOISE COINS ---")
        for sym, p in noise[:10]:
            last = p["events"][-1]
            log.info(
                "NOISE | %s | n=%d | median_asym=%.2f | last asym=%.2f",
                sym, len(p["events"]), p["median_asymmetry"], last["asymmetry"],
            )

    tracking = [(s, st) for s, st in _coin_state.items()
                if st["phase"] == "TRACKING"]
    if tracking:
        log.info("--- TRACKING (in progress) ---")
        for sym, st in tracking[:10]:
            t = st["tracking"]
            age = now - t["start_ts"]
            log.info("TRACK | %s | dir=%s | move=%.2f%% | age=%.0fs",
                     sym, t["direction"], t["move_pct"], age)

    log.info("========== END REPORT ==========")


async def report_loop():
    global _last_report
    while True:
        try:
            if time.time() - _last_report >= REPORT_INTERVAL_SEC:
                _last_report = time.time()
                _report()
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
            log.warning("Contract refresh: %s", exc)


async def universe_refresh_loop(session):
    while True:
        try:
            await refresh_universe(session)
        except Exception as exc:
            log.warning("Universe refresh: %s", exc)
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)


def _heartbeat():
    global _last_heartbeat
    if time.time() - _last_heartbeat < HEARTBEAT_SEC:
        return
    _last_heartbeat = time.time()
    tracking = sum(1 for s in _coin_state.values() if s["phase"] == "TRACKING")
    measuring = sum(1 for s in _coin_state.values() if s["phase"] == "MEASURING")
    tradable = sum(1 for s in _coin_state.values()
                   if _profile_is_tradable(s.get("profile")))
    log.info(
        "HEARTBEAT | phase=%s | coins=%d tracking=%d measuring=%d tradable=%d "
        "| pos=%s | diag[qual=%d rej=%d evt=%d ent=%d "
        "ex_rev=%d ex_hard=%d ex_time=%d] | streak W=%d L=%d tr=%d",
        "TRADING" if _trading_enabled else "LEARNING",
        len(_coin_state), tracking, measuring, tradable,
        "open" if (_active_pos or _paper_pos) else "none",
        _diag["qualified_moves"], _diag["interim_rejects"],
        _diag["events_finalized"], _diag["trades_entered"],
        _diag["exits_reversal"], _diag["exits_hard"], _diag["exits_time"],
        _streak["wins"], _streak["losses"], _streak["trades"],
    )


# =============================================================================
# MAIN
# =============================================================================
async def main():
    _start_keepalive()

    if getattr(mm, "__version__", "UNKNOWN") != _EXPECTED_MM_VERSION:
        log.critical("Version mismatch: expected %s got %s",
                     _EXPECTED_MM_VERSION, getattr(mm, "__version__", "?"))
        raise SystemExit(1)

    _load_streak()

    log.info(
        "Startup | mode=%s | streak W=%d L=%d tr=%d | "
        "qualify: >=%.1f%% in <%ds no >%.1f%% interim reversal | "
        "asym>=%.1f | exit: %.1f%% retrace OR -%.1f%% hard OR %ds | "
        "learn=%.0fs",
        "LIVE" if _streak["live_activated"] else "PAPER",
        _streak["wins"], _streak["losses"], _streak["trades"],
        mm.MOVE_THRESHOLD_PCT, mm.MOVE_MAX_DURATION_SEC,
        mm.MOVE_MAX_INTERIM_REVERSAL_PCT,
        mm.MIN_ASYMMETRY_RATIO,
        mm.EXIT_REVERSAL_PCT, mm.EXIT_HARD_STOP_PCT, mm.EXIT_TIME_CAP_SEC,
        LEARNING_PHASE_SEC,
    )
    log.info("Fresh learning phase — no profiles loaded. Starting from zero.")

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
        asyncio.create_task(price_sweeper_loop(session))
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

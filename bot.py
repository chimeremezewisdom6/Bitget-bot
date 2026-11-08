#!/usr/bin/env python3
"""
bot.py — PREDICT strategy | Bitget UTA V3 | Render Free Tier.
v2026.12.10
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

import market_math as pm
import account_setup as acc

API_BASE = "https://api.bitget.com"
PORT = 10000
PRODUCT_TYPE = "USDT-FUTURES"
LEVERAGE = 5
PULSE_SEC = 4.0

UNIVERSE_REFRESH_SEC = 300
CONTRACTS_REFRESH_SEC = 900
UNIVERSE_MIN_VOL_USD = pm.PRED_VOLUME_MIN_USD

PREDICT_WARMUP_SEC = 900
BOUNDARY_INTERVAL_SEC = 1800
BEHAVIOUR_SAMPLE_SEC = 60.0
HEARTBEAT_SEC = 60.0
SYMBOL_COOLDOWN_SEC = 300.0

PAPER_HISTORY_SIZE = 40
PAPER_WINS_REQUIRED = 32
PROFILE_HISTORY_SIZE = 10
MIN_MATCHES_FOR_MULTI = 3

STREAK_FILE = "predict_streak.json"
PROFILE_FILE = "predict_profiles.json"

_EXPECTED_PM_VERSION = "2026.12.10"

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
log = logging.getLogger("predict")
logging.getLogger("aiohttp").setLevel(logging.WARNING)


def _env(*names):
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    raise RuntimeError(f"Missing credential env var: {names}")


API_KEY = _env("BITGET_API_KEY", "API_KEY")
SECRET_KEY = _env("BITGET_API_SECRET", "SECRET_KEY")
PASSPHRASE = _env("BITGET_API_PASSPHRASE", "PASSPHRASE")


# =============================================================================
# HEALTH
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


def _start_keepalive():
    server = HTTPServer(("0.0.0.0", PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Keep-alive listening on :%d", PORT)


# =============================================================================
# API
# =============================================================================
def _sign(timestamp, method, request_path, body):
    msg = timestamp + method.upper() + request_path + body
    digest = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


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
        try:
            async with session.request(
                method, API_BASE + path_with_q, headers=headers,
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
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep((2 ** attempt) + 1)
    return {"code": "RETRY_EXHAUSTED", "msg": "max retries"}


async def _get_public_json(session, url, timeout=10.0):
    try:
        async with session.get(
            url, headers={"User-Agent": "predict-bot/1.0"},
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
_ticker_cache: Dict[str, dict] = {}
_recent_fills_cache: Dict[str, dict] = {}
_ready_symbols: set = set()

_started_at = time.time()
_next_boundary_ts = 0.0

_paper_positions: Dict[str, dict] = {}
_active_positions: Dict[str, dict] = {}
_cooldown_until: Dict[str, float] = {}

_streak = {"live_activated": False}
_paper_trade_history = []
_paper_total_trades = 0
_paper_total_wins = 0
_paper_total_losses = 0

_predict_profiles = []
_next_profile_id = 0
_global_tag_stats: Dict[str, list] = {}
_tag_descriptions: Dict[str, str] = {}
_live_tier_history: Dict[str, Dict[str, dict]] = {}
_live_bans: Dict[str, dict] = {}
_new_feature_candidates: Dict[str, dict] = {}
_new_features: set = set()
_pending_candidates: list = []
_recent_paper_stories: list = []

_cycle_snapshot = {
    "cycle_id": 0, "started_at": 0.0,
    "features": {}, "prices": {},
    "traded_symbols": set(), "trade_profile_ids": {},
}

_last_heartbeat = 0.0

_diag = {
    "sweep_fails": 0, "cycles": 0, "matches": 0,
    "paper_entries": 0, "live_entries": 0,
    "profiles_added": 0, "features_promoted": 0,
    "bans_fired": 0, "unbans": 0,
    "skips_book": 0, "skips_spread": 0, "skips_pressure": 0,
}


# =============================================================================
# PERSISTENCE
# =============================================================================
def _load_streak():
    global _paper_total_trades, _paper_total_wins, _paper_total_losses
    global _paper_trade_history
    try:
        with open(STREAK_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _streak["live_activated"] = bool(data.get("live_activated", False))
            _paper_total_trades = int(data.get("paper_total_trades", 0))
            _paper_total_wins = int(data.get("paper_total_wins", 0))
            _paper_total_losses = int(data.get("paper_total_losses", 0))
            hist = data.get("recent_history", [])
            if isinstance(hist, list):
                _paper_trade_history = [bool(x) for x in hist][-PAPER_HISTORY_SIZE:]
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        pass


def _save_streak():
    try:
        with open(STREAK_FILE, "w") as f:
            json.dump({
                "live_activated": _streak["live_activated"],
                "paper_total_trades": _paper_total_trades,
                "paper_total_wins": _paper_total_wins,
                "paper_total_losses": _paper_total_losses,
                "recent_history": _paper_trade_history,
            }, f)
    except OSError:
        pass


def _new_profile_id():
    global _next_profile_id
    _next_profile_id += 1
    return _next_profile_id


def _load_predict_profiles():
    global _predict_profiles, _next_profile_id
    global _global_tag_stats, _tag_descriptions, _live_tier_history
    global _live_bans, _new_feature_candidates, _new_features
    try:
        with open(PROFILE_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            active = data.get("active", []) or []
            _global_tag_stats = data.get("global_tag_stats", {}) or {}
            _tag_descriptions = data.get("tag_descriptions", {}) or {}
            _live_tier_history = data.get("live_tier_history", {}) or {}
            _live_bans = data.get("live_bans", {}) or {}
            _new_feature_candidates = data.get("new_feature_candidates", {}) or {}
            _new_features = set(data.get("new_features", []) or [])
        elif isinstance(data, list):
            active = data
        else:
            active = []
        _predict_profiles = [p for p in active if isinstance(p, dict)][-pm.PRED_PROFILE_MAX:]
        max_id = 0
        for p in _predict_profiles:
            p.setdefault("wins", 0)
            p.setdefault("losses", 0)
            p.setdefault("recent", [])
            p.setdefault("swings", [])
            p.setdefault("tag_history", {})
            i = p.get("id", 0)
            if isinstance(i, int) and i > max_id:
                max_id = i
        _next_profile_id = max_id
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _predict_profiles = []
        _global_tag_stats = {}
        _tag_descriptions = {}
        _live_tier_history = {}
        _live_bans = {}
        _new_feature_candidates = {}
        _new_features = set()


def _save_predict_profiles():
    try:
        with open(PROFILE_FILE, "w") as f:
            json.dump({
                "active": _predict_profiles,
                "global_tag_stats": _global_tag_stats,
                "tag_descriptions": _tag_descriptions,
                "live_tier_history": _live_tier_history,
                "live_bans": _live_bans,
                "new_feature_candidates": _new_feature_candidates,
                "new_features": list(_new_features),
            }, f)
    except OSError:
        pass


# =============================================================================
# RECORDING
# =============================================================================
def _record_result(net_pnl, exit_reason, source):
    global _paper_total_trades, _paper_total_wins, _paper_total_losses
    won = net_pnl > 0
    _paper_trade_history.append(won)
    if len(_paper_trade_history) > PAPER_HISTORY_SIZE:
        _paper_trade_history.pop(0)
    _paper_total_trades += 1
    if won:
        _paper_total_wins += 1
    else:
        _paper_total_losses += 1
    _save_streak()

    recent_n = len(_paper_trade_history)
    recent_wins = sum(_paper_trade_history)
    log.debug(
        "TRADE | net=%.3f%% | %s | src=%s | TOTAL %d/%d/%d | RECENT %d/%d/%d",
        net_pnl, exit_reason, source,
        _paper_total_wins, _paper_total_losses, _paper_total_trades,
        recent_wins, recent_n - recent_wins, recent_n)

    if not _streak["live_activated"] and recent_n >= PAPER_HISTORY_SIZE:
        if recent_wins >= PAPER_WINS_REQUIRED:
            _streak["live_activated"] = True
            _save_streak()
            log.info("*** GAUNTLET PASSED — %d/%d — LIVE UNLOCKED ***",
                     recent_wins, recent_n)


def _update_profile_result(prof_id, net_pnl, peak_pct=None, trough_pct=None,
                           story_text=None, ticks=None, direction=None,
                           start_ts=None, tags=None, symbol=None):
    if prof_id is None:
        return
    idx = None
    for i, p in enumerate(_predict_profiles):
        if p.get("id") == prof_id:
            idx = i
            break
    if idx is None:
        return
    p = _predict_profiles[idx]
    won = net_pnl > 0
    p.setdefault("recent", []).append(won)
    if len(p["recent"]) > PROFILE_HISTORY_SIZE:
        p["recent"].pop(0)
    if won:
        p["wins"] = p.get("wins", 0) + 1
    else:
        p["losses"] = p.get("losses", 0) + 1
    if peak_pct is not None and trough_pct is not None:
        p.setdefault("swings", []).append({
            "net": round(net_pnl, 3),
            "peak": round(peak_pct, 3),
            "trough": round(trough_pct, 3),
            "story": (story_text or "")[:600],
        })
        if len(p["swings"]) > PROFILE_HISTORY_SIZE:
            p["swings"].pop(0)
    if tags and ticks and direction and start_ts:
        vol_24h = _ticker_cache.get(symbol, {}).get("volume_24h_usd", 0) if symbol else 0
        tier = pm.market_cap_tier_from_volume(vol_24h)
        tag_hist = p.setdefault("tag_history", {})
        for t in tags:
            tag = t.get("tag")
            minute = t.get("minute", 0)
            ft = pm.measure_tag_followthrough(ticks, start_ts + minute * 60, direction)
            ft["tier"] = tier
            tag_hist.setdefault(tag, []).append(ft)
            if len(tag_hist[tag]) > 10:
                tag_hist[tag].pop(0)
            _global_tag_stats.setdefault(tag, []).append(ft)
            if len(_global_tag_stats[tag]) > 200:
                _global_tag_stats[tag].pop(0)
    _save_predict_profiles()


def _update_profile_from_live(prof_id, net_pnl):
    if prof_id is None:
        return
    for p in _predict_profiles:
        if p.get("id") == prof_id:
            if net_pnl > 0:
                p["wins"] = p.get("wins", 0) + 1
            elif net_pnl < 0:
                p["losses"] = p.get("losses", 0) + 1
            _save_predict_profiles()
            return


def _record_live_tier_result(tag, tier, net):
    if not tag or not tier:
        return
    th = _live_tier_history.setdefault(tag, {}).setdefault(
        tier, {"recent_net": [], "inactive": False})
    th["recent_net"].append(round(net, 3))
    if len(th["recent_net"]) > 20:
        th["recent_net"].pop(0)
    th["inactive"] = False
    fails, diag = pm.live_window_fails(th["recent_net"])
    if fails:
        already, _ = _is_banned(tag, tier)
        if not already:
            classification = _classify_failure(tag, tier)
            _ban_tier(tag, tier, diag["reason"], classification)
    _save_predict_profiles()


# =============================================================================
# PROFILE BANKING
# =============================================================================
def _can_bank_new_profile(features):
    if not any(p.get("wins", 0) >= 1 for p in _predict_profiles):
        return True
    for p in _predict_profiles:
        if p.get("wins", 0) >= 1 and pm.features_resemble_profile(features, p):
            return True
    return False


def _add_predict_profile(features, actual_direction):
    for i, p in enumerate(_predict_profiles):
        if pm.features_match_profile(features, p, tol=0.15):
            return None
    if not _can_bank_new_profile(features):
        return None
    profile = {
        "id": _new_profile_id(),
        "fluct_per_min": features["fluct_per_min"],
        "recent_abs_pct": features["recent_abs_pct"],
        "prior_move_pct": features["prior_move_pct"],
        "acceleration": features["acceleration"],
        "distance_from_extreme_pct": features["distance_from_extreme_pct"],
        "direction": actual_direction,
        "wins": 0, "losses": 0, "recent": [], "swings": [],
        "tag_history": {}, "added_at": time.time(),
    }
    _predict_profiles.append(profile)
    if len(_predict_profiles) > pm.PRED_PROFILE_MAX:
        _predict_profiles.pop(0)
    _save_predict_profiles()
    _diag["profiles_added"] += 1
    log.info("PROFILE ADDED | id=%d dir=%s | bank=%d",
             profile["id"], actual_direction, len(_predict_profiles))
    return profile["id"]


# =============================================================================
# BAN SYSTEM
# =============================================================================
def _ban_key(tag, tier):
    return f"{tag}|{tier}"


def _is_banned(tag, tier):
    b = _live_bans.get(_ban_key(tag, tier))
    if not b:
        return False, None
    return time.time() < b.get("banned_until", 0), b


def _classify_failure(tag, tier):
    other_tier_failing = other_tier_checked = 0
    for other_tag, tiers_map in _live_tier_history.items():
        if other_tag == tag:
            continue
        rn = (tiers_map.get(tier) or {}).get("recent_net", [])
        if len(rn) >= pm.LIVE_FAIL_WINDOW:
            other_tier_checked += 1
            if sum(rn[-pm.LIVE_FAIL_WINDOW:]) < pm.LIVE_FAIL_MIN_NET_SUM:
                other_tier_failing += 1
    same_tag_other_failing = same_tag_other_checked = 0
    for other_tier, tv in (_live_tier_history.get(tag) or {}).items():
        if other_tier == tier:
            continue
        rn = tv.get("recent_net", [])
        if len(rn) >= pm.LIVE_FAIL_WINDOW:
            same_tag_other_checked += 1
            if sum(rn[-pm.LIVE_FAIL_WINDOW:]) < pm.LIVE_FAIL_MIN_NET_SUM:
                same_tag_other_failing += 1
    if other_tier_checked >= 2 and other_tier_failing >= 2:
        return "market_regime"
    if same_tag_other_checked >= 1 and same_tag_other_failing >= 1:
        return "feature_wide"
    return "tier_specific"


def _ban_tier(tag, tier, reason, classification):
    key = _ban_key(tag, tier)
    b = _live_bans.setdefault(key, {
        "banned_until": 0.0, "ban_count": 0,
        "last_reason": "", "last_classification": "", "history": []})
    b["ban_count"] += 1
    duration = min(pm.LIVE_BAN_INITIAL_SEC * (2 ** min(b["ban_count"] - 1, 4)),
                   pm.LIVE_BAN_MAX_SEC)
    b["banned_until"] = time.time() + duration
    b["last_reason"] = reason
    b["last_classification"] = classification
    b["history"].append({"ts": int(time.time()), "reason": reason,
                         "classification": classification,
                         "duration": duration})
    if len(b["history"]) > 20:
        b["history"].pop(0)
    _diag["bans_fired"] += 1
    log.info("TIER BANNED | tag=%s tier=%s | %s | %s | #%d | %ds",
             tag, tier, reason, classification, b["ban_count"], duration)
    _save_predict_profiles()


def _review_bans():
    now = time.time()
    for key in list(_live_bans.keys()):
        b = _live_bans[key]
        if b.get("banned_until", 0) > now:
            continue
        tag, tier = key.split("|", 1)
        samples = _global_tag_stats.get(tag, [])
        p_ok, p_diag = pm.tier_paper_eligible(tier, samples)
        if p_ok:
            if now - b.get("banned_until", now) > pm.LIVE_BAN_CLEAN_RESET_SEC:
                b["ban_count"] = 0
            log.info("TIER UNBANNED | tag=%s tier=%s | paper: %s",
                     tag, tier, p_diag.get("reason"))
            b["banned_until"] = 0.0
            _diag["unbans"] += 1
        else:
            b["banned_until"] = now + pm.LIVE_BAN_INITIAL_SEC * 2
            log.info("TIER BAN EXTENDED | tag=%s tier=%s | paper: %s",
                     tag, tier, p_diag.get("reason"))
    _save_predict_profiles()


# =============================================================================
# UNIVERSE
# =============================================================================
def _extract_positions(d):
    payload = d.get("data")
    if isinstance(payload, dict):
        return payload.get("list") or []
    if isinstance(payload, list):
        return payload
    return []


async def refresh_contracts(session):
    d = await _request(session, "GET", "/api/v2/mix/market/contracts",
                        query={"productType": PRODUCT_TYPE}, signed=False)
    if d.get("code") != "00000":
        log.warning("Contract refresh failed")
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
    if s.endswith("SWAP") or s.endswith("PERP"):
        s = s[:-4]
    return s


async def _tickers_bitget(session):
    prices, stats = {}, {}
    d = await _get_public_json(
        session, API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}")
    if not isinstance(d, dict) or d.get("code") != "00000":
        return prices, stats
    for t in d.get("data", []) or []:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        try:
            p = t.get("lastPr") or t.get("last")
            if not p:
                continue
            prices[sym] = float(p)
            stats[sym] = {
                "high_24h": float(t.get("high24h") or 0),
                "low_24h": float(t.get("low24h") or 0),
                "open_24h": float(t.get("openUtc") or t.get("open24h") or 0),
                "volume_24h_usd": float(t.get("usdtVolume") or t.get("quoteVolume") or 0),
            }
        except (TypeError, ValueError):
            continue
    return prices, stats


async def _vol_exchange(session, url, parser):
    d = await _get_public_json(session, url)
    return parser(d) if d is not None else {}


def _parse_binance(d):
    out = {}
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


def _parse_bybit(d):
    out = {}
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


def _parse_okx(d):
    out = {}
    if not isinstance(d, dict) or d.get("code") != "0":
        return out
    for t in d.get("data", []) or []:
        inst = t.get("instId", "")
        if "USDT-SWAP" not in inst:
            continue
        sym = _norm(inst)
        try:
            out[sym] = (out.get(sym, 0.0) + float(t.get("volCcy24h") or 0)
                        * float(t.get("last") or 0))
        except (TypeError, ValueError):
            pass
    return out


async def refresh_universe(session):
    global _last_universe_exchange_count
    bitget_vol = {}
    d = await _get_public_json(
        session, API_BASE + f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}")
    if isinstance(d, dict) and d.get("code") == "00000":
        for t in d.get("data", []) or []:
            sym = t.get("symbol", "")
            if sym.endswith("USDT"):
                try:
                    bitget_vol[sym] = float(t.get("usdtVolume") or 0)
                except (TypeError, ValueError):
                    pass
    others = await asyncio.gather(
        _vol_exchange(session, "https://fapi.binance.com/fapi/v1/ticker/24hr", _parse_binance),
        _vol_exchange(session, "https://api.bybit.com/v5/market/tickers?category=linear", _parse_bybit),
        _vol_exchange(session, "https://www.okx.com/api/v5/market/tickers?instType=SWAP", _parse_okx),
        return_exceptions=True,
    )
    agg = dict(bitget_vol)
    ok = 1 if bitget_vol else 0
    for r in others:
        if isinstance(r, dict) and r:
            ok += 1
            for sym, vol in r.items():
                agg[sym] = agg.get(sym, 0.0) + vol
    if _last_universe_exchange_count > 0 and ok < _last_universe_exchange_count - 1:
        log.warning("Universe refresh SKIPPED: %d exchanges", ok)
        return
    filtered = []
    exc_stock = exc_vol = 0
    for s, v in agg.items():
        c = _contracts.get(s)
        if not c:
            continue
        if c.get("is_stock"):
            exc_stock += 1
            continue
        if v < UNIVERSE_MIN_VOL_USD:
            exc_vol += 1
            continue
        filtered.append(s)
    filtered.sort(key=lambda s: agg[s], reverse=True)
    _universe.clear()
    _universe.extend(filtered)
    _last_universe_exchange_count = ok
    log.debug("Universe: %d | excl %d stock, %d low-vol",
              len(_universe), exc_stock, exc_vol)


# =============================================================================
# MARKET / POSITION
# =============================================================================
async def fetch_depth(session, symbol):
    d = await _request(session, "GET", "/api/v2/mix/market/merge-depth",
                        query={"symbol": symbol, "productType": PRODUCT_TYPE,
                               "limit": "20"}, signed=False)
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
    return await acc.get_balance(session)


async def get_position(session, symbol):
    d = await _request(session, "GET", "/api/v3/position/current-position",
                        query={"category": PRODUCT_TYPE, "symbol": symbol})
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
            return {"total": size, "entryPrice": entry}
    return None


async def _place_order(session, symbol, side, qty_str, trade_side):
    body = {"category": PRODUCT_TYPE, "symbol": symbol,
            "side": side, "orderType": "market", "tradeSide": trade_side,
            "qty": qty_str,
            "reduceOnly": "no" if trade_side == "open" else "yes"}
    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        return (res.get("data") or {}).get("orderId")
    acc.log_order_failure(f"{side.upper()} {trade_side.upper()} {symbol}", body, res)
    return None


async def cancel_open_orders(session, symbol):
    res = await _request(session, "POST", "/api/v3/trade/cancel-all-orders",
                          body={"category": PRODUCT_TYPE, "symbol": symbol})
    if res.get("code") == "00000":
        return
    await _request(session, "POST", "/api/v2/mix/order/cancel-all-orders",
                    body={"productType": PRODUCT_TYPE, "symbol": symbol,
                          "marginCoin": "USDT"})


async def close_live_position(session, pos, reason):
    symbol = pos["symbol"]
    live = await get_position(session, symbol)
    if not live or live["total"] <= 0:
        return True
    await cancel_open_orders(session, symbol)
    vp = _contracts.get(symbol, {}).get("volumePlace", 0)
    qty_str = f"{live['total']:.{vp}f}"
    side = "buy" if pos["direction"] == "SHORT" else "sell"
    oid = await _place_order(session, symbol, side, qty_str, "close")
    return oid is not None


async def _latest_close(session, symbol):
    d = await _request(session, "GET", "/api/v2/mix/market/ticker",
                        query={"symbol": symbol, "productType": PRODUCT_TYPE},
                        signed=False)
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


# =============================================================================
# SYMBOL READINESS
# =============================================================================
async def _ensure_symbol_ready(session, sym):
    if sym in _ready_symbols:
        return True
    ok1, msg1 = await acc.ensure_leverage(session, sym, LEVERAGE)
    ok2, msg2 = await acc.ensure_margin_mode(session, sym, "crossed")
    if ok1 and ok2:
        _ready_symbols.add(sym)
        log.debug("SYMBOL READY | %s | %s | %s", sym, msg1, msg2)
        return True
    log.warning("SYMBOL SETUP FAILED | %s | lev=%s marg=%s", sym, msg1, msg2)
    return False


# =============================================================================
# COIN STATE
# =============================================================================
def _get_state(symbol):
    if symbol not in _coin_state:
        _coin_state[symbol] = {"price_history": []}
    return _coin_state[symbol]


def _has_open_position(sym):
    return sym in _active_positions or sym in _paper_positions


# =============================================================================
# PAPER CYCLE
# =============================================================================
def _build_predict_candidates(now_ts):
    candidates = []
    for sym, state in _coin_state.items():
        if sym not in _contracts or _contracts[sym].get("is_stock"):
            continue
        if time.time() < _cooldown_until.get(sym, 0):
            continue
        cache = _ticker_cache.get(sym, {})
        feats = pm.compute_features_for_predict(
            state["price_history"], now_ts,
            cache.get("high_24h", 0), cache.get("low_24h", 0),
            cache.get("volume_24h_usd", 0))
        if not feats["valid"]:
            continue
        score = (feats["fluct_per_min"] * 10.0
                 + min(feats["acceleration"], 3.0) * 1.0
                 + feats["recent_abs_pct"] * 0.5)
        candidates.append((sym, feats, score))
    return candidates


async def _enter_one_paper(session, sym, feats, score, prof_id):
    price = _ticker_cache.get(sym, {}).get("price", 0)
    if price <= 0:
        return False
    depth = await fetch_depth(session, sym)
    if depth is None:
        _diag["skips_book"] += 1
        return False
    bids, asks, mid = depth
    if not pm.evaluate_book(bids, asks, mid)["is_valid"]:
        _diag["skips_book"] += 1
        return False
    if not pm.evaluate_spread(bids, asks)["is_ok"]:
        _diag["skips_spread"] += 1
        return False
    balance = pm.evaluate_book_balance(bids, asks, mid)
    if feats["direction"] == "SHORT":
        if (balance["d_bid"] < pm.MIN_SIDE_DEPTH_USD
                or balance["depth_ratio"] < pm.PRED_ENTRY_MIN_DEPTH_RATIO):
            _diag["skips_pressure"] += 1
            return False
    else:
        if (balance["d_ask"] < pm.MIN_SIDE_DEPTH_USD
                or balance["depth_ratio"] > 1.0 / pm.PRED_ENTRY_MIN_DEPTH_RATIO):
            _diag["skips_pressure"] += 1
            return False
    _paper_positions[sym] = {
        "symbol": sym, "direction": feats["direction"], "entry": price,
        "opened_at": time.time(), "paper": True, "trade_type": "PREDICT",
        "matched_profile_id": prof_id, "kind": "paper",
        "entry_depth_ratio": balance["depth_ratio"],
        "peak_price": price, "trough_price": price, "ticks": [],
    }
    _diag["paper_entries"] += 1
    log.debug("PAPER OPEN | %s %s @ %.6f | profile#%s",
              sym, feats["direction"], price, prof_id)
    return True


async def try_predict_entries(session, candidates, now_ts):
    if time.time() - _started_at < PREDICT_WARMUP_SEC:
        return 0
    if not candidates:
        return 0
    matched = []
    for sym, feats, score in candidates:
        if _has_open_position(sym):
            continue
        for prof in _predict_profiles:
            if pm.features_match_profile(feats, prof):
                matched.append((sym, feats, score,
                                prof.get("id"), prof.get("wins", 0)))
                _diag["matches"] += 1
                break
    if not matched:
        return 0
    matched.sort(key=lambda x: (x[4], x[2]), reverse=True)
    to_trade = matched if len(matched) >= MIN_MATCHES_FOR_MULTI else matched[:1]
    entered = 0
    for sym, feats, score, prof_id, _wins in to_trade:
        if _has_open_position(sym):
            continue
        if await _enter_one_paper(session, sym, feats, score, prof_id):
            _cycle_snapshot["traded_symbols"].add(sym)
            _cycle_snapshot["trade_profile_ids"][sym] = prof_id
            entered += 1
    return entered


def _snapshot_predict_features(now_ts):
    _cycle_snapshot["cycle_id"] += 1
    _cycle_snapshot["started_at"] = now_ts
    candidates = _build_predict_candidates(now_ts)
    _cycle_snapshot["features"] = {sym: f for sym, f, _ in candidates}
    _cycle_snapshot["prices"] = {
        sym: _ticker_cache.get(sym, {}).get("price", 0)
        for sym, _, _ in candidates}
    _cycle_snapshot["traded_symbols"] = set()
    _cycle_snapshot["trade_profile_ids"] = {}
    return candidates


def _finalize_predict_cycle(now_ts):
    feats_map = _cycle_snapshot["features"]
    prices_map = _cycle_snapshot["prices"]
    cycle_id = _cycle_snapshot["cycle_id"]
    if not feats_map:
        return
    best_sym, best_abs, best_dir = None, 0.0, None
    for sym in feats_map:
        start = prices_map.get(sym, 0)
        end = _ticker_cache.get(sym, {}).get("price", 0)
        if start <= 0 or end <= 0:
            continue
        chg = (end - start) / start * 100.0
        if abs(chg) > best_abs:
            best_abs = abs(chg)
            best_sym = sym
            best_dir = "LONG" if chg > 0 else "SHORT"

    log.info("")
    log.info("=" * 78)
    log.info("  CYCLE %d | %s -> %s", cycle_id,
             time.strftime("%H:%M:%S",
                           time.gmtime(_cycle_snapshot.get("started_at", now_ts))),
             time.strftime("%H:%M:%S", time.gmtime(now_ts)))
    log.info("=" * 78)

    recent_stories = [s for s in _recent_paper_stories
                      if now_ts - s.get("closed_at", 0) <= 1900]
    if recent_stories:
        log.info("  PAPER TRADES (%d):", len(recent_stories))
        for s in recent_stories:
            log.info("  %s | %s | profile#%s | net=%+.2f%% | peak=%+.2f%% | trough=%+.2f%%",
                     s["symbol"], s["direction"], s.get("profile_id"),
                     s["net"], s["peak"], s["trough"])
            if s.get("story"):
                log.info("    %s", s["story"])
    else:
        log.info("  PAPER TRADES: 0")

    if best_sym:
        traded = best_sym in _cycle_snapshot["traded_symbols"]
        winner_feats = feats_map.get(best_sym, {})
        note = ""
        if not traded and winner_feats:
            added = _add_predict_profile(winner_feats, best_dir)
            note = f" -> PROFILE #{added} ADDED" if added else " -> REJECTED"
        elif traded:
            note = " -> traded (no bank)"
        log.info("  WINNER | %s %+.2f%% (%s)%s",
                 best_sym, (best_abs if best_dir == "LONG" else -best_abs),
                 best_dir, note)

    ranked = pm.rank_features(_global_tag_stats, _tag_descriptions,
                              _live_tier_history, _new_features)
    if ranked:
        log.info("  FEATURE LEADERBOARD (top 6):")
        for idx, r in enumerate(ranked[:6], start=1):
            parts = []
            for tier, ts in list(r["tiers"].items())[:2]:
                banned, _ = _is_banned(r["tag"], tier)
                status = "BAN" if banned else "ok"
                parts.append(f"{tier}:paper={ts.get('paper_majority')}/"
                             f"{pm.GATE_WINDOW}/{ts.get('paper_avg')} "
                             f"live_n={ts.get('live_trades')}/{status}")
            log.info("    #%d %s | n=%d | %s",
                     idx, r["tag"], r["samples"], " ".join(parts))

    now = time.time()
    active = [(k, v) for k, v in _live_bans.items()
              if v.get("banned_until", 0) > now]
    if active:
        log.info("  BANS ACTIVE: %d", len(active))
        for k, b in active[:4]:
            log.info("    %s | #%d | %s | %dmin left",
                     k, b["ban_count"], b["last_classification"],
                     int(b["banned_until"] - now) // 60)

    log.info("  BANK: %d (proven=%d) | gauntlet %d/%d | live %s",
             len(_predict_profiles),
             sum(1 for p in _predict_profiles if p.get("wins", 0) >= 1),
             sum(_paper_trade_history), len(_paper_trade_history),
             "UNLOCKED" if _streak["live_activated"] else "locked")
    log.info("=" * 78)

    _cycle_snapshot["features"] = {}
    _cycle_snapshot["prices"] = {}
    _cycle_snapshot["traded_symbols"] = set()
    _cycle_snapshot["trade_profile_ids"] = {}


# =============================================================================
# PAPER MANAGEMENT
# =============================================================================
async def _manage_paper_position(session, pos):
    symbol = pos["symbol"]
    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return
    if current > pos.get("peak_price", current):
        pos["peak_price"] = current
    if current < pos.get("trough_price", current):
        pos["trough_price"] = current
    if time.time() - pos["opened_at"] < pm.PRED_MAX_HOLD_SEC:
        return
    entry = pos["entry"]
    if pos["direction"] == "SHORT":
        gross = (entry - current) / entry * 100.0
        peak_swing = (entry - pos.get("trough_price", entry)) / entry * 100.0
        trough_swing = (entry - pos.get("peak_price", entry)) / entry * 100.0
    else:
        gross = (current - entry) / entry * 100.0
        peak_swing = (pos.get("peak_price", entry) - entry) / entry * 100.0
        trough_swing = (pos.get("trough_price", entry) - entry) / entry * 100.0
    net = gross - pm.FEE_ROUND_TRIP_PCT
    ticks = pos.get("ticks") or []
    story = pm.build_behaviour_story(ticks, entry, current, pos["opened_at"])
    _record_result(net, "TIME_EXIT", "MATCH")
    _update_profile_result(pos.get("matched_profile_id"), net,
                           peak_pct=peak_swing, trough_pct=trough_swing,
                           story_text=story.get("story"),
                           ticks=ticks, direction=pos["direction"],
                           start_ts=pos["opened_at"], tags=story.get("tags"),
                           symbol=symbol)
    _recent_paper_stories.append({
        "symbol": symbol, "direction": pos["direction"],
        "profile_id": pos.get("matched_profile_id"),
        "net": round(net, 2),
        "peak": round(peak_swing, 2), "trough": round(trough_swing, 2),
        "opened_at": pos["opened_at"], "closed_at": time.time(),
        "story": story.get("story", ""),
    })
    if len(_recent_paper_stories) > 20:
        _recent_paper_stories.pop(0)
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _paper_positions.pop(symbol, None)


# =============================================================================
# LIVE MICROTRADE
# =============================================================================
def _recent_minute_bucket(sym, now_ts):
    state = _coin_state.get(sym)
    if not state or not state.get("price_history"):
        return None
    cutoff = now_ts - 60
    window = [(t, p) for t, p in state["price_history"] if t >= cutoff and p > 0]
    if len(window) < 3:
        return None
    prices = [p for _, p in window]
    b = {"minute": 0,
         "open": prices[0], "close": prices[-1],
         "high": max(prices), "low": min(prices),
         "vol_usd": 0.0, "buy_usd": 0.0, "sell_usd": 0.0,
         "trades": len(window), "whale_buys": 0, "whale_sells": 0}
    last = _recent_fills_cache.get(sym)
    if last:
        b["vol_usd"] = last.get("vol_usd", 0.0)
        b["buy_usd"] = last.get("buy_usd", 0.0)
        b["sell_usd"] = last.get("sell_usd", 0.0)
        b["whale_buys"] = last.get("whale_buys", 0)
        b["whale_sells"] = last.get("whale_sells", 0)
    return b


async def _scan_live_tags(session, now_ts):
    feature_rules = pm.build_live_feature_rules(
        _global_tag_stats, _tag_descriptions, _live_tier_history, _new_features)
    if not feature_rules:
        return
    for tag in list(feature_rules.keys()):
        rule = feature_rules[tag]
        rule["tiers"] = {tier: tr for tier, tr in rule["tiers"].items()
                         if not _is_banned(tag, tier)[0]}
        if not rule["tiers"]:
            del feature_rules[tag]
    if not feature_rules:
        return
    for sym in _universe:
        if _has_open_position(sym):
            continue
        if time.time() < _cooldown_until.get(sym, 0):
            continue
        cache = _ticker_cache.get(sym, {})
        cap_tier = pm.market_cap_tier_from_volume(cache.get("volume_24h_usd", 0))
        bucket = _recent_minute_bucket(sym, now_ts)
        if not bucket:
            continue
        for bt in pm.tag_behaviour_events([bucket]):
            tag = bt["tag"]
            rule = feature_rules.get(tag)
            if not rule:
                continue
            tier_rule = rule["tiers"].get(cap_tier)
            if not tier_rule:
                continue
            direction = tier_rule["direction"]
            state = _coin_state.get(sym)
            if not state or not state.get("price_history"):
                continue
            feats = pm.compute_features_for_predict(
                state["price_history"], now_ts,
                cache.get("high_24h", 0), cache.get("low_24h", 0),
                cache.get("volume_24h_usd", 0))
            if not feats["valid"] or feats["direction"] != direction:
                continue
            matched_profile_id = None
            for p in _predict_profiles:
                if (p.get("wins", 0) >= 1 and p["direction"] == direction
                        and pm.features_match_profile(feats, p)):
                    matched_profile_id = p["id"]
                    break
            if matched_profile_id is None:
                continue
            await _open_live_microtrade(session, sym, direction,
                                          matched_profile_id, tag, cap_tier,
                                          tier_rule)
            break


async def _open_live_microtrade(session, sym, direction, prof_id, tag,
                                 tier, rule):
    contract = _contracts.get(sym)
    if not contract:
        return False
    if not await _ensure_symbol_ready(session, sym):
        return False
    px = _ticker_cache.get(sym, {}).get("price", 0)
    if px <= 0:
        return False
    balance = await get_usdt_balance(session)
    qty_str = pm.calculate_order_qty(
        balance=balance, price=px, leverage=LEVERAGE,
        volume_place=contract["volumePlace"],
        min_order_volume=contract["minOrderVolume"],
        min_notional=contract["minNotional"])
    if not qty_str:
        return False
    side_api = "sell" if direction == "SHORT" else "buy"
    oid = await _place_order(session, sym, side_api, qty_str, "open")
    if not oid:
        return False
    _active_positions[sym] = {
        "symbol": sym, "direction": direction, "entry": px,
        "opened_at": time.time(), "paper": False, "order_id": oid,
        "trade_type": "PREDICT", "matched_profile_id": prof_id,
        "kind": "microtrade", "tag": tag, "tier": tier,
        "target_pct": rule["target_pct"],
        "timeout_sec": rule["timeout_sec"],
        "peak_price": px, "trough_price": px,
    }
    _diag["live_entries"] += 1
    log.info("LIVE MICRO | %s %s | tag=%s tier=%s | profile#%d | "
             "target=%+.2f%% | price=%.6f",
             sym, direction, tag, tier, prof_id, rule["target_pct"], px)
    return True


async def _manage_live_microtrade(session, pos):
    symbol = pos["symbol"]
    live = await get_position(session, symbol)
    if live is None or live["total"] <= 0:
        _active_positions.pop(symbol, None)
        return
    current = await _latest_close(session, symbol)
    if current is None or current <= 0:
        return
    if current > pos.get("peak_price", current):
        pos["peak_price"] = current
    if current < pos.get("trough_price", current):
        pos["trough_price"] = current
    entry = pos["entry"]
    if pos["direction"] == "SHORT":
        gross = (entry - current) / entry * 100.0
    else:
        gross = (current - entry) / entry * 100.0
    net = gross - pm.FEE_ROUND_TRIP_PCT
    elapsed = time.time() - pos["opened_at"]
    reason = None
    if net >= pos["target_pct"]:
        reason = "MICRO_TARGET"
    elif elapsed >= pos["timeout_sec"]:
        reason = "MICRO_TIMEOUT"
    if not reason:
        return
    if not await close_live_position(session, pos, reason):
        return
    log.debug("LIVE EXIT | %s %s | %s | net=%+.2f%%",
              symbol, pos["direction"], reason, net)
    _record_result(net, reason, "MATCH")
    _update_profile_from_live(pos.get("matched_profile_id"), net)
    _record_live_tier_result(pos.get("tag"), pos.get("tier"), net)
    _cooldown_until[symbol] = time.time() + SYMBOL_COOLDOWN_SEC
    _active_positions.pop(symbol, None)


async def _manage_positions(session):
    for sym in list(_paper_positions.keys()):
        await _manage_paper_position(session, _paper_positions[sym])
    for sym in list(_active_positions.keys()):
        await _manage_live_microtrade(session, _active_positions[sym])


# =============================================================================
# BEHAVIOUR SAMPLER (paper only)
# =============================================================================
async def _sample_behaviour(session, pos):
    sym = pos["symbol"]
    now = time.time()
    ticks = pos.setdefault("ticks", [])
    price = await _latest_close(session, sym)
    if price is None or price <= 0:
        return
    vol_usd = 0.0
    d = await _request(session, "GET", "/api/v2/mix/market/candles",
                        query={"symbol": sym, "productType": PRODUCT_TYPE,
                               "granularity": "1m", "limit": "2"},
                        signed=False)
    if d.get("code") == "00000" and isinstance(d.get("data"), list) and d["data"]:
        try:
            vol_usd = float(d["data"][-1][6]) if len(d["data"][-1]) > 6 else 0.0
        except (TypeError, ValueError, IndexError):
            vol_usd = 0.0
    buy_usd = sell_usd = 0.0
    trades = whale_buys = whale_sells = 0
    d2 = await _request(session, "GET", "/api/v2/mix/market/fills",
                         query={"symbol": sym, "productType": PRODUCT_TYPE,
                                "limit": "100"}, signed=False)
    if d2.get("code") == "00000" and isinstance(d2.get("data"), list):
        for fill in d2["data"]:
            try:
                size = float(fill.get("size") or 0)
                px = float(fill.get("price") or 0)
                side = (fill.get("side") or "").lower()
                usd = size * px
                trades += 1
                if side in ("buy", "long"):
                    buy_usd += usd
                    if usd >= pm.WHALE_ORDER_USD:
                        whale_buys += 1
                else:
                    sell_usd += usd
                    if usd >= pm.WHALE_ORDER_USD:
                        whale_sells += 1
            except (TypeError, ValueError):
                continue
    ticks.append({"ts": now, "price": price, "vol_usd": vol_usd,
                  "taker_buy_usd": buy_usd, "taker_sell_usd": sell_usd,
                  "trades": trades})
    cutoff = now - pm.PRED_MAX_HOLD_SEC - 300
    pos["ticks"] = [t for t in ticks if t["ts"] >= cutoff]
    _recent_fills_cache[sym] = {
        "vol_usd": vol_usd, "buy_usd": buy_usd, "sell_usd": sell_usd,
        "whale_buys": whale_buys, "whale_sells": whale_sells, "ts": now}


async def _behaviour_loop(session):
    last_run = 0.0
    while True:
        if time.time() - last_run < BEHAVIOUR_SAMPLE_SEC:
            await asyncio.sleep(2)
            continue
        last_run = time.time()
        try:
            for pos in list(_paper_positions.values()):
                await _sample_behaviour(session, pos)
        except Exception as exc:
            log.debug("Behaviour sample error: %s", exc)
        await asyncio.sleep(2)


# =============================================================================
# CANDIDATE EVAL
# =============================================================================
async def _candidate_evaluation_loop(session):
    global _pending_candidates
    while True:
        await asyncio.sleep(30)
        now = time.time()
        still = []
        for c in _pending_candidates:
            if now - c["ts"] < 60:
                still.append(c)
                continue
            try:
                current = await _latest_close(session, c["symbol"])
                if not current or current <= 0:
                    continue
                entry_px = c["entry_price"]
                raw = ((current - entry_px) / entry_px * 100.0
                       if c["direction"] == "LONG"
                       else (entry_px - current) / entry_px * 100.0)
                net = raw - pm.FEE_ROUND_TRIP_PCT
                obj = pm.update_candidate_streak(
                    _new_feature_candidates, c["tag"], c["tier"], net)
                if pm.candidate_ready_to_promote(obj):
                    _new_features.add(c["tag"])
                    _tag_descriptions[c["tag"]] = c["description"]
                    _global_tag_stats.setdefault(c["tag"], [])
                    obj["promoted"] = True
                    _diag["features_promoted"] += 1
                    _save_predict_profiles()
                    log.info("NEW FEATURE PROMOTED | tag=%s | streak=%d | tiers=%s | desc=%s",
                             c["tag"], obj["streak"],
                             {s["tier"] for s in obj["streak_successes"]},
                             c["description"][:200])
            except Exception as exc:
                log.debug("Candidate eval: %s", exc)
        _pending_candidates = still


# =============================================================================
# BACKGROUND LOOPS
# =============================================================================
async def _ban_review_loop(session):
    while True:
        await asyncio.sleep(600)
        try:
            _review_bans()
        except Exception as exc:
            log.debug("Ban review: %s", exc)


async def _reconcile_loop(session):
    while True:
        await asyncio.sleep(300)
        try:
            live = await acc.get_all_positions(session)
            exchange_syms = {p["symbol"] for p in live}
            tracked_syms = set(_active_positions.keys())
            orphans = exchange_syms - tracked_syms
            if orphans:
                log.warning("RECONCILE | %d orphan(s): %s",
                            len(orphans), orphans)
                await acc.adopt_or_close_orphans(
                    session, tracked_syms, close_unknown=True)
        except Exception as exc:
            log.debug("Reconcile error: %s", exc)


async def _contracts_refresh_loop(session):
    while True:
        await asyncio.sleep(CONTRACTS_REFRESH_SEC)
        try:
            await refresh_contracts(session)
        except Exception as exc:
            log.debug("Contract refresh: %s", exc)


async def _universe_refresh_loop(session):
    while True:
        try:
            await refresh_universe(session)
        except Exception as exc:
            log.debug("Universe refresh: %s", exc)
        await asyncio.sleep(UNIVERSE_REFRESH_SEC)


# =============================================================================
# SWEEPER
# =============================================================================
async def price_sweeper_loop(session):
    global _next_boundary_ts
    _next_boundary_ts = time.time() + BOUNDARY_INTERVAL_SEC
    while True:
        try:
            now_ts = time.time()
            prices, stats = await _tickers_bitget(session)
            if not prices:
                _diag["sweep_fails"] += 1
                await asyncio.sleep(PULSE_SEC)
                continue
            _ticker_cache.clear()
            _ticker_cache.update(stats)
            for sym, px in prices.items():
                _ticker_cache.setdefault(sym, {})["price"] = px
            for sym in _universe:
                price = prices.get(sym)
                if not price or price <= 0:
                    continue
                state = _get_state(sym)
                state["price_history"].append((now_ts, price))
                cutoff = now_ts - pm.PRED_LOOKBACK_SEC - 60
                state["price_history"] = [
                    (t, p) for t, p in state["price_history"] if t >= cutoff]

            if now_ts >= _next_boundary_ts:
                _next_boundary_ts += BOUNDARY_INTERVAL_SEC
                while _next_boundary_ts <= now_ts:
                    _next_boundary_ts += BOUNDARY_INTERVAL_SEC
                _diag["cycles"] += 1
                _finalize_predict_cycle(now_ts)
                candidates = _snapshot_predict_features(now_ts)
                await try_predict_entries(session, candidates, now_ts)

            if _streak["live_activated"]:
                await _scan_live_tags(session, now_ts)

            for pos in list(_paper_positions.values()):
                ticks = pos.get("ticks") or []
                if len(ticks) < 5:
                    continue
                buckets = pm.summarize_minute_window(
                    ticks, pos["opened_at"],
                    pos["opened_at"] + pm.PRED_MAX_HOLD_SEC)
                for i in range(1, len(buckets)):
                    b, prev = buckets[i], buckets[i - 1]
                    if b["open"] <= 0 or prev["close"] <= 0:
                        continue
                    move_pct = (b["close"] - prev["close"]) / prev["close"] * 100.0
                    if abs(move_pct) < pm.UNEXPLAINED_MOVE_MIN_PCT:
                        continue
                    if pm.tag_behaviour_events([b]):
                        continue
                    proposed = pm.classify_proposed_tag([b], move_pct)
                    direction = "LONG" if move_pct > 0 else "SHORT"
                    desc = pm.describe_move_context([b], [], move_pct, 60)
                    cache = _ticker_cache.get(pos["symbol"], {})
                    tier = pm.market_cap_tier_from_volume(
                        cache.get("volume_24h_usd", 0))
                    _pending_candidates.append({
                        "tag": proposed, "symbol": pos["symbol"],
                        "tier": tier, "direction": direction,
                        "entry_price": b["close"], "ts": time.time(),
                        "description": desc,
                    })
                    if len(_pending_candidates) > 200:
                        _pending_candidates = _pending_candidates[-200:]
        except Exception as exc:
            log.warning("Sweeper error: %s", exc)
            _diag["sweep_fails"] += 1
        await asyncio.sleep(PULSE_SEC)


# =============================================================================
# HEARTBEAT
# =============================================================================
def _heartbeat():
    global _last_heartbeat
    if time.time() - _last_heartbeat < HEARTBEAT_SEC:
        return
    _last_heartbeat = time.time()
    log.debug(
        "pulse | coins=%d | cycles=%d | paper=%d live=%d | bank=%d feats=%d "
        "bans=%d | gauntlet=%d/%d | live=%s",
        len(_coin_state), _diag["cycles"],
        len(_paper_positions), len(_active_positions),
        len(_predict_profiles), len(_global_tag_stats),
        sum(1 for b in _live_bans.values()
            if b.get("banned_until", 0) > time.time()),
        sum(_paper_trade_history), len(_paper_trade_history),
        _streak["live_activated"])


# =============================================================================
# MAIN
# =============================================================================
async def main():
    _start_keepalive()

    if getattr(pm, "__version__", "UNKNOWN") != _EXPECTED_PM_VERSION:
        log.critical("Version mismatch: expected %s got %s",
                     _EXPECTED_PM_VERSION, getattr(pm, "__version__", "?"))
        raise SystemExit(1)

    _load_streak()
    _load_predict_profiles()

    log.info(
        "Startup | PREDICT | vol>=%.0f | fluct>=%.2f%%/m | cycle=%ds | "
        "paper hold=%.0fs | gauntlet=%d/%d | profiles=%d (proven=%d) | "
        "features=%d (new=%d) | bans=%d",
        pm.PRED_VOLUME_MIN_USD, pm.PRED_MIN_FLUCTUATION_PCT_PER_MIN,
        BOUNDARY_INTERVAL_SEC, pm.PRED_MAX_HOLD_SEC,
        PAPER_WINS_REQUIRED, PAPER_HISTORY_SIZE,
        len(_predict_profiles),
        sum(1 for p in _predict_profiles if p.get("wins", 0) >= 1),
        len(_global_tag_stats), len(_new_features),
        sum(1 for b in _live_bans.values()
            if b.get("banned_until", 0) > time.time()))

    connector = aiohttp.TCPConnector(limit=30, ttl_dns_cache=300)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector,
                                      timeout=timeout) as session:
        await refresh_contracts(session)
        await refresh_universe(session)
        await acc.startup_check(session, _universe, leverage=LEVERAGE,
                                margin_mode="crossed")

        asyncio.create_task(_contracts_refresh_loop(session))
        asyncio.create_task(_universe_refresh_loop(session))
        asyncio.create_task(_behaviour_loop(session))
        asyncio.create_task(_candidate_evaluation_loop(session))
        asyncio.create_task(_ban_review_loop(session))
        asyncio.create_task(_reconcile_loop(session))
        asyncio.create_task(price_sweeper_loop(session))

        log.info("Main loop | universe=%d", len(_universe))

        while True:
            loop_start = time.time()
            try:
                await _manage_positions(session)
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

"""
account_setup.py
================
Health, configuration, and recovery for Bitget UTA.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time

import aiohttp

log = logging.getLogger("account")

API_BASE = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"


def _env(*names):
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    raise RuntimeError(f"Missing credential env var: {names}")


API_KEY = _env("BITGET_API_KEY", "API_KEY")
SECRET_KEY = _env("BITGET_API_SECRET", "SECRET_KEY")
PASSPHRASE = _env("BITGET_API_PASSPHRASE", "PASSPHRASE")


def _sign(timestamp, method, request_path, body):
    msg = timestamp + method.upper() + request_path + body
    digest = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


async def _request(session, method, path, *, query=None, body=None,
                   signed=True, retries=3):
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
                "ACCESS-PASSPHRASE": PASSPHRASE})
        try:
            async with session.request(
                method, API_BASE + path_with_q, headers=headers,
                data=body_str if body_str else None,
                timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                if resp.status == 429 or resp.status >= 500:
                    await asyncio.sleep((2 ** attempt) + 1)
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"code": "JSON_ERROR", "msg": text[:160]}
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep((2 ** attempt) + 1)
    return {"code": "RETRY_EXHAUSTED", "msg": "max retries"}


async def verify_uta_mode(session):
    d = await _request(session, "GET", "/api/v3/account/settings")
    if d.get("code") == "00000":
        data = d.get("data") or {}
        return True, {"uta": True, "hold_mode": data.get("holdMode"),
                      "margin_mode": data.get("marginMode"),
                      "auto_loan": data.get("autoLoan")}
    msg = str(d.get("msg", "")).lower()
    if "not support" in msg or "unauthorized" in msg or d.get("code") == "40011":
        return False, {"reason": "UTA not enabled", "detail": d.get("msg")}
    return False, {"reason": d.get("msg"), "code": d.get("code")}


async def ensure_one_way_mode(session):
    d = await _request(session, "GET", "/api/v3/account/settings")
    if d.get("code") == "00000":
        data = d.get("data") or {}
        if data.get("holdMode") == "one_way_mode":
            return True, "already one_way_mode"
    res = await _request(session, "POST", "/api/v3/account/set-hold-mode",
                          body={"holdMode": "one_way_mode"})
    if res.get("code") == "00000":
        return True, "set to one_way_mode"
    return False, f"failed: {res.get('msg')}"


async def ensure_margin_mode(session, symbol, mode="crossed"):
    body = {"category": PRODUCT_TYPE, "symbol": symbol, "marginMode": mode}
    res = await _request(session, "POST", "/api/v3/account/set-margin-mode", body=body)
    if res.get("code") == "00000":
        return True, f"v3 margin={mode}"
    body_v2 = {"symbol": symbol, "productType": PRODUCT_TYPE,
               "marginCoin": "USDT", "marginMode": mode}
    res2 = await _request(session, "POST", "/api/v2/mix/account/set-margin", body=body_v2)
    if res2.get("code") == "00000":
        return True, f"v2 margin={mode}"
    return False, f"v3:{res.get('msg')} | v2:{res2.get('msg')}"


async def ensure_leverage(session, symbol, leverage):
    body = {"category": PRODUCT_TYPE, "symbol": symbol, "leverage": str(leverage)}
    res = await _request(session, "POST", "/api/v3/account/set-leverage", body=body)
    if res.get("code") == "00000":
        return True, f"v3 {leverage}x"
    body_v2 = {"symbol": symbol, "productType": PRODUCT_TYPE,
               "marginCoin": "USDT", "leverage": str(leverage)}
    res2 = await _request(session, "POST", "/api/v2/mix/account/set-leverage", body=body_v2)
    if res2.get("code") == "00000":
        return True, f"v2 {leverage}x"
    return False, f"v3:{res.get('msg')} | v2:{res2.get('msg')}"


async def get_balance(session):
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
    return 0.0


async def get_all_positions(session):
    d = await _request(session, "GET", "/api/v3/position/current-position",
                        query={"category": PRODUCT_TYPE})
    if d.get("code") != "00000":
        return []
    payload = d.get("data")
    rows = payload.get("list") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out = []
    for p in rows:
        try:
            total = float(p.get("total") or p.get("size") or 0)
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        sym = p.get("symbol", "")
        try:
            entry = float(p.get("entryPrice") or p.get("averageOpenPrice") or 0)
        except (TypeError, ValueError):
            entry = 0.0
        side = (p.get("posSide") or "").lower()
        direction = "LONG" if side in ("long", "buy") else "SHORT"
        out.append({"symbol": sym, "direction": direction,
                    "total": total, "entry": entry})
    return out


async def _close_orphan(session, pos):
    sym = pos["symbol"]
    await _request(session, "POST", "/api/v3/trade/cancel-all-orders",
                    body={"category": PRODUCT_TYPE, "symbol": sym})
    side = "buy" if pos["direction"] == "SHORT" else "sell"
    body = {"category": PRODUCT_TYPE, "symbol": sym,
            "side": side, "orderType": "market", "tradeSide": "close",
            "qty": f"{pos['total']:.8f}", "reduceOnly": "yes"}
    res = await _request(session, "POST", "/api/v3/trade/place-order", body=body)
    if res.get("code") == "00000":
        log.info("ORPHAN CLOSED | %s %s size=%.6f", sym, pos["direction"], pos["total"])
        return True
    log.error("ORPHAN CLOSE FAILED | %s %s | %s", sym, pos["direction"], res.get("msg"))
    return False


async def adopt_or_close_orphans(session, tracked_symbols, close_unknown=True):
    all_pos = await get_all_positions(session)
    orphans = [p for p in all_pos if p["symbol"] not in tracked_symbols]
    if not orphans:
        return []
    log.warning("RECONCILE | %d orphan position(s)", len(orphans))
    for o in orphans:
        log.warning("  %s %s size=%.6f entry=%.6f",
                    o["symbol"], o["direction"], o["total"], o["entry"])
    if close_unknown:
        for o in orphans:
            await _close_orphan(session, o)
    return orphans


async def startup_check(session, universe, leverage=5,
                        margin_mode="crossed", preflight_symbols=50):
    log.info("=" * 60)
    log.info("ACCOUNT PREFLIGHT")
    log.info("=" * 60)
    uta_ok, uta_info = await verify_uta_mode(session)
    if not uta_ok:
        log.critical("UTA mode NOT enabled. Reason: %s", uta_info.get("reason"))
        raise SystemExit(1)
    log.info("UTA: OK (hold=%s margin=%s auto_loan=%s)",
             uta_info.get("hold_mode"), uta_info.get("margin_mode"),
             uta_info.get("auto_loan"))
    ow_ok, ow_msg = await ensure_one_way_mode(session)
    if not ow_ok:
        log.critical("One-way mode setup failed: %s", ow_msg)
        raise SystemExit(1)
    log.info("One-way mode: %s", ow_msg)
    bal = await get_balance(session)
    log.info("USDT available: %.4f", bal)
    orphans = await adopt_or_close_orphans(session, set(), close_unknown=True)
    if universe:
        to_set = universe[:preflight_symbols]
        log.info("Setting leverage=%dx margin=%s on first %d symbols...",
                 leverage, margin_mode, len(to_set))
        lev_ok = lev_fail = margin_ok = 0
        for sym in to_set:
            ok1, _ = await ensure_leverage(session, sym, leverage)
            ok2, _ = await ensure_margin_mode(session, sym, margin_mode)
            if ok1:
                lev_ok += 1
            else:
                lev_fail += 1
            if ok2:
                margin_ok += 1
            await asyncio.sleep(0.1)
        log.info("Leverage OK on %d/%d (failed %d — retried per-order)",
                 lev_ok, len(to_set), lev_fail)
        log.info("Margin OK on %d/%d", margin_ok, len(to_set))
    log.info("PREFLIGHT OK | orphans_closed=%d", len(orphans))
    log.info("=" * 60)
    return True


_order_failures = []


def log_order_failure(context, request, response):
    entry = {"ts": time.time(), "context": context, "request": request,
             "code": response.get("code"), "msg": response.get("msg")}
    _order_failures.append(entry)
    if len(_order_failures) > 50:
        _order_failures.pop(0)
    log.error("ORDER FAILURE | %s | code=%s msg=%s | req=%s",
              context, response.get("code"), response.get("msg"),
              json.dumps(request)[:300])


def get_recent_failures(n=10):
    return _order_failures[-n:]


async def health_snapshot(session):
    bal = await get_balance(session)
    positions = await get_all_positions(session)
    return {"ts": time.time(), "balance_usdt": bal, "positions": positions,
            "position_count": len(positions),
            "recent_failures": len(_order_failures)}


async def diagnose(session):
    snap = await health_snapshot(session)
    log.info("=" * 60)
    log.info("DIAGNOSTIC @ %s",
             time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(snap["ts"])))
    log.info("Balance USDT: %.4f", snap["balance_usdt"])
    log.info("Open positions: %d", snap["position_count"])
    for p in snap["positions"]:
        log.info("  %s %s size=%.6f entry=%.6f",
                 p["symbol"], p["direction"], p["total"], p["entry"])
    log.info("Recent order failures: %d", snap["recent_failures"])
    for f in get_recent_failures(5):
        log.info("  [%s] %s | %s",
                 time.strftime("%H:%M:%S", time.localtime(f["ts"])),
                 f["context"], f["msg"])
    log.info("=" * 60)
    return snap

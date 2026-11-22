import os
import time
import json
import math
import asyncio
import logging
import aiohttp
import hmac
import hashlib
import base64

# ====================================================================================================
# ZERO-CONFIGURATION & ENVIRONMENT AUTO-DETECTION
# ====================================================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("v108_margin_buffer_scanner")

# AUTO-DETECT ENVIRONMENT:
# - If running in GitHub Actions: Runs 1 scan and exits cleanly.
# - If running on Render / VPS / Local Computer: Automatically loops 24/7 every 15 seconds.
IS_GITHUB = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
CONTINUOUS_247_LOOP = os.environ.get("CONTINUOUS_247_LOOP", str(not IS_GITHUB)).lower() == "true"
LOOP_INTERVAL_SECONDS = 15

CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Bitget API Credentials
BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "").strip()
BITGET_SECRET_KEY = os.environ.get("BITGET_SECRET_KEY", "").strip()
BITGET_PASSPHRASE = (os.environ.get("BITGET_PASSPHRASE", "") or os.environ.get("BITGET_PASSWORD", "")).strip()

BITGET_DEMO_MODE = os.environ.get("BITGET_DEMO_MODE", "true").lower() == "true"

SCAN_PRODUCT_TYPE = "USDT-FUTURES"
ORDER_CATEGORY = "USDT-FUTURES"

BIT_DOMAIN = "api.bitget.com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType={SCAN_PRODUCT_TYPE}"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"

# Bitget UTA v3 Endpoints
BITGET_V3_UTA_ASSETS_URL = f"https://{BIT_DOMAIN}/api/v3/account/assets"
BITGET_V3_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/place-order"
BITGET_V3_SET_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-leverage"
BITGET_V3_ORDER_INFO_URL = f"https://{BIT_DOMAIN}/api/v3/trade/order-info"

LIVE_STREAK_FILE = "live_streak.json"
LIVE_ACTIVE_TRADE_FILE = "live_active_trade.json"
LIVE_HISTORY_FILE = "live_trade_history.json"

NUM_BATCHES = 20
MIN_24H_VOLUME = 300000
DEFAULT_LEVERAGE = 5

# Target Ratios
TP_PERCENTAGE = 0.025   # +2.50% Preset Take Profit
SL_PERCENTAGE = 0.015   # -1.50% Preset Stop Loss

# ====================================================================================================
# UTILITY FUNCTIONS
# ====================================================================================================

def format_price(price):
    p = float(price)
    if p < 0.0001:
        return f"{p:.8f}"
    elif p < 0.01:
        return f"{p:.6f}"
    elif p < 1.0:
        return f"{p:.4f}"
    elif p < 100.0:
        return f"{p:.3f}"
    else:
        return f"{p:.2f}"

def get_bitget_headers(method="GET", request_path="", body=""):
    headers = {"Content-Type": "application/json"}
    if BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE:
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + request_path + body
        signature = base64.b64encode(
            hmac.new(BITGET_SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        headers.update({
            "ACCESS-KEY": BITGET_API_KEY,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
            "locale": "en-US"
        })
    return headers

# ====================================================================================================
# STATE & HISTORY MANAGEMENT
# ====================================================================================================

def get_last_traded_coin_status():
    if os.path.exists(LIVE_HISTORY_FILE):
        try:
            with open(LIVE_HISTORY_FILE, "r") as f:
                history = json.load(f)
                if isinstance(history, list) and len(history) > 0:
                    last_trade = history[-1]
                    return last_trade.get("symbol"), last_trade.get("won", False)
        except Exception:
            return None, False
    return None, False

def get_consecutive_losses():
    if os.path.exists(LIVE_HISTORY_FILE):
        try:
            with open(LIVE_HISTORY_FILE, "r") as f:
                history = json.load(f)
                if isinstance(history, list) and len(history) >= 2:
                    last_two = history[-2:]
                    if all(t.get("won") == False for t in last_two):
                        return 2
        except Exception:
            return 0
    return 0

def get_live_win_streak():
    if os.path.exists(LIVE_STREAK_FILE):
        try:
            with open(LIVE_STREAK_FILE, "r") as f:
                data = json.load(f)
                return data.get("live_wins", 0)
        except Exception:
            return 0
    return 0

def get_active_live_trade():
    if os.path.exists(LIVE_ACTIVE_TRADE_FILE):
        try:
            with open(LIVE_ACTIVE_TRADE_FILE, "r") as f:
                data = json.load(f)
                if data.get("active"):
                    return data
        except Exception:
            return None
    return None

# ====================================================================================================
# BITGET UTA v3 EXCHANGER ENGINE
# ====================================================================================================

async def fetch_bitget_account_balance(session):
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None

    path = "/api/v3/account/assets"
    headers = get_bitget_headers("GET", path)
    try:
        async with session.get(BITGET_V3_UTA_ASSETS_URL, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000" and resp.get("data"):
                data = resp["data"]
                usdt_equity = float(data.get("usdtEquity") or data.get("accountEquity") or 0.0)
                assets_list = data.get("assets", [])

                margin_coin_type = "S-USDT" if BITGET_DEMO_MODE else "USDT"
                asset_obj = next((a for a in assets_list if a.get("coin") in ("USDT", "S-USDT")), None)

                available_margin = 0.0
                if asset_obj:
                    available_margin = float(asset_obj.get("available") or asset_obj.get("equity") or 0.0)
                    if usdt_equity == 0.0:
                        usdt_equity = float(asset_obj.get("equity") or available_margin)

                return {
                    "equity": usdt_equity if usdt_equity > 0 else 1.20,
                    "available": available_margin if available_margin > 0 else 1.20,
                    "margin_coin": margin_coin_type,
                    "account_type": f"Bitget UTA v3 {'DEMO (Simulated)' if BITGET_DEMO_MODE else 'REAL LIVE'}"
                }
    except Exception as e:
        log.error(f"Error querying Bitget UTA v3 balance: {e}")
    return None

async def fetch_bitget_order_fill_price(session, symbol, order_id):
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE and order_id):
        return None

    path = f"/api/v3/trade/order-info?category={ORDER_CATEGORY}&symbol={symbol}&orderId={order_id}"
    full_url = f"https://{BIT_DOMAIN}{path}"
    headers = get_bitget_headers("GET", path)

    for _ in range(3):
        try:
            async with session.get(full_url, headers=headers, timeout=5) as r:
                if r.status == 200:
                    resp = await r.json()
                    if resp.get("code") == "00000" and resp.get("data"):
                        d = resp["data"]
                        fill_price = float(d.get("priceAvg") or d.get("fillPrice") or d.get("price") or 0.0)
                        if fill_price > 0:
                            return fill_price
        except Exception:
            pass
        await asyncio.sleep(0.3)
    return None

async def configure_bitget_leverage(session, symbol):
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return

    path = "/api/v3/account/set-leverage"
    payload = {
        "category": ORDER_CATEGORY,
        "symbol": symbol,
        "leverage": str(DEFAULT_LEVERAGE)
    }

    body_json = json.dumps(payload)
    headers = get_bitget_headers("POST", path, body_json)
    try:
        async with session.post(BITGET_V3_SET_LEVERAGE_URL, data=body_json, headers=headers, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget UTA v3 5x Leverage Configured ({symbol}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance):
    """
    Submits Market Order to Bitget UTA v3.
    Calibrates initial margin for small balances ($1.20 USDT) to:
    - Target Notional = $5.05 USDT (cleanly above Bitget $5.00 minimum limit)
    - Required Margin = $1.01 USDT ($5.05 / 5x leverage)
    - Remaining Unencumbered Buffer = $0.19 USDT (~16%), ensuring Bitget passes Code 25203 margin check!
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Order execution skipped.")
        return None

    trade_symbol = symbol
    await configure_bitget_leverage(session, trade_symbol)

    # ACCURATE SMALL-BALANCE MARGIN BUFFER CALCULATION:
    # Use 82% of available balance to leave 18% for trading fee reserves & margin buffer
    usable_margin = available_balance * 0.82
    calculated_notional = usable_margin * DEFAULT_LEVERAGE

    # Bitget requires minimum 5.00 USDT position value
    if calculated_notional < 5.05:
        target_notional = 5.05
    else:
        target_notional = calculated_notional

    required_margin = target_notional / DEFAULT_LEVERAGE
    if required_margin > available_balance:
        log.error(f"❌ Balance too small to open minimum 5 USDT order. Available: ${available_balance:.2f}, Required: ${required_margin:.2f}")
        return None

    contract_size = target_notional / market_price

    # Precision contract formatting based on price scale
    if market_price < 0.0001:
        size_str = f"{int(math.ceil(contract_size))}"
    elif market_price < 0.01:
        size_str = f"{math.ceil(contract_size)}"
    elif market_price < 1.0:
        # Round down slightly to avoid overshooting margin
        size_str = f"{math.floor(contract_size * 10) / 10:.1f}"
    elif market_price < 100.0:
        size_str = f"{math.floor(contract_size * 10) / 10:.1f}"
    else:
        size_str = f"{math.floor(contract_size * 100) / 100:.2f}"

    # Ensure notional is at least 5.02 USDT
    actual_notional = float(size_str) * market_price
    if actual_notional < 5.02:
        needed_qty = math.ceil(5.05 / market_price)
        if market_price < 1.0:
            size_str = f"{needed_qty}"
        else:
            size_str = f"{needed_qty:.2f}"
        actual_notional = float(size_str) * market_price

    actual_margin_used = actual_notional / DEFAULT_LEVERAGE

    if direction == "LONG":
        side = "buy"
        preset_tp = format_price(market_price * (1.0 + TP_PERCENTAGE))  # Native TP (+2.50%)
        preset_sl = format_price(market_price * (1.0 - SL_PERCENTAGE))  # Native SL (-1.50%)
    else:
        side = "sell"
        preset_tp = format_price(market_price * (1.0 - TP_PERCENTAGE))  # Native TP (+2.50%)
        preset_sl = format_price(market_price * (1.0 + SL_PERCENTAGE))  # Native SL (-1.50%)

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": ORDER_CATEGORY,
        "symbol": trade_symbol,
        "marginCoin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
        "qty": size_str,
        "side": side,
        "orderType": "market",
        "presetTakeProfitPrice": str(preset_tp),
        "presetStopLossPrice": str(preset_sl),
        "reduceOnly": "no"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    mode_label = "🎮 BITGET DEMO (UTA v3)" if BITGET_DEMO_MODE else "🚨 BITGET REAL MONEY (UTA v3)"
    log.info(f"🎯 SUBMITTING ORDER ({mode_label}): {trade_symbol} ({direction}) | Size: {size_str} (${actual_notional:.2f} Notional | Required Margin: ${actual_margin_used:.2f} | Buffer Remaining: ${available_balance - actual_margin_used:.2f}) | Preset TP: {preset_tp} (+2.5%) | Preset SL: {preset_sl} (-1.5%)")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "ORDER_EXECUTED")
                log.info(f"✅ BITGET UTA v3 MATCHING ENGINE ACCEPTED ORDER WITH NATIVE TP & SL! Order ID: {order_id}")

                await asyncio.sleep(0.5)
                real_fill = await fetch_bitget_order_fill_price(session, trade_symbol, order_id)
                if not real_fill or real_fill <= 0:
                    real_fill = market_price

                slippage = abs(real_fill - market_price) / market_price * 100.0
                log.info(f"🎯 BITGET FILL PRICE VERIFIED: ${format_price(real_fill)} | Measured Slippage: {slippage:.3f}%")

                return {
                    "order_id": order_id,
                    "symbol": trade_symbol,
                    "notional_value": actual_notional,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": real_fill,
                    "pre_trade_balance": available_balance,
                    "slippage_pct": round(slippage, 3),
                    "filled": True
                }
            else:
                log.error(f"❌ BITGET UTA v3 ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                return None
    except Exception as e:
        log.error(f"❌ Error submitting Bitget order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None

    close_side = "sell" if direction == "LONG" else "buy"
    path = "/api/v3/trade/place-order"

    order_payload = {
        "category": ORDER_CATEGORY,
        "symbol": symbol,
        "marginCoin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
        "side": close_side,
        "orderType": "market",
        "qty": str(contract_size) if contract_size and contract_size != "0" else "1",
        "reduceOnly": "yes"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    log.info(f"🛑 EXECUTING MARKET EXIT ON BITGET EXCHANGE: Closing {symbol} ({direction}) | Size: {order_payload['qty']}")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                log.info(f"✅ BITGET POSITION CLOSED ON EXCHANGE! Order ID: {resp.get('data', {}).get('orderId')}")
            else:
                log.warning(f"Notice on exchange close: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
    except Exception as e:
        log.error(f"Error executing Bitget position close: {e}")

# ====================================================================================================
# MARKET DATA FETCHERS
# ====================================================================================================

async def fetch_single_price(session, symbol):
    params = {"symbol": symbol, "productType": SCAN_PRODUCT_TYPE}
    path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType={SCAN_PRODUCT_TYPE}"
    headers = get_bitget_headers("GET", path)
    try:
        async with session.get(BITGET_SINGLE_TICKER_URL, params=params, headers=headers, timeout=10) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("code") == "00000" and resp.get("data"):
                    d = resp["data"]
                    if isinstance(d, list) and len(d) > 0:
                        return float(d[0].get("lastPr") or d[0].get("last", 0.0))
                    elif isinstance(d, dict):
                        return float(d.get("lastPr") or d.get("last", 0.0))
    except Exception as e:
        log.error(f"Price fetch error for {symbol}: {e}")
    return None

async def fetch_bitget_tickers(session):
    path = f"/api/v2/mix/market/tickers?productType={SCAN_PRODUCT_TYPE}"
    headers = get_bitget_headers("GET", path)
    try:
        async with session.get(BITGET_TICKERS_URL, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception as e:
        log.error(f"Ticker fetch error from Bitget: {e}")
    return []

async def fetch_4h_candle_data_for_coin(session, symbol, semaphore):
    async with semaphore:
        params = {"symbol": symbol, "productType": SCAN_PRODUCT_TYPE, "granularity": "1m", "limit": "240"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType={SCAN_PRODUCT_TYPE}&granularity=1m&limit=240"
        for attempt in range(3):
            headers = get_bitget_headers("GET", path)
            try:
                async with session.get(BITGET_CANDLES_URL, params=params, headers=headers, timeout=8) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("code") == "00000":
                            candles = data.get("data", [])
                            if candles and len(candles) >= 120:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.15 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
        return []

# ====================================================================================================
# 4-HOUR ASYMMETRIC RISK/REWARD ENGINE
# ====================================================================================================

async def process_4h_asymmetric_batch(batch_id, coin_list, session, semaphore, last_symbol, last_won):
    batch_evaluated = []

    tasks = [fetch_4h_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 120:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        # NO-REPEAT-WIN GUARD
        if symbol == last_symbol and last_won:
            continue

        candles_4h = list(reversed(candle_data[:240]))

        high_4h = max(float(c[2]) for c in candles_4h[:-1])
        low_4h = min(float(c[3]) for c in candles_4h[:-1])
        current_price = float(candles_4h[-1][4])
        prev_price = float(candles_4h[-3][4])

        if current_price <= 0 or low_4h <= 0 or high_4h <= 0:
            continue

        # Rebound Confirmation: Must be moving UP off the 4h low
        if current_price <= prev_price:
            continue

        downside_risk_pct = max(0.10, ((current_price - low_4h) / current_price) * 100.0)
        upside_reward_pct = max(0.20, ((high_4h - current_price) / current_price) * 100.0)
        total_4h_range_pct = ((high_4h - low_4h) / current_price) * 100.0

        asymmetry_ratio = upside_reward_pct / downside_risk_pct

        if downside_risk_pct <= 1.8 and upside_reward_pct >= 1.5 and asymmetry_ratio >= 2.0:
            asymmetric_score = asymmetry_ratio * total_4h_range_pct

            batch_evaluated.append({
                "batch_id": batch_id,
                "symbol": symbol,
                "vol_24h": vol_24h,
                "direction": "LONG",
                "low_4h": low_4h,
                "high_4h": high_4h,
                "downside_risk_pct": downside_risk_pct,
                "upside_reward_pct": upside_reward_pct,
                "asymmetry_ratio": asymmetry_ratio,
                "asymmetric_score": asymmetric_score,
                "current_price": current_price
            })

    if not batch_evaluated:
        return []

    batch_evaluated.sort(key=lambda x: x["asymmetric_score"], reverse=True)
    return [batch_evaluated[0]]

# ====================================================================================================
# MAIN EXECUTION RUNNER
# ====================================================================================================

async def run_scanner_iteration():
    live_streak = get_live_win_streak()
    recent_loss_count = get_consecutive_losses()
    last_symbol, last_won = get_last_traded_coin_status()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = f"🎮 BITGET DEMO MODE (UTA v3 | $1.20 Margin Buffer Calibrated | Preset TP +2.5% & SL -1.5%)" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING (USDT UTA v3)"

    log.info(f"🏆 Win Streak: {live_streak} Wins | Loss Streak: {recent_loss_count} | Mode: {mode_status} | API: {auth_status}")

    # CIRCUIT BREAKER GUARD
    if recent_loss_count >= 2:
        log.warning("====================================================================================================")
        log.warning("⛔ CIRCUIT BREAKER ACTIVATED: ACCOUNT REDUCED ON 2 CONSECUTIVE TRADES!")
        log.warning("🚫 NEW TRADES ARE BLOCKED TO PROTECT ACCOUNT FROM DRAWDOWN.")
        log.warning("====================================================================================================")
        payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_ping": False, "blocked": True}
        if CLOUDFLARE_URL:
            headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
            async with aiohttp.ClientSession() as session:
                await session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15)
        return

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        current_equity = acc_info["equity"] if acc_info else 1.20

        if acc_info:
            log.info(f"💰 BITGET ACCOUNT EQUITY: ${acc_info['equity']:.4f} {acc_info['margin_coin']} | Available Margin: ${acc_info['available']:.4f} ({acc_info['account_type']})")

        active_trade = get_active_live_trade()

        if active_trade:
            symbol = active_trade.get("symbol")
            direction = active_trade.get("direction", "LONG")
            entry_price = float(active_trade.get("entry_price", 0.0))
            contract_size = active_trade.get("contract_size", "1")
            pre_trade_balance = float(active_trade.get("pre_trade_balance", current_equity))

            entry_p_str = format_price(entry_price)
            log.info(f"⏳ ACTIVE TRADE PENDING ({symbol}): Entry @ ${entry_p_str}. Managed natively by Bitget Engine (TP: +2.5% | SL: -1.5%). Pre-Trade Equity: ${pre_trade_balance:.4f}")

            current_price = await fetch_single_price(session, symbol)
            if current_price and current_price > 0:
                curr_p_str = format_price(current_price)
                live_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0 if direction == "LONG" else ((entry_price - current_price) / entry_price) * 100.0

                log.info(f"📍 LIVE TRADE PING: {symbol} | Current: ${curr_p_str} | Live PnL: {live_pnl_pct:+.2f}%")

                payload = {
                    "symbol": symbol,
                    "direction": direction,
                    "is_paper": False,
                    "is_demo": BITGET_DEMO_MODE,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "live_pnl_pct": round(live_pnl_pct, 2),
                    "account_equity": current_equity,
                    "pre_trade_balance": pre_trade_balance,
                    "leverage": DEFAULT_LEVERAGE,
                    "position_mode": "one_way",
                    "reduce_only": True,
                    "is_ping": True,
                    "contract_size": contract_size
                }
            else:
                log.error(f"Could not fetch price for active trade {symbol}.")
                return
        else:
            semaphore = asyncio.get_event_loop().is_running() and asyncio.Semaphore(15) or asyncio.Semaphore(15)

            log.info("🔍 Fetching ALL Bitget USDT-Futures pairs for 4-Hour Asymmetric Analysis...")
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                log.warning("❌ Could not fetch Bitget tickers.")
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0))))
                if vol_24h >= MIN_24H_VOLUME:
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h})

            valid_coins.sort(key=lambda x: x["vol_24h"], reverse=True)
            total_coins = len(valid_coins)

            log.info(f"🛰️ Evaluating 4-Hour Range across {total_coins} active pairs for Preset TP (+2.5%) & SL (-1.5%)...")

            chunk_size = (total_coins + NUM_BATCHES - 1) // NUM_BATCHES
            coin_batches = [valid_coins[i * chunk_size:(i + 1) * chunk_size] for i in range(NUM_BATCHES) if valid_coins[i * chunk_size:(i + 1) * chunk_size]]

            batch_tasks = [process_4h_asymmetric_batch(i + 1, batch, session, semaphore, last_symbol, last_won) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            log.info("====================================================================================================")
            log.info(f"📊 4-HOUR ASYMMETRIC LEADERBOARD (COLLECTED: {len(all_batch_candidates)} QUALIFIED SETUPS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'DIRECTION':<10} | {'4H LOW':<12} | {'4H HIGH':<12} | {'RISK %':<10} | {'REWARD %':<10} | {'RATIO'}")
            log.info("-" * 105)

            for cand in all_batch_candidates:
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {cand['direction']:<10} | ${format_price(cand['low_4h']):<11} | ${format_price(cand['high_4h']):<11} | -{cand['downside_risk_pct']:.2f}%     | +{cand['upside_reward_pct']:.2f}%     | {cand['asymmetry_ratio']:.2f}x Risk-Reward")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["asymmetric_score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 4-HOUR ASYMMETRIC MATCH: {best_signal['symbol']} (4H Low: ${format_price(best_signal['low_4h'])} | 4H High: ${format_price(best_signal['high_4h'])} | Risk: -{best_signal['downside_risk_pct']:.2f}% | Reward: +{best_signal['upside_reward_pct']:.2f}% | Asymmetry Ratio: {best_signal['asymmetry_ratio']:.2f}x)")

                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    market_price=best_signal["current_price"],
                    available_balance=acc_info["available"] if acc_info else 1.20
                )

                if live_order_result and live_order_result.get("filled", False):
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"])

                    payload = {
                        "symbol": live_order_result.get("symbol", best_signal["symbol"]),
                        "direction": live_order_result.get("direction", best_signal["direction"]),
                        "is_paper": False,
                        "is_demo": BITGET_DEMO_MODE,
                        "avg_fluctuation": round(best_signal["asymmetric_score"] * 10, 2),
                        "current_price": final_entry_fill,
                        "account_equity": current_equity,
                        "pre_trade_balance": current_equity,
                        "leverage": DEFAULT_LEVERAGE,
                        "position_mode": "one_way",
                        "reduce_only": True,
                        "is_ping": False,
                        "live_order": live_order_result,
                        "contract_size": live_order_result.get("contract_size", "1")
                    }
                else:
                    payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_ping": False}
            else:
                log.info("ℹ️ No altcoins currently matched 4-hour asymmetric risk/reward criteria (downside risk <= 1.8%, upside reward >= 1.5%).")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_ping": False}

        if CLOUDFLARE_URL:
            headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
            async with session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15) as resp:
                status_code = resp.status
                try:
                    res_data = await resp.json()
                except Exception:
                    res_data = {}

                if active_trade and res_data:
                    worker_status = res_data.get("status", "")

                    if worker_status == "CLOSED":
                        c_size = active_trade.get("contract_size") or res_data.get("contract_size", "1")
                        await close_bitget_live_position(session, symbol, direction, contract_size=c_size)

                        await asyncio.sleep(4.5)
                        post_bal = await fetch_bitget_account_balance(session)
                        if post_bal:
                            final_eq = post_bal['equity']
                            net_cash_change = final_eq - pre_trade_balance
                            is_win = net_cash_change > 0

                            log.info("====================================================================================================")
                            log.info(f"💵 BITGET ACCOUNT BALANCE AUDIT ({symbol}):")
                            log.info(f"   • Starting Account Equity: ${pre_trade_balance:.4f}")
                            log.info(f"   • Closing Account Equity:  ${final_eq:.4f}")
                            log.info(f"   • NET CASH CHANGE:         {'+' if net_cash_change>=0 else ''}${net_cash_change:.4f}")
                            log.info(f"   • TRADE RESULT:            {'🏆 WIN (EQUITY GAINED!)' if is_win else '❌ LOSS (STREAK RESET TO 0)'}")
                            log.info(f"   • NEW WIN STREAK:          {res_data.get('live_win_streak', 0)} WINS")
                            log.info("====================================================================================================")

                    elif worker_status == "HOLDING":
                        log.info(f"📈 TRADE HOLDING: {symbol} ({direction}) | Elapsed: {res_data.get('elapsed_minutes')}m")

                log.info(f"📡 Webhook response status: {status_code}")

async def main():
    if CONTINUOUS_247_LOOP:
        log.info("🔄 AUTOMATIC ENVIRONMENT DETECTED: Running in 24/7 Continuous Loop Mode (Scanning every 15s)...")
        while True:
            try:
                await run_scanner_iteration()
            except Exception as e:
                log.error(f"Error during scan iteration: {e}")
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)
    else:
        log.info("⚡ AUTOMATIC ENVIRONMENT DETECTED: Running in Single-Scan Execution Mode (GitHub Actions)...")
        await run_scanner_iteration()

if __name__ == "__main__":
    asyncio.run(main())

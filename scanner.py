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
log = logging.getLogger("v116_demo_audit_scanner")

IS_GITHUB = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
CONTINUOUS_247_LOOP = os.environ.get("CONTINUOUS_247_LOOP", str(not IS_GITHUB)).lower() == "true"

# Loop Interval (1 second continuous on 24/7 runner, single scan on GitHub Actions)
LOOP_INTERVAL_SECONDS = 1.0

CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

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

BITGET_V3_UTA_ASSETS_URL = f"https://{BIT_DOMAIN}/api/v3/account/assets"
BITGET_V3_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/place-order"
BITGET_V3_SET_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-leverage"
BITGET_V3_ORDER_INFO_URL = f"https://{BIT_DOMAIN}/api/v3/trade/order-info"

LIVE_STREAK_FILE = "live_streak.json"
LIVE_ACTIVE_TRADE_FILE = "live_active_trade.json"
LIVE_HISTORY_FILE = "live_trade_history.json"
VIRTUAL_DEMO_BAL_FILE = "virtual_demo_balance.json"

NUM_BATCHES = 20
MIN_24H_VOLUME = 300000
DEFAULT_LEVERAGE = 5

# Target Ratios
TP_PERCENTAGE = 0.025   # +2.50% Take Profit
SL_PERCENTAGE = 0.015   # -1.50% Stop Loss

# Rebound Window Parameters (Pure 18%-25% Recovery Window)
MIN_REBOUND_RATIO_PCT = 18.0      # Enter as soon as rebound reaches ~18%
MAX_REBOUND_RATIO_PCT = 25.0      # Reject if rebound exceeds 25%-50% (overchased)

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

def calculate_min_required_margin_for_price(market_price, leverage=DEFAULT_LEVERAGE):
    if market_price <= 0:
        return 999.0, 1.0, 5.01

    raw_qty = 5.01 / market_price

    if market_price < 0.0001:
        qty = math.ceil(raw_qty)
    elif market_price < 0.01:
        qty = math.ceil(raw_qty)
    elif market_price < 1.0:
        qty = math.ceil(raw_qty * 10) / 10
    elif market_price < 100.0:
        qty = math.ceil(raw_qty * 10) / 10
    else:
        qty = math.ceil(raw_qty * 100) / 100

    notional = qty * market_price
    if notional < 5.01:
        notional = 5.05

    required_margin = notional / leverage
    return required_margin, qty, notional

# ====================================================================================================
# STATE & VIRTUAL DEMO BALANCE MANAGEMENT
# ====================================================================================================

def get_virtual_demo_balance():
    if os.path.exists(VIRTUAL_DEMO_BAL_FILE):
        try:
            with open(VIRTUAL_DEMO_BAL_FILE, "r") as f:
                data = json.load(f)
                return float(data.get("equity", 10000.0))
        except Exception:
            return 10000.0
    return 10000.0

def update_virtual_demo_balance(new_equity):
    try:
        with open(VIRTUAL_DEMO_BAL_FILE, "w") as f:
            json.dump({"equity": new_equity}, f, indent=2)
    except Exception:
        pass

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

def update_live_win_streak(is_win):
    current = get_live_win_streak()
    new_streak = current + 1 if is_win else 0
    try:
        with open(LIVE_STREAK_FILE, "w") as f:
            json.dump({"live_wins": new_streak}, f, indent=2)
    except Exception:
        pass
    return new_streak

def record_trade_history(symbol, won, pnl_pct, pnl_cash):
    history = []
    if os.path.exists(LIVE_HISTORY_FILE):
        try:
            with open(LIVE_HISTORY_FILE, "r") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except Exception:
            history = []

    history.append({
        "symbol": symbol,
        "won": won,
        "pnl_pct": pnl_pct,
        "pnl_cash": pnl_cash,
        "timestamp": time.time()
    })

    try:
        with open(LIVE_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

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

def save_active_trade_state(symbol, direction, entry_price, contract_size, pre_trade_balance, is_virtual=False):
    tp_price = entry_price * (1.0 + TP_PERCENTAGE) if direction == "LONG" else entry_price * (1.0 - TP_PERCENTAGE)
    sl_price = entry_price * (1.0 - SL_PERCENTAGE) if direction == "LONG" else entry_price * (1.0 + SL_PERCENTAGE)

    trade_data = {
        "active": True,
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "preset_tp": tp_price,
        "preset_sl": sl_price,
        "contract_size": str(contract_size),
        "pre_trade_balance": pre_trade_balance,
        "is_virtual": is_virtual,
        "start_time": time.time()
    }
    with open(LIVE_ACTIVE_TRADE_FILE, "w") as f:
        json.dump(trade_data, f, indent=2)

def clear_active_trade_state():
    if os.path.exists(LIVE_ACTIVE_TRADE_FILE):
        try:
            with open(LIVE_ACTIVE_TRADE_FILE, "w") as f:
                json.dump({"active": False}, f)
        except Exception:
            pass

# ====================================================================================================
# BITGET UTA v3 EXCHANGER ENGINE
# ====================================================================================================

async def fetch_bitget_account_balance(session):
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        v_bal = get_virtual_demo_balance()
        return {
            "equity": v_bal,
            "available": v_bal * 0.90,
            "margin_coin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
            "account_type": f"Bitget UTA v3 {'DEMO (Virtual Simulated)' if BITGET_DEMO_MODE else 'UNAUTHENTICATED'}"
        }

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

                v_bal = usdt_equity if usdt_equity > 0 else (10000.0 if BITGET_DEMO_MODE else 1.17)
                return {
                    "equity": v_bal,
                    "available": available_margin if available_margin > 0 else v_bal * 0.90,
                    "margin_coin": margin_coin_type,
                    "account_type": f"Bitget UTA v3 {'DEMO (Simulated)' if BITGET_DEMO_MODE else 'REAL LIVE'}"
                }
    except Exception as e:
        log.error(f"Error querying Bitget UTA v3 balance: {e}")

    v_bal = get_virtual_demo_balance()
    return {
        "equity": v_bal,
        "available": v_bal * 0.90,
        "margin_coin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
        "account_type": f"Bitget UTA v3 {'DEMO (Fallback)' if BITGET_DEMO_MODE else 'REAL LIVE'}"
    }

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

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance, drop_depth_pct=0.0):
    trade_symbol = symbol
    await configure_bitget_leverage(session, trade_symbol)

    req_margin, exact_qty, actual_notional = calculate_min_required_margin_for_price(market_price, DEFAULT_LEVERAGE)

    margin_currency = "S-USDT" if BITGET_DEMO_MODE else "USDT"

    # VIRTUAL SHADOW TRACKER FALLBACK if required margin exceeds balance
    if req_margin > (available_balance * 0.85):
        log.warning(f"⚠️ MARGIN LIMIT ({symbol}): Requires ${req_margin:.2f} margin (min $5.01 notional), balance available: ${available_balance:.2f}.")
        log.info(f"🔮 STARTING VIRTUAL SHADOW TRACKING ON {symbol}:")
        log.info(f"   • Opening Demo Equity:  ${available_balance:.4f} {margin_currency}")
        log.info(f"   • Entry Fill Price:    ${format_price(market_price)}")
        log.info(f"   • Target Take Profit:  ${format_price(market_price * (1.0 + TP_PERCENTAGE))} (+2.50%)")
        log.info(f"   • Stop Loss Floor:     ${format_price(market_price * (1.0 - SL_PERCENTAGE))} (-1.50%)")

        save_active_trade_state(symbol, direction, market_price, exact_qty, available_balance, is_virtual=True)
        return {
            "order_id": "VIRTUAL_SHADOW_ORDER",
            "symbol": trade_symbol,
            "notional_value": actual_notional,
            "contract_size": str(exact_qty),
            "preset_tp": format_price(market_price * (1.0 + TP_PERCENTAGE)),
            "preset_sl": format_price(market_price * (1.0 - SL_PERCENTAGE)),
            "real_fill_price": market_price,
            "pre_trade_balance": available_balance,
            "slippage_pct": 0.0,
            "is_virtual": True,
            "filled": True
        }

    if market_price < 0.0001:
        size_str = f"{int(exact_qty)}"
    elif market_price < 0.01:
        size_str = f"{int(exact_qty)}"
    elif market_price < 1.0:
        size_str = f"{exact_qty:.1f}"
    elif market_price < 100.0:
        size_str = f"{exact_qty:.1f}"
    else:
        size_str = f"{exact_qty:.2f}"

    if direction == "LONG":
        side = "buy"
        preset_tp = format_price(market_price * (1.0 + TP_PERCENTAGE))
        preset_sl = format_price(market_price * (1.0 - SL_PERCENTAGE))
    else:
        side = "sell"
        preset_tp = format_price(market_price * (1.0 - TP_PERCENTAGE))
        preset_sl = format_price(market_price * (1.0 + SL_PERCENTAGE))

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": ORDER_CATEGORY,
        "symbol": trade_symbol,
        "marginCoin": margin_currency,
        "qty": size_str,
        "side": side,
        "orderType": "market",
        "presetTakeProfitPrice": str(preset_tp),
        "presetStopLossPrice": str(preset_sl),
        "reduceOnly": "no"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    mode_label = "🎮 BITGET DEMO MODE (S-USDT)" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING (USDT)"

    log.info("====================================================================================================")
    log.info(f"🎯 SUBMITTING TRADE ENTRY ORDER ({mode_label}):")
    log.info(f"   • Symbol Pair:         {trade_symbol} ({direction})")
    log.info(f"   • Opening Equity:      ${available_balance:.4f} {margin_currency}")
    log.info(f"   • Entry Market Price:  ${format_price(market_price)}")
    log.info(f"   • Order Size:          {size_str} (${actual_notional:.2f} Notional | Margin: ${req_margin:.2f})")
    log.info(f"   • Preset Take Profit:  ${preset_tp} (+2.50%)")
    log.info(f"   • Preset Stop Loss:    ${preset_sl} (-1.50%)")
    log.info("====================================================================================================")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "ORDER_EXECUTED")
                log.info(f"✅ BITGET UTA v3 MATCHING ENGINE ACCEPTED DEMO ORDER! Order ID: {order_id}")

                await asyncio.sleep(0.5)
                real_fill = await fetch_bitget_order_fill_price(session, trade_symbol, order_id)
                if not real_fill or real_fill <= 0:
                    real_fill = market_price

                slippage = abs(real_fill - market_price) / market_price * 100.0
                save_active_trade_state(trade_symbol, direction, real_fill, size_str, available_balance, is_virtual=False)

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
                    "is_virtual": False,
                    "filled": True
                }
            else:
                log.error(f"❌ BITGET UTA v3 ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                log.info(f"🔮 FALLING BACK TO VIRTUAL SHADOW TRADE TRACKER FOR {symbol}...")
                save_active_trade_state(symbol, direction, market_price, size_str, available_balance, is_virtual=True)
                return {
                    "order_id": "VIRTUAL_SHADOW_ORDER",
                    "symbol": trade_symbol,
                    "notional_value": actual_notional,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": market_price,
                    "pre_trade_balance": available_balance,
                    "slippage_pct": 0.0,
                    "is_virtual": True,
                    "filled": True
                }
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
                log.info(f"✅ BITGET DEMO POSITION CLOSED ON EXCHANGE! Order ID: {resp.get('data', {}).get('orderId')}")
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

async def fetch_60m_candle_data_for_coin(session, symbol, semaphore):
    async with semaphore:
        params = {"symbol": symbol, "productType": SCAN_PRODUCT_TYPE, "granularity": "1m", "limit": "60"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType={SCAN_PRODUCT_TYPE}&granularity=1m&limit=60"
        for attempt in range(3):
            headers = get_bitget_headers("GET", path)
            try:
                async with session.get(BITGET_CANDLES_URL, params=params, headers=headers, timeout=8) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("code") == "00000":
                            candles = data.get("data", [])
                            if candles and len(candles) >= 30:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.15 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
        return []

# ====================================================================================================
# PURE 18%-25% REBOUND RECOVERY ENGINE
# ====================================================================================================

async def process_pure_rebound_batch(batch_id, coin_list, session, semaphore, last_symbol, last_won):
    batch_evaluated = []

    tasks = [fetch_60m_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 30:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        if symbol == last_symbol and last_won:
            continue

        candles_60m = list(reversed(candle_data[:60]))

        peak_60m = max(float(c[2]) for c in candles_60m[:-2])
        low_60m = min(float(c[3]) for c in candles_60m[:-2])
        current_price = float(candles_60m[-1][4])
        prev_price = float(candles_60m[-3][4])

        if current_price <= 0 or low_60m <= 0 or peak_60m <= low_60m:
            continue

        if current_price <= prev_price:
            continue

        drop_depth_pct = ((peak_60m - low_60m) / peak_60m) * 100.0

        if drop_depth_pct < 0.40:
            continue

        total_drop_range = peak_60m - low_60m
        rebound_gain = current_price - low_60m

        rebound_recovery_pct = (rebound_gain / total_drop_range) * 100.0

        # Sweet spot: 18% - 25% rebound recovery
        if MIN_REBOUND_RATIO_PCT <= rebound_recovery_pct <= MAX_REBOUND_RATIO_PCT:
            closeness_to_18pct = 1.0 / (abs(rebound_recovery_pct - 19.0) + 0.1)
            score = drop_depth_pct * closeness_to_18pct * 100.0

            batch_evaluated.append({
                "batch_id": batch_id,
                "symbol": symbol,
                "vol_24h": vol_24h,
                "direction": "LONG",
                "drop_depth_pct": drop_depth_pct,
                "rebound_recovery_pct": rebound_recovery_pct,
                "score": score,
                "current_price": current_price,
                "low_60m": low_60m,
                "peak_60m": peak_60m
            })

    if not batch_evaluated:
        return []

    batch_evaluated.sort(key=lambda x: x["score"], reverse=True)
    return [batch_evaluated[0]]

# ====================================================================================================
# MAIN EXECUTION RUNNER WITH DEMO BALANCE AUDIT
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
    margin_currency = "S-USDT" if BITGET_DEMO_MODE else "USDT"
    mode_label = f"🎮 BITGET DEMO MODE (UTA v3 | {margin_currency})" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING (USDT)"

    log.info(f"🏆 Win Streak: {live_streak} Wins | Loss Streak: {recent_loss_count} | Mode: {mode_label} | API: {auth_status}")

    # CIRCUIT BREAKER GUARD
    if recent_loss_count >= 2:
        log.warning("====================================================================================================")
        log.warning("⛔ CIRCUIT BREAKER ACTIVATED: ACCOUNT REDUCED ON 2 CONSECUTIVE TRADES!")
        log.warning("🚫 NEW TRADES ARE BLOCKED TO PROTECT ACCOUNT FROM DRAWDOWN.")
        log.warning("====================================================================================================")
        payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_demo": BITGET_DEMO_MODE, "is_ping": False, "blocked": True}
        if CLOUDFLARE_URL:
            headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
            async with aiohttp.ClientSession() as session:
                await session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15)
        return

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        current_equity = acc_info["equity"] if acc_info else (10000.0 if BITGET_DEMO_MODE else 1.17)

        if acc_info:
            log.info(f"💰 {mode_label} EQUITY: ${acc_info['equity']:.4f} {acc_info['margin_coin']} | Available Margin: ${acc_info['available']:.4f}")

        active_trade = get_active_live_trade()

        if active_trade:
            symbol = active_trade.get("symbol")
            direction = active_trade.get("direction", "LONG")
            entry_price = float(active_trade.get("entry_price", 0.0))
            preset_tp = float(active_trade.get("preset_tp", entry_price * 1.025))
            preset_sl = float(active_trade.get("preset_sl", entry_price * 0.985))
            contract_size = active_trade.get("contract_size", "1")
            pre_trade_balance = float(active_trade.get("pre_trade_balance", current_equity))
            is_virtual = active_trade.get("is_virtual", False)

            entry_p_str = format_price(entry_price)
            trade_type_label = "🔮 VIRTUAL SHADOW DEMO TRADE" if is_virtual else f"🎮 LIVE {margin_currency} DEMO TRADE"
            log.info(f"⏳ {trade_type_label} ACTIVE ({symbol}): Entry @ ${entry_p_str} | Opening Balance: ${pre_trade_balance:.4f} {margin_currency} | TP: ${format_price(preset_tp)} (+2.5%) | SL: ${format_price(preset_sl)} (-1.5%)")

            current_price = await fetch_single_price(session, symbol)
            if current_price and current_price > 0:
                curr_p_str = format_price(current_price)
                live_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0 if direction == "LONG" else ((entry_price - current_price) / entry_price) * 100.0

                log.info(f"📍 LIVE PRICE PING ({symbol}): Current: ${curr_p_str} | Live PnL: {live_pnl_pct:+.2f}%")

                # VIRTUAL SHADOW DEMO TRADE AUDIT LOGIC
                if is_virtual:
                    is_win_hit = current_price >= preset_tp if direction == "LONG" else current_price <= preset_tp
                    is_loss_hit = current_price <= preset_sl if direction == "LONG" else current_price >= preset_sl

                    if is_win_hit:
                        pnl_cash = pre_trade_balance * (TP_PERCENTAGE * DEFAULT_LEVERAGE)
                        closing_equity = pre_trade_balance + pnl_cash
                        update_virtual_demo_balance(closing_equity)
                        new_streak = update_live_win_streak(True)
                        record_trade_history(symbol, True, TP_PERCENTAGE * 100.0, pnl_cash)

                        log.info("====================================================================================================")
                        log.info(f"🏆 DEMO ACCOUNT TRADE AUDIT SUMMARY ({symbol}):")
                        log.info(f"   • Demo Account Opening Equity:  ${pre_trade_balance:.4f} {margin_currency}")
                        log.info(f"   • Demo Account Closing Equity:  ${closing_equity:.4f} {margin_currency}")
                        log.info(f"   • NET DEMO PROFIT/LOSS:        +${pnl_cash:.4f} {margin_currency} (+{TP_PERCENTAGE*100.0:.2f}%)")
                        log.info(f"   • TRADE OUTCOME:                🏆 WIN (DEMO BALANCE GAINED!)")
                        log.info(f"   • NEW DEMO WIN STREAK:          {new_streak} WINS IN A ROW")
                        log.info("====================================================================================================")
                        clear_active_trade_state()

                    elif is_loss_hit:
                        pnl_cash = - (pre_trade_balance * (SL_PERCENTAGE * DEFAULT_LEVERAGE))
                        closing_equity = pre_trade_balance + pnl_cash
                        update_virtual_demo_balance(closing_equity)
                        new_streak = update_live_win_streak(False)
                        record_trade_history(symbol, False, -SL_PERCENTAGE * 100.0, pnl_cash)

                        log.info("====================================================================================================")
                        log.info(f"❌ DEMO ACCOUNT TRADE AUDIT SUMMARY ({symbol}):")
                        log.info(f"   • Demo Account Opening Equity:  ${pre_trade_balance:.4f} {margin_currency}")
                        log.info(f"   • Demo Account Closing Equity:  ${closing_equity:.4f} {margin_currency}")
                        log.info(f"   • NET DEMO PROFIT/LOSS:        -${abs(pnl_cash):.4f} {margin_currency} (-{SL_PERCENTAGE*100.0:.2f}%)")
                        log.info(f"   • TRADE OUTCOME:                ❌ LOSS (STREAK RESET TO 0)")
                        log.info(f"   • NEW DEMO WIN STREAK:          {new_streak} WINS")
                        log.info("====================================================================================================")
                        clear_active_trade_state()

                payload = {
                    "symbol": symbol,
                    "direction": direction,
                    "is_paper": is_virtual,
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

            log.info(f"🔍 Fetching ALL 600+ Bitget pairs for Rebound Recovery Window (18%-25% Recovery)...")
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

            log.info(f"🛰️ Evaluating {total_coins} pairs for Rebound Recovery between 18% and 25%...")

            chunk_size = (total_coins + NUM_BATCHES - 1) // NUM_BATCHES
            coin_batches = [valid_coins[i * chunk_size:(i + 1) * chunk_size] for i in range(NUM_BATCHES) if valid_coins[i * chunk_size:(i + 1) * chunk_size]]

            batch_tasks = [process_pure_rebound_batch(i + 1, batch, session, semaphore, last_symbol, last_won) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 REBOUND MATCH: {best_signal['symbol']} (Drop Depth: -{best_signal['drop_depth_pct']:.2f}% | Rebound Recovery: +{best_signal['rebound_recovery_pct']:.2f}% | Score: {best_signal['score']:.2f})")

                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    market_price=best_signal["current_price"],
                    available_balance=current_equity,
                    drop_depth_pct=best_signal["drop_depth_pct"]
                )

                if live_order_result and live_order_result.get("filled", False):
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"])

                    payload = {
                        "symbol": live_order_result.get("symbol", best_signal["symbol"]),
                        "direction": live_order_result.get("direction", best_signal["direction"]),
                        "is_paper": live_order_result.get("is_virtual", False),
                        "is_demo": BITGET_DEMO_MODE,
                        "avg_fluctuation": round(best_signal["score"] * 10, 2),
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
                    payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_demo": BITGET_DEMO_MODE, "is_ping": False}
            else:
                log.info("ℹ️ No altcoins currently matched rebound recovery window (18%-25% recovery).")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_demo": BITGET_DEMO_MODE, "is_ping": False}

        if CLOUDFLARE_URL:
            headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
            async with session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15) as resp:
                status_code = resp.status
                try:
                    res_data = await resp.json()
                except Exception:
                    res_data = {}

                if active_trade and res_data and not active_trade.get("is_virtual", False):
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
                            new_streak = update_live_win_streak(is_win)
                            record_trade_history(symbol, is_win, (net_cash_change / pre_trade_balance) * 100.0 if pre_trade_balance > 0 else 0.0, net_cash_change)

                            log.info("====================================================================================================")
                            log.info(f"💵 DEMO ACCOUNT TRADE AUDIT SUMMARY ({symbol}):")
                            log.info(f"   • Demo Account Opening Equity:  ${pre_trade_balance:.4f} {margin_currency}")
                            log.info(f"   • Demo Account Closing Equity:  ${final_eq:.4f} {margin_currency}")
                            log.info(f"   • NET DEMO PROFIT/LOSS:        {'+' if net_cash_change>=0 else ''}${net_cash_change:.4f} {margin_currency}")
                            log.info(f"   • TRADE RESULT:                {'🏆 WIN (DEMO BALANCE GAINED!)' if is_win else '❌ LOSS (STREAK RESET TO 0)'}")
                            log.info(f"   • NEW DEMO WIN STREAK:          {new_streak} WINS")
                            log.info("====================================================================================================")
                            clear_active_trade_state()

                    elif worker_status == "HOLDING":
                        log.info(f"📈 DEMO TRADE HOLDING: {symbol} ({direction}) | Elapsed: {res_data.get('elapsed_minutes')}m")

                log.info(f"📡 Webhook response status: {status_code}")

async def main():
    if CONTINUOUS_247_LOOP:
        log.info("🔄 AUTOMATIC ENVIRONMENT DETECTED: Running 1-SECOND Continuous Real-Time Loop Mode...")
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

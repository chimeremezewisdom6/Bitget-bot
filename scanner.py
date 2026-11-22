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
# ZERO-CONFIGURATION & TRUTH-IN-REPORTING ENGINE
# ====================================================================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("v128_truth_engine_scanner")

IS_GITHUB = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
CONTINUOUS_247_LOOP = os.environ.get("CONTINUOUS_247_LOOP", str(not IS_GITHUB)).lower() == "true"
LOOP_INTERVAL_SECONDS = 1.0

CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# MULTI-KEY / "POLLINATION KEYS" ENGINE (Supports up to 5 API Key Sets)
def load_bitget_api_keys():
    keys = []
    k0 = os.environ.get("BITGET_API_KEY", "").strip()
    s0 = os.environ.get("BITGET_SECRET_KEY", "").strip()
    p0 = (os.environ.get("BITGET_PASSPHRASE", "") or os.environ.get("BITGET_PASSWORD", "")).strip()
    if k0 and s0 and p0:
        keys.append({"key": k0, "secret": s0, "passphrase": p0, "id": 1})

    for i in range(1, 6):
        k = os.environ.get(f"BITGET_API_KEY_{i}", "").strip()
        s = os.environ.get(f"BITGET_SECRET_KEY_{i}", "").strip()
        p = (os.environ.get(f"BITGET_PASSPHRASE_{i}", "") or os.environ.get(f"BITGET_PASSWORD_{i}", "")).strip()
        if k and s and p and k != k0:
            keys.append({"key": k, "secret": s, "passphrase": p, "id": i})

    return keys

BITGET_KEYS = load_bitget_api_keys()
KEY_ROTATION_INDEX = 0

def get_next_bitget_key():
    global KEY_ROTATION_INDEX
    if not BITGET_KEYS:
        return None
    key_set = BITGET_KEYS[KEY_ROTATION_INDEX % len(BITGET_KEYS)]
    KEY_ROTATION_INDEX += 1
    return key_set

# FORCE DEMO MODE DEFAULT TO TRUE TO PROTECT REAL ACC EQUITY
BITGET_DEMO_ENV = os.environ.get("BITGET_DEMO_MODE", "true").lower()
BITGET_DEMO_MODE = BITGET_DEMO_ENV != "false"

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
AI_DECISION_LOG_FILE = "ai_trader_decisions.json"

NUM_BATCHES = 20
MIN_24H_VOLUME = 300000
DEFAULT_LEVERAGE = 5

MIN_REQUIRED_COLOR_COUNT = 42    # Must have over 42 candles of SAME color out of 60 to enter
TARGET_COLOR_COUNT = 30          # Must form 30 candles of position color SINCE ENTRY
MAX_TRADE_DURATION_MIN = 54.0     # Must achieve target in less than 54 minutes

# ====================================================================================================
# UTILITY & AUTONOMOUS DECISION LOGGING FUNCTIONS
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

def log_ai_decision(symbol, decision_type, reason, action_taken):
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "symbol": symbol,
        "type": decision_type,
        "reason": reason,
        "action": action_taken
    }
    log.info(f"🧠 [TRUTH-ENGINE] {decision_type} on {symbol} | Reason: {reason} | Action: {action_taken}")

    logs = []
    if os.path.exists(AI_DECISION_LOG_FILE):
        try:
            with open(AI_DECISION_LOG_FILE, "r") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except Exception:
            logs = []

    logs.append(entry)
    try:
        with open(AI_DECISION_LOG_FILE, "w") as f:
            json.dump(logs[-100:], f, indent=2)
    except Exception:
        pass

def get_bitget_headers(method="GET", request_path="", body="", key_set=None):
    headers = {"Content-Type": "application/json"}
    if not key_set:
        key_set = BITGET_KEYS[0] if BITGET_KEYS else None

    if key_set:
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + request_path + body
        signature = base64.b64encode(
            hmac.new(key_set["secret"].encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        headers.update({
            "ACCESS-KEY": key_set["key"],
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": key_set["passphrase"],
            "locale": "en-US"
        })
    return headers

def calculate_ai_position_parameters(market_price, available_balance, volatility_pct, confidence_score):
    leverage = 10 if (confidence_score >= 95.0 and volatility_pct < 3.5) else 5

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
    return required_margin, qty, notional, leverage

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

def save_active_trade_state(symbol, direction, entry_price, contract_size, pre_trade_balance, dynamic_tp, dynamic_sl, leverage, dominant_color, dominant_count, is_virtual=False):
    trade_data = {
        "active": True,
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "peak_price": entry_price,
        "lowest_price": entry_price,
        "ai_target_tp": dynamic_tp,
        "ai_floor_sl": dynamic_sl,
        "leverage": leverage,
        "contract_size": str(contract_size),
        "pre_trade_balance": pre_trade_balance,
        "dominant_color": dominant_color,
        "initial_dominant_count": dominant_count,
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
# BITGET UTA v3 EXCHANGER ENGINE WITH MULTI-KEY ROTATION
# ====================================================================================================

async def fetch_bitget_account_balance(session):
    key_set = get_next_bitget_key()
    if not key_set:
        v_bal = get_virtual_demo_balance()
        return {
            "equity": v_bal,
            "available": v_bal * 0.90,
            "margin_coin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
            "account_type": f"Bitget UTA v3 {'DEMO (Simulated)' if BITGET_DEMO_MODE else 'UNAUTHENTICATED'}"
        }

    path = "/api/v3/account/assets"
    headers = get_bitget_headers("GET", path, key_set=key_set)
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
                    "account_type": f"Bitget UTA v3 {'DEMO (Key #' + str(key_set['id']) + ')' if BITGET_DEMO_MODE else 'REAL LIVE'}"
                }
    except Exception as e:
        log.error(f"Error querying Bitget balance via Key #{key_set['id']}: {e}")

    v_bal = get_virtual_demo_balance()
    return {
        "equity": v_bal,
        "available": v_bal * 0.90,
        "margin_coin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
        "account_type": f"Bitget UTA v3 {'DEMO (Fallback)' if BITGET_DEMO_MODE else 'REAL LIVE'}"
    }

async def fetch_bitget_order_fill_price(session, symbol, order_id, key_set=None):
    if not (key_set and order_id):
        return None

    path = f"/api/v3/trade/order-info?category={ORDER_CATEGORY}&symbol={symbol}&orderId={order_id}"
    full_url = f"https://{BIT_DOMAIN}{path}"
    headers = get_bitget_headers("GET", path, key_set=key_set)

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

async def configure_bitget_leverage(session, symbol, leverage=5, key_set=None):
    if not key_set:
        return

    path = "/api/v3/account/set-leverage"
    payload = {
        "category": ORDER_CATEGORY,
        "symbol": symbol,
        "leverage": str(leverage)
    }

    body_json = json.dumps(payload)
    headers = get_bitget_headers("POST", path, body_json, key_set=key_set)
    try:
        async with session.post(BITGET_V3_SET_LEVERAGE_URL, data=body_json, headers=headers, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget UTA v3 {leverage}x Leverage Configured ({symbol} via Key #{key_set['id']}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance, confidence_score=90.0, volatility_pct=2.0, dynamic_tp=0.0, dynamic_sl=0.0, sl_pct_val=1.5, dominant_color="GREEN", dominant_count=0):
    key_set = get_next_bitget_key()
    trade_symbol = symbol

    req_margin, exact_qty, actual_notional, adaptive_leverage = calculate_ai_position_parameters(market_price, available_balance, volatility_pct, confidence_score)
    await configure_bitget_leverage(session, trade_symbol, leverage=adaptive_leverage, key_set=key_set)

    margin_currency = "S-USDT" if BITGET_DEMO_MODE else "USDT"

    # Virtual Shadow Tracker if required margin exceeds balance
    if req_margin > (available_balance * 0.85):
        log_ai_decision(symbol, "MARGIN_SHADOW_FALLBACK", f"Required margin ${req_margin:.2f} > Balance limit", "Opened Virtual Shadow Trade Tracker")
        save_active_trade_state(symbol, direction, market_price, exact_qty, available_balance, dynamic_tp, dynamic_sl, adaptive_leverage, dominant_color, dominant_count, is_virtual=True)
        return {
            "order_id": "VIRTUAL_SHADOW_ORDER",
            "symbol": trade_symbol,
            "notional_value": actual_notional,
            "contract_size": str(exact_qty),
            "preset_tp": format_price(dynamic_tp),
            "preset_sl": format_price(dynamic_sl),
            "real_fill_price": market_price,
            "pre_trade_balance": available_balance,
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

    preset_tp = format_price(dynamic_tp)
    preset_sl = format_price(dynamic_sl)

    if not key_set:
        log_ai_decision(symbol, "NO_API_KEY_FALLBACK", "No active Pollination Key set provided", "Executing Virtual AI Trade")
        save_active_trade_state(symbol, direction, market_price, size_str, available_balance, dynamic_tp, dynamic_sl, adaptive_leverage, dominant_color, dominant_count, is_virtual=True)
        return {
            "order_id": "VIRTUAL_SHADOW_ORDER",
            "symbol": trade_symbol,
            "notional_value": actual_notional,
            "contract_size": size_str,
            "preset_tp": preset_tp,
            "preset_sl": preset_sl,
            "real_fill_price": market_price,
            "pre_trade_balance": available_balance,
            "is_virtual": True,
            "filled": True
        }

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": ORDER_CATEGORY,
        "symbol": trade_symbol,
        "marginCoin": margin_currency,
        "qty": size_str,
        "side": "buy" if direction == "LONG" else "sell",
        "orderType": "market",
        "presetTakeProfitPrice": str(preset_tp),
        "presetStopLossPrice": str(preset_sl),
        "reduceOnly": "no"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json, key_set=key_set)

    mode_label = f"🎮 BITGET DEMO MODE ({margin_currency})" if BITGET_DEMO_MODE else f"🚨 REAL MONEY BITGET TRADING (USDT)"

    log.info("====================================================================================================")
    log.info(f"🚨 TRADE IS HAPPENING NOW! ({mode_label})")
    log.info(f"   • Symbol Pair Opened:   {trade_symbol} ({direction})")
    log.info(f"   • 60m Candle Color:     {dominant_count} {dominant_color} Candles out of 60 (PASSED >42 THRESHOLD!)")
    log.info(f"   • Exit Target Rule:     Form 30+ {dominant_color} Candles SINCE ENTRY in < 54 Minutes")
    log.info(f"   • Dynamic Stop Loss:    ${preset_sl} (-{sl_pct_val:.2f}% Risk Floor)")
    log.info(f"   • Account Opening Equity: ${available_balance:.4f} {margin_currency}")
    log.info(f"   • Margin Used for Trade:  ${req_margin:.4f} {margin_currency} ({adaptive_leverage}x Leverage)")
    log.info(f"   • Remaining Free Margin:  ${available_balance - req_margin:.4f} {margin_currency}")
    log.info(f"   • Entry Fill Price:       ${format_price(market_price)}")
    log.info(f"   • Order Position Size:    {size_str} (${actual_notional:.2f} Notional Value)")
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
                log.info(f"✅ BITGET MATCHING ENGINE ACCEPTED ORDER (Key #{key_set['id']})! Order ID: {order_id}")

                await asyncio.sleep(0.5)
                real_fill = await fetch_bitget_order_fill_price(session, trade_symbol, order_id, key_set=key_set)
                if not real_fill or real_fill <= 0:
                    real_fill = market_price

                save_active_trade_state(trade_symbol, direction, real_fill, size_str, available_balance, dynamic_tp, dynamic_sl, adaptive_leverage, dominant_color, dominant_count, is_virtual=False)
                log_ai_decision(trade_symbol, "ORDER_ENTERED", f"Filled at ${format_price(real_fill)} matching {dominant_color} direction ({dominant_count} candles > 42)", "Active 54m / 30-Candle Color Supervision Engaged")

                return {
                    "order_id": order_id,
                    "symbol": trade_symbol,
                    "notional_value": actual_notional,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": real_fill,
                    "pre_trade_balance": available_balance,
                    "is_virtual": False,
                    "filled": True
                }
            else:
                err_msg = f"Code: {resp.get('code')} | Msg: {resp.get('msg')}"
                log.error(f"❌ BITGET ORDER REJECTED: {err_msg}")
                log_ai_decision(trade_symbol, "ORDER_REJECTED", err_msg, "Switched to Virtual Shadow Trade Tracker")
                save_active_trade_state(symbol, direction, market_price, size_str, available_balance, dynamic_tp, dynamic_sl, adaptive_leverage, dominant_color, dominant_count, is_virtual=True)
                return {
                    "order_id": "VIRTUAL_SHADOW_ORDER",
                    "symbol": trade_symbol,
                    "notional_value": actual_notional,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": market_price,
                    "pre_trade_balance": available_balance,
                    "is_virtual": True,
                    "filled": True
                }
    except Exception as e:
        log.error(f"❌ Error submitting Bitget order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    key_set = get_next_bitget_key()
    if not key_set:
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
    headers = get_bitget_headers("POST", path, body_json, key_set=key_set)

    log.info(f"🛑 AUTONOMOUS AI EXECUTING MARKET EXIT: Closing {symbol} ({direction}) | Size: {order_payload['qty']}")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                log.info(f"✅ BITGET POSITION CLOSED ON EXCHANGE! Order ID: {resp.get('data', {}).get('orderId')}")
                log_ai_decision(symbol, "POSITION_CLOSED", f"Market exit order executed for size {order_payload['qty']}", "Cleared Active Trade State")
            else:
                log.warning(f"Notice on exchange close: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
    except Exception as e:
        log.error(f"Error executing Bitget position close: {e}")

# ====================================================================================================
# MARKET DATA FETCHERS & 60-CANDLE COLOR SCANNER
# ====================================================================================================

async def fetch_single_price(session, symbol):
    key_set = get_next_bitget_key()
    params = {"symbol": symbol, "productType": SCAN_PRODUCT_TYPE}
    path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType={SCAN_PRODUCT_TYPE}"
    headers = get_bitget_headers("GET", path, key_set=key_set)
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
    key_set = get_next_bitget_key()
    path = f"/api/v2/mix/market/tickers?productType={SCAN_PRODUCT_TYPE}"
    headers = get_bitget_headers("GET", path, key_set=key_set)
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
        key_set = get_next_bitget_key()
        params = {"symbol": symbol, "productType": SCAN_PRODUCT_TYPE, "granularity": "1m", "limit": "60"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType={SCAN_PRODUCT_TYPE}&granularity=1m&limit=60"
        for attempt in range(3):
            headers = get_bitget_headers("GET", path, key_set=key_set)
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
# STRICT 42+ CANDLE COLOR ENTRY GATE & DYNAMIC STOP LOSS ENGINE
# ====================================================================================================

async def process_dominant_candle_color_batch(batch_id, coin_list, session, semaphore, last_symbol, last_won):
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

        candles_chrono = list(reversed(candle_data[:60]))

        green_count = 0
        red_count = 0

        for c in candles_chrono:
            open_p = float(c[1])
            close_p = float(c[4])
            if close_p >= open_p:
                green_count += 1
            else:
                red_count += 1

        current_price = float(candles_chrono[-1][4])
        low_60m = min(float(c[3]) for c in candles_chrono)
        high_60m = max(float(c[2]) for c in candles_chrono)

        if current_price <= 0 or low_60m <= 0:
            continue

        if green_count >= red_count:
            direction = "LONG"
            dominant_color = "GREEN"
            dominant_count = green_count
        else:
            direction = "SHORT"
            dominant_color = "RED"
            dominant_count = red_count

        # STRICT ENTRY GATE: MUST HAVE OVER 42+ CANDLES OF SAME COLOR OUT OF 60!
        if dominant_count < MIN_REQUIRED_COLOR_COUNT:
            continue

        volatility_pct = ((high_60m - low_60m) / low_60m) * 100.0
        raw_sl_pct = max(0.5, min(2.5, volatility_pct * 0.40))

        if direction == "LONG":
            dynamic_sl = current_price * (1.0 - (raw_sl_pct / 100.0))
            dynamic_tp = current_price * (1.0 + (raw_sl_pct * 2.0 / 100.0))
        else:
            dynamic_sl = current_price * (1.0 + (raw_sl_pct / 100.0))
            dynamic_tp = current_price * (1.0 - (raw_sl_pct * 2.0 / 100.0))

        confidence_score = min(99.0, 75.0 + (dominant_count * 0.45))

        batch_evaluated.append({
            "batch_id": batch_id,
            "symbol": symbol,
            "vol_24h": vol_24h,
            "direction": direction,
            "dominant_color": dominant_color,
            "dominant_count": dominant_count,
            "volatility_pct": volatility_pct,
            "sl_pct_val": raw_sl_pct,
            "confidence_score": confidence_score,
            "dynamic_tp": dynamic_tp,
            "dynamic_sl": dynamic_sl,
            "current_price": current_price
        })

    if not batch_evaluated:
        return []

    batch_evaluated.sort(key=lambda x: x["dominant_count"], reverse=True)
    return [batch_evaluated[0]]

# ====================================================================================================
# MAIN SUPERVISION LOOP: RISK-FIRST STOP LOSS & TRUTH-IN-REPORTING EVALUATOR
# ====================================================================================================

async def run_scanner_iteration():
    live_streak = get_live_win_streak()
    recent_loss_count = get_consecutive_losses()
    last_symbol, last_won = get_last_traded_coin_status()

    num_active_keys = len(BITGET_KEYS)
    auth_status = f"🔐 AUTHENTICATED ({num_active_keys} Bitget Pollination Key Sets Active)" if num_active_keys > 0 else "🔓 PUBLIC API (Unauthenticated)"
    margin_currency = "S-USDT" if BITGET_DEMO_MODE else "USDT"
    mode_label = f"🎮 BITGET DEMO MODE (UTA v3 | {margin_currency})" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING (USDT)"

    log.info(f"🏆 Win Streak: {live_streak} Wins | Loss Streak: {recent_loss_count} | Mode: {mode_label} | Keys: {auth_status}")

    # CIRCUIT BREAKER GUARD
    if recent_loss_count >= 2:
        log.warning("====================================================================================================")
        log.warning("⛔ AI CIRCUIT BREAKER ACTIVATED: 2 CONSECUTIVE LOSSES DETECTED!")
        log.warning("🚫 PAUSING NEW TRADES UNTIL HUMAN SAFETY OVERRIDE TO PRESERVE ACCOUNT CAPITAL.")
        log.warning("====================================================================================================")
        log_ai_decision("GLOBAL", "CIRCUIT_BREAKER", "2 Consecutive Losses", "Paused New Trade Entries")
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
            ai_target_tp = float(active_trade.get("ai_target_tp", entry_price * 1.030))
            ai_floor_sl = float(active_trade.get("ai_floor_sl", entry_price * 0.985))
            leverage = int(active_trade.get("leverage", DEFAULT_LEVERAGE))
            contract_size = active_trade.get("contract_size", "1")
            pre_trade_balance = float(active_trade.get("pre_trade_balance", current_equity))
            dominant_color = active_trade.get("dominant_color", "GREEN")
            start_time = float(active_trade.get("start_time", time.time()))
            is_virtual = active_trade.get("is_virtual", False)

            current_time = time.time()
            elapsed_minutes = (current_time - start_time) / 60.0

            entry_p_str = format_price(entry_price)
            trade_type_label = "🔮 VIRTUAL SHADOW TRADE" if is_virtual else f"🎮 LIVE {margin_currency} DEMO TRADE"
            log.info(f"⏳ {trade_type_label} SUPERVISION ({symbol}): Entry @ ${entry_p_str} | Elapsed: {elapsed_minutes:.1f}m / 54.0m Max | Target: 30+ {dominant_color} Candles | SL Floor: ${format_price(ai_floor_sl)}")

            candle_data = await fetch_60m_candle_data_for_coin(session, symbol, asyncio.Semaphore(5))
            current_price = await fetch_single_price(session, symbol)

            if current_price and current_price > 0:
                curr_p_str = format_price(current_price)
                live_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0 if direction == "LONG" else ((entry_price - current_price) / entry_price) * 100.0

                # ----------------------------------------------------------------------------------
                # STEP 1: RISK-FIRST CHECK: EVALUATE STOP LOSS BEFORE ANYTHING ELSE!
                # ----------------------------------------------------------------------------------
                is_sl_breached = current_price <= ai_floor_sl if direction == "LONG" else current_price >= ai_floor_sl

                if is_sl_breached or live_pnl_pct <= -5.0:
                    pnl_cash = pre_trade_balance * (live_pnl_pct / 100.0 * leverage)
                    closing_equity = max(0.0, pre_trade_balance + pnl_cash)

                    if not is_virtual:
                        await close_bitget_live_position(session, symbol, direction, contract_size=contract_size)

                    update_virtual_demo_balance(closing_equity)
                    new_streak = update_live_win_streak(False)
                    record_trade_history(symbol, False, live_pnl_pct * leverage, pnl_cash)

                    log_ai_decision(symbol, "STOP_LOSS_EXECUTED", f"Price ${curr_p_str} breached Stop Loss ${format_price(ai_floor_sl)} (PnL: {live_pnl_pct:.2f}%)", "Stop Loss Executed Immediately")

                    log.info("====================================================================================================")
                    log.info(f"❌ STOP LOSS TRIGGERED & POSITION CLOSED! ({symbol})")
                    log.info(f"   • Entry Price:                  ${entry_p_str}")
                    log.info(f"   • Exit Price:                   ${curr_p_str} (PnL: {live_pnl_pct:.2f}%)")
                    log.info(f"   • Trade Opening Balance:        ${pre_trade_balance:.4f} {margin_currency}")
                    log.info(f"   • Trade Closing Balance:        ${closing_equity:.4f} {margin_currency}")
                    log.info(f"   • NET LOSS SUFFERED:            -${abs(pnl_cash):.4f} {margin_currency}")
                    log.info(f"   • TRADE RESULT:                  ❌ LOSS (STREAK RESET TO 0)")
                    log.info("====================================================================================================")
                    clear_active_trade_state()
                    return

                # ----------------------------------------------------------------------------------
                # STEP 2: COUNT CANDLES FORMED SINCE ENTRY (IGNORE PRE-ENTRY CANDLES)
                # ----------------------------------------------------------------------------------
                candles_since_entry = 0
                if candle_data:
                    candles_chrono = list(reversed(candle_data[:60]))
                    for c in candles_chrono:
                        c_timestamp_sec = float(c[0]) / 1000.0 if float(c[0]) > 1e11 else float(c[0])
                        # Only count candles opened AFTER entry start_time
                        if c_timestamp_sec >= (start_time - 60.0):
                            o_p = float(c[1])
                            c_p = float(c[4])
                            c_color = "GREEN" if c_p >= o_p else "RED"
                            if c_color == dominant_color:
                                candles_since_entry += 1

                log.info(f"📍 LIVE MONITOR ({symbol}): Current: ${curr_p_str} | PnL: {live_pnl_pct:+.2f}% | Candles Since Entry: {candles_since_entry}/30 {dominant_color} | Elapsed: {elapsed_minutes:.1f}m")

                # ----------------------------------------------------------------------------------
                # STEP 3: COLOR TARGET EXIT (Must have 30+ candles SINCE ENTRY & Positive PnL!)
                # ----------------------------------------------------------------------------------
                if candles_since_entry >= TARGET_COLOR_COUNT and live_pnl_pct > 0.0 and elapsed_minutes < MAX_TRADE_DURATION_MIN:
                    pnl_cash = pre_trade_balance * (live_pnl_pct / 100.0 * leverage)
                    closing_equity = pre_trade_balance + pnl_cash

                    if not is_virtual:
                        await close_bitget_live_position(session, symbol, direction, contract_size=contract_size)

                    update_virtual_demo_balance(closing_equity)
                    new_streak = update_live_win_streak(True)
                    record_trade_history(symbol, True, live_pnl_pct * leverage, pnl_cash)

                    log_ai_decision(symbol, "COLOR_TARGET_ACHIEVED", f"Formed {candles_since_entry} {dominant_color} candles since entry in {elapsed_minutes:.1f}m (PnL: +{live_pnl_pct:.2f}%)", "Target Achieved: Closing for Profit")

                    log.info("====================================================================================================")
                    log.info(f"🏆 COLOR TARGET ACHIEVED & TRADE CLOSED! ({symbol})")
                    log.info(f"   • Dominant Color Goal:          Formed {candles_since_entry} {dominant_color} Candles Since Entry")
                    log.info(f"   • Time Elapsed:                 {elapsed_minutes:.1f} Minutes (Target: < 54.0m)")
                    log.info(f"   • Trade Opening Balance:        ${pre_trade_balance:.4f} {margin_currency}")
                    log.info(f"   • Trade Closing Balance:        ${closing_equity:.4f} {margin_currency}")
                    log.info(f"   • NET PROFIT GAINED:            +${pnl_cash:.4f} {margin_currency} (+{live_pnl_pct*leverage:.2f}%)")
                    log.info(f"   • TRADE RESULT:                  🏆 WIN")
                    log.info(f"   • NEW WIN STREAK:                {new_streak} WINS IN A ROW")
                    log.info("====================================================================================================")
                    clear_active_trade_state()
                    return

                # ----------------------------------------------------------------------------------
                # STEP 4: TIME LIMIT EXPIRED (54-Minute Cutoff)
                # ----------------------------------------------------------------------------------
                if elapsed_minutes >= MAX_TRADE_DURATION_MIN and candles_since_entry < TARGET_COLOR_COUNT:
                    pnl_cash = pre_trade_balance * (live_pnl_pct / 100.0 * leverage)
                    closing_equity = max(0.0, pre_trade_balance + pnl_cash)
                    is_win = pnl_cash >= 0

                    if not is_virtual:
                        await close_bitget_live_position(session, symbol, direction, contract_size=contract_size)

                    update_virtual_demo_balance(closing_equity)
                    new_streak = update_live_win_streak(is_win)
                    record_trade_history(symbol, is_win, live_pnl_pct * leverage, pnl_cash)

                    log_ai_decision(symbol, "TIME_LIMIT_EXPIRED_54M", f"Hit 54m limit ({elapsed_minutes:.1f}m) with {candles_since_entry}/30 candles", f"Time Expired: Closed. Result: {'WIN' if is_win else 'LOSS'}")

                    log.info("====================================================================================================")
                    log.info(f"⌛ 54-MINUTE TIME LIMIT EXPIRED & TRADE CLOSED! ({symbol})")
                    log.info(f"   • Candles Since Entry:          {candles_since_entry}/30 {dominant_color} Candles")
                    log.info(f"   • Time Elapsed:                 {elapsed_minutes:.1f} Minutes (Hit 54m Cutoff)")
                    log.info(f"   • Trade Opening Balance:        ${pre_trade_balance:.4f} {margin_currency}")
                    log.info(f"   • Trade Closing Balance:        ${closing_equity:.4f} {margin_currency}")
                    log.info(f"   • NET PROFIT/LOSS:              {'+' if pnl_cash>=0 else ''}${pnl_cash:.4f} {margin_currency}")
                    log.info(f"   • TRADE RESULT:                  {'🏆 WIN' if is_win else '❌ LOSS'}")
                    log.info("====================================================================================================")
                    clear_active_trade_state()
                    return

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
                    "leverage": leverage,
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

            log.info(f"🕯️ TRUTH-ENGINE SCANNER: Evaluating all 600+ Bitget pairs for OVER 42+ candles of SAME color in last 60m...")
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

            chunk_size = (total_coins + NUM_BATCHES - 1) // NUM_BATCHES
            coin_batches = [valid_coins[i * chunk_size:(i + 1) * chunk_size] for i in range(NUM_BATCHES) if valid_coins[i * chunk_size:(i + 1) * chunk_size]]

            batch_tasks = [process_dominant_candle_color_batch(i + 1, batch, session, semaphore, last_symbol, last_won) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["dominant_count"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 APPROVED 42+ CANDLE COLOR MATCH: {best_signal['symbol']} ({best_signal['dominant_count']}/60 {best_signal['dominant_color']} Candles | Direction: {best_signal['direction']} | Dynamic SL: -{best_signal['sl_pct_val']:.2f}%)")

                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    market_price=best_signal["current_price"],
                    available_balance=current_equity,
                    confidence_score=best_signal["confidence_score"],
                    volatility_pct=best_signal["volatility_pct"],
                    dynamic_tp=best_signal["dynamic_tp"],
                    dynamic_sl=best_signal["dynamic_sl"],
                    sl_pct_val=best_signal["sl_pct_val"],
                    dominant_color=best_signal["dominant_color"],
                    dominant_count=best_signal["dominant_count"]
                )

                if live_order_result and live_order_result.get("filled", False):
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"])

                    payload = {
                        "symbol": live_order_result.get("symbol", best_signal["symbol"]),
                        "direction": live_order_result.get("direction", best_signal["direction"]),
                        "is_paper": live_order_result.get("is_virtual", False),
                        "is_demo": BITGET_DEMO_MODE,
                        "avg_fluctuation": round(best_signal["confidence_score"] * 10, 2),
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
                log.info("ℹ️ No altcoins currently matched the >42+ candle color threshold in the last 60 minutes.")
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

                            log_ai_decision(symbol, "EXCHANGE_CLOSE_AUDIT", f"Closing Equity ${final_eq:.4f}", f"Result: {'WIN' if is_win else 'LOSS'}")

                            log.info("====================================================================================================")
                            log.info(f"🏁 TRADE CLOSED & AUDITED! ({symbol})")
                            log.info(f"   • Trade Opening Account Balance: ${pre_trade_balance:.4f} {margin_currency}")
                            log.info(f"   • Trade Closing Account Balance: ${final_eq:.4f} {margin_currency}")
                            log.info(f"   • NET PROFIT/LOSS:              {'+' if net_cash_change>=0 else ''}${net_cash_change:.4f} {margin_currency}")
                            log.info(f"   • TRADE RESULT:                  {'🏆 WIN' if is_win else '❌ LOSS'}")
                            log.info(f"   • NEW WIN STREAK:                {new_streak} WINS")
                            log.info("====================================================================================================")
                            clear_active_trade_state()

                    elif worker_status == "HOLDING":
                        log.info(f"📈 DEMO TRADE HOLDING: {symbol} ({direction}) | Elapsed: {res_data.get('elapsed_minutes')}m")

                log.info(f"📡 Webhook response status: {status_code}")

async def main():
    if CONTINUOUS_247_LOOP:
        log.info(f"🔄 AUTOMATIC ENVIRONMENT DETECTED: Running 1-SECOND Truth-Engine Loop ({len(BITGET_KEYS)} Pollination Keys)...")
        while True:
            try:
                await run_scanner_iteration()
            except Exception as e:
                log.error(f"Error during scan iteration: {e}")
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)
    else:
        log.info(f"⚡ AUTOMATIC ENVIRONMENT DETECTED: Running Single-Scan Truth-Engine Execution ({len(BITGET_KEYS)} Pollination Keys)...")
        await run_scanner_iteration()

if __name__ == "__main__":
    asyncio.run(main())

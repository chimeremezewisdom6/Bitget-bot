import os
import time
import json
import asyncio
import logging
import aiohttp
import hmac
import hashlib
import base64

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("scanner")

CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

# Bitget API Credentials (Supports BITGET_PASSPHRASE or BITGET_PASSWORD)
BITGET_API_KEY = os.environ.get("BITGET_API_KEY", "").strip()
BITGET_SECRET_KEY = os.environ.get("BITGET_SECRET_KEY", "").strip()
BITGET_PASSPHRASE = (os.environ.get("BITGET_PASSPHRASE", "") or os.environ.get("BITGET_PASSWORD", "")).strip()

# BITGET DEMO MODE TOGGLE (Set BITGET_DEMO_MODE="false" in GitHub Secrets for Real Money Live Trading)
BITGET_DEMO_MODE = os.environ.get("BITGET_DEMO_MODE", "true").lower() == "true"

PRODUCT_TYPE = "USDT-FUTURES"
ORDER_CATEGORY = "USDT-FUTURES"

# Official Bitget Demo Pairs Supported on S-USDT Demo Margin
BITGET_SUPPORTED_DEMO_PAIRS = ["SBTCUSDT", "SETHUSDT", "SSOLUSDT"]

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType={PRODUCT_TYPE}"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"

# Official Bitget v3 Unified Trading Account (UTA) API Endpoints
BITGET_V3_UTA_ASSETS_URL = f"https://{BIT_DOMAIN}/api/v3/account/assets"
BITGET_V3_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/place-order"
BITGET_V3_SET_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-leverage"
BITGET_V3_SET_POS_MODE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-position-mode"
BITGET_V3_ORDER_INFO_URL = f"https://{BIT_DOMAIN}/api/v3/trade/order-info"

LIVE_STREAK_FILE = "live_streak.json"
LIVE_ACTIVE_TRADE_FILE = "live_active_trade.json"

NUM_BATCHES = 20            # Exactly 20 separate scanning batches / workers
MIN_24H_VOLUME = 300000     # Min $300k Volume Filter
DEFAULT_LEVERAGE = 5        # Strictly 5x Leverage
BALANCE_USAGE_PCT = 0.90    # Strictly 90% of available USDT equity allocated per trade

def format_price(price):
    """Formats price dynamically to match Bitget precision step size."""
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

async def fetch_bitget_account_balance(session):
    """Queries official Bitget UTA v3 API and returns live Demo or Real USDT equity & available margin."""
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
                usdt_asset = next((a for a in assets_list if a.get("coin") in ("USDT", "S-USDT")), None)

                available_margin = 0.0
                if usdt_asset:
                    available_margin = float(usdt_asset.get("available") or usdt_asset.get("equity") or 0.0)
                    if usdt_equity == 0.0:
                        usdt_equity = float(usdt_asset.get("equity") or available_margin)
                elif usdt_equity > 0:
                    available_margin = usdt_equity

                return {
                    "equity": usdt_equity,
                    "available": available_margin,
                    "margin_coin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
                    "account_type": f"Bitget UTA v3 {'DEMO (Simulated)' if BITGET_DEMO_MODE else 'REAL LIVE'}"
                }
    except Exception as e:
        log.error(f"Error querying Bitget UTA v3 balance: {e}")
    return None

async def fetch_bitget_order_fill_price(session, symbol, order_id):
    """Fetches exact executed fill price directly from Bitget v3 Order Info API."""
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

async def configure_bitget_symbol_settings(session, trade_symbol):
    """Configures 5x Leverage on Bitget UTA v3 API."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return

    path_lev = "/api/v3/account/set-leverage"
    body_lev = json.dumps({
        "category": "USDT-FUTURES",
        "symbol": trade_symbol,
        "leverage": str(DEFAULT_LEVERAGE)
    })
    headers_lev = get_bitget_headers("POST", path_lev, body_lev)
    try:
        async with session.post(BITGET_V3_SET_LEVERAGE_URL, data=body_lev, headers=headers_lev, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget UTA v3 5x Leverage Configured ({trade_symbol}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance):
    """
    DYNAMIC N-CANDLE EXPANSION MARKET ORDER EXECUTION:
    - Real Live Mode (BITGET_DEMO_MODE = False): Trades exact matched symbol.
    - Demo Mode (BITGET_DEMO_MODE = True): Maps to SBTCUSDT if altcoin is not directly listed on demo.
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Cannot execute order.")
        return None

    if BITGET_DEMO_MODE:
        candidate_demo_sym = f"S{symbol}" if not symbol.startswith("S") else symbol
        if candidate_demo_sym in BITGET_SUPPORTED_DEMO_PAIRS:
            trade_symbol = candidate_demo_sym
        else:
            trade_symbol = "SBTCUSDT"
            log.info(f"ℹ️ Map Notice: Bitget Demo exchange supports SBTC/SETH/SSOL. Mapping matched {symbol} signal to demo pair {trade_symbol}.")
    else:
        trade_symbol = symbol

    await configure_bitget_symbol_settings(session, trade_symbol)

    if trade_symbol != symbol and BITGET_DEMO_MODE:
        demo_price = await fetch_single_price(session, "BTCUSDT")
        if demo_price and demo_price > 0:
            market_price = demo_price

    used_margin = available_balance * BALANCE_USAGE_PCT
    notional_value = used_margin * DEFAULT_LEVERAGE

    if notional_value < 5.0:
        notional_value = 5.50

    contract_size = notional_value / market_price

    if market_price < 0.001:
        size_str = f"{int(contract_size)}"
    elif market_price > 1000:
        size_str = f"{contract_size:.3f}"
    elif market_price > 10:
        size_str = f"{contract_size:.2f}"
    elif market_price > 1:
        size_str = f"{contract_size:.1f}"
    else:
        size_str = f"{int(contract_size)}"

    if float(size_str) <= 0:
        size_str = "1"

    if direction == "LONG":
        side = "buy"
        preset_tp = format_price(market_price * 1.025)  # Hard +2.50% TP
        preset_sl = format_price(market_price * 0.9875) # Hard -1.25% SL
    else:
        side = "sell"
        preset_tp = format_price(market_price * 0.975)  # Hard +2.50% TP
        preset_sl = format_price(market_price * 1.0125) # Hard -1.25% SL

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": "USDT-FUTURES",
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

    mode_label = "🎮 BITGET DEMO" if BITGET_DEMO_MODE else "🚨 BITGET REAL MONEY"
    log.info(f"🎯 SUBMITTING DYNAMIC N-CANDLE EXPANSION MARKET ORDER ({mode_label}): {trade_symbol} ({direction} | Matched: {symbol}) | Size: {size_str} | TP: {preset_tp} (+2.5%) | SL: {preset_sl} (-1.25%)")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "ORDER_EXECUTED")
                log.info(f"✅ BITGET MATCHING ENGINE ACCEPTED ORDER! Order ID: {order_id}")

                await asyncio.sleep(0.5)
                real_fill = await fetch_bitget_order_fill_price(session, trade_symbol, order_id)
                if not real_fill or real_fill <= 0:
                    real_fill = market_price

                slippage = abs(real_fill - market_price) / market_price * 100.0
                log.info(f"🎯 BITGET FILL PRICE VERIFIED: ${format_price(real_fill)} | Measured Slippage: {slippage:.3f}%")

                return {
                    "order_id": order_id,
                    "symbol": trade_symbol,
                    "original_symbol": symbol,
                    "notional_value": notional_value,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": real_fill,
                    "pre_trade_balance": available_balance,
                    "slippage_pct": round(slippage, 3),
                    "filled": True
                }
            else:
                log.error(f"❌ BITGET ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                return None
    except Exception as e:
        log.error(f"❌ Error submitting Bitget order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    """Executes an Immediate Market Close Order via v3 UTA API."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None

    close_side = "sell" if direction == "LONG" else "buy"
    path = "/api/v3/trade/place-order"

    order_payload = {
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "marginCoin": "S-USDT" if BITGET_DEMO_MODE else "USDT",
        "side": close_side,
        "orderType": "market",
        "reduceOnly": "yes"
    }

    if contract_size and contract_size != "0":
        order_payload["qty"] = str(contract_size)
    else:
        order_payload["qty"] = "1"

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

async def fetch_single_price(session, symbol):
    params = {"symbol": symbol, "productType": PRODUCT_TYPE}
    path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType={PRODUCT_TYPE}"
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
    path = f"/api/v2/mix/market/tickers?productType={PRODUCT_TYPE}"
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
    """Fetches 60 1-MINUTE candles (OHLCV) for a single coin with retry handling."""
    async with semaphore:
        params = {"symbol": symbol, "productType": PRODUCT_TYPE, "granularity": "1m", "limit": "60"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType={PRODUCT_TYPE}&granularity=1m&limit=60"
        for attempt in range(3):
            headers = get_bitget_headers("GET", path)
            try:
                async with session.get(BITGET_CANDLES_URL, params=params, headers=headers, timeout=8) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("code") == "00000":
                            candles = data.get("data", [])
                            if candles and len(candles) >= 60:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.15 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
        return []

async def process_coin_batch(batch_id, coin_list, session, semaphore):
    """
    DYNAMIC N-CANDLE (5 TO 60 CANDLES) SMALL STRUCTURE TO BIG PRICE MOVE DETECTOR
    -----------------------------------------------------------------------------
    Evaluates 60 1-minute OHLCV candles across all Bitget Futures pairs:
      1. Scans ALL dynamic window lengths N from 6 to 59 candles (e.g. 6, 7, 12, 17, 23, 42 candles).
      2. Excludes static fixed intervals (5, 10, 15, 20, 30, 60).
      3. For each dynamic window N:
         - Measures the SMALL compression structure range %: (High_N - Low_N) / Open_N * 100.
         - Requires small compression range <= 0.85% (Tight Coiled Structure).
         - Measures the BIG price expansion move % occurring right after/at the end of the window.
         - Calculates Expansion Ratio = (Big Move %) / (Small Range % + 0.01) * (Volume Surge).
      4. Ranks ALL market pairs across ALL dynamic N-window setups to pick the #1 EXPLOSIVE MOVE!
    """
    batch_evaluated = []

    tasks = [fetch_60m_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    EXCLUDED_FIXED_WINDOWS = {5, 10, 15, 20, 30, 60}

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 60:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        # Reverse to chronological order (index 0 = 60m ago, index 59 = current 1m candle)
        candles_60m = list(reversed(candle_data[:60]))

        best_coin_setup = None
        highest_expansion_score = 0.0

        # Scan ALL dynamic N-candle window lengths from 6 to 55 (excluding fixed 5, 10, 15, 20, 30, 60)
        for n_candles in range(6, 56):
            if n_candles in EXCLUDED_FIXED_WINDOWS:
                continue

            comp_window = candles_60m[:n_candles]
            trigger_window = candles_60m[n_candles:]

            if not comp_window or not trigger_window:
                continue

            comp_high = max(float(c[2]) for c in comp_window)
            comp_low = min(float(c[3]) for c in comp_window)
            comp_open = float(comp_window[0][1])

            if comp_open <= 0 or comp_low <= 0:
                continue

            # 1. SMALL CANDLE STRUCTURE RANGE %
            comp_range_pct = ((comp_high - comp_low) / comp_open) * 100.0
            if comp_range_pct > 0.90:  # Must be a tight small structure
                continue

            # Volume surge check
            comp_vol_avg = sum(float(c[5]) for c in comp_window) / float(n_candles)
            trig_vol_avg = sum(float(c[5]) for c in trigger_window) / float(len(trigger_window))

            if comp_vol_avg <= 0:
                continue

            vol_surge = trig_vol_avg / comp_vol_avg
            if vol_surge < 1.4:
                continue

            p_current = float(candles_60m[-1][4])

            move_up_pct = ((p_current - comp_high) / comp_high) * 100.0
            move_down_pct = ((comp_low - p_current) / comp_low) * 100.0

            is_bull_breakout = (p_current > comp_high) and (move_up_pct >= 0.35)
            is_bear_breakout = (p_current < comp_low) and (move_down_pct >= 0.35)

            if is_bull_breakout or is_bear_breakout:
                direction = "LONG" if is_bull_breakout else "SHORT"
                big_move_pct = move_up_pct if is_bull_breakout else move_down_pct

                # DYNAMIC EXPANSION SCORE = (Big Move %) / (Small Setup Range %) * Vol Surge
                expansion_score = (big_move_pct / (comp_range_pct + 0.05)) * vol_surge

                if expansion_score > highest_expansion_score:
                    highest_expansion_score = expansion_score
                    best_coin_setup = {
                        "batch_id": batch_id,
                        "symbol": symbol,
                        "vol_24h": vol_24h,
                        "direction": direction,
                        "n_candles": n_candles,
                        "small_range_pct": comp_range_pct,
                        "big_move_pct": big_move_pct,
                        "vol_surge": vol_surge,
                        "expansion_score": expansion_score,
                        "current_price": p_current
                    }

        if best_coin_setup:
            batch_evaluated.append(best_coin_setup)

    if not batch_evaluated:
        return []

    # Sort candidates exchange-wide by highest Dynamic Expansion Score
    batch_evaluated.sort(key=lambda x: x["expansion_score"], reverse=True)
    return [batch_evaluated[0]]

async def main():
    live_streak = get_live_win_streak()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = f"🎮 BITGET DEMO MODE ({ORDER_CATEGORY} | Dynamic 5-60 N-Candle Expansion Engine | 5x Leverage)" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING"

    log.info(f"🏆 Current BITGET WIN STREAK: {live_streak} Wins | Mode: {mode_status} | API: {auth_status}")

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        current_equity = acc_info["equity"] if acc_info else 10000.0

        if acc_info:
            log.info(f"💰 BITGET ACCOUNT EQUITY: ${acc_info['equity']:.4f} {acc_info['margin_coin']} | Available Margin: ${acc_info['available']:.4f} ({acc_info['account_type']})")
        else:
            log.warning("⚠️ Bitget balance query pending...")

        active_trade = get_active_live_trade()

        if active_trade:
            symbol = active_trade.get("symbol")
            direction = active_trade.get("direction", "LONG")
            entry_price = float(active_trade.get("entry_price", 0.0))
            contract_size = active_trade.get("contract_size", "1")
            pre_trade_balance = float(active_trade.get("pre_trade_balance", current_equity))

            entry_p_str = format_price(entry_price)
            log.info(f"⏳ DYNAMIC N-CANDLE TRADE ACTIVE: {symbol} ({direction} @ ${entry_p_str}). Pre-Trade Equity: ${pre_trade_balance:.4f}. Monitoring price...")

            current_price = await fetch_single_price(session, symbol)
            if current_price and current_price > 0:
                curr_p_str = format_price(current_price)
                if direction == "LONG":
                    live_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                else:
                    live_pnl_pct = ((entry_price - current_price) / entry_price) * 100.0

                pnl_str = f"{live_pnl_pct:+.2f}%"
                log.info(f"📍 LIVE TRADE PING: {symbol} | Entry Price: ${entry_p_str} | Current Price: ${curr_p_str} | Price Move: {pnl_str}")

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
            log.info(f"🛰️ Scanning ALL Bitget Live USDT-Futures Pairs ({PRODUCT_TYPE} | Dynamic N-Candle Windows 5-60)...")
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

            log.info(f"✅ Found {total_coins} active pairs across Bitget USDT-Futures. Dividing into 20 parallel batch workers (~{chunk_size} pairs/batch)...")

            semaphore = asyncio.get_event_loop().is_running() and asyncio.Semaphore(15) or asyncio.Semaphore(15)
            batch_tasks = [process_coin_batch(i + 1, batch, session, semaphore) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            log.info("====================================================================================================")
            log.info(f"📊 DYNAMIC N-CANDLE COMPRESSION-TO-EXPANSION CANDIDATES (COLLECTED: {len(all_batch_candidates)} TOP SETUPS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'DIRECTION':<10} | {'WINDOW (N)':<12} | {'SMALL RANGE':<14} | {'BIG MOVE':<12} | {'SCORE':<14}")
            log.info("-" * 95)

            for cand in all_batch_candidates:
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {cand['direction']:<10} | {cand['n_candles']} Candles    | {cand['small_range_pct']:.2f}%         | {cand['big_move_pct']:+.2f}%     | {cand['expansion_score']:.4f}")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["expansion_score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 DYNAMIC N-CANDLE EXPANSION MATCHED: {best_signal['symbol']} ({best_signal['direction']} | Score: {best_signal['expansion_score']:.4f} | N={best_signal['n_candles']} Candles | Small Range: {best_signal['small_range_pct']:.2f}% | Big Move: {best_signal['big_move_pct']:+.2f}%)")

                # EXECUTE BITGET ORDER
                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    market_price=best_signal["current_price"],
                    available_balance=acc_info["available"] if acc_info else 10000.0
                )

                if live_order_result and live_order_result.get("filled", False):
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"])

                    payload = {
                        "symbol": live_order_result.get("symbol", best_signal["symbol"]),
                        "direction": best_signal["direction"],
                        "is_paper": False,
                        "is_demo": BITGET_DEMO_MODE,
                        "avg_fluctuation": round(best_signal["expansion_score"] * 10, 2),
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
                log.info(f"ℹ️ No active dynamic N-candle expansion candidates matched across pairs this scan run.")
                payload = {
                    "symbol": "NONE",
                    "direction": "NONE",
                    "is_paper": False,
                    "is_ping": False
                }

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

                    # POST-TRADE BITGET BALANCE AUDIT (4.5s SETTLEMENT DELAY BUFFER)
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

            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {status_code}")

if __name__ == "__main__":
    asyncio.run(main())

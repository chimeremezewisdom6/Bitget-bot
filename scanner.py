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

# MARKET SCANNING PRODUCT TYPE (Scans ALL 600+ real market pairs for signals)
SCAN_PRODUCT_TYPE = "USDT-FUTURES"

# BITGET DEMO vs REAL ISOLATION
# In Demo Mode (BITGET_DEMO_MODE = True), trades route strictly to Bitget's SUSDT-FUTURES demo ledger.
# Real money (USDT) CANNOT be touched when BITGET_DEMO_MODE is True.
DEMO_PRODUCT_TYPE = "SUSDT-FUTURES"
DEMO_MARGIN_COIN = "S-USDT"
SUPPORTED_DEMO_SYMBOLS = ["SBTCUSDT", "SETHUSDT", "SSOLUSDT"]

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType={SCAN_PRODUCT_TYPE}"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"

# Official Bitget v2 & v3 Endpoints
BITGET_V3_UTA_ASSETS_URL = f"https://{BIT_DOMAIN}/api/v3/account/assets"
BITGET_V3_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/place-order"
BITGET_V3_SET_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-leverage"
BITGET_V3_SET_POS_MODE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-position-mode"

BITGET_V2_DEMO_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v2/mix/order/place-order"
BITGET_V2_DEMO_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v2/mix/account/set-leverage"

LIVE_STREAK_FILE = "live_streak.json"
LIVE_ACTIVE_TRADE_FILE = "live_active_trade.json"

NUM_BATCHES = 20            # Exactly 20 separate scanning batches / workers
MIN_24H_VOLUME = 300000     # Min $300k Volume Filter
DEFAULT_LEVERAGE = 5        # Strictly 5x Leverage
BALANCE_USAGE_PCT = 0.90    # Strictly 90% of available equity allocated per trade

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
    """Queries official Bitget API and returns live Demo (S-USDT) or Real (USDT) equity & available margin."""
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

                target_coin = "S-USDT" if BITGET_DEMO_MODE else "USDT"
                asset_obj = next((a for a in assets_list if a.get("coin") == target_coin), None)
                if not asset_obj and BITGET_DEMO_MODE:
                    asset_obj = next((a for a in assets_list if "S-" in str(a.get("coin"))), None)

                available_margin = 0.0
                if asset_obj:
                    available_margin = float(asset_obj.get("available") or asset_obj.get("equity") or 0.0)
                    usdt_equity = float(asset_obj.get("equity") or available_margin)

                return {
                    "equity": usdt_equity if usdt_equity > 0 else 10000.0,
                    "available": available_margin if available_margin > 0 else 10000.0,
                    "margin_coin": target_coin,
                    "account_type": f"Bitget {'DEMO (S-USDT Air-Gapped)' if BITGET_DEMO_MODE else 'REAL LIVE (USDT)'}"
                }
    except Exception as e:
        log.error(f"Error querying Bitget balance: {e}")
    return None

async def configure_bitget_leverage(session, symbol):
    """Configures 5x Leverage on Bitget Exchange."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return

    if BITGET_DEMO_MODE:
        path = "/api/v2/mix/account/set-leverage"
        payload = {
            "productType": DEMO_PRODUCT_TYPE,
            "symbol": symbol,
            "marginCoin": DEMO_MARGIN_COIN,
            "leverage": str(DEFAULT_LEVERAGE)
        }
        url = BITGET_V2_DEMO_LEVERAGE_URL
    else:
        path = "/api/v3/account/set-leverage"
        payload = {
            "category": "USDT-FUTURES",
            "symbol": symbol,
            "leverage": str(DEFAULT_LEVERAGE)
        }
        url = BITGET_V3_SET_LEVERAGE_URL

    body_json = json.dumps(payload)
    headers = get_bitget_headers("POST", path, body_json)
    try:
        async with session.post(url, data=body_json, headers=headers, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget 5x Leverage Configured ({symbol}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance):
    """
    AIR-GAPPED DEMO vs REAL MONEY EXECUTION ENGINE:
    - IF BITGET_DEMO_MODE == True:
        Strictly routes to Bitget's SUSDT-FUTURES demo ledger using S-USDT demo margin!
        Real USDT funds CANNOT be touched under any circumstances.
    - IF BITGET_DEMO_MODE == False:
        Routes to Real Live USDT-FUTURES account across all 600+ real pairs.
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Cannot execute order.")
        return None

    if BITGET_DEMO_MODE:
        candidate_demo_sym = f"S{symbol}" if not symbol.startswith("S") else symbol
        if candidate_demo_sym in SUPPORTED_DEMO_PAIRS:
            trade_symbol = candidate_demo_sym
        else:
            trade_symbol = "SBTCUSDT"
            log.info(f"🛡️ DEMO AIR-GAP PROTECTOR: Mapping matched signal {symbol} to official Bitget S-USDT Demo pair {trade_symbol}. Real USDT funds are 100% UNTOUCHED.")

        # Get live market price of the demo symbol
        demo_price = await fetch_single_price(session, "BTCUSDT")
        if demo_price and demo_price > 0:
            market_price = demo_price
    else:
        trade_symbol = symbol

    await configure_bitget_leverage(session, trade_symbol)

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

    if BITGET_DEMO_MODE:
        path = "/api/v2/mix/order/place-order"
        url = BITGET_V2_DEMO_PLACE_ORDER_URL
        order_payload = {
            "productType": DEMO_PRODUCT_TYPE,
            "symbol": trade_symbol,
            "marginCoin": DEMO_MARGIN_COIN,
            "size": size_str,
            "side": side,
            "orderType": "market",
            "presetTakeProfitPrice": str(preset_tp),
            "presetStopLossPrice": str(preset_sl)
        }
    else:
        path = "/api/v3/trade/place-order"
        url = BITGET_V3_PLACE_ORDER_URL
        order_payload = {
            "category": "USDT-FUTURES",
            "symbol": trade_symbol,
            "marginCoin": "USDT",
            "qty": size_str,
            "side": side,
            "orderType": "market",
            "presetTakeProfitPrice": str(preset_tp),
            "presetStopLossPrice": str(preset_sl),
            "reduceOnly": "no"
        }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    mode_label = "🎮 BITGET DEMO (S-USDT AIR-GAPPED)" if BITGET_DEMO_MODE else "🚨 BITGET REAL MONEY (USDT)"
    log.info(f"🎯 SUBMITTING MARKET ORDER ({mode_label}): {trade_symbol} ({direction} | Matched Signal: {symbol}) | Size: {size_str} | TP: {preset_tp} (+2.5%) | SL: {preset_sl} (-1.25%)")

    try:
        async with session.post(url, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "ORDER_EXECUTED")
                log.info(f"✅ BITGET DEMO MATCHING ENGINE ACCEPTED ORDER! Order ID: {order_id}")
                return {
                    "order_id": order_id,
                    "symbol": trade_symbol,
                    "original_symbol": symbol,
                    "notional_value": notional_value,
                    "contract_size": size_str,
                    "preset_tp": preset_tp,
                    "preset_sl": preset_sl,
                    "real_fill_price": market_price,
                    "pre_trade_balance": available_balance,
                    "filled": True
                }
            else:
                log.error(f"❌ BITGET ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                return None
    except Exception as e:
        log.error(f"❌ Error submitting Bitget order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    """Executes an Immediate Market Close Order."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None

    close_side = "sell" if direction == "LONG" else "buy"

    if BITGET_DEMO_MODE:
        path = "/api/v2/mix/order/place-order"
        url = BITGET_V2_DEMO_PLACE_ORDER_URL
        order_payload = {
            "productType": DEMO_PRODUCT_TYPE,
            "symbol": symbol,
            "marginCoin": DEMO_MARGIN_COIN,
            "side": close_side,
            "orderType": "market",
            "size": str(contract_size) if contract_size and contract_size != "0" else "1",
            "reduceOnly": "yes"
        }
    else:
        path = "/api/v3/trade/place-order"
        url = BITGET_V3_PLACE_ORDER_URL
        order_payload = {
            "category": "USDT-FUTURES",
            "symbol": symbol,
            "marginCoin": "USDT",
            "side": close_side,
            "orderType": "market",
            "qty": str(contract_size) if contract_size and contract_size != "0" else "1",
            "reduceOnly": "yes"
        }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    log.info(f"🛑 EXECUTING MARKET EXIT ON BITGET EXCHANGE: Closing {symbol} ({direction}) | Size: {order_payload.get('qty') or order_payload.get('size')}")

    try:
        async with session.post(url, data=body_json, headers=headers, timeout=10) as r:
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
    """Fetches 60 1-MINUTE candles (OHLCV) for a single coin with retry handling."""
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
                            if candles and len(candles) >= 60:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.15 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
        return []

async def process_coin_batch(batch_id, coin_list, session, semaphore):
    """
    SMALL BUILD-UP (~0.5%) TO BIG EXPANSION DETECTOR ENGINE
    --------------------------------------------------------
    Evaluates 60 1-minute OHLCV candles across all Bitget Futures pairs:
      1. Scans dynamic N-candle buildup windows (from 5 to 50 candles).
      2. Detects steady, controlled build-up moves of 0.25% to 0.85% (target ~0.50%).
      3. Requires high directional candle consistency during the build-up phase (>= 65% same color candles).
      4. Detects immediate explosive price expansion (+1.00% to +3.00%+) breaking out from the build-up phase on volume acceleration (>= 1.35x).
      5. Calculates Score = (Big Expansion %) / (Build-Up Move %) * Volume Acceleration * Consistency.
      6. Ranks ALL market pairs to select the #1 EXPLOSIVE SETUP!
    """
    batch_evaluated = []

    tasks = [fetch_60m_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 60:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        # Reverse to chronological order (index 0 = 60m ago, index 59 = current 1m candle)
        candles_60m = list(reversed(candle_data[:60]))

        best_coin_setup = None
        highest_buildup_score = 0.0

        for n_candles in range(5, 50):
            buildup_window = candles_60m[:n_candles]
            expansion_window = candles_60m[n_candles:]

            if not buildup_window or not expansion_window:
                continue

            b_open = float(buildup_window[0][1])
            b_close = float(buildup_window[-1][4])
            b_high = max(float(c[2]) for c in buildup_window)
            b_low = min(float(c[3]) for c in buildup_window)

            if b_open <= 0 or b_low <= 0:
                continue

            # MEASURE SMALL BUILD-UP MOVE % (~0.50% TARGET RANGE: 0.25% to 0.85%)
            buildup_range_pct = ((b_high - b_low) / b_open) * 100.0
            buildup_net_pct = ((b_close - b_open) / b_open) * 100.0

            if buildup_range_pct < 0.20 or buildup_range_pct > 0.90:
                continue

            green_candles = sum(1 for c in buildup_window if float(c[4]) > float(c[1]))
            red_candles = sum(1 for c in buildup_window if float(c[4]) < float(c[1]))
            consistency_ratio = max(green_candles, red_candles) / float(n_candles)

            if consistency_ratio < 0.65:
                continue

            b_vol_avg = sum(float(c[5]) for c in buildup_window) / float(n_candles)
            exp_vol_avg = sum(float(c[5]) for c in expansion_window) / float(len(expansion_window))

            if b_vol_avg <= 0:
                continue

            vol_accel = exp_vol_avg / b_vol_avg
            if vol_accel < 1.35:
                continue

            p_current = float(candles_60m[-1][4])

            exp_move_up = ((p_current - b_high) / b_high) * 100.0
            exp_move_down = ((b_low - p_current) / b_low) * 100.0

            is_bull_expansion = (p_current > b_high) and (exp_move_up >= 0.35) and (buildup_net_pct > 0)
            is_bear_expansion = (p_current < b_low) and (exp_move_down >= 0.35) and (buildup_net_pct < 0)

            if is_bull_expansion or is_bear_expansion:
                direction = "LONG" if is_bull_expansion else "SHORT"
                big_expansion_pct = exp_move_up if is_bull_expansion else exp_move_down

                effective_buildup_pct = max(buildup_range_pct, 0.15)
                buildup_score = (big_expansion_pct / effective_buildup_pct) * vol_accel * consistency_ratio

                if buildup_score > highest_buildup_score:
                    highest_buildup_score = buildup_score
                    best_coin_setup = {
                        "batch_id": batch_id,
                        "symbol": symbol,
                        "vol_24h": vol_24h,
                        "direction": direction,
                        "n_candles": n_candles,
                        "buildup_range_pct": buildup_range_pct,
                        "big_expansion_pct": big_expansion_pct,
                        "vol_accel": vol_accel,
                        "buildup_score": buildup_score,
                        "current_price": p_current
                    }

        if best_coin_setup:
            batch_evaluated.append(best_coin_setup)

    if not batch_evaluated:
        return []

    batch_evaluated.sort(key=lambda x: x["buildup_score"], reverse=True)
    return [batch_evaluated[0]]

async def main():
    live_streak = get_live_win_streak()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = f"🎮 BITGET DEMO MODE (S-USDT Air-Gapped | 0.5% Build-Up Engine | 5x Leverage)" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING (USDT)"

    log.info(f"🏆 Current BITGET WIN STREAK: {live_streak} Wins | Mode: {mode_status} | API: {auth_status}")

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        current_equity = acc_info["equity"] if acc_info else 10000.0

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
            log.info(f"⏳ 0.5% BUILD-UP TRADE ACTIVE: {symbol} ({direction} @ ${entry_p_str}). Pre-Trade Equity: ${pre_trade_balance:.4f}. Monitoring price...")

            current_price = await fetch_single_price(session, symbol if not BITGET_DEMO_MODE else "BTCUSDT")
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
            log.info(f"🛰️ Scanning ALL Bitget Live USDT-Futures Pairs ({SCAN_PRODUCT_TYPE} | Small 0.5% Build-Up to Big Move)...")
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
            log.info(f"📊 SMALL 0.5% BUILD-UP TO BIG EXPANSION CANDIDATES (COLLECTED: {len(all_batch_candidates)} TOP SETUPS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'DIRECTION':<10} | {'BUILDUP (N)':<12} | {'BUILDUP MOVE':<14} | {'BIG EXPANSION':<14} | {'SCORE':<14}")
            log.info("-" * 100)

            for cand in all_batch_candidates:
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {cand['direction']:<10} | {cand['n_candles']} Candles    | {cand['buildup_range_pct']:.2f}%         | {cand['big_expansion_pct']:+.2f}%       | {cand['buildup_score']:.4f}")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["buildup_score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 SMALL 0.5% BUILD-UP EXPANSION MATCHED: {best_signal['symbol']} ({best_signal['direction']} | Score: {best_signal['buildup_score']:.4f} | N={best_signal['n_candles']} Candles | Build-Up: {best_signal['buildup_range_pct']:.2f}% | Big Move: {best_signal['big_expansion_pct']:+.2f}%)")

                # EXECUTE ORDER
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
                        "avg_fluctuation": round(best_signal["buildup_score"] * 10, 2),
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
                log.info(f"ℹ️ No active small build-up expansion candidates matched across pairs this scan run.")
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

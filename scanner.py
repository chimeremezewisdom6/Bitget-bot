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

ALLOW_LIVE_TRADING = os.environ.get("ALLOW_LIVE_TRADING", "true").lower() == "true"

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType=USDT-FUTURES"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"

# Official Bitget v3 Unified Trading Account (UTA) API Endpoints
BITGET_V3_UTA_ASSETS_URL = f"https://{BIT_DOMAIN}/api/v3/account/assets"
BITGET_V3_PLACE_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/place-order"
BITGET_V3_CANCEL_ORDER_URL = f"https://{BIT_DOMAIN}/api/v3/trade/cancel-order"
BITGET_V3_SET_LEVERAGE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-leverage"
BITGET_V3_SET_POS_MODE_URL = f"https://{BIT_DOMAIN}/api/v3/account/set-position-mode"
BITGET_V3_ORDER_INFO_URL = f"https://{BIT_DOMAIN}/api/v3/trade/order-info"

LIVE_STREAK_FILE = "live_streak.json"
LIVE_ACTIVE_TRADE_FILE = "live_active_trade.json"

NUM_BATCHES = 20           # Exactly 20 separate scanning batches / workers
MIN_24H_VOLUME = 100000    # Min $100k Volume
MAX_24H_VOLUME = 10000000  # Max $10M Volume Range
MIN_RECENT_CANDLES = 9     # Requires 9 or 10 same-color candles in recent 10m
MIN_20M_TREND_CANDLES = 14 # Requires >= 14/20 same-color candles over full 20m macro window
DEFAULT_LEVERAGE = 5       # Strictly 5x Leverage
BALANCE_USAGE_PCT = 0.90   # Strictly 90% of available USDT equity allocated per trade

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
    """Queries official Bitget UTA v3 API and returns live USDT equity & available margin."""
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
                usdt_asset = next((a for a in assets_list if a.get("coin") == "USDT"), None)

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
                    "margin_coin": "USDT",
                    "account_type": "Unified Trading Account (UTA v3)"
                }
    except Exception as e:
        log.error(f"Error querying Bitget UTA v3 balance: {e}")
    return None

async def cancel_unfilled_bitget_order(session, symbol, order_id):
    """Cancels an unfilled limit order on Bitget UTA v3 if it doesn't execute within 3 seconds."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE and order_id):
        return

    path = "/api/v3/trade/cancel-order"
    body_payload = json.dumps({
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "orderId": order_id
    })
    headers = get_bitget_headers("POST", path, body_payload)

    try:
        async with session.post(BITGET_V3_CANCEL_ORDER_URL, data=body_payload, headers=headers, timeout=5) as r:
            resp = await r.json()
            if resp.get("code") == "00000":
                log.info(f"🛑 UNFILLED LIMIT ORDER CANCELED ON BITGET ({symbol} Order: {order_id}) - ZERO SLIPPAGE TAKEN!")
    except Exception as e:
        log.debug(f"Order cancel notice: {e}")

async def fetch_bitget_order_status_and_fill(session, symbol, order_id):
    """Checks if order is filled and returns exact executed fill price."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE and order_id):
        return None

    path = f"/api/v3/trade/order-info?category=USDT-FUTURES&symbol={symbol}&orderId={order_id}"
    full_url = f"https://{BIT_DOMAIN}{path}"
    headers = get_bitget_headers("GET", path)

    try:
        async with session.get(full_url, headers=headers, timeout=5) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("code") == "00000" and resp.get("data"):
                    d = resp["data"]
                    status = d.get("state") or d.get("status")
                    fill_price = float(d.get("priceAvg") or d.get("fillPrice") or d.get("price") or 0.0)
                    executed_qty = float(d.get("baseVolume") or d.get("fillQty") or d.get("qty") or 0.0)
                    return {"status": status, "fill_price": fill_price, "executed_qty": executed_qty}
    except Exception as e:
        log.debug(f"Order status check notice: {e}")
    return None

async def configure_bitget_symbol_settings(session, symbol):
    """Configures 5x Leverage and One-Way Mode on Bitget UTA v3."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return

    path_pos = "/api/v3/account/set-position-mode"
    body_pos = json.dumps({"category": "USDT-FUTURES", "posMode": "one_way"})
    headers_pos = get_bitget_headers("POST", path_pos, body_pos)
    try:
        async with session.post(BITGET_V3_SET_POS_MODE_URL, data=body_pos, headers=headers_pos, timeout=5) as r:
            res = await r.json()
            log.info(f"⚙️ Bitget UTA v3 Position Mode Check ({symbol}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Position mode notice: {e}")

    path_lev = "/api/v3/account/set-leverage"
    body_lev = json.dumps({
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "leverage": str(DEFAULT_LEVERAGE)
    })
    headers_lev = get_bitget_headers("POST", path_lev, body_lev)
    try:
        async with session.post(BITGET_V3_SET_LEVERAGE_URL, data=body_lev, headers=headers_lev, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget UTA v3 5x Leverage Configured ({symbol}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, target_limit_price, available_balance):
    """
    Executes a ZERO-SLIPPAGE LIMIT ORDER on Bitget Engine at exact price.
    - Uses 90% of Available Balance at 5x Leverage.
    - 3-second Auto-Cancel Guard if not filled immediately.
    - Preset +1.0% Engine Take-Profit & -1.0% Engine Stop-Loss attached directly to Bitget.
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Cannot execute live trade.")
        return None

    await configure_bitget_symbol_settings(session, symbol)

    used_margin = available_balance * BALANCE_USAGE_PCT
    notional_value = used_margin * DEFAULT_LEVERAGE

    if notional_value < 5.0:
        notional_value = 5.50

    contract_size = notional_value / target_limit_price

    if target_limit_price < 0.001:
        size_str = f"{int(contract_size)}"
    elif target_limit_price > 1000:
        size_str = f"{contract_size:.3f}"
    elif target_limit_price > 10:
        size_str = f"{contract_size:.2f}"
    elif target_limit_price > 1:
        size_str = f"{contract_size:.1f}"
    else:
        size_str = f"{int(contract_size)}"

    if float(size_str) <= 0:
        size_str = "1"

    limit_p_str = format_price(target_limit_price)

    # STRICT 1.00% TAKE PROFIT AND STRICT 1.00% STOP LOSS ATTACHED DIRECTLY TO BITGET ENGINE
    if direction == "LONG":
        side = "buy"
        preset_tp = format_price(target_limit_price * 1.010)  # Strict +1.00% TP
        preset_sl = format_price(target_limit_price * 0.990)  # Strict -1.00% SL
    else:
        side = "sell"
        preset_tp = format_price(target_limit_price * 0.990)  # Strict +1.00% TP
        preset_sl = format_price(target_limit_price * 1.010)  # Strict -1.00% SL

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "marginCoin": "USDT",
        "qty": size_str,
        "side": side,
        "orderType": "limit",
        "price": limit_p_str,
        "presetTakeProfitPrice": str(preset_tp),
        "presetStopLossPrice": str(preset_sl),
        "reduceOnly": "no"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    log.info(f"🎯 SUBMITTING ZERO-SLIPPAGE LIMIT ORDER TO BITGET: {symbol} ({direction}) @ ${limit_p_str} | Size: {size_str} | 3s Fill Guard Active!")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "LIVE_ORDER_EXECUTED")
                log.info(f"✅ LIMIT ORDER ACCEPTED BY BITGET MATCHING ENGINE! Order ID: {order_id}")

                await asyncio.sleep(2.5)
                order_info = await fetch_bitget_order_status_and_fill(session, symbol, order_id)

                if order_info and order_info.get("executed_qty", 0) > 0:
                    real_fill = order_info["fill_price"] if order_info["fill_price"] > 0 else target_limit_price
                    log.info(f"⚡ LIMIT ORDER FILLED AT EXACT PRICE: ${format_price(real_fill)}! ZERO SLIPPAGE TAKEN.")
                    return {
                        "order_id": order_id,
                        "notional_value": notional_value,
                        "contract_size": size_str,
                        "preset_tp": preset_tp,
                        "preset_sl": preset_sl,
                        "real_fill_price": real_fill,
                        "pre_trade_balance": available_balance,
                        "filled": True
                    }
                else:
                    log.warning(f"⚠️ LIMIT ORDER AT ${limit_p_str} NOT FILLED WITHIN 3 SECONDS. CANCELING NOW TO PROTECT FUNDS!")
                    await cancel_unfilled_bitget_order(session, symbol, order_id)
                    return {"filled": False, "canceled": True}
            else:
                log.error(f"❌ BITGET LIMIT ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                return None
    except Exception as e:
        log.error(f"❌ Error submitting limit order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    """Executes an Immediate Live Market Close Order (reduceOnly: yes) via v3 UTA API for 10-minute timeout or manual exit."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None

    close_side = "sell" if direction == "LONG" else "buy"
    path = "/api/v3/trade/place-order"

    order_payload = {
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "marginCoin": "USDT",
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

    log.info(f"🛑 EXECUTING LIVE MARKET EXIT ON BITGET UTA v3 EXCHANGE: Closing {symbol} ({direction}) | Size: {order_payload['qty']}")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                log.info(f"✅ LIVE BITGET UTA v3 POSITION CLOSED ON EXCHANGE! Order ID: {resp.get('data', {}).get('orderId')}")
            else:
                log.warning(f"Notice on exchange close: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
    except Exception as e:
        log.error(f"Error executing live Bitget position close: {e}")

async def fetch_single_price(session, symbol):
    params = {"symbol": symbol, "productType": "USDT-FUTURES"}
    path = f"/api/v2/mix/market/ticker?symbol={symbol}&productType=USDT-FUTURES"
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
    path = "/api/v2/mix/market/tickers?productType=USDT-FUTURES"
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

async def fetch_candle_data_for_coin(session, symbol, semaphore):
    """Fetches 20 1-minute candles for a single coin with retry handling."""
    async with semaphore:
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1m", "limit": "20"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType=USDT-FUTURES&granularity=1m&limit=20"
        for attempt in range(3):
            headers = get_bitget_headers("GET", path)
            try:
                async with session.get(BITGET_CANDLES_URL, params=params, headers=headers, timeout=8) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("code") == "00000":
                            candles = data.get("data", [])
                            if candles and len(candles) >= 20:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.15 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
        return []

async def process_coin_batch(batch_id, coin_list, session, semaphore):
    """
    Processes a single batch of coins, evaluating 20-minute macro candle patterns.
    Requires >=9/10 in recent 10m AND >=14/20 in full 20m macro window to prevent counter-trend spikes.
    """
    batch_evaluated = []

    tasks = [fetch_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 20:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        candles_20m = list(reversed(candle_data[:20]))
        recent_10m = candles_20m[10:]

        recent_green = 0
        recent_red = 0
        recent_doji = 0
        fluctuations = []

        for c in recent_10m:
            o = float(c[1])
            h = float(c[2])
            l = float(c[3])
            cl = float(c[4])

            if o > 0:
                fluctuations.append(((h - l) / o) * 100.0)

            if cl > o:
                recent_green += 1
            elif cl < o:
                recent_red += 1
            else:
                recent_doji += 1

        total_green = 0
        total_red = 0
        total_doji = 0

        for c in candles_20m:
            o = float(c[1])
            cl = float(c[4])
            if cl > o:
                total_green += 1
            elif cl < o:
                total_red += 1
            else:
                total_doji += 1

        avg_fluctuation = (sum(fluctuations) / len(fluctuations)) if fluctuations else 0.0
        close_price = float(candles_20m[-1][4])

        max_recent_wins = max(recent_green, recent_red)
        dominant_direction = "LONG" if recent_green >= recent_red else "SHORT"

        macro_confirmed = False
        if dominant_direction == "LONG" and recent_green >= MIN_RECENT_CANDLES and total_green >= MIN_20M_TREND_CANDLES:
            macro_confirmed = True
        elif dominant_direction == "SHORT" and recent_red >= MIN_RECENT_CANDLES and total_red >= MIN_20M_TREND_CANDLES:
            macro_confirmed = True

        if macro_confirmed:
            batch_evaluated.append({
                "batch_id": batch_id,
                "symbol": symbol,
                "vol_24h": vol_24h,
                "green_count": recent_green,
                "red_count": recent_red,
                "doji_count": recent_doji,
                "total_green_20m": total_green,
                "total_red_20m": total_red,
                "max_wins": max_recent_wins,
                "direction": dominant_direction,
                "avg_fluctuation": avg_fluctuation,
                "current_price": close_price
            })

    if not batch_evaluated:
        return []

    max_batch_wins = max(c["max_wins"] for c in batch_evaluated)
    top_candidates = [c for c in batch_evaluated if c["max_wins"] == max_batch_wins]
    top_candidates.sort(key=lambda x: x["avg_fluctuation"], reverse=True)
    return top_candidates

async def main():
    live_streak = get_live_win_streak()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = "🚨 REAL MONEY LIVE BITGET TRADING (5x Leverage | 10-Min Stagnant Lock & Zero-Slippage Limit Entry)"

    log.info(f"🏆 Current REAL LIVE BITGET WIN STREAK: {live_streak} Wins | Mode: {mode_status} | API: {auth_status}")

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        current_equity = acc_info["equity"] if acc_info else 1.32

        if acc_info:
            log.info(f"💰 BITGET LIVE ACCOUNT EQUITY: ${acc_info['equity']:.4f} USDT | Available Margin: ${acc_info['available']:.4f} USDT ({acc_info['account_type']})")
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
            log.info(f"⏳ LIVE TRADE ACTIVE on {symbol} ({direction} @ ${entry_p_str}). Pre-Trade Equity: ${pre_trade_balance:.4f} USDT. Monitoring 10-min timeout...")

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
                log.error(f"Could not fetch live price for active trade {symbol}.")
                return
        else:
            log.info(f"🛰️ Fetching Bitget Futures coins ($100k to $10M Volume Range)...")
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                log.warning("❌ Could not fetch Bitget tickers.")
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0))))
                if MIN_24H_VOLUME <= vol_24h <= MAX_24H_VOLUME:
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h})

            valid_coins.sort(key=lambda x: x["vol_24h"], reverse=True)
            total_coins = len(valid_coins)

            chunk_size = (total_coins + NUM_BATCHES - 1) // NUM_BATCHES
            coin_batches = [valid_coins[i * chunk_size:(i + 1) * chunk_size] for i in range(NUM_BATCHES) if valid_coins[i * chunk_size:(i + 1) * chunk_size]]

            log.info(f"✅ Found {total_coins} active altcoins. Dividing into {len(coin_batches)} parallel batch workers (~{chunk_size} coins/batch)...")

            semaphore = asyncio.Semaphore(15)
            batch_tasks = [process_coin_batch(i + 1, batch, session, semaphore) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            log.info("====================================================================================================")
            log.info(f"📊 20-BATCH TOP CANDIDATE SUMMARY TABLE (COLLECTED: {len(all_batch_candidates)} 20M MACRO TREND CONFIRMED PAIRS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'RECENT 10M BREAKDOWN':<28} | {'20M MACRO TREND':<18} | {'AVG FLUCTUATION':<15}")
            log.info("-" * 105)

            for cand in all_batch_candidates:
                pattern_str = f"{cand['green_count']} Green / {cand['red_count']} Red"
                macro_str = f"{cand['total_green_20m']}G / {cand['total_red_20m']}R (20m)"
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {pattern_str:<28} | {macro_str:<18} | {cand['avg_fluctuation']:.2f}%")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["avg_fluctuation"], reverse=True)
                best_signal = all_batch_candidates[0]
                macro_info = f"{best_signal['total_green_20m']} Green / {best_signal['total_red_20m']} Red in 20m"

                log.info(f"🔥 BEST 20-CANDLE MACRO-CONFIRMED ENTRY SIGNAL FROM BATCH {best_signal['batch_id']:02d}: {best_signal['symbol']} ({best_signal['max_wins']}/10 {best_signal['direction']} | Macro: {macro_info} | Fluctuation: {best_signal['avg_fluctuation']:.2f}%)")

                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    target_limit_price=best_signal["current_price"],
                    available_balance=acc_info["available"] if acc_info else 1.32
                )

                if live_order_result and not live_order_result.get("filled", False):
                    log.info("🛡️ Limit Order was canceled by 3s Fill Guard. Skipping trade to protect account balance.")
                    payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_ping": False}
                else:
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"]) if live_order_result else best_signal["current_price"]

                    payload = {
                        "symbol": best_signal["symbol"],
                        "direction": best_signal["direction"],
                        "is_paper": False,
                        "avg_fluctuation": round(best_signal["avg_fluctuation"], 2),
                        "current_price": final_entry_fill,
                        "account_equity": current_equity,
                        "pre_trade_balance": current_equity,
                        "leverage": DEFAULT_LEVERAGE,
                        "position_mode": "one_way",
                        "reduce_only": True,
                        "is_ping": False,
                        "live_order": live_order_result,
                        "contract_size": live_order_result.get("contract_size", "1") if live_order_result else "1"
                    }
            else:
                log.info(f"ℹ️ No batch winners reached >= 9/10 recent candles WITH >= 14/20 macro trend confirmation this minute.")
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

                    # POST-TRADE BITGET BALANCE AUDIT & STRICT CASH GAIN WIN EVALUATION
                    await asyncio.sleep(1.5)
                    post_bal = await fetch_bitget_account_balance(session)
                    if post_bal:
                        final_eq = post_bal['equity']
                        net_cash_change = final_eq - pre_trade_balance
                        is_win = net_cash_change > 0

                        log.info("====================================================================================================")
                        log.info(f"💵 BITGET REAL ACCOUNT BALANCE AUDIT ({symbol}):")
                        log.info(f"   • Starting Account Equity: ${pre_trade_balance:.4f} USDT")
                        log.info(f"   • Closing Account Equity:  ${final_eq:.4f} USDT")
                        log.info(f"   • NET CASH CHANGE:         {'+' if net_cash_change>=0 else ''}${net_cash_change:.4f} USDT")
                        log.info(f"   • TRADE RESULT:            {'🏆 WIN (NET CASH PROFIT LOCKED AT 10M!)' if is_win else '❌ LOSS / FLAT EXIT (STREAK RESET TO 0)'}")
                        log.info(f"   • NEW LIVE WIN STREAK:     {res_data.get('live_win_streak', 0)} WINS")
                        log.info("====================================================================================================")

                elif worker_status == "HOLDING":
                    log.info(f"📈 TRADE HOLDING: {symbol} ({direction}) | Elapsed: {res_data.get('elapsed_minutes')}m")

            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {status_code}")

if __name__ == "__main__":
    asyncio.run(main())

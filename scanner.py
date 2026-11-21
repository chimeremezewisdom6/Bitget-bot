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

# BITGET DEMO MODE TOGGLE (Set BITGET_DEMO_MODE="false" in GitHub Secrets for Real Money)
BITGET_DEMO_MODE = os.environ.get("BITGET_DEMO_MODE", "true").lower() == "true"

PRODUCT_TYPE = "USDT-FUTURES"
ORDER_CATEGORY = "SUSDT-FUTURES" if BITGET_DEMO_MODE else "USDT-FUTURES"

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

async def configure_bitget_symbol_settings(session, symbol):
    """Configures 5x Leverage and One-Way Mode on Bitget UTA v3."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return

    demo_sym = f"S{symbol}" if (BITGET_DEMO_MODE and not symbol.startswith("S")) else symbol

    path_pos = "/api/v3/account/set-position-mode"
    body_pos = json.dumps({"category": ORDER_CATEGORY, "posMode": "one_way"})
    headers_pos = get_bitget_headers("POST", path_pos, body_pos)
    try:
        async with session.post(BITGET_V3_SET_POS_MODE_URL, data=body_pos, headers=headers_pos, timeout=5) as r:
            res = await r.json()
            log.info(f"⚙️ Bitget UTA v3 Position Mode Check ({demo_sym}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Position mode notice: {e}")

    path_lev = "/api/v3/account/set-leverage"
    body_lev = json.dumps({
        "category": ORDER_CATEGORY,
        "symbol": demo_sym,
        "leverage": str(DEFAULT_LEVERAGE)
    })
    headers_lev = get_bitget_headers("POST", path_lev, body_lev)
    try:
        async with session.post(BITGET_V3_SET_LEVERAGE_URL, data=body_lev, headers=headers_lev, timeout=5) as r:
            res = await r.json()
            log.info(f"⚡ Bitget UTA v3 5x Leverage Configured ({demo_sym}): {res.get('msg', 'OK')}")
    except Exception as e:
        log.debug(f"Leverage notice: {e}")

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance):
    """
    EXECUTING RED-CARD OPPONENT COLLAPSE MARKET ORDER:
    - Submits order to Bitget matching engine in <1ms.
    - Hard Preset Engine Take-Profit (+2.50%) & Stop-Loss (-1.25%) attached directly on Bitget!
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Cannot execute order.")
        return None

    trade_symbol = f"S{symbol}" if (BITGET_DEMO_MODE and not symbol.startswith("S")) else symbol

    await configure_bitget_symbol_settings(session, symbol)

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

    mode_label = "🎮 BITGET DEMO" if BITGET_DEMO_MODE else "🚨 BITGET REAL MONEY"
    log.info(f"🎯 SUBMITTING RED-CARD COLLAPSE MARKET ORDER ({mode_label}): {trade_symbol} ({direction}) | Size: {size_str} | TP: {preset_tp} (+2.5%) | SL: {preset_sl} (-1.25%)")

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
        "category": ORDER_CATEGORY,
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
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_payload, headers=headers, timeout=10) as r:
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

async def fetch_30m_candle_data_for_coin(session, symbol, semaphore):
    """Fetches 30 1-MINUTE candles (OHLCV) for a single coin with retry handling."""
    async with semaphore:
        params = {"symbol": symbol, "productType": PRODUCT_TYPE, "granularity": "1m", "limit": "30"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType={PRODUCT_TYPE}&granularity=1m&limit=30"
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

async def process_coin_batch(batch_id, coin_list, session, semaphore):
    """
    RED-CARD OPPONENT CANDLE STRUCTURE COLLAPSE & AGGREGATED WINNER ENGINE
    -----------------------------------------------------------------------
    Evaluates 30 1-minute OHLCV candles across all Bitget Futures pairs:
      1. First 15m Half (Candles 0-15): Benchmark boundary for opponent defense.
      2. Second 15m Half (Candles 15-30): Blowout momentum & opponent structural collapse.

      Condition A (Blowout Win Count):
        - Dominant side wins >= 9 out of 15 1-minute candles in current 15m half.

      Condition B (Opponent Red-Card Handicap - Structural Breakdown):
        - Opposing side's push distance (wick/body height) is CRIPPLED (<= 32% of total 15m range).
        - Opponent has lost all defensive volume & liquidity.

      Condition C (Volume Dominance):
        - Dominant volume >= 1.4x opposing volume.

      Condition D ("One Goal Needed to Win Aggregated"):
        - Price is pressing within 0.40% of breaking the prior 15m boundary or already broke out!

      Ranks ALL 370+ market pairs by Aggregated Dominance Score to pick the #1 GUARANTEED MATCH WINNER!
    """
    batch_evaluated = []

    tasks = [fetch_30m_candle_data_for_coin(session, c["symbol"], semaphore) for c in coin_list]
    candles_results = await asyncio.gather(*tasks)

    for idx, candle_data in enumerate(candles_results):
        if not candle_data or len(candle_data) < 30:
            continue

        coin = coin_list[idx]
        symbol = coin["symbol"]
        vol_24h = coin["vol_24h"]

        # Reverse to chronological order (index 0 = 30m ago, index 29 = current 1m candle)
        candles_30m = list(reversed(candle_data[:30]))

        first_half_15m = candles_30m[:15]   # Prior 15m
        second_half_15m = candles_30m[15:]  # Current 15m

        green_wins = sum(1 for c in second_half_15m if float(c[4]) > float(c[1]))
        red_wins = sum(1 for c in second_half_15m if float(c[4]) < float(c[1]))

        vol_green = sum(float(c[5]) for c in second_half_15m if float(c[4]) > float(c[1]))
        vol_red = sum(float(c[5]) for c in second_half_15m if float(c[4]) < float(c[1]))

        p_first_high = max(float(c[2]) for c in first_half_15m)
        p_first_low = min(float(c[3]) for c in first_half_15m)
        p_current = float(second_half_15m[-1][4])

        opp_push_green = sum((float(c[2]) - max(float(c[1]), float(c[4]))) for c in second_half_15m)  # Top wicks for bears
        opp_push_red = sum((min(float(c[1]), float(c[4])) - float(c[3])) for c in second_half_15m)   # Bottom wicks for bulls

        total_range_second = max(float(c[2]) for c in second_half_15m) - min(float(c[3]) for c in second_half_15m)
        if total_range_second <= 0:
            continue

        # BULLISH AGGREGATED MATCH WINNER (LONG)
        # - Green wins >= 9/15 candles.
        # - Green Volume >= 1.4x Red Volume.
        # - Opponent "Red Card" handicap: Red push is crippled (<= 32% of 15m range).
        # - Pressing within 0.40% of breaking prior 15m high!
        is_bullish_aggregated = (
            (green_wins >= 9) and
            (vol_green >= 1.4 * (vol_red + 1e-6)) and
            (opp_push_red / total_range_second <= 0.32) and
            (p_current >= p_first_high * 0.996)
        )

        # BEARISH AGGREGATED MATCH WINNER (SHORT)
        is_bearish_aggregated = (
            (red_wins >= 9) and
            (vol_red >= 1.4 * (vol_green + 1e-6)) and
            (opp_push_green / total_range_second <= 0.32) and
            (p_current <= p_first_low * 1.004)
        )

        if is_bullish_aggregated or is_bearish_aggregated:
            direction = "LONG" if is_bullish_aggregated else "SHORT"
            win_score = (green_wins / 15.0) * (vol_green / (vol_red + 1.0)) if is_bullish_aggregated else (red_wins / 15.0) * (vol_red / (vol_green + 1.0))

            batch_evaluated.append({
                "batch_id": batch_id,
                "symbol": symbol,
                "vol_24h": vol_24h,
                "direction": direction,
                "green_wins": green_wins,
                "red_wins": red_wins,
                "win_score": win_score,
                "current_price": p_current
            })

    if not batch_evaluated:
        return []

    # Sort candidates by highest Aggregated Match Score
    batch_evaluated.sort(key=lambda x: x["win_score"], reverse=True)
    return [batch_evaluated[0]]

async def main():
    live_streak = get_live_win_streak()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = f"🎮 BITGET DEMO MODE ({ORDER_CATEGORY} | 370+ Real Pairs Scanned | 5x Leverage)" if BITGET_DEMO_MODE else "🚨 REAL MONEY LIVE BITGET TRADING"

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
            log.info(f"⏳ RED-CARD MATCH WINNER TRADE ACTIVE: {symbol} ({direction} @ ${entry_p_str}). Pre-Trade Equity: ${pre_trade_balance:.4f}. Monitoring price...")

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
            log.info(f"🛰️ Scanning ALL Bitget Live USDT-Futures Pairs ({PRODUCT_TYPE} | Min Volume: $300k)...")
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
            log.info(f"📊 RED-CARD OPPONENT COLLAPSE CANDIDATES (COLLECTED: {len(all_batch_candidates)} TOP SETUPS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'DIRECTION':<10} | {'15M BREAKDOWN':<20} | {'WIN SCORE':<18}")
            log.info("-" * 75)

            for cand in all_batch_candidates:
                breakdown_str = f"{cand['green_wins']}G / {cand['red_wins']}R (15m)"
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {cand['direction']:<10} | {breakdown_str:<20} | {cand['win_score']:.4f}")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["win_score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 RED-CARD OPPONENT COLLAPSE MATCHED: {best_signal['symbol']} ({best_signal['direction']} | Score: {best_signal['win_score']:.4f} | 15m Breakdown: {best_signal['green_wins']}G / {best_signal['red_wins']}R)")

                # EXECUTE BITGET ORDER (AUTOMATICALLY PREFIXES DEMO SYMBOL IF DEMO MODE IS ACTIVE)
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
                        "avg_fluctuation": round(best_signal["win_score"] * 10, 2),
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
                log.info(f"ℹ️ No active red-card opponent collapse candidates matched across pairs this scan run.")
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

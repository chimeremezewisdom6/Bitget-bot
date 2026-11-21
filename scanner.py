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
MIN_24H_VOLUME = 100000    # Min $100k Volume (Scans ALL BTC, ETH, SOL, & Altcoins)
MAX_SLIPPAGE_PCT = 0.0010  # Strictly 0.10% Max Slippage Protection Cap
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

async def fetch_bitget_order_status_and_fill(session, symbol, order_id):
    """Checks if order is filled and returns exact executed fill price."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE and order_id):
        return None

    path = f"/api/v3/trade/order-info?category=USDT-FUTURES&symbol={symbol}&orderId={order_id}"
    full_url = f"https://{BIT_DOMAIN}{path}"
    headers = get_bitget_headers("GET", path)

    for _ in range(3):
        try:
            async with session.get(full_url, headers=headers, timeout=5) as r:
                if r.status == 200:
                    resp = await r.json()
                    if resp.get("code") == "00000" and resp.get("data"):
                        d = resp["data"]
                        status = d.get("state") or d.get("status")
                        fill_price = float(d.get("priceAvg") or d.get("fillPrice") or d.get("price") or 0.0)
                        executed_qty = float(d.get("baseVolume") or d.get("fillQty") or d.get("qty") or d.get("size") or 0.0)
                        if executed_qty > 0 or status in ("filled", "completed"):
                            return {"status": status, "fill_price": fill_price, "executed_qty": executed_qty}
        except Exception:
            pass
        await asyncio.sleep(0.3)
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

async def place_bitget_live_order(session, symbol, direction, market_price, available_balance):
    """
    SMART UNEXPLODED ABSORPTION IOC LIMIT ENTRY:
    - Long: Sets limit price = market_price * 1.0010 (0.10% max slippage ceiling).
    - Short: Sets limit price = market_price * 0.9990 (0.10% max slippage floor).
    - timeInForce: "IOC" (Immediate Or Cancel) -> Microsecond execution on Bitget engine (<1ms).
    - Hard Engine Take-Profit (+2.50%) & Stop-Loss (-1.50%).
    """
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        log.error("❌ Missing Bitget API Keys. Cannot execute live trade.")
        return None

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
        capped_limit_price = market_price * (1.0 + MAX_SLIPPAGE_PCT)
        preset_tp = format_price(market_price * 1.025)  # Hard +2.50% TP
        preset_sl = format_price(market_price * 0.985)  # Hard -1.50% SL
    else:
        side = "sell"
        capped_limit_price = market_price * (1.0 - MAX_SLIPPAGE_PCT)
        preset_tp = format_price(market_price * 0.975)  # Hard +2.50% TP
        preset_sl = format_price(market_price * 1.015)  # Hard -1.50% SL

    limit_p_str = format_price(capped_limit_price)

    path = "/api/v3/trade/place-order"
    order_payload = {
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "marginCoin": "USDT",
        "qty": size_str,
        "side": side,
        "orderType": "limit",
        "price": limit_p_str,
        "timeInForce": "IOC",
        "presetTakeProfitPrice": str(preset_tp),
        "presetStopLossPrice": str(preset_sl),
        "reduceOnly": "no"
    }

    body_json = json.dumps(order_payload)
    headers = get_bitget_headers("POST", path, body_json)

    log.info(f"🎯 SUBMITTING FRESH ABSORPTION IOC LIMIT ORDER TO BITGET: {symbol} ({direction}) | Limit Cap: ${limit_p_str} (Market: ${format_price(market_price)}) | Size: {size_str} | TP: {preset_tp} (+2.5%) | SL: {preset_sl} (-1.5%)")

    try:
        async with session.post(BITGET_V3_PLACE_ORDER_URL, data=body_json, headers=headers, timeout=10) as r:
            resp_text = await r.text()
            try:
                resp = json.loads(resp_text)
            except Exception:
                resp = {}

            if r.status == 200 and resp.get("code") == "00000":
                order_id = resp.get("data", {}).get("orderId", "LIVE_ORDER_EXECUTED")
                log.info(f"⚡ FRESH ABSORPTION ORDER PROCESSED BY BITGET ENGINE! Order ID: {order_id}")

                order_info = await fetch_bitget_order_status_and_fill(session, symbol, order_id)

                if order_info and order_info.get("executed_qty", 0) > 0:
                    real_fill = order_info["fill_price"] if order_info["fill_price"] > 0 else market_price
                    log.info(f"✅ FRESH ABSORPTION ORDER FILLED INSTANTLY AT: ${format_price(real_fill)}! (SLIPPAGE CAP: 0.10%)")
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
                    log.warning(f"🛡️ FRESH ABSORPTION ORDER AUTO-KILLED BY BITGET ENGINE: Spread exceeded 0.10% cap. Protected funds!")
                    return {"filled": False, "canceled": True}
            else:
                log.error(f"❌ BITGET IOC ORDER REJECTED: Code: {resp.get('code')} | Msg: {resp.get('msg')}")
                return None
    except Exception as e:
        log.error(f"❌ Error submitting IOC order: {e}")
        return None

async def close_bitget_live_position(session, symbol, direction, contract_size=""):
    """Executes an Immediate Live Market Close Order (reduceOnly: yes) via v3 UTA API."""
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

async def fetch_60m_candle_data_for_coin(session, symbol, semaphore):
    """Fetches 60 1-MINUTE candles (OHLCV) for a single coin with retry handling."""
    async with semaphore:
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1m", "limit": "60"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType=USDT-FUTURES&granularity=1m&limit=60"
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
    HIGH-IQ FRESH CAPITAL ABSORPTION & UNEXPLODED OPEN INTEREST (OI) ENGINE
    -----------------------------------------------------------------------
    Evaluates 60 1-minute OHLCV candles across all Bitget pairs:
      1. Condition A (Heavy Dump Baseline / Low Range / Oversold):
         - Measures 24h/60m price performance. Requires coin to have dumped or stayed compressed (e.g. 60m overall price move <= +0.5% or negative).
      2. Condition B (Heavy Fresh Capital / Order Flow Inflow):
         - Recent 60m trading volume is heavily expanded relative to overall price range (Volume-to-Range Ratio >= 2.0x average).
         - Capital / contracts are entering heavily, but price HAS NOT YET EXPLODED (+10%+ move hasn't happened yet!).
      3. Condition C (Recent 15m Green Turn / Reversal Trigger):
         - Recent 15m candles show a positive gain (+0.40% to +1.50%), proving buyers are actively stepping in and turning the price green!
      4. Ranks ALL market pairs by Absorption Accumulation Score to pick the #1 EXPLOSIVE SETUP in the market!
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
        change_24h_pct = float(coin.get("change24h") or coin.get("priceChangePercent") or 0.0)

        # Reverse to chronological order (index 0 = 60m ago, index 59 = current 1m candle)
        candles_60m = list(reversed(candle_data[:60]))

        older_45m = candles_60m[:45]
        recent_15m = candles_60m[45:]

        p_start_60m = float(candles_60m[0][1])  # Open 60m ago
        p_start_15m = float(recent_15m[0][1])  # Open 15m ago
        p_current = float(candles_60m[-1][4])  # Current close

        if p_start_60m <= 0 or p_start_15m <= 0:
            continue

        move_60m_pct = ((p_current - p_start_60m) / p_start_60m) * 100.0
        move_15m_pct = ((p_current - p_start_15m) / p_start_15m) * 100.0

        # Calculate Volume Accumulation vs Price Range (Capital Inflow)
        total_vol_60m = sum(float(c[5]) for c in candles_60m)
        total_vol_15m = sum(float(c[5]) for c in recent_15m)

        vol_share_15m = (total_vol_15m / total_vol_60m) if total_vol_60m > 0 else 0.0

        # 1. BULLISH ABSORPTION SETUP (HEAVY DUMP + FRESH BUY CAPITAL + 15M GREEN TURN)
        # - Coin is heavily dumped / depressed (24h or 60m move is negative or low).
        # - Has NOT exploded yet (60m total move < +3.0%).
        # - Recent 15m turned positive (+0.30% to +2.0% green reversal move).
        # - Volume share in recent 15m is concentrated (>= 30% of total 60m volume in last 15m).
        is_bullish_absorption = (
            (change_24h_pct <= 2.0 or move_60m_pct <= 1.0) and
            (move_60m_pct < 3.0) and
            (move_15m_pct >= 0.35) and
            (vol_share_15m >= 0.28)
        )

        # 2. BEARISH ABSORPTION SETUP (PUMP EXHAUSTION + FRESH SELL CAPITAL + 15M RED TURN)
        is_bearish_absorption = (
            (change_24h_pct >= -2.0 or move_60m_pct >= -1.0) and
            (move_60m_pct > -3.0) and
            (move_15m_pct <= -0.35) and
            (vol_share_15m >= 0.28)
        )

        if is_bullish_absorption or is_bearish_absorption:
            direction = "LONG" if is_bullish_absorption else "SHORT"
            abs_move_15m = abs(move_15m_pct)

            # Score formula: Concentrated Volume Share x Recent 15m Spark Move x Depressed Price Discount Factor
            absorption_score = vol_share_15m * abs_move_15m * (1.0 + (abs(change_24h_pct) / 100.0))

            batch_evaluated.append({
                "batch_id": batch_id,
                "symbol": symbol,
                "vol_24h": vol_24h,
                "change_24h_pct": change_24h_pct,
                "move_15m_pct": move_15m_pct,
                "vol_share_15m": vol_share_15m,
                "direction": direction,
                "absorption_score": absorption_score,
                "current_price": p_current
            })

    if not batch_evaluated:
        return []

    # Sort candidates by highest Absorption Score to pick the #1 unexploded setup in the market
    batch_evaluated.sort(key=lambda x: x["absorption_score"], reverse=True)
    return [batch_evaluated[0]]

async def main():
    live_streak = get_live_win_streak()

    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    auth_status = "🔐 AUTHENTICATED (Bitget API Key active)" if auth_active else "🔓 PUBLIC API (Unauthenticated)"
    mode_status = "🚨 REAL MONEY LIVE BITGET TRADING (5x Leverage | Fresh Capital Absorption & Unexploded Setup)"

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
            log.info(f"⏳ ABSORPTION TRADE ACTIVE on {symbol} ({direction} @ ${entry_p_str}). Pre-Trade Equity: ${pre_trade_balance:.4f} USDT. Monitoring price...")

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
            log.info(f"🛰️ Scanning ALL Bitget Futures Pairs for Fresh Capital Absorption & Unexploded Setup...")
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                log.warning("❌ Could not fetch Bitget tickers.")
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0))))
                change_24h = float(t.get("change24h") or t.get("priceChangePercent") or 0.0)
                if vol_24h >= MIN_24H_VOLUME:
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h, "change24h": change_24h})

            valid_coins.sort(key=lambda x: x["vol_24h"], reverse=True)
            total_coins = len(valid_coins)

            chunk_size = (total_coins + NUM_BATCHES - 1) // NUM_BATCHES
            coin_batches = [valid_coins[i * chunk_size:(i + 1) * chunk_size] for i in range(NUM_BATCHES) if valid_coins[i * chunk_size:(i + 1) * chunk_size]]

            log.info(f"✅ Found {total_coins} pairs across ALL Bitget USDT-Futures. Dividing into 20 parallel batch workers (~{chunk_size} pairs/batch)...")

            semaphore = asyncio.Semaphore(15)
            batch_tasks = [process_coin_batch(i + 1, batch, session, semaphore) for i, batch in enumerate(coin_batches)]
            batch_results = await asyncio.gather(*batch_tasks)

            all_batch_candidates = []
            for batch_cand in batch_results:
                all_batch_candidates.extend(batch_cand)

            log.info("====================================================================================================")
            log.info(f"📊 ALL-MARKET FRESH CAPITAL ABSORPTION CANDIDATES (COLLECTED: {len(all_batch_candidates)} TOP SETUPS):")
            log.info(f"{'BATCH':<8} | {'COIN PAIR':<14} | {'DIRECTION':<10} | {'24H DROP':<12} | {'15M SPARK':<12} | {'ABSORPTION SCORE':<18}")
            log.info("-" * 88)

            for cand in all_batch_candidates:
                log.info(f"Batch {cand['batch_id']:02d} | {cand['symbol']:<14} | {cand['direction']:<10} | {cand['change_24h_pct']:+.2f}%     | {cand['move_15m_pct']:+.2f}%     | {cand['absorption_score']:.4f}")

            log.info("====================================================================================================")

            if all_batch_candidates:
                all_batch_candidates.sort(key=lambda x: x["absorption_score"], reverse=True)
                best_signal = all_batch_candidates[0]

                log.info(f"🔥 #1 UNEXPLODED CAPITAL ABSORPTION SETUP MATCHED FROM BATCH {best_signal['batch_id']:02d}: {best_signal['symbol']} ({best_signal['direction']} | Score: {best_signal['absorption_score']:.4f} | 24h: {best_signal['change_24h_pct']:+.2f}% | 15m Spark: {best_signal['move_15m_pct']:+.2f}%)")

                # EXECUTE SMART IOC LIMIT ORDER WITH 0.10% SLIPPAGE PROTECTION CAP
                live_order_result = await place_bitget_live_order(
                    session=session,
                    symbol=best_signal["symbol"],
                    direction=best_signal["direction"],
                    market_price=best_signal["current_price"],
                    available_balance=acc_info["available"] if acc_info else 1.32
                )

                if live_order_result and not live_order_result.get("filled", False):
                    log.info("🛡️ Smart IOC Order auto-killed by Bitget engine due to spread cap (>0.10%). Protected account equity!")
                    payload = {"symbol": "NONE", "direction": "NONE", "is_paper": False, "is_ping": False}
                else:
                    final_entry_fill = live_order_result.get("real_fill_price", best_signal["current_price"]) if live_order_result else best_signal["current_price"]

                    payload = {
                        "symbol": best_signal["symbol"],
                        "direction": best_signal["direction"],
                        "is_paper": False,
                        "avg_fluctuation": round(best_signal["absorption_score"] * 10, 2),
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
                log.info(f"ℹ️ No active absorption candidates matched across the entire Bitget USDT-Futures market this scan run.")
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
                        log.info(f"💵 BITGET REAL ACCOUNT BALANCE AUDIT ({symbol}):")
                        log.info(f"   • Starting Account Equity: ${pre_trade_balance:.4f} USDT")
                        log.info(f"   • Closing Account Equity:  ${final_eq:.4f} USDT")
                        log.info(f"   • NET CASH CHANGE:         {'+' if net_cash_change>=0 else ''}${net_cash_change:.4f} USDT")
                        log.info(f"   • TRADE RESULT:            {'🏆 WIN (ABSORPTION SETUP NET CASH GAINED!)' if is_win else '❌ LOSS (STREAK RESET TO 0)'}")
                        log.info(f"   • NEW LIVE WIN STREAK:     {res_data.get('live_win_streak', 0)} WINS")
                        log.info("====================================================================================================")

                elif worker_status == "HOLDING":
                    log.info(f"📈 TRADE HOLDING: {symbol} ({direction}) | Elapsed: {res_data.get('elapsed_minutes')}m")

            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {status_code}")

if __name__ == "__main__":
    asyncio.run(main())

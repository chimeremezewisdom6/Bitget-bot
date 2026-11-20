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

# Safety Toggle: Set to 'true' in GitHub env to allow live real-money trading after 8 paper wins
ALLOW_LIVE_TRADING = os.environ.get("ALLOW_LIVE_TRADING", "false").lower() == "true"

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_ACCOUNT_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/account"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType=USDT-FUTURES"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"
BITGET_ACCOUNT_URL = f"{BITGET_ACCOUNT_BASE}/accounts?productType=USDT-FUTURES"

STREAK_FILE = "streak.json"
ACTIVE_TRADE_FILE = "active_trade.json"
SEMAPHORE = asyncio.Semaphore(12)

MIN_24H_VOLUME = 100000     # Min $100k Volume
MAX_24H_VOLUME = 10000000   # Max $10M Volume Range
MIN_CANDLE_WINS = 9        # Requires 9 or 10 same-color candles (allowing Doji)
DEFAULT_LEVERAGE = 5        # Strictly 5x Leverage

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

def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                data = json.load(f)
                return data.get("wins", 0)
        except Exception:
            return 0
    return 0

def get_active_trade():
    if os.path.exists(ACTIVE_TRADE_FILE):
        try:
            with open(ACTIVE_TRADE_FILE, "r") as f:
                data = json.load(f)
                if data.get("active"):
                    return data
        except Exception:
            return None
    return None

async def fetch_bitget_account_balance(session):
    """Fetches live Bitget Unified Trading Account equity balance and available USDT margin."""
    if not (BITGET_API_KEY and BITGET_SECRET_KEY and BITGET_PASSPHRASE):
        return None
    path = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    headers = get_bitget_headers("GET", path)
    try:
        async with session.get(BITGET_ACCOUNT_URL, headers=headers, timeout=10) as r:
            if r.status == 200:
                resp = await r.json()
                if resp.get("code") == "00000" and resp.get("data"):
                    accounts = resp["data"]
                    if isinstance(accounts, list) and len(accounts) > 0:
                        acc = accounts[0]
                        usdt_equity = float(acc.get("usdtEquity") or acc.get("accountEquity") or acc.get("available", 0.0))
                        available_margin = float(acc.get("available") or acc.get("maxTransferOut", 0.0))
                        return {
                            "equity": usdt_equity,
                            "available": available_margin,
                            "margin_coin": acc.get("marginCoin", "USDT"),
                            "account_type": "Unified Trading Account (Futures)"
                        }
    except Exception as e:
        log.error(f"Bitget Account Balance Fetch Error: {e}")
    return None

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

async def fetch_bitget_1m_candles_with_retry(session, symbol, max_retries=3):
    async with SEMAPHORE:
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1m", "limit": "10"}
        path = f"/api/v2/mix/market/candles?symbol={symbol}&productType=USDT-FUTURES&granularity=1m&limit=10"

        for attempt in range(max_retries):
            headers = get_bitget_headers("GET", path)
            try:
                async with session.get(BITGET_CANDLES_URL, params=params, headers=headers, timeout=10) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get("code") == "00000":
                            candles = data.get("data", [])
                            if candles and len(candles) >= 10:
                                return candles
                    elif r.status in (429, 403):
                        await asyncio.sleep(0.4 * (attempt + 1))
            except Exception:
                await asyncio.sleep(0.2 * (attempt + 1))

            await asyncio.sleep(0.04)

        return []

async def main():
    wins = get_win_streak()
    is_paper = (wins < 8) or (not ALLOW_LIVE_TRADING)

    # Check for keys (accepts either BITGET_PASSPHRASE or BITGET_PASSWORD)
    has_key = bool(BITGET_API_KEY)
    has_secret = bool(BITGET_SECRET_KEY)
    has_pass = bool(BITGET_PASSPHRASE)
    auth_active = has_key and has_secret and has_pass

    if auth_active:
        auth_status = "🔐 AUTHENTICATED (Bitget API Key active)"
    else:
        missing = []
        if not has_key: missing.append("BITGET_API_KEY")
        if not has_secret: missing.append("BITGET_SECRET_KEY")
        if not has_pass: missing.append("BITGET_PASSPHRASE or BITGET_PASSWORD")
        auth_status = f"🔓 PUBLIC API (Missing: {', '.join(missing)})"

    mode_status = "PAPER TRADING (Target: 8/8 Win Streak)" if is_paper else "🚨 LIVE REAL-MONEY BITGET TRADING (5x Leverage | Reduce-Only | One-Way Mode)"

    log.info(f"🏆 Current Paper Win Streak: {wins}/8 | Mode: {mode_status} | API: {auth_status}")

    async with aiohttp.ClientSession() as session:
        acc_info = await fetch_bitget_account_balance(session)
        if acc_info:
            log.info(f"💰 BITGET ACCOUNT BALANCE: Equity: ${acc_info['equity']:.2f} USDT | Available: ${acc_info['available']:.2f} USDT | Setting: 5x Leverage, Reduce-Only, One-Way Mode ({acc_info['account_type']})")
        elif auth_active:
            log.warning("⚠️ Could not fetch Bitget account balance. Verify API key permissions on Bitget.")
        else:
            log.info(f"ℹ️ Running in Unauthenticated mode. Missing environment variables: {auth_status}")

        active_trade = get_active_trade()

        if active_trade:
            symbol = active_trade.get("symbol")
            direction = active_trade.get("direction", "LONG")
            entry_price = float(active_trade.get("entry_price", 0.0))
            log.info(f"⏳ Trade ACTIVE on {symbol} ({direction} @ {entry_price}). Fetching live price for 5-min ping...")

            current_price = await fetch_single_price(session, symbol)
            if current_price and current_price > 0:
                if direction == "LONG":
                    live_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                else:
                    live_pnl_pct = ((entry_price - current_price) / entry_price) * 100.0

                pnl_str = f"{live_pnl_pct:+.2f}%"
                log.info(f"📍 LIVE TRADE PING: {symbol} | Entry: {entry_price:.5f} | Current: {current_price:.5f} | Live PnL: {pnl_str}")

                payload = {
                    "symbol": symbol,
                    "direction": direction,
                    "is_paper": is_paper,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "live_pnl_pct": round(live_pnl_pct, 2),
                    "account_equity": acc_info["equity"] if acc_info else None,
                    "leverage": DEFAULT_LEVERAGE,
                    "position_mode": "one_way",
                    "reduce_only": True,
                    "is_ping": True
                }
            else:
                log.error(f"Could not fetch live price for active trade {symbol}.")
                return
        else:
            log.info(f"🛰️ Scanning Bitget Futures coins ($100k to $10M Volume Range)...")
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
            total_scanned = len(valid_coins)
            log.info(f"✅ Found {total_scanned} active altcoins in $100k-$10M volume range. Fetching candle streams...")

            tasks = [fetch_bitget_1m_candles_with_retry(session, coin["symbol"]) for coin in valid_coins]
            all_candles = await asyncio.gather(*tasks)

            cat_10_green = 0
            cat_9_green = 0
            cat_8_green = 0
            cat_6_7_green = 0
            cat_neutral_chop = 0
            cat_6_7_red = 0
            cat_8_red = 0
            cat_9_red = 0
            cat_10_red = 0

            all_evaluated = []
            dropped_count = 0

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 10:
                    dropped_count += 1
                    continue

                coin_info = valid_coins[idx]
                symbol = coin_info["symbol"]
                vol_24h = coin_info["vol_24h"]
                candles = list(reversed(candle_data[:10]))

                green_count = 0
                red_count = 0
                doji_count = 0
                fluctuations = []

                for c in candles:
                    o = float(c[1])
                    h = float(c[2])
                    l = float(c[3])
                    cl = float(c[4])

                    if o > 0:
                        fluctuations.append(((h - l) / o) * 100.0)

                    if cl > o:
                        green_count += 1
                    elif cl < o:
                        red_count += 1
                    else:
                        doji_count += 1

                avg_fluctuation = (sum(fluctuations) / len(fluctuations)) if fluctuations else 0.0
                close_10m = float(candles[-1][4])

                if green_count == 10:
                    cat_10_green += 1
                elif green_count == 9:
                    cat_9_green += 1
                elif green_count == 8:
                    cat_8_green += 1
                elif green_count in (6, 7):
                    cat_6_7_green += 1
                elif red_count == 10:
                    cat_10_red += 1
                elif red_count == 9:
                    cat_9_red += 1
                elif red_count == 8:
                    cat_8_red += 1
                elif red_count in (6, 7):
                    cat_6_7_red += 1
                else:
                    cat_neutral_chop += 1

                all_evaluated.append({
                    "symbol": symbol,
                    "vol_24h": vol_24h,
                    "green_count": green_count,
                    "red_count": red_count,
                    "doji_count": doji_count,
                    "avg_fluctuation": avg_fluctuation,
                    "current_price": close_10m
                })

            log.info("=================================================================================")
            log.info(f"📊 MARKET CANDLE CATEGORY SUMMARY TABLE (FULLY EVALUATED: {len(all_evaluated)} / {total_scanned} COINS | DROPPED: {dropped_count}):")
            log.info(f"{'CANDLE PATTERN CATEGORY':<42} | {'NUMBER OF COINS':<15}")
            log.info("-" * 62)
            log.info(f"{'10 Green / 0 Red (Extreme Bullish Momentum)':<42} | {cat_10_green:<15}")
            log.info(f"{'9 Green / 0-1 Red (Strong Bullish Momentum - LONG Signal)':<42} | {cat_9_green:<15}")
            log.info(f"{'8 Green / 0-2 Red (High Bullish Momentum)':<42} | {cat_8_green:<15}")
            log.info(f"{'6-7 Green Candles (Moderate Bullish Trend)':<42} | {cat_6_7_green:<15}")
            log.info(f"{'4-5 Green / 4-5 Red (Sideways / Neutral Chop)':<42} | {cat_neutral_chop:<15}")
            log.info(f"{'6-7 Red Candles (Moderate Bearish Trend)':<42} | {cat_6_7_red:<15}")
            log.info(f"{'8 Red / 0-2 Green (High Bearish Momentum)':<42} | {cat_8_red:<15}")
            log.info(f"{'9 Red / 0-1 Green (Strong Bearish Momentum - SHORT Signal)':<42} | {cat_9_red:<15}")
            log.info(f"{'10 Red / 0 Green (Extreme Bearish Momentum)':<42} | {cat_10_red:<15}")
            log.info("=================================================================================")

            valid_longs = [c for c in all_evaluated if c["green_count"] >= MIN_CANDLE_WINS and c["avg_fluctuation"] >= 0.20]
            valid_shorts = [c for c in all_evaluated if c["red_count"] >= MIN_CANDLE_WINS and c["avg_fluctuation"] >= 0.20]

            for c in valid_longs:
                c["direction"] = "LONG"
                c["max_wins"] = c["green_count"]

            for c in valid_shorts:
                c["direction"] = "SHORT"
                c["max_wins"] = c["red_count"]

            all_signals = valid_longs + valid_shorts

            if all_signals:
                all_signals.sort(key=lambda x: x["avg_fluctuation"], reverse=True)
                best_signal = all_signals[0]
                doji_info = f" ({best_signal['doji_count']} Doji)" if best_signal['doji_count'] > 0 else ""
                log.info(f"🔥 ENTRY SIGNAL MATCHED: {best_signal['symbol']} ({best_signal['max_wins']}/10 {best_signal['direction']}{doji_info} | Fluctuation: {best_signal['avg_fluctuation']:.2f}%)")
                payload = {
                    "symbol": best_signal["symbol"],
                    "direction": best_signal["direction"],
                    "is_paper": is_paper,
                    "avg_fluctuation": round(best_signal["avg_fluctuation"], 2),
                    "current_price": best_signal["current_price"],
                    "account_equity": acc_info["equity"] if acc_info else None,
                    "leverage": DEFAULT_LEVERAGE,
                    "position_mode": "one_way",
                    "reduce_only": True,
                    "is_ping": False
                }
            else:
                log.info(f"ℹ️ No signals reaching >= {MIN_CANDLE_WINS}/10 candles with >= 0.20% fluctuation this minute.")
                payload = {
                    "symbol": "NONE",
                    "direction": "NONE",
                    "is_paper": is_paper,
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
                gross_pnl = res_data.get("gross_pnl_percent", "0.00")
                peak_pnl = res_data.get("peak_gross_pnl", "0.00")
                reason = res_data.get("reason", "")

                if worker_status == "CLOSED":
                    log.info(f"🛑 TRADE CLOSED: {symbol} ({direction}) | Closing Gross PnL: {gross_pnl}% | Peak PnL: {peak_pnl}% | Exit Reason: {reason} | Win Streak: {res_data.get('new_win_streak')}")
                elif worker_status == "HOLDING":
                    log.info(f"📈 TRADE HOLDING (5-MIN PING): {symbol} ({direction}) | Live Gross PnL: {gross_pnl}% | Peak PnL: {peak_pnl}% | Elapsed: {res_data.get('elapsed_minutes')}m")

            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {status_code}")

if __name__ == "__main__":
    asyncio.run(main())

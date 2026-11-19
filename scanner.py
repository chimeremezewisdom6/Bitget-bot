import os
import time
import json
import asyncio
import logging
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("scanner")

CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

BIT_DOMAIN = "api." + "bitget" + ".com"
BITGET_BASE = f"https://{BIT_DOMAIN}/api/v2/mix/market"
BITGET_TICKERS_URL = f"{BITGET_BASE}/tickers?productType=USDT-FUTURES"
BITGET_CANDLES_URL = f"{BITGET_BASE}/candles"
BITGET_SINGLE_TICKER_URL = f"{BITGET_BASE}/ticker"

STREAK_FILE = "streak.json"
ACTIVE_TRADE_FILE = "active_trade.json"
SEMAPHORE = asyncio.Semaphore(15)

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

async def fetch_single_price(session, symbol):
    params = {"symbol": symbol, "productType": "USDT-FUTURES"}
    try:
        async with session.get(BITGET_SINGLE_TICKER_URL, params=params, timeout=10) as r:
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
    try:
        async with session.get(BITGET_TICKERS_URL, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception as e:
        log.error(f"Ticker fetch error from Bitget: {e}")
    return []

async def fetch_bitget_1m_candles(session, symbol):
    async with SEMAPHORE:
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1m", "limit": "10"}
        try:
            async with session.get(BITGET_CANDLES_URL, params=params, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("code") == "00000":
                        return data.get("data", [])
        except Exception:
            pass
        return []

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    active_trade = get_active_trade()

    log.info(f"🏆 Current Win Streak: {wins}/8 | Mode: {'PAPER TRADING' if is_paper else '🚨 LIVE REAL-MONEY BITGET TRADING'}")

    if active_trade:
        symbol = active_trade.get("symbol")
        direction = active_trade.get("direction", "LONG")
        log.info(f"⏳ Trade active on {symbol} ({direction}). Fetching live price for ping...")

        async with aiohttp.ClientSession() as session:
            current_price = await fetch_single_price(session, symbol)
            if current_price and current_price > 0:
                payload = {
                    "symbol": symbol,
                    "direction": direction,
                    "is_paper": is_paper,
                    "current_price": current_price,
                    "is_ping": True
                }
                log.info(f"📍 Live Bitget Price for {symbol}: {current_price}")
            else:
                log.error(f"Could not fetch live price for active trade {symbol}.")
                return
    else:
        log.info("🛰️ Scanning ALL Bitget Futures pairs with $100k+ 24h Volume...")
        async with aiohttp.ClientSession() as session:
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                log.warning("❌ Could not fetch Bitget tickers. Check network connection.")
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0))))
                if vol_24h >= 100000:
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h})

            valid_coins.sort(key=lambda x: x["vol_24h"], reverse=True)
            total_scanned = len(valid_coins)
            log.info(f"✅ Successfully fetched data from Bitget! Found {total_scanned} active USDT-Futures pairs with $100k+ volume.")

            tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in valid_coins]
            all_candles = await asyncio.gather(*tasks)

            all_evaluated = []

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 10:
                    continue

                coin_info = valid_coins[idx]
                symbol = coin_info["symbol"]
                candles = list(reversed(candle_data))  # oldest to newest (10 1m candles)

                green_count = 0
                red_count = 0
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

                avg_fluctuation = (sum(fluctuations) / len(fluctuations)) if fluctuations else 0.0
                max_win_candles = max(green_count, red_count)
                direction = "LONG" if green_count >= red_count else "SHORT"
                close_10m = float(candles[-1][4])

                all_evaluated.append({
                    "symbol": symbol,
                    "direction": direction,
                    "green_count": green_count,
                    "red_count": red_count,
                    "max_wins": max_win_candles,
                    "avg_fluctuation": avg_fluctuation,
                    "current_price": close_10m
                })

            # Sort all scanned market coins by Candle Win Count descending, then Highest Fluctuation descending
            all_evaluated.sort(key=lambda x: (x["max_wins"], x["avg_fluctuation"]), reverse=True)

            log.info("--------------------------------------------------")
            log.info("📊 TOP 5 HIGHEST CANDLE WINNERS IN THE MARKET RIGHT NOW:")
            for i, c in enumerate(all_evaluated[:5], 1):
                log.info(f"  #{i} {c['symbol']}: {c['max_wins']}/10 Candles ({c['direction']}) | 10-Min Avg Fluctuation: {c['avg_fluctuation']:.2f}% | Price: {c['current_price']}")
            log.info("--------------------------------------------------")

            # Filter strictly for 9/10 or 10/10 winners with >= 0.20% avg 10m fluctuation
            valid_signals = [c for c in all_evaluated if c["max_wins"] >= 9 and c["avg_fluctuation"] >= 0.20]

            if valid_signals:
                # Select the 9/10 or 10/10 coin with the HIGHEST 10-minute average fluctuation
                valid_signals.sort(key=lambda x: x["avg_fluctuation"], reverse=True)
                best_signal = valid_signals[0]
                log.info(f"🔥 ENTRY SIGNAL MATCHED: {best_signal['symbol']} ({best_signal['max_wins']}/10 {best_signal['direction']} | Highest Fluctuation: {best_signal['avg_fluctuation']:.2f}%)")
                payload = {
                    "symbol": best_signal["symbol"],
                    "direction": best_signal["direction"],
                    "is_paper": is_paper,
                    "avg_fluctuation": round(best_signal["avg_fluctuation"], 2),
                    "current_price": best_signal["current_price"],
                    "is_ping": False
                }
            else:
                highest_coin = all_evaluated[0] if all_evaluated else None
                top_info = f"Highest in market: {highest_coin['symbol']} ({highest_coin['max_wins']}/10 {highest_coin['direction']}, {highest_coin['avg_fluctuation']:.2f}% fluc)" if highest_coin else "N/A"
                log.info(f"ℹ️ No coin reached 9/10 or 10/10 candles with >=0.20% fluctuation this minute. ({top_info})")
                payload = {
                    "symbol": "NONE",
                    "direction": "NONE",
                    "is_paper": is_paper,
                    "highest_market_winner": top_info,
                    "is_ping": False
                }

    headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15) as resp:
            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {resp.status}")

if __name__ == "__main__":
    asyncio.run(main())

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

MIN_24H_VOLUME = 100000     # Min $100k Volume
MAX_24H_VOLUME = 10000000   # Max $10M Volume Range
MIN_CANDLE_WINS = 8        # Minimum 8/10 candles for trade entry

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
        log.info(f"🛰️ Scanning Bitget Futures coins ($100k to $10M Volume Range)...")
        async with aiohttp.ClientSession() as session:
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
            log.info(f"✅ Found {total_scanned} active altcoins in $100k-$10M volume range.")

            tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in valid_coins]
            all_candles = await asyncio.gather(*tasks)

            # Initialize exact 10-candle distribution counters
            distribution = {
                (10, 0): [],
                (9, 1): [],
                (8, 2): [],
                (7, 3): [],
                (6, 4): [],
                (5, 5): [],
                (4, 6): [],
                (3, 7): [],
                (2, 8): [],
                (1, 9): [],
                (0, 10): []
            }

            all_evaluated = []

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 10:
                    continue

                coin_info = valid_coins[idx]
                symbol = coin_info["symbol"]
                vol_24h = coin_info["vol_24h"]
                candles = list(reversed(candle_data))  # oldest to newest (10 1m candles)

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

                # Record in distribution if exact green/red pair matches
                pair = (green_count, red_count)
                if pair in distribution:
                    distribution[pair].append(symbol)

                all_evaluated.append({
                    "symbol": symbol,
                    "vol_24h": vol_24h,
                    "green_count": green_count,
                    "red_count": red_count,
                    "doji_count": doji_count,
                    "avg_fluctuation": avg_fluctuation,
                    "current_price": close_10m
                })

            log.info("==========================================================================")
            log.info("📊 FULL MARKET CANDLE DISTRIBUTION MATRIX (LAST 10 MINUTES):")
            log.info(f"  🟢 10 Green / 0 Red : {len(distribution[(10, 0)])} coins {distribution[(10, 0)][:3]}")
            log.info(f"  🟢  9 Green / 1 Red : {len(distribution[(9, 1)])} coins {distribution[(9, 1)][:3]}")
            log.info(f"  🟢  8 Green / 2 Red : {len(distribution[(8, 2)])} coins {distribution[(8, 2)][:3]}")
            log.info(f"  🟢  7 Green / 3 Red : {len(distribution[(7, 3)])} coins {distribution[(7, 3)][:3]}")
            log.info(f"  🟢  6 Green / 4 Red : {len(distribution[(6, 4)])} coins {distribution[(6, 4)][:3]}")
            log.info(f"  ⚖️  5 Green / 5 Red : {len(distribution[(5, 5)])} coins {distribution[(5, 5)][:3]}")
            log.info(f"  🔴  4 Green / 6 Red : {len(distribution[(4, 6)])} coins {distribution[(4, 6)][:3]}")
            log.info(f"  🔴  3 Green / 7 Red : {len(distribution[(3, 7)])} coins {distribution[(3, 7)][:3]}")
            log.info(f"  🔴  2 Green / 8 Red : {len(distribution[(2, 8)])} coins {distribution[(2, 8)][:3]}")
            log.info(f"  🔴  1 Green / 9 Red : {len(distribution[(1, 9)])} coins {distribution[(1, 9)][:3]}")
            log.info(f"  🔴  0 Green / 10 Red: {len(distribution[(0, 10)])} coins {distribution[(0, 10)][:3]}")
            log.info("==========================================================================")

            # Filter for entry signals (>= MIN_CANDLE_WINS e.g. 8/10 with >= 0.20% avg fluctuation)
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
                log.info(f"🔥 ENTRY SIGNAL MATCHED: {best_signal['symbol']} ({best_signal['max_wins']}/10 {best_signal['direction']} | Fluctuation: {best_signal['avg_fluctuation']:.2f}%)")
                payload = {
                    "symbol": best_signal["symbol"],
                    "direction": best_signal["direction"],
                    "is_paper": is_paper,
                    "avg_fluctuation": round(best_signal["avg_fluctuation"], 2),
                    "current_price": best_signal["current_price"],
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
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15) as resp:
            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {resp.status}")

if __name__ == "__main__":
    asyncio.run(main())

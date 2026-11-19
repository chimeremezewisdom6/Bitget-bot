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
SEMAPHORE = asyncio.Semaphore(10)

MAX_ALLOWED_FRICTION_PCT = 0.32  # Hard Cap on Friction (Fees + Spread)

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
        log.error(f"Ticker fetch error: {e}")
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

    # =========================================================================
    # 1. TRADE IS ACTIVE -> FETCH LIVE PRICE & PING CLOUDFLARE WORKER
    # =========================================================================
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
                log.info(f"📍 Fetched live price for {symbol}: {current_price}")
            else:
                log.error(f"Could not fetch live price for active trade {symbol}.")
                return
    # =========================================================================
    # 2. NO ACTIVE TRADE -> SCAN TOP 200 VOLUME COINS & EVALUATE SIGNALS
    # =========================================================================
    else:
        log.info("🛰️ Scanning Bitget Top 200 Futures ($100k+ Volume, 9/10 Candles, Anti-Spike Filter, Friction <= 0.32%)...")
        async with aiohttp.ClientSession() as session:
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                log.warning("No Bitget tickers fetched.")
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0.0) or (float(t.get("baseVolume", 0.0)) * float(t.get("lastPr", 0.0))))
                if vol_24h >= 100000:  # $100k+ Volume Filter
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h})

            valid_coins.sort(key=lambda x: x["vol_24h"], reverse=True)
            top_200 = valid_coins[:200]

            log.info(f"Isolated {len(top_200)} top Bitget volume coins. Evaluating 10-minute candles...")

            tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in top_200]
            all_candles = await asyncio.gather(*tasks)

            top_signals = []

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 10:
                    continue

                coin_info = top_200[idx]
                symbol = coin_info["symbol"]
                candles = list(reversed(candle_data))  # oldest to newest

                green_count = 0
                red_count = 0
                fluctuations = []
                ranges = []

                for c in candles:
                    o = float(c[1])
                    h = float(c[2])
                    l = float(c[3])
                    cl = float(c[4])

                    c_range = h - l
                    ranges.append(c_range)

                    if o > 0:
                        fluctuations.append((c_range / o) * 100.0)

                    if cl > o:
                        green_count += 1
                    elif cl < o:
                        red_count += 1

                avg_fluctuation = (sum(fluctuations) / len(fluctuations)) if fluctuations else 0.0

                # FILTER 1: Average per-minute fluctuation >= 0.20%
                if avg_fluctuation < 0.20:
                    continue

                # FILTER 2: Anti-Spike / 2-Candle Pump Filter
                # If top 2 largest candles account for >= 80% of total 10m volatility range sum, EXCLUDE!
                total_range_sum = sum(ranges)
                sorted_ranges = sorted(ranges, reverse=True)
                top_2_range_sum = sum(sorted_ranges[:2])

                if total_range_sum > 0 and (top_2_range_sum / total_range_sum) >= 0.80:
                    log.info(f"⛔ Excluded {symbol}: Top 2 candles account for {(top_2_range_sum/total_range_sum)*100:.1f}% of 10m move (Spike/Pump Filter).")
                    continue

                # FILTER 3: Strict 9/10 or 10/10 Candle Consistency
                if green_count >= 9:
                    direction = "LONG"
                    score = (green_count * 10.0) + (avg_fluctuation * 5.0)
                elif red_count >= 9:
                    direction = "SHORT"
                    score = (red_count * 10.0) + (avg_fluctuation * 5.0)
                else:
                    continue

                # FILTER 4: Dynamic Friction Hard Cap (Bitget Taker Fee 0.12% + Slippage <= 0.32%)
                estimated_slippage = max(0.04, avg_fluctuation * 0.40)
                calculated_friction = 0.12 + estimated_slippage

                if calculated_friction > MAX_ALLOWED_FRICTION_PCT:
                    log.info(f"⛔ Excluded {symbol}: Estimated friction ({calculated_friction:.2f}%) exceeds hard cap of {MAX_ALLOWED_FRICTION_PCT}%.")
                    continue

                close_10m = float(candles[-1][4])

                top_signals.append({
                    "symbol": symbol,
                    "direction": direction,
                    "avg_fluctuation": avg_fluctuation,
                    "calculated_friction": calculated_friction,
                    "current_price": close_10m,
                    "score": score
                })

            top_signals.sort(key=lambda x: x["score"], reverse=True)

            if top_signals:
                best_signal = top_signals[0]
                log.info(f"🔥 BEST SIGNAL FOUND: {best_signal['symbol']} ({best_signal['direction']} | Fluctuation: {best_signal['avg_fluctuation']:.2f}%/min | Friction: {best_signal['calculated_friction']:.2f}% | Price: {best_signal['current_price']})")
                payload = {
                    "symbol": best_signal["symbol"],
                    "direction": best_signal["direction"],
                    "is_paper": is_paper,
                    "avg_fluctuation": round(best_signal["avg_fluctuation"], 2),
                    "calculated_friction": round(best_signal["calculated_friction"], 2),
                    "current_price": best_signal["current_price"],
                    "is_ping": False
                }
            else:
                log.info("No valid 9/10 momentum signals meeting friction & anti-spike criteria found this cycle.")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper, "is_ping": False}

    # =========================================================================
    # 3. POST PAYLOAD TO CLOUDFLARE WORKER WEBHOOK
    # =========================================================================
    headers = {"X-Webhook-Secret": WEBHOOK_SECRET, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers, timeout=15) as resp:
            log.info(f"📡 Webhook sent to Cloudflare Worker | Status: {resp.status}")

if __name__ == "__main__":
    asyncio.run(main())

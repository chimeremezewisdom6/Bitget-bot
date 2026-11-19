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

BITGET_TICKERS_URL = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
BITGET_CANDLES_URL = "https://api.bitget.com/api/v2/mix/market/candles"

STREAK_FILE = "streak.json"

def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                return json.load(f).get("wins", 0)
        except Exception:
            return 0
    return 0

async def fetch_bitget_tickers(session):
    """Fetches 24h stats for every coin on Bitget in ONE request."""
    try:
        async with session.get(BITGET_TICKERS_URL, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception as e:
        log.error(f"Failed to fetch Bitget tickers: {e}")
    return []

async def fetch_bitget_candles(session, symbol):
    """Fetches 24h of 15m candles for a specific coin."""
    params = {"symbol": symbol, "granularity": "15m", "limit": "96"}
    try:
        async with session.get(BITGET_CANDLES_URL, params=params, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception:
        return []
    return []

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    log.info(f"🛰️ Scanning Bitget Direct (100% Real Data)... (Streak: {wins}/8 | Mode: {mode_text})")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch ALL tickers from Bitget
        tickers = await fetch_bitget_tickers(session)
        if not tickers:
            log.error("❌ Failed to fetch Bitget markets.")
            return

        # 2. Filter out junk coins (Min $1M Volume)
        valid_coins = []
        for t in tickers:
            vol_24h = float(t.get("quoteVolume", 0))
            if vol_24h > 1000000: 
                valid_coins.append(t)
                
        valid_coins.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        log.info(f"✅ Found {len(valid_coins)} real coins with >$1M volume.")
        
        # Check top 100 highest volume coins
        top_100 = valid_coins[:100]
        
        # 3. Fetch 15m Candles for these 100 coins concurrently
        tasks = [fetch_bitget_candles(session, coin["symbol"]) for coin in top_100]
        all_candles = await asyncio.gather(*tasks)
        
        top_signals = []

        for idx, candle_data in enumerate(all_candles):
            if not candle_data or len(candle_data) < 90:
                continue
                
            coin_info = top_100[idx]
            symbol = coin_info["symbol"]
            
            # Bitget returns candles newest-first. [0] is the current 15m candle.
            current_candle = candle_data[0]
            close_price = float(current_candle[4])
            open_price = float(current_candle[1])
            vol_15m = float(current_candle[5])
            
            # Calculate 24h baseline from the 96 candles (24 hours)
            total_vol_24h = sum([float(c[5]) for c in candle_data])
            avg_vol_15m_baseline = total_vol_24h / 96.0
            
            price_change_15m = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
            
            # Volatility normalization (Mega vs Micro)
            ranges_24h = [(float(c[2]) - float(c[3])) / float(c[3]) for c in candle_data if float(c[3]) > 0]
            avg_range_24h = sum(ranges_24h) / len(ranges_24h) if ranges_24h else 0.01
            
            # --- CALCULATE METRICS ---
            vol_surge = vol_15m / avg_vol_15m_baseline if avg_vol_15m_baseline > 0 else 0
            move_multiplier = (price_change_15m / 100) / avg_range_24h if avg_range_24h > 0 else 0
            
            # 🚨 STRICT FILTERS 🚨
            if abs(price_change_15m) < 1.0: continue 
            if vol_surge < 2.0: continue 
            
            score = abs(price_change_15m) * vol_surge
            direction = "LONG" if price_change_15m > 0 else "SHORT"
            
            top_signals.append({
                "symbol": symbol,
                "direction": direction, 
                "score": score,
                "move_mult": move_multiplier,
                "vol_surge": vol_surge,
                "vol_24h_usd": float(coin_info["quoteVolume"]),
                "vol_15m": vol_15m,
                "change_15m": price_change_15m
            })
            
            top_signals.sort(key=lambda x: x["score"], reverse=True)
            if len(top_signals) > 3:
                top_signals.pop()

        scan_time = time.time() - start_time
        log.info(f"✅ Scan complete in {scan_time:.2f} seconds.")

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 REAL BITGET PAIRS ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['symbol']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  True Bitget Vol: ${sig['vol_24h_usd']:,.0f}")
                log.info(f"  [15M Data]  Vol: {sig['vol_15m']:,.0f} | Price Change: {sig['change_15m']:+.2f}%")
                log.info(f"  [Imbalance] 15M Volume is {sig['vol_surge']:.1f}x normal")

            best_signal = top_signals[0]
            log.info(f"🎯 SELECTED BEST: {best_signal['symbol']} {best_signal['direction']}")
            payload = {"symbol": best_signal["symbol"], "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ No Bitget coins passed the filters (Vol > $1M, Move > 1%). Waiting...")
            payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}

        # Send to Cloudflare Webhook
        headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "OPENED":
                    log.info(f"🟢 TRADE OPENED: {data['symbol']} {data['direction']} at {data['entry_price']} ({data['mode']})")
                elif data.get("status") == "HOLDING":
                    log.info(f"⏳ HOLDING: {data['symbol']} | Current PnL: {data['pnl_percent']}% | Peak PnL: {data['peak_pnl']}%")
                elif data.get("status") == "CLOSED":
                    emoji = "✅" if data["won"] else "❌"
                    log.info(f"{emoji} TRADE CLOSED: {data['symbol']} | Final PnL: {data['pnl_percent']}% | Peak: {data['peak_pnl']}% | Reason: {data['reason']} | New Streak: {data['streak']}/8")

if __name__ == "__main__":
    asyncio.run(main())

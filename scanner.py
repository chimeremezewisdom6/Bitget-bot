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
    log.info(f"🛰️ Scanning Bitget (Time Compression Engine)... (Streak: {wins}/8 | Mode: {mode_text})")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tickers = await fetch_bitget_tickers(session)
        if not tickers:
            log.error("❌ Failed to fetch Bitget markets.")
            return

        # 1. Filter by Volume (>$1M)
        valid_coins = []
        for t in tickers:
            vol_24h = float(t.get("quoteVolume", 0))
            if vol_24h > 1000000: 
                valid_coins.append(t)
                
        valid_coins.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        log.info(f"✅ Found {len(valid_coins)} real coins with >$1M volume.")
        
        # 2. Fetch 15m Candles for Top 100 coins
        top_100 = valid_coins[:100]
        tasks = [fetch_bitget_candles(session, coin["symbol"]) for coin in top_100]
        all_candles = await asyncio.gather(*tasks)
        
        top_signals = []

        for idx, candle_data in enumerate(all_candles):
            if not candle_data or len(candle_data) < 90:
                continue
                
            coin_info = top_100[idx]
            symbol = coin_info["symbol"]
            
            current_candle = candle_data[0]
            
            # --- 15M DATA ---
            open_15m = float(current_candle[1])
            high_15m = float(current_candle[2])
            low_15m = float(current_candle[3])
            close_15m = float(current_candle[4])
            vol_15m = float(current_candle[5])
            
            # --- 24H DATA ---
            open_24h = float(candle_data[-1][1])
            close_24h = close_15m
            total_vol_24h = sum([float(c[5]) for c in candle_data])
            avg_vol_15m_baseline = total_vol_24h / 96.0
            
            # --- CALCULATE CHANGES ---
            change_15m = ((close_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0
            change_24h = ((close_24h - open_24h) / open_24h) * 100 if open_24h > 0 else 0
            
            # --- NOISE FILTER ---
            candle_range = high_15m - low_15m
            candle_body = abs(close_15m - open_15m)
            if candle_range == 0: continue
            body_ratio = candle_body / candle_range
            
            # 🚨 ONLY BASIC FILTERS TO ENSURE REAL TRADES 🚨
            # 1. Must move at least 1% in 15m
            if abs(change_15m) < 1.0: continue 
            # 2. Volume must be surging (Takers present)
            vol_surge = vol_15m / avg_vol_15m_baseline if avg_vol_15m_baseline > 0 else 0
            if vol_surge < 1.5: continue
            # 3. Noise filter (No huge wicks)
            if body_ratio < 0.50: continue
            
            # --- TIME COMPRESSION LOGIC ---
            # How close is the 15m move to the 24h move? (Absolute values)
            # If change_24h is 0.1 and change_15m is 5.0, ratio is 50x (Huge compression)
            aggression_ratio = abs(change_15m) / abs(change_24h) if abs(change_24h) > 0.1 else abs(change_15m) * 10
            
            # Score: Aggression Ratio * Volume Surge * Body Ratio
            score = aggression_ratio * vol_surge * body_ratio
            
            # Determine direction based purely on the 15m candle
            direction = "LONG" if change_15m > 0 else "SHORT"
            
            top_signals.append({
                "symbol": symbol,
                "direction": direction, 
                "score": score,
                "vol_surge": vol_surge,
                "body_ratio": body_ratio,
                "change_24h": change_24h,
                "change_15m": change_15m,
                "aggression_ratio": aggression_ratio,
                "vol_24h_usd": float(coin_info["quoteVolume"])
            })
            
            top_signals.sort(key=lambda x: x["score"], reverse=True)
            if len(top_signals) > 3:
                top_signals.pop()

        scan_time = time.time() - start_time
        log.info(f"✅ Scan complete in {scan_time:.2f} seconds.")

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 BEST PAIRS (Time Compression) ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['symbol']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  True Vol: ${sig['vol_24h_usd']:,.0f} | Price Change: {sig['change_24h']:+.2f}%")
                log.info(f"  [15M Data]  Price Change: {sig['change_15m']:+.2f}% (Vol Surge: {sig['vol_surge']:.1f}x)")
                log.info(f"  [Compression] 15m move is {sig['aggression_ratio']*100:.1f}% of the 24h move!")
                log.info(f"  [Noise Check] 15m Candle Body is {sig['body_ratio']*100:.1f}% of total range.")

            # Since we only add signals that pass the basic filters, the #1 result is our best available option
            best_signal = top_signals[0]
            log.info(f"🎯 SELECTED BEST: {best_signal['symbol']} {best_signal['direction']}")
            payload = {"symbol": best_signal["symbol"], "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ Market is completely dead (No coin moved >1% with volume). Waiting...")
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

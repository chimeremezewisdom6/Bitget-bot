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
SEMAPHORE = asyncio.Semaphore(10) # Prevent Bitget IP ban

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

async def fetch_bitget_1m_candles(session, symbol):
    async with SEMAPHORE:
        # 🚨 CRITICAL FIX: Added productType and period (granularity)
        params = {
            "symbol": symbol, 
            "productType": "USDT-FUTURES",
            "granularity": "1m", 
            "limit": "15"
        }
        try:
            async with session.get(BITGET_CANDLES_URL, params=params, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("code") == "00000":
                        return data.get("data", [])
                elif r.status == 429:
                    await asyncio.sleep(1) # Back off if rate limited
        except Exception:
            pass
        return []

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    log.info(f"🛰️ Scanning Bitget (Candle Arrangement)... (Streak: {wins}/8 | Mode: {mode_text})")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tickers = await fetch_bitget_tickers(session)
        if not tickers:
            log.error("❌ Failed to fetch Bitget markets.")
            return

        # 1. Filter by Volume (>$200k) and calculate volatility
        valid_coins = []
        for t in tickers:
            vol_24h = float(t.get("quoteVolume", 0))
            price_change_24h = abs(float(t.get("priceChangePercent", 0)))
            
            if vol_24h > 200000: # Changed to 200k
                valid_coins.append({
                    "symbol": t["symbol"],
                    "vol_24h": vol_24h,
                    "volatility": price_change_24h
                })
                
        # 2. Sort by Volatility (highest first) and take Top 200
        valid_coins.sort(key=lambda x: x["volatility"], reverse=True)
        top_200 = valid_coins[:200]
        
        log.info(f"✅ Found {len(valid_coins)} coins >$200k vol. Selected Top {len(top_200)} most volatile.")
        
        # 3. Fetch 1m Candles for these Top 200 coins safely
        tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in top_200]
        all_candles = await asyncio.gather(*tasks)
        
        top_signals = []

        for idx, candle_data in enumerate(all_candles):
            if not candle_data or len(candle_data) < 10:
                continue
                
            coin_info = top_200[idx]
            symbol = coin_info["symbol"]
            
            # Reverse the candles so index 0 is the OLDEST candle (15 mins ago)
            # This makes reading the sequence from left to right logical.
            candles = list(reversed(candle_data))
            
            open_15m = float(candles[0][1])
            close_15m = float(candles[-1][4])
            total_15m_move_pct = ((close_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0
            
            up_steps = 0
            down_steps = 0
            sequence = []
            
            for c in candles:
                o = float(c[1])
                cl = float(c[4])
                if cl > o:
                    up_steps += 1
                    sequence.append("U")
                elif cl < o:
                    down_steps += 1
                    sequence.append("D")
                else:
                    sequence.append("-") # Doji
            
            if up_steps == 0 and down_steps == 0:
                continue 
                
            if up_steps > down_steps:
                direction = "LONG"
                dominance_ratio = up_steps / down_steps if down_steps > 0 else up_steps
            elif down_steps > up_steps:
                direction = "SHORT"
                dominance_ratio = down_steps / up_steps if up_steps > 0 else down_steps
            else:
                continue
                
            score = dominance_ratio * abs(total_15m_move_pct) if abs(total_15m_move_pct) > 0 else dominance_ratio * 0.1
            
            top_signals.append({
                "symbol": symbol,
                "direction": direction,
                "up_steps": up_steps,
                "down_steps": down_steps,
                "dominance_ratio": dominance_ratio,
                "change_15m": total_15m_move_pct,
                "vol_24h_usd": coin_info["vol_24h"],
                "sequence": " ".join(sequence),
                "score": score
            })
            
            top_signals.sort(key=lambda x: x["score"], reverse=True)
            if len(top_signals) > 3:
                top_signals.pop()

        scan_time = time.time() - start_time
        log.info(f"✅ Scan complete in {scan_time:.2f} seconds.")

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 BEST COINS (Candle Arrangement) ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['symbol']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  True Vol: ${sig['vol_24h_usd']:,.0f}")
                log.info(f"  [15M Data]  Price Change: {sig['change_15m']:+.2f}%")
                log.info(f"  [Arrangement] {sig['sequence']} (Oldest to Newest)")
                log.info(f"  [Steps]     {sig['up_steps']} UP vs {sig['down_steps']} DOWN ({sig['dominance_ratio']:.2f}x dominance)")

            best_signal = top_signals[0]
            log.info(f"🎯 SELECTED BEST: {best_signal['symbol']} {best_signal['direction']}")
            payload = {"symbol": best_signal["symbol"], "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ Market is dead. No valid arrangements found.")
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

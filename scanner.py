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
BITGET_SINGLE_TICKER_URL = "https://api.bitget.com/api/v2/mix/market/ticker"

STREAK_FILE = "streak.json"
ACTIVE_TRADE_FILE = "active_trade.json"
SEMAPHORE = asyncio.Semaphore(10)

def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                return json.load(f).get("wins", 0)
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
                data = await r.json()
                if data.get("code") == "00000" and data.get("data"):
                    return float(data["data"][0]["lastPr"])
    except Exception:
        pass
    return None

async def fetch_bitget_tickers(session):
    try:
        async with session.get(BITGET_TICKERS_URL, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
    except Exception:
        pass
    return []

async def fetch_bitget_1m_candles(session, symbol):
    async with SEMAPHORE:
        # Look at the last 10 1-minute candles
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
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    
    active_trade = get_active_trade()
    
    if active_trade:
        log.info(f"⏳ Active trade in progress: {active_trade['symbol']}. Fetching live price... (Streak: {wins}/8)")
        async with aiohttp.ClientSession() as session:
            current_price = await fetch_single_price(session, active_trade['symbol'])
            
            if current_price:
                payload = {
                    "symbol": active_trade['symbol'], 
                    "direction": active_trade['direction'], 
                    "is_paper": is_paper,
                    "current_price": current_price,
                    "is_ping": True
                }
            else:
                log.error("❌ Failed to fetch active trade price.")
                return
    else:
        log.info(f"🛰️ Scanning Bitget (Slow Acceleration Engine)... (Streak: {wins}/8 | Mode: {mode_text})")
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                return

            valid_coins = []
            for t in tickers:
                vol_24h = float(t.get("quoteVolume", 0))
                price_change_24h = abs(float(t.get("priceChangePercent", 0)))
                if vol_24h > 200000: 
                    valid_coins.append({"symbol": t["symbol"], "vol_24h": vol_24h, "volatility": price_change_24h})
                    
            valid_coins.sort(key=lambda x: x["volatility"], reverse=True)
            top_200 = valid_coins[:200]
            
            tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in top_200]
            all_candles = await asyncio.gather(*tasks)
            
            top_signals = []

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 10:
                    continue
                    
                coin_info = top_200[idx]
                symbol = coin_info["symbol"]
                candles = list(reversed(candle_data)) # Oldest to newest (10 candles)
                
                open_10m = float(candles[0][1])
                close_10m = float(candles[-1][4])
                net_move_pct = ((close_10m - open_10m) / open_10m) * 100 if open_10m > 0 else 0
                
                up_steps = 0
                down_steps = 0
                up_bodies = []
                down_bodies = []
                is_spike = False
                sequence = []
                
                for c in candles:
                    o = float(c[1])
                    cl = float(c[4])
                    body_pct = ((cl - o) / o) * 100 if o > 0 else 0
                    
                    # 🚨 NO SPIKE RULE (Max 0.8% per 1m candle) 🚨
                    if abs(body_pct) > 0.8:
                        is_spike = True
                        break
                        
                    if cl > o:
                        up_steps += 1
                        up_bodies.append(body_pct)
                        sequence.append("U")
                    elif cl < o:
                        down_steps += 1
                        down_bodies.append(abs(body_pct))
                        sequence.append("D")
                    else:
                        sequence.append("-")
                
                if is_spike or up_steps == 0 or down_steps == 0:
                    continue
                    
                # 🚨 FILTER 1: 70% Dominance (e.g., 7 out of 10) 🚨
                max_steps = max(up_steps, down_steps)
                min_steps = min(up_steps, down_steps)
                
                if max_steps < 7:
                    continue
                    
                # 🚨 FILTER 2: SLOW ACCELERATION 🚨
                # Check if the winning side's bodies are getting larger (recent 3 vs first 3)
                if up_steps > down_steps:
                    direction = "LONG"
                    winning_bodies = up_bodies
                    losing_bodies = down_bodies
                else:
                    direction = "SHORT"
                    winning_bodies = down_bodies
                    losing_bodies = up_bodies
                    
                if len(winning_bodies) >= 6:
                    first_3_avg = sum(winning_bodies[:3]) / 3
                    last_3_avg = sum(winning_bodies[-3:]) / 3
                    
                    # If the last 3 candles are smaller than the first 3, it's decelerating. We want acceleration.
                    if last_3_avg < first_3_avg:
                        continue
                        
                # 🚨 FILTER 3: Opposing side is completely dead 🚨
                total_win_vol = sum(winning_bodies)
                total_lose_vol = sum(losing_bodies)
                
                if total_lose_vol > (total_win_vol * 0.4):
                    continue # Losers are fighting back too hard
                    
                # Score: Step Dominance * Acceleration * Net Move
                dominance_ratio = max_steps / min_steps if min_steps > 0 else 10.0
                score = dominance_ratio * abs(net_move_pct)
                
                top_signals.append({
                    "symbol": symbol,
                    "direction": direction,
                    "net_move": net_move_pct,
                    "sequence": " ".join(sequence),
                    "dominance_ratio": dominance_ratio,
                    "current_price": close_10m,
                    "score": score
                })
                
                top_signals.sort(key=lambda x: x["score"], reverse=True)
                if len(top_signals) > 3:
                    top_signals.pop()

            scan_time = time.time() - start_time
            log.info(f"✅ Scan complete in {scan_time:.2f} seconds.")

            if top_signals:
                best_signal = top_signals[0]
                log.info(f"🏆 SELECTED BEST: {best_signal['symbol']} {best_signal['direction']}")
                log.info(f"  [Sequence]    {best_signal['sequence']}")
                log.info(f"  [Dominance]   {best_signal['dominance_ratio']:.1f}x stronger on {best_signal['direction']} side")
                log.info(f"  [Net Move]    {best_signal['net_move']:+.2f}% (Slowly accelerating...)")
                
                payload = {
                    "symbol": best_signal["symbol"], 
                    "direction": best_signal["direction"], 
                    "is_paper": is_paper,
                    "current_price": best_signal["current_price"],
                    "is_ping": False
                }
            else:
                log.warning("❌ No coins passed the Slow Acceleration filter right now.")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper, "is_ping": False}

    # Send to Cloudflare Webhook
    headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "OPENED":
                    log.info(f"🟢 TRADE OPENED: {data['symbol']} {data['direction']} at {data['entry_price']}")
                    log.info(f"   [Stop Loss] {data['stop_loss']}")
                elif data.get("status") == "HOLDING":
                    log.info(f"⏳ HOLDING: {data['symbol']} | PnL: {data['pnl_percent']}% | Peak PnL: {data['peak_pnl']}%")
                elif data.get("status") == "CLOSED":
                    emoji = "✅" if data["won"] else "❌"
                    log.info(f"{emoji} TRADE CLOSED: {data['symbol']}")
                    log.info(f"   [FINAL PnL] {data['pnl_percent']}% | [Peak PnL] {data['peak_pnl']}%")
                    log.info(f"   [Reason] {data['reason']} | [New Streak] {data['streak']}/8")
            else:
                err = await resp.text()
                log.error(f"❌ CLOUDFLARE ERROR: {err}")

if __name__ == "__main__":
    asyncio.run(main())

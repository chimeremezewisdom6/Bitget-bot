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

def is_trade_active():
    if os.path.exists(ACTIVE_TRADE_FILE):
        try:
            with open(ACTIVE_TRADE_FILE, "r") as f:
                return json.load(f).get("active", False)
        except Exception:
            return False
    return False

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
        # Look at the last 15 1-minute candles
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1m", "limit": "15"}
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
    
    if is_trade_active():
        log.info(f"⏳ Active trade in progress. Pinging Cloudflare to manage TP/SL... (Streak: {wins}/8)")
        payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}
    else:
        log.info(f"🛰️ Scanning Bitget (Stealth Trap Engine)... (Streak: {wins}/8 | Mode: {mode_text})")
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            tickers = await fetch_bitget_tickers(session)
            if not tickers:
                return

            # Filter by >$200k Volume and Top 200 Volatile
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
                if not candle_data or len(candle_data) < 15:
                    continue
                    
                coin_info = top_200[idx]
                symbol = coin_info["symbol"]
                candles = list(reversed(candle_data)) # Oldest to newest
                
                open_15m = float(candles[0][1])
                close_15m = float(candles[-1][4])
                net_move_pct = ((close_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0
                
                up_steps = 0
                down_steps = 0
                up_body_pct = 0.0
                down_body_pct = 0.0
                is_spike = False
                sequence = []
                
                for c in candles:
                    o = float(c[1])
                    cl = float(c[4])
                    
                    # Calculate single candle move %
                    candle_move_pct = abs(((cl - o) / o) * 100) if o > 0 else 0
                    
                    # 🚨 NO SPIKE RULE 🚨
                    if candle_move_pct > 1.0:
                        is_spike = True
                        break
                        
                    if cl > o:
                        up_steps += 1
                        up_body_pct += candle_move_pct
                        sequence.append("U")
                    elif cl < o:
                        down_steps += 1
                        down_body_pct += candle_move_pct
                        sequence.append("D")
                    else:
                        sequence.append("-")
                
                # Reject if there was a 1% spike
                if is_spike:
                    continue
                    
                if up_steps == 0 or down_steps == 0:
                    continue
                    
                # --- STEALTH TRAP LOGIC ---
                # LONG TRAP: Fewer green candles, but massive green bodies, price is going up
                if down_steps > up_steps and net_move_pct > 0.2 and up_body_pct > (down_body_pct * 1.5):
                    direction = "LONG"
                    dominance = up_body_pct / down_body_pct
                    trap_type = f"Only {up_steps} Green candles, but they are {dominance:.1f}x larger than the {down_steps} Red candles!"
                    
                # SHORT TRAP: Fewer red candles, but massive red bodies, price is going down
                elif up_steps > down_steps and net_move_pct < -0.2 and down_body_pct > (up_body_pct * 1.5):
                    direction = "SHORT"
                    dominance = down_body_pct / up_body_pct
                    trap_type = f"Only {down_steps} Red candles, but they are {dominance:.1f}x larger than the {up_steps} Green candles!"
                    
                else:
                    continue # No trap, skip
                    
                score = abs(net_move_pct) * dominance
                
                top_signals.append({
                    "symbol": symbol,
                    "direction": direction,
                    "net_move": net_move_pct,
                    "up_steps": up_steps,
                    "down_steps": down_steps,
                    "dominance": dominance,
                    "trap_type": trap_type,
                    "sequence": " ".join(sequence),
                    "vol_24h_usd": coin_info["vol_24h"],
                    "current_price": close_15m,
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
                log.info(f"  [Trap Found]  {best_signal['trap_type']}")
                log.info(f"  [Net Move]    {best_signal['net_move']:+.2f}% (Price agrees with the strong side!)")
                
                payload = {
                    "symbol": best_signal["symbol"], 
                    "direction": best_signal["direction"], 
                    "is_paper": is_paper,
                    "current_price": best_signal["current_price"]
                }
            else:
                log.warning("❌ No stealth traps found right now. (Market is too normal).")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}

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

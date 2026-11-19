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

async def fetch_bitget_1m_candles(session, symbol):
    # Fetch the last 15 1-minute candles
    params = {"symbol": symbol, "granularity": "1m", "limit": "15"}
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
    log.info(f"🛰️ Scanning Bitget (Step Counting Engine)... (Streak: {wins}/8 | Mode: {mode_text})")
    
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
        
        # 2. Fetch 1m Candles for Top 100 coins
        top_100 = valid_coins[:100]
        tasks = [fetch_bitget_1m_candles(session, coin["symbol"]) for coin in top_100]
        all_candles = await asyncio.gather(*tasks)
        
        top_signals = []

        for idx, candle_data in enumerate(all_candles):
            if not candle_data or len(candle_data) < 5:
                continue
                
            coin_info = top_100[idx]
            symbol = coin_info["symbol"]
            
            # Count steps (wicks) in the last 15 minutes
            up_steps = 0
            down_steps = 0
            total_15m_move_pct = 0.0
            
            # candle_data[0] is the most recent 1m candle
            # candle_data[-1] is the candle 15 minutes ago
            open_15m = float(candle_data[-1][1])
            close_15m = float(candle_data[0][4])
            
            if open_15m > 0:
                total_15m_move_pct = ((close_15m - open_15m) / open_15m) * 100

            for c in candle_data:
                o = float(c[1])
                cl = float(c[4])
                if cl > o:
                    up_steps += 1
                elif cl < o:
                    down_steps += 1
            
            # Determine direction and dominance ratio
            if up_steps == 0 and down_steps == 0:
                continue # Doji flat, skip
                
            if up_steps > down_steps:
                direction = "LONG"
                # Calculate how many times more up steps than down steps
                dominance_ratio = up_steps / down_steps if down_steps > 0 else up_steps
            elif down_steps > up_steps:
                direction = "SHORT"
                dominance_ratio = down_steps / up_steps if up_steps > 0 else down_steps
            else:
                continue # Perfect tie, skip
            
            # We want coins that actually moved in the 15m window
            if abs(total_15m_move_pct) < 0.1:
                continue
                
            # Score is the dominance ratio multiplied by the actual percentage move
            # This ensures a 6-to-2 step with 2% move beats a 6-to-2 step with 0.5% move
            score = dominance_ratio * abs(total_15m_move_pct)
            
            top_signals.append({
                "symbol": symbol,
                "direction": direction,
                "up_steps": up_steps,
                "down_steps": down_steps,
                "dominance_ratio": dominance_ratio,
                "change_15m": total_15m_move_pct,
                "vol_24h_usd": float(coin_info["quoteVolume"]),
                "score": score
            })
            
            top_signals.sort(key=lambda x: x["score"], reverse=True)
            if len(top_signals) > 3:
                top_signals.pop()

        scan_time = time.time() - start_time
        log.info(f"✅ Scan complete in {scan_time:.2f} seconds.")

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 BEST COINS (Step Dominance) ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['symbol']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  True Vol: ${sig['vol_24h_usd']:,.0f}")
                log.info(f"  [15M Data]  Price Change: {sig['change_15m']:+.2f}%")
                log.info(f"  [Steps]     {sig['up_steps']} UP steps vs {sig['down_steps']} DOWN steps")
                log.info(f"  [Dominance] {sig['dominance_ratio']:.2f}x stronger on the {sig['direction']} side")

            best_signal = top_signals[0]
            log.info(f"🎯 SELECTED BEST: {best_signal['symbol']} {best_signal['direction']}")
            payload = {"symbol": best_signal["symbol"], "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ Market is completely dead. No valid candles found.")
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

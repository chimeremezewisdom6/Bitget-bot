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

async def fetch_bitget_15m_candles(session, symbol):
    async with SEMAPHORE:
        params = {"symbol": symbol, "productType": "USDT-FUTURES", "granularity": "15m", "limit": "96"}
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
    
    # 🚨 1. CHECK IF TRADE IS ACTIVE 🚨
    if is_trade_active():
        log.info(f"⏳ Active trade in progress. Pinging Cloudflare to manage TP/SL... (Streak: {wins}/8)")
        payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}
    else:
        log.info(f"🛰️ Scanning Bitget (Blowout Engine)... (Streak: {wins}/8 | Mode: {mode_text})")
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
            
            tasks = [fetch_bitget_15m_candles(session, coin["symbol"]) for coin in top_200]
            all_candles = await asyncio.gather(*tasks)
            
            top_signals = []

            for idx, candle_data in enumerate(all_candles):
                if not candle_data or len(candle_data) < 90:
                    continue
                    
                coin_info = top_200[idx]
                symbol = coin_info["symbol"]
                current_candle = candle_data[0]
                
                # --- 15M DATA ---
                open_15m = float(current_candle[1])
                high_15m = float(current_candle[2])
                low_15m = float(current_candle[3])
                close_15m = float(current_candle[4])
                vol_15m = float(current_candle[5])
                
                # --- 24H DATA ---
                total_vol_24h = sum([float(c[5]) for c in candle_data])
                avg_vol_15m_baseline = total_vol_24h / 96.0
                vol_surge = vol_15m / avg_vol_15m_baseline if avg_vol_15m_baseline > 0 else 0
                
                candle_range = high_15m - low_15m
                candle_body = abs(close_15m - open_15m)
                
                if candle_range <= 0: continue
                body_ratio = candle_body / candle_range
                change_15m = ((close_15m - open_15m) / open_15m) * 100 if open_15m > 0 else 0
                
                # 🚨 FILTERS 🚨
                if abs(change_15m) < 0.5: continue
                if vol_surge < 1.0: continue
                if body_ratio < 0.60: continue # Must be a blowout candle
                    
                direction = "LONG" if change_15m > 0 else "SHORT"
                score = abs(change_15m) * body_ratio * vol_surge
                
                top_signals.append({
                    "symbol": symbol,
                    "direction": direction,
                    "net_profit": change_15m,
                    "body_ratio": body_ratio,
                    "vol_surge": vol_surge,
                    "vol_24h_usd": coin_info["vol_24h"],
                    "high_15m": high_15m,
                    "low_15m": low_15m,
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
                log.info(f"  [Blowout] {best_signal['net_profit']:+.2f}% move | Body Ratio: {best_signal['body_ratio']*100:.1f}%")
                # Pass the 15m high and low for dynamic SL/TP
                payload = {
                    "symbol": best_signal["symbol"], 
                    "direction": best_signal["direction"], 
                    "is_paper": is_paper,
                    "high_15m": best_signal["high_15m"],
                    "low_15m": best_signal["low_15m"]
                }
            else:
                log.warning("❌ No coins passed the Blowout Filter.")
                payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}

    # Send to Cloudflare Webhook
    headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "OPENED":
                    log.info(f"🟢 TRADE OPENED: {data['symbol']} {data['direction']} at {data['entry_price']}")
                    log.info(f"   [Take Profit] {data['take_profit']} | [Stop Loss] {data['stop_loss']}")
                elif data.get("status") == "HOLDING":
                    log.info(f"⏳ HOLDING: {data['symbol']} | PnL: {data['pnl_percent']}% | Peak PnL: {data['peak_pnl']}%")
                elif data.get("status") == "CLOSED":
                    emoji = "✅" if data["won"] else "❌"
                    log.info(f"{emoji} TRADE CLOSED: {data['symbol']}")
                    log.info(f"   [FINAL PnL] {data['pnl_percent']}% | [Peak PnL] {data['peak_pnl']}%")
                    log.info(f"   [Reason] {data['reason']} | [New Streak] {data['streak']}/8")

if __name__ == "__main__":
    asyncio.run(main())

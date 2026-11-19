import os
import time
import json
import asyncio
import logging
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("scanner")

API_KEYS_RAW = os.environ.get("COINALYZE_API_KEYS", "")
COINALYZE_KEYS = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]
CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

BASE_URL = "https://api." + "coinalyze" + ".net/v1"
STREAK_FILE = "streak.json"

def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                return json.load(f).get("wins", 0)
        except Exception:
            return 0
    return 0

async def fetch_coinalyze_batch(session, endpoint, params):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    for key in COINALYZE_KEYS:
        p = dict(params)
        p["api_key"] = key
        try:
            async with session.get(url, params=p, timeout=20) as r:
                if r.status == 200:
                    return await r.json()
                elif r.status == 429:
                    continue # Rotate to next key
        except Exception:
            continue
    return None

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    log.info(f"🛰️ Scanning Top 1000 (Coinalyze 30+ Exchange Aggregate)... (Streak: {wins}/8 | Mode: {mode_text})")
    
    now_ts = int(time.time())
    ts_24h_ago = now_ts - 86400
    
    async with aiohttp.ClientSession() as session:
        markets = await fetch_coinalyze_batch(session, "future-markets", {})
        if not markets:
            log.error("❌ Failed to fetch markets from Coinalyze.")
            return

        all_syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:1000]
        
        top_signals = []

        for i in range(0, len(all_syms), 50):
            chunk = all_syms[i:i+50]
            data_24h_15m = await fetch_coinalyze_batch(session, "ohlcv-history", {
                "symbols": ",".join(chunk), "interval": "15min", "from": ts_24h_ago, "to": now_ts
            })
            
            if not data_24h_15m:
                await asyncio.sleep(1.5) # Prevent rate limit
                continue
                
            for item in data_24h_15m:
                history = item.get("history", [])
                if len(history) < 90:
                    continue
                
                # --- 24H BASELINE ---
                open_24h = history[0]["o"]
                close_24h = history[-1]["c"]
                vol_24h = sum([c["v"] for c in history])
                
                # 24h Price Change %
                price_change_24h = ((close_24h - open_24h) / open_24h) * 100 if open_24h > 0 else 0
                
                # Average 15m volume over the last 24 hours
                avg_vol_15m_baseline = vol_24h / 96.0
                
                # Average 15m price range over the last 24 hours (Volatility)
                ranges_24h = [(c["h"] - c["l"]) / c["l"] for c in history if c["l"] > 0]
                avg_range_24h = sum(ranges_24h) / len(ranges_24h) if ranges_24h else 0.01

                # --- 15M CURRENT ACTION ---
                current_candle = history[-1]
                vol_15m = current_candle["v"]
                close_price = current_candle["c"]
                open_price = current_candle["o"]
                
                # 15m Price Change %
                price_change_15m = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
                
                # --- CALCULATE IMBALANCE (SCORE) ---
                # How much bigger is the 15m volume compared to the 24h average?
                vol_surge = vol_15m / avg_vol_15m_baseline if avg_vol_15m_baseline > 0 else 0
                
                # How much bigger is the 15m price move compared to the normal 15m move?
                move_multiplier = (price_change_15m / 100) / avg_range_24h if avg_range_24h > 0 else 0
                
                score = abs(move_multiplier) * vol_surge
                
                if score > 0:
                    direction = "LONG" if price_change_15m > 0 else "SHORT"
                    clean_sym = item["symbol"].split("_")[0].replace("USD", "")
                    
                    top_signals.append({
                        "raw_symbol": item["symbol"],
                        "clean_sym": clean_sym,
                        "direction": direction, 
                        "score": score,
                        "move_mult": move_multiplier,
                        "vol_surge": vol_surge,
                        "vol_24h": vol_24h,
                        "vol_15m": vol_15m,
                        "change_24h": price_change_24h,
                        "change_15m": price_change_15m
                    })
                    
                    # Sort and keep only the top 3
                    top_signals.sort(key=lambda x: x["score"], reverse=True)
                    if len(top_signals) > 3:
                        top_signals.pop()
            
            await asyncio.sleep(1.5) # Prevent rate limit

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 PAIRS WITH HIGHEST IMBALANCE (Weak Side Detected) ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['clean_sym']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  Volume: {sig['vol_24h']:,.0f} | Price Change: {sig['change_24h']:+.2f}%")
                log.info(f"  [15M Data]  Volume: {sig['vol_15m']:,.0f} | Price Change: {sig['change_15m']:+.2f}%")
                log.info(f"  [Imbalance] 15M Volume is {sig['vol_surge']:.1f}x normal | 15M Move is {sig['move_mult']:.1f}x normal")
                log.info(f"  => Takers are aggressively pushing {sig['direction']} while passive limit orders are overwhelmed.")

            best_signal = top_signals[0]
            raw_sym = best_signal["raw_symbol"].split("_")[0]
            sym = raw_sym + "T" if raw_sym.endswith("USD") else raw_sym
            
            log.info(f"🎯 SELECTED BEST: {sym} {best_signal['direction']}")
            payload = {"symbol": sym, "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ Failed to gather enough data. (Check API limits).")
            payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}

        # Send to Cloudflare
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
                elif data.get("status") == "WAITING":
                    log.info(f"⏳ WAITING: {data['message']}")
            else:
                log.error(f"❌ Cloudflare failed: {await resp.text()}")

if __name__ == "__main__":
    asyncio.run(main())

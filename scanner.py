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
                    log.warning("API Limit hit, rotating key...")
                    continue
        except Exception as e:
            log.error(f"Fetch error: {e}")
            continue
    return None

async def main():
    if not CLOUDFLARE_URL:
        log.error("CLOUDFLARE_URL is not set.")
        return

    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER TRADING" if is_paper else "💵 REAL MONEY"
    log.info(f"🛰️ Scanning Top 1000... (Streak: {wins}/8 | Mode: {mode_text})")
    
    now_ts = int(time.time())
    ts_24h_ago = now_ts - 86400
    ts_1h_ago = now_ts - 3600
    
    async with aiohttp.ClientSession() as session:
        markets = await fetch_coinalyze_batch(session, "future-markets", {})
        if not markets:
            log.error("Failed to fetch markets.")
            return

        # Filter for USDT perpetuals and take the top 1000
        all_syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:1000]
        
        best_signal = None
        highest_conviction = 0

        # Process in chunks of 50 to respect API limits
        for i in range(0, len(all_syms), 50):
            chunk = all_syms[i:i+50]
            sym_str = ",".join(chunk)
            
            # Fetch 24h data (1h interval) and 15m data
            data_24h = await fetch_coinalyze_batch(session, "ohlcv-history", {
                "symbols": sym_str, "interval": "1hour", "from": ts_24h_ago, "to": now_ts
            })
            data_15m = await fetch_coinalyze_batch(session, "ohlcv-history", {
                "symbols": sym_str, "interval": "15min", "from": ts_1h_ago, "to": now_ts
            })
            
            if not data_24h or not data_15m:
                continue
                
            dict_24h = {item["symbol"]: item.get("history", []) for item in data_24h}
            dict_15m = {item["symbol"]: item.get("history", []) for item in data_15m}

            for sym in chunk:
                hist_24h = dict_24h.get(sym, [])
                hist_15m = dict_15m.get(sym, [])
                
                if len(hist_24h) < 10 or len(hist_15m) < 3:
                    continue
                
                # --- 24H BASELINE ---
                vol_24h = sum([c["v"] for c in hist_24h])
                avg_vol_15m_baseline = vol_24h / 96.0 # 96 15-minute periods in 24 hours
                
                # Calculate 24h average range (Volatility Normalization)
                ranges_24h = [(c["h"] - c["l"]) / c["l"] for c in hist_24h if c["l"] > 0]
                avg_range_24h = sum(ranges_24h) / len(ranges_24h) if ranges_24h else 0.01

                # --- 15M CURRENT ACTION ---
                current_candle = hist_15m[-1]
                vol_15m = current_candle["v"]
                close_price = current_candle["c"]
                open_price = current_candle["o"]
                
                # 15m Percentage Change
                price_change_15m = (close_price - open_price) / open_price if open_price > 0 else 0
                
                # --- TAKER DOMINANCE LOGIC ---
                # Volume Spike: Current 15m volume is at least 3x the 24h average
                volume_surge = vol_15m > (avg_vol_15m_baseline * 3.0)
                
                if volume_surge:
                    # Normalize the 15m percentage change against the 24h average range
                    normalized_move = price_change_15m / avg_range_24h if avg_range_24h > 0 else 0
                    
                    # Takers buying aggressively (overwhelming limit sellers)
                    if normalized_move > 1.5:
                        conviction = abs(normalized_move)
                        if conviction > highest_conviction:
                            highest_conviction = conviction
                            best_signal = {"symbol": sym, "direction": "LONG", "conviction": conviction}
                            
                    # Takers selling aggressively (overwhelming limit buyers)
                    elif normalized_move < -1.5:
                        conviction = abs(normalized_move)
                        if conviction > highest_conviction:
                            highest_conviction = conviction
                            best_signal = {"symbol": sym, "direction": "SHORT", "conviction": conviction}

        # 3. Execute the strongest signal
        if best_signal:
            raw_sym = best_signal["symbol"].split("_")[0]
            sym = raw_sym + "T" if raw_sym.endswith("USD") else raw_sym
            
            log.info(f"🎯 Found Taker Dominance! {best_signal['direction']} on {sym} (Conviction: {best_signal['conviction']:.2f})")
            
            payload = {"symbol": sym, "direction": best_signal["direction"], "is_paper": is_paper}
            headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
            
            async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    log.info(f"✅ Cloudflare executed {mode_text} {best_signal['direction']} trade for {sym}!")
                else:
                    err = await resp.text()
                    log.error(f"❌ Cloudflare failed: {err}")
        else:
            log.info("⏳ No taker dominance found. Waiting for next scan.")

if __name__ == "__main__":
    asyncio.run(main())

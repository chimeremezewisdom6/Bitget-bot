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

class KeyManager:
    def __init__(self, keys):
        self.keys = keys
        self.key_index = 0

    def get_key(self):
        if not self.keys: return ""
        key = self.keys[self.key_index]
        self.key_index = (self.key_index + 1) % len(self.keys)
        return key

key_manager = KeyManager(COINALYZE_KEYS)

def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                return json.load(f).get("wins", 0)
        except Exception:
            return 0
    return 0

async def fetch_coinalyze_safe(session, target_url):
    for attempt in range(3):
        api_key = key_manager.get_key()
        try:
            async with session.get(target_url, params={"api_key": api_key}, timeout=10) as r:
                if r.status == 200:
                    return await r.json()
                elif r.status == 429:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    return None
        except Exception:
            await asyncio.sleep(0.5)
            continue
    return None

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    log.info(f"🛰️ Scanning Top 1000 (Strict Filter Mode)... (Streak: {wins}/8 | Mode: {mode_text})")
    
    start_time = time.time()
    now_ts = int(time.time())
    ts_24h_ago = now_ts - 86400
    
    async with aiohttp.ClientSession() as session:
        markets_url = f"{BASE_URL}/future-markets"
        markets = await fetch_coinalyze_safe(session, markets_url)
        
        if not markets or not isinstance(markets, list):
            log.error("❌ Failed to fetch markets.")
            return

        all_syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:1000]
        chunks = [all_syms[i:i+20] for i in range(0, len(all_syms), 20)]
        
        log.info(f"⚡ Processing {len(chunks)} chunks with strict filters (Vol > $1M, Move > 1%)...")

        results = []
        for chunk in chunks:
            sym_str = ",".join(chunk)
            target_url = f"{BASE_URL}/ohlcv-history?symbols={sym_str}&interval=15min&from={ts_24h_ago}&to={now_ts}"
            data = await fetch_coinalyze_safe(session, target_url)
            if data and isinstance(data, list):
                results.extend(data)
            await asyncio.sleep(0.2) # Safe delay

        scan_time = time.time() - start_time
        log.info(f"✅ Data gathered in {scan_time:.2f} seconds.")

        top_signals = []

        for item in results:
            history = item.get("history", [])
            if len(history) < 90:
                continue
            
            # --- 24H BASELINE ---
            open_24h = history[0]["o"]
            close_24h = history[-1]["c"]
            vol_24h = sum([c["v"] for c in history])
            price_change_24h = ((close_24h - open_24h) / open_24h) * 100 if open_24h > 0 else 0
            avg_vol_15m_baseline = vol_24h / 96.0
            ranges_24h = [(c["h"] - c["l"]) / c["l"] for c in history if c["l"] > 0]
            avg_range_24h = sum(ranges_24h) / len(ranges_24h) if ranges_24h else 0.01

            # --- 15M CURRENT ACTION ---
            current_candle = history[-1]
            vol_15m = current_candle["v"]
            close_price = current_candle["c"]
            open_price = current_candle["o"]
            price_change_15m = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
            
            # --- CALCULATE METRICS ---
            vol_surge = vol_15m / avg_vol_15m_baseline if avg_vol_15m_baseline > 0 else 0
            move_multiplier = (price_change_15m / 100) / avg_range_24h if avg_range_24h > 0 else 0
            
            # ==========================================
            # 🚨 HARD FILTERS (REJECT WEAK COINS) 🚨
            # ==========================================
            # 1. Reject if 24h volume is under 1,000,000
            if vol_24h < 1000000:
                continue
            
            # 2. Reject if 15m price change is less than 1.0%
            if abs(price_change_15m) < 1.0:
                continue
                
            # 3. Reject if volume surge is less than 2.0x normal
            if vol_surge < 2.0:
                continue

            # If it passes all filters, calculate score
            score = abs(price_change_15m) * vol_surge
            
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
            
            top_signals.sort(key=lambda x: x["score"], reverse=True)
            if len(top_signals) > 3:
                top_signals.pop()

        # --- SHOW THE DETAILED BREAKDOWN ---
        if top_signals:
            log.info("🏆 --- TOP 3 PAIRS THAT PASSED THE FILTERS ---")
            for idx, sig in enumerate(top_signals):
                log.info(f"--- RANK {idx+1}: {sig['clean_sym']} ({sig['direction']}) | Score: {sig['score']:.2f} ---")
                log.info(f"  [24H Data]  Volume: {sig['vol_24h']:,.0f} | Price Change: {sig['change_24h']:+.2f}%")
                log.info(f"  [15M Data]  Volume: {sig['vol_15m']:,.0f} | Price Change: {sig['change_15m']:+.2f}%")
                log.info(f"  [Imbalance] 15M Volume is {sig['vol_surge']:.1f}x normal | 15M Move is {sig['move_mult']:.1f}x normal")
                log.info(f"  => Takers are aggressively pushing {sig['direction']}!")

            best_signal = top_signals[0]
            raw_sym = best_signal["raw_symbol"].split("_")[0]
            sym = raw_sym + "T" if raw_sym.endswith("USD") else raw_sym
            
            log.info(f"🎯 SELECTED BEST: {sym} {best_signal['direction']}")
            payload = {"symbol": sym, "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            log.warning("❌ No coins passed the strict filters this scan (Vol > $1M, Move > 1%). Waiting...")
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

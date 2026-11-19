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
                    continue
        except Exception:
            continue
    return None

async def main():
    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER" if is_paper else "💵 LIVE"
    log.info(f"🛰️ Scanning... (Streak: {wins}/8 | Mode: {mode_text})")
    
    now_ts = int(time.time())
    ts_24h_ago = now_ts - 86400
    
    async with aiohttp.ClientSession() as session:
        markets = await fetch_coinalyze_batch(session, "future-markets", {})
        if not markets:
            return

        all_syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:1000]
        best_signal = None
        highest_score = 0

        for i in range(0, len(all_syms), 50):
            chunk = all_syms[i:i+50]
            data_24h_15m = await fetch_coinalyze_batch(session, "ohlcv-history", {
                "symbols": ",".join(chunk), "interval": "15min", "from": ts_24h_ago, "to": now_ts
            })
            
            if not data_24h_15m:
                continue
                
            for item in data_24h_15m:
                history = item.get("history", [])
                if len(history) < 90:
                    continue
                
                vol_24h = sum([c["v"] for c in history])
                avg_vol_15m_baseline = vol_24h / 96.0
                ranges_24h = [(c["h"] - c["l"]) / c["l"] for c in history if c["l"] > 0]
                avg_range_24h = sum(ranges_24h) / len(ranges_24h) if ranges_24h else 0.01

                current_candle = history[-1]
                vol_15m = current_candle["v"]
                close_price = current_candle["c"]
                open_price = current_candle["o"]
                
                price_change_15m = (close_price - open_price) / open_price if open_price > 0 else 0
                volume_surge = vol_15m > (avg_vol_15m_baseline * 2.5) 
                
                if volume_surge:
                    normalized_move = price_change_15m / avg_range_24h if avg_range_24h > 0 else 0
                    if abs(normalized_move) > 1.5:
                        vol_multiplier = vol_15m / avg_vol_15m_baseline
                        score = abs(normalized_move) * vol_multiplier
                        direction = "LONG" if normalized_move > 0 else "SHORT"
                        
                        if score > highest_score:
                            highest_score = score
                            best_signal = {"symbol": item["symbol"], "direction": direction, "score": score}

        # Send to Cloudflare
        if best_signal:
            raw_sym = best_signal["symbol"].split("_")[0]
            sym = raw_sym + "T" if raw_sym.endswith("USD") else raw_sym
            payload = {"symbol": sym, "direction": best_signal["direction"], "is_paper": is_paper}
        else:
            payload = {"symbol": "NONE", "direction": "NONE", "is_paper": is_paper}

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

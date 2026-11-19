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

async def fetch_coinalyze(session, endpoint, params):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    for key in COINALYZE_KEYS:
        p = dict(params)
        p["api_key"] = key
        try:
            async with session.get(url, params=p, timeout=15) as r:
                if r.status == 200:
                    return await r.json()
                elif r.status == 429:
                    continue
        except Exception:
            continue
    return None

async def main():
    if not CLOUDFLARE_URL:
        log.error("CLOUDFLARE_URL is not set.")
        return

    wins = get_win_streak()
    is_paper = wins < 8
    mode_text = "📝 PAPER TRADING" if is_paper else "💵 REAL MONEY"
    log.info(f"🛰️ Scanning... (Streak: {wins}/8 | Mode: {mode_text})")
    
    now_ts = int(time.time())
    frm_ts = now_ts - 3600 
    
    async with aiohttp.ClientSession() as session:
        markets = await fetch_coinalyze(session, "future-markets", {})
        if not markets:
            return

        syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:20]
        data = await fetch_coinalyze(session, "ohlcv-history", {
            "symbols": ",".join(syms), "interval": "5min", "from": frm_ts, "to": now_ts
        })
        
        if data:
            for item in data:
                closes = [c["c"] for c in (item.get("history") or [])]
                if len(closes) < 5: 
                    continue
                
                if closes[-1] > closes[-3]:
                    raw_sym = item["symbol"].split("_")[0]
                    sym = raw_sym + "T" if raw_sym.endswith("USD") else raw_sym
                    
                    payload = {"symbol": sym, "direction": "LONG", "is_paper": is_paper}
                    headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
                    
                    async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            log.info(f"✅ Cloudflare executed {mode_text} trade for {sym}!")
                            return
                        else:
                            err = await resp.text()
                            log.error(f"❌ Cloudflare failed: {err}")

if __name__ == "__main__":
    asyncio.run(main())

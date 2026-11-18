import os
import time
import asyncio
import logging
import threading
import aiohttp
import numpy as np
import gradio as gr

os.environ["GRADIO_SSR_MODE"] = "False"
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("hf_scanner")

API_KEYS_RAW = os.environ.get("COINALYZE_API_KEYS", "")
COINALYZE_KEYS = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]
CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

BASE_URL = "https://api." + "coinalyze" + ".net/v1"

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
                    log.warning("⚠️ Key hit limit, rotating to next key...")
                    continue
        except Exception as e:
            log.error(f"Fetch error: {e}")
            continue
    return None

async def background_loop():
    while True:
        try:
            if not CLOUDFLARE_URL:
                await asyncio.sleep(10)
                continue

            log.info("🛰️ Scanning...")
            now_ts = int(time.time())
            frm_ts = now_ts - 3600 
            
            async with aiohttp.ClientSession() as session:
                markets = await fetch_coinalyze(session, "future-markets", {})
                if markets:
                    syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:20]
                    data = await fetch_coinalyze(session, "ohlcv-history", {
                        "symbols": ",".join(syms), "interval": "5min", "from": frm_ts, "to": now_ts
                    })
                    
                    if data:
                        for item in data:
                            closes = [c["c"] for c in (item.get("history") or [])]
                            if len(closes) < 5: continue
                            
                            # Simple test: If price is going up, send LONG
                            if closes[-1] > closes[-3]:
                                sym = item["symbol"].replace("USDT_PERP.A", "USDT")
                                log.info(f"🎯 Signal for {sym}. Sending to Cloudflare...")
                                
                                payload = {"symbol": sym, "direction": "LONG"}
                                headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
                                
                                async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
                                    if resp.status == 200:
                                        log.info("✅ Cloudflare executed the trade!")
                                        break 
                                    else:
                                        log.error(f"❌ Cloudflare rejected: {await resp.text()}")
            
            await asyncio.sleep(300)
        except Exception as e:
            log.error(f"Loop error: {e}")
            await asyncio.sleep(60)

with gr.Blocks(title="HF Scanner") as demo:
    gr.Markdown("# 🧠 Hugging Face Scanner")

def start_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(background_loop())

if __name__ == "__main__":
    threading.Thread(target=start_loop, daemon=True).start()
    demo.launch(server_name="0.0.0.0", server_port=7860)

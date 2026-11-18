import os
import time
import json
import asyncio
import logging
import threading
import aiohttp
import gradio as gr
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

os.environ["GRADIO_SSR_MODE"] = "False"
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("hf_scanner")

# --- ENVIRONMENT CONFIGURATION ---
API_KEYS_RAW = os.environ.get("COINALYZE_API_KEYS", "")
COINALYZE_KEYS = [k.strip() for k in API_KEYS_RAW.split(",") if k.strip()]
CLOUDFLARE_URL = os.environ.get("CLOUDFLARE_URL", "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

BASE_URL = "https://api." + "coinalyze" + ".net/v1"
STREAK_FILE = "streak.json"

# --- WIN STREAK LOGIC ---
def get_win_streak():
    if os.path.exists(STREAK_FILE):
        try:
            with open(STREAK_FILE, "r") as f:
                return json.load(f).get("wins", 0)
        except Exception:
            return 0
    return 0

def update_win_streak(won):
    current = get_win_streak()
    new_streak = current + 1 if won else 0
    with open(STREAK_FILE, "w") as f:
        json.dump({"wins": new_streak}, f)
    return new_streak

# --- COINALYZE FETCH (With Key Rotation) ---
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
                    log.warning(f"⚠️ Key hit limit, rotating to next key...")
                    continue
        except Exception as e:
            log.error(f"Fetch error: {e}")
            continue
    return None

# --- SCANNER LOOP ---
async def background_loop():
    while True:
        try:
            if not CLOUDFLARE_URL:
                await asyncio.sleep(10)
                continue

            wins = get_win_streak()
            is_paper = wins < 8
            mode_text = "📝 PAPER TRADING" if is_paper else "💵 REAL MONEY"
            log.info(f"🛰️ Scanning... (Current Streak: {wins}/8 | Mode: {mode_text})")
            
            now_ts = int(time.time())
            frm_ts = now_ts - 3600 # 1 hour lookback
            
            async with aiohttp.ClientSession() as session:
                markets = await fetch_coinalyze(session, "future-markets", {})
                if markets:
                    # Get top 20 coins
                    syms = [m["symbol"] for m in markets if m.get("symbol", "").endswith("_PERP.A")][:20]
                    data = await fetch_coinalyze(session, "ohlcv-history", {
                        "symbols": ",".join(syms), "interval": "5min", "from": frm_ts, "to": now_ts
                    })
                    
                    if data:
                        for item in data:
                            closes = [c["c"] for c in (item.get("history") or [])]
                            if len(closes) < 5: 
                                continue
                            
                            # Simple test strategy: If price is going up, LONG
                            if closes[-1] > closes[-3]:
                                # Format symbol for Bitget UTA (e.g., ADAUSD_PERP.A -> ADAUSDT)
                                raw_sym = item["symbol"].split("_")[0]
                                if raw_sym.endswith("USD"):
                                    sym = raw_sym + "T"
                                else:
                                    sym = raw_sym
                                
                                payload = {
                                    "symbol": sym, 
                                    "direction": "LONG",
                                    "is_paper": is_paper
                                }
                                headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
                                
                                async with session.post(CLOUDFLARE_URL, json=payload, headers=headers) as resp:
                                    if resp.status == 200:
                                        log.info(f"✅ Cloudflare executed {mode_text} trade for {sym}!")
                                        break
                                    else:
                                        err = await resp.text()
                                        log.error(f"❌ Cloudflare failed: {err}")

        except Exception as e:
            log.error(f"Loop error: {e}")
            
        await asyncio.sleep(300) # Wait 5 minutes before next scan

# --- GRADIO UI & FASTAPI ---
with gr.Blocks(title="HF Scanner") as demo:
    gr.Markdown("# 🧠 Hugging Face Scanner")
    gr.Markdown("Running on Hugging Face. Sends signals to Cloudflare.")

api = FastAPI()

# Cloudflare sends the win/loss result here to update the streak
@api.post("/trade_result")
async def trade_result(request: Request):
    auth = request.headers.get("X-Webhook-Secret")
    if auth != WEBHOOK_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    data = await request.json()
    won = data.get("won", False)
    new_streak = update_win_streak(won)
    log.info(f"📊 Trade closed. Won: {won}. New Streak: {new_streak}/8")
    return JSONResponse({"status": "ok", "streak": new_streak})

# Mount Gradio app to FastAPI
app = gr.mount_gradio_app(api, demo, path="/")

# Start background scanner loop
def start_background_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(background_loop())

if __name__ == "__main__":
    threading.Thread(target=start_background_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=7860)

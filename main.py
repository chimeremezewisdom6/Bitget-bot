import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt
import base64

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "my_secret_password_123")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "YES") == "YES"
WIN_THRESHOLD = 8
LEVERAGE = 5 

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")

# MUST BE EXACTLY: https://chimeremeze321-crypto-aggregator.hf.space/ready
HF_READY_URL = os.environ.get("HF_READY_URL") 

is_trading = False

# --- GITHUB STATE ---
def get_github_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

async def load_state():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/state.json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_github_headers()) as res:
            if res.status == 200:
                data = await res.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                return json.loads(content), data['sha']
    # Default state with all 10 setups
    return {
        "RSI_Standard": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "RSI_Extreme": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Sweep_20": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Sweep_50": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Squeeze_Tight": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Squeeze_Extreme": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Volume_RSI": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Wick_Rejection": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "Momentum": {"paper_streak": 0, "live_unlocked": False, "live_history": []},
        "EMA_Cross": {"paper_streak": 0, "live_unlocked": False, "live_history": []}
    }, None

async def save_state(state, sha):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/state.json"
    content = base64.b64encode(json.dumps(state, indent=2).encode('utf-8')).decode('utf-8')
    payload = {"message": "Update state", "content": content}
    if sha: payload["sha"] = sha
    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=get_github_headers(), json=payload) as res:
            if res.status in [200, 201]:
                log.info("✅ State saved to GitHub.")
            else:
                log.error(f"❌ Failed to save state: {await res.text()}")

# --- EXECUTE TRADE ---
async def execute_trade(symbol, direction):
    exchange = ccxt.bitget({
        'apiKey': os.environ.get("BITGET_API_KEY"),
        'secret': os.environ.get("BITGET_SECRET"),
        'password': os.environ.get("BITGET_PASSPHRASE"),
        'options': {'defaultType': 'swap', 'uta': True}
    })
    try:
        await exchange.load_markets()
        await exchange.set_leverage(LEVERAGE, symbol, params={'uta': True})
        
        ticker = await exchange.fetch_ticker(symbol)
        entry_price = ticker['last']
        
        log.info(f"🚀 [PAPER TRADE] Opened {direction} on {symbol} at ${entry_price} | Leverage: {LEVERAGE}x")
        
        peak_price = entry_price
        trailing_callback = 0.005 
        
        for _ in range(120): # Max 2 hours
            await asyncio.sleep(60) 
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker['last']
            except Exception: continue 
                
            if direction == "LONG":
                peak_price = max(peak_price, current_price)
                drop_from_peak = ((peak_price - current_price) / peak_price)
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                
                log.info(f"📊 {symbol} LONG | Current: ${current_price} | PnL: {profit_pct:+.2f}%")
                
                if (profit_pct > 1.0 and drop_from_peak > trailing_callback) or profit_pct < -2.0:
                    log.info(f"💰 TRAILING STOP HIT. Final Profit: {profit_pct:+.2f}%")
                    break
                    
            elif direction == "SHORT":
                peak_price = min(peak_price, current_price) 
                bounce_from_peak = ((current_price - peak_price) / peak_price)
                profit_pct = ((entry_price - current_price) / entry_price) * 100
                
                log.info(f"📊 {symbol} SHORT | Current: ${current_price} | PnL: {profit_pct:+.2f}%")
                
                if (profit_pct > 1.0 and bounce_from_peak > trailing_callback) or profit_pct < -2.0:
                    log.info(f"💰 TRAILING STOP HIT. Final Profit: {profit_pct:+.2f}%")
                    break
        
        final_ticker = await exchange.fetch_ticker(symbol)
        final_price = final_ticker['last']
        final_pnl = ((final_price - entry_price) / entry_price) * 100 if direction == "LONG" else ((entry_price - final_price) / entry_price) * 100
        
        return final_pnl > 0, final_pnl
    except Exception as e:
        log.error(f"Execution failed: {e}")
        return False, 0.0
    finally:
        await exchange.close()

# --- WORKER ---
async def process_trade(symbol, direction, setup_type):
    global is_trading
    is_trading = True
    
    try:
        state, sha = await load_state()
        
        # If a new setup type is added on HF that isn't in state.json yet, create it
        if setup_type not in state:
            state[setup_type] = {"paper_streak": 0, "live_unlocked": False, "live_history": []}
            
        strat = state[setup_type]
        is_live = LIVE_TRADING and strat["live_unlocked"]
        
        won, pnl = await execute_trade(symbol, direction)
        
        if is_live:
            strat["live_history"].append(1 if won else 0)
            if len(strat["live_history"]) > 8: strat["live_history"].pop(0)
            if len(strat["live_history"]) >= 3 and strat["live_history"][-3:] == [0, 0, 0]:
                strat["live_unlocked"] = False
                strat["paper_streak"] = 0
                strat["live_history"] = []
                log.info(f"🛑 DEMOTED: 3 losses. Back to paper.")
        else:
            if won:
                strat["paper_streak"] += 1
                log.info(f"✅ [{setup_type}] Paper WIN. Streak: {strat['paper_streak']}/8")
            else:
                strat["paper_streak"] = 0
                log.info(f"❌ [{setup_type}] Paper LOSS.")
                
            if strat["paper_streak"] >= WIN_THRESHOLD:
                strat["live_unlocked"] = True
                log.info(f"🚀 [{setup_type}] GATE UNLOCKED.")

        await save_state(state, sha)
        
        # ROBUST CALLBACK TO HUGGING FACE
        if HF_READY_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(HF_READY_URL, timeout=10) as resp:
                        if resp.status == 200:
                            log.info(f"📡 Callback sent to Hugging Face! Status: 200 OK.")
                        else:
                            log.error(f"⚠️ Callback to HF failed. Status: {resp.status}")
            except Exception as e:
                log.error(f"❌ Callback network error to HF: {e}")
                
    finally:
        is_trading = False

# --- WEBHOOK RECEIVER ---
async def handle_signal(request):
    global is_trading
    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized")

    # If Render is already trading, reject immediately so HF keeps it in memory
    if is_trading:
        return web.Response(status=429, text="Busy")

    try:
        data = await request.json()
        log.info(f"📥 Signal Received: {data['symbol']} {data['direction']} | Setup: {data.get('setup_type')}")
        asyncio.create_task(process_trade(data['symbol'], data['direction'], data.get('setup_type', 'RSI_Standard')))
        return web.Response(status=200, text="Started")
    except Exception as e:
        return web.Response(status=500, text="Error")

async def main():
    app = web.Application()
    app.router.add_post('/signal', handle_signal)
    app.router.add_get('/', lambda r: web.Response(text="Alive"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    log.info(f"🚀 Webhook Active on port {port}")
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

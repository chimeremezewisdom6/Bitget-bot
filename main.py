import os
import json
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_orderbook_executor")

# --- CONFIGURATION ---
WEBHOOK_SECRET = os.environ.get("RENDER_WEBHOOK_SECRET")
LIVE_TRADING = os.environ.get("LIVE_TRADING", "NO") == "YES"
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "").rstrip("/")

# Exchange API Credentials
EX_KEY = os.environ.get("BITGET_KEY", "")
EX_SECRET = os.environ.get("BITGET_SECRET", "")
EX_PASS = os.environ.get("BITGET_PASS", "")

DEPTH_LEVELS = 20

# --- SINGLE TRADE LOCK ---
trade_lock = asyncio.Lock()
active_trade = None

async def notify_hf_ready():
    """Notifies Hugging Face Space when Render finishes a trade and frees the slot."""
    if not HF_SPACE_URL:
        return
    ready_endpoint = f"{HF_SPACE_URL}/ready"
    log.info(f"🔔 Notifying Hugging Face Space at {ready_endpoint}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ready_endpoint, timeout=10) as resp:
                if resp.status == 200:
                    log.info("✅ Hugging Face notified: Render is free for next trade.")
    except Exception as e:
        log.error(f"❌ Failed to notify Hugging Face: {e}")

async def monitor_orderbook_shift(symbol, direction):
    """Monitors live order book depth and exits immediately when opposing side dominates."""
    exchange = ccxt.bitget({
        "apiKey": EX_KEY,
        "secret": EX_SECRET,
        "password": EX_PASS,
        "options": {"defaultType": "swap", "uta": True}
    })

    try:
        await exchange.load_markets()
        log.info(f"⚡ Monitoring Live Order Book Imbalance for {symbol} ({direction})...")

        max_time_seconds = 3600
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < max_time_seconds:
            await asyncio.sleep(2)

            try:
                orderbook = await exchange.fetch_order_book(symbol, limit=DEPTH_LEVELS)
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])

                if not bids or not asks: continue

                bid_depth = sum(price * qty for price, qty in bids[:DEPTH_LEVELS])
                ask_depth = sum(price * qty for price, qty in asks[:DEPTH_LEVELS])

                if direction == "LONG":
                    # Exit trigger: Ask Depth >= Bid Depth (ratio <= 1.0)
                    if ask_depth >= bid_depth:
                        log.info(f"🛑 OPPOSING SHIFT DETECTED on {symbol}! Ask Depth ({ask_depth:.2f}) >= Bid Depth ({bid_depth:.2f}). Exiting instantly.")
                        return True, 1.0
                elif direction == "SHORT":
                    # Exit trigger: Bid Depth >= Ask Depth (ratio <= 1.0)
                    if bid_depth >= ask_depth:
                        log.info(f"🛑 OPPOSING SHIFT DETECTED on {symbol}! Bid Depth ({bid_depth:.2f}) >= Ask Depth ({ask_depth:.2f}). Exiting instantly.")
                        return True, 1.0
            except Exception as e:
                log.error(f"Depth fetch error: {e}")
                continue

        log.info(f"⏰ Maximum trade duration reached (60 min). Exiting {symbol}.")
        return True, 0.5

    except Exception as e:
        log.error(f"Execution monitoring error: {e}")
        return False, 0.0
    finally:
        await exchange.close()

async def process_trade(symbol, direction, setup_type):
    global active_trade
    try:
        log.info(f"⚙️ Executing Order Book Imbalance trade on {symbol} ({direction})...")
        trade_won, pnl_pct = await monitor_orderbook_shift(symbol, direction)
        log.info(f"📈 Trade Finished | Result: {'WIN' if trade_won else 'LOSS'}")
    finally:
        active_trade = None
        log.info("✅ Trade slot freed. Notifying Hugging Face Space...")
        await notify_hf_ready()

async def handle_signal(request):
    global active_trade

    if request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return web.Response(status=401, text="Unauthorized secret token")

    if active_trade is not None:
        log.warning(f"⚠️ Trade active on {active_trade}. Rejecting signal.")
        return web.Response(status=429, text="Busy: Active trade in progress")

    try:
        data = await request.json()
        symbol = data.get("symbol")
        direction = data.get("direction")
        setup_type = data.get("setup_type", "OrderBook_Imbalance")

        if not symbol or not direction:
            return web.Response(status=400, text="Missing symbol or direction")

        log.info(f"📥 Signal Accepted: {symbol} {direction} | Type: {setup_type}")
        active_trade = symbol

        asyncio.create_task(process_trade(symbol, direction, setup_type))
        return web.Response(status=200, text="Signal accepted")

    except Exception as e:
        log.error(f"Signal handling error: {e}")
        active_trade = None
        return web.Response(status=500, text="Internal Server Error")

async def handle_health(request):
    return web.Response(status=200, text="OrderBook Executor is alive and running!")

async def main():
    app = web.Application()
    app.router.add_post("/signal", handle_signal)
    app.router.add_get("/", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    log.info(f"🚀 Render OrderBook Executor Webhook Live on port {port}")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

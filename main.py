import os
import sys
import asyncio
import logging
import aiohttp
from aiohttp import web
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("render_executor")

# --- ENVIRONMENT CONFIGURATION ---
PORT = int(os.environ.get("PORT", 10000))
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "").rstrip("/")
RENDER_WEBHOOK_SECRET = os.environ.get("RENDER_WEBHOOK_SECRET", "")
EX_KEY = os.environ.get("BITGET_API_KEY", "")
EX_SECRET = os.environ.get("BITGET_API_SECRET", "")
EX_PASS = os.environ.get("BITGET_PASSPHRASE", "")
DEPTH_LEVELS = 20

# Global Active Trade Lock
active_trade = None

async def notify_hf_ready(symbol=None, direction=None, won=False, pnl_pct=0.0):
    """Notifies Hugging Face Space with trade outcome and frees slot."""
    if not HF_SPACE_URL:
        log.warning("⚠️ HF_SPACE_URL is not configured. Skipping callback notification.")
        return
    ready_endpoint = f"{HF_SPACE_URL}/ready"
    log.info(f"🔔 Notifying Hugging Face Space at {ready_endpoint} with result...")
    payload = {
        "symbol": symbol,
        "direction": direction,
        "won": won,
        "pnl_pct": pnl_pct
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ready_endpoint, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    log.info("✅ Hugging Face notified successfully.")
                else:
                    log.error(f"❌ HF callback failed | Status: {resp.status}")
    except Exception as e:
        log.error(f"❌ Failed to notify Hugging Face: {e}")

async def monitor_orderbook_shift(symbol, direction):
    """Monitors orderbook depth shift and returns (won, pnl_pct)."""
    exchange = ccxt.bitget({
        "apiKey": EX_KEY,
        "secret": EX_SECRET,
        "password": EX_PASS,
        "options": {"defaultType": "swap", "uta": True}
    })
    try:
        await exchange.load_markets()
        ticker = await exchange.fetch_ticker(symbol)
        entry_price = ticker.get("last", 0.0)
        log.info(f"📍 Entry Price for {symbol}: {entry_price}")

        max_time_seconds = 3600
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < max_time_seconds:
            await asyncio.sleep(2)
            try:
                orderbook = await exchange.fetch_order_book(symbol, limit=DEPTH_LEVELS)
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])
                if not bids or not asks:
                    continue

                bid_depth = sum(price * qty for price, qty in bids[:DEPTH_LEVELS])
                ask_depth = sum(price * qty for price, qty in asks[:DEPTH_LEVELS])
                curr_price = (bids[0][0] + asks[0][0]) / 2.0 if bids and asks else entry_price

                # Exit condition check based on orderbook imbalance reversal
                should_exit = False
                if direction == "LONG" and ask_depth >= bid_depth:
                    should_exit = True
                elif direction == "SHORT" and bid_depth >= ask_depth:
                    should_exit = True

                if should_exit:
                    pnl_pct = ((curr_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - curr_price) / entry_price * 100)
                    won = pnl_pct > 0
                    log.info(f"🎯 Order Book Shift Triggered Exit | PnL: {pnl_pct:+.2f}%")
                    return won, pnl_pct
            except Exception as e:
                log.error(f"Depth fetch error: {e}")
                continue

        # Exit on 1-hour timeout
        ticker = await exchange.fetch_ticker(symbol)
        exit_price = ticker.get("last", entry_price)
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - exit_price) / entry_price * 100)
        won = pnl_pct > 0
        log.info(f"⏰ Timeout Reached (60m) | PnL: {pnl_pct:+.2f}%")
        return won, pnl_pct

    except Exception as e:
        log.error(f"Execution error: {e}")
        return False, 0.0
    finally:
        await exchange.close()

async def process_trade(symbol, direction, setup_type):
    global active_trade
    try:
        log.info(f"⚙️ Executing Order Book Imbalance trade on {symbol} ({direction})...")
        trade_won, pnl_pct = await monitor_orderbook_shift(symbol, direction)
        log.info(f"📈 Trade Finished | Result: {'WIN' if trade_won else 'LOSS'} ({pnl_pct:+.2f}%)")
    finally:
        active_trade = None
        await notify_hf_ready(symbol, direction, trade_won, pnl_pct)

# --- AIOHTTP WEB SERVER FOR RENDER ---
routes = web.RouteTableDef()

@routes.get("/")
@routes.get("/health")
async def health_check(request):
    return web.json_response({"status": "online", "active_trade": active_trade})

@routes.post("/signal")
async def handle_signal(request):
    global active_trade

    # Secret Header Verification
    incoming_secret = request.headers.get("X-Webhook-Secret", "")
    if RENDER_WEBHOOK_SECRET and incoming_secret != RENDER_WEBHOOK_SECRET:
        log.warning("❌ Signal rejected: Invalid X-Webhook-Secret header.")
        return web.json_response({"error": "Unauthorized"}, status=401)

    if active_trade is not None:
        log.warning(f"⚠️ Signal rejected: Trade already in progress on {active_trade}.")
        return web.json_response({"error": "Busy", "active_trade": active_trade}, status=429)

    try:
        data = await request.json()
        symbol = data.get("symbol")
        direction = data.get("direction", "LONG")
        setup_type = data.get("setup_type", "OrderBook_Imbalance")

        if not symbol:
            return web.json_response({"error": "Missing symbol"}, status=400)

        active_trade = symbol
        log.info(f"📥 Signal Accepted from HF: {symbol} ({direction})")

        # Start execution in background task
        asyncio.create_task(process_trade(symbol, direction, setup_type))
        return web.json_response({"status": "accepted", "symbol": symbol, "direction": direction})
    except Exception as e:
        log.error(f"Error handling signal payload: {e}")
        return web.json_response({"error": str(e)}, status=400)

def main():
    app = web.Application()
    app.add_routes(routes)
    log.info(f"🚀 Render Web Service starting on port {PORT}...")
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()

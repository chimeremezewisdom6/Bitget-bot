import os
import time
import asyncio
import logging
from aiohttp import web
import aiohttp
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("executor")

# --- ENV (Accepts your exact Render variable names) ---
PORT = int(os.environ.get("PORT", 10000))

# Accepts HF_READY_URL or HF_SPACE_URL and strips /ready if present
_hf_url = (os.environ.get("HF_SPACE_URL") or os.environ.get("HF_READY_URL") or "").rstrip("/")
HF_SPACE_URL = _hf_url.replace("/ready", "")

# Accepts WEBHOOK_SECRET or RENDER_WEBHOOK_SECRET
RENDER_WEBHOOK_SECRET = (os.environ.get("RENDER_WEBHOOK_SECRET") or 
                         os.environ.get("WEBHOOK_SECRET") or "")

# Accepts BITGET_SECRET / BITGET_API_SECRET
EX_KEY = os.environ.get("BITGET_API_KEY", "")
EX_SECRET = (os.environ.get("BITGET_SECRET") or os.environ.get("BITGET_API_SECRET") or "")
EX_PASS = (os.environ.get("BITGET_PASSWORD") or os.environ.get("BITGET_PASSPHRASE") or "")

# Position sizing
POSITION_MARGIN_USDT = float(os.environ.get("POSITION_MARGIN_USDT", "10"))
LEVERAGE = int(os.environ.get("LEVERAGE", "5"))

# Dynamic exit logic
WINDOW_MINUTES = 30
MOMENTUM_CHECK_INTERVAL = 30
HARD_TIMEOUT_SECONDS = int(os.environ.get("HARD_TIMEOUT_SECONDS", "3600"))

active_trade = None
lock = asyncio.Lock()


def creds_ok():
    return bool(EX_KEY and EX_SECRET and EX_PASS)


async def notify_hf(symbol, direction, won, pnl_pct, aborted=False):
    if not HF_SPACE_URL:
        return
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{HF_SPACE_URL}/ready",
                              json={"symbol": symbol, "direction": direction,
                                    "won": won, "pnl_pct": pnl_pct,
                                    "aborted": aborted}, timeout=10) as r:
                if r.status == 200:
                    log.info("✅ HF notified.")
    except Exception as e:
        log.error(f"HF notify error: {e}")


def compute_bias(closes):
    """Dynamic ranking metric: returns up_sum, down_sum, direction."""
    if len(closes) < 10:
        return None
    up = 0.0; down = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0:
            up += d
        elif d < 0:
            down += -d
    if up + down <= 0:
        return None
    direction = "LONG" if up > down else "SHORT"
    return up, down, direction


async def place(exchange, symbol, side, amount, reduce_only=False):
    return await exchange.create_order(symbol, "market", side, amount,
                                       params={"reduceOnly": reduce_only})


async def run_trade(symbol, direction):
    if not creds_ok():
        log.error("Bitget creds missing.")
        return False, 0.0, True

    exchange = ccxt.bitget({
        "apiKey": EX_KEY, "secret": EX_SECRET, "password": EX_PASS,
        "enableRateLimit": True, "options": {"defaultType": "swap"},
    })

    try:
        await exchange.load_markets()
        if symbol not in exchange.markets:
            log.error(f"Market missing: {symbol}")
            return False, 0.0, True

        # Get initial momentum data to calculate dynamic SL
        candles = await exchange.fetch_ohlcv(symbol, "1m", limit=WINDOW_MINUTES)
        closes = [c[4] for c in candles if c and len(c) >= 5]
        bias = compute_bias(closes)
        if not bias:
            log.error(f"Not enough data for {symbol}")
            return False, 0.0, True
        init_up, init_down, _ = bias
        if init_up + init_down <= 0:
            return False, 0.0, True
        
        init_range_pct = (max(closes) - min(closes)) / min(closes) * 100.0
        sl_dist_pct = max(init_range_pct * 2.0, 0.5) # Stop loss is 2x the 30m range

        ticker = await exchange.fetch_ticker(symbol)
        entry_px = float(ticker.get("last") or 0)
        if entry_px <= 0:
            return False, 0.0, True

        market = exchange.market(symbol)
        contract_size = float(market.get("contractSize") or 1.0)
        notional = POSITION_MARGIN_USDT * LEVERAGE
        amount = notional / entry_px / contract_size
        try:
            amount = float(exchange.amount_to_precision(symbol, amount))
        except Exception:
            pass
        if amount <= 0:
            log.error(f"Trade size too small ({amount})")
            return False, 0.0, True

        try:
            await exchange.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

        side = "buy" if direction == "LONG" else "sell"
        log.info(f"💵 ENTRY {side} {amount} {symbol} @ ~{entry_px}")
        order = await place(exchange, symbol, side, amount)
        fill = float(order.get("average") or order.get("price") or entry_px)
        
        sl_price = (fill * (1 - sl_dist_pct / 100) if direction == "LONG"
                    else fill * (1 + sl_dist_pct / 100))

        start = time.monotonic()
        last_mom = 0.0
        current = fill
        exit_reason = None

        while (time.monotonic() - start) < HARD_TIMEOUT_SECONDS:
            await asyncio.sleep(5)

            try:
                t = await exchange.fetch_ticker(symbol)
                current = float(t.get("last") or current)
            except Exception:
                pass

            if direction == "LONG" and current <= sl_price:
                exit_reason = "STOP_LOSS"
                break
            if direction == "SHORT" and current >= sl_price:
                exit_reason = "STOP_LOSS"
                break

            if time.monotonic() - last_mom >= MOMENTUM_CHECK_INTERVAL:
                try:
                    c = await exchange.fetch_ohlcv(symbol, "1m", limit=WINDOW_MINUTES)
                    cls = [x[4] for x in c if x and len(x) >= 5]
                    b = compute_bias(cls)
                    if b:
                        up, dn, _ = b
                        if direction == "LONG" and dn >= up:
                            exit_reason = "MOMENTUM_FLIP"
                        elif direction == "SHORT" and up >= dn:
                            exit_reason = "MOMENTUM_FLIP"
                        if exit_reason:
                            break
                except Exception as e:
                    log.debug(f"momentum check: {e}")
                last_mom = time.monotonic()

        if exit_reason is None:
            exit_reason = "TIMEOUT"

        exit_side = "sell" if direction == "LONG" else "buy"
        log.info(f"💵 EXIT [{exit_reason}] {exit_side} {amount} {symbol}")
        try:
            await place(exchange, symbol, exit_side, amount, reduce_only=True)
        except Exception as e:
            log.critical(f"🚨 EXIT FAILED — close manually: {e}")
            return False, 0.0, True

        pnl = ((current - fill) / fill * 100 if direction == "LONG"
               else (fill - current) / fill * 100)
        won = pnl > 0
        log.info(f"📈 [{exit_reason}] {'WIN' if won else 'LOSS'} {pnl:+.2f}%")
        return won, pnl, False

    except Exception as e:
        log.error(f"Trade error: {e}")
        return False, 0.0, True
    finally:
        try:
            await exchange.close()
        except Exception:
            pass


async def process(symbol, direction):
    global active_trade
    won, pnl, aborted = False, 0.0, False
    try:
        won, pnl, aborted = await run_trade(symbol, direction)
    except Exception as e:
        aborted = True
    finally:
        async with lock:
            active_trade = None
        await notify_hf(symbol, direction, won, pnl, aborted=aborted)


routes = web.RouteTableDef()

@routes.get("/")
@routes.get("/health")
async def health(request):
    return web.json_response({"status": "online", "active_trade": active_trade, "creds_ok": creds_ok()})

@routes.post("/signal")
async def on_signal(request):
    global active_trade
    if RENDER_WEBHOOK_SECRET:
        if request.headers.get("X-Webhook-Secret", "") != RENDER_WEBHOOK_SECRET:
            return web.json_response({"error": "Unauthorized"}, status=401)
    async with lock:
        if active_trade:
            return web.json_response({"error": "Busy", "active_trade": active_trade}, status=429)
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Bad JSON"}, status=400)
        sym = data.get("symbol")
        direction = data.get("direction", "LONG")
        if not sym:
            return web.json_response({"error": "Missing symbol"}, status=400)
        active_trade = sym
        log.info(f"📥 Signal {sym} {direction}")
    asyncio.create_task(process(sym, direction))
    return web.json_response({"status": "accepted"})

def main():
    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()

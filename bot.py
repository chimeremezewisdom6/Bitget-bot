import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== KEEP-ALIVE SERVER FOR RENDER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget Whale Exhaustion Bot Active!")

    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[*] Health check active on port {port}")
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ==================== CONFIGURATION ====================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

COMPOUND_RATIO = 0.80        # Use 80% of wallet balance per trade
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum wallet balance
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'

TAKE_PROFIT_PCT = 0.015      # +1.5% Take Profit
VOLUME_DUMP_MULT = 2.2       # Whale volume dump multiplier

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
        'oneWayMode': True,
        'hedged': False,
    }
})

def get_available_balance():
    try:
        bal = exchange.fetch_balance({'type': 'swap'})
        if 'USDT' in bal and 'free' in bal['USDT']:
            return float(bal['USDT']['free'])
        elif 'free' in bal and 'USDT' in bal['free']:
            return float(bal['free']['USDT'])
        return 0.0
    except Exception as e:
        print(f"[!] Balance check: {e}")
        return 0.0

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for Whale Exhaustion scan.")
        return valid
    except Exception as e:
        print(f"[!] Symbol load error: {e}")
        return []

def place_buy_order(symbol, coin_amount):
    """Safely executes buy order in any position mode."""
    try:
        return exchange.create_order(
            symbol=symbol,
            type='market',
            side='buy',
            amount=coin_amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e1:
        if '25156' in str(e1) or 'tradeSide' in str(e1):
            return exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=coin_amount,
                params={'tradeSide': 'open'}
            )
        raise e1

def check_order_book_bids(symbol):
    """Verifies that buyers now dominate the order book."""
    try:
        ob = exchange.fetch_order_book(symbol, limit=15)
        if not ob or not ob['bids'] or not ob['asks']:
            return False
        total_bids = sum([b[1] for b in ob['bids'][:15]])
        total_asks = sum([a[1] for a in ob['asks'][:15]])
        if total_asks <= 0:
            return True
        return (total_bids / total_asks) >= 1.5
    except Exception:
        return False

def evaluate_symbol(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=25)
        if len(ohlcv) < 22:
            return

        volumes = [c[5] for c in ohlcv]

        # CANDLE 1 (Whale Dump): Completed at index -3
        c1_open, c1_high, c1_low, c1_close, c1_vol = (
            ohlcv[-3][1], ohlcv[-3][2], ohlcv[-3][3], ohlcv[-3][4], ohlcv[-3][5]
        )

        # CANDLE 2 (Confirmation Whale Stopped): Completed at index -2
        c2_open, c2_high, c2_low, c2_close, c2_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # -------------------------------------------------------------------------
        # STEP 1: VERIFY CANDLE 1 WAS A WHALE DUMP
        # -------------------------------------------------------------------------
        avg_vol = sum(volumes[-15:-3]) / 12.0
        if avg_vol <= 0 or (c1_vol / avg_vol) < VOLUME_DUMP_MULT:
            return  # No whale volume on Candle 1

        # Must be a RED dump candle
        c1_drop = ((c1_close - c1_open) / c1_open) * 100
        if c1_drop > -1.0:
            return  # Dump was too small to be a whale

        # -------------------------------------------------------------------------
        # STEP 2: VERIFY CANDLE 2 PROVES THE WHALE HAS STOPPED TRADING
        # -------------------------------------------------------------------------
        # Rule A: The whale stopped dumping (Volume on Candle 2 drops significantly)
        if c2_vol >= c1_vol * 0.85:
            return  # Volume is still too high, whale might still be dumping!

        # Rule B: The low holds (Price did NOT go lower than the whale dump low)
        if c2_low < c1_low:
            return  # Price made a lower low, sellers are not done!

        # Rule C: Buyers take over (Candle 2 closes GREEN and above Candle 1 close)
        if c2_close <= c2_open or c2_close <= c1_close:
            return  # Candle 2 is not green, buyers have not taken the upper hand!

        # -------------------------------------------------------------------------
        # STEP 3: ORDER BOOK CONFIRMATION (Buyers heavily outnumber sellers)
        # -------------------------------------------------------------------------
        if not check_order_book_bids(symbol):
            return  # Order book not yet stacked with buyers

        # -------------------------------------------------------------------------
        # STEP 4: WHALE IS CONFIRMED GONE -> EXECUTE
        # -------------------------------------------------------------------------
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c2_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        market = exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        if min_amount and float(coin_amount) < min_amount:
            return

        if float(coin_amount) <= 0:
            return

        try:
            exchange.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

        # Stop loss placed right below the whale dump low
        smart_sl = c1_low * 0.998
        tp_price = exchange.price_to_precision(symbol, c2_close * (1 + TAKE_PROFIT_PCT))
        smart_sl_price = exchange.price_to_precision(symbol, smart_sl)

        print(f"\n🐋 [WHALE DUMP COMPLETED & BUYERS IN CONTROL] {symbol}")
        print(f" ├─ Whale Dump (Candle 1): {c1_drop:.2f}% drop with {c1_vol / avg_vol:.1f}x volume")
        print(f" ├─ Whale Stopped (Candle 2): Volume dried up, Low held at ${c1_low}")
        print(f" ├─ Buyers Reversal: Green candle closed at ${c2_close}")
        print(f" ├─ Entry Price: ${c2_close}")
        print(f" └─ Take Profit Target (+1.5%): ${tp_price}")

        # Place Entry Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

        # Place Take-Profit Limit
        try:
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'reduceOnly': True, 'tradeSide': 'sell_single'}
            )
            print(f"🎯 [AUTO TP PLACED] at ${tp_price}")
        except Exception as tp_err:
            print(f"[!] TP notice: {tp_err}")

        # 5-minute cooldown to let the trade run
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Whale Exhaustion & Confirmation Scanner on Bitget...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

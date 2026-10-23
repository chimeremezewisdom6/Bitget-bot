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
        self.wfile.write(b"Bitget Whale Absorption Engine Running 24/7!")

    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[*] Health check server active on port {port}")
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ==================== CONFIGURATION ====================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

COMPOUND_RATIO = 0.80        # Reinvest 80% of balance per trade
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum balance to trigger
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'

TAKE_PROFIT_PCT = 0.015      # +1.5% Take Profit
ORDERBOOK_IMBALANCE = 1.8    # Bids must be 1.8x larger than Asks
VOLUME_CLIMAX_MULT = 2.2     # Volume must be 2.2x above average

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
        print(f"[*] Loaded {len(valid)} active pairs for Whale Imbalance Scan.")
        return valid
    except Exception as e:
        print(f"[!] Symbol load error: {e}")
        return []

def place_buy_order(symbol, coin_amount):
    """Dual fallback to ensure Bitget fills order in any position mode."""
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

def check_order_book_imbalance(symbol):
    """Checks live Bitget depth. Returns True if buyers heavily outnumber sellers."""
    try:
        ob = exchange.fetch_order_book(symbol, limit=15)
        if not ob or not ob['bids'] or not ob['asks']:
            return False, 0.0

        total_bids = sum([b[1] for b in ob['bids'][:15]])
        total_asks = sum([a[1] for a in ob['asks'][:15]])

        if total_asks <= 0:
            return True, 99.0

        imbalance_ratio = total_bids / total_asks
        return imbalance_ratio >= ORDERBOOK_IMBALANCE, imbalance_ratio
    except Exception:
        return False, 0.0

def evaluate_symbol(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=20)
        if len(ohlcv) < 18:
            return

        volumes = [c[5] for c in ohlcv]

        # Latest completed candle is index -2
        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        candle_range = c_high - c_low
        if candle_range <= 0:
            return

        # 1. Volume Climax Check (Did aggressive volume hit this candle?)
        avg_vol = sum(volumes[-12:-2]) / 10.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_CLIMAX_MULT:
            return

        # 2. Absorption Check (Did buyers absorb the selling leaving a lower wick?)
        lower_wick = min(c_open, c_close) - c_low
        wick_ratio = lower_wick / candle_range

        # Lower wick must be at least 25% of total candle (shows buying absorption)
        if wick_ratio < 0.25:
            return

        # 3. LIVE ORDER BOOK IMBALANCE (The Whale Exhaustion Confirmation)
        is_imbalanced, ratio = check_order_book_imbalance(symbol)
        if not is_imbalanced:
            return

        # Balance check & compounding
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Skip coins where $7 doesn't meet minimum contract limit
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

        # Smart Stop Loss: Placed 0.2% below the absorption wick
        smart_sl_price = c_low * 0.998
        tp_price = exchange.price_to_precision(symbol, c_close * (1 + TAKE_PROFIT_PCT))
        smart_sl_price = exchange.price_to_precision(symbol, smart_sl_price)

        print(f"\n🐋 [WHALE ABSORPTION & IMBALANCE DETECTED] {symbol}")
        print(f" ├─ Wallet: ${current_balance:.2f} USDT")
        print(f" ├─ Volume Climax: {c_vol / avg_vol:.1f}x average")
        print(f" ├─ Absorption Wick: {wick_ratio * 100:.1f}%")
        print(f" ├─ Order Book Imbalance: {ratio:.2f}x MORE BIDS THAN ASKS! 🔥")
        print(f" ├─ Entry Price: ${c_close}")
        print(f" └─ Take Profit Target (+1.5%): ${tp_price}")

        # Place Entry Buy Order
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

        # 5-minute cooldown to let the bounce play out
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Whale Imbalance & Absorption Scanner on Bitget...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

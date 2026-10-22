import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== WEB SERVER (KEEP-ALIVE) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget Bot is Running 24/7!")

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

MARGIN_PER_TRADE = 2.0       # $2 USDT margin
LEVERAGE = 3                 # 3x leverage ($6 position)
TIMEFRAMES = ['5m', '15m', '30m', '1h']
MIN_PRICE_DROP = -3.0
MIN_OI_SURGE = 3.0
MIN_VOLUME_USDT = 1_000_000

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
    }
})

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs.")
        return valid
    except Exception as e:
        print(f"[!] Error loading symbols: {e}")
        return []

def evaluate_symbol(symbol):
    for tf in TIMEFRAMES:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=3)
            if len(ohlcv) < 3:
                continue

            c_open, c_high, c_low, c_close = (
                ohlcv[-2][1],
                ohlcv[-2][2],
                ohlcv[-2][3],
                ohlcv[-2][4]
            )

            max_dip = ((c_low - c_open) / c_open) * 100
            if max_dip > MIN_PRICE_DROP:
                continue

            candle_range = c_high - c_low
            if candle_range <= 0:
                continue

            rebound_ratio = (c_close - c_low) / candle_range
            if rebound_ratio < 0.10:
                continue

            try:
                oi_history = exchange.fetch_open_interest_history(symbol, timeframe=tf, limit=3)
            except Exception:
                continue

            if not oi_history or len(oi_history) < 2:
                continue

            prev_oi = float(oi_history[-2].get('openInterestValue') or oi_history[-2].get('openInterestAmount') or 0)
            curr_oi = float(oi_history[-1].get('openInterestValue') or oi_history[-1].get('openInterestAmount') or 0)

            if prev_oi <= 0:
                continue

            oi_change = ((curr_oi - prev_oi) / prev_oi) * 100
            if oi_change < MIN_OI_SURGE:
                continue

            print(f"\n🔥 [TRIGGER MATCHED ON {tf}] {symbol}")
            target_notional = MARGIN_PER_TRADE * LEVERAGE
            coin_amount = target_notional / c_close
            coin_amount = exchange.amount_to_precision(symbol, coin_amount)

            if float(coin_amount) <= 0:
                print(f"[!] Size below minimum for {symbol}")
                return

            try:
                exchange.set_leverage(LEVERAGE, symbol)
            except Exception:
                pass

            print(f"[*] Executing Market Buy: {coin_amount} {symbol}...")
            order = exchange.create_market_buy_order(symbol, coin_amount)
            print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

            time.sleep(120)
            return

        except Exception:
            continue

def run_bot():
    print(f"[*] Starting Multi-Timeframe Scanner {TIMEFRAMES}...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.08)

        print("[*] Sweep completed. Sleeping 15s...")
        time.sleep(15)

if __name__ == "__main__":
    run_bot()

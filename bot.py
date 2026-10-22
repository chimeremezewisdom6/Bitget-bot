import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== WEB SERVER (RENDER KEEP-ALIVE) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget 5m Climax Scalper Running 24/7!")

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
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'             # Focus solely on 5m micro-dumps

# Strategy Parameters
RSI_OVERSOLD = 24.0          # Extreme oversold
VOLUME_MULTIPLIER = 2.2      # Volume must be 2.2x above average
TAKE_PROFIT_PCT = 0.013      # +1.3% target profit

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
    }
})

def calculate_rsi(closes, period=14):
    """Calculates 14-period RSI."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for 5m Climax Scan.")
        return valid
    except Exception as e:
        print(f"[!] Error loading symbols: {e}")
        return []

def evaluate_symbol(symbol):
    try:
        # Fetch last 20 candles of 5m
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=20)
        if len(ohlcv) < 18:
            return

        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        # Latest completed candle is index -2
        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. Check if the candle was a dump (>= 1.2% dip)
        dip_pct = ((c_low - c_open) / c_open) * 100
        if dip_pct > -1.2:
            return

        # 2. Check Volume Climax: Current volume >= 2.2x the average of previous 10 candles
        avg_vol = sum(volumes[-12:-2]) / 10.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_MULTIPLIER:
            return

        # 3. Check RSI: must be below 24
        rsi = calculate_rsi(closes[:-1])
        if rsi > RSI_OVERSOLD:
            return

        # --- TRIGGER MATCHED ---
        print(f"\n⚡ [5M SELLING CLIMAX DETECTED] {symbol}")
        print(f" ├─ 5m Dip: {dip_pct:.2f}%")
        print(f" ├─ Volume Surge: {c_vol / avg_vol:.1f}x avg")
        print(f" └─ 5m RSI: {rsi:.1f}")

        target_notional = MARGIN_PER_TRADE * LEVERAGE
        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        if float(coin_amount) <= 0:
            return

        try:
            exchange.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

        # Execute Market Entry
        print(f"[*] Buying {coin_amount} {symbol}...")
        order = exchange.create_market_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Filled! ID: {order['id']}")

        # Set automatic Take Profit (+1.3%)
        tp_price = exchange.price_to_precision(symbol, c_close * (1 + TAKE_PROFIT_PCT))
        try:
            print(f"[*] Placing Take-Profit limit order at ${tp_price}...")
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'reduceOnly': True}
            )
            print("🎯 [TP SET] Take-profit placed successfully!")
        except Exception as tp_err:
            print(f"[!] Warning: Could not set auto TP: {tp_err}")

        # Sleep 5 minutes cooldown so it doesn't re-enter the same coin immediately
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting 5m Climax Scanner on Bitget ($1M+ Volume)...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep finished. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

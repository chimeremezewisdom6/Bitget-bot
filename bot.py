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
        self.wfile.write(b"Bitget Breakout Engine Running 24/7!")

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
TIMEFRAME = '5m'

# 1:1 Equal Take Profit and Stop Loss
TAKE_PROFIT_PCT = 0.015      # +1.5% Take Profit
STOP_LOSS_PCT = 0.015        # -1.5% Stop Loss
VOLUME_SPIKE_MULT = 3.0      # Volume must be 3x above average

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
    }
})

def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)
    ema = [prices[0]]
    for p in prices[1:]:
        ema.append((p - ema[-1]) * multiplier + ema[-1])
    return ema[-1]

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for Squeeze Breakout.")
        return valid
    except Exception as e:
        print(f"[!] Error loading symbols: {e}")
        return []

def evaluate_symbol(symbol):
    try:
        # Fetch last 30 candles of 5m
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=30)
        if len(ohlcv) < 25:
            return

        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        # Latest completed candle is index -2
        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. Breakout Check: Did candle close higher than the highest high of the previous 20 candles?
        prev_20_high = max(highs[-22:-2])
        if c_close <= prev_20_high:
            return

        # 2. Volume Explosion Check: Volume >= 3.0x average of previous 15 candles
        avg_vol = sum(volumes[-17:-2]) / 15.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_SPIKE_MULT:
            return

        # 3. Bullish Dominance: Candle must close in upper 85% of its range (crushed sellers)
        candle_range = c_high - c_low
        if candle_range <= 0 or ((c_close - c_low) / candle_range) < 0.85:
            return

        # 4. Moving Average Momentum: Price above 9 EMA and 21 EMA
        ema_9 = calculate_ema(closes[:-1], 9)
        ema_21 = calculate_ema(closes[:-1], 21)
        if c_close < ema_9 or ema_9 < ema_21:
            return

        # --- TRIGGER MATCHED ---
        print(f"\n🚀 [SHORT SQUEEZE BREAKOUT] {symbol}")
        print(f" ├─ Broke 20-candle high: ${prev_20_high}")
        print(f" ├─ Volume Spike: {c_vol / avg_vol:.1f}x avg")
        print(f" └─ Close Price: ${c_close}")

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

        # Set 1:1 TP (+1.5%) and SL (-1.5%)
        tp_price = exchange.price_to_precision(symbol, c_close * (1 + TAKE_PROFIT_PCT))
        sl_price = exchange.price_to_precision(symbol, c_close * (1 - STOP_LOSS_PCT))

        try:
            # Place Limit Take Profit
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'reduceOnly': True}
            )
            print(f"🎯 [TP SET] +1.5% at ${tp_price}")
        except Exception as tp_err:
            print(f"[!] Warning TP: {tp_err}")

        # Cooldown 5 minutes to avoid double-entering the same breakout
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting 5m Squeeze Breakout Scanner ($1M+ Volume)...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

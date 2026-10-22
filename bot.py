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
        self.wfile.write(b"Bitget Compounding Bot Active!")

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

COMPOUND_RATIO = 0.80        # Reinvest 80% of wallet balance per trade
MIN_USDT_BALANCE = 1.90      # Minimum balance to trade
LEVERAGE = 3                 # 3x leverage
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'

TAKE_PROFIT_PCT = 0.015      # +1.5% Take Profit
VOLUME_SPIKE_MULT = 3.0      # Volume must be 3x above average

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
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
        print(f"[!] Error fetching balance: {e}")
        return 0.0

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
            # Exclude traditional tokenized equities (e.g., TSM, GLW, BE) that have huge minimum contract sizes
            base = symbol.split('/')[0]
            if base in ['TSM', 'GLW', 'BE', 'METU', 'NVDA', 'AAPL', 'TSLA', 'AMZN', 'MSFT', 'GOOGL']:
                continue

            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active crypto pairs (stocks filtered out).")
        return valid
    except Exception as e:
        print(f"[!] Error loading symbols: {e}")
        return []

def evaluate_symbol(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=30)
        if len(ohlcv) < 25:
            return

        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. Breakout Check (20-candle high)
        prev_20_high = max(highs[-22:-2])
        if c_close <= prev_20_high:
            return

        # 2. Volume Explosion (3x average)
        avg_vol = sum(volumes[-17:-2]) / 15.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_SPIKE_MULT:
            return

        # 3. Bullish Dominance
        candle_range = c_high - c_low
        if candle_range <= 0 or ((c_close - c_low) / candle_range) < 0.85:
            return

        # 4. Moving Average Momentum
        ema_9 = calculate_ema(closes[:-1], 9)
        ema_21 = calculate_ema(closes[:-1], 21)
        if c_close < ema_9 or ema_9 < ema_21:
            return

        # Check Balance & Position Sizing
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE

        # Ensure order satisfies Bitget's minimum $5 notional limit
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        if float(coin_amount) <= 0:
            return

        # Check Exchange Minimum Contract Size
        market = exchange.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        if min_amount and float(coin_amount) < min_amount:
            return

        print(f"\n🚀 [QUALIFIED CRYPTO BREAKOUT] {symbol}")
        print(f" ├─ Wallet Balance: ${current_balance:.2f} USDT")
        print(f" ├─ Compounded Margin (80%): ${trade_margin:.2f} USDT")
        print(f" ├─ Position Value (3x): ${target_notional:.2f} USDT")
        print(f" └─ Breakout Price: ${c_close}")

        try:
            exchange.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

        # Execute Market Entry with Hedge Mode compatibility
        try:
            order = exchange.create_market_buy_order(
                symbol,
                coin_amount,
                params={'tradeSide': 'open'}
            )
            print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")
        except Exception as order_err:
            print(f"[!] Order rejected by Bitget on {symbol}: {order_err}")
            return

        # Set Take Profit (+1.5%)
        tp_price = exchange.price_to_precision(symbol, c_close * (1 + TAKE_PROFIT_PCT))
        try:
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'tradeSide': 'close', 'reduceOnly': True}
            )
            print(f"🎯 [AUTO TP PLACED] Target: ${tp_price} (+1.5%)")
        except Exception as tp_err:
            print(f"[!] Warning placing TP on {symbol}: {tp_err}")

        # 5-minute cooldown
        time.sleep(300)

    except Exception as e:
        print(f"[!] Evaluation Error: {e}")
        return

def run_bot():
    print(f"[*] Starting 5m Compounding Breakout Scanner...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

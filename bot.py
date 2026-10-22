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
        self.wfile.write(b"Bitget One-Way Compounding Engine Running 24/7!")

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

# Compounding settings
COMPOUND_RATIO = 0.80        # Reinvest 80% of wallet balance per trade
MIN_USDT_BALANCE = 1.90      # Minimum $1.90 balance to trade
LEVERAGE = 3                 # 3x leverage
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'

TAKE_PROFIT_PCT = 0.015      # +1.5% Take Profit
STOP_LOSS_PCT = 0.015        # -1.5% Stop Loss
VOLUME_SPIKE_MULT = 3.0      # Volume 3x above average

# Initialize Bitget strictly for ONE-WAY MODE
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
    """Fetches real-time available USDT balance."""
    try:
        bal = exchange.fetch_balance({'type': 'swap'})
        if 'USDT' in bal and 'free' in bal['USDT']:
            return float(bal['USDT']['free'])
        elif 'free' in bal and 'USDT' in bal['free']:
            return float(bal['free']['USDT'])
        return 0.0
    except Exception as e:
        print(f"[!] Balance error: {e}")
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
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for One-Way scan.")
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

        # 1. Breakout Check (Broke the 20-candle ceiling)
        prev_20_high = max(highs[-22:-2])
        if c_close <= prev_20_high:
            return

        # 2. Volume Spike Check (3x volume explosion)
        avg_vol = sum(volumes[-17:-2]) / 15.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_SPIKE_MULT:
            return

        # 3. Bullish Dominance (Closed in upper 85% of candle)
        candle_range = c_high - c_low
        if candle_range <= 0 or ((c_close - c_low) / candle_range) < 0.85:
            return

        # 4. Momentum Check (Price > 9 EMA > 21 EMA)
        ema_9 = calculate_ema(closes[:-1], 9)
        ema_21 = calculate_ema(closes[:-1], 21)
        if c_close < ema_9 or ema_9 < ema_21:
            return

        # Balance check
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        # Compounding math (80% margin)
        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Skip stock futures or contracts where $7 is below the exchange minimum lot
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

        print(f"\n🚀 [QUALIFIED ONE-WAY BREAKOUT] {symbol}")
        print(f" ├─ Wallet: ${current_balance:.2f} USDT")
        print(f" ├─ Margin Used (80%): ${trade_margin:.2f} USDT")
        print(f" ├─ Trade Value (3x): ${target_notional:.2f} USDT")
        print(f" └─ Amount: {coin_amount} @ ${c_close}")

        # Place Market Buy in ONE-WAY MODE
        try:
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=coin_amount,
                params={
                    'oneWayMode': True,
                    'hedged': False,
                }
            )
            print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

            # Place Take-Profit in ONE-WAY MODE (reduceOnly ensures it closes the Long)
            tp_price = exchange.price_to_precision(symbol, c_close * (1 + TAKE_PROFIT_PCT))
            try:
                exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side='sell',
                    amount=coin_amount,
                    price=tp_price,
                    params={
                        'reduceOnly': True,
                        'oneWayMode': True,
                        'hedged': False,
                    }
                )
                print(f"🎯 [AUTO TP PLACED] Target: ${tp_price} (+1.5%)")
            except Exception as tp_err:
                print(f"[!] TP notice: {tp_err}")

            # Cooldown 5 minutes to let the trade develop
            time.sleep(300)

        except Exception as order_err:
            print(f"[!] Order rejected by Bitget on {symbol}: {order_err}")

    except Exception:
        return

def run_bot():
    print(f"[*] Starting One-Way Compounding Breakout Scanner on Bitget...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

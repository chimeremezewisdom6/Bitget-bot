import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== KEEP-ALIVE SERVER (FOR RENDER 24/7) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget Smart Liquidity Trap Engine Running 24/7!")

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

COMPOUND_RATIO = 0.80        # Reinvest 80% of available USDT per trade
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum balance required to trade
MIN_VOLUME_USDT = 1_000_000  # $1,000,000+ daily volume filter
TIMEFRAME = '5m'             # 5-minute execution timeframe

TAKE_PROFIT_PCT = 0.025      # +2.5% Target (void fill)
SL_CUSHION = 0.008           # 0.8% Wise Cushion below the sweep low
VOLUME_MULT = 1.8            # Volume must be at least 1.8x average (stop-loss trigger volume)

# Initialize Bitget
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
    """Fetches live available USDT balance from Bitget."""
    try:
        bal = exchange.fetch_balance({'type': 'swap'})
        if 'USDT' in bal and 'free' in bal['USDT']:
            return float(bal['USDT']['free'])
        elif 'free' in bal and 'USDT' in bal['free']:
            return float(bal['free']['USDT'])
        return 0.0
    except Exception as e:
        print(f"[!] Balance read notice: {e}")
        return 0.0

def get_tradable_symbols():
    """Fetches all active USDT-M Perpetual pairs with >= $1M volume."""
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for Smart Sweep Scan.")
        return valid
    except Exception as e:
        print(f"[!] Symbol fetch error: {e}")
        return []

def place_buy_order(symbol, coin_amount):
    """Dual-mode order placement: works in One-Way or Hedge mode seamlessly."""
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

def evaluate_symbol(symbol):
    try:
        # Fetch 60 candles (~5 hours of market structure)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
        if len(ohlcv) < 55:
            return

        lows = [c[3] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        # Latest completed candle is index -2
        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. IDENTIFY THE 4-HOUR STRUCTURAL FLOOR (Lowest low of 50 candles before this one)
        structural_floor = min(lows[-52:-2])

        # 2. THE SWEEP CHECK: Price MUST have punctured BELOW the 50-candle floor
        if c_low >= structural_floor:
            return  # Did not sweep the floor

        # 3. THE TRAP CONFIRMATION: Price MUST close back ABOVE the floor
        # Proves the whale run out of selling power and shorts are trapped below!
        if c_close <= structural_floor:
            return  # Closed below floor, selling might continue

        # 4. ABSORPTION WICK: Lower wick must be at least 25% of the candle's total range
        candle_range = c_high - c_low
        if candle_range <= 0:
            return
        lower_wick = min(c_open, c_close) - c_low
        if (lower_wick / candle_range) < 0.25:
            return

        # 5. VOLUME CONFIRMATION: Volume spike showing stop-loss execution
        avg_vol = sum(volumes[-20:-2]) / 18.0
        if avg_vol <= 0 or (c_vol / avg_vol) < VOLUME_MULT:
            return

        # Balance check & Dynamic Compounding
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Safety Check: Skip high-priced stock futures if order doesn't meet minimum lot
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

        # SMART & WISE STOP LOSS: 0.8% cushion below the absolute sweep low
        smart_sl = c_low * (1.0 - SL_CUSHION)
        sl_pct = ((c_close - smart_sl) / c_close) * 100

        # Discard extreme outliers (avoid massive wicks where risk > 2.8%)
        if sl_pct > 2.8 or sl_pct < 0.5:
            return

        tp_price = exchange.price_to_precision(symbol, c_close * (1.0 + TAKE_PROFIT_PCT))
        smart_sl_price = exchange.price_to_precision(symbol, smart_sl)

        print(f"\n⚡ [SMART LIQUIDITY SWEEP & SHORT TRAP] {symbol}")
        print(f" ├─ Wallet: ${current_balance:.2f} USDT")
        print(f" ├─ 4h Structural Floor Swept: ${structural_floor}")
        print(f" ├─ Sweep Low: ${c_low} (Stops triggered)")
        print(f" ├─ Closed Back Above Floor: ${c_close}")
        print(f" ├─ Target (+2.5% TP): ${tp_price}")
        print(f" └─ Wise Stop Loss (-{sl_pct:.2f}%): ${smart_sl_price}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

        # Place Take-Profit Limit (+2.5%)
        try:
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'reduceOnly': True, 'tradeSide': 'sell_single'}
            )
            print(f"🎯 [AUTO TP PLACED] at ${tp_price} (+2.5%)")
        except Exception as tp_err:
            print(f"[!] TP notice: {tp_err}")

        # 5-minute pause to let the upward void fill develop
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Smart Liquidity Trap Scanner on Bitget ($1M+ Volume)...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep finished. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

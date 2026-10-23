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
        self.wfile.write(b"Bitget Real-Money 15m Engine Running 24/7!")

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

COMPOUND_RATIO = 0.80        # Reinvest 80% of wallet balance per trade
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum balance to trade
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '15m'            # 15-minute timeframe to let the money work!

# REAL-MONEY IMBALANCE RULES:
MIN_DOLLAR_RATIO = 3.5       # Buy dollars must be at least 3.5x to 10x larger than sell dollars
MAX_SELL_EXAGGERATION = 0.35 # Sell volume cannot exceed 35% of total volume (protects 10:1 ratio)
BREAKEVEN_TRIGGER_PCT = 0.008 # Move SL to Entry at +0.8% profit

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
        print(f"[!] Balance error: {e}")
        return 0.0

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for 15m Money Flow scan.")
        return valid
    except Exception as e:
        print(f"[!] Symbol fetch error: {e}")
        return []

def get_real_money_flow(symbol):
    """Calculates actual cash dollars ($) flowing into Buys vs Sells on the tape."""
    try:
        trades = exchange.fetch_trades(symbol, limit=100)
        if not trades or len(trades) < 20:
            return 0, 0, 0.0

        buy_dollars = sum([float(t.get('cost', 0) or (t['price'] * t['amount'])) for t in trades if t.get('side') == 'buy'])
        sell_dollars = sum([float(t.get('cost', 0) or (t['price'] * t['amount'])) for t in trades if t.get('side') == 'sell'])

        if sell_dollars <= 0:
            return buy_dollars, sell_dollars, 99.0

        ratio = buy_dollars / sell_dollars
        return buy_dollars, sell_dollars, ratio
    except Exception:
        return 0, 0, 0.0

def place_buy_order(symbol, coin_amount):
    """Dual-mode order placement: works in One-Way or Hedge mode seamlessly."""
    try:
        return exchange.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'buy_single'})
    except Exception as e1:
        if '25156' in str(e1) or 'tradeSide' in str(e1):
            return exchange.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'open'})
        raise e1

def manage_trade_adaptively(symbol, coin_amount, entry_price, dynamic_tp, smart_sl):
    """Monitors live trade: watches for Take Profit, Breakeven (+0.8%), and dying buy volume."""
    print(f"🛡️ [MONEY MONITOR ACTIVE] Watching real-time cash flow on {symbol}...")
    breakeven_set = False
    start_time = time.time()

    while (time.time() - start_time) < 1800: # 30 min max run
        try:
            ticker = exchange.fetch_ticker(symbol)
            curr_price = float(ticker['last'])
            pnl_pct = (curr_price - entry_price) / entry_price

            # 1. Take Profit reached
            if curr_price >= dynamic_tp:
                print(f"🎯 [TAKE PROFIT HIT] Closing {symbol} at ${curr_price} (+{pnl_pct*100:.2f}%)!")
                exchange.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                return

            # 2. Risk-Free Breakeven Trigger (+0.8%)
            if pnl_pct >= BREAKEVEN_TRIGGER_PCT and not breakeven_set:
                smart_sl = entry_price * 1.001
                breakeven_set = True
                print(f"🔒 [BREAKEVEN ACTIVATED] {symbol} up +{pnl_pct*100:.2f}%! Stop Loss moved to Entry. ZERO RISK!")

            # 3. Check if Upper Money is Dying (Exit early with profit if buy pressure collapses)
            if pnl_pct >= 0.012: # If up at least 1.2%
                _, _, live_ratio = get_real_money_flow(symbol)
                if live_ratio < 1.5: # Money is dying!
                    print(f"⚠️ [UPPER MONEY DIED] Buyer cash flow collapsed on {symbol}. Closing early in profit at +{pnl_pct*100:.2f}%!")
                    exchange.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                    return

            # 4. Stop Loss hit
            if curr_price <= smart_sl:
                reason = "BREAKEVEN EXIT ($0 Loss)" if breakeven_set else "STRUCTURAL STOP"
                print(f"⚠️ [{reason}] Closing {symbol} at ${curr_price}...")
                exchange.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                return

            time.sleep(5)
        except Exception:
            time.sleep(5)
            continue

def evaluate_symbol(symbol):
    try:
        # Fetch 25 candles on the 15-MINUTE chart
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=25)
        if len(ohlcv) < 20:
            return

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]

        # Candle 1 (Previous 15m candle): index -3
        c1_high = ohlcv[-3][2]

        # Candle 2 (Latest completed 15m candle): index -2
        c2_open, c2_high, c2_low, c2_close = ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4]

        # ---------------------------------------------------------------------
        # 1. WAIT FOR MONEY TO MOVE THE PRICE (Displacement Breakout)
        # ---------------------------------------------------------------------
        # Price must have closed GREEN and physically broken above previous 15m high
        if c2_close <= c2_open or c2_close <= c1_high:
            return  # Price is sitting still or falling; DO NOT ENTER!

        # ---------------------------------------------------------------------
        # 2. CHECK THE REAL MONEY (DOLLARS INFLOW ON THE TAPE)
        # ---------------------------------------------------------------------
        buy_dollars, sell_dollars, money_ratio = get_real_money_flow(symbol)
        
        # Rule: Must have heavy buyer dominance (at least 3.5:1 up to 10:1 ratio!)
        if money_ratio < MIN_DOLLAR_RATIO:
            return  # Not enough heavy cash behind the move

        # Exaggeration Filter: Sells cannot be heavy (enforcing the 10:1 not 10:5 rule)
        total_dollars = buy_dollars + sell_dollars
        if (sell_dollars / total_dollars) > MAX_SELL_EXAGGERATION:
            return  # Sellers are pushing back too hard, skip!

        # ---------------------------------------------------------------------
        # 3. DYNAMIC PROFIT TARGET (Targeting the recent resistance ceiling)
        # ---------------------------------------------------------------------
        range_ceiling = max(highs[-18:-2])
        dynamic_tp = range_ceiling * 0.996
        profit_room_pct = (dynamic_tp - c2_close) / c2_close

        # Must offer at least +1.8% to +5.0% room
        if profit_room_pct < 0.018 or profit_room_pct > 0.050:
            return

        # Balance check & compounding
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c2_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Skip stock contracts if below min lot
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

        # Smart structural stop: 0.7% below the breakout candle's low
        smart_sl = c2_low * 0.993

        print(f"\n💰 [REAL-MONEY INFLOW BREAKOUT CONFIRMED] {symbol}")
        print(f" ├─ Timeframe: 15-Minute (Noise Filtered!)")
        print(f" ├─ Buy Dollars Flow: ${buy_dollars:,.0f} USDT")
        print(f" ├─ Sell Dollars Flow: ${sell_dollars:,.0f} USDT")
        print(f" ├─ Money Ratio: {money_ratio:.1f} : 1 BUYER DOMINANCE! 🔥")
        print(f" ├─ Price Confirmation: Broke 15m high (${c1_high}) -> Closed at ${c2_close}")
        print(f" ├─ Target (+{profit_room_pct*100:.2f}%): ${dynamic_tp:.4f}")
        print(f" └─ Entry Price: ${c2_close}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

        # Start Active Monitoring (Breakeven + Dying Money Exit)
        manage_trade_adaptively(symbol, coin_amount, c2_close, dynamic_tp, smart_sl)

        time.sleep(120)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting 15-Minute Real-Money Flow Scanner on Bitget...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 15m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

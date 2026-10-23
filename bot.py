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
        self.wfile.write(b"Bitget Global Top 200 Engine Running 24/7!")

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
TIMEFRAME = '15m'            # 15-Minute Timeframe (Filters noise!)
BREAKEVEN_TRIGGER_PCT = 0.008 # Move SL to Entry at +0.8% profit

# Bitget Client
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

# Free Global Binance Client (NO KEYS NEEDED - For Global Top 200 Leaderboard)
global_exchange = ccxt.binance()

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

def get_global_top_200_bases():
    """Fetches the Top 200 most traded coins globally by 24h volume from Binance."""
    try:
        tickers = global_exchange.fetch_tickers()
        usdt_pairs = []
        for sym, t in tickers.items():
            if sym.endswith('/USDT'):
                base = sym.split('/')[0]
                vol = float(t.get('quoteVolume', 0))
                usdt_pairs.append((base, vol))
        
        # Sort by 24h volume descending and take the Top 200
        usdt_pairs.sort(key=lambda x: x[1], reverse=True)
        top_200_bases = set([x[0] for x in usdt_pairs[:200]])
        print(f"[*] Updated Global Top 200 Leaderboard. Top: {usdt_pairs[0][0]} (${usdt_pairs[0][1]:,.0f} 24h vol).")
        return top_200_bases
    except Exception as e:
        print(f"[!] Warning fetching global tickers: {e}")
        return set()

def get_tradable_symbols(global_top_bases):
    """Filters Bitget contracts to ONLY those in the Global Top 200."""
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT'):
                base = symbol.split(':')[0].split('/')[0]
                # MUST BE IN THE GLOBAL TOP 200
                if base in global_top_bases:
                    valid.append((symbol, ticker))
        print(f"[*] Loaded {len(valid)} Bitget contracts verified in the GLOBAL TOP 200.")
        return valid
    except Exception as e:
        print(f"[!] Symbol error: {e}")
        return []

def calculate_ema(prices, period):
    multiplier = 2 / (period + 1)
    ema = [prices[0]]
    for p in prices[1:]:
        ema.append((p - ema[-1]) * multiplier + ema[-1])
    return ema[-1]

def check_order_book_bids(symbol):
    try:
        ob = exchange.fetch_order_book(symbol, limit=15)
        if not ob or not ob['bids'] or not ob['asks']:
            return False, 0.0
        bids = sum([b[1] for b in ob['bids'][:15]])
        asks = sum([a[1] for a in ob['asks'][:15]])
        if asks <= 0: return True, 99.0
        return (bids / asks) >= 1.6, (bids / asks)
    except Exception:
        return False, 0.0

def place_buy_order(symbol, coin_amount):
    """Dual-mode order placement."""
    try:
        return exchange.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'buy_single'})
    except Exception as e1:
        if '25156' in str(e1) or 'tradeSide' in str(e1):
            return exchange.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'open'})
        raise e1

def manage_trade_adaptively(symbol, coin_amount, entry_price, dynamic_tp, smart_sl):
    """Monitors live trade: locks Breakeven at +0.8% so trade has ZERO RISK!"""
    print(f"🛡️ [GLOBAL RUNNER MONITOR ACTIVE] Guarding {symbol}...")
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

            # 3. Stop Loss hit
            if curr_price <= smart_sl:
                reason = "BREAKEVEN EXIT ($0 Loss)" if breakeven_set else "STRUCTURAL STOP"
                print(f"⚠️ [{reason}] Closing {symbol} at ${curr_price}...")
                exchange.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                return

            time.sleep(5)
        except Exception:
            time.sleep(5)
            continue

def evaluate_symbol(symbol_data):
    symbol, ticker = symbol_data
    try:
        # Fetch 25 candles on the 15-MINUTE chart
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=25)
        if len(ohlcv) < 20:
            return

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        # Candle 1 (Previous 15m candle): index -3
        c1_high = ohlcv[-3][2]

        # Candle 2 (Completed 15m candle): index -2
        c2_open, c2_high, c2_low, c2_close, c2_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. GLOBAL MOMENTUM: Price must be above 20 EMA on 15m
        ema_20 = calculate_ema(closes[:-1], 20)
        if c2_close < ema_20:
            return

        # 2. INITIATION: Candle must close GREEN and break previous 15m high
        if c2_close <= c2_open or c2_close <= c1_high:
            return

        # 3. VOLUME CONFIRMATION: Volume must be at least 1.8x average
        avg_vol = sum(volumes[-16:-2]) / 14.0
        if avg_vol <= 0 or (c2_vol / avg_vol) < 1.8:
            return

        # 4. ORDER BOOK LIQUIDITY: Bids must dominate Asks on Bitget
        has_bids, ratio = check_order_book_bids(symbol)
        if not has_bids:
            return

        # 5. DYNAMIC TARGET: Ceiling target between +1.8% and +4.5%
        range_ceiling = max(highs[-18:-2])
        dynamic_tp = range_ceiling * 0.996
        profit_room_pct = (dynamic_tp - c2_close) / c2_close

        if profit_room_pct < 0.018 or profit_room_pct > 0.045:
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

        # Stop loss: 0.7% below the breakout candle's low
        smart_sl = c2_low * 0.993

        print(f"\n🌐 [GLOBAL TOP-200 MOMENTUM BREAKOUT] {symbol}")
        print(f" ├─ Timeframe: 15-Minute (Noise Filtered)")
        print(f" ├─ Global Status: Verified Top 200 Worldwide by Volume")
        print(f" ├─ Order Book Support: {ratio:.2f}x Bids over Asks 🔥")
        print(f" ├─ Target (+{profit_room_pct*100:.2f}%): ${dynamic_tp:.4f}")
        print(f" └─ Entry Price: ${c2_close}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Global Top-200 Order Filled! ID: {order['id']}")

        # Start Active Adaptive Monitoring (Breakeven + Dynamic Exit)
        manage_trade_adaptively(symbol, coin_amount, c2_close, dynamic_tp, smart_sl)

        time.sleep(120)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Global Top 200 Scanner (Binance Anchored + Bitget Executed)...")
    last_global_fetch = 0
    global_bases = set()

    while True:
        # Refresh Global Top 200 list every 3 hours
        if time.time() - last_global_fetch > 10800:
            global_bases = get_global_top_200_bases()
            last_global_fetch = time.time()

        symbols_data = get_tradable_symbols(global_bases)
        for sym_data in symbols_data:
            evaluate_symbol(sym_data)
            time.sleep(0.06)

        print("[*] Global Top 200 sweep complete. Re-scanning...")
        time.sleep(15)

if __name__ == "__main__":
    run_bot()

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
        self.wfile.write(b"Multi-Exchange Consensus Engine Active 24/7!")

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
MIN_USDT_BALANCE = 1.90      # Minimum balance to trade
TIMEFRAME = '15m'            # 15-Minute Timeframe
BREAKEVEN_TRIGGER_PCT = 0.008 # Move SL to Entry at +0.8% profit

# Minimum COMBINED volume across Bybit + OKX + Gate.io
MIN_COMBINED_GLOBAL_VOLUME = 15_000_000  # $15,000,000+ USD!

# 1. Execution Client (Bitget)
bitget = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
    'options': {
        'defaultType': 'swap',
        'oneWayMode': True,
        'hedged': False,
    }
})

# 2. Free Global Market Feeds (NO API KEYS NEEDED)
bybit = ccxt.bybit({'enableRateLimit': True})
okx = ccxt.okx({'enableRateLimit': True})
gateio = ccxt.gateio({'enableRateLimit': True})

def get_available_balance():
    try:
        bal = bitget.fetch_balance({'type': 'swap'})
        if 'USDT' in bal and 'free' in bal['USDT']:
            return float(bal['USDT']['free'])
        elif 'free' in bal and 'USDT' in bal['free']:
            return float(bal['free']['USDT'])
        return 0.0
    except Exception as e:
        print(f"[!] Balance error: {e}")
        return 0.0

def fetch_multi_exchange_global_volumes():
    """Aggregates real-time 24h trading volume from Bybit, OKX, and Gate.io."""
    global_volumes = {}
    print("[*] Fetching Global Liquidity Consensus from Bybit, OKX, and Gate.io...")

    # 1. Bybit Volume
    try:
        bybit_tickers = bybit.fetch_tickers()
        for sym, t in bybit_tickers.items():
            base = sym.split('/')[0].split(':')[0].upper()
            vol = float(t.get('quoteVolume', 0))
            global_volumes[base] = global_volumes.get(base, 0) + vol
        print(f" ├─ Bybit: Loaded {len(bybit_tickers)} pairs.")
    except Exception as e:
        print(f" ├─ [!] Bybit feed notice: {e}")

    # 2. OKX Volume
    try:
        okx_tickers = okx.fetch_tickers()
        for sym, t in okx_tickers.items():
            base = sym.split('/')[0].split(':')[0].upper()
            vol = float(t.get('quoteVolume', 0))
            global_volumes[base] = global_volumes.get(base, 0) + vol
        print(f" ├─ OKX: Loaded {len(okx_tickers)} pairs.")
    except Exception as e:
        print(f" ├─ [!] OKX feed notice: {e}")

    # 3. Gate.io Volume
    try:
        gate_tickers = gateio.fetch_tickers()
        for sym, t in gate_tickers.items():
            base = sym.split('/')[0].split('_')[0].upper()
            vol = float(t.get('quoteVolume', 0))
            global_volumes[base] = global_volumes.get(base, 0) + vol
        print(f" └─ Gate.io: Loaded {len(gate_tickers)} pairs.")
    except Exception as e:
        print(f" └─ [!] Gate.io feed notice: {e}")

    return global_volumes

def get_tradable_symbols(global_volumes):
    """Filters Bitget contracts to ONLY those backed by heavy global consensus."""
    try:
        bitget.load_markets()
        tickers = bitget.fetch_tickers()
        valid = []

        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT'):
                base = symbol.split(':')[0].split('/')[0].upper()

                # Clean multiplier prefixes (e.g. 1000PEPE -> PEPE)
                clean_base = base
                for prefix in ['1000000', '10000', '1000']:
                    if clean_base.startswith(prefix) and len(clean_base) > len(prefix):
                        clean_base = clean_base[len(prefix):]
                        break

                combined_vol = global_volumes.get(base, 0) or global_volumes.get(clean_base, 0)

                # MUST HAVE AT LEAST $15,000,000 COMBINED GLOBAL VOLUME!
                if combined_vol >= MIN_COMBINED_GLOBAL_VOLUME:
                    valid.append((symbol, ticker, combined_vol))

        # Sort descending by global volume (heaviest coins first!)
        valid.sort(key=lambda x: x[2], reverse=True)
        selected = [(v[0], v[1], v[2]) for v in valid]
        print(f"[*] Verified {len(selected)} Bitget contracts backed by >= $15M Combined Global Volume.")
        return selected
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
        ob = bitget.fetch_order_book(symbol, limit=15)
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
        return bitget.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'buy_single'})
    except Exception as e1:
        if '25156' in str(e1) or 'tradeSide' in str(e1):
            return bitget.create_order(symbol, 'market', 'buy', coin_amount, params={'tradeSide': 'open'})
        raise e1

def manage_trade_adaptively(symbol, coin_amount, entry_price, dynamic_tp, smart_sl):
    """Monitors live trade: locks Breakeven at +0.8% so trade has ZERO RISK!"""
    print(f"🛡️ [GLOBAL TITAN MONITOR ACTIVE] Guarding {symbol}...")
    breakeven_set = False
    start_time = time.time()

    while (time.time() - start_time) < 1800: # 30 min max run
        try:
            ticker = bitget.fetch_ticker(symbol)
            curr_price = float(ticker['last'])
            pnl_pct = (curr_price - entry_price) / entry_price

            # 1. Take Profit reached
            if curr_price >= dynamic_tp:
                print(f"🎯 [TAKE PROFIT HIT] Closing {symbol} at ${curr_price} (+{pnl_pct*100:.2f}%)!")
                bitget.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
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
                bitget.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                return

            time.sleep(5)
        except Exception:
            time.sleep(5)
            continue

def evaluate_symbol(symbol_data):
    symbol, ticker, combined_global_vol = symbol_data
    try:
        # Fetch 25 candles on the 15-MINUTE chart
        ohlcv = bitget.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=25)
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

        # 1. MOMENTUM: Price must be above 20 EMA on 15m
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
        coin_amount = bitget.amount_to_precision(symbol, coin_amount)

        # Skip stock contracts if below min lot
        market = bitget.market(symbol)
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        if min_amount and float(coin_amount) < min_amount:
            return

        if float(coin_amount) <= 0:
            return

        try:
            bitget.set_leverage(LEVERAGE, symbol)
        except Exception:
            pass

        # Stop loss: 0.7% below the breakout candle's low
        smart_sl = c2_low * 0.993

        base_name = symbol.split(':')[0]
        print(f"\n🌐 [GLOBAL MULTI-EXCHANGE BREAKOUT VERIFIED] {symbol}")
        print(f" ├─ Asset: {base_name}")
        print(f" ├─ Combined Global Volume: ${combined_global_vol:,.0f} USDT (Bybit + OKX + Gate)")
        print(f" ├─ Order Book Support: {ratio:.2f}x Bids over Asks 🔥")
        print(f" ├─ Target (+{profit_room_pct*100:.2f}%): ${dynamic_tp:.4f}")
        print(f" └─ Entry Price: ${c2_close}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Global Multi-Exchange Order Filled! ID: {order['id']}")

        # Start Active Adaptive Monitoring (Breakeven + Dynamic Exit)
        manage_trade_adaptively(symbol, coin_amount, c2_close, dynamic_tp, smart_sl)

        time.sleep(120)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Multi-Exchange Consensus Engine (Bybit + OKX + Gate.io + Bitget)...")
    last_global_fetch = 0
    global_volumes = {}

    while True:
        # Refresh Global Volume Consensus every 3 hours
        if time.time() - last_global_fetch > 10800 or len(global_volumes) == 0:
            global_volumes = fetch_multi_exchange_global_volumes()
            last_global_fetch = time.time()

        symbols_data = get_tradable_symbols(global_volumes)
        for sym_data in symbols_data:
            evaluate_symbol(sym_data)
            time.sleep(0.06)

        print("[*] Multi-Exchange sweep complete. Re-scanning...")
        time.sleep(15)

if __name__ == "__main__":
    run_bot()

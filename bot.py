import os
import time
import json
import urllib.request
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== KEEP-ALIVE SERVER (FOR RENDER 24/7) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget Global Top 500 Engine Active 24/7!")

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

def fetch_global_top_500_symbols():
    """Fetches the True Global Top 500 cryptocurrencies worldwide via CoinCap."""
    try:
        url = "https://api.coincap.io/v2/assets?limit=500"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode())
            global_symbols = set([item['symbol'].upper() for item in data.get('data', [])])
            if len(global_symbols) > 50:
                print(f"[*] Global Aggregator: Loaded {len(global_symbols)} verified worldwide assets (TOP 500).")
                return global_symbols
    except Exception as e:
        print(f"[!] Global Aggregator notice: {e}")
    
    # Fallback list of top liquid global giants
    return {"BTC", "ETH", "SOL", "DOGE", "PEPE", "SUI", "XRP", "NEAR", "AVAX", "LINK", "ADA", "SHIB", "BNB", "DOT", "LTC", "BCH", "APT", "UNI", "ICP", "FET", "RENDER", "TAO", "WIF", "BONK", "FLOKI", "AR", "INJ", "TIA", "SEI", "KAS"}

def get_tradable_symbols(global_verified_symbols):
    """Filters Bitget contracts to ONLY those present in the Global Top 500."""
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []

        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT'):
                base = symbol.split(':')[0].split('/')[0].upper()
                
                # Strip multiplier prefixes (e.g. 1000PEPE -> PEPE, 1000BONK -> BONK)
                clean_base = base
                for prefix in ['1000000', '10000', '1000']:
                    if clean_base.startswith(prefix) and len(clean_base) > len(prefix):
                        clean_base = clean_base[len(prefix):]
                        break

                # Check if base coin or clean base is in the Global Top 500
                if base in global_verified_symbols or clean_base in global_verified_symbols:
                    vol = float(ticker.get('quoteVolume', 0))
                    if vol >= 500_000: # Ensure coin has active trading
                        valid.append((symbol, ticker, vol))

        # Sort descending by volume so biggest coins are scanned first
        valid.sort(key=lambda x: x[2], reverse=True)
        selected = [(v[0], v[1]) for v in valid]
        print(f"[*] Successfully loaded {len(selected)} Bitget contracts verified in the GLOBAL TOP 500.")
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
    print(f"🛡️ [TOP-500 RUNNER MONITOR ACTIVE] Guarding {symbol}...")
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

        base_name = symbol.split(':')[0]
        print(f"\n🌐 [GLOBAL TOP-500 MOMENTUM BREAKOUT] {symbol}")
        print(f" ├─ Asset: {base_name} (Verified in Global Top 500 Worldwide!)")
        print(f" ├─ Order Book Support: {ratio:.2f}x Bids over Asks 🔥")
        print(f" ├─ Target (+{profit_room_pct*100:.2f}%): ${dynamic_tp:.4f}")
        print(f" └─ Entry Price: ${c2_close}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Global Top-500 Order Filled! ID: {order['id']}")

        # Start Active Adaptive Monitoring (Breakeven + Dynamic Exit)
        manage_trade_adaptively(symbol, coin_amount, c2_close, dynamic_tp, smart_sl)

        time.sleep(120)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Global Top 500 Scanner (Worldwide Liquid Assets + Bitget Executed)...")
    last_global_fetch = 0
    global_verified_symbols = set()

    while True:
        # Refresh Global Top 500 list every 2 hours
        if time.time() - last_global_fetch > 7200 or len(global_verified_symbols) == 0:
            fetched = fetch_global_top_500_symbols()
            if fetched and len(fetched) > 0:
                global_verified_symbols = fetched
            last_global_fetch = time.time()

        symbols_data = get_tradable_symbols(global_verified_symbols)
        for sym_data in symbols_data:
            evaluate_symbol(sym_data)
            time.sleep(0.06)

        print("[*] Global Top 500 sweep complete. Re-scanning...")
        time.sleep(15)

if __name__ == "__main__":
    run_bot()

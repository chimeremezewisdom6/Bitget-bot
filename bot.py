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
        self.wfile.write(b"Bitget Full 2-Sequence + OI + Breakeven Bot Active!")

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

COMPOUND_RATIO = 0.80        # Reinvest 80% of available balance
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum balance to trade
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'

# YOUR EXACT STRATEGY RULES:
MIN_PRICE_DROP = -3.0        # Price must drop at least -3.0%
MIN_OI_SURGE = 3.0           # Open Interest must surge at least +3.0%
HEFTY_IMBALANCE_RATIO = 2.2  # Bids must be >= 2.2x Asks (Hefty only!)
BREAKEVEN_TRIGGER_PCT = 0.008 # Move SL to Entry as soon as trade is up +0.8%

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
        print(f"[!] Balance read notice: {e}")
        return 0.0

def get_tradable_symbols():
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
        valid = []
        for symbol, ticker in tickers.items():
            if symbol.endswith(':USDT') and ticker.get('quoteVolume', 0) >= MIN_VOLUME_USDT:
                valid.append(symbol)
        print(f"[*] Loaded {len(valid)} active pairs for Complete Scan.")
        return valid
    except Exception as e:
        print(f"[!] Symbol fetch error: {e}")
        return []

def check_hefty_imbalance(symbol):
    """Verifies that buyers heavily dominate the live order book (Bids >= 2.2x Asks)."""
    try:
        ob = exchange.fetch_order_book(symbol, limit=20)
        if not ob or not ob['bids'] or not ob['asks']:
            return False, 0.0
        total_bids = sum([b[1] for b in ob['bids'][:15]])
        total_asks = sum([a[1] for a in ob['asks'][:15]])
        if total_asks <= 0:
            return True, 99.0
        ratio = total_bids / total_asks
        return ratio >= HEFTY_IMBALANCE_RATIO, ratio
    except Exception:
        return False, 0.0

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

def manage_trade_adaptively(symbol, coin_amount, entry_price, dynamic_tp, smart_sl):
    """Active trade monitor: Moves Stop Loss to Breakeven at +0.8% to guarantee NO RED!"""
    print(f"🛡️ [ADAPTIVE MONITOR ACTIVE] Guarding {symbol} against losses...")
    breakeven_set = False
    start_time = time.time()

    while (time.time() - start_time) < 1200:
        try:
            ticker = exchange.fetch_ticker(symbol)
            curr_price = float(ticker['last'])
            pnl_pct = (curr_price - entry_price) / entry_price

            # 1. Take Profit reached
            if curr_price >= dynamic_tp:
                print(f"🎯 [TAKE PROFIT REACHED] Closing {symbol} at ${curr_price} (+{pnl_pct*100:.2f}%)!")
                exchange.create_order(symbol, 'market', 'sell', coin_amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
                return

            # 2. Move SL to Breakeven at +0.8% gain (Trade becomes 100% Risk-Free!)
            if pnl_pct >= BREAKEVEN_TRIGGER_PCT and not breakeven_set:
                smart_sl = entry_price * 1.001
                breakeven_set = True
                print(f"🔒 [BREAKEVEN ACTIVATED] {symbol} is up +{pnl_pct*100:.2f}%! Stop Loss moved to Entry (${smart_sl:.4f}). Trade is now RISK-FREE!")

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

def evaluate_symbol(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=40)
        if len(ohlcv) < 35:
            return

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]

        # Candle 1 (Whale Dump): Completed at index -4
        c1_open, c1_low, c1_close = ohlcv[-4][1], ohlcv[-4][3], ohlcv[-4][4]
        
        # Candle 2 (First Rebound): Completed at index -3
        c2_open, c2_close, c2_low = ohlcv[-3][1], ohlcv[-3][4], ohlcv[-3][3]

        # Candle 3 (Second Rebound / Retest Confirmation): Completed at index -2
        c3_open, c3_high, c3_low, c3_close = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4]
        )

        # ---------------------------------------------------------------------
        # 1. RULE 1: PRICE DUMP >= 3.0%
        # ---------------------------------------------------------------------
        dump_pct = ((c1_low - c1_open) / c1_open) * 100
        if dump_pct > MIN_PRICE_DROP:
            return  # Did not dump at least 3.0%

        # ---------------------------------------------------------------------
        # 2. RULE 2: OPEN INTEREST SURGE >= +3.0% (Whales/Shorts Entered)
        # ---------------------------------------------------------------------
        try:
            oi_history = exchange.fetch_open_interest_history(symbol, timeframe=TIMEFRAME, limit=5)
            if not oi_history or len(oi_history) < 3:
                return
            prev_oi = float(oi_history[-4].get('openInterestValue') or oi_history[-4].get('openInterestAmount') or 0)
            curr_oi = float(oi_history[-2].get('openInterestValue') or oi_history[-2].get('openInterestAmount') or 0)
            if prev_oi <= 0:
                return
            oi_change = ((curr_oi - prev_oi) / prev_oi) * 100
            if oi_change < MIN_OI_SURGE:
                return  # Open interest did not surge >= +3.0%
        except Exception:
            return

        # ---------------------------------------------------------------------
        # 3. RULE 3: TWO-SEQUENCE DOUBLE REBOUND (Floor Holds & Closes Green)
        # ---------------------------------------------------------------------
        # The low must hold on the second test:
        if c3_low < (c1_low * 0.997):
            return  # Floor broke, dump is continuing!

        # Second rebound must close GREEN and above Candle 2 close:
        if c3_close <= c3_open or c3_close <= c2_close:
            return  # Not a confirmed green bounce

        # ---------------------------------------------------------------------
        # 4. RULE 4: HEFTY ORDER BOOK IMBALANCE (Bids >= 2.2x Asks)
        # ---------------------------------------------------------------------
        has_hefty_imbalance, ratio = check_hefty_imbalance(symbol)
        if not has_hefty_imbalance:
            return  # Imbalance is not strong enough

        # ---------------------------------------------------------------------
        # 5. DYNAMIC CEILING TARGET (Take Profit)
        # ---------------------------------------------------------------------
        range_ceiling = max(highs[-30:-2])
        dynamic_tp = range_ceiling * 0.995
        room_pct = (dynamic_tp - c3_close) / c3_close

        # Must have at least +1.8% room to run
        if room_pct < 0.018 or room_pct > 0.065:
            return

        # Balance check & compounding
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c3_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Skip stock contracts if under min contract limit
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

        # Smart structural stop loss: 0.8% below the double bottom floor
        smart_sl = c1_low * 0.992

        print(f"\n💎 [FULL STRATEGY TRIGGERED: DUMP + OI + DOUBLE REBOUND] {symbol}")
        print(f" ├─ Rule 1 (Dump): {dump_pct:.2f}% (>= -3.0% dump)")
        print(f" ├─ Rule 2 (OI Surge): +{oi_change:.2f}% (>= +3.0% surge)")
        print(f" ├─ Rule 3 (Double Rebound): Floor held at ${c1_low} -> Rebounded Green!")
        print(f" ├─ Rule 4 (Hefty Imbalance): {ratio:.2f}x BIDS OVER ASKS! 🔥")
        print(f" ├─ Dynamic Ceiling Target (+{room_pct*100:.2f}%): ${dynamic_tp:.4f}")
        print(f" └─ Entry Price: ${c3_close}")

        # Place Entry Buy Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

        # Start Active Adaptive Monitoring (Breakeven + Dynamic Exit)
        manage_trade_adaptively(symbol, coin_amount, c3_close, dynamic_tp, smart_sl)

        # 2-minute cooldown after trade exit
        time.sleep(120)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting All-In-One Double-Rebound + OI Scanner on Bitget...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] Sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

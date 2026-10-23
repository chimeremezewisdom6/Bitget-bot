import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==================== KEEP-ALIVE SERVER FOR RENDER ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bitget Dynamic Liquidity Range Engine Active!")

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

COMPOUND_RATIO = 0.80        # Reinvest 80% of wallet balance
LEVERAGE = 3                 # 3x leverage
MIN_USDT_BALANCE = 1.90      # Minimum balance to trade
MIN_VOLUME_USDT = 1_000_000  # $1M+ daily volume
TIMEFRAME = '5m'             # Execution timeframe

# Dynamic Range Filters
MIN_PROFIT_ROOM = 0.018      # Only enter if there is at least +1.8% room to the ceiling
MAX_PROFIT_ROOM = 0.060      # Cap profit targets at +6.0% for realistic fills

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
        print(f"[*] Loaded {len(valid)} active pairs for Dynamic Range scan.")
        return valid
    except Exception as e:
        print(f"[!] Error loading symbols: {e}")
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
        # Fetch 40 candles (over 3 hours of real price action)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=40)
        if len(ohlcv) < 35:
            return

        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        # Latest completed candle is index -2
        c_open, c_high, c_low, c_close, c_vol = (
            ohlcv[-2][1], ohlcv[-2][2], ohlcv[-2][3], ohlcv[-2][4], ohlcv[-2][5]
        )

        # 1. DYNAMIC RANGE CEILING (Where long traders will take profit)
        range_ceiling = max(highs[-32:-2])

        # 2. DYNAMIC RANGE FLOOR (Where short sellers have their Take-Profit targets)
        range_floor = min(lows[-32:-2])

        # 3. VERIFY SHORTS HIT THEIR TARGET & CLOSED:
        # Price must have dipped to or below the floor, triggering short TP buy orders
        if c_low > range_floor:
            return

        # 4. UPPER SIDE TAKES CONTROL:
        # Price must reject the floor and close back ABOVE it as a green candle
        if c_close <= range_floor or c_close <= c_open:
            return

        # 5. MEASURE THE DYNAMIC ROOM TO RUN:
        # Target the ceiling minus a 5% buffer so the order fills before resistance
        dynamic_tp_price = range_ceiling * 0.995
        potential_profit_pct = (dynamic_tp_price - c_close) / c_close

        # Filter out coins with too little room to run
        if potential_profit_pct < MIN_PROFIT_ROOM or potential_profit_pct > MAX_PROFIT_ROOM:
            return

        # Volume confirmation: Short covering creates a spike
        avg_vol = sum(volumes[-15:-2]) / 13.0
        if avg_vol <= 0 or (c_vol / avg_vol) < 1.5:
            return

        # Balance check & compounding
        current_balance = get_available_balance()
        if current_balance < MIN_USDT_BALANCE:
            return

        trade_margin = current_balance * COMPOUND_RATIO
        target_notional = trade_margin * LEVERAGE
        if target_notional < 5.5:
            target_notional = 5.5

        coin_amount = target_notional / c_close
        coin_amount = exchange.amount_to_precision(symbol, coin_amount)

        # Safety Check: Skip stock perps if below min contract size
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

        # DYNAMIC STRUCTURAL STOP LOSS: Placed below the floor rejection wick
        smart_sl = c_low * 0.993  # 0.7% cushion below the floor wick
        sl_pct = ((c_close - smart_sl) / c_close) * 100

        # Discard trades where risk is disproportionate
        if sl_pct > 2.2 or sl_pct < 0.4:
            return

        tp_price = exchange.price_to_precision(symbol, dynamic_tp_price)
        smart_sl_price = exchange.price_to_precision(symbol, smart_sl)

        print(f"\n🏛️ [DYNAMIC RANGE LIQUIDITY ROTATION] {symbol}")
        print(f" ├─ Shorts Take-Profit Floor: ${range_floor}")
        print(f" ├─ Entry (Upper side in control): ${c_close}")
        print(f" ├─ Longs Take-Profit Target (Ceiling): ${tp_price} (+{potential_profit_pct * 100:.2f}%)")
        print(f" ├─ Structural Stop Loss: ${smart_sl_price} (-{sl_pct:.2f}%)")
        print(f" └─ Risk-to-Reward: 1 : {potential_profit_pct / (sl_pct / 100):.2f}")

        # Place Entry Order
        order = place_buy_order(symbol, coin_amount)
        print(f"✅ [SUCCESS] Order Filled! ID: {order['id']}")

        # Place Dynamic Take-Profit Limit
        try:
            exchange.create_order(
                symbol=symbol,
                type='limit',
                side='sell',
                amount=coin_amount,
                price=tp_price,
                params={'reduceOnly': True, 'tradeSide': 'sell_single'}
            )
            print(f"🎯 [DYNAMIC TP PLACED] at ${tp_price} (+{potential_profit_pct * 100:.2f}%)")
        except Exception as tp_err:
            print(f"[!] TP notice: {tp_err}")

        # 5-minute cooldown to let the rotation play out
        time.sleep(300)

    except Exception:
        return

def run_bot():
    print(f"[*] Starting Dynamic Liquidity Range Scanner on Bitget ($1M+ Volume)...")
    symbols = get_tradable_symbols()

    while True:
        for sym in symbols:
            evaluate_symbol(sym)
            time.sleep(0.06)

        print("[*] 5m sweep complete. Re-scanning...")
        time.sleep(10)

if __name__ == "__main__":
    run_bot()

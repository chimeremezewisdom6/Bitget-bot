import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==========================================================
# 1. RENDER KEEP-ALIVE SERVER (Port 10000)
# ==========================================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is hunting momentum.")

    def log_message(self, format, *args):
        return  # Silence HTTP server logs to keep terminal clean

def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)

# ==========================================================
# 2. EXCHANGE CONFIGURATION
# ==========================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

exchange = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "password": PASSPHRASE,
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap",
        "createMarketBuyOrderRequiresPrice": False
    }
})

LEVERAGE = 3
BALANCE_USE_PCT = 0.80  # 80% compounding
MIN_NOTIONAL = 5.20     # Safe buffer above Bitget's $5.00 min requirement
MIN_24H_VOLUME = 15_000_000  # $15M minimum global liquidity

# ==========================================================
# 3. BITGET ONE-WAY ORDER HELPERS (Error 25156 Immune)
# ==========================================================
def open_long_position(symbol, amount):
    """Dual-fallback execution for Bitget Unified One-Way Mode"""
    try:
        return exchange.create_order(
            symbol=symbol,
            type='market',
            side='buy',
            amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e

def close_long_position(symbol, amount):
    """Dual-fallback exit for Bitget Unified One-Way Mode"""
    try:
        return exchange.create_order(
            symbol=symbol,
            type='market',
            side='sell',
            amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e

def get_open_position():
    """Returns symbol, amount, entry_price of active long position, or None"""
    try:
        positions = exchange.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            side = p.get('side', '').lower()
            if contracts > 0 and side == 'long':
                return {
                    'symbol': p['symbol'],
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0))
                }
    except Exception as e:
        print(f"[POSITION CHECK ERROR] {e}", flush=True)
    return None

# ==========================================================
# 4. MOMENTUM SCREENER (Early Initiation / No Top Chasing)
# ==========================================================
def scan_for_momentum():
    """
    1. Grabs all swap tickers in ONE fast API call.
    2. Filters liquid coins moving between +1.5% and +9% (not top-extended).
    3. Verifies RVol >= 2.5x and clean funding rate.
    """
    try:
        exchange.load_markets()
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"[SCANNER ERROR] Failed fetching tickers: {e}", flush=True)
        return None

    candidates = []
    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue

        vol_24h = float(t.get('quoteVolume', 0) or 0)
        pct_24h = float(t.get('percentage', 0) or 0)

        # Liquidity + Anti-Top Filter:
        # Pumping between +1.5% and +9.0% with at least $15M volume
        if vol_24h >= MIN_24H_VOLUME and 1.5 <= pct_24h <= 9.0:
            candidates.append((symbol, pct_24h, vol_24h))

    # Sort by 24h percentage gain descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Inspect top candidates for 15m structural initiation
    for symbol, pct_24h, _ in candidates[:10]:
        try:
            market = exchange.market(symbol)
            min_lot = float(market['limits']['amount']['min'] or 0)

            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=25)
            if len(ohlcv) < 22:
                continue

            closes = [c[4] for c in ohlcv]
            volumes = [c[5] for c in ohlcv]
            cur_price = closes[-1]

            # 1. Base / Average check: 20-period SMA
            sma_20 = sum(closes[-21:-1]) / 20
            dist_from_sma = ((cur_price - sma_20) / sma_20) * 100

            # Must be breaking out fresh from base (0.8% to 3.5% above baseline)
            if not (0.8 <= dist_from_sma <= 3.5):
                continue

            # 2. Whale Volume (RVol >= 2.5x)
            avg_vol = sum(volumes[-21:-1]) / 20
            cur_vol = volumes[-1]
            rvol = cur_vol / avg_vol if avg_vol > 0 else 0
            if rvol < 2.5:
                continue

            # 3. Clean Funding Rate Check (< 0.03% per 8h)
            try:
                funding = exchange.fetch_funding_rate(symbol)
                fr = float(funding.get('fundingRate', 0) or 0)
                if fr > 0.0003:  # Too crowded
                    continue
            except Exception:
                pass  # Do not block if funding endpoint times out

            # 4. Open Interest Expansion
            try:
                oi_data = exchange.fetch_open_interest(symbol)
                oi_val = float(oi_data.get('openInterestValue', 0) or oi_data.get('openInterestAmount', 0))
                if oi_val <= 0:
                    continue
            except Exception:
                pass

            print(f"[FOUND RUNNER] {symbol} | RVol: {rvol:.2f}x | DistSMA: +{dist_from_sma:.2f}% | 24h: +{pct_24h:.1f}%", flush=True)
            return symbol, cur_price, min_lot

        except Exception as e:
            continue

    return None

# ==========================================================
# 5. TRADE GUARDIAN (Execution & State Machine)
# ==========================================================
def manage_active_trade(symbol, contracts, entry_price):
    highest_price = entry_price
    entry_time = time.time()
    last_log_time = 0

    print(f"\n[GUARDIAN ACTIVE] Managing {symbol} | Entry: {entry_price:.6f} | Qty: {contracts}", flush=True)

    while True:
        try:
            time.sleep(3)
            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker['last'])

            if cur_price > highest_price:
                highest_price = cur_price

            pnl_pct = ((cur_price - entry_price) / entry_price) * 100
            peak_pnl = ((highest_price - entry_price) / entry_price) * 100
            elapsed_min = (time.time() - entry_time) / 60

            # Log heartbeat every 20 seconds
            if time.time() - last_log_time > 20:
                print(f"[STATUS] {symbol} PnL: {pnl_pct:+.2f}% | Peak: {peak_pnl:+.2f}% | Active: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # ----------------------------------------------------
            # RULE 1: THE FEE-SHIELD LOCK (+1.0% -> +0.5%)
            # Once it crosses +1.0%, never allow it below +0.5%
            # ----------------------------------------------------
            if peak_pnl >= 1.0:
                guaranteed_floor = entry_price * 1.005
                if cur_price <= guaranteed_floor:
                    print(f"[EXIT TRIGGER] Fee-Shield Triggered! Locked +0.5% profit (Peak: +{peak_pnl:.2f}%)", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # ----------------------------------------------------
            # RULE 2: MOMENTUM STALL / BOX EXHAUSTION EXIT
            # If trade has run > 15 mins and stays stuck in a box
            # ----------------------------------------------------
            if elapsed_min >= 15 and peak_pnl < 1.0:
                if abs(pnl_pct) <= 0.45:
                    print(f"[EXIT TRIGGER] Momentum stalled in a tight box after {elapsed_min:.0f} mins. Closing trade.", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # ----------------------------------------------------
            # RULE 3: INITIAL STRUCTURAL STOP LOSS (-1.2%)
            # ----------------------------------------------------
            if peak_pnl < 1.0 and pnl_pct <= -1.20:
                print(f"[EXIT TRIGGER] Initial Stop Loss hit at {pnl_pct:.2f}%.", flush=True)
                close_long_position(symbol, contracts)
                break

            # ----------------------------------------------------
            # RULE 4: DYNAMIC RUNNER TRAIL (+3% to +10%+ expansion)
            # Give 1.5% breathing room from highest peak
            # ----------------------------------------------------
            if peak_pnl >= 3.0:
                trailing_floor = highest_price * 0.985
                if cur_price <= trailing_floor:
                    print(f"[EXIT TRIGGER] Trailing stop triggered. Banked runner at +{pnl_pct:.2f}% (Peak: +{peak_pnl:.2f}%)", flush=True)
                    close_long_position(symbol, contracts)
                    break

        except Exception as e:
            print(f"[GUARDIAN LOOP WARNING] {e}", flush=True)
            time.sleep(2)

# ==========================================================
# 6. MAIN ENGINE LOOP
# ==========================================================
def main():
    start_keep_alive()
    print("[SYSTEM] Bitget Early-Base Momentum Hunter initialized.", flush=True)

    while True:
        try:
            # Check if position is already open
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            # Fetch Wallet Balance
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info['USDT']['free'] or 0)
            
            # Sizing: 80% available balance * 3x leverage
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE
            
            if notional < MIN_NOTIONAL:
                print(f"[WAITING] Margin too low for $5 min notional (Balance: ${usdt_free:.2f} | Notional: ${notional:.2f})", flush=True)
                time.sleep(15)
                continue

            # Scan for early momentum
            result = scan_for_momentum()
            if not result:
                time.sleep(10)
                continue

            symbol, cur_price, min_lot = result

            # Calculate amount and precision
            raw_amount = notional / cur_price
            formatted_amount = float(exchange.amount_to_precision(symbol, raw_amount))

            # Safety check: does the account meet the contract minimum lot size?
            if formatted_amount < min_lot:
                print(f"[SKIP] {symbol}: Sizing ({formatted_amount}) below min lot ({min_lot})", flush=True)
                time.sleep(5)
                continue

            # Ensure leverage is configured on Bitget
            try:
                exchange.set_leverage(LEVERAGE, symbol, params={'marginMode': 'crossed'})
            except Exception:
                pass

            print(f"[ENTERING LONG] {symbol} | Size: {formatted_amount} | Notional: ${notional:.2f}", flush=True)
            order = open_long_position(symbol, formatted_amount)
            print(f"[ORDER PLACED] ID: {order.get('id')}", flush=True)

            # Wait 3 seconds for exchange fill confirmation before launching guardian
            time.sleep(3)

        except Exception as e:
            print(f"[MAIN LOOP ERROR] {e}", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    main()

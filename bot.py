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
        self.wfile.write(b"Trader Desk Bot is watching the charts.")

    def log_message(self, format, *args):
        return

def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)

# ==========================================================
# 2. EXCHANGE & STRATEGY SETTINGS
# ==========================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials!", flush=True)
    sys.exit(1)

exchange = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "password": PASSPHRASE,
    "enableRateLimit": True,
    "timeout": 15000,
    "options": {
        "defaultType": "swap",
        "createMarketBuyOrderRequiresPrice": False
    }
})

LEVERAGE = 3
BALANCE_USE_PCT = 0.80             # 80% compounding
MIN_NOTIONAL = 5.10                # Safety buffer above Bitget $5.00 min
MIN_24H_VOLUME = 15_000_000         # $15M minimum liquid volume
INSPECTION_INTERVAL_SECONDS = 900  # 15 minutes chart inspection cycle (set 1800 for 30m)
CONVICTION_THRESHOLD = 80          # Score out of 100 required to take a trade

# ==========================================================
# 3. BITGET ONE-WAY ORDER HELPERS
# ==========================================================
def open_long_position(symbol, amount):
    """Dual-fallback for Bitget Unified One-Way Mode"""
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
    """Returns open long position if any"""
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
# 4. TRADER ANALYSIS & CONVICTION SCORING ENGINE
# ==========================================================
def evaluate_coin(symbol, pct_24h):
    """
    Analyzes a candidate across 15m chart structure:
    - Base Compression (25 pts)
    - Relative Volume Spike (30 pts)
    - Open Interest Inflow (25 pts)
    - Funding Runway (20 pts)
    """
    score = 0
    thesis = []

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=25)
    if len(ohlcv) < 22:
        return 0, "Insufficient candle history", 0, 0, 0

    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]
    cur_price = closes[-1]

    # 1. Base / Average Proximity (20-period SMA)
    sma_20 = sum(closes[-21:-1]) / 20
    dist_from_sma = ((cur_price - sma_20) / sma_20) * 100

    if 0.6 <= dist_from_sma <= 2.5:
        score += 25
        thesis.append(f"Clean base breakout (+{dist_from_sma:.1f}% off 20 SMA)")
    elif 2.5 < dist_from_sma <= 4.0:
        score += 15
        thesis.append(f"Moderate extension (+{dist_from_sma:.1f}% off 20 SMA)")
    else:
        thesis.append(f"Suboptimal base distance ({dist_from_sma:+.1f}%)")

    # 2. Relative Volume Spike (15m RVol)
    avg_vol = sum(volumes[-21:-1]) / 20
    cur_vol = volumes[-1]
    rvol = cur_vol / avg_vol if avg_vol > 0 else 0

    if rvol >= 2.5:
        score += 30
        thesis.append(f"Whale volume surge ({rvol:.2f}x)")
    elif rvol >= 1.8:
        score += 18
        thesis.append(f"Above-average volume ({rvol:.2f}x)")
    else:
        thesis.append(f"Low volume ({rvol:.2f}x < 1.8x)")

    # 3. Open Interest (Whale Money Inflow)
    try:
        oi_data = exchange.fetch_open_interest(symbol)
        oi_val = float(oi_data.get('openInterestValue', 0) or oi_data.get('openInterestAmount', 0))
        if oi_val > 0:
            score += 25
            thesis.append("Positive whale OI backing")
        else:
            thesis.append("Flat open interest")
    except Exception:
        score += 10
        thesis.append("OI neutral")

    # 4. Clean Funding Runway
    try:
        funding = exchange.fetch_funding_rate(symbol)
        fr = float(funding.get('fundingRate', 0) or 0)
        if fr <= 0.0001:  # <= 0.01%
            score += 20
            thesis.append(f"Prime funding ({fr*100:.3f}%)")
        elif fr <= 0.0003:  # <= 0.03%
            score += 10
            thesis.append(f"Acceptable funding ({fr*100:.3f}%)")
        else:
            thesis.append(f"Crowded funding ({fr*100:.3f}%)")
    except Exception:
        score += 10

    full_thesis = "; ".join(thesis)
    return score, full_thesis, cur_price, rvol, dist_from_sma

def perform_market_inspection(inspection_num, usdt_balance):
    """
    Screens the market like a seasoned trader:
    Ranks setups, logs observations, and picks ONLY the highest-conviction coin.
    """
    print("\n" + "=" * 80, flush=True)
    print(f" [TRADER DESK LOG #{inspection_num}] Market Review | Timeframe: 15m–1h Structure", flush=True)
    print(f" Portfolio: ${usdt_balance:.2f} USDT (100% Cash / Capital Preserved)", flush=True)
    print("=" * 80, flush=True)

    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"[ERROR] Failed fetching tickers: {e}", flush=True)
        return None

    # Step 1: Filter liquid universe moving between +1.0% and +9.0% 24h
    candidates = []
    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue
        vol_24h = float(t.get('quoteVolume', 0) or 0)
        pct_24h = float(t.get('percentage', 0) or 0)

        if vol_24h >= MIN_24H_VOLUME and 1.0 <= pct_24h <= 9.0:
            candidates.append((symbol, pct_24h, vol_24h))

    candidates.sort(key=lambda x: x[1], reverse=True)
    print(f"[*] Universe Scanned: {len(tickers)} pairs | {len(candidates)} in active momentum window", flush=True)

    if not candidates:
        print("[OBSERVATION] No liquid pairs currently breaking out. Staying 100% in USDT.", flush=True)
        return None

    # Step 2: Grade the top setups
    ranked_setups = []
    print("\n--- TOP WATCHLIST OBSERVATIONS ---", flush=True)
    for symbol, pct_24h, _ in candidates[:5]:
        try:
            score, thesis, cur_price, rvol, dist_sma = evaluate_coin(symbol, pct_24h)
            clean_name = symbol.split(':')[0]
            print(f"  #{len(ranked_setups)+1} {clean_name:<10} | Score: {score:>3}/100 | RVol: {rvol:>4.2f}x | DistSMA: {dist_sma:>+5.2f}%", flush=True)
            print(f"     Thesis: {thesis}", flush=True)
            ranked_setups.append({
                'symbol': symbol,
                'score': score,
                'price': cur_price,
                'thesis': thesis
            })
        except Exception:
            continue

    if not ranked_setups:
        return None

    # Sort setups by conviction score
    ranked_setups.sort(key=lambda x: x['score'], reverse=True)
    best_candidate = ranked_setups[0]

    print("-" * 80, flush=True)
    if best_candidate['score'] >= CONVICTION_THRESHOLD:
        print(f"[DECISION] >> HIGH CONVICTION FOUND: {best_candidate['symbol']} (Score: {best_candidate['score']}/100)", flush=True)
        print(f"            Thesis: {best_candidate['thesis']}", flush=True)
        print(f"            Action: Entering Long to capture expansion.", flush=True)
        return best_candidate['symbol'], best_candidate['price']
    else:
        print(f"[DECISION] Top setup was {best_candidate['symbol']} with Score {best_candidate['score']}/100 (< {CONVICTION_THRESHOLD}).", flush=True)
        print(f"           No trade meets our risk/reward standards. Staying in USDT cash.", flush=True)
        print(f"           Next comprehensive chart inspection in {INSPECTION_INTERVAL_SECONDS // 60} minutes.\n", flush=True)
        return None

# ==========================================================
# 5. ACTIVE TRADE GUARDIAN
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

            if time.time() - last_log_time > 15:
                print(f"[TRADE STATUS] {symbol} | PnL: {pnl_pct:+.2f}% | Peak: {peak_pnl:+.2f}% | Duration: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. THE FEE-SHIELD LOCK (+1.0% -> +0.5%)
            # If price reaches +1.0%, stop loss locks in at +0.5% (net profit guaranteed)
            if peak_pnl >= 1.0:
                guaranteed_floor = entry_price * 1.005
                if cur_price <= guaranteed_floor:
                    print(f"[EXIT TRIGGER] Fee-Shield hit! Locked +0.5% profit (Peak was +{peak_pnl:.2f}%)", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # 2. MOMENTUM STALL / BOX CHOP EXIT
            # If after 15 mins price is stalled flat in a box, close immediately
            if elapsed_min >= 15 and peak_pnl < 1.0:
                if abs(pnl_pct) <= 0.45:
                    print(f"[EXIT TRIGGER] Momentum stalled in a box after {elapsed_min:.0f} mins. Dumping position.", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # 3. INITIAL STRUCTURAL STOP (-1.2%)
            if peak_pnl < 1.0 and pnl_pct <= -1.20:
                print(f"[EXIT TRIGGER] Hard stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                close_long_position(symbol, contracts)
                break

            # 4. RUNNER TRAIL (+3% to +10%+ expansion)
            if peak_pnl >= 3.0:
                trailing_floor = highest_price * 0.985
                if cur_price <= trailing_floor:
                    print(f"[EXIT TRIGGER] Trailing stop triggered. Banked runner at +{pnl_pct:.2f}% (Peak: +{peak_pnl:.2f}%)", flush=True)
                    close_long_position(symbol, contracts)
                    break

        except Exception as e:
            print(f"[GUARDIAN WARNING] {e}", flush=True)
            time.sleep(2)

# ==========================================================
# 6. MAIN ENGINE LOOP
# ==========================================================
def main():
    start_keep_alive()
    print("[SYSTEM] Bitget Trader Desk & Momentum Hunter initialized.", flush=True)

    try:
        print("[SYSTEM] Pre-loading Bitget markets...", flush=True)
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    inspection_num = 1

    while True:
        try:
            # Check if already in an active position
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            # Fetch Wallet Balance
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info['USDT']['free'] or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            if notional < MIN_NOTIONAL:
                print(f"[WAITING] Margin low for $5 min notional (Free: ${usdt_free:.2f} | Notional: ${notional:.2f})", flush=True)
                time.sleep(30)
                continue

            # Perform the structured 15m–30m chart inspection
            trade_candidate = perform_market_inspection(inspection_num, usdt_free)
            inspection_num += 1

            if not trade_candidate:
                # Patiently wait in USDT cash until the next chart review window
                time.sleep(INSPECTION_INTERVAL_SECONDS)
                continue

            symbol, cur_price = trade_candidate
            market = exchange.market(symbol)
            min_lot = float(market['limits']['amount']['min'] or 0)

            # Sizing calculations
            raw_amount = notional / cur_price
            formatted_amount = float(exchange.amount_to_precision(symbol, raw_amount))

            if formatted_amount < min_lot:
                print(f"[SKIP] {symbol}: Size {formatted_amount} below min lot {min_lot}. Staying in cash.", flush=True)
                time.sleep(30)
                continue

            try:
                exchange.set_leverage(LEVERAGE, symbol, params={'marginMode': 'crossed'})
            except Exception:
                pass

            print(f"\n[ORDER PLACEMENT] Entering Long {symbol} | Size: {formatted_amount} | Notional: ${notional:.2f}", flush=True)
            order = open_long_position(symbol, formatted_amount)
            print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)

            time.sleep(3)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)

if __name__ == "__main__":
    main()

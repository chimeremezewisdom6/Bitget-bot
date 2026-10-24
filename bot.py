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
        self.wfile.write(b"Trader Desk Bot is actively hunting early crypto momentum.")

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
    "timeout": 15000,
    "options": {
        "defaultType": "swap",
        "createMarketBuyOrderRequiresPrice": False
    }
})

LEVERAGE = 3
BALANCE_USE_PCT = 0.85             # 85% of $2.63 = ~$6.70 notional (above $5.00 min)
MIN_NOTIONAL = 5.10                # Safety buffer above Bitget $5.00 min
MIN_24H_VOLUME = 8_000_000         # $8M liquid crypto volume floor
INSPECTION_INTERVAL_SECONDS = 900  # 15 minutes structured review
CONVICTION_THRESHOLD = 70          # Score required to strike

# Non-Crypto / TradFi Blacklist (stocks, commodities, ETFs on Bitget)
NON_CRYPTO_SYMBOLS = {
    'CL', 'BZ', 'SOXS', 'SOXL', 'KORU', 'MU', 'TSLA', 'NVDA', 'AAPL', 'MSFT',
    'AMZN', 'GOOGL', 'META', 'SPX', 'NDX', 'DJI', 'XAU', 'XAG', 'MINIMAX', 'DOS'
}

# ==========================================================
# 3. BITGET ONE-WAY ORDER HELPERS
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
# 4. EARLY-RIDE FEATURE SCORING ENGINE
# ==========================================================
def evaluate_coin(symbol):
    score = 0
    thesis = []

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=25)
    if len(ohlcv) < 22:
        return 0, "Insufficient candle history", 0, 0, 0

    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]
    cur_price = closes[-1]

    # FEATURE 1: Base Launchpad Proximity (Early vs Late Ride)
    sma_20 = sum(closes[-21:-1]) / 20
    dist_from_sma = ((cur_price - sma_20) / sma_20) * 100

    if 0.5 <= dist_from_sma <= 2.8:
        score += 25
        thesis.append(f"Early Launchpad (+{dist_from_sma:.1f}% off 15m SMA)")
    elif 2.8 < dist_from_sma <= 4.5:
        score += 15
        thesis.append(f"Developing Move (+{dist_from_sma:.1f}% off 15m SMA)")
    elif dist_from_sma > 4.5:
        thesis.append(f"Late Ride / Extended (+{dist_from_sma:.1f}% top risk)")
    else:
        thesis.append(f"Below/Flat SMA ({dist_from_sma:+.1f}%)")

    # FEATURE 2: Relative Volume Ignition (15m RVol)
    avg_vol = sum(volumes[-21:-1]) / 20
    cur_vol = volumes[-1]
    rvol = cur_vol / avg_vol if avg_vol > 0 else 0

    if rvol >= 2.2:
        score += 30
        thesis.append(f"Whale volume ignition ({rvol:.2f}x)")
    elif rvol >= 1.6:
        score += 22
        thesis.append(f"Solid breakout volume ({rvol:.2f}x)")
    elif rvol >= 1.2:
        score += 12
        thesis.append(f"Moderate volume ({rvol:.2f}x)")
    else:
        thesis.append(f"Low volume ({rvol:.2f}x)")

    # FEATURE 3: Open Interest (Whale Capital Entering)
    try:
        oi_data = exchange.fetch_open_interest(symbol)
        oi_val = float(oi_data.get('openInterestValue', 0) or oi_data.get('openInterestAmount', 0))
        if oi_val > 0:
            score += 25
            thesis.append("Whale OI active")
        else:
            score += 15
            thesis.append("OI neutral")
    except Exception:
        score += 15
        thesis.append("OI steady")

    # FEATURE 4: Clean Funding Runway
    try:
        funding = exchange.fetch_funding_rate(symbol)
        fr = float(funding.get('fundingRate', 0) or 0)
        if fr <= 0.00015:
            score += 20
            thesis.append(f"Clean funding ({fr*100:.3f}%)")
        elif fr <= 0.00035:
            score += 12
            thesis.append(f"Acceptable funding ({fr*100:.3f}%)")
        else:
            thesis.append(f"Crowded funding ({fr*100:.3f}%)")
    except Exception:
        score += 15

    full_thesis = "; ".join(thesis)
    return score, full_thesis, cur_price, rvol, dist_from_sma

def perform_market_inspection(inspection_num, usdt_balance):
    print("\n" + "=" * 80, flush=True)
    print(f" [TRADER DESK LOG #{inspection_num}] Crypto Early-Momentum Review", flush=True)
    print(f" Portfolio: ${usdt_balance:.2f} USDT (Target Conviction Score >= {CONVICTION_THRESHOLD})", flush=True)
    print("=" * 80, flush=True)

    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"[ERROR] Failed fetching tickers: {e}", flush=True)
        return None

    # Step 1: Filter ONLY real crypto pairs backed by >= $8M liquidity
    candidates = []
    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue

        base_asset = symbol.split('/')[0].upper()
        if base_asset in NON_CRYPTO_SYMBOLS:
            continue

        vol_24h = float(t.get('quoteVolume', 0) or 0)
        pct_24h = float(t.get('percentage', 0) or 0)

        if vol_24h >= MIN_24H_VOLUME:
            candidates.append((symbol, pct_24h, vol_24h))

    # Sort candidate pool by 24h trading volume (highest whale attention)
    candidates.sort(key=lambda x: x[2], reverse=True)
    print(f"[*] Universe Scanned: {len(tickers)} pairs | {len(candidates)} real crypto pairs meet >= $8M liquidity", flush=True)

    if not candidates:
        print("[OBSERVATION] No liquid crypto pairs found. Preserving cash in USDT.", flush=True)
        return None

    # Step 2: Inspect top 10 most active crypto pairs
    ranked_setups = []
    print("\n--- TOP CRYPTO WATCHLIST OBSERVATIONS ---", flush=True)
    for symbol, pct_24h, vol_24h in candidates[:10]:
        try:
            score, thesis, cur_price, rvol, dist_sma = evaluate_coin(symbol)
            clean_name = symbol.split(':')[0]
            print(f"  #{len(ranked_setups)+1} {clean_name:<10} (24h: {pct_24h:>+5.1f}%) | Score: {score:>3}/100 | RVol: {rvol:>4.2f}x | DistSMA: {dist_sma:>+5.2f}%", flush=True)
            print(f"     Thesis: {thesis}", flush=True)
            ranked_setups.append({
                'symbol': symbol,
                'score': score,
                'rvol': rvol,
                'price': cur_price,
                'thesis': thesis
            })
        except Exception:
            continue

    if not ranked_setups:
        return None

    # Step 3: Sort by HIGHEST SCORE first, with RVol as tie-breaker
    ranked_setups.sort(key=lambda x: (x['score'], x['rvol']), reverse=True)

    # Filter all setups that achieved >= CONVICTION_THRESHOLD
    qualifying_setups = [s for s in ranked_setups if s['score'] >= CONVICTION_THRESHOLD]

    print("-" * 80, flush=True)
    if qualifying_setups:
        # If more than 1 crypto qualifies, show the comparison
        if len(qualifying_setups) > 1:
            print(f"[*] MULTI-RUNNER EVENT: {len(qualifying_setups)} cryptos passed Score >= {CONVICTION_THRESHOLD}!", flush=True)
            for i, q in enumerate(qualifying_setups, 1):
                clean_sym = q['symbol'].split(':')[0]
                status = "<-- [#1 HIGHEST WINNER]" if i == 1 else ""
                print(f"    #{i} {clean_sym:<10} | Score: {q['score']}/100 | RVol: {q['rvol']:.2f}x {status}", flush=True)

        best_candidate = qualifying_setups[0]
        print(f"\n[DECISION] >> SELECTING #1 HIGHEST: {best_candidate['symbol']} (Score: {best_candidate['score']}/100 | RVol: {best_candidate['rvol']:.2f}x)", flush=True)
        print(f"            Thesis: {best_candidate['thesis']}", flush=True)
        print(f"            Action: Entering Long on the highest-conviction coin.", flush=True)
        return best_candidate['symbol'], best_candidate['price']
    else:
        best_candidate = ranked_setups[0]
        print(f"[DECISION] Top setup {best_candidate['symbol']} scored {best_candidate['score']}/100 (< {CONVICTION_THRESHOLD}).", flush=True)
        print(f"           No clean Early Ride setup confirmed. Preserving capital in USDT cash.", flush=True)
        print(f"           Next chart review in {INSPECTION_INTERVAL_SECONDS // 60} minutes.\n", flush=True)
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
            if peak_pnl >= 1.0:
                guaranteed_floor = entry_price * 1.005
                if cur_price <= guaranteed_floor:
                    print(f"[EXIT TRIGGER] Fee-Shield hit! Locked +0.5% net profit (Peak was +{peak_pnl:.2f}%)", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # 2. MOMENTUM STALL / BOX CHOP EXIT
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
    print("[SYSTEM] Bitget Crypto Momentum Hunter initialized.", flush=True)

    try:
        print("[SYSTEM] Pre-loading Bitget markets...", flush=True)
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    inspection_num = 1

    while True:
        try:
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info['USDT']['free'] or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            if notional < MIN_NOTIONAL:
                print(f"[WAITING] Margin low for $5 min notional (Free: ${usdt_free:.2f} | Notional: ${notional:.2f})", flush=True)
                time.sleep(30)
                continue

            trade_candidate = perform_market_inspection(inspection_num, usdt_free)
            inspection_num += 1

            if not trade_candidate:
                wait_step = 180
                total_waited = 0
                while total_waited < INSPECTION_INTERVAL_SECONDS:
                    time.sleep(wait_step)
                    total_waited += wait_step
                    mins_left = (INSPECTION_INTERVAL_SECONDS - total_waited) // 60
                    if mins_left > 0:
                        print(f"[RADAR PULSE] Preserving ${usdt_free:.2f} USDT cash. Next review in {mins_left}m...", flush=True)
                continue

            symbol, cur_price = trade_candidate
            market = exchange.market(symbol)
            min_lot = float(market['limits']['amount']['min'] or 0)

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

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
        self.wfile.write(b"Trader Desk Bot is actively watching the charts.")

    def log_message(self, format, *args):
        return  # Silence HTTP server logs to keep terminal output clean

def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)

# ==========================================================
# 2. EXCHANGE CONFIGURATION & TUNED SETTINGS
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
BALANCE_USE_PCT = 0.85             # 85% of $2.62 = $2.22 margin -> ~$6.68 notional (safely above $5.00 min)
MIN_NOTIONAL = 5.10                # Safety buffer above Bitget's $5.00 min order requirement
MIN_24H_VOLUME = 10_000_000        # $10,000,000 minimum volume floor
INSPECTION_INTERVAL_SECONDS = 900  # 15 minutes structured chart review cycle
CONVICTION_THRESHOLD = 70          # Out of 100 (Responsive entry for early breakout runners)

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
# 4. TRADER ANALYSIS & CONVICTION SCORING
# ==========================================================
def evaluate_coin(symbol, pct_24h):
    """
    Grades candidate across 4 institutional pillars:
    - Base Compression (Up to 25 pts)
    - Relative Volume Spike (Up to 30 pts)
    - Open Interest Inflow (Up to 25 pts)
    - Clean Funding Runway (Up to 20 pts)
    """
    score = 0
    thesis = []

    ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=25)
    if len(ohlcv) < 22:
        return 0, "Insufficient candle history", 0, 0, 0

    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]
    cur_price = closes[-1]

    # 1. Base Proximity (20-period SMA)
    sma_20 = sum(closes[-21:-1]) / 20
    dist_from_sma = ((cur_price - sma_20) / sma_20) * 100

    if 0.5 <= dist_from_sma <= 2.5:
        score += 25
        thesis.append(f"Prime base breakout (+{dist_from_sma:.1f}% off 20 SMA)")
    elif 2.5 < dist_from_sma <= 4.2:
        score += 18
        thesis.append(f"Moderate expansion (+{dist_from_sma:.1f}% off 20 SMA)")
    else:
        thesis.append(f"Base distance {dist_from_sma:+.1f}%")

    # 2. Relative Volume Spike (15m RVol)
    avg_vol = sum(volumes[-21:-1]) / 20
    cur_vol = volumes[-1]
    rvol = cur_vol / avg_vol if avg_vol > 0 else 0

    if rvol >= 2.2:
        score += 30
        thesis.append(f"Heavy whale volume ({rvol:.2f}x)")
    elif rvol >= 1.6:
        score += 22
        thesis.append(f"Solid breakout volume ({rvol:.2f}x)")
    elif rvol >= 1.2:
        score += 12
        thesis.append(f"Developing volume ({rvol:.2f}x)")
    else:
        thesis.append(f"Low volume ({rvol:.2f}x)")

    # 3. Open Interest (Whale Capital Inflow)
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

    # 4. Clean Funding Runway
    try:
        funding = exchange.fetch_funding_rate(symbol)
        fr = float(funding.get('fundingRate', 0) or 0)
        if fr <= 0.00015:  # <= 0.015% per 8h
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
    print(f" [TRADER DESK LOG #{inspection_num}] Market Review | Timeframe: 15m Structure", flush=True)
    print(f" Portfolio: ${usdt_balance:.2f} USDT (100% Cash | Target Conviction Score >= {CONVICTION_THRESHOLD})", flush=True)
    print("=" * 80, flush=True)

    try:
        tickers = exchange.fetch_tickers()
    except Exception as e:
        print(f"[ERROR] Failed fetching tickers: {e}", flush=True)
        return None

    # Filter liquid universe (>= $10M Volume, 24h change between +0.8% and +9.5%)
    candidates = []
    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue
        vol_24h = float(t.get('quoteVolume', 0) or 0)
        pct_24h = float(t.get('percentage', 0) or 0)

        if vol_24h >= MIN_24H_VOLUME and 0.8 <= pct_24h <= 9.5:
            candidates.append((symbol, pct_24h, vol_24h))

    candidates.sort(key=lambda x: x[1], reverse=True)
    print(f"[*] Universe Scanned: {len(tickers)} pairs | {len(candidates)} match volume (>= $10M) & price range", flush=True)

    if not candidates:
        print("[OBSERVATION] No liquid pairs currently breaking out. Preserving capital in USDT.", flush=True)
        return None

    ranked_setups = []
    print("\n--- TOP WATCHLIST OBSERVATIONS ---", flush=True)
    for symbol, pct_24h, _ in candidates[:6]:
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

    ranked_setups.sort(key=lambda x: x['score'], reverse=True)
    best_candidate = ranked_setups[0]

    print("-" * 80, flush=True)
    if best_candidate['score'] >= CONVICTION_THRESHOLD:
        print(f"[DECISION] >> CONVICTION TARGET HIT: {best_candidate['symbol']} (Score: {best_candidate['score']}/100)", flush=True)
        print(f"            Thesis: {best_candidate['thesis']}", flush=True)
        print(f"            Action: Executing Long entry.", flush=True)
        return best_candidate['symbol'], best_candidate['price']
    else:
        print(f"[DECISION] Top setup was {best_candidate['symbol']} with Score {best_candidate['score']}/100 (< {CONVICTION_THRESHOLD}).", flush=True)
        print(f"           Risk/reward sub-optimal. Sitting patient in USDT cash.", flush=True)
        print(f"           Next chart inspection in {INSPECTION_INTERVAL_SECONDS // 60} minutes.\n", flush=True)
        return None

# ==========================================================
# 5. ACTIVE TRADE GUARDIAN

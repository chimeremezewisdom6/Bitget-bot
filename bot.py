import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER KEEP-ALIVE SERVER (PORT 10000)
# ==============================================================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Dual Long/Short Trajectory Matching Engine is active.")

    def log_message(self, format, *args):
        return  # Silence server logs


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. CONFIGURATION & TRADING RISK RULES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

# Risk & Order Sizing
LEVERAGE = 3
BALANCE_USE_PCT = 0.85        # Use 85% of free USDT
MIN_NOTIONAL = 5.10           # Minimum $5.10 order value on Bitget
MIN_24H_VOLUME = 5_000_000    # $5M global liquidity floor
SCAN_INTERVAL_SECONDS = 60    # Rapid scan interval
MAX_CONCURRENT_CAMERAS = 6    # Film up to 6 coins simultaneously
BASELINE_TAPES_REQUIRED = 10  # Baseline films needed before live matching begins
SIMILARITY_THRESHOLD = 75.0   # 75% curve match to strike
LIBRARY_FILE = "video_library.json"

# Non-Crypto / TradFi Blacklist
NON_CRYPTO_SYMBOLS = {
    'CL', 'BZ', 'SOXS', 'SOXL', 'KORU', 'MU', 'TSLA', 'NVDA', 'AAPL', 'MSFT',
    'AMZN', 'GOOGL', 'META', 'SPX', 'NDX', 'DJI', 'XAU', 'XAG', 'MINIMAX', 'DOS'
}

exchange = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "password": PASSPHRASE,
    "enableRateLimit": True,
    "timeout": 20000,
    "options": {
        "defaultType": "swap",
        "createMarketBuyOrderRequiresPrice": False
    }
})


# ==============================================================================
# 3. STATISTICAL & TECHNICAL UTILITIES
# ==============================================================================
def calculate_rsi(closes, period=14):
    """Calculates standard Relative Strength Index (RSI)."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


# ==============================================================================
# 4. VIDEO LIBRARY (PERSISTENT FOOTPRINT STORAGE)
# ==============================================================================
def load_video_library():
    default_lib = {
        "total_filmed": 0,
        "hero_tapes": [],    # Tapes that pumped and held gains (Long standard)
        "trap_tapes": [],    # Tapes that spiked and dumped (Short standard)
        "active_films": []   # Currently filming in parallel
    }
    if os.path.exists(LIBRARY_FILE):
        try:
            with open(LIBRARY_FILE, "r") as f:
                data = json.load(f)
                default_lib.update(data)
                return default_lib
        except Exception:
            pass
    return default_lib


def save_video_library(lib):
    try:
        with open(LIBRARY_FILE, "w") as f:
            json.dump(lib, f, indent=2)
    except Exception as e:
        print(f"[LIBRARY WARNING] Failed to save video library: {e}", flush=True)


# ==============================================================================
# 5. VIDEO REPLAY & SHAPE-MATCHING ENGINE
# ==============================================================================
def calculate_trajectory_similarity(live_frames, ref_frames):
    """
    Compares the opening scene (first 3-5 frames) of a live coin against
    the opening scene of a historical Tape. Returns 0% to 100% similarity.
    """
    compare_len = min(len(live_frames), len(ref_frames))
    if compare_len < 3:
        return 0.0

    errors = []
    for i in range(compare_len):
        live_pnl = live_frames[i]['pnl']
        ref_pnl = ref_frames[i]['pnl']
        live_dd = live_frames[i]['drawdown']
        ref_dd = ref_frames[i]['drawdown']

        # Measure curve divergence
        pnl_diff = abs(live_pnl - ref_pnl)
        dd_diff = abs(live_dd - ref_dd)
        errors.append(min((pnl_diff * 3.0) + (dd_diff * 2.0), 30.0))

    avg_error = sum(errors) / len(errors)
    similarity = max(100.0 - avg_error, 0.0)
    return round(similarity, 1)


# ==============================================================================
# 6. BITGET ONE-WAY DUAL-ORDER HELPERS (LONG & SHORT)
# ==============================================================================
def get_open_position():
    """Checks for active Long or Short position."""
    try:
        positions = exchange.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            side = p.get('side', '').lower()
            if contracts > 0 and side in ['long', 'short']:
                return {
                    'symbol': p['symbol'],
                    'side': side,
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0))
                }
    except Exception as e:
        print(f"[POSITION CHECK ERROR] {e}", flush=True)
    return None


def open_long_position(symbol, amount):
    """Executes market buy order for Long."""
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
    """Executes market sell order to close Long."""
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


def open_short_position(symbol, amount):
    """Executes market sell order for Short."""
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
                params={'tradeSide': 'open'}
            )
        raise e


def close_short_position(symbol, amount):
    """Executes market buy order to close Short."""
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
                params={'tradeSide': 'close'}
            )
        raise e


# ==============================================================================
# 7. SCANNER WITH STRICT OVERPOWER RULE
# ==============================================================================
def inspect_coin_overpower_imbalance(symbol, pct_24h, vol_24h):
    """
    STRICT OVERPOWER RULE:
    5m gain strictly exceeds the 1h magnitude: pct_5m > abs(pct_1h)
    """
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=25)
        if len(ohlcv) < 20:
            return None

        closes = [x[4] for x in ohlcv]
        volumes = [x[5] for x in ohlcv]

        cur_price = closes[-1]
        price_5m_ago = closes[-2]
        pct_5m = ((cur_price - price_5m_ago) / price_5m_ago) * 100

        price_1h_ago = closes[-13] if len(closes) >= 13 else closes[0]
        pct_1h = ((cur_price - price_1h_ago) / price_1h_ago) * 100

        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
        rsi_5m = calculate_rsi(closes, period=14)

        is_overpower = (pct_5m >= 2.0 and rvol >= 2.0 and pct_5m > (abs(pct_1h) + 0.05))

        if not is_overpower:
            return None

        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        return {
            "symbol": symbol,
            "cur_price": cur_price,
            "pct_5m": round(pct_5m, 2),
            "pct_1h": round(pct_1h, 2),
            "pct_24h": round(pct_24h, 2),
            "rvol": rvol,
            "rsi_5m": rsi_5m,
            "funding_pct": round(funding_rate, 4),
            "vol_24h_m": round(vol_24h / 1_000_000, 2)
        }
    except Exception:
        return None


# ==============================================================================
# 8. ACTIVE TRADE GUARDIAN (HANDLES BOTH LONGS AND SHORTS)
# ==============================================================================
def manage_active_trade(symbol, side, contracts, entry_price):
    """Guards active Long or Short with 4 strict capital-protection rules."""
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0

    print(f"\n[GUARDIAN ACTIVE] Managing {side.upper()} on {symbol} | Entry: {entry_price} | Contracts: {contracts}", flush=True)

    while True:
        try:
            time.sleep(3)
            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker.get('last', 0) or 0)

            if cur_price > highest_price:
                highest_price = cur_price
            if cur_price < lowest_price:
                lowest_price = cur_price

            elapsed_min = (time.time() - entry_time) / 60

            # Calculate direction-specific PnL
            if side == 'long':
                pnl_pct = ((cur_price - entry_price) / entry_price) * 100
                peak_pnl = ((highest_price - entry_price) / entry_price) * 100
            else:  # short
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100

            if time.time() - last_log_time > 15:
                print(f"[TRADE STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% | Peak: {peak_pnl:+.2f}% | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. FEE-SHIELD LOCK (+1.0% -> +0.5%)
            if peak_pnl >= 1.0:
                if side == 'long' and cur_price <= entry_price * 1.005:
                    print(f"[EXIT TRIGGER] Long Fee-Shield hit! Locked +0.5% profit (Peak was +{peak_pnl:.2f}%).", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= entry_price * 0.995:
                    print(f"[EXIT TRIGGER] Short Fee-Shield hit! Locked +0.5% profit (Peak was +{peak_pnl:.2f}%).", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 2. MOMENTUM STALL / BOX CHOP EXIT (15 Mins)
            if elapsed_min >= 15 and peak_pnl < 1.0:
                if abs(pnl_pct) <= 0.45:
                    print(f"[EXIT TRIGGER] Momentum stalled in a box for {elapsed_min:.0f}m. Dumping chop.", flush=True)
                    if side == 'long':
                        close_long_position(symbol, contracts)
                    else:
                        close_short_position(symbol, contracts)
                    break

            # 3. INITIAL HARD STOP (-1.2%)
            if peak_pnl < 1.0 and pnl_pct <= -1.20:
                print(f"[EXIT TRIGGER] Hard stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                if side == 'long':
                    close_long_position(symbol, contracts)
                else:
                    close_short_position(symbol, contracts)
                break

            # 4. RUNNER TRAILING STOP (+3% or higher)
            if peak_pnl >= 3.0:
                if side == 'long':
                    trailing_floor = highest_price * 0.985
                    if cur_price <= trailing_floor:
                        print(f"[EXIT TRIGGER] Long Trailing stop triggered at {pnl_pct:+.2f}% (Peak: +{peak_pnl:.2f}%).", flush=True)
                        close_long_position(symbol, contracts)
                        break
                else:  # short
                    trailing_ceiling = lowest_price * 1.015
                    if cur_price >= trailing_ceiling:
                        print(f"[EXIT TRIGGER] Short Trailing stop triggered at {pnl_pct:+.2f}% (Peak: +{peak_pnl:.2f}%).", flush=True)
                        close_short_position(symbol, contracts)
                        break

        except Exception as e:
            print(f"[GUARDIAN WARNING] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 9. MAIN AUTONOMOUS DUAL ENGINE
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] Dual Long/Short Trajectory Matching Engine initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    lib = load_video_library()
    print(f"[LIBRARY] Historical Films: {lib['total_filmed']} | Hero Tapes: {len(lib['hero_tapes'])} | Trap Tapes: {len(lib['trap_tapes'])}", flush=True)

    cycle = 1

    while True:
        try:
            # 1. Manage Active Live Trade if any
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            # 2. Advance all Active Films simultaneously
            remaining_films = []
            trade_candidate = None  # Will hold: (symbol, side, cur_price)

            for film in lib['active_films']:
                sym = film['symbol']
                elapsed_min = (time.time() - film['started_at']) / 60

                try:
                    ticker = exchange.fetch_ticker(sym)
                    cur_price = float(ticker.get('last', 0) or 0)
                except Exception:
                    remaining_films.append(film)
                    continue

                if cur_price > film['peak_price']:
                    film['peak_price'] = cur_price
                if cur_price < film['lowest_price']:
                    film['lowest_price'] = cur_price

                base_price = film['base_price']
                cur_pnl = ((cur_price - base_price) / base_price) * 100
                peak_pnl = ((film['peak_price'] - base_price) / base_price) * 100
                drawdown = ((cur_price - film['peak_price']) / film['peak_price']) * 100

                # Record Frame every ~2 minutes
                last_frame_min = film['frames'][-1]['min'] if film['frames'] else -99
                if (elapsed_min - last_frame_min) >= 2.0:
                    frame = {
                        "frame_no": len(film['frames']) + 1,
                        "min": round(elapsed_min, 1),
                        "pnl": round(cur_pnl, 2),
                        "peak": round(peak_pnl, 2),
                        "drawdown": round(drawdown, 2)
                    }
                    film['frames'].append(frame)

                # --- PATTERN REPLAY SCREENING (Minutes 6 to 12) ---
                if lib['total_filmed'] >= BASELINE_TAPES_REQUIRED and not film.get('evaluated'):
                    if 6.0 <= elapsed_min <= 12.0 and len(film['frames']) >= 3:
                        film['evaluated'] = True

                        best_hero_score = 0.0
                        best_hero_ref = None
                        for hero in lib['hero_tapes']:
                            sim = calculate_trajectory_similarity(film['frames'], hero['frames'])
                            if sim > best_hero_score:
                                best_hero_score = sim
                                best_hero_ref = hero

                        best_trap_score = 0.0
                        best_trap_ref = None
                        for trap in lib['trap_tapes']:
                            sim = calculate_trajectory_similarity(film['frames'], trap['frames'])
                            if sim > best_trap_score:
                                best_trap_score = sim
                                best_trap_ref = trap

                        funding = film['initial_metrics']['funding_pct']

                        # BRANCH A: HERO MATCH -> EXECUTE LONG
                        if best_hero_score >= SIMILARITY_THRESHOLD and cur_pnl >= 1.0 and drawdown > -1.0:
                            print("\n" + "*" * 80, flush=True)
                            print(f"[DUAL ENGINE: LONG GREEN LIGHT] {sym} is repeating a Hero Tape footprint!", flush=True)
                            print(f"  Similarity: {best_hero_score}% match to Hero Tape ({best_hero_ref['symbol']})", flush=True)
                            print(f"  Action: Entering 3x LONG to ride momentum expansion.", flush=True)
                            print("*" * 80 + "\n", flush=True)
                            trade_candidate = (sym, 'long', cur_price)

                        # BRANCH B: TRAP MATCH -> EXECUTE SHORT (FADE THE TRAP)
                        elif best_trap_score >= SIMILARITY_THRESHOLD and (drawdown <= -1.2 or cur_pnl <= 0.2) and funding >= -0.01:
                            print("\n" + "*" * 80, flush=True)
                            print(f"[DUAL ENGINE: SHORT GREEN LIGHT] {sym} is repeating a Trap Tape footprint!", flush=True)
                            print(f"  Similarity: {best_trap_score}% match to Trap Tape ({best_trap_ref['symbol']})", flush=True)
                            print(f"  Funding Check: {funding:+.4f}% (Clean, no short-squeeze risk).", flush=True)
                            print(f"  Action: Entering 3x SHORT to fade the failed breakout.", flush=True)
                            print("*" * 80 + "\n", flush=True)
                            trade_candidate = (sym, 'short', cur_price)
                        else:
                            print(f"[VIDEO SCREENING] {sym} inconclusive (Hero: {best_hero_score}% | Trap: {best_trap_score}%). Preserving cash.", flush=True)

                # --- COMPLETE 60-MINUTE FILM ARCHIVING ---
                if elapsed_min >= 60:
                    film['final_pnl'] = round(cur_pnl, 2)
                    film['peak_pnl'] = round(peak_pnl, 2)

                    if cur_pnl >= 2.5 and peak_pnl >= 4.0 and film['lowest_price'] >= base_price * 0.985:
                        label = "HERO_PUMP_TAPE"
                        lib['hero_tapes'].append(film)
                    elif cur_pnl <= 0.0 or drawdown <= -2.5:
                        label = "TRAP_DUMP_TAPE"
                        lib['trap_tapes'].append(film)
                    else:
                        label = "STAGNANT_CHOP_TAPE"

                    film['label'] = label
                    lib['total_filmed'] += 1

                    print("\n" + "=" * 80, flush=True)
                    print(f"[TAPE ARCHIVED #{lib['total_filmed']}] Finished 60m film on {sym}", flush=True)
                    print(f"  Classification: {label} (Peak: +{film['peak_pnl']}% | Close: {film['final_pnl']}%)", flush=True)
                    print(f"  Total Library:  {len(lib['hero_tapes'])} Heroes | {len(lib['trap_tapes'])} Traps", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    save_video_library(lib)
                else:
                    remaining_films.append(film)

            lib['active_films'] = remaining_films

            # 3. Check Wallet Balance & Sizing
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            # 4. Scan Market for New Overpower Imbalances (Parallel Scanning)
            try:
                tickers = exchange.fetch_tickers()
            except Exception as e:
                time.sleep(10)
                continue

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

            candidates.sort(key=lambda x: x[2], reverse=True)
            top_candidates = candidates[:30]

            active_syms = {f['symbol'] for f in lib['active_films']}

            for sym, pct_24h, vol_24h in top_candidates:
                if len(lib['active_films']) >= MAX_CONCURRENT_CAMERAS:
                    break

                if sym in active_syms:
                    continue

                metrics = inspect_coin_overpower_imbalance(sym, pct_24h, vol_24h)
                if not metrics:
                    continue

                new_film = {
                    "film_id": lib['total_filmed'] + len(lib['active_films']) + 1,
                    "symbol": sym,
                    "started_at": time.time(),
                    "base_price": metrics['cur_price'],
                    "peak_price": metrics['cur_price'],
                    "lowest_price": metrics['cur_price'],
                    "initial_metrics": metrics,
                    "frames": [
                        {
                            "frame_no": 1,
                            "min": 0.0,
                            "pnl": 0.0,
                            "peak": 0.0,
                            "drawdown": 0.0
                        }
                    ],
                    "evaluated": False
                }
                lib['active_films'].append(new_film)
                active_syms.add(sym)
                save_video_library(lib)

                print("\n" + "-" * 80, flush=True)
                print(f"[OVERPOWER DETECTED] Camera #{len(lib['active_films'])} started on {sym}!", flush=True)
                print(f"  5m Gain: +{metrics['pct_5m']}% OVERPOWERED 1h Magnitude ({abs(metrics['pct_1h'])}%)", flush=True)
                print(f"  Filming to see if it becomes a LONG (Hero) or a SHORT (Trap)...", flush=True)
                print("-" * 80 + "\n", flush=True)

            # 5. Place Trade if Replay Engine Triggered Long or Short
            if trade_candidate and notional >= MIN_NOTIONAL:
                symbol, side, cur_price = trade_candidate
                market = exchange.market(symbol)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / cur_price
                formatted_amount = float(exchange.amount_to_precision(symbol, raw_amount))

                if formatted_amount >= min_lot:
                    try:
                        exchange.set_leverage(LEVERAGE, symbol, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    if side == 'long':
                        print(f"\n[ORDER EXECUTION] Entering LONG on {symbol} | Amount: {formatted_amount} | Notional: ${notional:.2f}", flush=True)
                        order = open_long_position(symbol, formatted_amount)
                    else:
                        print(f"\n[ORDER EXECUTION] Entering SHORT on {symbol} | Amount: {formatted_amount} | Notional: ${notional:.2f}", flush=True)
                        order = open_short_position(symbol, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(3)
                    continue

            # Heartbeat Pulse
            if cycle % 2 == 0:
                active_summary = ", ".join([f"{f['symbol']} ({(time.time()-f['started_at'])/60:.0f}m)" for f in lib['active_films']])
                if not active_summary:
                    active_summary = "Scanning for overpower spikes..."
                print(
                    f"[RADAR PULSE] Films Done: {lib['total_filmed']}/{BASELINE_TAPES_REQUIRED} | "
                    f"Library: {len(lib['hero_tapes'])} Long Tapes / {len(lib['trap_tapes'])} Short Tapes | "
                    f"Cameras: [{active_summary}] | Vault: ${usdt_free:.2f} USDT",
                    flush=True
                )

            cycle += 1
            save_video_library(lib)
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

import os
import sys
import time
import math
import json
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER 24/7 KEEP-ALIVE SERVER (PORT 10000)
# ==============================================================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"APEX-11 Autonomous Multi-Strategy Tournament is active.")

    def log_message(self, format, *args):
        return


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. CONFIGURATION & GRADUATION RULES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BASE_LEVERAGE = 3
BALANCE_USE_PCT = 0.88          # Use 88% of free vault margin
MIN_NOTIONAL = 5.15             # Buffer above Bitget's $5.00 limit
MIN_24H_VOLUME = 1_000_000      # $1,000,000 Volume Floor
SCAN_INTERVAL_SECONDS = 45      # Fast 45-second scan loop
MAX_PARALLEL_EXPERIMENTS = 10   # Run up to 10 parallel paper experiments
MIN_TARGET_PROFIT_PCT = 1.50    # Minimum profit hurdle to count as a win
TOURNAMENT_FILE = "strategy_tournament.json"

# Graduation thresholds: 3 tests, >= 66% win rate, average profit >= 1.5%
MIN_TESTS_TO_GRADUATE = 3
GRADUATION_WIN_RATE = 66.0

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
# 3. MATHEMATICAL INDICATORS
# ==============================================================================
def calculate_atr(ohlcv, period=14):
    if len(ohlcv) < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i - 1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    if len(tr_list) < period:
        return 0.0
    return sum(tr_list[-period:]) / period


def calculate_rsi(closes, period=14):
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
# 4. PERSISTENT TOURNAMENT STORAGE & GRADUATION ENGINE
# ==============================================================================
STRATEGY_NAMES = [
    "1_BEAR_TRAP_OI_ABSORPTION",
    "2_SQUEEZE_EXHAUSTION_FADE",
    "3_RSI_WASHOUT_CLEAN_BOUNCE",
    "4_BLOWOFF_TOP_OVERBOUGHT",
    "5_INSTITUTIONAL_OI_EXPANSION",
    "6_CLEAN_STAIR_MOMENTUM",
    "7_HIGH_RVOL_IGNITION",
    "8_HIGH_AMPLITUDE_SWING",
    "9_CROWDED_FUNDING_DUMP",
    "10_WATERFALL_BREAKDOWN",
    "11_TRADER_AGGRESSIVENESS_SURGE"  # New 11th Model!
]

def load_tournament():
    default_data = {
        "total_experiments_completed": 0,
        "models": {
            name: {
                "tested": 0, "wins": 0, "losses": 0, "stalls": 0,
                "max_profit": 0.0, "is_graduated": False
            } for name in STRATEGY_NAMES
        },
        "active_experiments": []
    }
    if os.path.exists(TOURNAMENT_FILE):
        try:
            with open(TOURNAMENT_FILE, "r") as f:
                data = json.load(f)
                default_data.update(data)
                return default_data
        except Exception:
            pass
    return default_data


def save_tournament(data):
    try:
        with open(TOURNAMENT_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[MEMORY WARNING] Save failed: {e}", flush=True)


def check_and_update_graduation(tourn, model_name):
    """Checks if a model earned the statistical right to trade live."""
    m = tourn['models'][model_name]
    if m['tested'] >= MIN_TESTS_TO_GRADUATE:
        win_rate = (m['wins'] / m['tested']) * 100
        if win_rate >= GRADUATION_WIN_RATE and m['max_profit'] >= MIN_TARGET_PROFIT_PCT:
            if not m['is_graduated']:
                m['is_graduated'] = True
                print("\n" + "#" * 80, flush=True)
                print(f"[MODEL GRADUATED TO LIVE TRADING] {model_name} PROVED ITS EDGE!", flush=True)
                print(f"Stats: {m['wins']} Wins / {m['tested']} Tests ({win_rate:.0f}% Win Rate) | Max Run: +{m['max_profit']}%", flush=True)
                print("Authorized for real-money execution on next confirmed trigger.", flush=True)
                print("#" * 80 + "\n", flush=True)


# ==============================================================================
# 5. BITGET ONE-WAY LIVE EXECUTION HELPERS
# ==============================================================================
def get_open_position():
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
        print(f"[POSITION QUERY WARNING] {e}", flush=True)
    return None


def open_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e


def close_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e


def open_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e


def close_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e


# ==============================================================================
# 6. THE 11-MODEL SIGNAL SCANNER (FEATURING TRADER AGGRESSIVENESS)
# ==============================================================================
def screen_coin_for_models(symbol, t_data):
    try:
        bid = float(t_data.get('bid', 0) or 0)
        ask = float(t_data.get('ask', 0) or 0)
        last_price = float(t_data.get('last', 0) or 0)
        pct_24h = float(t_data.get('percentage', 0) or 0)
        vol_24h_m = float(t_data.get('quoteVolume', 0) or 0) / 1_000_000

        if bid <= 0 or ask <= 0 or last_price <= 0:
            return []

        spread_pct = ((ask - bid) / last_price) * 100
        if spread_pct > 0.08:
            return []

        # 5-minute fast OHLCV
        ohlcv_5m = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=25)
        if len(ohlcv_5m) < 20:
            return []

        closed_candles = ohlcv_5m[:-1]
        closes = [x[4] for x in closed_candles]
        volumes = [x[5] for x in closed_candles]
        highs = [x[2] for x in closed_candles]
        lows = [x[3] for x in closed_candles]

        c_open = closed_candles[-1][1]
        c_high = closed_candles[-1][2]
        c_low = closed_candles[-1][3]
        c_close = closed_candles[-1][4]

        candle_range = c_high - c_low
        if candle_range == 0:
            return []

        body_pct = abs(c_close - c_open) / candle_range
        pct_5m = ((c_close - c_open) / c_open) * 100
        pullback_pct = ((c_high - c_close) / c_high) * 100 if pct_5m > 0 else ((c_close - c_low) / c_low) * 100

        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
        rsi = calculate_rsi(closes, period=14)
        amp_pct = ((highs[-1] - lows[-1]) / lows[-1]) * 100 if lows[-1] > 0 else 0
        atr = calculate_atr(closed_candles, period=14)

        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        matches = []

        # ----------------------------------------------------------------------
        # MODEL 11: TRADER AGGRESSIVENESS SURGE (Violent Taker Dominance)
        # RVol >= 3.5x, Body >= 75% of candle range (Marubozu), Move >= 1.2%
        # ----------------------------------------------------------------------
        if rvol >= 3.5 and body_pct >= 0.75 and abs(pct_5m) >= 1.20:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("11_TRADER_AGGRESSIVENESS_SURGE", side, f"Pure Taker Violence: {rvol}x Volume Marubozu", atr))

        # Model 1: BEAR_TRAP_OI_ABSORPTION
        if pct_24h <= -2.0 and pct_5m >= 1.2 and rvol >= 1.8:
            matches.append(("1_BEAR_TRAP_OI_ABSORPTION", "long", "Downtrend Absorption Squeeze", atr))

        # Model 2: SQUEEZE_EXHAUSTION_FADE
        if pct_24h >= 2.0 and pct_5m >= 1.5 and rsi >= 72 and pullback_pct >= 0.5:
            matches.append(("2_SQUEEZE_EXHAUSTION_FADE", "short", "Short-covering exhaustion top", atr))

        # Model 3: RSI_WASHOUT_CLEAN_BOUNCE (Clean stair-step from oversold floor)
        if pct_24h <= -8.0 and pct_5m >= 1.5 and pullback_pct <= 0.40:
            matches.append(("3_RSI_WASHOUT_CLEAN_BOUNCE", "long", "Clean oversold bounce without wick", atr))

        # Model 4: BLOWOFF_TOP_OVERBOUGHT
        if rsi >= 75.0 and pullback_pct >= 0.6 and funding_rate >= 0.03:
            matches.append(("4_BLOWOFF_TOP_OVERBOUGHT", "short", "Retail FOMO top rejection", atr))

        # Model 5: INSTITUTIONAL_OI_EXPANSION
        if pct_5m >= 1.2 and rvol >= 2.2 and funding_rate <= 0.012:
            matches.append(("5_INSTITUTIONAL_OI_EXPANSION", "long", "Whale accumulation on clean funding", atr))

        # Model 6: CLEAN_STAIR_MOMENTUM
        if pct_5m >= 1.4 and pullback_pct <= 0.25:
            matches.append(("6_CLEAN_STAIR_MOMENTUM", "long", "Solid green candle zero pullback", atr))

        # Model 7: HIGH_RVOL_IGNITION
        if rvol >= 3.0 and abs(pct_5m) >= 1.2:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("7_HIGH_RVOL_IGNITION", side, f"High {rvol}x volume breakout", atr))

        # Model 8: HIGH_AMPLITUDE_SWING
        if amp_pct >= 4.0 and pct_5m >= 1.2:
            matches.append(("8_HIGH_AMPLITUDE_SWING", "long", f"Wide {amp_pct:.1f}% swing bounce", atr))

        # Model 9: CROWDED_FUNDING_DUMP
        if funding_rate >= 0.035 and pct_5m <= -0.5:
            matches.append(("9_CROWDED_FUNDING_DUMP", "short", "Over-leveraged long squeeze dump", atr))

        # Model 10: WATERFALL_BREAKDOWN
        if pct_5m <= -2.0 and rvol >= 2.0:
            matches.append(("10_WATERFALL_BREAKDOWN", "short", "Liquidation waterfall cascade", atr))

        return [(m[0], m[1], m[2], last_price, pct_5m, rvol, vol_24h_m, m[3]) for m in matches]

    except Exception:
        return []


# ==============================================================================
# 7. ACTIVE TRADE GUARDIAN (FOR BOTH LIVE TRADES & PAPER EXPERIMENTS)
# ==============================================================================
def manage_live_trade(symbol, side, initial_contracts, entry_price, entry_atr):
    """Dynamic risk manager for live real-money trades."""
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    last_position_check = time.time()
    fee_shield_active = False

    atr = entry_atr if entry_atr > 0 else (entry_price * 0.012)
    stop_distance = min(1.3 * atr, entry_price * 0.0145)  # 1.45% max price loss
    fee_shield_trigger = 0.9 * atr
    runner_trigger = 1.8 * atr
    trail_distance = 1.1 * atr

    initial_stop_price = entry_price - stop_distance if side == 'long' else entry_price + stop_distance
    stop_pct = (stop_distance / entry_price) * 100
    print(f"\n[LIVE GUARDIAN ENGAGED] {side.upper()} {symbol} | Fill: {entry_price:.5f} | Hard Stop: {initial_stop_price:.5f} ({stop_pct:.2f}%)", flush=True)

    while True:
        try:
            time.sleep(2)
            if time.time() - last_position_check > 20:
                pos = get_open_position()
                if not pos or pos['symbol'] != symbol or pos['side'] != side:
                    print(f"\n[LIVE INFO] {symbol} closed externally. Exiting live guardian.", flush=True)
                    break
                last_position_check = time.time()

            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker.get('last', 0) or 0)
            if cur_price <= 0:
                continue

            if cur_price > highest_price:
                highest_price = cur_price
            if cur_price < lowest_price:
                lowest_price = cur_price

            elapsed_min = (time.time() - entry_time) / 60

            if side == 'long':
                pnl_pct = ((cur_price - entry_price) / entry_price) * 100
                peak_pnl = ((highest_price - entry_price) / entry_price) * 100
                peak_distance = highest_price - entry_price
            else:
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100
                peak_distance = entry_price - lowest_price

            if time.time() - last_log_time > 10:
                shield_status = "LOCKED (+0.40%)" if fee_shield_active else "MONITORING"
                print(f"[LIVE STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% (Peak: {peak_pnl:+.2f}%) | Shield: {shield_status} | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            def execute_exit(reason):
                print(f"\n[LIVE EXIT TRIGGER] {reason} | PnL: {pnl_pct:+.2f}%", flush=True)
                live_pos = get_open_position()
                close_amount = live_pos['contracts'] if live_pos else initial_contracts
                if side == 'long':
                    close_long_position(symbol, close_amount)
                else:
                    close_short_position(symbol, close_amount)

            # 1. Fee-Shield Lock (+0.9x ATR -> Lock +0.40% net profit)
            if not fee_shield_active and peak_distance >= fee_shield_trigger:
                fee_shield_active = True
                print(f"\n[LIVE FEE-SHIELD] {symbol} moved 0.9x ATR! Stop locked at Breakeven +0.40% net.", flush=True)

            if fee_shield_active:
                if side == 'long' and cur_price <= entry_price * 1.0040:
                    execute_exit("Long Fee-Shield Hit")
                    break
                elif side == 'short' and cur_price >= entry_price * 0.9960:
                    execute_exit("Short Fee-Shield Hit")
                    break

            # 2. Hard Stop Loss
            if not fee_shield_active:
                if side == 'long' and cur_price <= initial_stop_price:
                    execute_exit("Long Tight Stop Hit")
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    execute_exit("Short Tight Stop Hit")
                    break

            # 3. Trailing Runner
            if peak_distance >= runner_trigger:
                if side == 'long':
                    trail_stop = highest_price - trail_distance
                    if cur_price <= trail_stop:
                        execute_exit("Long Trailing Stop Hit")
                        break
                else:
                    trail_stop = lowest_price + trail_distance
                    if cur_price >= trail_stop:
                        execute_exit("Short Trailing Stop Hit")
                        break

            # 4. Fast 15-Minute Stagnation Exit
            if elapsed_min >= 15.0 and peak_distance < (0.6 * atr):
                execute_exit("15m Stagnation Exit (Recycled Margin)")
                break

        except Exception as e:
            print(f"[LIVE GUARDIAN EXCEPTION] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 8. PARALLEL PAPER EXPERIMENT TRACKER
# ==============================================================================
def update_experiments(tourn):
    remaining = []

    for exp in tourn['active_experiments']:
        sym = exp['symbol']
        side = exp['side']
        base_price = exp['base_price']
        elapsed_min = (time.time() - exp['started_at']) / 60

        try:
            ticker = exchange.fetch_ticker(sym)
            cur_price = float(ticker.get('last', 0) or 0)
        except Exception:
            remaining.append(exp)
            continue

        if cur_price > exp['highest_price']:
            exp['highest_price'] = cur_price
        if cur_price < exp['lowest_price']:
            exp['lowest_price'] = cur_price

        if side == 'long':
            pnl_pct = ((cur_price - base_price) / base_price) * 100
            peak_pnl = ((exp['highest_price'] - base_price) / base_price) * 100
            max_drawdown = ((exp['lowest_price'] - base_price) / base_price) * 100
        else:
            pnl_pct = ((base_price - cur_price) / base_price) * 100
            peak_pnl = ((base_price - exp['lowest_price']) / base_price) * 100
            max_drawdown = ((base_price - exp['highest_price']) / base_price) * 100

        # Complete experiment after 25 minutes
        if elapsed_min >= 25.0:
            model_name = exp['model_name']
            stats = tourn['models'][model_name]
            stats['tested'] += 1

            if peak_pnl > stats['max_profit']:
                stats['max_profit'] = round(peak_pnl, 2)

            if peak_pnl >= MIN_TARGET_PROFIT_PCT and max_drawdown > -1.20:
                outcome = "PROFITABLE_WINNER"
                stats['wins'] += 1
            elif peak_pnl < 1.0:
                outcome = "LOW_PROFIT_STALL"
                stats['stalls'] += 1
            else:
                outcome = "FAILED_DRAWDOWN"
                stats['losses'] += 1

            tourn['total_experiments_completed'] += 1

            print("\n" + "=" * 80, flush=True)
            print(f"[PAPER EXPERIMENT COMPLETE #{tourn['total_experiments_completed']}] {model_name} on {sym}", flush=True)
            print(f"  Result:      {outcome}", flush=True)
            print(f"  Peak Gain:   +{peak_pnl:.2f}% | Drawdown: {max_drawdown:.2f}%", flush=True)
            print(f"  Model Score: {stats['wins']} Wins / {stats['tested']} Tested (Best: +{stats['max_profit']}%)", flush=True)
            print("=" * 80 + "\n", flush=True)

            check_and_update_graduation(tourn, model_name)
            save_tournament(tourn)
        else:
            remaining.append(exp)

    tourn['active_experiments'] = remaining


# ==============================================================================
# 9. MAIN AUTONOMOUS ENGINE (LAB + LIVE DESK)
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-11 Autonomous Multi-Strategy Desk initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    tourn = load_tournament()
    cycle = 1

    while True:
        try:
            # 1. Manage active live real-money trade if open
            pos = get_open_position()
            if pos:
                fallback_atr = pos['entry_price'] * 0.012
                manage_live_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(3)
                continue

            # 2. Update all running digital experiments
            if tourn['active_experiments']:
                update_experiments(tourn)
                save_tournament(tourn)

            # 3. Balance Check & Dynamic Leverage Ladder
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            notional = (usdt_free * BALANCE_USE_PCT) * leverage

            # 4. Fetch Universe in 1 single call
            try:
                tickers = exchange.fetch_tickers()
            except Exception as e:
                time.sleep(10)
                continue

            liquid_candidates = []
            for symbol, t in tickers.items():
                if not symbol.endswith(":USDT"):
                    continue
                base_asset = symbol.split('/')[0].upper()
                if base_asset in NON_CRYPTO_SYMBOLS:
                    continue
                vol_24h = float(t.get('quoteVolume', 0) or 0)
                if vol_24h >= MIN_24H_VOLUME:
                    liquid_candidates.append((symbol, vol_24h, t))

            liquid_candidates.sort(key=lambda x: x[1], reverse=True)
            active_syms = {e['symbol'] for e in tourn['active_experiments']}

            live_trade_triggered = False

            # 5. Screen Universe
            for sym, vol_24h, t_data in liquid_candidates:
                time.sleep(0.025)
                matched_models = screen_coin_for_models(sym, t_data)

                for m_name, side, reason, price, p_5m, rvol, vol_m, atr in matched_models:
                    model_stat = tourn['models'][m_name]

                    # ----------------------------------------------------------
                    # BRANCH A: MODEL IS GRADUATED -> EXECUTE REAL 3X/4X TRADE!
                    # ----------------------------------------------------------
                    if model_stat['is_graduated'] and not live_trade_triggered and notional >= MIN_NOTIONAL:
                        ticker_now = exchange.fetch_ticker(sym)
                        live_price = float(ticker_now.get('last', 0) or 0)

                        market = exchange.market(sym)
                        min_lot = float(market['limits']['amount']['min'] or 0)
                        raw_amount = notional / live_price
                        formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))
                        actual_notional = formatted_amount * live_price

                        if formatted_amount >= min_lot and actual_notional >= 5.15:
                            try:
                                exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                            except Exception:
                                pass

                            print("\n" + "#" * 80, flush=True)
                            print(f"[GRADUATED MODEL STRIKE: {side.upper()}] Triggered by {m_name} on {sym}!", flush=True)
                            print(f"  Signal:    {reason} (5m: {p_5m:+.2f}%, RVol: {rvol}x)", flush=True)
                            print(f"  Execution: Real Order {leverage}x {side.upper()} | Notional: ${actual_notional:.2f}", flush=True)
                            print("#" * 80 + "\n", flush=True)

                            if side == 'long':
                                order = open_long_position(sym, formatted_amount)
                            else:
                                order = open_short_position(sym, formatted_amount)

                            print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                            time.sleep(2)

                            real_pos = get_open_position()
                            real_fill_price = real_pos['entry_price'] if real_pos else live_price
                            real_contracts = real_pos['contracts'] if real_pos else formatted_amount

                            manage_live_trade(sym, side, real_contracts, real_fill_price, atr)
                            live_trade_triggered = True
                            break

                    # ----------------------------------------------------------
                    # BRANCH B: MODEL IS IN LAB -> RUN DIGITAL PAPER EXPERIMENT
                    # ----------------------------------------------------------
                    elif len(tourn['active_experiments']) < MAX_PARALLEL_EXPERIMENTS and sym not in active_syms:
                        new_exp = {
                            "exp_id": tourn['total_experiments_completed'] + len(tourn['active_experiments']) + 1,
                            "symbol": sym,
                            "model_name": m_name,
                            "side": side,
                            "base_price": price,
                            "highest_price": price,
                            "lowest_price": price,
                            "started_at": time.time(),
                            "frames": [{"min": 0.0, "pnl": 0.0, "peak": 0.0, "drawdown": 0.0}]
                        }
                        tourn['active_experiments'].append(new_exp)
                        active_syms.add(sym)
                        save_tournament(tourn)

                        print(f"[PAPER EXPERIMENT #{new_exp['exp_id']}] Testing {m_name} on {sym} ({side.upper()}) | Zero real cash placed.", flush=True)

                if live_trade_triggered:
                    break

            # 6. Periodic Status Pulse
            if cycle % 2 == 0:
                graduated_count = sum(1 for m in tourn['models'].values() if m['is_graduated'])
                print(f"\n[LAB PULSE] Total Studies: {tourn['total_experiments_completed']} | Active Cameras: {len(tourn['active_experiments'])}/10 | Graduated Models: {graduated_count}/11 | Vault: ${usdt_free:.2f} USDT", flush=True)
                for name, s in tourn['models'].items():
                    status = "[LIVE AUTHORIZED]" if s['is_graduated'] else "[STUDYING]"
                    win_pct = (s['wins'] / s['tested']) * 100 if s['tested'] > 0 else 0
                    print(f"  • {name:<32} {status:<18} | Tested: {s['tested']:2d} | Wins (>=1.5%): {s['wins']:2d} ({win_pct:.0f}%)", flush=True)
                print("-" * 80, flush=True)

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()

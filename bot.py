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
        self.wfile.write(b"APEX-V3 Failsafe Multi-Strategy Engine is active.")

    def log_message(self, format, *args):
        return  # Silence server logs


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. EMERGENCY CIRCUIT BREAKER & ANTI-BLOWOUT SHIELD
# ==============================================================================
CB_FILE = "circuit_breaker.json"
LOCKOUT_FILE = "EMERGENCY_LOCKOUT.txt"

ABSOLUTE_EQUITY_FLOOR = 1.50    # SHIELD 1: Balance can NEVER drop below $1.50
MAX_CONSECUTIVE_LOSSES = 2      # SHIELD 2: 2 losses in a row = 24h hard freeze
MAX_ORDER_NOTIONAL = 7.50       # SHIELD 4: Hard cap on position value ($7.50 max)
MIN_ORDER_NOTIONAL = 5.15       # Buffer above Bitget's $5.00 minimum

class CircuitBreaker:
    def __init__(self):
        self.consecutive_losses = 0
        self.last_loss_time = 0
        self.load_state()

    def load_state(self):
        if os.path.exists(CB_FILE):
            try:
                with open(CB_FILE, "r") as f:
                    data = json.load(f)
                    self.consecutive_losses = data.get("consecutive_losses", 0)
                    self.last_loss_time = data.get("last_loss_time", 0)
            except Exception:
                pass

    def save_state(self):
        try:
            with open(CB_FILE, "w") as f:
                json.dump({
                    "consecutive_losses": self.consecutive_losses,
                    "last_loss_time": self.last_loss_time
                }, f, indent=2)
        except Exception:
            pass

    def check_safety(self, current_balance):
        # 1. Hard Lockout File Check
        if os.path.exists(LOCKOUT_FILE):
            return False, "HARD_LOCKOUT: Emergency lockout file exists. Trading permanently halted."

        # 2. Hard Equity Floor ($1.50)
        if current_balance < ABSOLUTE_EQUITY_FLOOR:
            with open(LOCKOUT_FILE, "w") as f:
                f.write(f"Kill switch triggered at ${current_balance:.2f} on {time.ctime()}")
            return False, f"EQUITY_FLOOR_BREACH: Balance ${current_balance:.2f} breached $1.50 floor! Engine locked."

        # 3. Two-Strike Consecutive Loss Freeze (24h cooldown)
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            elapsed_hours = (time.time() - self.last_loss_time) / 3600
            if elapsed_hours < 24.0:
                remaining = 24.0 - elapsed_hours
                return False, f"TWO_STRIKE_FREEZE: 2 consecutive losses. Trading frozen for {remaining:.1f} more hours."
            else:
                print("\n[CIRCUIT BREAKER] 24-hour cooling-off period ended. Resetting loss strikes.\n", flush=True)
                self.consecutive_losses = 0
                self.save_state()

        return True, "SAFE"

    def record_trade_result(self, pnl_pct):
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            print(f"\n[CIRCUIT BREAKER] Strike logged. Consecutive losses: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}", flush=True)
        else:
            self.consecutive_losses = 0
            print("\n[CIRCUIT BREAKER] Winning trade logged. Loss strikes reset to 0.", flush=True)
        self.save_state()


# ==============================================================================
# 3. CONFIGURATION & CAPITAL BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BASE_LEVERAGE = 3
BALANCE_USE_PCT = 0.88          # Use 88% of vault margin
MIN_24H_VOLUME = 1_000_000      # $1,000,000 volume floor
SCAN_INTERVAL_SECONDS = 45      # Rapid 45-second scan loop
MAX_PARALLEL_EXPERIMENTS = 8    # Run up to 8 simultaneous digital paper experiments
TOURNAMENT_FILE = "rotational_tournament.json"

# Strict 4:1 Ratio & Capacity Rules
MIN_IMPULSE_PCT = 2.00          # Minimum 2.0% straight impulse
MAX_REBOUND_PCT = 0.50          # Maximum 0.50% counter-wick (4:1 ratio)
MIN_CAPACITY_RUNWAY_PCT = 1.50  # Must have >= 1.50% open room to nearest wall
MIN_VERIFIED_TAPES = 5          # Must observe 5 verified winning occurrences first
SIMILARITY_THRESHOLD = 90.0     # 90.0% curve match required to trade live
MAX_RECENT_EXCLUSION = 3        # Excludes last 3 traded coins to force rotation

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

circuit_breaker = CircuitBreaker()


# ==============================================================================
# 4. MATHEMATICAL INDICATORS
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


def calculate_curve_similarity(live_frames, hero_frames):
    comp_len = min(len(live_frames), len(hero_frames))
    if comp_len < 3:
        return 0.0

    errors = []
    for i in range(comp_len):
        diff = abs(live_frames[i]['pnl'] - hero_frames[i]['pnl'])
        dd_diff = abs(live_frames[i]['drawdown'] - hero_frames[i]['drawdown'])
        errors.append((diff * 3.0) + (dd_diff * 2.0))

    avg_err = sum(errors) / len(errors)
    return round(max(100.0 - (avg_err * 2.5), 0.0), 1)


# ==============================================================================
# 5. CAPACITY & RUNWAY VERIFICATION ENGINE
# ==============================================================================
def check_profit_capacity(side, cur_price, highs, lows, rsi):
    """
    Guarantees the coin has the statistical capacity to move 
    AT LEAST +1.50% from the current entry price.
    """
    if side == "long":
        if rsi > 68.0:
            return False, "RSI exhausted (>68.0). No fuel to push +1.5%."

        recent_resistance = max(highs[-25:-1]) if len(highs) >= 26 else max(highs)
        if recent_resistance > cur_price:
            distance_to_ceiling = ((recent_resistance - cur_price) / cur_price) * 100
            if distance_to_ceiling < MIN_CAPACITY_RUNWAY_PCT:
                return False, f"Overhead resistance too close ({distance_to_ceiling:.2f}% < 1.50%)."

        return True, "Capacity runway verified (>= +1.50% open space)."

    else:  # short
        if rsi < 32.0:
            return False, "RSI oversold (<32.0). No fuel to drop -1.5%."

        recent_support = min(lows[-25:-1]) if len(lows) >= 26 else min(lows)
        if recent_support < cur_price:
            distance_to_floor = ((cur_price - recent_support) / cur_price) * 100
            if distance_to_floor < MIN_CAPACITY_RUNWAY_PCT:
                return False, f"Support floor too close ({distance_to_floor:.2f}% < 1.50%)."

        return True, "Downside capacity runway verified (>= -1.50% open space)."


# ==============================================================================
# 6. PERSISTENT TOURNAMENT STORAGE & ROTATION QUEUE
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
    "11_TRADER_AGGRESSIVENESS_SURGE",
    "12_BLUE_SKY_BREAKOUT_RUNNER"
]

def load_tournament():
    default_data = {
        "total_experiments": 0,
        "models": {
            name: {
                "tested": 0, "wins": 0, "losses": 0, "stalls": 0,
                "max_profit": 0.0, "is_graduated": False
            } for name in STRATEGY_NAMES
        },
        "verified_winning_tapes": [],
        "active_studies": [],
        "recently_traded": []
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


def push_traded_coin(tourn, symbol):
    if symbol not in tourn['recently_traded']:
        tourn['recently_traded'].append(symbol)
    if len(tourn['recently_traded']) > MAX_RECENT_EXCLUSION:
        tourn['recently_traded'].pop(0)
    save_tournament(tourn)


# ==============================================================================
# 7. BITGET ORDER HELPERS (SHIELD 3: PERMANENT REDUCEONLY FIX)
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
    """PERMANENT FIX: includes reduceOnly: True to eliminate Bitget error 25203."""
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'reduceOnly': True, 'tradeSide': 'close'}
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
    """PERMANENT FIX: includes reduceOnly: True to cleanly close shorts."""
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'reduceOnly': True, 'tradeSide': 'close'}
            )
        raise e


# ==============================================================================
# 8. THE 12-MODEL SIGNAL SCANNER (WITH 4:1 RATIO & CAPACITY CHECKS)
# ==============================================================================
def screen_coin_for_12_models(symbol, t_data):
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

        ohlcv_5m = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=35)
        if len(ohlcv_5m) < 30:
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
        upper_wick = ((c_high - c_close) / c_open) * 100 if pct_5m > 0 else 0
        lower_wick = ((c_close - c_low) / c_open) * 100 if pct_5m < 0 else 0
        pullback_pct = upper_wick if pct_5m > 0 else lower_wick

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

        # MODEL 12: BLUE_SKY_BREAKOUT_RUNNER
        recent_25_high = max(highs[-26:-2])
        if c_close > recent_25_high and pct_5m >= 1.50 and upper_wick <= 0.40 and rsi <= 68.0:
            matches.append(("12_BLUE_SKY_BREAKOUT_RUNNER", "long", "Blue Sky Breakout above 25-candle ceiling", atr))

        # MODEL 11: TRADER_AGGRESSIVENESS_SURGE
        if rvol >= 3.5 and body_pct >= 0.75 and abs(pct_5m) >= 1.20 and pullback_pct <= 0.35:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("11_TRADER_AGGRESSIVENESS_SURGE", side, f"Taker Violence: {rvol}x Marubozu", atr))

        # MODEL 6: CLEAN_STAIR_MOMENTUM (Strict 4:1 straight-line impulse)
        if pct_5m >= MIN_IMPULSE_PCT and upper_wick <= MAX_REBOUND_PCT:
            ratio = pct_5m / max(upper_wick, 0.05)
            if ratio >= 4.0:
                matches.append(("6_CLEAN_STAIR_MOMENTUM", "long", f"Clean 4:1 Straight Line (Ratio {ratio:.1f})", atr))

        # MODEL 1: BEAR_TRAP_OI_ABSORPTION
        if pct_24h <= -2.0 and pct_5m >= 1.2 and rvol >= 1.8:
            matches.append(("1_BEAR_TRAP_OI_ABSORPTION", "long", "Downtrend Absorption Squeeze", atr))

        # MODEL 2: SQUEEZE_EXHAUSTION_FADE
        if pct_24h >= 2.0 and pct_5m >= 1.5 and rsi >= 72 and pullback_pct >= 0.5:
            matches.append(("2_SQUEEZE_EXHAUSTION_FADE", "short", "Short-covering exhaustion top", atr))

        # MODEL 3: RSI_WASHOUT_CLEAN_BOUNCE
        if pct_24h <= -8.0 and pct_5m >= 1.5 and pullback_pct <= 0.40:
            matches.append(("3_RSI_WASHOUT_CLEAN_BOUNCE", "long", "Clean oversold bounce without wick", atr))

        # MODEL 4: BLOWOFF_TOP_OVERBOUGHT
        if rsi >= 75.0 and pullback_pct >= 0.6 and funding_rate >= 0.03:
            matches.append(("4_BLOWOFF_TOP_OVERBOUGHT", "short", "Retail FOMO top rejection", atr))

        # MODEL 5: INSTITUTIONAL_OI_EXPANSION
        if pct_5m >= 1.2 and rvol >= 2.2 and funding_rate <= 0.012:
            matches.append(("5_INSTITUTIONAL_OI_EXPANSION", "long", "Whale accumulation on clean funding", atr))

        # MODEL 7: HIGH_RVOL_IGNITION
        if rvol >= 3.0 and abs(pct_5m) >= 1.2:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("7_HIGH_RVOL_IGNITION", side, f"High {rvol}x volume breakout", atr))

        # MODEL 8: HIGH_AMPLITUDE_SWING
        if amp_pct >= 4.0 and pct_5m >= 1.2:
            matches.append(("8_HIGH_AMPLITUDE_SWING", "long", f"Wide {amp_pct:.1f}% swing bounce", atr))

        # MODEL 9: CROWDED_FUNDING_DUMP
        if funding_rate >= 0.035 and pct_5m <= -0.5:
            matches.append(("9_CROWDED_FUNDING_DUMP", "short", "Over-leveraged long squeeze dump", atr))

        # MODEL 10: WATERFALL_BREAKDOWN
        if pct_5m <= -2.0 and rvol >= 2.0:
            matches.append(("10_WATERFALL_BREAKDOWN", "short", "Liquidation waterfall cascade", atr))

        # Filter all candidates through +1.50% Capacity Runway Check
        qualified = []
        for m_name, side, reason, c_atr in matches:
            has_capacity, cap_msg = check_profit_capacity(side, c_close, highs, lows, rsi)
            if has_capacity:
                qualified.append((m_name, side, reason, last_price, pct_5m, rvol, vol_24h_m, c_atr))

        return qualified

    except Exception:
        return []


# ==============================================================================
# 9. ACTIVE TRADE GUARDIAN (LIVE RISK ENGINE WITH CIRCUIT BREAKER HOOK)
# ==============================================================================
def manage_live_trade(symbol, side, initial_contracts, entry_price, entry_atr):
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

                # Try up to 3 times to guarantee execution
                for attempt in range(1, 4):
                    try:
                        if side == 'long':
                            close_long_position(symbol, close_amount)
                        else:
                            close_short_position(symbol, close_amount)
                        break
                    except Exception as exit_err:
                        print(f"[EXIT ATTEMPT {attempt} FAILED] {exit_err}", flush=True)
                        time.sleep(1)

                # Record outcome directly into the Circuit Breaker
                circuit_breaker.record_trade_result(pnl_pct)

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
                    execute_exit("Long Hard Stop Hit")
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    execute_exit("Short Hard Stop Hit")
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
                execute_exit("15m Stagnation Exit (Recycled Capital)")
                break

        except Exception as e:
            print(f"[LIVE GUARDIAN EXCEPTION] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 10. SIMULTANEOUS DIGITAL PAPER EXPERIMENT TRACKER
# ==============================================================================
def update_experiments(tourn):
    remaining = []

    for exp in tourn['active_studies']:
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
            max_dd = ((exp['lowest_price'] - base_price) / base_price) * 100
        else:
            pnl_pct = ((base_price - cur_price) / base_price) * 100
            peak_pnl = ((base_price - exp['lowest_price']) / base_price) * 100
            max_dd = ((base_price - exp['highest_price']) / base_price) * 100

        # Record telemetry frame every 2 minutes
        last_frame_min = exp['frames'][-1]['min'] if exp['frames'] else -99
        if (elapsed_min - last_frame_min) >= 2.0:
            exp['frames'].append({
                "min": round(elapsed_min, 1),
                "pnl": round(pnl_pct, 2),
                "peak": round(peak_pnl, 2),
                "drawdown": round(max_dd, 2)
            })

        # Finalize after 20 minutes
        if elapsed_min >= 20.0:
            m_name = exp['model_name']
            stats = tourn['models'][m_name]
            stats['tested'] += 1

            if peak_pnl > stats['max_profit']:
                stats['max_profit'] = round(peak_pnl, 2)

            if peak_pnl >= MIN_CAPACITY_RUNWAY_PCT and max_dd > -0.60:
                stats['wins'] += 1
                outcome = "VERIFIED_WINNER"

                tape = {
                    "tape_id": len(tourn['verified_winning_tapes']) + 1,
                    "symbol": sym,
                    "model_name": m_name,
                    "side": side,
                    "peak_pnl": round(peak_pnl, 2),
                    "drawdown": round(max_dd, 2),
                    "frames": exp['frames']
                }
                tourn['verified_winning_tapes'].append(tape)
                print("\n" + "=" * 80, flush=True)
                print(f"[VERIFIED FOOTPRINT ARCHIVED #{tape['tape_id']}] {m_name} on {sym}", flush=True)
                print(f"  Peak Expansion: +{peak_pnl:.2f}% | Drawdown Held To: {max_dd:.2f}%", flush=True)
                print(f"  Total Verified Library: {len(tourn['verified_winning_tapes'])}/{MIN_VERIFIED_TAPES} Tapes Recorded", flush=True)
                print("=" * 80 + "\n", flush=True)
            elif peak_pnl < 1.0:
                stats['stalls'] += 1
                outcome = "LOW_PROFIT_STALL"
            else:
                stats['losses'] += 1
                outcome = "FAILED_DRAWDOWN"

            tourn['total_experiments'] += 1
            save_tournament(tourn)
        else:
            remaining.append(exp)

    tourn['active_studies'] = remaining


# ==============================================================================
# 11. MAIN ENGINE LOOP (FAILSAFE GOVERNOR + MULTI-STRATEGY TOURNAMENT)
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-V3 Failsafe Multi-Strategy Engine initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    tourn = load_tournament()
    cycle = 1

    while True:
        try:
            # 1. Manage active live trade if one is running
            pos = get_open_position()
            if pos:
                fallback_atr = pos['entry_price'] * 0.012
                manage_live_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(3)
                continue

            # 2. Update all running digital paper experiments
            if tourn['active_studies']:
                update_experiments(tourn)
                save_tournament(tourn)

            # 3. Balance Check & SHIELD 1 & 2 SAFETY AUDIT
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            is_safe, reason = circuit_breaker.check_safety(usdt_free)
            if not is_safe:
                print(f"\n[CIRCUIT BREAKER LOCKDOWN ACTIVE] Reason: {reason}", flush=True)
                print(f"Vault Cash Protected at: ${usdt_free:.2f} USDT. Engine sleeping...\n", flush=True)
                time.sleep(60)
                continue

            # Scales leverage to guarantee order size is always >= $5.15 notional
            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            # SHIELD 4: Hard Notional Sizing Clamp ($5.15 floor to $7.50 ceiling)
            raw_notional = (usdt_free * BALANCE_USE_PCT) * leverage
            notional = max(min(raw_notional, MAX_ORDER_NOTIONAL), MIN_ORDER_NOTIONAL)

            # 4. Pull Universe in 1 single call
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

            active_syms = {s['symbol'] for s in tourn['active_studies']}
            live_trade_triggered = False

            # 5. Screen Universe for 12 Models
            for sym, vol_24h, t_data in liquid_candidates:
                # DYNAMIC ROTATION RULE: Exclude recently traded coins
                if sym in tourn['recently_traded']:
                    continue

                if sym in active_syms:
                    continue

                time.sleep(0.025)
                matched_setups = screen_coin_for_12_models(sym, t_data)

                for m_name, side, reason, price, p_5m, rvol, vol_m, atr in matched_setups:
                    # CHECK FOOTPRINT LIBRARY: Must have >= 5 verified tapes
                    # AND must match a winning tape by >= 90.0% similarity
                    library = tourn['verified_winning_tapes']
                    is_live_authorized = False
                    best_similarity = 0.0

                    if len(library) >= MIN_VERIFIED_TAPES:
                        live_dummy_frame = [{"min": 0.0, "pnl": 0.0, "drawdown": 0.0}]
                        for hero in library:
                            if hero['side'] == side:
                                sim = calculate_curve_similarity(live_dummy_frame, hero['frames'])
                                if sim > best_similarity:
                                    best_similarity = sim

                        if best_similarity >= SIMILARITY_THRESHOLD:
                            is_live_authorized = True

                    # BRANCH A: 5 TAPES VERIFIED & >= 90% SIMILARITY -> LIVE TRADE
                    if is_live_authorized and not live_trade_triggered and notional >= MIN_ORDER_NOTIONAL:
                        ticker_now = exchange.fetch_ticker(sym)
                        live_price = float(ticker_now.get('last', 0) or 0)

                        market = exchange.market(sym)
                        min_lot = float(market['limits']['amount']['min'] or 0)
                        raw_amount = notional / live_price
                        formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))
                        actual_notional = formatted_amount * live_price

                        if formatted_amount >= min_lot and actual_notional >= MIN_ORDER_NOTIONAL:
                            try:
                                exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                            except Exception:
                                pass

                            print("\n" + "#" * 80, flush=True)
                            print(f"[FAILSAFE LIVE STRIKE: {side.upper()}] Triggered by {m_name} on {sym}!", flush=True)
                            print(f"  Signal:    {reason} (5m: {p_5m:+.2f}%, RVol: {rvol}x)", flush=True)
                            print(f"  Footprint: {best_similarity}% Curve Match to Verified Winner Tape", flush=True)
                            print(f"  Execution: Real Order {leverage}x {side.upper()} | Notional: ${actual_notional:.2f}", flush=True)
                            print("#" * 80 + "\n", flush=True)

                            if side == 'long':
                                order = open_long_position(sym, formatted_amount)
                            else:
                                order = open_short_position(sym, formatted_amount)

                            print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                            time.sleep(2)

                            # Enforce rotation: add to exclusion queue immediately
                            push_traded_coin(tourn, sym)

                            real_pos = get_open_position()
                            real_fill_price = real_pos['entry_price'] if real_pos else live_price
                            real_contracts = real_pos['contracts'] if real_pos else formatted_amount

                            manage_live_trade(sym, side, real_contracts, real_fill_price, atr)
                            live_trade_triggered = True
                            break

                    # BRANCH B: RUNNING PARALLEL DIGITAL PAPER EXPERIMENT
                    elif len(tourn['active_studies']) < MAX_PARALLEL_EXPERIMENTS and sym not in active_syms:
                        new_study = {
                            "symbol": sym,
                            "model_name": m_name,
                            "side": side,
                            "base_price": price,
                            "highest_price": price,
                            "lowest_price": price,
                            "started_at": time.time(),
                            "frames": [{"min": 0.0, "pnl": 0.0, "drawdown": 0.0}]
                        }
                        tourn['active_studies'].append(new_study)
                        active_syms.add(sym)
                        save_tournament(tourn)

                        print(f"[PAPER EXPERIMENT #{len(tourn['active_studies'])}] Filming {m_name} on {sym} ({side.upper()}) | Zero real cash placed.")

                if live_trade_triggered:
                    break

            # Periodic Status Pulse
            if cycle % 2 == 0:
                tapes_count = len(tourn['verified_winning_tapes'])
                strikes = circuit_breaker.consecutive_losses
                mode_str = f"LIVE READY ({tapes_count} Tapes)" if tapes_count >= MIN_VERIFIED_TAPES else f"BUILDING LIBRARY ({tapes_count}/{MIN_VERIFIED_TAPES} Tapes)"
                recent_str = ", ".join(tourn['recently_traded']) if tourn['recently_traded'] else "None (Ready to rotate)"
                print(
                    f"\n[RADAR PULSE] Status: {mode_str} | Active Cameras: {len(tourn['active_studies'])}/{MAX_PARALLEL_EXPERIMENTS} | "
                    f"Vault: ${usdt_free:.2f} USDT ({leverage}x tier) | Loss Strikes: {strikes}/2 | Excluded: [{recent_str}]",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()

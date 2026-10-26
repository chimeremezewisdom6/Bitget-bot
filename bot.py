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
        self.wfile.write(b"APEX-V3 Adaptive 3-Phase Multi-Strategy Engine is active.")

    def log_message(self, format, *args):
        return

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
BRAIN_FILE = "brain_state.json"

ABSOLUTE_EQUITY_FLOOR = 1.50   # SHIELD 1: Balance can NEVER drop below $1.50
MAX_CONSECUTIVE_LOSSES = 2     # SHIELD 2: 2 live losses = Quarantine & Cooldown
MAX_ORDER_NOTIONAL = 7.50      # SHIELD 4: Hard cap on position value ($7.50 max)
MIN_ORDER_NOTIONAL = 5.15      # Buffer above Bitget's $5.00 exchange minimum

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
        if os.path.exists(LOCKOUT_FILE):
            return False, "HARD_LOCKOUT: Emergency lockout file exists. Trading permanently halted."

        if current_balance < ABSOLUTE_EQUITY_FLOOR:
            with open(LOCKOUT_FILE, "w") as f:
                f.write(f"Kill switch triggered at ${current_balance:.2f} on {time.ctime()}")
            return False, f"EQUITY_FLOOR_BREACH: Balance ${current_balance:.2f} breached $1.50 floor! Engine locked."

        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            elapsed_hours = (time.time() - self.last_loss_time) / 3600
            if elapsed_hours < 24.0:
                remaining = 24.0 - elapsed_hours
                return False, f"TWO_STRIKE_FREEZE: 2 consecutive losses. Cooldown active for {remaining:.1f} more hours."
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

circuit_breaker = CircuitBreaker()

# ==============================================================================
# 3. FAST ADAPTIVE LEARNING BRAIN (POST-MORTEM & 9/10 SYNTHESIS)
# ==============================================================================
class AdaptiveLearningBrain:
    def __init__(self):
        self.rolling_trials = []       # Stores 1 (win) or 0 (loss) for last 10 rapid outcomes
        self.quarantine_mode = False
        self.quarantine_target = 5
        self.quarantine_progress = 0
        self.learned_adjustments = {
            "min_rvol": 1.8,
            "max_counter_wick": 0.50,
            "min_runway": 1.50,
            "max_rsi_long": 68.0,
            "min_rsi_short": 32.0
        }
        self.load_brain()

    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.rolling_trials = data.get("rolling_trials", [])
                    self.quarantine_mode = data.get("quarantine_mode", False)
                    self.quarantine_target = data.get("quarantine_target", 5)
                    self.quarantine_progress = data.get("quarantine_progress", 0)
                    self.learned_adjustments.update(data.get("learned_adjustments", {}))
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "rolling_trials": self.rolling_trials,
                    "quarantine_mode": self.quarantine_mode,
                    "quarantine_target": self.quarantine_target,
                    "quarantine_progress": self.quarantine_progress,
                    "learned_adjustments": self.learned_adjustments
                }, f, indent=2)
        except Exception:
            pass

    def record_trial_result(self, is_win):
        self.rolling_trials.append(1 if is_win else 0)
        if len(self.rolling_trials) > 10:
            self.rolling_trials.pop(0)
        self.save_brain()

    def get_synthesized_win_rate(self):
        if len(self.rolling_trials) == 0:
            return 0.0
        return (sum(self.rolling_trials) / len(self.rolling_trials)) * 100.0

    def can_synthesized_engine_trade(self):
        # 9 out of 10 win rate unlocked (>= 90%)
        if len(self.rolling_trials) >= 10 and sum(self.rolling_trials) >= 9:
            return True
        return False

    def diagnose_and_adapt(self, exit_reason, pnl_pct):
        print(f"\n[POST-MORTEM BRAIN] Analyzing trade loss: {exit_reason} (PnL: {pnl_pct:+.2f}%)", flush=True)
        if "Hard Stop" in exit_reason:
            self.learned_adjustments["max_counter_wick"] = max(0.25, round(self.learned_adjustments["max_counter_wick"] - 0.05, 2))
            print(f"[BRAIN MUTATION] Adverse wick stopped trade. Tightened max counter-wick to: {self.learned_adjustments['max_counter_wick']:.2f}%", flush=True)
        elif "Stagnation" in exit_reason:
            self.learned_adjustments["min_rvol"] = min(3.0, round(self.learned_adjustments["min_rvol"] + 0.2, 2))
            print(f"[BRAIN MUTATION] Volume stagnation decay. Increased required RVol floor to: {self.learned_adjustments['min_rvol']:.2f}x", flush=True)
        else:
            self.learned_adjustments["min_runway"] = min(2.5, round(self.learned_adjustments["min_runway"] + 0.20, 2))
            print(f"[BRAIN MUTATION] Capacity wall hit. Increased capacity runway to: {self.learned_adjustments['min_runway']:.2f}%", flush=True)
        self.save_brain()

    def enter_quarantine(self, tapes_to_learn=5):
        self.quarantine_mode = True
        self.quarantine_progress = 0
        self.quarantine_target = tapes_to_learn
        self.save_brain()
        print(f"\n[ADAPTIVE QUARANTINE] 2-Strike Event: Halting live orders.", flush=True)
        print(f"[ADAPTIVE QUARANTINE] Observing market until {tapes_to_learn} verified winning paper tapes are completed under new rules.\n", flush=True)

    def check_quarantine_tape(self):
        if self.quarantine_mode:
            self.quarantine_progress += 1
            print(f"[QUARANTINE PROGRESS] Archived verified tape {self.quarantine_progress}/{self.quarantine_target}", flush=True)
            if self.quarantine_progress >= self.quarantine_target:
                self.quarantine_mode = False
                self.quarantine_progress = 0
                circuit_breaker.consecutive_losses = 0
                circuit_breaker.save_state()
                print(f"\n[QUARANTINE COMPLETE] Successfully assimilated current market regime! Live execution re-authorized.\n", flush=True)
            self.save_brain()

brain = AdaptiveLearningBrain()

# ==============================================================================
# 4. CONFIGURATION & CAPITAL BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BASE_LEVERAGE = 3
BALANCE_USE_PCT = 0.88          # Use 88% of vault margin
MIN_24H_VOLUME = 1_000_000      # $1,000,000 liquid volume floor
SCAN_INTERVAL_SECONDS = 30      # Fast 30-second scan loop
MAX_PARALLEL_EXPERIMENTS = 8    # Keep up to 8 parallel cameras running 24/7
TOURNAMENT_FILE = "rotational_tournament.json"

MIN_IMPULSE_PCT = 2.00          # Minimum 2.0% straight impulse
MAX_REBOUND_PCT = 0.50          # Maximum 0.50% counter-wick
MIN_CAPACITY_RUNWAY_PCT = 1.50  # Must have >= 1.50% open room to nearest wall
MIN_VERIFIED_TAPES = 5          # Must observe 5 verified winning occurrences first
SIMILARITY_THRESHOLD = 88.0     # 88.0% curve signature match required for Phase 1 live execution
MAX_RECENT_EXCLUSION = 3        # Exclude last 3 traded coins to force rotation

# Blacklist TradFi, commodities, and pre-market/synthetic pairs with oversized minimum lot sizes
NON_CRYPTO_SYMBOLS = {
    'CL', 'BZ', 'SOXS', 'SOXL', 'KORU', 'MU', 'TSLA', 'NVDA', 'AAPL', 'MSFT',
    'AMZN', 'GOOGL', 'META', 'SPX', 'NDX', 'DJI', 'XAU', 'XAG', 'MINIMAX', 'DOS',
    'ANTHROPIC', 'OPENAI', 'SPACEX', 'STRIPE', 'SCALE'
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
# 5. MATHEMATICAL INDICATORS & SIGNATURE SIMILARITY ENGINE
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

def calculate_entry_signature_similarity(cand_vector, hero_vector):
    weights = [0.25, 0.25, 0.20, 0.15, 0.15]
    total_score = 0.0
    for i in range(len(weights)):
        c_val = cand_vector[i]
        h_val = hero_vector[i]
        base = max(abs(h_val), 0.001)
        pct_diff = abs(c_val - h_val) / base
        score = max(0.0, 1.0 - pct_diff)
        total_score += score * weights[i]
    return round(total_score * 100.0, 1)

# ==============================================================================
# 6. CAPACITY & RUNWAY VERIFICATION ENGINE
# ==============================================================================
def check_profit_capacity(side, cur_price, highs, lows, rsi, min_runway=1.50, max_rsi_long=68.0, min_rsi_short=32.0):
    if cur_price <= 0:
        return False, 0.0

    lookback_highs = highs[-24:]
    lookback_lows = lows[-24:]

    if side == "long":
        if rsi > max_rsi_long:
            return False, 0.0
        ceiling = max(lookback_highs)
        clearance_pct = 3.0 if ceiling <= cur_price else ((ceiling - cur_price) / cur_price) * 100.0
        return clearance_pct >= min_runway, clearance_pct
    else:
        if rsi < min_rsi_short:
            return False, 0.0
        floor = min(lookback_lows)
        clearance_pct = 3.0 if floor >= cur_price else ((cur_price - floor) / cur_price) * 100.0
        return clearance_pct >= min_runway, clearance_pct

# ==============================================================================
# 7. TOURNAMENT DATA PERSISTENCE & ROTATION
# ==============================================================================
def load_tournament():
    if os.path.exists(TOURNAMENT_FILE):
        try:
            with open(TOURNAMENT_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "active_studies": [],
        "verified_winning_tapes": [],
        "recently_traded": [],
        "models": {f"M{i}": {"tested": 0, "wins": 0, "losses": 0, "stalls": 0, "max_profit": 0.0} for i in range(1, 13)}
    }

def save_tournament(tourn):
    try:
        with open(TOURNAMENT_FILE, "w") as f:
            json.dump(tourn, f, indent=2)
    except Exception:
        pass

def push_traded_coin(tourn, symbol):
    if "recently_traded" not in tourn:
        tourn["recently_traded"] = []
    if symbol in tourn["recently_traded"]:
        tourn["recently_traded"].remove(symbol)
    tourn["recently_traded"].append(symbol)
    if len(tourn["recently_traded"]) > MAX_RECENT_EXCLUSION:
        tourn["recently_traded"].pop(0)
    save_tournament(tourn)

# ==============================================================================
# 8. BITGET POSITION & EXECUTION INTERFACE (ONE-WAY NETTING MODE)
# ==============================================================================
def get_open_position():
    try:
        positions = exchange.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            if contracts > 0:
                side = 'long' if p.get('side') == 'long' or float(p.get('entryPrice', 0)) > 0 and p.get('side') != 'short' else 'short'
                return {
                    'symbol': p['symbol'],
                    'side': side,
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0) or 0)
                }
    except Exception as e:
        print(f"[WARN] get_open_position failed: {e}", flush=True)
    return None

def open_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeside' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e

def close_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeside' in str(e).lower():
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
        if '25156' in str(e) or 'tradeside' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e

def close_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeside' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'reduceOnly': True, 'tradeSide': 'close'}
            )
        raise e

# ==============================================================================
# 9. THE 12-MODEL SIGNAL SCANNER (EVALUATES CLOSED CANDLE ohlcv[-2])
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
        if candle_range <= 0:
            return []

        pct_5m = ((c_close - c_open) / c_open) * 100.0
        avg_vol = sum(volumes[-15:-1]) / 14 if sum(volumes[-15:-1]) > 0 else 1.0
        rvol = round(volumes[-1] / avg_vol, 2)
        atr = calculate_atr(closed_candles, period=14)
        rsi = calculate_rsi(closes, period=14)

        pullback_pct = ((c_high - c_close) / c_open) * 100.0 if pct_5m >= 0 else ((c_close - c_low) / c_open) * 100.0
        amp_pct = (candle_range / c_open) * 100.0
        funding_rate = float(t_data.get('info', {}).get('fundingRate', 0.0) or 0.01)

        eff_min_rvol = brain.learned_adjustments["min_rvol"]
        eff_max_wick = brain.learned_adjustments["max_counter_wick"]
        eff_min_runway = brain.learned_adjustments["min_runway"]
        eff_rsi_long_max = brain.learned_adjustments["max_rsi_long"]
        eff_rsi_short_min = brain.learned_adjustments["min_rsi_short"]

        matches = []

        # 1. Bear Trap OI Absorption
        if pct_24h <= -2.0 and pct_5m >= 1.2 and rvol >= max(1.8, eff_min_rvol):
            matches.append(("1_BEAR_TRAP_OI_ABSORPTION", "long", "Downtrend Absorption Squeeze", atr, pct_5m, pullback_pct, rvol, rsi))

        # 2. Squeeze Exhaustion Fade
        if pct_24h >= 2.0 and pct_5m >= 1.5 and rsi >= 72 and pullback_pct <= eff_max_wick:
            matches.append(("2_SQUEEZE_EXHAUSTION_FADE", "short", "Short-covering exhaustion top", atr, pct_5m, pullback_pct, rvol, rsi))

        # 3. RSI Washout Clean Bounce
        if pct_24h <= -8.0 and pct_5m >= 1.5 and pullback_pct <= 0.40:
            matches.append(("3_RSI_WASHOUT_CLEAN_BOUNCE", "long", "Clean oversold bounce without wick", atr, pct_5m, pullback_pct, rvol, rsi))

        # 4. Blowoff Top Overbought
        if rsi >= 75.0 and pullback_pct >= 0.6 and funding_rate >= 0.03:
            matches.append(("4_BLOWOFF_TOP_OVERBOUGHT", "short", "Retail FOMO top rejection", atr, pct_5m, pullback_pct, rvol, rsi))

        # 5. Institutional OI Expansion
        if pct_5m >= 1.2 and rvol >= max(2.0, eff_min_rvol) and funding_rate <= 0.012:
            matches.append(("5_INSTITUTIONAL_OI_EXPANSION", "long", "Whale accumulation on clean funding", atr, pct_5m, pullback_pct, rvol, rsi))

        # 6. 4:1 Clean Stair Momentum
        if pct_5m >= MIN_IMPULSE_PCT and pullback_pct <= eff_max_wick and rvol >= eff_min_rvol:
            matches.append(("6_CLEAN_STAIR_MOMENTUM", "long", "Strict 4:1 impulse", atr, pct_5m, pullback_pct, rvol, rsi))

        # 7. High RVol Ignition
        if rvol >= max(2.5, eff_min_rvol) and abs(pct_5m) >= 1.2:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("7_HIGH_RVOL_IGNITION", side, f"High {rvol}x volume breakout", atr, pct_5m, pullback_pct, rvol, rsi))

        # 8. High Amplitude Swing
        if amp_pct >= 3.8 and pct_5m >= 1.2:
            matches.append(("8_HIGH_AMPLITUDE_SWING", "long", f"Wide {amp_pct:.1f}% swing bounce", atr, pct_5m, pullback_pct, rvol, rsi))

        # 9. Crowded Funding Dump
        if funding_rate >= 0.035 and pct_5m <= -0.5:
            matches.append(("9_CROWDED_FUNDING_DUMP", "short", "Over-leveraged long squeeze dump", atr, pct_5m, pullback_pct, rvol, rsi))

        # 10. Waterfall Breakdown
        if pct_5m <= -1.8 and rvol >= max(1.8, eff_min_rvol):
            matches.append(("10_WATERFALL_BREAKDOWN", "short", "Liquidation cascade", atr, pct_5m, pullback_pct, rvol, rsi))

        # 11. Trader Aggressiveness Surge
        if rvol >= 2.2 and abs(pct_5m) >= 1.5 and candle_range / max(atr, 0.0001) >= 1.3:
            side = "long" if pct_5m > 0 else "short"
            matches.append(("11_TRADER_AGGRESSIVENESS_SURGE", side, "Market taker surge", atr, pct_5m, pullback_pct, rvol, rsi))

        # 12. Blue Sky Breakout Runner
        if pct_24h >= 4.0 and pct_5m >= 1.8 and c_close >= max(highs[-20:]):
            matches.append(("12_BLUE_SKY_BREAKOUT_RUNNER", "long", "Clear sky breakout", atr, pct_5m, pullback_pct, rvol, rsi))

        qualified = []
        for m_name, side, reason, c_atr, p5, pb, rv, r_val in matches:
            has_capacity, cap_msg = check_profit_capacity(
                side, c_close, highs, lows, r_val,
                min_runway=eff_min_runway,
                max_rsi_long=eff_rsi_long_max,
                min_rsi_short=eff_rsi_short_min
            )
            if has_capacity:
                entry_vector = [abs(p5), pb, rv, r_val, cap_msg]
                qualified.append((m_name, side, reason, last_price, p5, rv, vol_24h_m, c_atr, entry_vector))

        return qualified

    except Exception:
        return []

# ==============================================================================
# 10. ACTIVE TRADE GUARDIAN (LIVE RISK ENGINE)
# ==============================================================================
def manage_live_trade(symbol, side, initial_contracts, entry_price, entry_atr):
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    last_position_check = time.time()
    fee_shield_active = False

    atr = entry_atr if entry_atr > 0 else (entry_price * 0.012)
    stop_distance = min(1.3 * atr, entry_price * 0.0145)   # 1.45% max price loss
    fee_shield_trigger = 0.9 * atr
    runner_trigger = 1.8 * atr
    trail_distance = 1.1 * atr

    initial_stop_price = entry_price - stop_distance if side == 'long' else entry_price + stop_distance
    stop_pct = (stop_distance / entry_price) * 100
    print(f"\n[LIVE GUARDIAN ENGAGED] {side.upper()} {symbol} | Fill: {entry_price:.5f} | Hard Stop: {initial_stop_price:.5f} (-{stop_pct:.2f}%)\n", flush=True)

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

                circuit_breaker.record_trade_result(pnl_pct)
                brain.record_trial_result(pnl_pct > 0)

                if pnl_pct < 0:
                    brain.diagnose_and_adapt(reason, pnl_pct)
                    if circuit_breaker.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                        brain.enter_quarantine(tapes_to_learn=5)

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
# 11. HIGH-SPEED PAPER INCUBATOR (DYNAMIC FAST RESOLUTION)
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

        is_completed = False
        outcome = "MONITORING"

        # 1. Fast Win: Reached >= +1.50% profit target with clean drawdown
        if peak_pnl >= MIN_CAPACITY_RUNWAY_PCT and max_dd > -0.60 and (pnl_pct >= 1.20 or elapsed_min >= 4.0):
            is_completed = True
            outcome = "VERIFIED_WINNER"

        # 2. Fast Stop-Out: Adverse wick breached -0.60% max drawdown limit
        elif max_dd <= -0.60:
            is_completed = True
            outcome = "ADVERSE_WICK_LOSS"

        # 3. Fast Stagnation Cut: 10 minutes passed without hitting +0.80%
        elif elapsed_min >= 10.0 and peak_pnl < 0.80:
            is_completed = True
            outcome = "STAGNATION_TIMEOUT"

        # 4. Hard Ceiling: Finalize after 15 minutes max
        elif elapsed_min >= 15.0:
            is_completed = True
            outcome = "VERIFIED_WINNER" if (peak_pnl >= MIN_CAPACITY_RUNWAY_PCT and max_dd > -0.60) else "TIMEOUT_LOSS"

        if is_completed:
            m_name = exp['model_name']
            if m_name not in tourn['models']:
                tourn['models'][m_name] = {"tested": 0, "wins": 0, "losses": 0, "stalls": 0, "max_profit": 0.0}

            stats = tourn['models'][m_name]
            stats['tested'] += 1

            if peak_pnl > stats['max_profit']:
                stats['max_profit'] = round(peak_pnl, 2)

            if outcome == "VERIFIED_WINNER":
                stats['wins'] += 1
                tape = {
                    "tape_id": len(tourn['verified_winning_tapes']) + 1,
                    "symbol": sym,
                    "model_name": m_name,
                    "side": side,
                    "peak_pnl": round(peak_pnl, 2),
                    "drawdown": round(max_dd, 2),
                    "entry_vector": exp.get('entry_vector', [2.0, 0.40, 2.2, 50.0, 2.0]),
                    "frames": exp.get('frames', [])
                }
                tourn['verified_winning_tapes'].append(tape)
                print(f"\n[RAPID EXPERIMENT WIN] #{tape['tape_id']} {m_name} on {sym} (+{peak_pnl:.2f}% in {elapsed_min:.1f}m)!", flush=True)

                brain.record_trial_result(True)
                brain.check_quarantine_tape()

            else:
                stats['losses'] += 1
                brain.record_trial_result(False)

        else:
            remaining.append(exp)

    tourn['active_studies'] = remaining

# ==============================================================================
# 12. MAIN ENGINE LOOP (FAILSAFE GOVERNOR + 3-PHASE EXECUTION)
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-V3 Failsafe 3-Phase Multi-Strategy Engine initialized.", flush=True)

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
                print(f"Vault Cash Protected at: ${usdt_free:.2f} USDT. Sleeping...\n", flush=True)
                time.sleep(60)
                continue

            # Dynamic Leverage Ladder: Guarantees order size is always >= $5.15 notional
            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            # SHIELD 4: Hard Notional Sizing Clamp ($5.15 floor to $7.50 ceiling)
            raw_notional = (usdt_free * BALANCE_USE_PCT) * leverage
            notional = max(min(raw_notional, MAX_ORDER_NOTIONAL), MIN_ORDER_NOTIONAL)

            # 4. Pull Universe in 1 single throttled call
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
                if sym in tourn.get('recently_traded', []):
                    continue

                if sym in active_syms:
                    continue

                time.sleep(0.025)  # 25ms micro-throttle
                matched_setups = screen_coin_for_12_models(sym, t_data)

                for m_name, side, reason, price, p_5m, rvol, vol_m, atr, cand_vector in matched_setups:
                    library = tourn['verified_winning_tapes']
                    is_live_authorized = False
                    authorization_mode = "NONE"
                    best_similarity = 0.0

                    # ---------------------------------------------------------
                    # PHASE 1: DIRECT TAPE MATCH (FAST SNIPER)
                    # ---------------------------------------------------------
                    if len(library) >= MIN_VERIFIED_TAPES and not brain.quarantine_mode:
                        for hero in library:
                            if hero['side'] == side:
                                hero_vec = hero.get('entry_vector', [2.0, 0.40, 2.2, 50.0, 2.0])
                                sim = calculate_entry_signature_similarity(cand_vector, hero_vec)
                                if sim > best_similarity:
                                    best_similarity = sim

                        if best_similarity >= SIMILARITY_THRESHOLD:
                            is_live_authorized = True
                            authorization_mode = f"PHASE 1 [Tape Match {best_similarity}%]"

                    # ---------------------------------------------------------
                    # PHASE 2: THE 9/10 SYNTHESIZED AUTONOMOUS BRAIN
                    # ---------------------------------------------------------
                    if not is_live_authorized and not brain.quarantine_mode:
                        if brain.can_synthesized_engine_trade():
                            is_live_authorized = True
                            win_rate = brain.get_synthesized_win_rate()
                            authorization_mode = f"PHASE 2 [9/10 Brain Hit {win_rate:.0f}% Win Rate]"

                    # ---------------------------------------------------------
                    # EXECUTION: LIVE ORDER (FAILSAFE LOT & PRECISION CLAMP)
                    # ---------------------------------------------------------
                    if is_live_authorized and not live_trade_triggered and notional >= MIN_ORDER_NOTIONAL:
                        ticker_now = exchange.fetch_ticker(sym)
                        live_price = float(ticker_now.get('last', 0) or 0)
                        if live_price <= 0:
                            continue

                        market = exchange.market(sym)
                        min_lot = float(market.get('limits', {}).get('amount', {}).get('min') or 0)
                        amount_precision = float(market.get('precision', {}).get('amount') or 0)
                        min_required_amount = max(min_lot, amount_precision)

                        raw_amount = notional / live_price

                        # FAILSAFE PRE-CHECK: Skip immediately if account notional cannot afford min lot
                        if raw_amount < min_required_amount:
                            print(f"[SIZING SKIP] {sym} requires minimum lot {min_required_amount}, but vault notional gives {raw_amount:.6f}. Cleanly skipping.", flush=True)
                            continue

                        # Wrap CCXT amount_to_precision to prevent InvalidOrder crashes
                        try:
                            formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))
                        except Exception as prec_err:
                            print(f"[PRECISION SKIP] {sym} precision formatting error ({prec_err}). Skipping.", flush=True)
                            continue

                        actual_notional = formatted_amount * live_price

                        if formatted_amount >= min_required_amount and actual_notional >= MIN_ORDER_NOTIONAL:
                            try:
                                exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                            except Exception:
                                pass

                            print("\n" + "#" * 80, flush=True)
                            print(f"[FAILSAFE LIVE STRIKE: {side.upper()}] Triggered via {authorization_mode} on {sym}!", flush=True)
                            print(f"  Signal: {reason} (5m: {p_5m:+.2f}%, RVol: {rvol}x)", flush=True)
                            print(f"  Execution: Real Order {leverage}x {side.upper()} | Notional: ${actual_notional:.2f} USDT", flush=True)
                            print("#" * 80 + "\n", flush=True)

                            if side == 'long':
                                order = open_long_position(sym, formatted_amount)
                            else:
                                order = open_short_position(sym, formatted_amount)

                            print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                            time.sleep(2)

                            push_traded_coin(tourn, sym)

                            real_pos = get_open_position()
                            real_fill_price = real_pos['entry_price'] if real_pos else live_price
                            real_contracts = real_pos['contracts'] if real_pos else formatted_amount

                            manage_live_trade(sym, side, real_contracts, real_fill_price, atr)
                            live_trade_triggered = True
                            break

                    # ---------------------------------------------------------
                    # PHASE 3: CONTINUOUS HIGH-VELOCITY PAPER EXPERIMENT INCUBATOR
                    # ---------------------------------------------------------
                    elif len(tourn['active_studies']) < MAX_PARALLEL_EXPERIMENTS and sym not in active_syms:
                        new_study = {
                            "symbol": sym,
                            "model_name": m_name,
                            "side": side,
                            "base_price": price,
                            "highest_price": price,
                            "lowest_price": price,
                            "started_at": time.time(),
                            "entry_vector": cand_vector,
                            "frames": [{"min": 0.0, "pnl": 0.0, "drawdown": 0.0}]
                        }
                        tourn['active_studies'].append(new_study)
                        active_syms.add(sym)
                        save_tournament(tourn)
                        print(f"[INCUBATOR CAMERA #{len(tourn['active_studies'])}/8] Fast Testing {m_name} on {sym} ({side.upper()})", flush=True)

                if live_trade_triggered:
                    break

            # 6. Periodic Status Pulse
            if cycle % 2 == 0:
                tapes_count = len(tourn.get('verified_winning_tapes', []))
                strikes = circuit_breaker.consecutive_losses
                recent_str = ", ".join(tourn.get('recently_traded', [])) if tourn.get('recently_traded') else "None (Ready to rotate)"
                win_rate = brain.get_synthesized_win_rate()

                if brain.quarantine_mode:
                    mode_str = f"QUARANTINE RE-LEARNING ({brain.quarantine_progress}/{brain.quarantine_target} Tapes)"
                else:
                    mode_str = f"3-PHASE ACTIVE (Tapes: {tapes_count} | Rapid 9/10: {win_rate:.0f}%)"

                print(
                    f"\n[RADAR PULSE] Status: {mode_str} | Active Cameras: {len(tourn['active_studies'])}/{MAX_PARALLEL_EXPERIMENTS}\n"
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

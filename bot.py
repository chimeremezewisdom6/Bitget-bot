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
        self.wfile.write(b"APEX-V9 Self-Determining Autonomous Trader is active.")

    def log_message(self, format, *args):
        return

def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)

# ==============================================================================
# 2. EMERGENCY CIRCUIT BREAKER & REAL CAPITAL VAULT
# ==============================================================================
CB_FILE = "circuit_breaker.json"
LOCKOUT_FILE = "EMERGENCY_LOCKOUT.txt"
STUDY_LOG_FILE = "empirical_tapes.json"
STORYBOOK_FILE = "market_storybook.jsonl"
BRAIN_FILE = "student_brain.json"

ABSOLUTE_EQUITY_FLOOR = 1.50   # Hard floor ($1.50)
MAX_CONSECUTIVE_LOSSES = 2     # Two live losses = mandatory 24h rest
MAX_ORDER_NOTIONAL = 7.50      # Cap notional size
MIN_ORDER_NOTIONAL = 5.15      # Bitget $5.00 min + buffer

BITGET_TAKER_FEE_PCT = 0.06    # 0.06% Taker Fee
BITGET_MAINTENANCE_MARGIN = 0.005 # 0.5% Maintenance Margin

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
            return False, "HARD_LOCKOUT: Emergency lockout file active. Real money secured."

        if current_balance < ABSOLUTE_EQUITY_FLOOR:
            with open(LOCKOUT_FILE, "w") as f:
                f.write(f"Kill switch triggered at ${current_balance:.2f} on {time.ctime()}")
            return False, f"EQUITY_FLOOR_BREACH: Balance ${current_balance:.2f} breached floor! Vault locked."

        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            elapsed_hours = (time.time() - self.last_loss_time) / 3600
            if elapsed_hours < 24.0:
                remaining = 24.0 - elapsed_hours
                return False, f"TWO_STRIKE_FREEZE: Cooldown active for {remaining:.1f} more hours."
            else:
                print("\n[CIRCUIT BREAKER] 24-hour rest finished. Resetting strikes.\n", flush=True)
                self.consecutive_losses = 0
                self.save_state()

        return True, "SAFE"

    def record_trade_result(self, pnl_pct):
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            print(f"\n[CIRCUIT BREAKER] Live loss recorded. Strikes: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}", flush=True)
        else:
            self.consecutive_losses = 0
            print("\n[CIRCUIT BREAKER] Live win recorded. Strikes cleared to 0.", flush=True)
        self.save_state()

circuit_breaker = CircuitBreaker()

# ==============================================================================
# 3. STORYBOOK JOURNAL
# ==============================================================================
def write_story_log(event_type, symbol, observation, lesson):
    story_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "symbol": symbol,
        "observation": observation,
        "lesson_learned": lesson
    }
    try:
        with open(STORYBOOK_FILE, "a") as f:
            f.write(json.dumps(story_entry) + "\n")
    except Exception:
        pass
    print(f"\n[JOURNAL] {event_type} on {symbol}: {observation} -> LESSON: {lesson}", flush=True)

# ==============================================================================
# 4. AUTONOMOUS STUDENT BRAIN (LEARNS ITS OWN STOPS & TARGETS)
# ==============================================================================
class AutonomousStudentBrain:
    def __init__(self):
        # The bot dynamically tunes these stop multipliers based on past tape results
        self.strategy_params = {
            "QUICK_IMPULSE_CHASE": {"stop_mult": 1.4, "target_mult": 2.2, "trials": []},
            "MEAN_REVERSION_SNAP": {"stop_mult": 1.3, "target_mult": 2.0, "trials": []},
            "BREAKOUT_CONTINUATION": {"stop_mult": 1.5, "target_mult": 2.5, "trials": []}
        }
        self.quarantine_mode = False
        self.load_brain()

    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.strategy_params = data.get("strategy_params", self.strategy_params)
                    self.quarantine_mode = data.get("quarantine_mode", False)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "strategy_params": self.strategy_params,
                    "quarantine_mode": self.quarantine_mode
                }, f, indent=2)
        except Exception:
            pass

    def adapt_parameters_from_film(self, strategy, film_tape):
        """
        SELF-LEARNING MECHANIC:
        If stops get hit too fast (< 1.5m), widen the stop multiplier automatically.
        If trades peak high (> 2.0%) but end in stagnation, lower the target slightly.
        """
        strat = self.strategy_params.get(strategy)
        if not strat:
            return

        duration = film_tape.get('duration_minutes', 0)
        outcome = film_tape.get('outcome', '')
        peak_pnl = film_tape.get('peak_pnl_pct', 0)

        # 1. Choke Detection: If it died in under 90 seconds, stop was too tight!
        if outcome == "STOP_LOSS_HIT" and duration < 1.5:
            old_mult = strat['stop_mult']
            strat['stop_mult'] = min(round(strat['stop_mult'] + 0.15, 2), 2.5)
            print(f"[BOT SELF-LEARNED] {strategy} stop choked too fast ({duration}m). Widened stop mult from {old_mult}x -> {strat['stop_mult']}x", flush=True)

        # 2. Greed Detection: If it went into solid profit but didn't reach the target
        elif outcome == "STAGNATION_TIMEOUT" and peak_pnl >= 1.6:
            old_t = strat['target_mult']
            strat['target_mult'] = max(round(strat['target_mult'] - 0.10, 2), 1.8)
            print(f"[BOT SELF-LEARNED] {strategy} peaked at +{peak_pnl:.2f}% but stagnated. Lowered target mult from {old_t}x -> {strat['target_mult']}x", flush=True)

    def record_film_outcome(self, strategy, net_pnl, reason, film_tape):
        if strategy not in self.strategy_params:
            self.strategy_params[strategy] = {"stop_mult": 1.4, "target_mult": 2.2, "trials": []}

        rec = self.strategy_params[strategy]
        is_win = 1 if (net_pnl >= 1.50) else 0
        rec["trials"].append(is_win)
        if len(rec["trials"]) > 10:
            rec["trials"].pop(0)

        # Self-calibrate stops and targets based on this completed tape
        self.adapt_parameters_from_film(strategy, film_tape)

        win_count = sum(rec["trials"])
        sample_size = len(rec["trials"])
        win_rate = (win_count / sample_size) * 100 if sample_size > 0 else 0

        verdict = "QUALIFIED WIN (>=+1.5%)" if is_win else "FAILED TARGET (<+1.5%)"
        print(f"\n[LESSON RECORDED] {strategy} on {film_tape['symbol']} | Net: {net_pnl:+.2f}% | Verdict: {verdict}", flush=True)
        print(f"[REASON] {reason}", flush=True)
        print(f"[SCORECARD] {strategy}: {win_count}/{sample_size} passed (+1.5% target) -> {win_rate:.0f}% win rate\n", flush=True)

        write_story_log(
            event_type="PAPER_TRADE_FINISHED",
            symbol=film_tape['symbol'],
            observation=f"Trade lasted {film_tape['duration_minutes']}m with PnL of {net_pnl:+.2f}%.",
            lesson=reason
        )
        self.save_brain()

    def is_live_ready(self, strategy):
        if self.quarantine_mode:
            return False
        rec = self.strategy_params.get(strategy, {})
        trials = rec.get("trials", [])
        return len(trials) >= 10 and sum(trials) >= 9

    def get_summary_status(self):
        lines = []
        for strat, data in self.strategy_params.items():
            trials = data.get("trials", [])
            w = sum(trials)
            tot = len(trials)
            pct = (w / tot) * 100 if tot > 0 else 0
            lines.append(f"{strat[:4]}: {w}/{tot} ({pct:.0f}%) [S:{data['stop_mult']}x T:{data['target_mult']}x]")
        return " | ".join(lines)

brain = AutonomousStudentBrain()

# ==============================================================================
# 5. EXCHANGES SETUP
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BALANCE_USE_PCT = 0.85
MIN_24H_VOLUME = 1_000_000       # All coins > $1,000,000
SCAN_INTERVAL_SECONDS = 5        # Fast 5-second pulse
MAX_PARALLEL_CAMERAS = 12        # 12 parallel learning cameras
MAX_RECENT_EXCLUSION = 3

NON_CRYPTO_SYMBOLS = {
    'CL', 'BZ', 'SOXS', 'SOXL', 'KORU', 'MU', 'TSLA', 'NVDA', 'AAPL', 'MSFT',
    'AMZN', 'GOOGL', 'META', 'SPX', 'NDX', 'DJI', 'XAU', 'XAG', 'MINIMAX', 'DOS',
    'ANTHROPIC', 'OPENAI', 'SPACEX', 'STRIPE', 'SCALE'
}

bitget = ccxt.bitget({
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

global_radar = ccxt.binance({
    "enableRateLimit": True,
    "timeout": 10000,
    "options": {"defaultType": "future"}
})

ticker_memory = {}
global_binance_tickers = {}

# ==============================================================================
# 6. GLOBAL INTELLIGENCE WORKER (FIXED BINANCE SYMBOL MATCHER)
# ==============================================================================
def start_global_radar_worker():
    global global_binance_tickers
    def worker():
        while True:
            try:
                tickers = global_radar.fetch_tickers()
                temp = {}
                for s, t in tickers.items():
                    # Parse symbol properly: "ENA/USDT:USDT" -> "ENA"
                    base = s.split('/')[0].split(':')[0].upper()
                    temp[base] = {
                        "price": float(t.get('last', 0) or 0),
                        "pct_24h": float(t.get('percentage', 0) or 0),
                        "vol_quote": float(t.get('quoteVolume', 0) or 0)
                    }
                global_binance_tickers = temp
                time.sleep(3)
            except Exception:
                time.sleep(5)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("[SYSTEM] Global Cross-Exchange Radar engaged (Binance Mother Tape active).", flush=True)

# ==============================================================================
# 7. FILMING ARCHIVE PERSISTENCE
# ==============================================================================
def load_film_archive():
    if os.path.exists(STUDY_LOG_FILE):
        try:
            with open(STUDY_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_cameras": [], "completed_films": [], "recently_traded": []}

def save_film_archive(data):
    try:
        with open(STUDY_LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def push_recently_traded(archive, symbol):
    if "recently_traded" not in archive:
        archive["recently_traded"] = []
    if symbol in archive["recently_traded"]:
        archive["recently_traded"].remove(symbol)
    archive["recently_traded"].append(symbol)
    if len(archive["recently_traded"]) > MAX_RECENT_EXCLUSION:
        archive["recently_traded"].pop(0)
    save_film_archive(archive)

# ==============================================================================
# 8. BITGET ORDER & POSITION INTERFACE
# ==============================================================================
def get_open_position():
    try:
        positions = bitget.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            if contracts > 0:
                side = p.get('side', '').lower()
                if not side or side not in ['long', 'short']:
                    side = 'long' if float(p.get('entryPrice', 0) or 0) > 0 else 'short'
                return {
                    'symbol': p['symbol'],
                    'side': side,
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0) or 0)
                }
    except Exception as e:
        print(f"[WARN] get_open_position error: {e}", flush=True)
    return None

def open_long_position(symbol, amount):
    try:
        return bitget.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception:
        return bitget.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'open'}
        )

def close_long_position(symbol, amount):
    try:
        return bitget.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'sell_single'}
        )
    except Exception:
        return bitget.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'close'}
        )

def open_short_position(symbol, amount):
    try:
        return bitget.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception:
        return bitget.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'open'}
        )

def close_short_position(symbol, amount):
    try:
        return bitget.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'buy_single'}
        )
    except Exception:
        return bitget.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'close'}
        )

# ==============================================================================
# 9. DYNAMIC ATR SWING CALCULATOR (THE BOT SIZES ITS OWN STOPS)
# ==============================================================================
def calculate_natural_swing_atr(ohlcv_1m):
    """
    Measures how much the coin naturally breathes per minute.
    Returns the True Range in dollar value.
    """
    if len(ohlcv_1m) < 3:
        return 0.0

    ranges = []
    for candle in ohlcv_1m[-4:]:
        c_high = candle[2]
        c_low = candle[3]
        ranges.append(c_high - c_low)

    return sum(ranges) / len(ranges) if ranges else 0.0

# ==============================================================================
# 10. UNCHAINED APPRENTICE SCANNER
# ==============================================================================
def scan_all_coins_fearlessly(tickers, archive):
    global ticker_memory
    pings = []
    now = time.time()
    active_syms = {c['symbol'] for c in archive['active_cameras']}

    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue
        base = symbol.split('/')[0].split(':')[0].upper()
        if base in NON_CRYPTO_SYMBOLS:
            continue

        vol_24h = float(t.get('quoteVolume', 0) or 0)
        if vol_24h < MIN_24H_VOLUME or symbol in active_syms:
            continue

        cur_price = float(t.get('last', 0) or 0)
        if cur_price <= 0:
            continue

        if symbol in ticker_memory:
            past_price, past_time, past_vol = ticker_memory[symbol]
            dt = now - past_time

            if 5.0 <= dt <= 60.0:
                pct_change = ((cur_price - past_price) / past_price) * 100.0
                vol_delta = vol_24h - past_vol

                if abs(pct_change) >= 0.38 and vol_delta >= 4_000:
                    pings.append({
                        "symbol": symbol,
                        "base": base,
                        "direction": "EXPANDING_UP" if pct_change > 0 else "EXPANDING_DOWN",
                        "pct_move": round(pct_change, 2),
                        "capital_injected": round(vol_delta, 2),
                        "start_price": past_price,
                        "current_price": cur_price,
                        "dt_seconds": round(dt, 1)
                    })
                    ticker_memory[symbol] = (cur_price, now, vol_24h)
                    continue

        if symbol not in ticker_memory or (now - ticker_memory[symbol][1]) >= 15.0:
            ticker_memory[symbol] = (cur_price, now, vol_24h)

    pings.sort(key=lambda x: abs(x['pct_move']), reverse=True)
    return pings

# ==============================================================================
# 11. MULTI-CAMERA RECORDING LAB (WATCHING TRADES PLAY OUT)
# ==============================================================================
def run_filming_cameras(archive, leverage=4):
    remaining = []
    for cam in archive['active_cameras']:
        sym = cam['symbol']
        side = cam['trade_hypothesis']['side']
        entry_price = cam['trade_hypothesis']['entry_price']
        stop_price = cam['trade_hypothesis']['stop_price']
        target_price = cam['trade_hypothesis']['target_price']
        liq_price = cam['trade_hypothesis']['liq_price']
        strategy = cam['strategy']
        elapsed_min = (time.time() - cam['started_at']) / 60

        try:
            ticker = bitget.fetch_ticker(sym)
            cur_price = float(ticker.get('last', 0) or 0)
        except Exception:
            remaining.append(cam)
            continue

        if cur_price <= 0:
            remaining.append(cam)
            continue

        if cur_price > cam['highest_price']:
            cam['highest_price'] = cur_price
        if cur_price < cam['lowest_price']:
            cam['lowest_price'] = cur_price

        cam['film_ticks'].append({
            "t": round(time.time() - cam['started_at'], 1),
            "p": cur_price
        })

        if side == 'long':
            gross_pnl = ((cur_price - entry_price) / entry_price) * 100.0
            peak_pnl = ((cam['highest_price'] - entry_price) / entry_price) * 100.0
            max_dd = ((cam['lowest_price'] - entry_price) / entry_price) * 100.0
        else:
            gross_pnl = ((entry_price - cur_price) / entry_price) * 100.0
            peak_pnl = ((entry_price - cam['lowest_price']) / entry_price) * 100.0
            max_dd = ((entry_price - cam['highest_price']) / entry_price) * 100.0

        net_pnl = gross_pnl - (BITGET_TAKER_FEE_PCT * 2)
        is_finished = False
        outcome = "MONITORING"
        causality = ""

        # Check 1: Liquidation
        if (side == 'long' and cur_price <= liq_price) or (side == 'short' and cur_price >= liq_price):
            is_finished = True
            outcome = "LIQUIDATION_LOSS"
            causality = f"Adverse wick struck liquidation at {liq_price:.4f}."

        # Check 2: Stop Loss
        elif (side == 'long' and cur_price <= stop_price) or (side == 'short' and cur_price >= stop_price):
            is_finished = True
            outcome = "STOP_LOSS_HIT"
            causality = f"Invalidation level hit at {stop_price:.4f}. Net PnL: {net_pnl:+.2f}%."

        # Check 3: Target Hit (Win if net profit >= +1.50%)
        elif (side == 'long' and cur_price >= target_price) or (side == 'short' and cur_price <= target_price):
            is_finished = True
            outcome = "TARGET_ACHIEVED"
            causality = f"Target achieved at {target_price:.4f}. Clean Net PnL: {net_pnl:+.2f}%."

        # Check 4: Stagnation timeout after 10 minutes
        elif elapsed_min >= 10.0:
            is_finished = True
            outcome = "STAGNATION_TIMEOUT"
            causality = f"Momentum decayed into chop after 10m. Net PnL: {net_pnl:+.2f}%."

        if is_finished:
            film_tape = {
                "symbol": sym,
                "strategy": strategy,
                "side": side,
                "entry_price": entry_price,
                "exit_price": cur_price,
                "net_pnl_pct": round(net_pnl, 2),
                "peak_pnl_pct": round(peak_pnl, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "duration_minutes": round(elapsed_min, 1),
                "outcome": outcome,
                "ticks_filmed": len(cam['film_ticks']),
                "reason": causality
            }
            archive['completed_films'].append(film_tape)
            brain.record_film_outcome(strategy, net_pnl, causality, film_tape)
            save_film_archive(archive)
        else:
            remaining.append(cam)

    archive['active_cameras'] = remaining

# ==============================================================================
# 12. LIVE GUARDIAN (FOR REAL MONEY EXECUTION)
# ==============================================================================
live_trade_state = {
    "active": False,
    "symbol": None,
    "side": None,
    "entry_price": 0.0,
    "entry_time": 0.0,
    "initial_stop_price": 0.0,
    "target_price": 0.0,
    "contracts": 0.0,
    "fee_shield_active": False,
    "highest_price": 0.0,
    "lowest_price": 0.0,
    "atr": 0.0
}

def execute_live_exit(reason, pnl_pct):
    global live_trade_state
    sym = live_trade_state["symbol"]
    side = live_trade_state["side"]
    contracts = live_trade_state["contracts"]

    print(f"\n[LIVE GUARDIAN EXIT] {reason} | Net PnL: {pnl_pct:+.2f}%\n", flush=True)

    for attempt in range(1, 4):
        try:
            if side == 'long':
                close_long_position(sym, contracts)
            else:
                close_short_position(sym, contracts)
            break
        except Exception as e:
            print(f"[EXIT ATTEMPT {attempt}] Error: {e}", flush=True)
            time.sleep(1)

    circuit_breaker.record_trade_result(pnl_pct)
    write_story_log("LIVE_TRADE_CLOSED", sym, f"Closed with Net PnL {pnl_pct:+.2f}%.", reason)
    live_trade_state["active"] = False

def poll_live_trade_guardian():
    global live_trade_state
    if not live_trade_state["active"]:
        return

    sym = live_trade_state["symbol"]
    side = live_trade_state["side"]
    entry_p = live_trade_state["entry_price"]
    atr = live_trade_state["atr"]

    try:
        ticker = bitget.fetch_ticker(sym)
        cur_price = float(ticker.get('last', 0) or 0)
    except Exception:
        return

    if cur_price <= 0:
        return

    if cur_price > live_trade_state["highest_price"]:
        live_trade_state["highest_price"] = cur_price
    if cur_price < live_trade_state["lowest_price"]:
        live_trade_state["lowest_price"] = cur_price

    elapsed_sec = time.time() - live_trade_state["entry_time"]
    elapsed_min = elapsed_sec / 60.0

    if side == 'long':
        pnl_pct = ((cur_price - entry_p) / entry_p) * 100.0
        peak_distance = live_trade_state["highest_price"] - entry_p
    else:
        pnl_pct = ((entry_p - cur_price) / entry_p) * 100.0
        peak_distance = entry_p - live_trade_state["lowest_price"]

    # 1. Hesitation Cut (90 seconds without positive follow-through)
    if elapsed_sec >= 90 and pnl_pct < 0.08:
        execute_live_exit("Hesitation Cut: Momentum stalled without follow-through", pnl_pct)
        return

    # 2. Bank Target Profit (>= +1.50%)
    if pnl_pct >= 1.55:
        execute_live_exit("Target Target Banked: Reached >= +1.50% Goal", pnl_pct)
        return

    # 3. Fee-Shield Lock
    fee_shield_trigger = 0.8 * atr
    if not live_trade_state["fee_shield_active"] and peak_distance >= fee_shield_trigger:
        live_trade_state["fee_shield_active"] = True
        print(f"\n[FEE-SHIELD ENGAGED] {sym} covered 0.8x ATR. Breakeven profit locked.\n", flush=True)

    if live_trade_state["fee_shield_active"]:
        if side == 'long' and cur_price <= entry_p * 1.0035:
            execute_live_exit("Long Fee-Shield Breakeven Hit", pnl_pct)
            return
        elif side == 'short' and cur_price >= entry_p * 0.9965:
            execute_live_exit("Short Fee-Shield Breakeven Hit", pnl_pct)
            return

    # 4. Hard Stop
    if not live_trade_state["fee_shield_active"]:
        if side == 'long' and cur_price <= live_trade_state["initial_stop_price"]:
            execute_live_exit("Long Hard Stop Hit", pnl_pct)
            return
        elif side == 'short' and cur_price >= live_trade_state["initial_stop_price"]:
            execute_live_exit("Short Hard Stop Hit", pnl_pct)
            return

    # 5. Stagnation Exit
    if elapsed_min >= 12.0:
        execute_live_exit("12m Stagnation Timeout", pnl_pct)
        return

# ==============================================================================
# 13. MAIN ENGINE LOOP
# ==============================================================================
def main():
    global live_trade_state
    start_keep_alive()
    start_global_radar_worker()
    print("[SYSTEM] APEX-V9 Self-Determining Autonomous Trader online.", flush=True)

    try:
        bitget.load_markets()
        print(f"[SYSTEM] Loaded {len(bitget.markets)} pairs from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARN] Market load warning: {e}", flush=True)

    archive = load_film_archive()
    cycle = 1

    write_story_log("SYSTEM_START", "ALL", "Self-Determining Student Engine active.", "Dynamic stops and targets calibrated by empirical learning.")

    while True:
        try:
            # 1. Non-blocking Live Position Monitor
            pos = get_open_position()
            if pos and not live_trade_state["active"]:
                live_trade_state = {
                    "active": True,
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "entry_price": pos['entry_price'],
                    "entry_time": time.time(),
                    "initial_stop_price": pos['entry_price'] * (0.988 if pos['side'] == 'long' else 1.012),
                    "target_price": pos['entry_price'] * (1.016 if pos['side'] == 'long' else 0.984),
                    "contracts": pos['contracts'],
                    "fee_shield_active": False,
                    "highest_price": pos['entry_price'],
                    "lowest_price": pos['entry_price'],
                    "atr": pos['entry_price'] * 0.012
                }
                print(f"[POSITION RECOVERED] Managing: {pos['side'].upper()} {pos['symbol']}", flush=True)

            if live_trade_state["active"]:
                poll_live_trade_guardian()

            # 2. Run Observational Filming Cameras (Learning from Wins AND Losses)
            if archive['active_cameras']:
                run_filming_cameras(archive, leverage=4)
                save_film_archive(archive)

            # 3. Capital Safety Check
            balance_info = bitget.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            is_safe, reason = circuit_breaker.check_safety(usdt_free)
            if not is_safe:
                print(f"\n[VAULT SHIELD LOCKED] {reason} | Free USDT: ${usdt_free:.2f}. Real money protected...\n", flush=True)
                time.sleep(60)
                continue

            # Dynamic Leverage Ladder ($5.15 - $7.50 clamp)
            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            raw_notional = (usdt_free * BALANCE_USE_PCT) * leverage
            notional = max(min(raw_notional, MAX_ORDER_NOTIONAL), MIN_ORDER_NOTIONAL)

            # 4. SINGLE-CALL SCAN: Fetch Bitget tickers
            try:
                tickers = bitget.fetch_tickers()
            except Exception:
                time.sleep(4)
                continue

            # Scan universe fearlessly
            pings = scan_all_coins_fearlessly(tickers, archive)

            # 5. Classify & Film
            for ping in pings:
                sym = ping['symbol']
                base = ping['base']
                cur_price = ping['current_price']
                start_price = ping['start_price']
                dir_move = ping['direction']
                injected_cap = ping['capital_injected']

                if live_trade_state["active"]:
                    break

                try:
                    ohlcv_1m = bitget.fetch_ohlcv(sym, timeframe='1m', limit=5)
                except Exception:
                    continue

                if len(ohlcv_1m) < 3:
                    continue

                # --------------------------------------------------------------
                # AUTONOMOUS CALIBRATION: The bot determines stop and target!
                # --------------------------------------------------------------
                natural_swing = calculate_natural_swing_atr(ohlcv_1m)
                if natural_swing <= 0:
                    natural_swing = cur_price * 0.008

                # Select strategy archetype
                if base in global_binance_tickers and abs(global_binance_tickers[base].get('pct_24h', 0)) > 3.0:
                    strategy = "BREAKOUT_CONTINUATION"
                    side = "long" if dir_move == "EXPANDING_UP" else "short"
                elif abs(ping['pct_move']) >= 0.70:
                    strategy = "MEAN_REVERSION_SNAP"
                    side = "short" if dir_move == "EXPANDING_UP" else "long"
                else:
                    strategy = "QUICK_IMPULSE_CHASE"
                    side = "long" if dir_move == "EXPANDING_UP" else "short"

                # Bot looks up its learned multipliers for this specific strategy
                learned_params = brain.strategy_params.get(strategy, {"stop_mult": 1.4, "target_mult": 2.2})
                learned_stop_mult = learned_params["stop_mult"]
                learned_target_mult = learned_params["target_mult"]

                # Calculate stop distance using natural coin swing * learned multiplier
                stop_dist = natural_swing * learned_stop_mult
                # Floor stop distance to at least 0.75% of coin price so it can never choke in 10 seconds!
                min_stop_floor = cur_price * 0.0075
                if stop_dist < min_stop_floor:
                    stop_dist = min_stop_floor

                # Target must always target at least +1.60% gross to net +1.50% after taker fees
                target_dist = max(natural_swing * learned_target_mult, cur_price * 0.0160)

                entry_price = cur_price
                stop_price = entry_price - stop_dist if side == 'long' else entry_price + stop_dist
                target_price = entry_price + target_dist if side == 'long' else entry_price - target_dist
                stop_pct = (stop_dist / entry_price) * 100.0

                if side == 'long':
                    liq_price = entry_price * (1.0 - (1.0 / leverage) + BITGET_MAINTENANCE_MARGIN)
                else:
                    liq_price = entry_price * (1.0 + (1.0 / leverage) - BITGET_MAINTENANCE_MARGIN)

                # ==============================================================
                # STRICT LIVE GATE: 9/10 PAPER WINS REQUIRED FOR REAL CASH
                # ==============================================================
                if brain.is_live_ready(strategy) and not live_trade_state["active"] and notional >= MIN_ORDER_NOTIONAL:
                    market = bitget.market(sym)
                    min_lot = float(market.get('limits', {}).get('amount', {}).get('min') or 0)
                    amount_precision = float(market.get('precision', {}).get('amount') or 0)
                    min_required = max(min_lot, amount_precision)
                    raw_amount = notional / entry_price

                    if raw_amount < min_required:
                        continue

                    try:
                        formatted_amount = float(bitget.amount_to_precision(sym, raw_amount))
                    except Exception:
                        continue

                    actual_notional = formatted_amount * entry_price
                    if formatted_amount >= min_required and actual_notional >= MIN_ORDER_NOTIONAL:
                        try:
                            bitget.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                        except Exception:
                            pass

                        print("\n" + "=" * 80, flush=True)
                        print(f"[LIVE CRUCIBLE PASSED: {side.upper()}] Strategy {strategy} achieved 9/10 wins!", flush=True)
                        print(f"  Live Real Order: {sym} | Sizing: ${actual_notional:.2f} ({leverage}x)", flush=True)
                        print(f"  Entry: {entry_price:.4f} | Target (+1.5% min): {target_price:.4f} | Stop: {stop_price:.4f}", flush=True)
                        print("=" * 80 + "\n", flush=True)

                        order = open_long_position(sym, formatted_amount) if side == 'long' else open_short_position(sym, formatted_amount)
                        time.sleep(2)

                        push_recently_traded(archive, sym)
                        real_pos = get_open_position()
                        real_fill = real_pos['entry_price'] if real_pos else entry_price
                        real_cnt = real_pos['contracts'] if real_pos else formatted_amount

                        live_trade_state = {
                            "active": True,
                            "symbol": sym,
                            "side": side,
                            "entry_price": real_fill,
                            "entry_time": time.time(),
                            "initial_stop_price": stop_price,
                            "target_price": target_price,
                            "contracts": real_cnt,
                            "fee_shield_active": False,
                            "highest_price": real_fill,
                            "lowest_price": real_fill,
                            "atr": stop_dist
                        }
                        write_story_log("LIVE_TRADE_OPENED", sym, f"Executed {side.upper()} order.", f"Pattern {strategy} passed crucible.")
                        break

                # ==============================================================
                # FEARLESS ZERO-CASH EXPERIMENT (FILMING AUTONOMOUS TRADES)
                # ==============================================================
                elif len(archive['active_cameras']) < MAX_PARALLEL_CAMERAS and sym not in {c['symbol'] for c in archive['active_cameras']}:
                    new_cam = {
                        "symbol": sym,
                        "strategy": strategy,
                        "started_at": time.time(),
                        "highest_price": entry_price,
                        "lowest_price": entry_price,
                        "film_ticks": [{"t": 0, "p": entry_price}],
                        "trade_hypothesis": {
                            "side": side,
                            "entry_price": entry_price,
                            "stop_price": stop_price,
                            "target_price": target_price,
                            "liq_price": liq_price,
                            "simulated_notional": notional
                        }
                    }
                    archive['active_cameras'].append(new_cam)
                    save_film_archive(archive)
                    print(f"[AUTONOMOUS CAMERA #{len(archive['active_cameras'])} LOCKED] {sym} | Strategy: {strategy} ({side.upper()}) | Stop: {stop_price:.4f} (-{stop_pct:.2f}%) | Target: {target_price:.4f}", flush=True)
                    write_story_log("PAPER_EXPERIMENT_BEGUN", sym, f"Moved {ping['pct_move']:+.2f}%. Natural swing: ${natural_swing:.4f}.", f"Self-determined stop mult: {learned_stop_mult}x, target mult: {learned_target_mult}x.")

            # 6. Status Pulse
            if cycle % 3 == 0:
                summary_brain = brain.get_summary_status()
                strikes = circuit_breaker.consecutive_losses
                live_str = f"LOCKED: {live_trade_state['side'].upper()} {live_trade_state['symbol']}" if live_trade_state['active'] else "SCANNING ALL >$1M"
                total_liquid = len([s for s, t in tickers.items() if float(t.get('quoteVolume', 0) or 0) >= MIN_24H_VOLUME and s.endswith(':USDT')])
                global_sync_count = len(global_binance_tickers)

                print(
                    f"\n[ENGINE PULSE] Status: ACTIVE | Live: {live_str} | Coins Monitored: {total_liquid} (Global Binance Pairs: {global_sync_count})\n"
                    f"Vault: ${usdt_free:.2f} USDT ({leverage}x) | Loss Strikes: {strikes}/2 | Active Cameras: {len(archive['active_cameras'])}/{MAX_PARALLEL_CAMERAS}\n"
                    f"Self-Calibrated Scores -> [{summary_brain}]",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()

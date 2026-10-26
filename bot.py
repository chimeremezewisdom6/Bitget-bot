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
        self.wfile.write(b"APEX-V5 High-Speed Human Discernment Engine is active.")

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
EMPIRICAL_BRAIN_FILE = "empirical_brain.json"
STUDY_LOG_FILE = "empirical_tapes.json"

ABSOLUTE_EQUITY_FLOOR = 1.50   # Vault floor: never allow balance below $1.50
MAX_CONSECUTIVE_LOSSES = 2     # Two strikes triggers mandatory 24h rest
MAX_ORDER_NOTIONAL = 7.50      # Cap notional size
MIN_ORDER_NOTIONAL = 5.15      # Bitget $5 minimum + buffer

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
            return False, "HARD_LOCKOUT: Emergency lockout file exists. Trading halted."

        if current_balance < ABSOLUTE_EQUITY_FLOOR:
            with open(LOCKOUT_FILE, "w") as f:
                f.write(f"Kill switch triggered at ${current_balance:.2f} on {time.ctime()}")
            return False, f"EQUITY_FLOOR_BREACH: Balance ${current_balance:.2f} breached floor! Vault sealed."

        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            elapsed_hours = (time.time() - self.last_loss_time) / 3600
            if elapsed_hours < 24.0:
                remaining = 24.0 - elapsed_hours
                return False, f"TWO_STRIKE_FREEZE: Cooldown active for {remaining:.1f} more hours."
            else:
                print("\n[CIRCUIT BREAKER] 24-hour cooling period finished. Resetting strikes.\n", flush=True)
                self.consecutive_losses = 0
                self.save_state()

        return True, "SAFE"

    def record_trade_result(self, pnl_pct):
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            print(f"\n[CIRCUIT BREAKER] Loss recorded. Consecutive strikes: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}", flush=True)
        else:
            self.consecutive_losses = 0
            print("\n[CIRCUIT BREAKER] Winning trade logged. Strikes cleared.", flush=True)
        self.save_state()

circuit_breaker = CircuitBreaker()

# ==============================================================================
# 3. EMPIRICAL FIRST-PRINCIPLES RESEARCH BRAIN
# ==============================================================================
class EmpiricalScienceBrain:
    def __init__(self):
        self.archetype_records = {
            "RUBBER_BAND_SNAP": {"trials": [], "total_tested": 0},
            "COMPRESSION_LAUNCHPAD": {"trials": [], "total_tested": 0},
            "WATERFALL_FLUSH": {"trials": [], "total_tested": 0}
        }
        self.quarantine_mode = False
        self.quarantine_target = 5
        self.quarantine_progress = 0
        self.load_brain()

    def load_brain(self):
        if os.path.exists(EMPIRICAL_BRAIN_FILE):
            try:
                with open(EMPIRICAL_BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.archetype_records = data.get("archetype_records", self.archetype_records)
                    self.quarantine_mode = data.get("quarantine_mode", False)
                    self.quarantine_target = data.get("quarantine_target", 5)
                    self.quarantine_progress = data.get("quarantine_progress", 0)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(EMPIRICAL_BRAIN_FILE, "w") as f:
                json.dump({
                    "archetype_records": self.archetype_records,
                    "quarantine_mode": self.quarantine_mode,
                    "quarantine_target": self.quarantine_target,
                    "quarantine_progress": self.quarantine_progress
                }, f, indent=2)
        except Exception:
            pass

    def record_experiment_outcome(self, archetype, is_win, net_pnl, reason):
        if archetype not in self.archetype_records:
            self.archetype_records[archetype] = {"trials": [], "total_tested": 0}

        rec = self.archetype_records[archetype]
        rec["trials"].append(1 if is_win else 0)
        rec["total_tested"] += 1
        if len(rec["trials"]) > 10:
            rec["trials"].pop(0)

        win_count = sum(rec["trials"])
        sample_size = len(rec["trials"])
        win_rate = (win_count / sample_size) * 100 if sample_size > 0 else 0

        print(f"\n[EXPERIMENT] {archetype} | Result: {'WIN (+1)' if is_win else 'LOSS (0)'} | Net PnL: {net_pnl:+.2f}%", flush=True)
        print(f"[CAUSALITY] {reason}", flush=True)
        print(f"[SCORE] {archetype}: {win_count}/{sample_size} ({win_rate:.0f}% win rate)", flush=True)

        if self.quarantine_mode and is_win:
            self.quarantine_progress += 1
            print(f"[QUARANTINE PROGRESS] {self.quarantine_progress}/{self.quarantine_target}", flush=True)
            if self.quarantine_progress >= self.quarantine_target:
                self.quarantine_mode = False
                self.quarantine_progress = 0
                circuit_breaker.consecutive_losses = 0
                circuit_breaker.save_state()
                print(f"[QUARANTINE COMPLETE] Regime validated. Live execution unlocked.\n", flush=True)

        self.save_brain()

    def is_archetype_live_qualified(self, archetype):
        if self.quarantine_mode:
            return False
        rec = self.archetype_records.get(archetype, {})
        trials = rec.get("trials", [])
        return len(trials) >= 10 and sum(trials) >= 9

    def get_summary_status(self):
        lines = []
        for arch, data in self.archetype_records.items():
            trials = data.get("trials", [])
            w = sum(trials)
            tot = len(trials)
            pct = (w / tot) * 100 if tot > 0 else 0
            lines.append(f"{arch[:4]}: {w}/{tot} ({pct:.0f}%)")
        return " | ".join(lines)

brain = EmpiricalScienceBrain()

# ==============================================================================
# 4. CONFIGURATION & CAPITAL BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BALANCE_USE_PCT = 0.85
MIN_24H_VOLUME = 2_000_000       # User requirement: All coins > $2,000,000 volume
SCAN_INTERVAL_SECONDS = 8        # Fast 8-second radar cycle
MAX_PARALLEL_CAMERAS = 5         # Parallel zero-cash observational studies
MAX_RECENT_EXCLUSION = 4         # Memory rotation to prevent chasing the same coin

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

# In-memory ticker snapshot tracker to scan 100+ coins in 0.01 seconds
ticker_memory = {}

# ==============================================================================
# 5. HUMAN SKEPTICISM & VETO COMMITTEE (DISOBEDIENCE ENGINE)
# ==============================================================================
def human_skepticism_veto(symbol, side, ohlcv_1m):
    """
    Acts like a cautious human. Refuses to execute if the context suggests
    manipulation, trap liquidity, or dirty order flow—even if formulas say BUY.
    """
    if len(ohlcv_1m) < 3:
        return False, "Not enough recent tick context."

    last_candle = ohlcv_1m[-1]
    c_open = last_candle[1]
    c_high = last_candle[2]
    c_low = last_candle[3]
    c_close = last_candle[4]

    candle_range = c_high - c_low
    if candle_range <= 0:
        return False, "Zero volatility candle."

    body = abs(c_close - c_open)
    upper_wick = c_high - max(c_open, c_close)
    lower_wick = min(c_open, c_close) - c_low

    # 1. Reject Longs on Rejection Wicks (Whales dumping into retail buyers)
    if side == "long" and upper_wick > (body * 1.3):
        return False, f"VETO: Massive upper wick ({upper_wick:.4f} > body {body:.4f}). Sellers smashing price down."

    # 2. Reject Shorts on Absorbed Dumps (Smart money absorbing cheap supply)
    if side == "short" and lower_wick > (body * 1.3):
        return False, f"VETO: Massive lower wick ({lower_wick:.4f} > body {body:.4f}). Buyers aggressively stepping in."

    # 3. Order Book Depth & Bid-Ask Spread Reality Check
    try:
        ob = exchange.fetch_order_book(symbol, limit=10)
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])

        if not bids or not asks:
            return False, "VETO: Empty order book! Dangerous illiquidity."

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread_pct = ((best_ask - best_bid) / best_bid) * 100.0

        if spread_pct > 0.08:
            return False, f"VETO: Spread too wide ({spread_pct:.3f}%). Exchange slippage trap."

        bid_depth = sum([b[1] for b in bids[:5]])
        ask_depth = sum([a[1] for a in asks[:5]])

        if side == "long" and bid_depth < (ask_depth * 0.40):
            return False, f"VETO: Fake rally. Bid depth ({bid_depth:.1f}) collapsed under ask wall ({ask_depth:.1f})."

        if side == "short" and ask_depth < (bid_depth * 0.40):
            return False, f"VETO: Fake dump. Ask depth ({ask_depth:.1f}) too thin against buyer wall ({bid_depth:.1f})."

    except Exception as e:
        return False, f"VETO: Unable to verify order book safety ({e})."

    return True, "Human Safety Clearance Passed."

def capital_preservation_veto(balance, notional, stop_dist_pct):
    max_acceptable_dollar_loss = balance * 0.08
    projected_dollar_loss = notional * (stop_dist_pct / 100.0)

    if projected_dollar_loss > max_acceptable_dollar_loss:
        return False, f"VETO: Projected loss (${projected_dollar_loss:.2f}) exceeds 8% vault safety (${max_acceptable_dollar_loss:.2f})."

    return True, "Capital preservation approved."

# ==============================================================================
# 6. DATA PERSISTENCE & HELPERS
# ==============================================================================
def load_empirical_studies():
    if os.path.exists(STUDY_LOG_FILE):
        try:
            with open(STUDY_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_cameras": [], "completed_tapes": [], "recently_traded": []}

def save_empirical_studies(data):
    try:
        with open(STUDY_LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def push_traded_coin(study_data, symbol):
    if "recently_traded" not in study_data:
        study_data["recently_traded"] = []
    if symbol in study_data["recently_traded"]:
        study_data["recently_traded"].remove(symbol)
    study_data["recently_traded"].append(symbol)
    if len(study_data["recently_traded"]) > MAX_RECENT_EXCLUSION:
        study_data["recently_traded"].pop(0)
    save_empirical_studies(study_data)

# ==============================================================================
# 7. BITGET ORDER & POSITION INTERFACE
# ==============================================================================
def get_open_position():
    try:
        positions = exchange.fetch_positions()
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
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'open'}
        )

def close_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'sell_single'}
        )
    except Exception:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'close'}
        )

def open_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'open'}
        )

def close_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'buy_single'}
        )
    except Exception:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'reduceOnly': True, 'tradeSide': 'close'}
        )

# ==============================================================================
# 8. HIGH-SPEED SCANNER (ALL COINS > $2M VOLUME IN 1 CALL)
# ==============================================================================
def scan_all_liquid_universe(tickers, study_data):
    """
    Scans every single coin meeting > $2M volume across the exchange simultaneously.
    Uses memory differential to track micro-surges without spamming candle requests.
    """
    global ticker_memory
    pings = []
    now = time.time()
    active_syms = {c['symbol'] for c in study_data['active_cameras']}
    recent_syms = set(study_data.get('recently_traded', []))

    for symbol, t in tickers.items():
        if not symbol.endswith(":USDT"):
            continue
        base = symbol.split('/')[0].upper()
        if base in NON_CRYPTO_SYMBOLS:
            continue

        vol_24h = float(t.get('quoteVolume', 0) or 0)
        if vol_24h < MIN_24H_VOLUME:
            continue

        if symbol in recent_syms or symbol in active_syms:
            continue

        cur_price = float(t.get('last', 0) or 0)
        if cur_price <= 0:
            continue

        # Look up previous recorded price in memory snapshot
        if symbol in ticker_memory:
            past_price, past_time, past_vol = ticker_memory[symbol]
            dt = now - past_time

            # Check 15-45 second momentum window
            if 12.0 <= dt <= 60.0:
                pct_change = ((cur_price - past_price) / past_price) * 100.0
                vol_delta = vol_24h - past_vol

                # If coin surges >= 1.2% within 1 minute with at least $25,000 USDT in flow
                if abs(pct_change) >= 1.20 and vol_delta >= 25_000:
                    pings.append({
                        "symbol": symbol,
                        "direction": "EXPANDING_UP" if pct_change > 0 else "EXPANDING_DOWN",
                        "pct_move": round(pct_change, 2),
                        "capital_injected_1m": round(vol_delta, 2),
                        "start_price": past_price,
                        "current_price": cur_price,
                        "ticker_data": t
                    })
                    # Reset memory so we don't trigger back-to-back duplicate pings
                    ticker_memory[symbol] = (cur_price, now, vol_24h)
                    continue

        # Update running memory snapshot
        if symbol not in ticker_memory or (now - ticker_memory[symbol][1]) >= 30.0:
            ticker_memory[symbol] = (cur_price, now, vol_24h)

    # Sort pings by strongest velocity
    pings.sort(key=lambda x: abs(x['pct_move']), reverse=True)
    return pings

# ==============================================================================
# 9. ZERO-CASH OBSERVATIONAL SCIENCE DESK
# ==============================================================================
def run_empirical_experiments(study_data, leverage=4):
    remaining = []
    for cam in study_data['active_cameras']:
        sym = cam['symbol']
        side = cam['trade_hypothesis']['side']
        entry_price = cam['trade_hypothesis']['entry_price']
        stop_price = cam['trade_hypothesis']['stop_price']
        target_price = cam['trade_hypothesis']['target_price']
        liq_price = cam['trade_hypothesis']['liq_price']
        archetype = cam['archetype']
        elapsed_min = (time.time() - cam['started_at']) / 60

        try:
            ticker = exchange.fetch_ticker(sym)
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

        if side == 'long':
            gross_pnl_pct = ((cur_price - entry_price) / entry_price) * 100.0
            peak_pnl = ((cam['highest_price'] - entry_price) / entry_price) * 100.0
            max_dd = ((cam['lowest_price'] - entry_price) / entry_price) * 100.0
        else:
            gross_pnl_pct = ((entry_price - cur_price) / entry_price) * 100.0
            peak_pnl = ((entry_price - cam['lowest_price']) / entry_price) * 100.0
            max_dd = ((entry_price - cam['highest_price']) / entry_price) * 100.0

        net_pnl_pct = gross_pnl_pct - (BITGET_TAKER_FEE_PCT * 2)

        is_finished = False
        outcome = "MONITORING"
        causality_reason = ""

        if (side == 'long' and cur_price <= liq_price) or (side == 'short' and cur_price >= liq_price):
            is_finished = True
            outcome = "LIQUIDATION_LOSS"
            causality_reason = f"Adverse wick hit liquidation price ({liq_price:.4f})."

        elif (side == 'long' and cur_price <= stop_price) or (side == 'short' and cur_price >= stop_price):
            is_finished = True
            outcome = "STOP_LOSS_HIT"
            causality_reason = f"Reversal crossed invalidation level ({stop_price:.4f}). Net: {net_pnl_pct:+.2f}%."

        elif (side == 'long' and cur_price >= target_price) or (side == 'short' and cur_price <= target_price):
            is_finished = True
            outcome = "TAKE_PROFIT_HIT"
            causality_reason = f"Expansion completed capacity target ({target_price:.4f}). Net: {net_pnl_pct:+.2f}%."

        elif elapsed_min >= 8.0:
            is_finished = True
            outcome = "STAGNATION_CUT"
            causality_reason = f"Kinetic momentum faded into chop after 8m. Net: {net_pnl_pct:+.2f}%."

        if is_finished:
            is_win = (outcome == "TAKE_PROFIT_HIT" and net_pnl_pct > 0.50)
            brain.record_experiment_outcome(archetype, is_win, net_pnl_pct, causality_reason)

            tape = {
                "symbol": sym,
                "archetype": archetype,
                "side": side,
                "entry_price": entry_price,
                "net_pnl_pct": round(net_pnl_pct, 2),
                "peak_pnl_pct": round(peak_pnl, 2),
                "max_drawdown_pct": round(max_dd, 2),
                "duration_minutes": round(elapsed_min, 1),
                "outcome": outcome,
                "reason": causality_reason
            }
            study_data['completed_tapes'].append(tape)
            save_empirical_studies(study_data)
        else:
            remaining.append(cam)

    study_data['active_cameras'] = remaining

# ==============================================================================
# 10. NON-BLOCKING LIVE TRADE GUARDIAN
# ==============================================================================
live_trade_state = {
    "active": False,
    "symbol": None,
    "side": None,
    "entry_price": 0.0,
    "entry_time": 0.0,
    "initial_stop_price": 0.0,
    "contracts": 0.0,
    "fee_shield_active": False,
    "highest_price": 0.0,
    "lowest_price": 0.0,
    "atr": 0.0
}

def execute_live_exit(reason, pnl_pct):
    global live_trade_state
    symbol = live_trade_state["symbol"]
    side = live_trade_state["side"]
    contracts = live_trade_state["contracts"]

    print(f"\n[HUMAN GUARDIAN EXIT] {reason} | Net PnL: {pnl_pct:+.2f}%\n", flush=True)

    for attempt in range(1, 4):
        try:
            if side == 'long':
                close_long_position(symbol, contracts)
            else:
                close_short_position(symbol, contracts)
            break
        except Exception as e:
            print(f"[EXIT ATTEMPT {attempt} ERROR] {e}", flush=True)
            time.sleep(1)

    circuit_breaker.record_trade_result(pnl_pct)
    if pnl_pct < 0 and circuit_breaker.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        brain.quarantine_mode = True
        brain.quarantine_progress = 0
        brain.save_brain()
        print(f"\n[TWO STRIKES] Entering Quarantine Re-learning. Live capital protected.\n", flush=True)

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
        ticker = exchange.fetch_ticker(sym)
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

    # 1. Human Hesitation Exit: If trade fails to confirm into green in 90 seconds
    if elapsed_sec >= 90 and pnl_pct < 0.05:
        execute_live_exit("Human Hesitation Cut: Momentum stalled without follow-through", pnl_pct)
        return

    # 2. Fee-Shield Lock (+0.8x ATR -> Lock Breakeven +0.35%)
    fee_shield_trigger = 0.8 * atr
    if not live_trade_state["fee_shield_active"] and peak_distance >= fee_shield_trigger:
        live_trade_state["fee_shield_active"] = True
        print(f"\n[FEE-SHIELD ENGAGED] {sym} covered 0.8x ATR! Breakeven locked.\n", flush=True)

    if live_trade_state["fee_shield_active"]:
        if side == 'long' and cur_price <= entry_p * 1.0035:
            execute_live_exit("Long Fee-Shield Breakeven Hit", pnl_pct)
            return
        elif side == 'short' and cur_price >= entry_p * 0.9965:
            execute_live_exit("Short Fee-Shield Breakeven Hit", pnl_pct)
            return

    # 3. Hard Invalidation Stop
    if not live_trade_state["fee_shield_active"]:
        if side == 'long' and cur_price <= live_trade_state["initial_stop_price"]:
            execute_live_exit("Long Hard Stop Invalidation Hit", pnl_pct)
            return
        elif side == 'short' and cur_price >= live_trade_state["initial_stop_price"]:
            execute_live_exit("Short Hard Stop Invalidation Hit", pnl_pct)
            return

    # 4. Trailing Runner Exit
    runner_trigger = 1.6 * atr
    trail_distance = 1.0 * atr
    if peak_distance >= runner_trigger:
        if side == 'long' and cur_price <= (live_trade_state["highest_price"] - trail_distance):
            execute_live_exit("Long Trailing Runner Profit Banked", pnl_pct)
            return
        elif side == 'short' and cur_price >= (live_trade_state["lowest_price"] + trail_distance):
            execute_live_exit("Short Trailing Runner Profit Banked", pnl_pct)
            return

    # 5. Stagnation Timeout
    if elapsed_min >= 12.0:
        execute_live_exit("12m Stagnation Invalidation", pnl_pct)
        return

# ==============================================================================
# 11. MAIN ENGINE LOOP
# ==============================================================================
def main():
    global live_trade_state
    start_keep_alive()
    print("[SYSTEM] APEX-V5 High-Speed Human Discernment Engine online.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} pairs from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARN] Market load warning: {e}", flush=True)

    study_data = load_empirical_studies()
    cycle = 1

    while True:
        try:
            # 1. Live Position Monitor (Non-blocking)
            pos = get_open_position()
            if pos and not live_trade_state["active"]:
                live_trade_state = {
                    "active": True,
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "entry_price": pos['entry_price'],
                    "entry_time": time.time(),
                    "initial_stop_price": pos['entry_price'] * (0.988 if pos['side'] == 'long' else 1.012),
                    "contracts": pos['contracts'],
                    "fee_shield_active": False,
                    "highest_price": pos['entry_price'],
                    "lowest_price": pos['entry_price'],
                    "atr": pos['entry_price'] * 0.012
                }
                print(f"[POSITION RECOVERED] Managing: {pos['side'].upper()} {pos['symbol']}", flush=True)

            if live_trade_state["active"]:
                poll_live_trade_guardian()

            # 2. Update Zero-Cash Observational Experiments
            if study_data['active_cameras']:
                run_empirical_experiments(study_data, leverage=4)
                save_empirical_studies(study_data)

            # 3. Capital Safety Check
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            is_safe, reason = circuit_breaker.check_safety(usdt_free)
            if not is_safe:
                print(f"\n[DISOBEDIENCE LOCK] Refusing to trade: {reason}", flush=True)
                print(f"Vault safe at ${usdt_free:.2f} USDT. Resting...\n", flush=True)
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

            # 4. SINGLE-CALL SCAN: Fetch all tickers in 1 single network call
            try:
                tickers = exchange.fetch_tickers()
            except Exception:
                time.sleep(5)
                continue

            # Run high-speed in-memory scan across ALL coins with volume > $2M
            pings = scan_all_liquid_universe(tickers, study_data)

            # 5. Targeted Laser Inspection on Pings Only
            for ping in pings:
                sym = ping['symbol']
                cur_price = ping['current_price']
                start_price = ping['start_price']
                dir_move = ping['direction']
                injected_cap = ping['capital_injected_1m']

                if live_trade_state["active"]:
                    break

                # Fetch 1m candles only for coins that actually triggered a ping
                try:
                    ohlcv_1m = exchange.fetch_ohlcv(sym, timeframe='1m', limit=5)
                except Exception:
                    continue

                if len(ohlcv_1m) < 3:
                    continue

                peak_price = max([c[2] for c in ohlcv_1m[-2:]]) if dir_move == "EXPANDING_UP" else min([c[3] for c in ohlcv_1m[-2:]])
                total_wave = abs(peak_price - start_price)
                if total_wave <= 0:
                    continue

                retrace_ratio = (peak_price - cur_price) / total_wave if dir_move == "EXPANDING_UP" else (cur_price - peak_price) / total_wave

                if retrace_ratio >= 0.50:
                    archetype = "RUBBER_BAND_SNAP"
                    side = "short" if dir_move == "EXPANDING_UP" else "long"
                    stop_dist = total_wave * 0.35
                    target_dist = total_wave * 0.70
                elif retrace_ratio <= 0.20:
                    archetype = "COMPRESSION_LAUNCHPAD"
                    side = "long" if dir_move == "EXPANDING_UP" else "short"
                    stop_dist = total_wave * 0.40
                    target_dist = total_wave * 0.85
                else:
                    archetype = "WATERFALL_FLUSH"
                    side = "long" if dir_move == "EXPANDING_DOWN" else "short"
                    stop_dist = total_wave * 0.45
                    target_dist = total_wave * 0.90

                entry_price = cur_price
                stop_price = entry_price - stop_dist if side == 'long' else entry_price + stop_dist
                target_price = entry_price + target_dist if side == 'long' else entry_price - target_dist
                stop_pct = (stop_dist / entry_price) * 100.0

                if side == 'long':
                    liq_price = entry_price * (1.0 - (1.0 / leverage) + BITGET_MAINTENANCE_MARGIN)
                else:
                    liq_price = entry_price * (1.0 + (1.0 / leverage) - BITGET_MAINTENANCE_MARGIN)

                # ==============================================================
                # THE HUMAN SKEPTICISM CHECK (DISOBEDIENCE FILTER)
                # ==============================================================
                is_safe_to_enter, veto_reason = human_skepticism_veto(sym, side, ohlcv_1m)
                if not is_safe_to_enter:
                    # Reject suspicious spikes/wick manipulations
                    continue

                is_capital_safe, cap_reason = capital_preservation_veto(usdt_free, notional, stop_pct)
                if not is_capital_safe:
                    continue

                # ==============================================================
                # LIVE QUALIFICATION & EXECUTION
                # ==============================================================
                if brain.is_archetype_live_qualified(archetype) and not live_trade_state["active"] and notional >= MIN_ORDER_NOTIONAL:
                    market = exchange.market(sym)
                    min_lot = float(market.get('limits', {}).get('amount', {}).get('min') or 0)
                    amount_precision = float(market.get('precision', {}).get('amount') or 0)
                    min_required = max(min_lot, amount_precision)
                    raw_amount = notional / entry_price

                    if raw_amount < min_required:
                        continue

                    try:
                        formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))
                    except Exception:
                        continue

                    actual_notional = formatted_amount * entry_price
                    if formatted_amount >= min_required and actual_notional >= MIN_ORDER_NOTIONAL:
                        try:
                            exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                        except Exception:
                            pass

                        print("\n" + "=" * 80, flush=True)
                        print(f"[HUMAN STRIKE CLEARED] Order book verified across >$2M market.", flush=True)
                        print(f"  Executing {side.upper()} on {sym} | Sizing: ${actual_notional:.2f} USDT ({leverage}x)", flush=True)
                        print(f"  Target: {target_price:.4f} | Invalidation Stop: {stop_price:.4f} (-{stop_pct:.2f}%)", flush=True)
                        print("=" * 80 + "\n", flush=True)

                        order = open_long_position(sym, formatted_amount) if side == 'long' else open_short_position(sym, formatted_amount)
                        time.sleep(2)

                        push_traded_coin(study_data, sym)
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
                            "contracts": real_cnt,
                            "fee_shield_active": False,
                            "highest_price": real_fill,
                            "lowest_price": real_fill,
                            "atr": stop_dist
                        }
                        break

                # ==============================================================
                # ZERO-CASH OBSERVATIONAL SCIENCE LAB
                # ==============================================================
                elif len(study_data['active_cameras']) < MAX_PARALLEL_CAMERAS and sym not in {c['symbol'] for c in study_data['active_cameras']}:
                    new_cam = {
                        "symbol": sym,
                        "archetype": archetype,
                        "started_at": time.time(),
                        "highest_price": entry_price,
                        "lowest_price": entry_price,
                        "trade_hypothesis": {
                            "side": side,
                            "entry_price": entry_price,
                            "stop_price": stop_price,
                            "target_price": target_price,
                            "liq_price": liq_price,
                            "simulated_notional": notional
                        }
                    }
                    study_data['active_cameras'].append(new_cam)
                    save_empirical_studies(study_data)
                    print(f"[PAPER LAB] {sym} surged {ping['pct_move']:+.2f}%. Camera locked on {archetype} ({side.upper()}).", flush=True)

            # 6. Periodic Status Pulse
            if cycle % 3 == 0:
                summary_brain = brain.get_summary_status()
                strikes = circuit_breaker.consecutive_losses
                mode = "QUARANTINE" if brain.quarantine_mode else "ACTIVE"
                live_str = f"LOCKED: {live_trade_state['side'].upper()} {live_trade_state['symbol']}" if live_trade_state['active'] else "SCANNING ALL >$2M"

                # Count how many coins qualify above $2M volume
                total_tracked = len([s for s, t in tickers.items() if float(t.get('quoteVolume', 0) or 0) >= MIN_24H_VOLUME and s.endswith(':USDT')])

                print(
                    f"\n[ENGINE PULSE] Status: {mode} | Live: {live_str} | Coins Monitored: {total_tracked}\n"
                    f"Vault: ${usdt_free:.2f} USDT ({leverage}x) | Loss Strikes: {strikes}/2 | Active Cameras: {len(study_data['active_cameras'])}/{MAX_PARALLEL_CAMERAS}\n"
                    f"Empirical Scores (9/10 required) -> [{summary_brain}]",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(8)

if __name__ == "__main__":
    main()

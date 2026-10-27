import os
import sys
import time
import math
import json
import traceback
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER 24/7 KEEP-ALIVE & LIVE TAPE VIEWER (PORT 10000)
# ==============================================================================
STUDY_LOG_FILE = "empirical_tapes.json"
STORYBOOK_FILE = "market_storybook.jsonl"
RECIPE_BOOK_FILE = "autonomous_recipes.json"
CB_FILE = "circuit_breaker.json"
LOCKOUT_FILE = "EMERGENCY_LOCKOUT.txt"

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        if self.path == "/tapes":
            if os.path.exists(STUDY_LOG_FILE):
                with open(STUDY_LOG_FILE, "r") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(b'{"completed_films": []}')
        elif self.path == "/recipes":
            if os.path.exists(RECIPE_BOOK_FILE):
                with open(RECIPE_BOOK_FILE, "r") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(b'{"recipes": {}}')
        else:
            status = {
                "engine": "APEX-V16 Growing-Depth & Anti-Spoofing Order Flow Engine",
                "vault_protected": True,
                "recipes_active": len(brain.recipes),
                "summary": brain.get_summary_status()
            }
            self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

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
ABSOLUTE_EQUITY_FLOOR = 1.50   # Vault hard floor ($1.50)
MAX_CONSECUTIVE_LOSSES = 2     # Two live losses = mandatory rest
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
            return False, "HARD_LOCKOUT: Emergency lockout active. Real money secured."

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
                self.consecutive_losses = 0
                self.save_state()

        return True, "SAFE"

    def record_trade_result(self, pnl_pct):
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            print(f"\n[CIRCUIT BREAKER] Live loss logged. Strikes: {self.consecutive_losses}/{MAX_CONSECUTIVE_LOSSES}", flush=True)
        else:
            self.consecutive_losses = 0
            print("\n[CIRCUIT BREAKER] Winning trade logged. Strikes cleared to 0.", flush=True)
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
    print(f"[JOURNAL] {event_type} on {symbol}: {observation} | Lesson: {lesson}", flush=True)

# ==============================================================================
# 4. AUTONOMOUS HYPOTHESIS & DEPTH TREND BRAIN
# ==============================================================================
class AutonomousChefBrain:
    def __init__(self):
        self.recipes = {
            "GROWING_BID_PRESSURE_LONG": {
                "max_duration_min": 3.0,
                "stop_mult": 1.4,
                "target_mult": 1.8,
                "invert_bias": False,
                "trials": []
            },
            "GROWING_ASK_DUMP_SHORT": {
                "max_duration_min": 3.0,
                "stop_mult": 1.4,
                "target_mult": 1.8,
                "invert_bias": False,
                "trials": []
            },
            "BREAKOUT_CONTINUATION": {
                "max_duration_min": 3.0,
                "stop_mult": 1.5,
                "target_mult": 1.7,
                "invert_bias": True,
                "trials": []
            },
            "MEAN_REVERSION_SNAP": {
                "max_duration_min": 3.5,
                "stop_mult": 1.6,
                "target_mult": 1.8,
                "invert_bias": False,
                "trials": []
            },
            "QUICK_IMPULSE_CHASE": {
                "max_duration_min": 2.8,
                "stop_mult": 1.5,
                "target_mult": 1.6,
                "invert_bias": False,
                "trials": []
            }
        }
        self.quarantine_mode = False
        self.coin_penalties = {}
        self.recent_coin_history = []
        self.load_recipes()

    def load_recipes(self):
        if os.path.exists(RECIPE_BOOK_FILE):
            try:
                with open(RECIPE_BOOK_FILE, "r") as f:
                    data = json.load(f)
                    self.recipes = data.get("recipes", self.recipes)
                    self.quarantine_mode = data.get("quarantine_mode", False)
            except Exception:
                pass

    def save_recipes(self):
        try:
            with open(RECIPE_BOOK_FILE, "w") as f:
                json.dump({
                    "recipes": self.recipes,
                    "quarantine_mode": self.quarantine_mode
                }, f, indent=2)
        except Exception:
            pass

    def evaluate_and_invent_recipe(self, strat_name, completed_tape, recent_tapes):
        r = self.recipes.get(strat_name)
        if not r:
            return

        dur = completed_tape['duration_minutes']
        pnl = completed_tape['net_pnl_pct']
        peak = completed_tape['peak_pnl_pct']
        outcome = completed_tape['outcome']
        sym = completed_tape['symbol']

        # 1. Stagnation prevention: shorten hold time if it decays
        if outcome == "STAGNATION_TIMEOUT":
            old_timer = r['max_duration_min']
            r['max_duration_min'] = max(round(r['max_duration_min'] - 0.4, 1), 1.8)
            print(f"\n[CHEF REFLECTION] {strat_name} stagnated. Shortened hold: {old_timer}m -> {r['max_duration_min']}m.\n", flush=True)

        # 2. Inversion check
        recent_trials = r['trials'][-6:] if len(r['trials']) >= 6 else []
        if len(recent_trials) >= 6 and sum(recent_trials) <= 1:
            r['invert_bias'] = not r['invert_bias']
            r['trials'] = []
            print(f"\n[CHEF REFLECTION] {strat_name} failed repeatedly. Inverted bias: {r['invert_bias']}\n", flush=True)

        # 3. Greed prevention
        if peak >= 1.20 and pnl < 0.60:
            r['target_mult'] = max(round(r['target_mult'] - 0.08, 2), 1.4)

        # 4. Anti-revenge overtrading quarantine
        self.recent_coin_history.append((sym, time.time(), pnl))
        if len(self.recent_coin_history) > 30:
            self.recent_coin_history.pop(0)

        same_coin = [e for e in self.recent_coin_history if e[0] == sym and (time.time() - e[1]) <= 600]
        if len(same_coin) >= 2 and sum([e[2] for e in same_coin]) < 0:
            self.coin_penalties[sym] = time.time() + 240
            print(f"\n[CHEF ROTATION] Put {sym} on 4-minute timeout.\n", flush=True)

        self.save_recipes()

    def record_film_outcome(self, strategy, net_pnl, reason, film_tape, all_tapes):
        if strategy not in self.recipes:
            self.recipes[strategy] = {
                "max_duration_min": 3.0, "stop_mult": 1.5, "target_mult": 1.7,
                "invert_bias": False, "trials": []
            }

        r = self.recipes[strategy]
        is_win = 1 if (net_pnl >= 1.50) else 0
        r["trials"].append(is_win)
        if len(r["trials"]) > 10:
            r["trials"].pop(0)

        self.evaluate_and_invent_recipe(strategy, film_tape, all_tapes)

        win_count = sum(r["trials"])
        sample_size = len(r["trials"])
        win_rate = (win_count / sample_size) * 100 if sample_size > 0 else 0

        verdict = "QUALIFIED WIN (>=+1.5%)" if is_win else "FAILED TARGET (<+1.5%)"
        print(f"\n[RECIPE TESTED] {strategy} on {film_tape['symbol']} | Net: {net_pnl:+.2f}% | Verdict: {verdict}", flush=True)
        print(f"[SCORECARD] {strategy}: {win_count}/{sample_size} passed (+1.5% target) -> {win_rate:.0f}% win rate\n", flush=True)

        write_story_log(
            event_type="PAPER_EXPERIMENT_FINISHED",
            symbol=film_tape['symbol'],
            observation=f"Finished in {film_tape['duration_minutes']}m with PnL of {net_pnl:+.2f}%.",
            lesson=reason
        )
        self.save_recipes()

    def is_coin_in_penalty(self, symbol):
        return time.time() < self.coin_penalties.get(symbol, 0)

    def is_live_ready(self, strategy):
        if self.quarantine_mode:
            return False
        r = self.recipes.get(strategy, {})
        trials = r.get("trials", [])
        return len(trials) >= 10 and sum(trials) >= 9

    def get_summary_status(self):
        lines = []
        for strat, r in self.recipes.items():
            trials = r.get("trials", [])
            w = sum(trials)
            tot = len(trials)
            pct = (w / tot) * 100 if tot > 0 else 0
            inv = " [INV]" if r.get('invert_bias') else ""
            lines.append(f"{strat[:4]}: {w}/{tot} ({pct:.0f}%){inv} [Hold:{r['max_duration_min']}m]")
        return " | ".join(lines)

brain = AutonomousChefBrain()

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
SCAN_INTERVAL_SECONDS = 5
MAX_PARALLEL_CAMERAS = 12

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

bybit_radar = ccxt.bybit({"enableRateLimit": True, "timeout": 10000, "options": {"defaultType": "linear"}})
gate_radar = ccxt.gate({"enableRateLimit": True, "timeout": 10000, "options": {"defaultType": "swap"}})
okx_radar = ccxt.okx({"enableRateLimit": True, "timeout": 10000, "options": {"defaultType": "swap"}})

ticker_memory = {}
global_composite_tickers = {}
radar_counts = {"Binance": 0, "Bybit": 0, "OKX": 0, "Gate": 0}

# Order flow depth memory to track whether bids/asks are INCREASING over time
# Format: { symbol: [ (timestamp, bid_usdt, ask_usdt, mid_price), ... ] }
depth_history = {}

# ==============================================================================
# 6. GLOBAL MULTI-EXCHANGE RADAR (BINANCE VISION + TOP EXCHANGES)
# ==============================================================================
def fetch_binance_vision_tickers():
    endpoints = [
        "https://data-api.binance.vision/api/v3/ticker/24hr",
        "https://api-gcp.binance.com/api/v3/ticker/24hr"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    parsed = {}
                    for item in data:
                        sym = item.get('symbol', '')
                        if sym.endswith('USDT'):
                            base = sym[:-4].upper()
                            pct = float(item.get('priceChangePercent', 0) or 0)
                            vol = float(item.get('quoteVolume', 0) or 0)
                            last_p = float(item.get('lastPrice', 0) or 0)
                            if base and last_p > 0:
                                parsed[base] = {
                                    "source": "Binance",
                                    "pct_24h": pct,
                                    "vol_quote": vol,
                                    "price": last_p
                                }
                    if parsed:
                        return parsed
        except Exception:
            continue
    return {}

def start_global_radar_worker():
    global global_composite_tickers, radar_counts
    def worker():
        while True:
            bn = fetch_binance_vision_tickers()
            if bn:
                global_composite_tickers.update(bn)
                radar_counts["Binance"] = len(bn)

            for ex_name, ex in [("Bybit", bybit_radar), ("OKX", okx_radar), ("Gate", gate_radar)]:
                try:
                    tickers = ex.fetch_tickers()
                    c = 0
                    for s, t in tickers.items():
                        base = s.split('/')[0].split(':')[0].upper()
                        pct = float(t.get('percentage', 0) or 0)
                        vol = float(t.get('quoteVolume', 0) or 0)
                        last_p = float(t.get('last', 0) or 0)
                        if base and last_p > 0:
                            if base not in global_composite_tickers:
                                global_composite_tickers[base] = {
                                    "source": ex_name,
                                    "pct_24h": pct,
                                    "vol_quote": vol,
                                    "price": last_p
                                }
                            c += 1
                    radar_counts[ex_name] = c
                except Exception:
                    pass
                time.sleep(1)
            time.sleep(3)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("[SYSTEM] Global Multi-Exchange Composite Radar online.", flush=True)

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

# ==============================================================================
# 8. BITGET ORDER INTERFACE
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
        return bitget.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'buy_single'})
    except Exception:
        return bitget.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'open'})

def close_long_position(symbol, amount):
    try:
        return bitget.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'reduceOnly': True, 'tradeSide': 'sell_single'})
    except Exception:
        return bitget.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'reduceOnly': True, 'tradeSide': 'close'})

def open_short_position(symbol, amount):
    try:
        return bitget.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'sell_single'})
    except Exception:
        return bitget.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'open'})

def close_short_position(symbol, amount):
    try:
        return bitget.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'reduceOnly': True, 'tradeSide': 'buy_single'})
    except Exception:
        return bitget.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'reduceOnly': True, 'tradeSide': 'close'})

# ==============================================================================
# 9. GROWING-DEPTH & ANTI-SPOOFING ASYMMETRY AUDIT
# ==============================================================================
last_depth_audit_time = 0

def audit_order_flow_depth_trend(symbol):
    """
    HUMAN DEPTH TRACKER:
    Measures depth over time.
    1. For Long: Not only must Bids >> Asks, but Bids must be INCREASING minute-over-minute.
       If Bids are reducing (spoof cancel or dying demand), it VETOES the trade!
    2. For Short: Not only must Asks >> Bids, but Asks must be INCREASING minute-over-minute.
       If Asks are reducing, it VETOES the trade!
    """
    global depth_history
    try:
        ob = bitget.fetch_order_book(symbol, limit=25)
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])

        if not bids or not asks:
            return None

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        cur_mid = (best_bid + best_ask) / 2.0

        # Calculate dollar depth within 1.5% distance
        bid_depth_usdt = sum([price * qty for price, qty in bids if price >= cur_mid * 0.985])
        ask_depth_usdt = sum([price * qty for price, qty in asks if price <= cur_mid * 1.015])

        if ask_depth_usdt <= 0 or bid_depth_usdt <= 0:
            return None

        now = time.time()
        imbalance_ratio = bid_depth_usdt / ask_depth_usdt

        # Initialize history for this symbol
        if symbol not in depth_history:
            depth_history[symbol] = []

        depth_history[symbol].append((now, bid_depth_usdt, ask_depth_usdt, cur_mid))
        if len(depth_history[symbol]) > 10:
            depth_history[symbol].pop(0)

        # We need at least 1 prior check (30 to 90 seconds ago) to verify if depth is INCREASING
        prior_records = [rec for rec in depth_history[symbol] if 20.0 <= (now - rec[0]) <= 120.0]
        if not prior_records:
            return None

        prev_time, prev_bid, prev_ask, prev_price = prior_records[-1]

        # ----------------------------------------------------------------------
        # SCENARIO A: GROWING BID PRESSURE (REAL LONG ACCUMULATION)
        # Bids must be at least 3x asks, AND Bids must be INCREASING!
        # If bids are reducing, it's a fake/spoof wall -> VETO!
        # ----------------------------------------------------------------------
        if imbalance_ratio >= 3.0 and bid_depth_usdt >= 20_000:
            bid_growth_pct = ((bid_depth_usdt - prev_bid) / prev_bid) * 100.0

            # It MUST be increasing or holding strong (+5% or more growth), NOT reducing!
            if bid_growth_pct >= 5.0 and ask_depth_usdt <= (prev_ask * 1.2):
                return {
                    "type": "GROWING_BID_PRESSURE_LONG",
                    "side": "long",
                    "ratio": round(imbalance_ratio, 2),
                    "bid_usdt": round(bid_depth_usdt, 0),
                    "bid_growth_pct": round(bid_growth_pct, 1),
                    "ask_usdt": round(ask_depth_usdt, 0),
                    "mid_price": cur_mid
                }

        # ----------------------------------------------------------------------
        # SCENARIO B: GROWING ASK DUMP (REAL SHORT PRESSURE)
        # Asks must be at least 3x bids, AND Asks must be INCREASING!
        # If asks are reducing, buyers are defending -> VETO!
        # ----------------------------------------------------------------------
        elif imbalance_ratio <= 0.33 and ask_depth_usdt >= 20_000:
            ask_growth_pct = ((ask_depth_usdt - prev_ask) / prev_ask) * 100.0

            if ask_growth_pct >= 5.0 and bid_depth_usdt <= (prev_bid * 1.2):
                return {
                    "type": "GROWING_ASK_DUMP_SHORT",
                    "side": "short",
                    "ratio": round(imbalance_ratio, 2),
                    "ask_usdt": round(ask_depth_usdt, 0),
                    "ask_growth_pct": round(ask_growth_pct, 1),
                    "bid_usdt": round(bid_depth_usdt, 0),
                    "mid_price": cur_mid
                }

    except Exception:
        return None
    return None

# ==============================================================================
# 10. FAST SCANNER
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

        if brain.is_coin_in_penalty(symbol):
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
                        "current_price": cur_price
                    })
                    ticker_memory[symbol] = (cur_price, now, vol_24h)
                    continue

        if symbol not in ticker_memory or (now - ticker_memory[symbol][1]) >= 15.0:
            ticker_memory[symbol] = (cur_price, now, vol_24h)

    pings.sort(key=lambda x: abs(x['pct_move']), reverse=True)
    return pings

# ==============================================================================
# 11. MULTI-CAMERA LAB (APPLIES RECIPES IN REAL TIME)
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

        recipe = brain.recipes.get(strategy, {"max_duration_min": 3.0})
        max_hold_time = recipe.get("max_duration_min", 3.0)

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

        # Early Bank: Catch >= +1.50% net immediately
        if net_pnl >= 1.50:
            is_finished = True
            outcome = "TARGET_ACHIEVED"
            causality = f"Captured target early at +{net_pnl:.2f}% net!"

        # Breakeven Shield (+1.0% peak -> lock +0.25%)
        elif peak_pnl >= 1.00 and not cam.get('trail_locked', False):
            cam['trail_locked'] = True
            if side == 'long':
                cam['trade_hypothesis']['stop_price'] = entry_price * 1.0025
            else:
                cam['trade_hypothesis']['stop_price'] = entry_price * 0.9975
            stop_price = cam['trade_hypothesis']['stop_price']

        # 1. Liquidation
        elif (side == 'long' and cur_price <= liq_price) or (side == 'short' and cur_price >= liq_price):
            is_finished = True
            outcome = "LIQUIDATION_LOSS"
            causality = f"Hit liquidation at {liq_price:.4f}."

        # 2. Stop Hit
        elif (side == 'long' and cur_price <= stop_price) or (side == 'short' and cur_price >= stop_price):
            is_finished = True
            outcome = "STOP_LOSS_HIT"
            causality = f"Hit stop boundary at {stop_price:.4f}. Net PnL: {net_pnl:+.2f}%."

        # 3. Dynamic Timeout
        elif elapsed_min >= max_hold_time:
            is_finished = True
            outcome = "STAGNATION_TIMEOUT"
            causality = f"Decayed after dynamic hold limit of {max_hold_time:.1f}m. Net PnL: {net_pnl:+.2f}%."

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
            brain.record_film_outcome(strategy, net_pnl, causality, film_tape, archive['completed_films'])
            save_film_archive(archive)
        else:
            remaining.append(cam)

    archive['active_cameras'] = remaining

# ==============================================================================
# 12. LIVE GUARDIAN (FOR REAL MONEY)
# ==============================================================================
live_trade_state = {
    "active": False, "symbol": None, "side": None, "entry_price": 0.0,
    "entry_time": 0.0, "initial_stop_price": 0.0, "contracts": 0.0,
    "fee_shield_active": False, "highest_price": 0.0, "lowest_price": 0.0
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
    pnl_pct = ((cur_price - entry_p) / entry_p) * 100.0 if side == 'long' else ((entry_p - cur_price) / entry_p) * 100.0

    if pnl_pct >= 1.50:
        execute_live_exit("Banked Target >= +1.50%", pnl_pct)
        return

    if elapsed_sec >= 90 and pnl_pct < 0.05:
        execute_live_exit("Human Hesitation Cut: Momentum stalled", pnl_pct)
        return

    if side == 'long' and cur_price <= live_trade_state["initial_stop_price"]:
        execute_live_exit("Stop Hit", pnl_pct)
    elif side == 'short' and cur_price >= live_trade_state["initial_stop_price"]:
        execute_live_exit("Stop Hit", pnl_pct)

# ==============================================================================
# 13. MAIN ENGINE LOOP
# ==============================================================================
def main():
    global live_trade_state, last_depth_audit_time
    start_keep_alive()
    start_global_radar_worker()
    print("[SYSTEM] APEX-V16 Growing-Depth & Anti-Spoofing Engine online.", flush=True)

    try:
        bitget.load_markets()
        print(f"[SYSTEM] Loaded {len(bitget.markets)} pairs from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARN] Market load warning: {e}", flush=True)

    archive = load_film_archive()
    cycle = 1

    while True:
        try:
            # 1. Position Guardian
            pos = get_open_position()
            if pos and not live_trade_state["active"]:
                live_trade_state = {
                    "active": True, "symbol": pos['symbol'], "side": pos['side'],
                    "entry_price": pos['entry_price'], "entry_time": time.time(),
                    "initial_stop_price": pos['entry_price'] * (0.988 if pos['side'] == 'long' else 1.012),
                    "contracts": pos['contracts'], "fee_shield_active": False,
                    "highest_price": pos['entry_price'], "lowest_price": pos['entry_price']
                }
            if live_trade_state["active"]:
                poll_live_trade_guardian()

            # 2. Run Observational Cameras
            if archive['active_cameras']:
                run_filming_cameras(archive, leverage=4)
                save_film_archive(archive)

            # 3. Capital Safety Check
            balance_info = bitget.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            is_safe, reason = circuit_breaker.check_safety(usdt_free)
            if not is_safe:
                print(f"\n[VAULT SHIELD LOCKED] {reason} | Free USDT: ${usdt_free:.2f}. Sleeping...\n", flush=True)
                time.sleep(60)
                continue

            leverage = 3 if usdt_free >= 2.40 else (4 if usdt_free >= 1.80 else 5)
            raw_notional = (usdt_free * BALANCE_USE_PCT) * leverage
            notional = max(min(raw_notional, MAX_ORDER_NOTIONAL), MIN_ORDER_NOTIONAL)

            # 4. Fetch Universe Tickers
            try:
                tickers = bitget.fetch_tickers()
            except Exception:
                time.sleep(4)
                continue

            active_syms = {c['symbol'] for c in archive['active_cameras']}

            # ==============================================================
            # THE 5-MINUTE GROWING DEPTH SQUEEZE AUDIT (ANTI-SPOOFING)
            # ==============================================================
            now_t = time.time()
            if now_t - last_depth_audit_time >= 120.0:  # Check depth momentum every 2 minutes
                last_depth_audit_time = now_t
                top_vol_coins = [
                    s for s, t in tickers.items()
                    if s.endswith(":USDT") and float(t.get('quoteVolume', 0) or 0) >= MIN_24H_VOLUME
                ][:18]

                for audit_sym in top_vol_coins:
                    if audit_sym in active_syms or brain.is_coin_in_penalty(audit_sym):
                        continue

                    depth_event = audit_order_flow_depth_trend(audit_sym)
                    if depth_event and len(archive['active_cameras']) < MAX_PARALLEL_CAMERAS:
                        sq_type = depth_event["type"]
                        sq_side = depth_event["side"]
                        mid_p = depth_event["mid_price"]
                        ratio = depth_event["ratio"]

                        r = brain.recipes.get(sq_type, {"stop_mult": 1.4, "target_mult": 1.8, "max_duration_min": 3.0})
                        stop_d = max(mid_p * 0.009, mid_p * 0.006 * r['stop_mult'])
                        target_d = max(mid_p * 0.0160, mid_p * 0.006 * r['target_mult'])

                        s_price = mid_p - stop_d if sq_side == 'long' else mid_p + stop_d
                        t_price = mid_p + target_d if sq_side == 'long' else mid_p - target_d
                        l_price = mid_p * (1.0 - (1.0 / leverage) + BITGET_MAINTENANCE_MARGIN) if sq_side == 'long' else mid_p * (1.0 + (1.0 / leverage) - BITGET_MAINTENANCE_MARGIN)

                        new_cam = {
                            "symbol": audit_sym,
                            "strategy": sq_type,
                            "started_at": time.time(),
                            "highest_price": mid_p,
                            "lowest_price": mid_p,
                            "trail_locked": False,
                            "film_ticks": [{"t": 0, "p": mid_p}],
                            "trade_hypothesis": {
                                "side": sq_side,
                                "entry_price": mid_p,
                                "stop_price": s_price,
                                "target_price": t_price,
                                "liq_price": l_price,
                                "simulated_notional": notional
                            }
                        }
                        archive['active_cameras'].append(new_cam)
                        active_syms.add(audit_sym)
                        save_film_archive(archive)

                        growth_str = f"Bid grew +{depth_event['bid_growth_pct']}%" if sq_side == 'long' else f"Ask grew +{depth_event['ask_growth_pct']}%"
                        obs = f"Order Flow Squeeze confirmed! Ratio: {ratio}x ({growth_str}). Pressure verified."
                        print(f"\n[GROWING DEPTH VERIFIED] {audit_sym} -> {sq_type} ({sq_side.upper()}) | {obs}", flush=True)
                        write_story_log("GROWING_DEPTH_CONFIRMED", audit_sym, obs, f"Testing {sq_type}.")

            # 5. Formulate Hypotheses on Momentum Pings
            pings = scan_all_coins_fearlessly(tickers, archive)

            for ping in pings:
                sym = ping['symbol']
                base = ping['base']
                cur_price = ping['current_price']
                start_price = ping['start_price']
                dir_move = ping['direction']

                if live_trade_state["active"]:
                    break

                global_info = global_composite_tickers.get(base)
                global_pct = global_info.get('pct_24h', 0) if global_info else 0

                if global_info and abs(global_pct) > 3.0:
                    strategy = "BREAKOUT_CONTINUATION"
                    base_side = "long" if dir_move == "EXPANDING_UP" else "short"
                elif abs(ping['pct_move']) >= 0.70:
                    strategy = "MEAN_REVERSION_SNAP"
                    base_side = "short" if dir_move == "EXPANDING_UP" else "long"
                else:
                    strategy = "QUICK_IMPULSE_CHASE"
                    base_side = "long" if dir_move == "EXPANDING_UP" else "short"

                r = brain.recipes.get(strategy, {"stop_mult": 1.5, "target_mult": 1.7, "invert_bias": False})
                side = ("short" if base_side == "long" else "long") if r.get("invert_bias", False) else base_side

                wave = abs(cur_price - start_price)
                stop_dist = max(wave * r['stop_mult'], cur_price * 0.009)
                target_dist = max(wave * r['target_mult'], cur_price * 0.0160)

                entry_price = cur_price
                stop_price = entry_price - stop_dist if side == 'long' else entry_price + stop_dist
                target_price = entry_price + target_dist if side == 'long' else entry_price - target_dist
                liq_price = entry_price * (1.0 - (1.0 / leverage) + BITGET_MAINTENANCE_MARGIN) if side == 'long' else entry_price * (1.0 + (1.0 / leverage) - BITGET_MAINTENANCE_MARGIN)

                # ==============================================================
                # 9/10 PROMOTION CHECK (ZERO CASH -> REAL MONEY)
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

                        print(f"\n[LIVE PROMOTION EXECUTION: {side.upper()}] Recipe {strategy} hit 9/10 wins!", flush=True)
                        order = open_long_position(sym, formatted_amount) if side == 'long' else open_short_position(sym, formatted_amount)
                        time.sleep(2)

                        real_pos = get_open_position()
                        real_fill = real_pos['entry_price'] if real_pos else entry_price
                        real_cnt = real_pos['contracts'] if real_pos else formatted_amount

                        live_trade_state = {
                            "active": True, "symbol": sym, "side": side,
                            "entry_price": real_fill, "entry_time": time.time(),
                            "initial_stop_price": stop_price, "contracts": real_cnt,
                            "fee_shield_active": False, "highest_price": real_fill, "lowest_price": real_fill
                        }
                        break

                # ==============================================================
                # OPEN AUTONOMOUS PAPER CAMERA
                # ==============================================================
                elif len(archive['active_cameras']) < MAX_PARALLEL_CAMERAS and sym not in active_syms:
                    new_cam = {
                        "symbol": sym,
                        "strategy": strategy,
                        "started_at": time.time(),
                        "highest_price": entry_price,
                        "lowest_price": entry_price,
                        "trail_locked": False,
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
                    active_syms.add(sym)
                    save_film_archive(archive)
                    inv_tag = " [INVERTED]" if r.get("invert_bias") else ""
                    print(f"[AUTONOMOUS CAMERA #{len(archive['active_cameras'])} LOCKED] {sym} | {strategy}{inv_tag} ({side.upper()}) | Max Hold: {r['max_duration_min']}m", flush=True)

            # 6. Status Pulse
            if cycle % 3 == 0:
                summary_brain = brain.get_summary_status()
                strikes = circuit_breaker.consecutive_losses
                total_liquid = len([s for s, t in tickers.items() if float(t.get('quoteVolume', 0) or 0) >= MIN_24H_VOLUME and s.endswith(':USDT')])
                global_sync_count = len(global_composite_tickers)
                bn_c = radar_counts.get("Binance", 0)

                print(
                    f"\n[ENGINE PULSE] Status: ACTIVE | Cameras: {len(archive['active_cameras'])}/{MAX_PARALLEL_CAMERAS}\n"
                    f"Vault: ${usdt_free:.2f} USDT ({leverage}x) | Loss Strikes: {strikes}/2 | Radar: {global_sync_count} (Binance: {bn_c})\n"
                    f"Autonomous Recipe Book -> [{summary_brain}]",
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

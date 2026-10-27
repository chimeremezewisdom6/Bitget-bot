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
# 1. RENDER 24/7 KEEP-ALIVE SERVER (PORT 10000 FOR UPTIMEROBOT)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
EXAM_RECORDS_FILE = "exam_gradebook.json"
CB_FILE = "circuit_breaker.json"

class ExamStatusServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "engine": "APEX-V16 Autonomous Exam-Solving Engine",
            "active_exams": len(archive.get("active_cameras", [])),
            "gradebook": brain.get_gradebook_summary(),
            "status": "SOLVING_MARKETS"
        }
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_keep_alive():
    server = HTTPServer(("0.0.0.0", PORT), ExamStatusServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive Exam Server online on port {PORT}", flush=True)

# ==============================================================================
# 2. THE EXAM PAPER (QUESTIONS & RELATIONAL EQUATIONS)
# ==============================================================================
class MarketExamPaper:
    """
    The Question Paper: The bot solves these questions dynamically for every coin.
    No hardcoded orders are issued. The bot evaluates the solutions.
    """

    @staticmethod
    def solve_question_1_inflow_force(cur_bids, prev_bids, cur_asks, prev_asks):
        """
        QUESTION 1:
        Given previous and current order books, solve for Q1 (Net Inflow Force).
        Equation: Q1 = (Bid Growth / Ask Growth) * (Current Bid / Current Ask Ratio)
        """
        bid_growth = (cur_bids / prev_bids) if prev_bids > 0 else 1.0
        ask_growth = (cur_asks / prev_asks) if prev_asks > 0 else 1.0
        ratio = (cur_bids / cur_asks) if cur_asks > 0 else 1.0

        q1 = (bid_growth / ask_growth) * (ratio / 2.0) if ask_growth > 0 else ratio
        return round(q1, 3)

    @staticmethod
    def solve_question_2_spoof_resilience(cur_total_depth, prev_total_depth):
        """
        QUESTION 2:
        Is the liquidity expansion genuine or a spoof?
        Equation: Q2 = Total Book Depth Now / Baseline Book Depth
        """
        if prev_total_depth <= 0:
            return 1.0
        q2 = cur_total_depth / prev_total_depth
        return round(q2, 3)

    @staticmethod
    def solve_question_3_friction_edge(spread_pct, taker_fee_pct):
        """
        QUESTION 3:
        What is the friction cost of entry/exit, and what target is mathematically required?
        Equation: Friction = (2 * Taker Fee) + Spread
                  Target_Pct = max(Friction * 3.0, 0.40%)
                  Q3 (Net Edge) = Target_Pct - Friction
        """
        friction = (taker_fee_pct * 2.0) + spread_pct
        target_pct = max(friction * 3.0, 0.0040)  # Requires 3x the friction cost
        q3_net_edge = target_pct - friction
        return round(q3_net_edge * 100.0, 3), round(target_pct * 100.0, 3), round(friction * 100.0, 4)

    @staticmethod
    def solve_question_4_adaptive_time(target_pct, velocity_pct_per_min):
        """
        QUESTION 4:
        At current market speed, how many minutes will price need to travel to the target?
        Equation: Q4 (Minutes) = (Target_Pct / Velocity_Pct_Per_Min) * 1.5
        """
        if velocity_pct_per_min <= 0:
            return 8.0
        time_needed = (target_pct / velocity_pct_per_min) * 1.5
        # Bound time naturally between 4 minutes and 15 minutes
        q4_minutes = max(min(time_needed, 15.0), 4.0)
        return round(q4_minutes, 1)

    @staticmethod
    def solve_question_5_invalidation_boundary(target_pct):
        """
        QUESTION 5:
        Where does the hypothesis become invalid?
        Equation: Q5 (Stop Loss Pct) = Target_Pct / 1.5 (yielding a 1.5:1 Risk/Reward ratio)
        """
        q5_stop_pct = target_pct / 1.5
        return round(q5_stop_pct, 3)

    @classmethod
    def grade_candidate_exam(cls, market_input):
        """
        Runs the full examination on the coin and returns the complete answer sheet.
        """
        q1_force = cls.solve_question_1_inflow_force(
            market_input["cur_bids"], market_input["prev_bids"],
            market_input["cur_asks"], market_input["prev_asks"]
        )

        q2_resilience = cls.solve_question_2_spoof_resilience(
            market_input["cur_bids"] + market_input["cur_asks"],
            market_input["prev_bids"] + market_input["prev_asks"]
        )

        q3_edge, target_pct, friction = cls.solve_question_3_friction_edge(
            market_input["spread_pct"], market_input["taker_fee_pct"]
        )

        q4_time = cls.solve_question_4_adaptive_time(
            target_pct, market_input["velocity_pct_per_min"]
        )

        q5_stop = cls.solve_question_5_invalidation_boundary(target_pct)

        # ----------------------------------------------------------------------
        # FINAL EXAM SCORING (0% TO 100%)
        # ----------------------------------------------------------------------
        score = 0.0

        # Criterion 1: Strong Buyer Dominance (Q1 >= 2.0 gives full points)
        score += min((q1_force / 2.0) * 40.0, 40.0)

        # Criterion 2: Book Resilience / Anti-Spoof (Q2 >= 1.3 gives full points)
        score += min((q2_resilience / 1.3) * 30.0, 30.0)

        # Criterion 3: Net Profit Edge covers friction (Q3 >= 0.25% net)
        if q3_edge >= 0.25:
            score += 30.0

        passing_grade = score >= 75.0  # Pass mark: 75%

        return {
            "q1_inflow_force": q1_force,
            "q2_resilience": q2_resilience,
            "q3_net_edge_pct": q3_edge,
            "q4_time_minutes": q4_time,
            "q5_stop_pct": q5_stop,
            "target_pct": target_pct,
            "friction_pct": friction,
            "exam_score": round(score, 1),
            "passed": passing_grade
        }

# ==============================================================================
# 3. CONTINUOUS GRADEBOOK BRAIN (LEARNING FROM EXAM RESULTS)
# ==============================================================================
class GradebookBrain:
    def __init__(self):
        self.grades = []
        self.load()

    def load(self):
        if os.path.exists(EXAM_RECORDS_FILE):
            try:
                with open(EXAM_RECORDS_FILE, "r") as f:
                    self.grades = json.load(f).get("grades", [])
            except Exception:
                self.grades = []

    def save(self):
        try:
            with open(EXAM_RECORDS_FILE, "w") as f:
                json.dump({"grades": self.grades}, f, indent=2)
        except Exception:
            pass

    def record_exam_outcome(self, is_win):
        # Sliding window of the last 15 trade tests (no 0/0 wiping)
        self.grades.append(1 if is_win else 0)
        self.grades = self.grades[-15:]
        self.save()

    def is_candidate_for_live(self):
        # Requires 7 out of the last 10 solved exams to produce verified wins
        return len(self.grades) >= 10 and sum(self.grades[-10:]) >= 7

    def get_gradebook_summary(self):
        w = sum(self.grades)
        tot = len(self.grades)
        pct = (w / tot * 100) if tot > 0 else 0
        return f"{w}/{tot} exams verified ({pct:.0f}% success rate)"

brain = GradebookBrain()

# ==============================================================================
# 4. EXCHANGE SETUP & RISK VAULT
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing exchange credentials in environment variables!", flush=True)
    sys.exit(1)

bitget = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "password": PASSPHRASE,
    "enableRateLimit": True,
    "timeout": 20000,
    "options": {"defaultType": "swap"}
})

LEVERAGE = 4
TAKER_FEE_DECIMAL = 0.0006  # 0.06%
EQUITY_FLOOR = 1.50
MAX_CONSECUTIVE_LOSSES = 2

class RiskVault:
    def __init__(self):
        self.strikes = 0
        self.load()

    def load(self):
        if os.path.exists(CB_FILE):
            try:
                with open(CB_FILE, "r") as f:
                    self.strikes = json.load(f).get("strikes", 0)
            except Exception:
                pass

    def save(self):
        try:
            with open(CB_FILE, "w") as f:
                json.dump({"strikes": self.strikes}, f)
        except Exception:
            pass

    def check_safety(self, balance):
        if balance < EQUITY_FLOOR:
            return False, f"Balance ${balance:.2f} breached floor ${EQUITY_FLOOR:.2f}"
        if self.strikes >= MAX_CONSECUTIVE_LOSSES:
            return False, "Two-strike safety rest period active"
        return True, "SAFE"

    def register_result(self, won):
        self.strikes = 0 if won else self.strikes + 1
        self.save()

vault = RiskVault()
depth_memory = {}

# ==============================================================================
# 5. EXAM SOLVING WORKER (RUNS ON LIVE MARKET TICKS)
# ==============================================================================
def conduct_coin_exam(symbol):
    global depth_memory
    try:
        ob = bitget.fetch_order_book(symbol, limit=25)
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])

        if not bids or not asks:
            return None

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid = (best_bid + best_ask) / 2.0
        spread_pct = (best_ask - best_bid) / mid

        # Sum depth in USD within 1.5% band
        cur_bids = sum([p * q for p, q in bids if p >= mid * 0.985])
        cur_asks = sum([p * q for p, q in asks if p <= mid * 1.015])

        if cur_bids < 10_000 or cur_asks <= 0:
            return None

        now = time.time()
        if symbol not in depth_memory:
            depth_memory[symbol] = []

        depth_memory[symbol].append({"t": now, "b": cur_bids, "a": cur_asks, "p": mid})
        depth_memory[symbol] = [s for s in depth_memory[symbol] if now - s["t"] <= 600.0]

        # Valid baseline between 20s and 300s (under 5 mins)
        lookbacks = [s for s in depth_memory[symbol] if 20.0 <= (now - s["t"]) <= 300.0]
        if not lookbacks:
            return None

        baseline = lookbacks[0]
        elapsed_m = (now - baseline["t"]) / 60.0
        price_move = abs((mid - baseline["p"]) / baseline["p"]) * 100.0
        velocity = (price_move / elapsed_m) if elapsed_m > 0 else 0.05

        market_input = {
            "cur_bids": cur_bids,
            "cur_asks": cur_asks,
            "prev_bids": baseline["b"],
            "prev_asks": baseline["a"],
            "spread_pct": spread_pct,
            "velocity_pct_per_min": velocity,
            "taker_fee_pct": TAKER_FEE_DECIMAL
        }

        # The bot grades the candidate coin
        answers = MarketExamPaper.grade_candidate_exam(market_input)

        if answers["passed"]:
            return {
                "symbol": symbol,
                "mid": mid,
                "answers": answers,
                "summary": (
                    f"Exam Score: {answers['exam_score']}% | Q1(Force)={answers['q1_inflow_force']} | "
                    f"Q2(Resilience)={answers['q2_resilience']}x | Target=+{answers['target_pct']}% | "
                    f"Stop=-{answers['q5_stop_pct']}% | Time={answers['q4_time_minutes']}m"
                )
            }

    except Exception:
        return None

    return None

# ==============================================================================
# 6. OBSERVATION LAB (TRACKING SOLVED EXAMS IN REAL TIME)
# ==============================================================================
archive = {"active_cameras": []}

def monitor_active_cameras():
    remaining = []
    now = time.time()

    for cam in archive.get("active_cameras", []):
        sym = cam["symbol"]
        entry_p = cam["entry_p"]
        target_pct = cam["target_pct"]
        stop_pct = cam["stop_pct"]
        max_duration = cam["max_minutes"]
        elapsed_m = (now - cam["start_t"]) / 60.0

        try:
            ticker = bitget.fetch_ticker(sym)
            cur_p = float(ticker.get('last', 0) or 0)
        except Exception:
            remaining.append(cam)
            continue

        price_delta_pct = ((cur_p - entry_p) / entry_p) * 100.0
        net_roe = (price_delta_pct * LEVERAGE) - (TAKER_FEE_DECIMAL * 2.0 * LEVERAGE * 100.0)

        is_done = False
        won = False
        reason = ""

        # Did price solve for the target?
        if price_delta_pct >= target_pct:
            is_done = True
            won = True
            reason = f"Target Solved! Net ROE: {net_roe:+.2f}% in {elapsed_m:.1f}m"

        # Did price breach the solved stop boundary?
        elif price_delta_pct <= -stop_pct:
            is_done = True
            won = False
            reason = f"Stop Boundary Hit: Net ROE {net_roe:+.2f}%"

        # Did solved duration 'Q4' expire?
        elif elapsed_m >= max_duration:
            is_done = True
            won = net_roe > 0.20
            reason = f"Solved Time Q4 ({max_duration}m) Expired. Closed at {net_roe:+.2f}% ROE"

        if is_done:
            brain.record_exam_outcome(won)
            print(f"\n[EXAM RESULT RECORDED] {sym} -> {reason}", flush=True)
            print(f"[CURRENT GRADEBOOK] {brain.get_gradebook_summary()}\n", flush=True)
        else:
            remaining.append(cam)

    archive["active_cameras"] = remaining

# ==============================================================================
# 7. LIVE GUARDIAN (FOR REAL CAPITAL WHEN EXAMS QUALIFY)
# ==============================================================================
live_state = {"active": False, "symbol": None, "contracts": 0, "entry_p": 0, "start_t": 0, "target_pct": 0, "stop_pct": 0, "max_m": 0}

def close_live_trade(reason, won):
    global live_state
    sym = live_state["symbol"]
    cnt = live_state["contracts"]

    for _ in range(3):
        try:
            bitget.create_order(sym, 'market', 'sell', cnt, params={'reduceOnly': True, 'tradeSide': 'close'})
            break
        except Exception:
            time.sleep(1)

    vault.register_result(won)
    print(f"\n[LIVE TRADE EXITED] {sym} | Reason: {reason}\n", flush=True)
    live_state["active"] = False

def poll_live_guardian():
    global live_state
    if not live_state["active"]:
        return

    sym = live_state["symbol"]
    entry_p = live_state["entry_p"]
    elapsed_m = (time.time() - live_state["start_t"]) / 60.0

    try:
        cur_p = float(bitget.fetch_ticker(sym).get('last', 0) or 0)
    except Exception:
        return

    delta = ((cur_p - entry_p) / entry_p) * 100.0

    if delta >= live_state["target_pct"]:
        close_live_trade(f"Target Hit (+{delta:.2f}%)", won=True)
    elif delta <= -live_state["stop_pct"]:
        close_live_trade(f"Stop Boundary Hit ({delta:.2f}%)", won=False)
    elif elapsed_m >= live_state["max_m"]:
        close_live_trade(f"Time Q4 Elapsed ({elapsed_m:.1f}m)", won=(delta > 0))

# ==============================================================================
# 8. MAIN ENGINE LOOP
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-V16 Autonomous Exam-Solving Engine initialized.", flush=True)

    try:
        bitget.load_markets()
    except Exception as e:
        print(f"[WARN] Market load warning: {e}", flush=True)

    cycle = 0

    while True:
        try:
            # 1. Update cameras and live trade
            monitor_active_cameras()
            if live_state["active"]:
                poll_live_guardian()

            # 2. Risk check
            balance = float(bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
            is_safe, msg = vault.check_safety(balance)

            if not is_safe:
                print(f"[SAFETY PAUSE] {msg}. Free: ${balance:.2f}. Sleeping...", flush=True)
                time.sleep(30)
                continue

            notional = max(min(balance * 0.85 * LEVERAGE, 7.50), 5.15)

            # 3. Scan universe
            try:
                tickers = bitget.fetch_tickers()
            except Exception:
                time.sleep(4)
                continue

            active_syms = {c["symbol"] for c in archive.get("active_cameras", [])}
            candidates = [
                s for s, t in tickers.items()
                if s.endswith(":USDT")
                and float(t.get('quoteVolume', 0) or 0) >= 1_000_000
                and s not in active_syms
            ][:18]

            # 4. Run exams on candidate coins
            for sym in candidates:
                if len(archive.get("active_cameras", [])) >= 8:
                    break

                exam_result = conduct_coin_exam(sym)
                if exam_result:
                    ans = exam_result["answers"]
                    mid = exam_result["mid"]

                    # If the bot has proven itself with 7/10 verified exams, trade live
                    if brain.is_candidate_for_live() and not live_state["active"]:
                        try:
                            bitget.set_leverage(LEVERAGE, sym)
                        except Exception:
                            pass
                        amount = float(bitget.amount_to_precision(sym, notional / mid))
                        bitget.create_order(sym, 'market', 'buy', amount)
                        live_state = {
                            "active": True, "symbol": sym, "contracts": amount,
                            "entry_p": mid, "start_t": time.time(),
                            "target_pct": ans["target_pct"], "stop_pct": ans["q5_stop_pct"],
                            "max_m": ans["q4_time_minutes"]
                        }
                        print(f"\n[LIVE PROMOTION EXECUTED] {sym} passed exam with {ans['exam_score']}%! {exam_result['summary']}", flush=True)
                        break

                    # Otherwise, film in the observational lab
                    archive["active_cameras"].append({
                        "symbol": sym,
                        "entry_p": mid,
                        "target_pct": ans["target_pct"],
                        "stop_pct": ans["q5_stop_pct"],
                        "max_minutes": ans["q4_time_minutes"],
                        "start_t": time.time()
                    })
                    print(f"[EXAM PASSED & CAMERA LOCKED] {sym} -> {exam_result['summary']}", flush=True)

            # 5. Engine Heartbeat Pulse
            if cycle % 6 == 0:
                print(
                    f"\n[EXAM ENGINE PULSE] Active Solvers: {len(archive.get('active_cameras', []))}/8 | "
                    f"Vault: ${balance:.2f} ({LEVERAGE}x) | "
                    f"Gradebook: {brain.get_gradebook_summary()}",
                    flush=True
                )

            cycle += 1
            time.sleep(4)

        except Exception as e:
            print(f"[LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()

import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. LIVE KEEP-ALIVE SERVER (PORT 10000 FOR UPTIMEROBOT ON RENDER)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
BRAIN_FILE = "autonomous_diagnosis_memory.json"
CB_FILE = "circuit_breaker.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "engine": "APEX-V16 Self-Diagnosing Vacuum Bot",
            "mode": "DEMOTED_TO_PAPER (Needs 6/6)" if bot.is_demoted else ("LIVE_READY" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Needs 9/10)"),
            "paper_scorecard": bot.get_paper_score(),
            "live_strikes": f"{bot.consecutive_live_losses}/2",
            "active_cameras": len(bot.active_cameras),
            "current_parameters": bot.parameters
        }
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# 2. AUTONOMOUS DIAGNOSTIC ENGINE & STATE CONTROLLER
# ==============================================================================
class DiagnosticVacuumBot:
    def __init__(self):
        # 1. Capital & Leverage
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2
        self.is_demoted = False  # Set to True if 2 consecutive live losses occur

        # 2. Dynamic Parameters (The Bot Auto-Tunes These Upon Diagnosis)
        self.parameters = {
            "target_pct": 0.0050,         # +0.50% spot move (~+1.52% Net ROE with 4x)
            "stop_pct": 0.0035,           # -0.35% spot move (~-1.40% Net ROE)
            "min_depletion_factor": 2.2,  # Resistance must collapse by at least 2.2x
            "min_velocity_mult": 18.0,    # 5m volume churn must be >= 18x depth
            "max_hold_minutes": 8.0,      # Natural duration window
            "fade_buffer_mult": 2.0       # Re-fill multiplier to trigger a Fade Exit
        }

        # 3. Memory & Tracking (Sliding windows, no 0/0 wiping)
        self.paper_history = []
        self.active_cameras = []
        self.market_memory = {}
        self.load_brain()

        # 4. Live Trade State (Bound to self)
        self.live_state = {
            "active": False,
            "symbol": None,
            "side": None,
            "contracts": 0,
            "entry_price": 0.0,
            "target_price": 0.0,
            "stop_price": 0.0,
            "min_resistance_seen": 0.0,
            "peak_price": 0.0,
            "trough_price": 0.0,
            "start_time": 0.0
        }

        # 5. Bitget Exchange Connection
        self.api_key = os.environ.get("API_KEY")
        self.secret_key = os.environ.get("SECRET_KEY")
        self.passphrase = os.environ.get("PASSPHRASE")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing Bitget credentials!", flush=True)
            sys.exit(1)

        self.bitget = ccxt.bitget({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })

    # --------------------------------------------------------------------------
    # PERSISTENCE & BRAIN STATE
    # --------------------------------------------------------------------------
    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.parameters.update(data.get("parameters", {}))
                    self.paper_history = data.get("paper_history", [])
                    self.is_demoted = data.get("is_demoted", False)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "parameters": self.parameters,
                    "paper_history": self.paper_history,
                    "is_demoted": self.is_demoted
                }, f, indent=2)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # QUALIFICATION GATES (9/10 INITIAL OR 6/6 RE-QUALIFICATION)
    # --------------------------------------------------------------------------
    def is_qualified_for_live(self):
        if self.is_demoted:
            # Rule: After 2 live losses, must achieve a clean 6/6 streak in paper
            if len(self.paper_history) >= 6 and sum(self.paper_history[-6:]) == 6:
                print("\n[RE-QUALIFIED] Clean 6/6 streak achieved in paper! Live trading re-unlocked.\n", flush=True)
                self.is_demoted = False
                self.consecutive_live_losses = 0
                self.save_brain()
                return True
            return False
        else:
            # Standard Rule: Requires 9 wins out of the last 10 paper trades (9/10)
            return len(self.paper_history) >= 10 and sum(self.paper_history[-10:]) >= 9

    def get_paper_score(self):
        tot = len(self.paper_history)
        w = sum(self.paper_history)
        if self.is_demoted:
            streak = 0
            for r in reversed(self.paper_history):
                if r == 1: streak += 1
                else: break
            return f"DEMOTED: {streak}/6 streak needed"
        return f"{w}/{tot} (Last 10: {sum(self.paper_history[-10:])}/10 | Target: 9/10)"

    # --------------------------------------------------------------------------
    # AUTONOMOUS DIAGNOSIS & REPAIR (THE BOT FIXES ITS OWN MISTAKES)
    # --------------------------------------------------------------------------
    def diagnose_and_repair(self, outcome, peak_roe, net_roe, elapsed_m, symbol):
        """
        Diagnoses why a trade failed or succeeded, and auto-tunes parameters
        BEFORE the next trade runs.
        """
        p = self.parameters
        repaired = False
        action_note = ""

        # MISTAKE CASE 1: Stopped out quickly (< 2.5 min)
        # Diagnosis: Entered into a fake vacuum; resistance wasn't depleted enough.
        # Action: Raise minimum depletion and velocity filters to demand stronger proof.
        if outcome == "STOP_HIT" and elapsed_m <= 2.5:
            old_dep = p["min_depletion_factor"]
            p["min_depletion_factor"] = min(round(p["min_depletion_factor"] + 0.2, 2), 3.5)
            p["min_velocity_mult"] = min(round(p["min_velocity_mult"] + 2.0, 1), 35.0)
            action_note = f"Early reversal detected. Tightened entry filters: Depletion {old_dep}x -> {p['min_depletion_factor']}x, Velocity -> {p['min_velocity_mult']}x"
            repaired = True

        # MISTAKE CASE 2: Price had good profit (Peak >= +0.80% ROE) but died at timeout/stop
        # Diagnosis: Profit greed. Target was set slightly too far for current market conditions.
        # Action: Micro-adjust target closer so money gets banked.
        elif outcome in ["STOP_HIT", "TIMEOUT"] and peak_roe >= 0.80:
            old_tgt = p["target_pct"] * 100.0
            p["target_pct"] = max(round(p["target_pct"] - 0.0004, 4), 0.0038)
            action_note = f"Greed trap detected (peaked at {peak_roe:+.2f}% ROE). Adjusted target: {old_tgt:.2f}% -> {p['target_pct']*100:.2f}%"
            repaired = True

        # MISTAKE CASE 3: Timed out while lingering near breakeven
        # Diagnosis: Market velocity decayed and liquidity dried up.
        # Action: Shorten hold time slightly to prevent capital tie-up.
        elif outcome == "TIMEOUT" and abs(net_roe) < 0.30:
            old_hold = p["max_hold_minutes"]
            p["max_hold_minutes"] = max(round(p["max_hold_minutes"] - 0.5, 1), 5.5)
            action_note = f"Chop stagnation. Reduced hold timer: {old_hold}m -> {p['max_hold_minutes']}m"
            repaired = True

        # SUCCESS CASE: Clean win on target
        # Action: Maintain current settings or gently expand target if momentum was effortless (< 3 min)
        elif outcome == "TARGET_HIT" and elapsed_m <= 3.0:
            p["target_pct"] = min(round(p["target_pct"] + 0.0002, 4), 0.0060)
            action_note = f"Effortless win in {elapsed_m:.1f}m. Slightly expanded target to {p['target_pct']*100:.2f}%"
            repaired = True

        if repaired:
            print(f"\n[AUTONOMOUS DIAGNOSIS & REPAIR on {symbol}] {action_note}\n", flush=True)
            self.save_brain()

    # --------------------------------------------------------------------------
    # MEASURE RESTING DEPTH WITHIN 1.0% OF MID-PRICE
    # --------------------------------------------------------------------------
    def get_resting_depth(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0

            ask_dollars = sum([p * q for p, q in asks if p <= mid * 1.010])
            bid_dollars = sum([p * q for p, q in bids if p >= mid * 0.990])

            return {
                "mid": mid,
                "ask_dollars": ask_dollars,
                "bid_dollars": bid_dollars
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # AUDIT THE 5-MINUTE VACUUM USING AUTO-TUNED PARAMETERS
    # --------------------------------------------------------------------------
    def audit_5m_vacuum(self, symbol, vol_24h):
        now = time.time()
        depth = self.get_resting_depth(symbol)
        if not depth:
            return None

        if symbol not in self.market_memory:
            self.market_memory[symbol] = []

        self.market_memory[symbol].append({
            "t": now,
            "vol_24h": vol_24h,
            "ask_dollars": depth["ask_dollars"],
            "bid_dollars": depth["bid_dollars"],
            "price": depth["mid"]
        })
        self.market_memory[symbol] = [s for s in self.market_memory[symbol] if now - s["t"] <= 600.0]

        history = self.market_memory[symbol]
        past_snaps = [s for s in history if 210.0 <= (now - s["t"]) <= 360.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        mid = depth["mid"]

        delta_vol_5m = vol_24h - baseline["vol_24h"]
        if delta_vol_5m < 20_000:
            return None

        p = self.parameters

        # SETUP 1: LONG VACUUM
        if depth["ask_dollars"] > 0 and baseline["ask_dollars"] > 0:
            ask_depletion = baseline["ask_dollars"] / depth["ask_dollars"]
            velocity_long = delta_vol_5m / depth["ask_dollars"]
            price_change = ((mid - baseline["price"]) / baseline["price"]) * 100.0

            if ask_depletion >= p["min_depletion_factor"] and velocity_long >= p["min_velocity_mult"] and price_change >= 0.10:
                return {
                    "symbol": symbol,
                    "side": "long",
                    "mid": mid,
                    "initial_resistance": depth["ask_dollars"],
                    "reason": f"5M LONG VACUUM (Depletion: {ask_depletion:.1f}x >= {p['min_depletion_factor']}x | Velocity: {velocity_long:.0f}x)"
                }

        # SETUP 2: SHORT SINKHOLE
        if depth["bid_dollars"] > 0 and baseline["bid_dollars"] > 0:
            bid_depletion = baseline["bid_dollars"] / depth["bid_dollars"]
            velocity_short = delta_vol_5m / depth["bid_dollars"]
            price_change = ((baseline["price"] - mid) / baseline["price"]) * 100.0

            if bid_depletion >= p["min_depletion_factor"] and velocity_short >= p["min_velocity_mult"] and price_change >= 0.10:
                return {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "initial_resistance": depth["bid_dollars"],
                    "reason": f"5M SHORT SINKHOLE (Depletion: {bid_depletion:.1f}x >= {p['min_depletion_factor']}x | Velocity: {velocity_short:.0f}x)"
                }

        return None

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION CAMERAS (PAPER EXPERIMENT + DIAGNOSIS)
    # --------------------------------------------------------------------------
    def update_cameras(self):
        remaining = []
        now = time.time()

        for cam in self.active_cameras:
            sym = cam["symbol"]
            side = cam["side"]
            entry = cam["entry_p"]
            target = cam["target_p"]
            stop = cam["stop_p"]
            elapsed_m = (now - cam["start_t"]) / 60.0

            depth = self.get_resting_depth(sym)
            if not depth:
                remaining.append(cam)
                continue

            cur_price = depth["mid"]
            cur_ask_dollars = depth["ask_dollars"]
            cur_bid_dollars = depth["bid_dollars"]

            delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
            net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

            if net_roe > cam["peak_roe"]:
                cam["peak_roe"] = net_roe

            # Track thinnest resistance
            if side == "long" and cur_ask_dollars < cam["min_resistance"]:
                cam["min_resistance"] = cur_ask_dollars
            elif side == "short" and cur_bid_dollars < cam["min_resistance"]:
                cam["min_resistance"] = cur_bid_dollars

            # Fade Check: Did resistance refill 2x and price tick against trade?
            long_faded = (side == "long" and cur_ask_dollars >= (cam["min_resistance"] * self.parameters["fade_buffer_mult"]) and cur_price < entry)
            short_faded = (side == "short" and cur_bid_dollars >= (cam["min_resistance"] * self.parameters["fade_buffer_mult"]) and cur_price > entry)

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= self.parameters["max_hold_minutes"]

            is_finished = False
            outcome = ""

            if hit_target:
                is_finished = True
                outcome = "TARGET_HIT"
            elif hit_stop:
                is_finished = True
                outcome = "STOP_HIT"
            elif (long_faded or short_faded) and elapsed_m >= 1.5:
                is_finished = True
                outcome = "FADE_CUT"
            elif timed_out:
                is_finished = True
                outcome = "TIMEOUT"

            if is_finished:
                is_win = 1 if (net_roe >= 1.20 or outcome == "TARGET_HIT") else 0
                self.paper_history.append(is_win)
                self.paper_history = self.paper_history[-15:]

                print(f"\n=======================================================", flush=True)
                print(f"[PAPER EXPERIMENT FINISHED] {sym} ({side.upper()}) | Result: {outcome} | Net ROE: {net_roe:+.2f}%", flush=True)
                print(f"[SCORECARD] {self.get_paper_score()}", flush=True)

                # DIAGNOSE AND REPAIR IMMEDIATELY
                self.diagnose_and_repair(outcome, cam["peak_roe"], net_roe, elapsed_m, sym)
                print(f"=======================================================\n", flush=True)
            else:
                remaining.append(cam)

        self.active_cameras = remaining

    # --------------------------------------------------------------------------
    # MONITOR LIVE TRADE GUARDIAN (2-STRIKE DEMOTION RULE)
    # --------------------------------------------------------------------------
    def poll_live_trade(self):
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        side = self.live_state["side"]
        entry = self.live_state["entry_price"]
        target = self.live_state["target_price"]
        stop = self.live_state["stop_price"]
        elapsed_m = (time.time() - self.live_state["start_time"]) / 60.0

        depth = self.get_resting_depth(sym)
        if not depth:
            return

        cur_price = depth["mid"]
        delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        close_now = False
        won = False
        reason = ""

        if (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target):
            close_now = True
            won = True
            reason = f"Target Hit (+{net_roe:.2f}% ROE)"
        elif (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop):
            close_now = True
            won = False
            reason = f"Stop Loss Hit ({net_roe:.2f}% ROE)"
        elif elapsed_m >= self.parameters["max_hold_minutes"]:
            close_now = True
            won = net_roe > 0
            reason = f"Max Duration Elapsed ({elapsed_m:.1f}m)"

        if close_now:
            order_side = 'sell' if side == 'long' else 'buy'
            for _ in range(3):
                try:
                    self.bitget.create_order(sym, 'market', order_side, self.live_state["contracts"], params={'reduceOnly': True, 'tradeSide': 'close'})
                    break
                except Exception:
                    time.sleep(1)

            # Update live strikes
            if won:
                self.consecutive_live_losses = 0
                print(f"\n[LIVE WIN RECORDED] {sym} won with {net_roe:+.2f}% ROE! Strikes reset to 0.\n", flush=True)
            else:
                self.consecutive_live_losses += 1
                print(f"\n[LIVE LOSS RECORDED] Strikes: {self.consecutive_live_losses}/{self.max_live_losses} on {sym} ({net_roe:+.2f}% ROE)\n", flush=True)

                # ==============================================================
                # THE 2-STRIKE DEMOTION RULE
                # ==============================================================
                if self.consecutive_live_losses >= self.max_live_losses:
                    self.is_demoted = True
                    print(f"\n*******************************************************", flush=True)
                    print(f"[EMERGENCY 2-STRIKE DEMOTION TRIGGERED]", flush=True)
                    print(f"2 consecutive live losses encountered! Real trading LOCKED.", flush=True)
                    print(f"Returning to Paper Trading. Must score a clean 6/6 streak to re-enter.", flush=True)
                    print(f"*******************************************************\n", flush=True)

            self.save_brain()
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Autonomous Diagnosing Engine active.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                # 1. Update Paper Cameras & Live Position
                self.update_cameras()
                self.poll_live_trade()

                # 2. Risk & Vault Floor Check
                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    print(f"[VAULT PAUSE] Balance ${balance:.2f} below ${self.equity_floor:.2f} floor. Sleeping...", flush=True)
                    time.sleep(30)
                    continue

                notional = max(min(balance * 0.85 * self.leverage, 7.50), 5.15)

                # 3. Fetch Tickers
                try:
                    tickers = self.bitget.fetch_tickers()
                except Exception:
                    time.sleep(4)
                    continue

                active_syms = {c["symbol"] for c in self.active_cameras}
                candidates = [
                    s for s, t in tickers.items()
                    if s.endswith(":USDT")
                    and float(t.get('quoteVolume', 0) or 0) >= 1_000_000
                    and s not in active_syms
                ]
                candidates.sort(key=lambda s: float(tickers[s].get('quoteVolume', 0) or 0), reverse=True)

                # 4. Search for 5-Minute Liquidity Vacuums
                for sym in candidates[:20]:
                    if len(self.active_cameras) >= 8:
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    vacuum = self.audit_5m_vacuum(sym, vol_24h)

                    if vacuum:
                        side = vacuum["side"]
                        mid = vacuum["mid"]
                        tgt_dist = mid * self.parameters["target_pct"]
                        stop_dist = mid * self.parameters["stop_pct"]

                        target_p = mid + tgt_dist if side == "long" else mid - tgt_dist
                        stop_p = mid - stop_dist if side == "long" else mid + stop_dist

                        # CHECK QUALIFICATION STATUS (9/10 Initial OR 6/6 Re-qualification)
                        can_trade_live = self.is_qualified_for_live()

                        if can_trade_live and not self.live_state["active"]:
                            try:
                                self.bitget.set_leverage(self.leverage, sym)
                            except Exception:
                                pass

                            amount = float(self.bitget.amount_to_precision(sym, notional / mid))
                            order_side = 'buy' if side == 'long' else 'sell'
                            self.bitget.create_order(sym, 'market', order_side, amount)

                            self.live_state = {
                                "active": True, "symbol": sym, "side": side,
                                "contracts": amount, "entry_price": mid,
                                "target_price": target_p, "stop_price": stop_p,
                                "min_resistance_seen": vacuum["initial_resistance"],
                                "peak_price": mid, "trough_price": mid,
                                "start_time": time.time()
                            }
                            print(f"\n[LIVE ORDER EXECUTED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)
                            break
                        else:
                            # Run in Observational Paper Lab
                            self.active_cameras.append({
                                "symbol": sym,
                                "side": side,
                                "entry_p": mid,
                                "target_p": target_p,
                                "stop_p": stop_p,
                                "min_resistance": vacuum["initial_resistance"],
                                "peak_roe": 0.0,
                                "start_t": time.time()
                            })
                            print(f"[PAPER CAMERA LOCKED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)

                # 5. Heartbeat Status
                if cycle % 6 == 0:
                    status_mode = "DEMOTED (Needs 6/6)" if self.is_demoted else ("LIVE_READY" if self.is_qualified_for_live() else "QUALIFYING (Needs 9/10)")
                    print(
                        f"\n[ENGINE PULSE] Status: {status_mode} | Cameras: {len(self.active_cameras)}/8 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | Strikes: {self.consecutive_live_losses}/2 | "
                        f"Score: {self.get_paper_score()}",
                        flush=True
                    )

                cycle += 1
                time.sleep(4)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(5)

# ==============================================================================
# START BOT
# ==============================================================================
if __name__ == "__main__":
    bot = DiagnosticVacuumBot()
    bot.run()

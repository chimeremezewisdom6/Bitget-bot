import os
import sys
import time
import json
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. LIVE KEEP-ALIVE SERVER (PORT 10000 FOR UPTIMEROBOT ON RENDER)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
BRAIN_FILE = "tick_radar_experiments.json"

bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX 10-Phase Simultaneous Discovery & Radar Telemetry",
                "experiments_completed": f"{bot.experiments_completed}/10",
                "calibration_state": "CALIBRATED_ACTIVE" if bot.is_calibrated else "DISCOVERY_RECORDING",
                "calibrated_tp_pct": f"{bot.calibrated_tp:.2f}%",
                "calibrated_sl_pct": f"{bot.calibrated_sl:.2f}%",
                "qualifying_streak": f"{bot.consecutive_paper_wins}/{bot.REQUIRED_WIN_STREAK}",
                "mode": "LIVE_AUTHORIZED" if bot.is_qualified_for_live() else "PAPER_DISCOVERY",
                "active_experiments": len(bot.active_experiments),
                "active_live_trades": 1 if bot.live_state["active"] else 0
            }
        else:
            status = {"status": "initializing"}
            
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# 2. TICK RADAR & DISCOVERY ENGINE
# ==============================================================================
class TickRadarBot:
    def __init__(self):
        # 1. Capital & Live Execution Rules
        self.leverage = 1                      # Starts at 1x; dynamically calculated for live
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        # 2. 10-Experiment Discovery & Qualification Gate
        self.experiments_completed = 0
        self.MAX_EXPERIMENTS = 10
        self.is_calibrated = False
        self.calibrated_tp = 3.50             # Default baseline; adjusted after 10 tests
        self.calibrated_sl = 1.50             # Default baseline; adjusted after 10 tests

        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # Universe: Low & Mid-Cap Crypto Perps ($600k to $10M Volume)
        self.MIN_24H_VOL_USD = 600_000.0
        self.MAX_24H_VOL_USD = 10_000_000.0
        self.EXCLUSION_LIST = {
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'AVAX', 
            'LINK', 'SUI', 'PEPE', 'SHIB', 'NEAR', 'LTC', 'BCH', 'DOT', 'ZEC',
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU',
            'SKHYNIX', 'SKHY', 'SNDK', 'SNXX', 'BABA', 'COIN', 'MSTR', 'ARM', 'INTC', 'SMSN'
        }

        # Memory Buffers
        self.active_experiments = []           # Dual Long & Short pairs running without SL/TP
        self.calibrated_paper_trades = []      # Paper trades running after calibration
        self.experiment_results = []           # Logged peak/trough metrics
        self.coin_cooldowns = {}
        self.load_brain()

        # Live Trade State
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "target_price": 0.0, "stop_price": 0.0,
            "trailed": False, "start_time": 0.0
        }

        # Bitget CCXT Initialization
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

    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.experiments_completed = data.get("experiments_completed", 0)
                    self.is_calibrated = data.get("is_calibrated", False)
                    self.calibrated_tp = data.get("calibrated_tp", 3.50)
                    self.calibrated_sl = data.get("calibrated_sl", 1.50)
                    self.experiment_results = data.get("experiment_results", [])
                    self.consecutive_paper_wins = data.get("consecutive_paper_wins", 0)
                    self.all_time_wins = data.get("all_time_wins", 0)
                    self.all_time_losses = data.get("all_time_losses", 0)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "experiments_completed": self.experiments_completed,
                    "is_calibrated": self.is_calibrated,
                    "calibrated_tp": self.calibrated_tp,
                    "calibrated_sl": self.calibrated_sl,
                    "experiment_results": self.experiment_results[-20:],
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses
                }, f, indent=2)
        except Exception:
            pass

    def is_qualified_for_live(self):
        return self.is_calibrated and (self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK)

    # --------------------------------------------------------------------------
    # 1. LIVE TAPE RADAR (TICKS, URGENCY & MOTIVES)
    # --------------------------------------------------------------------------
    def get_tape_radar(self, symbol):
        """Fetches public trades to capture live market taker flow and motives."""
        try:
            trades = self.bitget.fetch_trades(symbol, limit=60)
            if not trades or len(trades) < 15:
                return None

            now_ms = time.time() * 1000
            recent = [t for t in trades if (now_ms - t['timestamp']) <= 90_000]
            if len(recent) < 8:
                return None

            buy_vol = sum([float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) for t in recent if t.get('side') == 'buy'])
            sell_vol = sum([float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) for t in recent if t.get('side') == 'sell'])
            total = buy_vol + sell_vol

            if total <= 0:
                return None

            buy_pct = (buy_vol / total) * 100.0
            sell_pct = (sell_vol / total) * 100.0
            cur_p = recent[-1]['price']

            # Diagnose Sequences
            seq_code = "S0:CHOP"
            status_code = "BALANCED"

            # Sequence 1: Urgent Motive (Extreme Panic Dump or FOMO Hold)
            if buy_pct >= 85.0 and total >= 15_000:
                seq_code = "S1:FOMO_HOLD"
                status_code = "URGENT_BUY"
            elif sell_pct >= 85.0 and total >= 15_000:
                seq_code = "S1:PANIC_DUMP"
                status_code = "URGENT_SELL"

            # Sequence 2: Institutional Whale Push
            elif any(float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) >= 5_000 for t in recent):
                seq_code = "S2:WHALE_PUSH"
                status_code = "FILL_APPROACH"

            # Sequence 3: Underdog Blitz vs Sleeping Giant
            elif buy_pct >= 75.0 and total < 15_000:
                seq_code = "S3:BLITZ_RUN"
                status_code = "RUNNING"
            elif sell_pct >= 75.0 and total < 15_000:
                seq_code = "S3:BLITZ_BLEED"
                status_code = "RUNNING"

            return {
                "cur_price": cur_p,
                "buy_usd": buy_vol,
                "sell_usd": sell_vol,
                "buy_pct": buy_pct,
                "sell_pct": sell_pct,
                "seq_code": seq_code,
                "status_code": status_code
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 2. RUN SIMULTANEOUS LONG & SHORT EXPERIMENTS (NO SL / NO TP)
    # --------------------------------------------------------------------------
    def update_experiments(self):
        """Monitors simultaneous Long & Short pairs, logging second-by-second radar telemetry."""
        remaining = []
        now = time.time()

        for exp in self.active_experiments:
            sym = exp["symbol"]
            entry = exp["entry_p"]
            exp_id = exp["id"]
            elapsed_m = (now - exp["start_t"]) / 60.0

            tape = self.get_tape_radar(sym)
            if not tape:
                remaining.append(exp)
                continue

            cur_p = tape["cur_price"]
            long_move = ((cur_p - entry) / entry) * 100.0
            short_move = ((entry - cur_p) / entry) * 100.0

            # Record peaks and troughs
            exp["max_long_peak"] = max(exp["max_long_peak"], long_move)
            exp["max_short_peak"] = max(exp["max_short_peak"], short_move)

            # Determine live behavior flag
            status = tape["status_code"]
            if long_move >= exp["max_long_peak"] and long_move > 0.8:
                status = "PEAK_NEW"
            elif short_move >= exp["max_short_peak"] and short_move > 0.8:
                status = "PEAK_NEW"
            elif (tape["buy_usd"] > 20_000 and abs(long_move - exp.get("last_long", 0.0)) < 0.05):
                status = "WALL_HIT"
            elif (exp["max_long_peak"] >= 2.5 and (exp["max_long_peak"] - long_move) >= 1.0):
                status = "GIANT_REV"

            exp["last_long"] = long_move

            # Compact Single-Line Radar Output (Custom Built for Phone Screenshots)
            b_k = int(tape["buy_usd"] / 1000)
            s_k = int(tape["sell_usd"] / 1000)
            bias_str = f"{int(tape['buy_pct'])}%B" if tape['buy_pct'] >= tape['sell_pct'] else f"{int(tape['sell_pct'])}%S"
            t_str = time.strftime("%H:%M:%S", time.localtime(now))
            base_sym = sym.split('/')[0]

            print(
                f"[EXP#{exp_id} {t_str}] {base_sym:<6} | L:{long_move:+.2f}% S:{short_move:+.2f}% | "
                f"FLOW: B${b_k}k/S${s_k}k ({bias_str}) | {tape['seq_code']} | {status}",
                flush=True
            )

            # Experiment runs for 30 minutes unconstrained to map full expansion
            if elapsed_m >= 30.0:
                winning_peak = max(exp["max_long_peak"], exp["max_short_peak"])
                trough_floor = min(exp["max_long_peak"], exp["max_short_peak"])

                print(f"\n" + "🏁"*35, flush=True)
                print(f"🏁 [EXPERIMENT #{exp_id} CONCLUDED] {sym}", flush=True)
                print(f"Observed Winner Peak  : +{winning_peak:.2f}% Spot Expansion", flush=True)
                print(f"Observed Floor Trough : {trough_floor:.2f}% Adverse Drift", flush=True)
                print(f"Duration Logged       : 30.0 Minutes Clean Unconstrained Film", flush=True)
                print("🏁"*35 + "\n", flush=True)

                self.experiments_completed += 1
                self.experiment_results.append({
                    "id": exp_id,
                    "symbol": sym,
                    "winner_peak": winning_peak,
                    "trough_floor": trough_floor
                })

                # Once 10 experiments finish, calibrate exact mathematical TP and SL
                if self.experiments_completed >= self.MAX_EXPERIMENTS and not self.is_calibrated:
                    avg_peak = sum([r["winner_peak"] for r in self.experiment_results[-10:]]) / 10.0
                    avg_trough = abs(sum([r["trough_floor"] for r in self.experiment_results[-10:]]) / 10.0)

                    # Take-profit placed at 80% of average peak to ensure reliable fills
                    self.calibrated_tp = round(max(avg_peak * 0.80, 2.50), 2)
                    # Stop-loss set just beyond normal noise floor
                    self.calibrated_sl = round(max(avg_trough * 1.15, 1.20), 2)
                    self.is_calibrated = True

                    print(f"\n" + "🎯"*35, flush=True)
                    print(f"🎯 [DISCOVERY COMPLETE: MATHEMATICAL CALIBRATION SET!]", flush=True)
                    print(f"Ten experiments mapped successfully across all 3 sequences.", flush=True)
                    print(f"Calibrated Take-Profit : +{self.calibrated_tp:.2f}% Spot", flush=True)
                    print(f"Calibrated Stop-Loss    : -{self.calibrated_sl:.2f}% Spot", flush=True)
                    print(f"Action                  : Paper Qualifying (8-Streak) is now officially ACTIVE!", flush=True)
                    print("🎯"*35 + "\n", flush=True)

                self.save_brain()
            else:
                remaining.append(exp)

        self.active_experiments = remaining

    # --------------------------------------------------------------------------
    # 3. POST-CALIBRATION PAPER QUALIFYING (8-WIN STREAK HUNT)
    # --------------------------------------------------------------------------
    def update_calibrated_paper_trades(self):
        if not self.is_calibrated:
            return

        remaining = []
        now = time.time()

        for trade in self.calibrated_paper_trades:
            sym = trade["symbol"]
            side = trade["side"]
            entry = trade["entry_p"]
            elapsed_m = (now - trade["start_t"]) / 60.0

            try:
                cur_p = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
            except Exception:
                remaining.append(trade)
                continue

            if cur_p <= 0:
                remaining.append(trade)
                continue

            gain_spot = ((cur_p - entry) / entry) * 100.0 if side == "long" else ((entry - cur_p) / entry) * 100.0

            hit_tp = gain_spot >= self.calibrated_tp
            hit_sl = gain_spot <= -self.calibrated_sl
            timed_out = elapsed_m >= 60.0

            if hit_tp or hit_sl or timed_out:
                is_win = hit_tp or (timed_out and gain_spot >= 1.5)

                print(f"\n=======================================================", flush=True)
                if is_win:
                    self.all_time_wins += 1
                    self.consecutive_paper_wins += 1
                    self.coin_cooldowns[sym] = time.time() + 600
                    print(f"🟢 [QUALIFYING WIN: +{gain_spot:.2f}% SPOT]", flush=True)
                    print(f"Streak Progress: {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} in a row!", flush=True)
                    if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                        print(f"🎉 [8/8 STREAK UNLOCKED] Live 90% Account Trading AUTHORIZED!\n", flush=True)
                else:
                    self.all_time_losses += 1
                    self.consecutive_paper_wins = 0
                    self.coin_cooldowns[sym] = time.time() + 3600
                    print(f"🔴 [QUALIFYING STOP-OUT: {gain_spot:.2f}% SPOT]", flush=True)
                    print(f"Streak reset back to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)

                self.save_brain()
                print(f"=======================================================\n", flush=True)
            else:
                remaining.append(trade)

        self.calibrated_paper_trades = remaining

    # --------------------------------------------------------------------------
    # 4. LIVE TRADE CONTROLLER (90% BALANCE & DYNAMIC LEVERAGE)
    # --------------------------------------------------------------------------
    def poll_live_trade(self):
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        side = self.live_state["side"]
        entry = self.live_state["entry_price"]
        elapsed_m = (time.time() - self.live_state["start_time"]) / 60.0

        try:
            cur_p = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
        except Exception:
            return

        gain_spot = ((cur_p - entry) / entry) * 100.0 if side == "long" else ((entry - cur_p) / entry) * 100.0

        hit_tp = gain_spot >= self.calibrated_tp
        hit_sl = gain_spot <= -self.calibrated_sl
        timed_out = elapsed_m >= 60.0

        if hit_tp or hit_sl or timed_out:
            is_win = hit_tp or (timed_out and gain_spot >= 1.5)
            order_side = 'sell' if side == 'long' else 'buy'

            for _ in range(3):
                try:
                    self.bitget.create_order(
                        sym, 'market', order_side,
                        self.live_state["contracts"],
                        params={'reduceOnly': True}
                    )
                    break
                except Exception:
                    time.sleep(1)

            print(f"\n=======================================================", flush=True)
            if is_win:
                self.consecutive_live_losses = 0
                print(f"🟢 [LIVE TRADE HARVESTED: +{gain_spot:.2f}% SPOT]", flush=True)
            else:
                self.consecutive_live_losses += 1
                print(f"🔴 [LIVE TRADE STOPPED: {gain_spot:.2f}% SPOT]", flush=True)
                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] Streak reset back to qualifying mode.\n", flush=True)
                    self.consecutive_paper_wins = 0

            self.save_brain()
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # 5. SCANNER & SIMULTANEOUS ENTRY
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX 10-Phase Discovery & Tick Radar Bot online.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} swap pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                self.update_experiments()
                self.update_calibrated_paper_trades()
                self.poll_live_trade()

                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    time.sleep(20)
                    continue

                try:
                    tickers = self.bitget.fetch_tickers()
                except Exception:
                    time.sleep(3)
                    continue

                active_syms = {e["symbol"] for e in self.active_experiments} | {t["symbol"] for t in self.calibrated_paper_trades}

                # Candidates: Low & Mid-Cap Perps ($600k to $10M)
                candidates = []
                for s, t in tickers.items():
                    if not s.endswith(":USDT"):
                        continue
                    base = s.split('/')[0].split(':')[0].upper()
                    if base in self.EXCLUSION_LIST:
                        continue

                    vol = float(t.get('quoteVolume', 0) or 0)
                    if self.MIN_24H_VOL_USD <= vol <= self.MAX_24H_VOL_USD and s not in active_syms:
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)

                for sym, vol in candidates[:15]:
                    # Phase 1: Run simultaneous Long & Short discovery tests until 10 are done
                    if not self.is_calibrated and len(self.active_experiments) < 2:
                        tape = self.get_tape_radar(sym)
                        if tape and tape["seq_code"] != "S0:CHOP":
                            exp_id = self.experiments_completed + len(self.active_experiments) + 1
                            if exp_id <= self.MAX_EXPERIMENTS:
                                self.active_experiments.append({
                                    "id": exp_id,
                                    "symbol": sym,
                                    "entry_p": tape["cur_price"],
                                    "start_t": time.time(),
                                    "max_long_peak": 0.0,
                                    "max_short_peak": 0.0,
                                    "last_long": 0.0
                                })
                                print(f"\n🧪 [EXPERIMENT #{exp_id} LAUNCHED] {sym} | Simultaneous Long & Short running freely without SL/TP.", flush=True)
                                break

                    # Phase 2 & 3: Calibrated Trading (Paper Qualifying or Live)
                    elif self.is_calibrated:
                        tape = self.get_tape_radar(sym)
                        if not tape:
                            continue

                        # Trigger if Sequence 1, 2, or 3 is clearly dominant
                        trigger_long = tape["buy_pct"] >= 75.0 and tape["seq_code"] in ["S1:FOMO_HOLD", "S2:WHALE_PUSH", "S3:BLITZ_RUN"]
                        trigger_short = tape["sell_pct"] >= 75.0 and tape["seq_code"] in ["S1:PANIC_DUMP", "S2:WHALE_PUSH", "S3:BLITZ_BLEED"]

                        if trigger_long or trigger_short:
                            side = "long" if trigger_long else "short"
                            mid = tape["cur_price"]

                            if self.is_qualified_for_live() and not self.live_state["active"]:
                                # 90% Balance Rule & Dynamic Minimum Leverage Calculation
                                margin_90 = balance * 0.90
                                exchange_min_notional = 5.25
                                needed_leverage = max(int(exchange_min_notional / margin_90) + 1, 1)

                                try:
                                    self.bitget.set_leverage(needed_leverage, sym)
                                except Exception:
                                    pass

                                notional_size = margin_90 * needed_leverage
                                amount = float(self.bitget.amount_to_precision(sym, notional_size / mid))
                                order_side = 'buy' if side == 'long' else 'sell'
                                self.bitget.create_order(sym, 'market', order_side, amount)

                                self.live_state = {
                                    "active": True, "symbol": sym, "side": side,
                                    "contracts": amount, "entry_price": mid,
                                    "start_time": time.time()
                                }
                                print(f"\n[LIVE ORDER: 90% ALLOCATION] {sym} ({side.upper()}) | Leverage: {needed_leverage}x | Margin: ${margin_90:.2f}", flush=True)
                                break

                            elif len(self.calibrated_paper_trades) < 2 and sym not in [t["symbol"] for t in self.calibrated_paper_trades]:
                                self.calibrated_paper_trades.append({
                                    "symbol": sym,
                                    "side": side,
                                    "entry_p": mid,
                                    "start_t": time.time()
                                })
                                print(f"\n[CALIBRATED TRADE LOCKED] {sym} ({side.upper()}) | Hunting 8-Win Streak toward Live.", flush=True)

                if cycle % 10 == 0:
                    status_desc = "LIVE_AUTHORIZED" if self.is_qualified_for_live() else (f"QUALIFYING ({self.consecutive_paper_wins}/8)" if self.is_calibrated else f"DISCOVERY ({self.experiments_completed}/10)")
                    print(
                        f"[SYSTEM PULSE] Mode: {status_desc} | "
                        f"Active Exp: {len(self.active_experiments)} | "
                        f"Vault: ${balance:.2f} | Streak: {self.consecutive_paper_wins}/8",
                        flush=True
                    )

                cycle += 1
                time.sleep(3)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(4)

# ==============================================================================
# START BOT
# ==============================================================================
if __name__ == "__main__":
    bot = TickRadarBot()
    bot.run()

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
BRAIN_FILE = "experiment_knowledge_bank.json"

bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX Continuous Experimentation & Novel Discovery Lab",
                "known_move_archetypes": len(bot.recorded_discoveries),
                "novel_anomalies_recorded": len(bot.novel_phenomena),
                "active_surveillance_coins": len(bot.market_tape),
                "post_trade_autopsies_filming": len(bot.post_trade_cameras),
                "streak_status": f"{bot.consecutive_paper_wins}/{bot.REQUIRED_WIN_STREAK} Wins in a row",
                "mode": "LIVE_AUTHORIZED" if bot.is_qualified_for_live() else "PAPER_QUALIFYING",
                "all_time_record": f"{bot.all_time_wins} Wins / {bot.all_time_losses} Losses",
                "active_trades": len(bot.active_cameras),
                "live_active": bot.live_state["active"],
                "quarantined_coins": len(bot.coin_cooldowns)
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
# 2. CONTINUOUS SCIENTIFIC EXPERIMENTATION ENGINE
# ==============================================================================
class ExperimentationLabBot:
    def __init__(self):
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # GREAT MOVE DEFINITIONS
        self.MIN_GREAT_MOVE_PCT = 4.00
        self.QUARANTINE_DURATION_SEC = 3600

        # UNIVERSE: LOW-CAP & MID-CAP CRYPTO PERPS ONLY ($500k to $12M)
        self.MIN_24H_VOL_USD = 500_000.0
        self.MAX_24H_VOL_USD = 12_000_000.0

        # Strict Mega-Cap & Stock Exclusion
        self.EXCLUSION_LIST = {
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'AVAX', 
            'LINK', 'SUI', 'PEPE', 'SHIB', 'NEAR', 'LTC', 'BCH', 'DOT', 'ZEC',
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU',
            'SKHYNIX', 'SKHY', 'SNDK', 'SNXX', 'BABA', 'COIN', 'MSTR', 'ARM', 'INTC', 'SMSN'
        }

        # EXPERIMENT MEMORY & SURVEILLANCE
        self.market_tape = {}            # {symbol: [snapshots up to 2-3 hours]}
        self.recorded_discoveries = []   # Standard verified archetypes
        self.novel_phenomena = []        # Discovered completely new, unexpected move signatures
        self.active_cameras = []         # Active paper trades
        self.post_trade_cameras = []     # Continuous film after paper trade exit
        self.coin_cooldowns = {}
        self.load_brain()

        # LIVE TRADE STATE
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "target_price": 0.0, "stop_price": 0.0,
            "trailed": False, "start_time": 0.0
        }

        # BITGET CCXT INITIALIZATION
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
                    self.consecutive_paper_wins = data.get("consecutive_paper_wins", 0)
                    self.all_time_wins = data.get("all_time_wins", 0)
                    self.all_time_losses = data.get("all_time_losses", 0)
                    self.recorded_discoveries = data.get("recorded_discoveries", [])[-20:]
                    self.novel_phenomena = data.get("novel_phenomena", [])[-20:]
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses,
                    "recorded_discoveries": self.recorded_discoveries[-20:],
                    "novel_phenomena": self.novel_phenomena[-20:]
                }, f, indent=2)
        except Exception:
            pass

    def is_qualified_for_live(self):
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    def record_trade_outcome(self, is_win, symbol, net_roe):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            self.coin_cooldowns[symbol] = time.time() + 600
            print(f"\n🔥 [PAPER TRADE SUCCESS] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row! ROE: +{net_roe:.2f}%", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK UNLOCKED] Real capital trading is AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            self.coin_cooldowns[symbol] = time.time() + self.QUARANTINE_DURATION_SEC
            print(f"\n💥 [PAPER TRADE INCOMPLETE] Resetting streak from {self.consecutive_paper_wins} back to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"🚫 [QUARANTINE] {symbol} locked out for 60 minutes.", flush=True)
            self.consecutive_paper_wins = 0
        self.save_brain()

    def get_order_book_metrics(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=50)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0

            spread_pct = (best_ask - best_bid) / mid
            bid_usd = sum([p * q for p, q in bids if p >= mid * 0.985])
            ask_usd = sum([p * q for p, q in asks if p <= mid * 1.015])

            return {
                "mid": mid,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_pct": spread_pct,
                "bid_usd": bid_usd,
                "ask_usd": ask_usd
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 1. SCIENTIFIC DISCOVERY: RECORD EXPERIMENTAL PROFILES & NOVEL ANOMALIES
    # --------------------------------------------------------------------------
    def inspect_and_record_tape(self, symbol, current_mid):
        """
        Continuously screens the tape. If a coin makes a move of >= 4.0%
        without snapping back, it dissects the entire anatomy of the move.
        If it does not match known patterns, it catalogs it as a NOVEL DISCOVERY.
        """
        tape = self.market_tape.get(symbol, [])
        if len(tape) < 30:
            return

        now = time.time()
        # Look across 20 to 90 minutes of baseline snapshots
        past_frames = [f for f in tape if 1200.0 <= (now - f["t"]) <= 5400.0]
        if not past_frames:
            return

        baseline_frame = past_frames[0]
        price_gain_pct = ((current_mid - baseline_frame["price"]) / baseline_frame["price"]) * 100.0
        price_drop_pct = ((baseline_frame["price"] - current_mid) / baseline_frame["price"]) * 100.0

        # Filter out fast whipsaws/snaps: Must sustain direction over recent 8 minutes
        recent_frames = [f for f in tape if (now - f["t"]) <= 480.0]
        if len(recent_frames) < 4:
            return

        recent_low = min([f["price"] for f in recent_frames])
        recent_high = max([f["price"] for f in recent_frames])

        is_sustained_pump = price_gain_pct >= self.MIN_GREAT_MOVE_PCT and ((recent_high - current_mid) / recent_high) * 100.0 <= 1.2
        is_sustained_dump = price_drop_pct >= self.MIN_GREAT_MOVE_PCT and ((current_mid - recent_low) / recent_low) * 100.0 <= 1.2

        if is_sustained_pump or is_sustained_dump:
            move_type = "SUSTAINED_PUMP" if is_sustained_pump else "SUSTAINED_DUMP"
            move_magnitude = price_gain_pct if is_sustained_pump else price_drop_pct

            # Calculate the scientific metrics that accompanied the move
            initial_bid = baseline_frame["bid_usd"]
            initial_ask = baseline_frame["ask_usd"]
            gap_ratio = (initial_bid / initial_ask) if is_sustained_pump else (initial_ask / initial_bid)
            spread_profile = baseline_frame.get("spread_pct", 0.0)

            # Check if this behavior is novel (different characters from what we previously observed)
            is_novel = True
            for disc in self.recorded_discoveries:
                ratio_diff = abs(disc["initial_gap_ratio"] - gap_ratio)
                if disc["type"] == move_type and ratio_diff < 1.0:
                    is_novel = False
                    break

            experiment_profile = {
                "type": move_type,
                "symbol": symbol,
                "magnitude_pct": round(move_magnitude, 2),
                "initial_gap_ratio": round(gap_ratio, 2),
                "initial_bid_usd": round(initial_bid),
                "initial_ask_usd": round(initial_ask),
                "spread_profile": round(spread_profile, 5),
                "duration_min": round((now - baseline_frame["t"]) / 60.0, 1),
                "timestamp": now
            }

            # Avoid duplicate logs for the same move
            already_logged = any(d["symbol"] == symbol and (now - d["timestamp"]) < 1800 for d in (self.recorded_discoveries + self.novel_phenomena))
            if not already_logged:
                if is_novel:
                    self.novel_phenomena.append(experiment_profile)
                    print(f"\n" + "🧪"*35, flush=True)
                    print(f"🔬 [SCIENTIFIC EXPERIMENT: NOVEL PHENOMENON DISCOVERED!]", flush=True)
                    print(f"Coin               : {symbol} | Trend: {move_type} ({move_magnitude:+.2f}%)", flush=True)
                    print(f"Unique Character   : Moved greatly with previously UNSEEN order-book dynamics!", flush=True)
                    print(f"Observed Ratio     : {gap_ratio:.2f}x (Bids: ${initial_bid:,.0f} vs Asks: ${initial_ask:,.0f})", flush=True)
                    print(f"Spread Signature   : {spread_profile*100:.3f}%", flush=True)
                    print(f"Trend Duration     : Sustained cleanly for {experiment_profile['duration_min']} minutes without reversing.", flush=True)
                    print(f"Experiment Action  : Added to Novel Knowledge Bank. Bot will now recognize this new archetype.", flush=True)
                    print("🧪"*35 + "\n", flush=True)
                else:
                    self.recorded_discoveries.append(experiment_profile)
                    print(f"\n🎬 [KNOWN ARCHETYPE CONFIRMED] {symbol} replicated {move_type} ({move_magnitude:+.2f}%) with {gap_ratio:.2f}x ratio.", flush=True)

                self.save_brain()

    # --------------------------------------------------------------------------
    # 2. CONTINUOUS POST-TRADE AUTOPSY FILMING
    # --------------------------------------------------------------------------
    def record_post_trade_autopsies(self):
        """
        Films coins for 2 hours AFTER a paper trade exits to note every detail:
        Did it pump another 10%? Did it stall, reverse, or consolidate?
        """
        remaining = []
        now = time.time()

        for autopsy in self.post_trade_cameras:
            sym = autopsy["symbol"]
            side = autopsy["side"]
            exit_p = autopsy["exit_price"]
            exit_t = autopsy["exit_time"]
            entry_p = autopsy["entry_price"]
            post_duration_m = (now - exit_t) / 60.0

            try:
                cur_p = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
            except Exception:
                remaining.append(autopsy)
                continue

            if cur_p <= 0:
                remaining.append(autopsy)
                continue

            # Track total move since entry and post-exit drift
            post_drift_pct = ((cur_p - exit_p) / exit_p) * 100.0 if side == "long" else ((exit_p - cur_p) / exit_p) * 100.0
            total_life_pct = ((cur_p - entry_p) / entry_p) * 100.0 if side == "long" else ((entry_p - cur_p) / entry_p) * 100.0

            autopsy["max_drift"] = max(autopsy.get("max_drift", 0.0), post_drift_pct)
            autopsy["min_drift"] = min(autopsy.get("min_drift", 0.0), post_drift_pct)

            # Conclude post-trade film after 90 minutes
            if post_duration_m >= 90.0:
                print(f"\n" + "📼"*35, flush=True)
                print(f"📼 [POST-TRADE FILM CONCLUDED: 90-MINUTE AUTOPSY]", flush=True)
                print(f"Coin             : {sym} ({side.upper()})", flush=True)
                print(f"Trade Exit Price : {exit_p} -> Current Post Price: {cur_p}", flush=True)
                print(f"Post-Exit Drift  : {post_drift_pct:+.2f}% (Max: +{autopsy['max_drift']:.2f}% | Min: {autopsy['min_drift']:.2f}%)", flush=True)
                print(f"Total Expansion  : Moved {total_life_pct:+.2f}% from initial entry origin.", flush=True)
                if autopsy["max_drift"] >= 3.0:
                    print(f"Scientific Note  : Coin exhibited a strong SECOND LEG after exit! Target could be expanded further.", flush=True)
                elif autopsy["min_drift"] <= -2.5:
                    print(f"Scientific Note  : Coin REVERSED sharply after exit. Exit timing was optimal.", flush=True)
                else:
                    print(f"Scientific Note  : Coin CONSOLIDATED in a tight band without clean continuation.", flush=True)
                print("📼"*35 + "\n", flush=True)
            else:
                remaining.append(autopsy)

        self.post_trade_cameras = remaining

    # --------------------------------------------------------------------------
    # 3. AUDIT LIVE CANDIDATES AGAINST KNOWN & NOVEL ARCHETYPES
    # --------------------------------------------------------------------------
    def audit_candidate(self, symbol):
        base = symbol.split('/')[0].split(':')[0].upper()
        if base in self.EXCLUSION_LIST or time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        metrics = self.get_order_book_metrics(symbol)
        if not metrics:
            return None

        now = time.time()
        if symbol not in self.market_tape:
            self.market_tape[symbol] = []

        self.market_tape[symbol].append({
            "t": now,
            "bid_usd": metrics["bid_usd"],
            "ask_usd": metrics["ask_usd"],
            "spread_pct": metrics["spread_pct"],
            "price": metrics["mid"]
        })
        # Maintain 2 hours (7200 seconds) of film
        self.market_tape[symbol] = [f for f in self.market_tape[symbol] if now - f["t"] <= 7200.0]

        # Continuously monitor tape for novel and known discoveries
        self.inspect_and_record_tape(symbol, metrics["mid"])

        tape = self.market_tape[symbol]
        snaps = [f for f in tape if 300.0 <= (now - f["t"]) <= 900.0]
        if not snaps:
            return None

        baseline = snaps[0]
        mid = metrics["mid"]
        cur_bid = metrics["bid_usd"]
        cur_ask = metrics["ask_usd"]

        if cur_bid <= 0 or cur_ask <= 0:
            return None

        # Build dynamic knowledge base from both standard discoveries and novel phenomena
        all_discoveries = self.recorded_discoveries + self.novel_phenomena
        pump_ratios = [d["initial_gap_ratio"] for d in all_discoveries if d["type"] == "SUSTAINED_PUMP"]
        dump_ratios = [d["initial_gap_ratio"] for d in all_discoveries if d["type"] == "SUSTAINED_DUMP"]

        # Default minimum ratios if memory is still learning (no 10x requirement)
        min_pump_ratio = min(pump_ratios[-5:]) if pump_ratios else 3.2
        min_dump_ratio = min(dump_ratios[-5:]) if dump_ratios else 3.2

        # ======================================================================
        # SHORT EXPERIMENT: LIQUIDITY VOID DUMP
        # ======================================================================
        bid_drain = baseline["bid_usd"] / cur_bid
        ask_to_bid_ratio = cur_ask / cur_bid

        if bid_drain >= 2.8 and ask_to_bid_ratio >= min_dump_ratio:
            peak_p = max([f["price"] for f in tape[-15:]])
            slip_pct = ((peak_p - mid) / peak_p) * 100.0

            if 0.20 <= slip_pct <= 1.00:
                return {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "target_price": mid * (1.0 - (self.MIN_GREAT_MOVE_PCT / 100.0)),
                    "stop_price": peak_p * 1.008,
                    "reason": (
                        f"EXPERIMENT ENTERED: Bids drained {bid_drain:.1f}x (${baseline['bid_usd']:,.0f} -> ${cur_bid:,.0f}). "
                        f"Asks dominate {ask_to_bid_ratio:.1f}x (Learned Threshold: {min_dump_ratio:.1f}x). "
                        f"Price cracking -{slip_pct:.2f}% into void."
                    )
                }

        # ======================================================================
        # LONG EXPERIMENT: SUPPLY SQUEEZE PUMP
        # ======================================================================
        ask_drain = baseline["ask_usd"] / cur_ask
        bid_to_ask_ratio = cur_bid / cur_ask

        if ask_drain >= 2.8 and bid_to_ask_ratio >= min_pump_ratio:
            trough_p = min([f["price"] for f in tape[-15:]])
            lift_pct = ((mid - trough_p) / trough_p) * 100.0

            if 0.20 <= lift_pct <= 1.00:
                return {
                    "symbol": symbol,
                    "side": "long",
                    "mid": mid,
                    "target_price": mid * (1.0 + (self.MIN_GREAT_MOVE_PCT / 100.0)),
                    "stop_price": trough_p * 0.992,
                    "reason": (
                        f"EXPERIMENT ENTERED: Asks drained {ask_drain:.1f}x (${baseline['ask_usd']:,.0f} -> ${cur_ask:,.0f}). "
                        f"Bids dominate {bid_to_ask_ratio:.1f}x (Learned Threshold: {min_pump_ratio:.1f}x). "
                        f"Price lifting +{lift_pct:.2f}% through ceiling."
                    )
                }

        return None

    # --------------------------------------------------------------------------
    # 4. PAPER TRADING LAB & AUTOPSY HANDOFF
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

            try:
                cur_price = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
            except Exception:
                remaining.append(cam)
                continue

            if cur_price <= 0:
                remaining.append(cam)
                continue

            delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
            net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

            # Trailing stop to lock in profits once half-way to 4.0%
            if delta >= 2.0 and not cam["trailed"]:
                cam["trailed"] = True
                cam["stop_p"] = entry * 1.010 if side == "long" else entry * 0.990
                stop = cam["stop_p"]
                print(f"🔒 [LAB TRAILING LOCK] {sym} reached +{delta:.2f}%! Stop moved to +1.0% profit floor.", flush=True)

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= 45.0

            if hit_target or hit_stop or timed_out:
                is_win = hit_target or (timed_out and net_roe > 0)

                print(f"\n=======================================================", flush=True)
                if is_win:
                    print(f"🟢 [LAB RESULT: EXPERIMENT SUCCEEDED!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()}) | Spot Gain: {delta:+.2f}%", flush=True)
                    print(f"Net ROE    : +{net_roe:.2f}% ({self.leverage}x Leverage)", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes | Exit Price: {cur_price}", flush=True)
                else:
                    print(f"🔴 [LAB RESULT: EXPERIMENT INCOMPLETE / STOPPED]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()}) | Spot Gain: {delta:+.2f}%", flush=True)
                    print(f"Net ROE    : {net_roe:.2f}% ROE", flush=True)

                self.record_trade_outcome(is_win, sym, net_roe)
                print(f"Streak     : {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row!", flush=True)
                print(f"All-Time   : {self.all_time_wins} Wins / {self.all_time_losses} Losses", flush=True)
                print(f"=======================================================\n", flush=True)

                # HAND OFF TO POST-TRADE CONTINUOUS SURVEILLANCE CAMERA
                self.post_trade_cameras.append({
                    "symbol": sym,
                    "side": side,
                    "entry_price": entry,
                    "exit_price": cur_price,
                    "exit_time": now,
                    "max_drift": 0.0,
                    "min_drift": 0.0
                })
                print(f"📹 [POST-TRADE CAMERA ACTIVATED] Filming {sym} for 90 minutes post-exit to study continuation/reversal dynamics...", flush=True)
            else:
                remaining.append(cam)

        self.active_cameras = remaining

    # --------------------------------------------------------------------------
    # 5. LIVE TRADE CONTROLLER (UNLOCKED AT 8/8)
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

        try:
            cur_price = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
        except Exception:
            return

        delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        if delta >= 2.0 and not self.live_state["trailed"]:
            self.live_state["trailed"] = True
            self.live_state["stop_price"] = entry * 1.010 if side == "long" else entry * 0.990
            stop = self.live_state["stop_price"]

        hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
        hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
        timed_out = elapsed_m >= 45.0

        if hit_target or hit_stop or timed_out:
            is_win = hit_target or (timed_out and net_roe > 0)
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
                print(f"🟢 [LIVE TRADE PROFIT: +{net_roe:.2f}% ROE]", flush=True)
                print(f"Coin: {sym} ({side.upper()}) | Spot Gain: +{delta:.2f}%", flush=True)
            else:
                self.consecutive_live_losses += 1
                print(f"🔴 [LIVE TRADE LOSS: {net_roe:.2f}% ROE]", flush=True)
                print(f"Strikes: {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)
                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] Resetting streak back to paper qualification.\n", flush=True)
                    self.consecutive_paper_wins = 0

            self.record_trade_outcome(is_win, sym, net_roe)
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # 6. EXPERIMENT SCANNER LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX Continuous Experimentation & Discovery Bot online.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} swap pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                self.update_cameras()
                self.record_post_trade_autopsies()
                self.poll_live_trade()

                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    time.sleep(25)
                    continue

                notional = max(min(balance * 0.85 * self.leverage, 7.50), 5.15)

                try:
                    tickers = self.bitget.fetch_tickers()
                except Exception:
                    time.sleep(4)
                    continue

                active_syms = {c["symbol"] for c in self.active_cameras}

                # TARGET: ONLY LOW-CAP & MID-CAP CRYPTO PERPS ($500k to $12M)
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

                # Surveillance top 25 low/mid-caps
                for sym, vol in candidates[:25]:
                    if len(self.active_cameras) >= 3:
                        break

                    setup = self.audit_candidate(sym)
                    if setup:
                        side = setup["side"]
                        mid = setup["mid"]
                        target_p = setup["target_price"]
                        stop_p = setup["stop_price"]

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
                                "trailed": False, "start_time": time.time()
                            }
                            print(f"\n[LIVE 8/8 EXECUTION] {sym} ({side.upper()}) | {setup['reason']}", flush=True)
                            break
                        elif sym not in [c["symbol"] for c in self.active_cameras]:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "trailed": False, "start_t": time.time()
                            })
                            print(f"\n[EXPERIMENT LOCKED ON TAPE] {sym} ({side.upper()}) | {setup['reason']}", flush=True)

                if cycle % 6 == 0:
                    status = "LIVE_READY (8/8 Achieved)" if self.is_qualified_for_live() else f"HUNTING STREAK ({self.consecutive_paper_wins}/8 in a row)"
                    print(
                        f"[EXPERIMENT PULSE] Active Trades: {len(self.active_cameras)}/3 | "
                        f"Post-Trade Films: {len(self.post_trade_cameras)} | "
                        f"Known Archetypes: {len(self.recorded_discoveries)} | "
                        f"Novel Discoveries: {len(self.novel_phenomena)} | "
                        f"Streak: {self.consecutive_paper_wins}/8 | Status: {status}",
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
    bot = ExperimentationLabBot()
    bot.run()

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
BRAIN_FILE = "reversal_engine_memory.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        net_score = bot.total_wins - bot.total_losses
        status = {
            "engine": "APEX-V16 True Net-Score Reversal Ignition Engine",
            "net_score": f"{net_score}/10 (Wins: {bot.total_wins}, Losses: {bot.total_losses})",
            "mode": "DEMOTED_TO_PAPER (Needs +6 streak)" if bot.is_demoted else ("LIVE_READY" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Needs +9 Net)"),
            "active_reversals": len(bot.active_cameras),
            "live_trade_active": bot.live_state["active"]
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
# 2. REVERSAL IGNITION & TRUE NET-SCORE ENGINE
# ==============================================================================
class ReversalIgnitionBot:
    def __init__(self):
        # 1. Capital & Leverage
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2
        self.is_demoted = False

        # 2. True Net Score Tracker: Net = Wins - Losses
        self.total_wins = 0
        self.total_losses = 0
        self.demoted_streak = 0  # Counts clean wins after demotion (needs 6)

        # 3. Memory & Tracking
        self.active_cameras = []
        self.market_history = {}    # Tracks 10-15m depth and price history
        self.coin_cooldowns = {}    # Prevents instant re-entry on the same coin
        self.load_brain()

        # 4. Live Trade Tracker (Bound directly to self)
        self.live_state = {
            "active": False,
            "symbol": None,
            "side": None,
            "contracts": 0,
            "entry_price": 0.0,
            "target_price": 0.0,
            "stop_price": 0.0,
            "trailed": False,
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

    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    data = json.load(f)
                    self.total_wins = data.get("total_wins", 0)
                    self.total_losses = data.get("total_losses", 0)
                    self.is_demoted = data.get("is_demoted", False)
                    self.demoted_streak = data.get("demoted_streak", 0)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "total_wins": self.total_wins,
                    "total_losses": self.total_losses,
                    "is_demoted": self.is_demoted,
                    "demoted_streak": self.demoted_streak
                }, f, indent=2)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # TRUE NET SCORECARD MATH (WINS MINUS LOSSES)
    # --------------------------------------------------------------------------
    def is_qualified_for_live(self):
        if self.is_demoted:
            # Re-entry requires a clean 6/6 consecutive win streak
            return self.demoted_streak >= 6
        # Initial rule: Net score (Wins - Losses) must reach +9
        net_score = self.total_wins - self.total_losses
        return net_score >= 9

    def get_score_status(self):
        net_score = self.total_wins - self.total_losses
        if self.is_demoted:
            return f"DEMOTED: {self.demoted_streak}/6 streak needed"
        return f"Net Score: {net_score}/10 ({self.total_wins} Wins, {self.total_losses} Losses | Need +9 for Live)"

    def record_trade_outcome(self, is_win):
        if is_win:
            self.total_wins += 1
            if self.is_demoted:
                self.demoted_streak += 1
        else:
            self.total_losses += 1
            if self.is_demoted:
                self.demoted_streak = 0  # A loss resets the demotion streak to 0
        self.save_brain()

    def get_resting_depth(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            mid = (bids[0][0] + asks[0][0]) / 2.0
            bid_usd = sum([p * q for p, q in bids if p >= mid * 0.988])
            ask_usd = sum([p * q for p, q in asks if p <= mid * 1.012])

            return {
                "mid": mid,
                "bid_usd": bid_usd,
                "ask_usd": ask_usd
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # AUDIT THE "LIGHT-UP" REVERSAL IGNITION
    # --------------------------------------------------------------------------
    def audit_reversal_ignition(self, symbol, vol_24h):
        """
        1. Identifies coins that dumped hard over the last 10-15 minutes (bids crushed 4x to 10x).
        2. Detects the 'Light-Up': The dump stops, resting bids increase by 15%+ from the low,
           and price ticks up.
        3. Enters LONG to catch the massive V-bottom relief rally.
        (And reverse for exhausted pumps to enter SHORT).
        """
        if time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        now = time.time()
        depth = self.get_resting_depth(symbol)
        if not depth:
            return None

        if symbol not in self.market_history:
            self.market_history[symbol] = []

        self.market_history[symbol].append({
            "t": now,
            "vol_24h": vol_24h,
            "bid_usd": depth["bid_usd"],
            "ask_usd": depth["ask_usd"],
            "price": depth["mid"]
        })
        self.market_history[symbol] = [s for s in self.market_history[symbol] if now - s["t"] <= 900.0]

        history = self.market_history[symbol]
        past_snaps = [s for s in history if 300.0 <= (now - s["t"]) <= 720.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        delta_vol = vol_24h - baseline["vol_24h"]

        if delta_vol < 30_000:
            return None

        mid = depth["mid"]
        price_drop_10m = ((mid - baseline["price"]) / baseline["price"]) * 100.0

        # Find the lowest depth and lowest price seen during this lookback window
        min_bids_seen = min([s["bid_usd"] for s in history])
        trough_price_seen = min([s["price"] for s in history])

        # ----------------------------------------------------------------------
        # SETUP 1: CATCH THE BIG REVERSE (LONG)
        # Condition A: Coin dumped heavily (-1.2% to -4.5%) over the last 10m.
        # Condition B: The dump stalled (current price is higher than trough).
        # Condition C: The 'Light-Up' -> Bids increased by >= 15% from the floor!
        # ----------------------------------------------------------------------
        bids_recovering = (depth["bid_usd"] >= min_bids_seen * 1.15) if min_bids_seen > 0 else False
        price_sparking_up = (mid > trough_price_seen * 1.0012)

        if -4.50 <= price_drop_10m <= -1.20 and bids_recovering and price_sparking_up:
            recovery_pct = ((depth["bid_usd"] - min_bids_seen) / min_bids_seen) * 100.0
            return {
                "symbol": symbol,
                "side": "long",
                "mid": mid,
                "reason": (
                    f"V-BOTTOM REVERSAL: Dumped {price_drop_10m:.2f}% over {elapsed_min:.1f}m. "
                    f"Bids lit up +{recovery_pct:.1f}% from the floor (${min_bids_seen:,.0f} -> ${depth['bid_usd']:,.0f})! "
                    f"Entering LONG to catch the squeeze bounce."
                )
            }

        # ----------------------------------------------------------------------
        # SETUP 2: CATCH THE BLOW-OFF TOP REVERSE (SHORT)
        # Condition A: Coin pumped heavily (+1.5% to +5.0%) over 10m.
        # Condition B: Price stalled below peak.
        # Condition C: The 'Fade Light-Up' -> Asks increased by >= 15% to trap buyers.
        # ----------------------------------------------------------------------
        min_asks_seen = min([s["ask_usd"] for s in history])
        peak_price_seen = max([s["price"] for s in history])
        asks_recovering = (depth["ask_usd"] >= min_asks_seen * 1.15) if min_asks_seen > 0 else False
        price_sparking_down = (mid < peak_price_seen * 0.9988)

        if 1.50 <= price_drop_10m <= 5.00 and asks_recovering and price_sparking_down:
            return {
                "symbol": symbol,
                "side": "short",
                "mid": mid,
                "reason": (
                    f"TOP BLOW-OFF REVERSAL: Pumped +{price_drop_10m:.2f}% over {elapsed_min:.1f}m. "
                    f"Asks reloaded resistance! Entering SHORT to catch the dump reversal."
                )
            }

        return None

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION LAB (SUSTAINED 12-MINUTE HOLD TIME)
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
            delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
            net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

            # Trailing Stop: Once profit reaches +0.40% spot (+1.12% ROE), move stop to lock in +0.10% spot (+0.40% ROE)
            if delta >= 0.40 and not cam["trailed"]:
                cam["trailed"] = True
                cam["stop_p"] = entry * 1.0010 if side == "long" else entry * 0.9990
                stop = cam["stop_p"]

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= 12.0  # Gives 12 minutes for the big reversal to unfold

            if hit_target or hit_stop or timed_out:
                is_win = hit_target or (timed_out and net_roe > 0)
                self.record_trade_outcome(is_win)

                print(f"\n=======================================================", flush=True)
                if is_win:
                    print(f"🟢 [TRADE RESULT: YOU MADE PROFIT!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Profit : +{net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)
                else:
                    print(f"🔴 [TRADE RESULT: YOU LOST!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Loss   : {net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)

                # 5-minute cooldown on the coin to prevent instant re-entry
                self.coin_cooldowns[sym] = time.time() + 300
                print(f"Scorecard  : {self.get_score_status()}", flush=True)
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

        if delta >= 0.40 and not self.live_state["trailed"]:
            self.live_state["trailed"] = True
            self.live_state["stop_price"] = entry * 1.0010 if side == "long" else entry * 0.9990
            stop = self.live_state["stop_price"]

        hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
        hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
        timed_out = elapsed_m >= 12.0

        if hit_target or hit_stop or timed_out:
            is_win = hit_target or (timed_out and net_roe > 0)
            order_side = 'sell' if side == 'long' else 'buy'

            for _ in range(3):
                try:
                    self.bitget.create_order(
                        sym, 'market', order_side,
                        self.live_state["contracts"],
                        params={'reduceOnly': True, 'tradeSide': 'close'}
                    )
                    break
                except Exception:
                    time.sleep(1)

            print(f"\n=======================================================", flush=True)
            if is_win:
                self.consecutive_live_losses = 0
                print(f"🟢 [LIVE TRADE: YOU MADE PROFIT!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Profit: +{net_roe:.2f}% ROE", flush=True)
            else:
                self.consecutive_live_losses += 1
                self.coin_cooldowns[sym] = time.time() + 300
                print(f"🔴 [LIVE TRADE: YOU LOST!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Loss: {net_roe:.2f}% ROE", flush=True)
                print(f"Strikes    : {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)

                if self.consecutive_live_losses >= self.max_live_losses:
                    self.is_demoted = True
                    self.demoted_streak = 0
                    print(f"\n[DEMOTION ACTIVE] 2 consecutive live losses! Real money locked until 6/6 paper streak.\n", flush=True)

            self.save_brain()
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Reversal Ignition Engine active.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                self.update_cameras()
                self.poll_live_trade()

                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    print(f"[VAULT PAUSE] Balance ${balance:.2f} below floor. Sleeping...", flush=True)
                    time.sleep(30)
                    continue

                notional = max(min(balance * 0.85 * self.leverage, 7.50), 5.15)

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

                # Scan for Reversal Ignitions
                for sym in candidates[:25]:
                    if len(self.active_cameras) >= 4:
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    reversal = self.audit_reversal_ignition(sym, vol_24h)

                    if reversal:
                        side = reversal["side"]
                        mid = reversal["mid"]

                        # Target: +0.75% spot move = +2.52% Net ROE on 4x leverage
                        target_p = mid * 1.0075 if side == "long" else mid * 0.9925
                        stop_p = mid * 0.9940 if side == "long" else mid * 1.0060

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
                            print(f"\n[LIVE REVERSAL ORDER EXECUTED] {sym} ({side.upper()}) | {reversal['reason']}", flush=True)
                            break
                        elif sym not in [c["symbol"] for c in self.active_cameras]:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "trailed": False, "start_t": time.time()
                            })
                            print(f"\n[REVERSAL IGNITION LOCKED] {sym} ({side.upper()}) | {reversal['reason']}", flush=True)

                if cycle % 6 == 0:
                    status = "DEMOTED (Need 6/6)" if self.is_demoted else ("LIVE_READY" if self.is_qualified_for_live() else "QUALIFYING (Need +9 Net)")
                    print(
                        f"[STATUS PULSE] Active Trades: {len(self.active_cameras)}/4 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | "
                        f"Status: {status} | {self.get_score_status()}",
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
    bot = ReversalIgnitionBot()
    bot.run()

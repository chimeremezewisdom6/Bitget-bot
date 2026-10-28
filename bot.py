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
BRAIN_FILE = "top3_market_memory.json"

class HealthCheckServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        wins = sum(bot.history_records)
        total = len(bot.history_records)
        losses = total - wins
        status = {
            "engine": "APEX-V16 Top-3 Global Leaderboard Engine",
            "mode": "DEMOTED (Needs 6/6)" if bot.is_demoted else ("LIVE_READY" if bot.is_qualified_for_live() else "PAPER (Needs 9/10)"),
            "record": f"{wins} WINS / {losses} LOSSES",
            "active_trades": len(bot.active_cameras),
            "top_3_leaderboard": bot.current_top_3
        }
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# 2. TOP-3 GLOBAL RANKING & SUSTAINED VACUUM ENGINE
# ==============================================================================
class TopThreeVacuumBot:
    def __init__(self):
        # 1. Capital & Risk Protection
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2
        self.is_demoted = False

        # 2. Minimum Capital Filters (No More $7,000 EVAA Micro-Dust)
        self.MIN_RESTING_BOOK_USD = 25_000.0  # Real institutional depth required
        self.MIN_5M_VOLUME_USD = 40_000.0     # Must have active multi-thousand volume
        
        # 3. Memory & Tracking
        self.history_records = []
        self.active_cameras = []
        self.market_memory = {}
        self.coin_cooldowns = {}
        self.current_top_3 = []
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
            "start_time": 0.0
        }

        # 5. Exchange Setup
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
                    self.history_records = data.get("history_records", [])
                    self.is_demoted = data.get("is_demoted", False)
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "history_records": self.history_records,
                    "is_demoted": self.is_demoted
                }, f, indent=2)
        except Exception:
            pass

    def is_qualified_for_live(self):
        if self.is_demoted:
            # Requires clean 6/6 consecutive paper wins to re-enter live
            return len(self.history_records) >= 6 and sum(self.history_records[-6:]) == 6
        # Standard: 9 out of last 10 wins (9/10)
        return len(self.history_records) >= 10 and sum(self.history_records[-10:]) >= 9

    def get_resting_depth(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            mid = (bids[0][0] + asks[0][0]) / 2.0
            ask_usd = sum([p * q for p, q in asks if p <= mid * 1.012])
            bid_usd = sum([p * q for p, q in bids if p >= mid * 0.988])

            return {
                "mid": mid,
                "ask_usd": ask_usd,
                "bid_usd": bid_usd
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # GLOBAL MARKET SCANNER: CALCULATE METRICS FOR EVERY COIN
    # --------------------------------------------------------------------------
    def evaluate_coin_metrics(self, symbol, vol_24h):
        if time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        now = time.time()
        depth = self.get_resting_depth(symbol)
        if not depth:
            return None

        # FILTER 1: Ban micro-dust books. Both sides must have real depth.
        if depth["ask_usd"] < self.MIN_RESTING_BOOK_USD or depth["bid_usd"] < self.MIN_RESTING_BOOK_USD:
            return None

        if symbol not in self.market_memory:
            self.market_memory[symbol] = []

        self.market_memory[symbol].append({
            "t": now,
            "vol_24h": vol_24h,
            "ask_usd": depth["ask_usd"],
            "bid_usd": depth["bid_usd"],
            "price": depth["mid"]
        })
        self.market_memory[symbol] = [s for s in self.market_memory[symbol] if now - s["t"] <= 600.0]

        history = self.market_memory[symbol]
        # Lookback 3 to 6 minutes
        past_snaps = [s for s in history if 180.0 <= (now - s["t"]) <= 360.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        delta_vol_5m = vol_24h - baseline["vol_24h"]
        if delta_vol_5m < self.MIN_5M_VOLUME_USD:
            return None

        mid = depth["mid"]

        # Long Evaluation: Resistance (Asks) fading while volume is surging
        ask_depletion = baseline["ask_usd"] / depth["ask_usd"] if depth["ask_usd"] > 0 else 1.0
        velocity_long = delta_vol_5m / depth["ask_usd"] if depth["ask_usd"] > 0 else 0
        price_change_long = ((mid - baseline["price"]) / baseline["price"]) * 100.0

        # Short Evaluation: Support (Bids) fading while volume is surging
        bid_depletion = baseline["bid_usd"] / depth["bid_usd"] if depth["bid_usd"] > 0 else 1.0
        velocity_short = delta_vol_5m / depth["bid_usd"] if depth["bid_usd"] > 0 else 0
        price_change_short = ((baseline["price"] - mid) / baseline["price"]) * 100.0

        best_setup = None

        # LONG CHECK: Early move (+0.10% to +0.45%), resistance fading >= 2.0x, velocity >= 15x
        if ask_depletion >= 2.0 and velocity_long >= 15.0 and (0.10 <= price_change_long <= 0.45):
            score_long = (ask_depletion * 30.0) + (velocity_long * 0.4) + (price_change_long * 20.0)
            best_setup = {
                "symbol": symbol,
                "side": "long",
                "mid": mid,
                "score": round(score_long, 2),
                "depletion": round(ask_depletion, 1),
                "velocity": round(velocity_long, 0),
                "price_change": round(price_change_long, 2),
                "depth_now": depth["ask_usd"],
                "depth_before": baseline["ask_usd"],
                "vol_5m": delta_vol_5m
            }

        # SHORT CHECK: Early move (-0.10% to -0.45%), support fading >= 2.0x, velocity >= 15x
        if bid_depletion >= 2.0 and velocity_short >= 15.0 and (0.10 <= price_change_short <= 0.45):
            score_short = (bid_depletion * 30.0) + (velocity_short * 0.4) + (price_change_short * 20.0)
            if not best_setup or score_short > best_setup["score"]:
                best_setup = {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "score": round(score_short, 2),
                    "depletion": round(bid_depletion, 1),
                    "velocity": round(velocity_short, 0),
                    "price_change": round(-price_change_short, 2),
                    "depth_now": depth["bid_usd"],
                    "depth_before": baseline["bid_usd"],
                    "vol_5m": delta_vol_5m
                }

        return best_setup

    # --------------------------------------------------------------------------
    # PICK THE TOP 3 MARKETS ACROSS ALL CANDIDATES
    # --------------------------------------------------------------------------
    def get_top_3_markets(self, candidates, tickers):
        evaluated = []
        for sym in candidates:
            vol_24h = float(tickers.get(sym, {}).get('quoteVolume', 0) or 0)
            result = self.evaluate_coin_metrics(sym, vol_24h)
            if result:
                evaluated.append(result)

        # Sort all valid candidates by total Market Strength Score
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        self.current_top_3 = evaluated[:3]
        return self.current_top_3

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION LAB (EXPLICIT PROFIT / LOSS)
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

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= 10.0  # Gives 10 full minutes to let sustained moves play out

            if hit_target or hit_stop or timed_out:
                is_profit = hit_target or (timed_out and net_roe > 0)
                self.history_records.append(1 if is_profit else 0)
                self.history_records = self.history_records[-15:]
                self.save_brain()

                wins = sum(self.history_records)
                total = len(self.history_records)
                losses = total - wins

                print(f"\n=======================================================", flush=True)
                if is_profit:
                    print(f"🟢 [TRADE RESULT: YOU MADE PROFIT!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Profit : +{net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)
                else:
                    print(f"🔴 [TRADE RESULT: YOU LOST!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Loss   : {net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)
                    self.coin_cooldowns[sym] = time.time() + 600
                    print(f"Action     : Put {sym} on 10-minute timeout (No Revenge Trading)", flush=True)

                status = "DEMOTED (Need 6/6 streak)" if self.is_demoted else f"{wins}/10 (Need 9/10 for Live)"
                print(f"Scorecard  : {wins} Wins / {losses} Losses | Status: {status}", flush=True)
                print(f"=======================================================\n", flush=True)
            else:
                remaining.append(cam)

        self.active_cameras = remaining

    # --------------------------------------------------------------------------
    # MONITOR LIVE TRADE GUARDIAN
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

        hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
        hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
        timed_out = elapsed_m >= 10.0

        if hit_target or hit_stop or timed_out:
            is_profit = hit_target or (timed_out and net_roe > 0)
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
            if is_profit:
                self.consecutive_live_losses = 0
                print(f"🟢 [LIVE TRADE: YOU MADE PROFIT!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Profit: +{net_roe:.2f}% ROE", flush=True)
            else:
                self.consecutive_live_losses += 1
                self.coin_cooldowns[sym] = time.time() + 600
                print(f"🔴 [LIVE TRADE: YOU LOST!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Loss: {net_roe:.2f}% ROE", flush=True)
                print(f"Strikes    : {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)

                if self.consecutive_live_losses >= self.max_live_losses:
                    self.is_demoted = True
                    print(f"\n[DEMOTED TO PAPER] 2 consecutive live losses! Must score 6/6 in paper to re-enter.\n", flush=True)

            self.save_brain()
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Top-3 Global Leaderboard Engine active.", flush=True)

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

                # --------------------------------------------------------------
                # SCAN THE ENTIRE MARKET AND EXTRACT THE ABSOLUTE TOP 3
                # --------------------------------------------------------------
                top_3_movers = self.get_top_3_markets(candidates, tickers)

                # Print Leaderboard on Cycle Heartbeat
                if cycle % 6 == 0 and top_3_movers:
                    print("\n--- [TOP 3 GLOBAL LEADERBOARD] ---", flush=True)
                    for idx, coin in enumerate(top_3_movers, 1):
                        print(f" #{idx}: {coin['symbol']} ({coin['side'].upper()}) | Score: {coin['score']} | Vol 5m: ${coin['vol_5m']:,.0f} | Move: {coin['price_change']:+.2f}% | Depth: ${coin['depth_now']:,.0f}", flush=True)
                    print("----------------------------------\n", flush=True)

                # Enter ONLY from the verified Top 3
                for best in top_3_movers:
                    if len(self.active_cameras) >= 3:  # Focus on maximum 3 quality trades at a time
                        break

                    sym = best["symbol"]
                    side = best["side"]
                    mid = best["mid"]

                    target_p = mid * 1.0050 if side == "long" else mid * 0.9950
                    stop_p = mid * 0.9965 if side == "long" else mid * 1.0035

                    # Qualification Check (9/10 initial or 6/6 re-entry)
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
                            "start_time": time.time()
                        }
                        print(f"\n[LIVE ORDER ENTERED] {sym} ({side.upper()}) Ranked #{top_3_movers.index(best)+1} Globally!", flush=True)
                        break
                    elif sym not in [c["symbol"] for c in self.active_cameras]:
                        self.active_cameras.append({
                            "symbol": sym, "side": side, "entry_p": mid,
                            "target_p": target_p, "stop_p": stop_p,
                            "start_t": time.time()
                        })
                        print(f"[QUALITY CAMERA LOCKED] {sym} ({side.upper()}) | Ranked #{top_3_movers.index(best)+1} Globally (Score: {best['score']})", flush=True)

                if cycle % 6 == 0:
                    wins = sum(self.history_records)
                    losses = len(self.history_records) - wins
                    status = "DEMOTED (Need 6/6)" if self.is_demoted else ("LIVE_READY" if self.is_qualified_for_live() else f"{wins}/10 (Need 9/10)")
                    print(
                        f"[STATUS PULSE] Open Quality Trades: {len(self.active_cameras)}/3 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | "
                        f"Status: {status} | Total: {wins} WINS / {losses} LOSSES",
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
    bot = TopThreeVacuumBot()
    bot.run()

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
BRAIN_FILE = "pre_dump_intelligence_memory.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "engine": "APEX-V16 Pre-Dump Distribution & Microstructure Engine",
            "streak_status": f"{bot.consecutive_paper_wins}/8 Wins in a row",
            "mode": "LIVE_AUTHORIZED (8/8 Streak Achieved)" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Hunting 8/8 Streak)",
            "all_time_record": f"{bot.all_time_wins} Wins / {bot.all_time_losses} Losses",
            "active_trades": len(bot.active_cameras),
            "live_active": bot.live_state["active"],
            "quarantined_coins": len(bot.coin_cooldowns)
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
# 2. PRE-DUMP DISTRIBUTION & MICROSTRUCTURE ENGINE
# ==============================================================================
class PreDumpHunterBot:
    def __init__(self):
        # 1. Capital, Leverage & Risk Vault
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        # 2. Strict 8-Win Streak Controller
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # 3. Market Quality Filters
        self.MAX_ALLOWED_SPREAD_PCT = 0.0012   # Maximum 0.12% spread allowed
        self.MIN_RESTING_DEPTH_USD = 20_000.0  # Real institutional order books
        self.QUARANTINE_DURATION_SEC = 3600    # 1-Hour ban on any coin that stops out

        # Non-Crypto Blacklist
        self.BLACKLIST = {
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU'
        }

        # 4. Memory & Tracking
        self.active_cameras = []
        self.market_history = {}    # Tracks depth & price evolution over 15-30m
        self.coin_cooldowns = {}
        self.load_brain()

        # 5. Live Trade Tracker (Bound directly to self)
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

        # 6. Bitget Exchange Connection
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
            except Exception:
                pass

    def save_brain(self):
        try:
            with open(BRAIN_FILE, "w") as f:
                json.dump({
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses
                }, f, indent=2)
        except Exception:
            pass

    def is_qualified_for_live(self):
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    def record_trade_outcome(self, is_win, symbol):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            self.coin_cooldowns[symbol] = time.time() + 600
            print(f"\n🔥 [STREAK PROGRESS] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row!", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK UNLOCKED] Real capital trading is now AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            self.coin_cooldowns[symbol] = time.time() + self.QUARANTINE_DURATION_SEC
            print(f"\n💥 [STREAK BROKEN] Lost trade! Resetting streak from {self.consecutive_paper_wins} back to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"🚫 [QUARANTINE] {symbol} locked out for 60 minutes.", flush=True)
            self.consecutive_paper_wins = 0
        self.save_brain()

    def get_order_book_metrics(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0

            spread_pct = (best_ask - best_bid) / mid
            if spread_pct > self.MAX_ALLOWED_SPREAD_PCT:
                return None

            bid_usd = sum([p * q for p, q in bids if p >= mid * 0.988])
            ask_usd = sum([p * q for p, q in asks if p <= mid * 1.012])

            if bid_usd < self.MIN_RESTING_DEPTH_USD or ask_usd < self.MIN_RESTING_DEPTH_USD:
                return None

            return {
                "mid": mid,
                "spread_pct": spread_pct,
                "bid_usd": bid_usd,
                "ask_usd": ask_usd
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # AUDIT PRE-DUMP DISTRIBUTION (BEFORE THE DUMP BEGINS)
    # --------------------------------------------------------------------------
    def audit_pre_dump_behavior(self, symbol, vol_24h):
        base = symbol.split('/')[0].split(':')[0].upper()
        if base in self.BLACKLIST or time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        now = time.time()
        metrics = self.get_order_book_metrics(symbol)
        if not metrics:
            return None

        if symbol not in self.market_history:
            self.market_history[symbol] = []

        self.market_history[symbol].append({
            "t": now,
            "vol_24h": vol_24h,
            "bid_usd": metrics["bid_usd"],
            "ask_usd": metrics["ask_usd"],
            "price": metrics["mid"]
        })
        self.market_history[symbol] = [s for s in self.market_history[symbol] if now - s["t"] <= 1500.0]

        history = self.market_history[symbol]
        # Look back 5 to 12 minutes
        past_snaps = [s for s in history if 300.0 <= (now - s["t"]) <= 720.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        delta_vol = vol_24h - baseline["vol_24h"]

        # Must have active volume turnover
        if delta_vol < 35_000:
            return None

        mid = metrics["mid"]

        # Track extremes over the window
        peak_price = max([s["price"] for s in history])
        max_bids_seen = max([s["bid_usd"] for s in history])
        baseline_asks = baseline["ask_usd"]

        # ======================================================================
        # THE PRE-DUMP SIGNATURE (SHORT BEFORE THE DROP)
        # ======================================================================
        # 1. Bids have hollowed out by at least 2.5x to 5x+ from the baseline
        # 2. Asks overhead have expanded (sellers stacking walls)
        # 3. Price is still near its highs (within 0.35% of peak) but struggling
        # 4. The Crack: Price just broke down by -0.15% to -0.35% off the peak
        bid_hollowing_factor = max_bids_seen / metrics["bid_usd"] if metrics["bid_usd"] > 0 else 1.0
        ask_stacking_factor = metrics["ask_usd"] / baseline_asks if baseline_asks > 0 else 1.0
        slip_from_peak_pct = ((peak_price - mid) / peak_price) * 100.0

        if (bid_hollowing_factor >= 2.5 and ask_stacking_factor >= 1.3 and 
            0.15 <= slip_from_peak_pct <= 0.40):

            # Invalidation: Stop sits safely right above the distribution peak
            stop_price = peak_price * 1.0020
            # Target: Down into the hollow void below
            target_price = mid * 0.9930

            return {
                "symbol": symbol,
                "side": "short",
                "mid": mid,
                "target_price": target_price,
                "stop_price": stop_price,
                "reason": (
                    f"PRE-DUMP CAUGHT: Bids hollowed out {bid_hollowing_factor:.1f}x (${max_bids_seen:,.0f} -> ${metrics['bid_usd']:,.0f}) "
                    f"while Asks stacked {ask_stacking_factor:.1f}x with ${delta_vol:,.0f} churn! "
                    f"Price cracked -{slip_from_peak_pct:.2f}% off peak. Floor is gone, entering SHORT before freefall!"
                )
            }

        # ======================================================================
        # MIRROR: PRE-PUMP ACCUMULATION (LONG BEFORE THE SURGE)
        # ======================================================================
        trough_price = min([s["price"] for s in history])
        max_asks_seen = max([s["ask_usd"] for s in history])
        baseline_bids = baseline["bid_usd"]

        ask_hollowing_factor = max_asks_seen / metrics["ask_usd"] if metrics["ask_usd"] > 0 else 1.0
        bid_stacking_factor = metrics["bid_usd"] / baseline_bids if baseline_bids > 0 else 1.0
        rise_from_trough_pct = ((mid - trough_price) / trough_price) * 100.0

        if (ask_hollowing_factor >= 2.5 and bid_stacking_factor >= 1.3 and 
            0.15 <= rise_from_trough_pct <= 0.40):

            stop_price = trough_price * 0.9980
            target_price = mid * 1.0070

            return {
                "symbol": symbol,
                "side": "long",
                "mid": mid,
                "target_price": target_price,
                "stop_price": stop_price,
                "reason": (
                    f"PRE-PUMP CAUGHT: Asks hollowed out {ask_hollowing_factor:.1f}x (${max_asks_seen:,.0f} -> ${metrics['ask_usd']:,.0f}) "
                    f"while Bids stacked {bid_stacking_factor:.1f}x with ${delta_vol:,.0f} churn! "
                    f"Price lifted +{rise_from_trough_pct:.2f}% off floor. Ceiling is gone, entering LONG before breakout!"
                )
            }

        return None

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION LAB
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

            # Trailing stop: If trade reaches +0.35% spot, lock in +0.10% profit floor
            if delta >= 0.35 and not cam["trailed"]:
                cam["trailed"] = True
                cam["stop_p"] = entry * 1.0010 if side == "long" else entry * 0.9990
                stop = cam["stop_p"]

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= 15.0

            if hit_target or hit_stop or timed_out:
                is_win = hit_target or (timed_out and net_roe > 0)

                print(f"\n=======================================================", flush=True)
                if is_win:
                    print(f"🟢 [TRADE RESULT: YOU MADE PROFIT!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Profit : +{net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)
                    print(f"Exit Price : {cur_price} (Entry: {entry})", flush=True)
                else:
                    print(f"🔴 [TRADE RESULT: YOU LOST!]", flush=True)
                    print(f"Coin       : {sym} ({side.upper()})", flush=True)
                    print(f"Net Loss   : {net_roe:.2f}% ROE", flush=True)
                    print(f"Duration   : {elapsed_m:.1f} minutes", flush=True)
                    print(f"Exit Price : {cur_price} (Entry: {entry})", flush=True)

                self.record_trade_outcome(is_win, sym)
                print(f"Streak     : {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row!", flush=True)
                print(f"All-Time   : {self.all_time_wins} Wins / {self.all_time_losses} Losses", flush=True)
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

        try:
            cur_price = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
        except Exception:
            return

        delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        if delta >= 0.35 and not self.live_state["trailed"]:
            self.live_state["trailed"] = True
            self.live_state["stop_price"] = entry * 1.0010 if side == "long" else entry * 0.9990
            stop = self.live_state["stop_price"]

        hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
        hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
        timed_out = elapsed_m >= 15.0

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
                print(f"🔴 [LIVE TRADE: YOU LOST!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Loss: {net_roe:.2f}% ROE", flush=True)
                print(f"Strikes    : {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)

                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] 2 consecutive live losses! Must score 8/8 in paper to re-enter.\n", flush=True)
                    self.consecutive_paper_wins = 0

            self.record_trade_outcome(is_win, sym)
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Pre-Dump Intelligence Bot online.", flush=True)

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

                # Scan for Pre-Dump Behavior
                for sym in candidates[:25]:
                    if len(self.active_cameras) >= 3:
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    setup = self.audit_pre_dump_behavior(sym, vol_24h)

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
                            print(f"\n[LIVE 8/8 ORDER ENTERED] {sym} ({side.upper()}) | {setup['reason']}", flush=True)
                            break
                        elif sym not in [c["symbol"] for c in self.active_cameras]:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "trailed": False, "start_t": time.time()
                            })
                            print(f"\n[PRE-DUMP LOCKED] {sym} ({side.upper()}) | {setup['reason']}", flush=True)

                if cycle % 6 == 0:
                    status = "LIVE_READY (8/8 Achieved)" if self.is_qualified_for_live() else f"HUNTING STREAK ({self.consecutive_paper_wins}/8 in a row)"
                    print(
                        f"[STATUS PULSE] Active: {len(self.active_cameras)}/3 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | "
                        f"Streak: {self.consecutive_paper_wins}/8 IN A ROW | Status: {status}",
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
    bot = PreDumpHunterBot()
    bot.run()

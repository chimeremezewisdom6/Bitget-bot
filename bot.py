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
BRAIN_FILE = "steamroller_reversal_memory.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "engine": "APEX-V16 Steamroller & 10x Reversal Engine",
            "streak_status": f"{bot.consecutive_paper_wins}/8 Wins in a row",
            "mode": "LIVE_AUTHORIZED (8/8 Streak Achieved)" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Hunting 8/8 Streak)",
            "all_time_record": f"{bot.all_time_wins} Wins / {bot.all_time_losses} Losses",
            "active_trades": len(bot.active_cameras),
            "live_active": bot.live_state["active"]
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
# 2. THE STEAMROLLER & 10X REVERSAL ENGINE
# ==============================================================================
class SteamrollerReversalBot:
    def __init__(self):
        # 1. Capital & Risk Vault
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        # 2. Strict 8-in-a-Row Streak Controller
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # 3. Memory & Tracking
        self.active_cameras = []
        self.market_history = {}    # Tracks 10-25m volume and depth flow
        self.coin_cooldowns = {}    # 5-minute cooldown to prevent instant re-entry
        self.load_brain()

        # 4. Live Trade Tracker (Bound to self)
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
        # Strict Rule: Must achieve 8 consecutive wins in a row without a loss
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    def record_trade_outcome(self, is_win):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            print(f"\n🔥 [STREAK PROGRESS] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row!", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK ACHIEVED] Real capital trading is now AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            print(f"\n💥 [STREAK BROKEN] Lost trade! Resetting streak from {self.consecutive_paper_wins} back to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            self.consecutive_paper_wins = 0  # Resets completely back to Game 1
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
    # AUDIT STEAMROLLER WAVES & 10X REVERSAL IGNITIONS
    # --------------------------------------------------------------------------
    def evaluate_market_setups(self, symbol, vol_24h):
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
        self.market_history[symbol] = [s for s in self.market_history[symbol] if now - s["t"] <= 1200.0]

        history = self.market_history[symbol]
        # Look back across 8 to 15 minutes
        past_snaps = [s for s in history if 480.0 <= (now - s["t"]) <= 900.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        delta_vol = vol_24h - baseline["vol_24h"]

        # Filter out dead illiquid coins (must have at least $40k fresh volume)
        if delta_vol < 40_000:
            return None

        mid = depth["mid"]
        price_change_pct = ((mid - baseline["price"]) / baseline["price"]) * 100.0

        # Lowest and highest points recorded during the window
        min_bids_seen = min([s["bid_usd"] for s in history])
        max_bids_seen = max([s["bid_usd"] for s in history])
        trough_price = min([s["price"] for s in history])

        min_asks_seen = min([s["ask_usd"] for s in history])
        max_asks_seen = max([s["ask_usd"] for s in history])
        peak_price = max([s["price"] for s in history])

        # ======================================================================
        # SETUP A: THE 10X CRASH + 15% REVERSAL IGNITION (CATCH THE BIG REVERSE)
        # ======================================================================
        # 1. Bids collapsed by 5x to 10x+ (e.g. $1M down to $100k or less)
        # 2. Price stopped crashing (mid > trough)
        # 3. New USDT entered: Bids expanded >= 15% from the lowest point!
        bid_crash_factor = max_bids_seen / min_bids_seen if min_bids_seen > 0 else 1.0
        bids_re_expanding = (depth["bid_usd"] >= min_bids_seen * 1.15) if min_bids_seen > 0 else False
        price_sparking_up = (mid > trough_price * 1.0015)

        if bid_crash_factor >= 5.0 and bids_re_expanding and price_sparking_up and (-6.0 <= price_change_pct <= -1.2):
            recovery_pct = ((depth["bid_usd"] - min_bids_seen) / min_bids_seen) * 100.0
            return {
                "symbol": symbol,
                "side": "long",
                "mid": mid,
                "hold_minutes": 15.0,
                "reason": (
                    f"10x CRASH + 15% IGNITION: Bids collapsed {bid_crash_factor:.1f}x during dump, "
                    f"then fresh USDT lit up +{recovery_pct:.1f}% from the floor (${min_bids_seen:,.0f} -> ${depth['bid_usd']:,.0f})! "
                    f"Entering LONG for the Big Reversal."
                )
            }

        # ======================================================================
        # SETUP B: THE STEAMROLLER AVALANCHE (RELENTLESS SELL CONTINUATION)
        # ======================================================================
        # Enormous selling dollars where new buyer USDT cannot recover it.
        # Dump is persistent (-1.0% to -3.0%) over 10m with relentless volume.
        if -3.00 <= price_change_pct <= -1.00 and delta_vol >= 80_000:
            return {
                "symbol": symbol,
                "side": "short",
                "mid": mid,
                "hold_minutes": 15.0,
                "reason": (
                    f"STEAMROLLER SHORT: Relentless selling (${delta_vol:,.0f} volume churned in {elapsed_min:.1f}m). "
                    f"Price down {price_change_pct:.2f}%. New buyer USDT cannot recover it; cascade will continue."
                )
            }

        # ======================================================================
        # SETUP C: THE STEAMROLLER RUNAWAY (RELENTLESS BUY CONTINUATION)
        # ======================================================================
        # Enormous buying dollars steamrolling any sellers trying to dump.
        if 1.00 <= price_change_pct <= 3.00 and delta_vol >= 80_000:
            return {
                "symbol": symbol,
                "side": "long",
                "mid": mid,
                "hold_minutes": 15.0,
                "reason": (
                    f"STEAMROLLER LONG: Enormous buying (${delta_vol:,.0f} volume churned in {elapsed_min:.1f}m). "
                    f"Price up +{price_change_pct:.2f}%. Seller supply swallowed; trend will continue."
                )
            }

        return None

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION LAB (15-MINUTE DURATION + EXPLICIT PROFIT/LOSS)
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
            max_hold = cam["max_hold"]
            elapsed_m = (now - cam["start_t"]) / 60.0

            depth = self.get_resting_depth(sym)
            if not depth:
                remaining.append(cam)
                continue

            cur_price = depth["mid"]
            delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
            net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

            # Trailing Stop: If profit hits +0.40% spot (+1.12% ROE), move stop to lock in +0.10% profit floor
            if delta >= 0.40 and not cam["trailed"]:
                cam["trailed"] = True
                cam["stop_p"] = entry * 1.0010 if side == "long" else entry * 0.9990
                stop = cam["stop_p"]

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= max_hold

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

                # Record streak (Win: +1 in a row | Loss: resets streak to 0/8)
                self.record_trade_outcome(is_win)

                # 5-minute cooldown to prevent machine-gunning the same coin
                self.coin_cooldowns[sym] = time.time() + 300
                print(f"Streak     : {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} Wins in a row! (Need 8/8 to unlock Live)", flush=True)
                print(f"Record     : {self.all_time_wins} Wins / {self.all_time_losses} Losses all-time", flush=True)
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
                self.coin_cooldowns[sym] = time.time() + 300
                print(f"🔴 [LIVE TRADE: YOU LOST!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Loss: {net_roe:.2f}% ROE", flush=True)
                print(f"Live Strikes: {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)

                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] 2 consecutive live losses! Resetting streak. Must win 8/8 in paper to re-enter.\n", flush=True)
                    self.consecutive_paper_wins = 0  # Streak reset back to Game 1

            self.save_brain()
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Steamroller & 10x Reversal Bot online.", flush=True)

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

                # Scan for Steamroller waves and 10x Reversal Ignitions
                for sym in candidates[:25]:
                    if len(self.active_cameras) >= 4:
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    setup = self.evaluate_market_setups(sym, vol_24h)

                    if setup:
                        side = setup["side"]
                        mid = setup["mid"]
                        max_hold = setup["hold_minutes"]

                        # Targets: +0.70% spot move = +2.32% Net ROE on 4x leverage
                        target_p = mid * 1.0070 if side == "long" else mid * 0.9930
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
                            print(f"\n[LIVE 8/8 QUALIFIED ORDER ENTERED] {sym} ({side.upper()}) | {setup['reason']}", flush=True)
                            break
                        elif sym not in [c["symbol"] for c in self.active_cameras]:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "max_hold": max_hold, "trailed": False, "start_t": time.time()
                            })
                            print(f"\n[OPPORTUNITY LOCKED] {sym} ({side.upper()}) | {setup['reason']}", flush=True)

                if cycle % 6 == 0:
                    status = "LIVE_READY (8/8 Achieved)" if self.is_qualified_for_live() else f"HUNTING STREAK ({self.consecutive_paper_wins}/8 in a row)"
                    print(
                        f"[STATUS PULSE] Active Trades: {len(self.active_cameras)}/4 | "
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
    bot = SteamrollerReversalBot()
    bot.run()

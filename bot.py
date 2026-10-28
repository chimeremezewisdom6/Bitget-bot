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
BRAIN_FILE = "pre_dump_intelligence_memory.json"

bot = None  # Populated on startup

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX-V16 Dual 10x Gap & Microstructure Engine",
                "streak_status": f"{bot.consecutive_paper_wins}/{bot.REQUIRED_WIN_STREAK} Wins in a row",
                "mode": "LIVE_AUTHORIZED (8/8 Streak Achieved)" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Hunting 8/8 Streak)",
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
# 2. DUAL 10x GAP & MICROSTRUCTURE ENGINE
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

        # 3. Liquid Crypto Market Filters (Rejects dead coins)
        self.MAX_ALLOWED_SPREAD_PCT = 0.0006   # Max 0.06% spread (must be tight)
        self.MIN_BASELINE_DEPTH_USD = 40_000.0 # Floor must have had at least $40k before collapse
        self.QUARANTINE_DURATION_SEC = 3600    # 1-Hour lockout for any failed trade

        # Non-Crypto / Low-Liquidity Equity Perps Blacklist
        self.BLACKLIST = {
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU',
            'SKHYNIX', 'SKHY', 'SNDK', 'SNXX', 'BABA', 'COIN', 'MSTR', 'ARM', 'INTC'
        }

        # 4. Memory & Tracking
        self.active_cameras = []
        self.market_history = {}
        self.coin_cooldowns = {}
        self.load_brain()

        # 5. Live Trade Tracker
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

    # --------------------------------------------------------------------------
    # 1. TAPE VELOCITY: CONFIRM ACTIVE REAL-TIME FLOW
    # --------------------------------------------------------------------------
    def is_market_actively_trading(self, symbol):
        """Rejects ghost books. Requires trades within the last 6 seconds."""
        try:
            trades = self.bitget.fetch_trades(symbol, limit=10)
            if not trades or len(trades) < 5:
                return False

            now_ms = time.time() * 1000
            latest_trade_time = trades[-1]['timestamp']

            # If no trade occurred in the last 6 seconds, coin is too inactive
            if (now_ms - latest_trade_time) > 6000:
                return False

            return True
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # 2. ORDER BOOK DEPTH & SPREAD INSPECTION
    # --------------------------------------------------------------------------
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
            if spread_pct > self.MAX_ALLOWED_SPREAD_PCT:
                return None

            # Calculate resting depth within 0.8% of mid price
            bid_usd = sum([p * q for p, q in bids if p >= mid * 0.992])
            ask_usd = sum([p * q for p, q in asks if p <= mid * 1.008])

            return {
                "mid": mid,
                "spread_pct": spread_pct,
                "bid_usd": bid_usd,
                "ask_usd": ask_usd
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 3. DUAL 10x GAP DETECTION LOGIC
    # --------------------------------------------------------------------------
    def audit_pre_dump_behavior(self, symbol, vol_24h):
        base = symbol.split('/')[0].split(':')[0].upper()
        if base in self.BLACKLIST or time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        # Verify active market tape first
        if not self.is_market_actively_trading(symbol):
            return None

        metrics = self.get_order_book_metrics(symbol)
        if not metrics:
            return None

        now = time.time()
        if symbol not in self.market_history:
            self.market_history[symbol] = []

        self.market_history[symbol].append({
            "t": now,
            "bid_usd": metrics["bid_usd"],
            "ask_usd": metrics["ask_usd"],
            "price": metrics["mid"]
        })
        self.market_history[symbol] = [s for s in self.market_history[symbol] if now - s["t"] <= 600.0]

        history = self.market_history[symbol]
        # Look back 2 to 6 minutes for historical baseline
        past_snaps = [s for s in history if 120.0 <= (now - s["t"]) <= 360.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        mid = metrics["mid"]
        cur_bid = metrics["bid_usd"]
        cur_ask = metrics["ask_usd"]

        if cur_bid <= 0 or cur_ask <= 0:
            return None

        # ======================================================================
        # DUAL 10x SHORT SETUP:
        # 1. Bids fell by 10x from baseline
        # 2. Asks are currently 10x larger than resting Bids
        # ======================================================================
        bid_collapse_factor = baseline["bid_usd"] / cur_bid
        ask_to_bid_gap = cur_ask / cur_bid

        if (baseline["bid_usd"] >= self.MIN_BASELINE_DEPTH_USD and 
            bid_collapse_factor >= 10.0 and 
            ask_to_bid_gap >= 10.0):

            peak_price = max([s["price"] for s in history])
            slip_pct = ((peak_price - mid) / peak_price) * 100.0

            # Price begins cracking downward into the void
            if 0.05 <= slip_pct <= 0.50:
                return {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "target_price": mid * 0.9920,       # 0.8% profit target
                    "stop_price": peak_price * 1.0015,   # Invalidation above wall
                    "reason": (
                        f"DUAL 10x DUMP: Bids collapsed {bid_collapse_factor:.1f}x "
                        f"(${baseline['bid_usd']:,.0f} -> ${cur_bid:,.0f}) AND "
                        f"Asks are {ask_to_bid_gap:.1f}x larger (${cur_ask:,.0f} vs ${cur_bid:,.0f})! "
                        f"Price cracked -{slip_pct:.2f}% into void."
                    )
                }

        # ======================================================================
        # DUAL 10x LONG SETUP:
        # 1. Asks fell by 10x from baseline
        # 2. Bids are currently 10x larger than resting Asks
        # ======================================================================
        ask_collapse_factor = baseline["ask_usd"] / cur_ask
        bid_to_ask_gap = cur_bid / cur_ask

        if (baseline["ask_usd"] >= self.MIN_BASELINE_DEPTH_USD and 
            ask_collapse_factor >= 10.0 and 
            bid_to_ask_gap >= 10.0):

            trough_price = min([s["price"] for s in history])
            lift_pct = ((mid - trough_price) / trough_price) * 100.0

            # Price begins lifting through the ceiling
            if 0.05 <= lift_pct <= 0.50:
                return {
                    "symbol": symbol,
                    "side": "long",
                    "mid": mid,
                    "target_price": mid * 1.0080,         # 0.8% profit target
                    "stop_price": trough_price * 0.9985,   # Invalidation below floor
                    "reason": (
                        f"DUAL 10x PUMP: Asks collapsed {ask_collapse_factor:.1f}x "
                        f"(${baseline['ask_usd']:,.0f} -> ${cur_ask:,.0f}) AND "
                        f"Bids are {bid_to_ask_gap:.1f}x larger (${cur_bid:,.0f} vs ${cur_ask:,.0f})! "
                        f"Price lifted +{lift_pct:.2f}% into gap."
                    )
                }

        return None

    # --------------------------------------------------------------------------
    # 4. MONITOR PAPER TRADE OBSERVATION LAB
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

            # Trailing stop: Once up +0.35%, move stop to +0.10% profit floor
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
    # 5. MONITOR LIVE TRADE EXECUTION
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
                        params={'reduceOnly': True}
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
    # 6. MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Dual 10x Gap Intelligence Bot online.", flush=True)

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
                
                # Filter for liquid crypto pairs ($15M+ turnover, no stocks)
                candidates = [
                    s for s, t in tickers.items()
                    if s.endswith(":USDT")
                    and float(t.get('quoteVolume', 0) or 0) >= 15_000_000
                    and not any(s.startswith(x) for x in ['SOX', 'SKHY', 'SNDK', 'SNXX', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'KORU'])
                    and s not in active_syms
                ]
                candidates.sort(key=lambda s: float(tickers[s].get('quoteVolume', 0) or 0), reverse=True)

                # Scan top candidates
                for sym in candidates[:30]:
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
                            print(f"\n[10x GAP LOCKED] {sym} ({side.upper()}) | {setup['reason']}", flush=True)

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

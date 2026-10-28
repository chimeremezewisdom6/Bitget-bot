import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# STEP 1: KEEP-ALIVE SERVER (PORT 10000 FOR UPTIMEROBOT)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "status": "RUNNING",
            "active_cameras": len(bot.active_cameras),
            "scorecard": f"{sum(bot.history)}/{len(bot.history)} wins"
        }
        self.wfile.write(json.dumps(status).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# STEP 2: THE TRADING ENGINE (EVERY VARIABLE USES 'self.' SO IT ALWAYS REACHES IT)
# ==============================================================================
class SimpleThinkingBot:
    def __init__(self):
        # 1. Account Settings
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_losses = 0
        self.max_losses = 2

        # 2. Memory & Scorecard (Rolling window of last 15 trades, never wipes to 0/0)
        self.history = []
        self.depth_memory = {}
        self.active_cameras = []

        # 3. Live Trade Tracker (Directly attached to self, so it is ALWAYS accessible)
        self.live_state = {
            "active": False,
            "symbol": None,
            "contracts": 0,
            "entry_price": 0.0,
            "target_price": 0.0,
            "stop_price": 0.0,
            "start_time": 0.0,
            "max_minutes": 10.0
        }

        # 4. Exchange Connection
        self.api_key = os.environ.get("API_KEY")
        self.secret_key = os.environ.get("SECRET_KEY")
        self.passphrase = os.environ.get("PASSPHRASE")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing API keys!", flush=True)
            sys.exit(1)

        self.bitget = ccxt.bitget({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })

    # --------------------------------------------------------------------------
    # STEP 3: ORDER BOOK DEPTH CHECK (5X WALL OR 2X SURGE)
    # --------------------------------------------------------------------------
    def inspect_coin(self, symbol):
        """
        Sentence-style rules:
        1. Are bids 5x higher than asks? OR
        2. Did bids double (2x) in under 5 minutes with real liquidity?
        """
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2.0

            # Measure total money in bids and asks within 1.5% of price
            bid_usd = sum([p * q for p, q in bids if p >= mid_price * 0.985])
            ask_usd = sum([p * q for p, q in asks if p <= mid_price * 1.015])

            if bid_usd < 10_000 or ask_usd <= 0:
                return None

            now = time.time()
            current_ratio = bid_usd / ask_usd

            # Remember this snapshot
            if symbol not in self.depth_memory:
                self.depth_memory[symbol] = []

            self.depth_memory[symbol].append({"t": now, "b": bid_usd, "a": ask_usd, "p": mid_price})
            self.depth_memory[symbol] = [s for s in self.depth_memory[symbol] if now - s["t"] <= 600.0]

            # Look back between 20 seconds and 5 minutes ago
            lookbacks = [s for s in self.depth_memory[symbol] if 20.0 <= (now - s["t"]) <= 300.0]
            if not lookbacks:
                return None

            baseline = lookbacks[0]
            elapsed_m = (now - baseline["t"]) / 60.0
            bid_growth = bid_usd / baseline["b"] if baseline["b"] > 0 else 1.0
            total_now = bid_usd + ask_usd
            total_then = baseline["b"] + baseline["a"]
            liquidity_growth = total_now / total_then if total_then > 0 else 1.0

            # Condition A: 5x Bids Wall
            if current_ratio >= 5.0 and bid_growth >= 1.0:
                return {
                    "symbol": symbol,
                    "mid": mid_price,
                    "reason": f"5x Bid Wall confirmed ({current_ratio:.1f}x higher than asks)",
                    "hold_minutes": 8.0
                }

            # Condition B: 2x Surge in < 5 minutes
            if bid_growth >= 2.0 and liquidity_growth >= 1.3:
                return {
                    "symbol": symbol,
                    "mid": mid_price,
                    "reason": f"Bids surged {bid_growth:.1f}x in {elapsed_m:.1f}m (Liquidity expanded {liquidity_growth:.1f}x)",
                    "hold_minutes": 10.0
                }

        except Exception:
            return None

        return None

    # --------------------------------------------------------------------------
    # STEP 4: MONITOR PAPER CAMERAS
    # --------------------------------------------------------------------------
    def update_cameras(self):
        remaining = []
        now = time.time()

        for cam in self.active_cameras:
            sym = cam["symbol"]
            entry = cam["entry_price"]
            target = cam["target_price"]
            stop = cam["stop_price"]
            max_m = cam["max_minutes"]
            elapsed_m = (now - cam["start_time"]) / 60.0

            try:
                ticker = self.bitget.fetch_ticker(sym)
                cur_price = float(ticker.get('last', 0) or 0)
            except Exception:
                remaining.append(cam)
                continue

            # Calculate Leveraged Profit (ROE)
            price_change_pct = ((cur_price - entry) / entry) * 100.0
            net_roe = (price_change_pct * self.leverage) - (0.06 * 2.0 * self.leverage)

            # Check Targets
            if cur_price >= target:
                self.history.append(1)
                self.history = self.history[-15:]
                print(f"\n[PAPER TARGET HIT] {sym} won with +{net_roe:.2f}% ROE in {elapsed_m:.1f}m!", flush=True)
                print(f"[SCORECARD] {sum(self.history)}/{len(self.history)} passed\n", flush=True)

            elif cur_price <= stop:
                self.history.append(0)
                self.history = self.history[-15:]
                print(f"\n[PAPER STOP HIT] {sym} exited at {net_roe:.2f}% ROE", flush=True)
                print(f"[SCORECARD] {sum(self.history)}/{len(self.history)} passed\n", flush=True)

            elif elapsed_m >= max_m:
                won = net_roe > 0.20
                self.history.append(1 if won else 0)
                self.history = self.history[-15:]
                print(f"\n[PAPER TIME EXPIRED] {sym} closed after {elapsed_m:.1f}m at {net_roe:+.2f}% ROE", flush=True)
                print(f"[SCORECARD] {sum(self.history)}/{len(self.history)} passed\n", flush=True)

            else:
                remaining.append(cam)

        self.active_cameras = remaining

    # --------------------------------------------------------------------------
    # STEP 5: MONITOR LIVE TRADE GUARDIAN
    # --------------------------------------------------------------------------
    def poll_live_guardian(self):
        # Because we use self.live_state, it can ALWAYS access it!
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        entry = self.live_state["entry_price"]
        target = self.live_state["target_price"]
        stop = self.live_state["stop_price"]
        max_m = self.live_state["max_minutes"]
        elapsed_m = (time.time() - self.live_state["start_time"]) / 60.0

        try:
            ticker = self.bitget.fetch_ticker(sym)
            cur_price = float(ticker.get('last', 0) or 0)
        except Exception:
            return

        price_change_pct = ((cur_price - entry) / entry) * 100.0
        net_roe = (price_change_pct * self.leverage) - (0.06 * 2.0 * self.leverage)

        should_close = False
        reason = ""
        won = False

        if cur_price >= target:
            should_close = True
            won = True
            reason = f"Target Hit (+{net_roe:.2f}% ROE)"

        elif cur_price <= stop:
            should_close = True
            won = False
            reason = f"Stop Hit ({net_roe:.2f}% ROE)"

        elif elapsed_m >= max_m:
            should_close = True
            won = net_roe > 0
            reason = f"Max Time Reached ({elapsed_m:.1f}m)"

        if should_close:
            for _ in range(3):
                try:
                    self.bitget.create_order(sym, 'market', 'sell', self.live_state["contracts"], params={'reduceOnly': True, 'tradeSide': 'close'})
                    break
                except Exception:
                    time.sleep(1)

            self.consecutive_losses = 0 if won else self.consecutive_losses + 1
            print(f"\n[LIVE TRADE CLOSED] {sym} | Reason: {reason}\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # STEP 6: MAIN RUNNER LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] Simple Thinking Bot running smoothly.", flush=True)

        try:
            self.bitget.load_markets()
        except Exception as e:
            print(f"[WARN] Markets load: {e}", flush=True)

        cycle = 0

        while True:
            try:
                # 1. Update Paper Cameras & Live Trade
                self.update_cameras()
                self.poll_live_guardian()

                # 2. Check Capital Safety
                balance_data = self.bitget.fetch_balance()
                usdt_free = float(balance_data.get('USDT', {}).get('free', 0) or 0)

                if usdt_free < self.equity_floor:
                    print(f"[PAUSE] Balance ${usdt_free:.2f} below ${self.equity_floor:.2f} floor. Sleeping...", flush=True)
                    time.sleep(30)
                    continue

                if self.consecutive_losses >= self.max_losses:
                    print("[PAUSE] 2 consecutive losses. Cooldown active. Sleeping...", flush=True)
                    time.sleep(60)
                    continue

                notional = max(min(usdt_free * 0.85 * self.leverage, 7.50), 5.15)

                # 3. Scan Coins
                try:
                    tickers = self.bitget.fetch_tickers()
                except Exception:
                    time.sleep(4)
                    continue

                active_symbols = {c["symbol"] for c in self.active_cameras}
                candidates = [
                    s for s, t in tickers.items()
                    if s.endswith(":USDT")
                    and float(t.get('quoteVolume', 0) or 0) >= 1_000_000
                    and s not in active_symbols
                ][:15]

                # 4. Check for Order Flow Setups
                for sym in candidates:
                    if len(self.active_cameras) >= 8:
                        break

                    signal = self.inspect_coin(sym)
                    if signal:
                        mid = signal["mid"]
                        # Set realistic targets (0.45% move = 1.5% profit on 4x leverage)
                        target_price = mid * 1.0045
                        stop_price = mid * 0.9965
                        hold_time = signal["hold_minutes"]

                        # Check if paper score qualifies for Real Money (7 out of last 10 wins)
                        is_ready = len(self.history) >= 10 and sum(self.history[-10:]) >= 7

                        if is_ready and not self.live_state["active"]:
                            try:
                                self.bitget.set_leverage(self.leverage, sym)
                            except Exception:
                                pass
                            amount = float(self.bitget.amount_to_precision(sym, notional / mid))
                            self.bitget.create_order(sym, 'market', 'buy', amount)

                            # Set live trade cleanly
                            self.live_state = {
                                "active": True,
                                "symbol": sym,
                                "contracts": amount,
                                "entry_price": mid,
                                "target_price": target_price,
                                "stop_price": stop_price,
                                "start_time": time.time(),
                                "max_minutes": hold_time
                            }
                            print(f"\n[LIVE PROMOTION TRADED] {sym} | {signal['reason']}", flush=True)
                            break

                        # Otherwise, open in observational paper camera
                        self.active_cameras.append({
                            "symbol": sym,
                            "entry_price": mid,
                            "target_price": target_price,
                            "stop_price": stop_price,
                            "start_time": time.time(),
                            "max_minutes": hold_time
                        })
                        print(f"[CAMERA LOCKED] {sym} -> {signal['reason']} | Hold: {hold_time}m", flush=True)

                # 5. Heartbeat Status
                if cycle % 6 == 0:
                    score = f"{sum(self.history)}/{len(self.history)}"
                    print(
                        f"\n[HEARTBEAT] Cameras: {len(self.active_cameras)}/8 | "
                        f"Vault: ${usdt_free:.2f} ({self.leverage}x) | "
                        f"Scorecard: {score} passed",
                        flush=True
                    )

                cycle += 1
                time.sleep(4)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(5)

# ==============================================================================
# STEP 7: START THE BOT
# ==============================================================================
if __name__ == "__main__":
    bot = SimpleThinkingBot()
    bot.run()

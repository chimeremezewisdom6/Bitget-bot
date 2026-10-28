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

class HealthCheckServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "engine": "APEX-V16 Pure Liquidity Vacuum & Capital Velocity Engine",
            "active_vacuums": len(bot.active_cameras),
            "scorecard": f"{sum(bot.trade_history)}/{len(bot.trade_history)} wins",
            "live_active": bot.live_state["active"]
        }
        self.wfile.write(json.dumps(status).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# 2. PURE LIQUIDITY VACUUM ENGINE (NO BID/ASK COMPARISONS)
# ==============================================================================
class PureLiquidityVacuumBot:
    def __init__(self):
        # 1. Capital & Risk Protection
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_losses = 0
        self.max_losses = 2

        # 2. Rolling Memory & Active Cameras
        self.trade_history = []
        self.active_cameras = []
        
        # Tracks resting circulating depth over time: { symbol: [ {"t": time, "ask_depth": $, "bid_depth": $, "price": $}, ... ] }
        self.circulating_depth_history = {}

        # 3. Live State (Bound directly to self to prevent any UnboundLocalError)
        self.live_state = {
            "active": False,
            "symbol": None,
            "side": None,
            "contracts": 0,
            "entry_price": 0.0,
            "target_price": 0.0,
            "stop_price": 0.0,
            "start_time": 0.0,
            "max_minutes": 10.0
        }

        # 4. Exchange Setup
        self.api_key = os.environ.get("API_KEY")
        self.secret_key = os.environ.get("SECRET_KEY")
        self.passphrase = os.environ.get("PASSPHRASE")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing exchange credentials in environment variables!", flush=True)
            sys.exit(1)

        self.bitget = ccxt.bitget({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })

    # --------------------------------------------------------------------------
    # MEASURE RESTING CIRCULATING DEPTH
    # --------------------------------------------------------------------------
    def measure_resting_circulating_depth(self, symbol):
        """
        Measures the actual dollars sitting on the book within 1.5% of price.
        Does NOT compare bids to asks.
        """
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=25)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None

            mid = (bids[0][0] + asks[0][0]) / 2.0

            # Available circulating sell orders (Asks) and buy orders (Bids)
            ask_dollars = sum([p * q for p, q in asks if p <= mid * 1.015])
            bid_dollars = sum([p * q for p, q in bids if p >= mid * 0.985])

            return {
                "mid": mid,
                "ask_dollars": ask_dollars,
                "bid_dollars": bid_dollars
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # AUDIT LIQUIDITY VACUUM & CAPITAL VELOCITY
    # --------------------------------------------------------------------------
    def audit_liquidity_vacuum(self, symbol, vol_24h):
        """
        Examines:
        1. Is there massive volume churning? (Hundreds of thousands or millions).
        2. Did circulating resting capital collapse over the last 1 to 4 minutes?
           - For Long: Did Asks collapse from $10k to $100?
           - For Short: Did Bids collapse from $100k to dust?
        3. Is price aligned with the direction of the vacuum?
        """
        now = time.time()
        depth = self.measure_resting_circulating_depth(symbol)
        if not depth:
            return None

        # Store depth snapshot
        if symbol not in self.circulating_depth_history:
            self.circulating_depth_history[symbol] = []

        self.circulating_depth_history[symbol].append({
            "t": now,
            "ask_dollars": depth["ask_dollars"],
            "bid_dollars": depth["bid_dollars"],
            "price": depth["mid"]
        })
        self.circulating_depth_history[symbol] = [s for s in self.circulating_depth_history[symbol] if now - s["t"] <= 480.0]

        history = self.circulating_depth_history[symbol]
        # Look back between 45 seconds and 4 minutes ago
        past_snaps = [s for s in history if 45.0 <= (now - s["t"]) <= 240.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_m = (now - baseline["t"]) / 60.0
        mid = depth["mid"]

        # Approximate 1-hour volume turnover rate
        volume_churn_1h = vol_24h / 24.0

        # Must have at least $50,000/hr in active volume churn to prevent dead coins
        if volume_churn_1h < 50_000:
            return None

        # ----------------------------------------------------------------------
        # SCENARIO A: LONG VACUUM (Ask resistance evaporated while volume churns)
        # Example: $10,000 asks shrank down to $500 while $2M volume trades!
        # ----------------------------------------------------------------------
        if depth["ask_dollars"] > 0 and baseline["ask_dollars"] > 0:
            ask_depletion = baseline["ask_dollars"] / depth["ask_dollars"]
            velocity_long = volume_churn_1h / depth["ask_dollars"]

            # Trigger condition:
            # 1. Asks depleted by at least 60% (depletion >= 2.5x)
            # 2. Turnover velocity is at least 80x (heavy churn through tiny depth)
            # 3. Price is moving UP into the vacuum (already winning)
            if ask_depletion >= 2.5 and velocity_long >= 80.0 and mid > baseline["price"]:
                return {
                    "symbol": symbol,
                    "side": "long",
                    "mid": mid,
                    "reason": (
                        f"LONG VACUUM: Asks evaporated from ${baseline['ask_dollars']:,.0f} down to ${depth['ask_dollars']:,.0f} "
                        f"({ask_depletion:.1f}x depletion) in {elapsed_m:.1f}m while ${volume_churn_1h:,.0f}/hr is churning! "
                        f"Velocity: {velocity_long:,.0f}x turnover!"
                    )
                }

        # ----------------------------------------------------------------------
        # SCENARIO B: SHORT SINKHOLE (Bid support evaporated while volume churns)
        # Example: $100,000 bids shrank down to dust while volume trades!
        # ----------------------------------------------------------------------
        if depth["bid_dollars"] > 0 and baseline["bid_dollars"] > 0:
            bid_depletion = baseline["bid_dollars"] / depth["bid_dollars"]
            velocity_short = volume_churn_1h / depth["bid_dollars"]

            # Trigger condition:
            # 1. Bids depleted by at least 60% (depletion >= 2.5x)
            # 2. Turnover velocity is at least 80x
            # 3. Price is moving DOWN into the sinkhole (already winning)
            if bid_depletion >= 2.5 and velocity_short >= 80.0 and mid < baseline["price"]:
                return {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "reason": (
                        f"SHORT SINKHOLE: Bids collapsed from ${baseline['bid_dollars']:,.0f} down to ${depth['bid_dollars']:,.0f} "
                        f"({bid_depletion:.1f}x depletion) in {elapsed_m:.1f}m while ${volume_churn_1h:,.0f}/hr is churning! "
                        f"Velocity: {velocity_short:,.0f}x turnover!"
                    )
                }

        return None

    # --------------------------------------------------------------------------
    # MONITOR PAPER CAMERAS
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

            won = False
            done = False
            reason = ""

            if (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target):
                done = True
                won = True
                reason = f"Vacuum Target Hit at +{net_roe:.2f}% Net ROE in {elapsed_m:.1f}m!"

            elif (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop):
                done = True
                won = False
                reason = f"Stop boundary reached at {net_roe:.2f}% ROE"

            elif elapsed_m >= 10.0:
                done = True
                won = net_roe > 0.20
                reason = f"10m natural hold concluded at {net_roe:+.2f}% ROE"

            if done:
                self.trade_history.append(1 if won else 0)
                self.trade_history = self.trade_history[-15:]
                print(f"\n[PAPER TEST COMPLETED] {sym} ({side.upper()}) | {reason}", flush=True)
                print(f"[SCORECARD] {sum(self.trade_history)}/{len(self.trade_history)} passed (+1.5% ROE goal)\n", flush=True)
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
            cur_p = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
        except Exception:
            return

        delta = ((cur_p - entry) / entry) * 100.0 if side == "long" else ((entry - cur_p) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        close_now = False
        won = False
        reason = ""

        if (side == "long" and cur_p >= target) or (side == "short" and cur_p <= target):
            close_now = True
            won = True
            reason = f"Target Banked (+{net_roe:.2f}% ROE)"
        elif (side == "long" and cur_p <= stop) or (side == "short" and cur_p >= stop):
            close_now = True
            won = False
            reason = f"Stop Reached ({net_roe:.2f}% ROE)"
        elif elapsed_m >= 10.0:
            close_now = True
            won = net_roe > 0
            reason = f"10m Hold Complete ({net_roe:+.2f}% ROE)"

        if close_now:
            order_side = 'sell' if side == 'long' else 'buy'
            for _ in range(3):
                try:
                    self.bitget.create_order(sym, 'market', order_side, self.live_state["contracts"], params={'reduceOnly': True, 'tradeSide': 'close'})
                    break
                except Exception:
                    time.sleep(1)

            self.consecutive_losses = 0 if won else self.consecutive_losses + 1
            print(f"\n[LIVE VACUUM TRADE CLOSED] {sym} ({side.upper()}) | Reason: {reason}\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Pure Liquidity Vacuum Engine active (Bids/Asks abandoned).", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                # 1. Update Existing Cameras & Live Guardian
                self.update_cameras()
                self.poll_live_trade()

                # 2. Risk & Account Verification
                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    print(f"[VAULT PAUSE] Balance ${balance:.2f} below ${self.equity_floor:.2f} floor. Sleeping...", flush=True)
                    time.sleep(30)
                    continue

                if self.consecutive_losses >= self.max_losses:
                    print("[VAULT PAUSE] 2 consecutive live losses. Rest pause active. Sleeping...", flush=True)
                    time.sleep(60)
                    continue

                notional = max(min(balance * 0.85 * self.leverage, 7.50), 5.15)

                # 3. Fetch Market Tickers & Filter Candidates
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

                # Rank by 24h volume so we evaluate the highest circulating coins first
                candidates.sort(key=lambda s: float(tickers[s].get('quoteVolume', 0) or 0), reverse=True)

                # 4. Check for Liquidity Vacuums Across Active Coins
                for sym in candidates[:20]:
                    if len(self.active_cameras) >= 8:
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    vacuum = self.audit_liquidity_vacuum(sym, vol_24h)

                    if vacuum:
                        side = vacuum["side"]
                        mid = vacuum["mid"]

                        # Targets scaled to 4x leverage: 0.45% move = ~1.50% Net ROE
                        if side == "long":
                            target_p = mid * 1.0045
                            stop_p = mid * 0.9960
                        else:
                            target_p = mid * 0.9955
                            stop_p = mid * 1.0040

                        # Unlock real money if 7 out of last 10 paper tests won
                        is_ready = len(self.trade_history) >= 10 and sum(self.trade_history[-10:]) >= 7

                        if is_ready and not self.live_state["active"]:
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
                                "start_time": time.time(), "max_minutes": 10.0
                            }
                            print(f"\n[LIVE VACUUM TRADE EXECUTED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)
                            break
                        else:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "start_t": time.time()
                            })
                            print(f"\n[VACUUM LOCKED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)

                # 5. Heartbeat Status
                if cycle % 6 == 0:
                    score = f"{sum(self.trade_history)}/{len(self.trade_history)}"
                    print(
                        f"\n[PULSE] Cameras: {len(self.active_cameras)}/8 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | "
                        f"Coins Tracked: {len(self.circulating_depth_history)} | "
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
# START BOT
# ==============================================================================
if __name__ == "__main__":
    bot = PureLiquidityVacuumBot()
    bot.run()

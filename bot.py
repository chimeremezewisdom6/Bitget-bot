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
            "engine": "APEX-V16 Dual-Procedure Vacuum & Fade Lab",
            "active_cameras": len(bot.active_cameras),
            "procedure_scorecard": bot.get_scorecard(),
            "live_trade": bot.live_state["active"],
            "tracked_pairs": len(bot.market_memory)
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
# 2. DUAL-PROCEDURE VACUUM ENGINE (ALL BOUND TO self. TO PREVENT SCOPE BUGS)
# ==============================================================================
class DualProcedureVacuumBot:
    def __init__(self):
        # 1. Risk & Leverage Settings
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_losses = 0
        self.max_losses = 2

        # 2. Scorecard for Both Procedures (Rolling 15-Trade Window)
        self.history_fixed_tp_sl = []  # Tracks Procedure A (Fixed TP/SL)
        self.history_fade_exit = []    # Tracks Procedure B (Dynamic Fade)
        
        self.active_cameras = []
        self.market_memory = {}        # 5-minute rolling market data store

        # 3. Live Trade Tracker (Directly attached to self)
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
            "start_time": 0.0,
            "max_minutes": 8.0
        }

        # 4. Exchange Connection
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
    # AUDIT THE 5-MINUTE VACUUM ENTRY
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

        # Look back between 3.5 and 6.0 minutes ago
        past_snaps = [s for s in history if 210.0 <= (now - s["t"]) <= 360.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        mid = depth["mid"]

        delta_vol_5m = vol_24h - baseline["vol_24h"]
        if delta_vol_5m < 20_000:
            return None

        # ----------------------------------------------------------------------
        # SETUP 1: LONG VACUUM (Asks collapsed while volume traded)
        # ----------------------------------------------------------------------
        if depth["ask_dollars"] > 0 and baseline["ask_dollars"] > 0:
            ask_depletion = baseline["ask_dollars"] / depth["ask_dollars"]
            velocity_long = delta_vol_5m / depth["ask_dollars"]
            price_change_pct = ((mid - baseline["price"]) / baseline["price"]) * 100.0

            if ask_depletion >= 2.0 and velocity_long >= 15.0 and price_change_pct >= 0.10:
                return {
                    "symbol": symbol,
                    "side": "long",
                    "mid": mid,
                    "initial_resistance": depth["ask_dollars"],
                    "reason": (
                        f"5M LONG VACUUM: ${delta_vol_5m:,.0f} volume churned in {elapsed_min:.1f}m while Asks "
                        f"collapsed from ${baseline['ask_dollars']:,.0f} down to ${depth['ask_dollars']:,.0f} "
                        f"({ask_depletion:.1f}x)! Velocity: {velocity_long:.0f}x | Price: +{price_change_pct:.2f}%"
                    )
                }

        # ----------------------------------------------------------------------
        # SETUP 2: SHORT SINKHOLE (Bids collapsed while volume traded)
        # ----------------------------------------------------------------------
        if depth["bid_dollars"] > 0 and baseline["bid_dollars"] > 0:
            bid_depletion = baseline["bid_dollars"] / depth["bid_dollars"]
            velocity_short = delta_vol_5m / depth["bid_dollars"]
            price_change_pct = ((baseline["price"] - mid) / baseline["price"]) * 100.0

            if bid_depletion >= 2.0 and velocity_short >= 15.0 and price_change_pct >= 0.10:
                return {
                    "symbol": symbol,
                    "side": "short",
                    "mid": mid,
                    "initial_resistance": depth["bid_dollars"],
                    "reason": (
                        f"5M SHORT SINKHOLE: ${delta_vol_5m:,.0f} volume churned in {elapsed_min:.1f}m while Bids "
                        f"collapsed from ${baseline['bid_dollars']:,.0f} down to ${depth['bid_dollars']:,.0f} "
                        f"({bid_depletion:.1f}x)! Velocity: {velocity_short:.0f}x | Price: -{price_change_pct:.2f}%"
                    )
                }

        return None

    # --------------------------------------------------------------------------
    # MONITOR OBSERVATION CAMERAS (A/B TESTING BOTH PROCEDURES)
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

            # Calculate True Net ROE at 4x leverage
            delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
            net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

            # Track peak prices and thinnest book levels seen during the trade
            if cur_price > cam["peak_price"]:
                cam["peak_price"] = cur_price
            if cur_price < cam["trough_price"]:
                cam["trough_price"] = cur_price

            if side == "long" and cur_ask_dollars < cam["min_resistance"]:
                cam["min_resistance"] = cur_ask_dollars
            elif side == "short" and cur_bid_dollars < cam["min_resistance"]:
                cam["min_resistance"] = cur_bid_dollars

            # ------------------------------------------------------------------
            # PROCEDURE B AUDIT: HAS THE SETUP FADED?
            # ------------------------------------------------------------------
            # Long Fade: Asks refilled 2x above thinnest point AND price ticked down from peak
            long_faded = (
                side == "long"
                and cur_ask_dollars >= (cam["min_resistance"] * 2.0)
                and cur_price < cam["peak_price"] * 0.9990
            )

            # Short Fade: Bids refilled 2x above lowest point AND price ticked up from trough
            short_faded = (
                side == "short"
                and cur_bid_dollars >= (cam["min_resistance"] * 2.0)
                and cur_price > cam["trough_price"] * 1.0010
            )

            fade_occurred = (long_faded or short_faded)
            if fade_occurred and cam["fade_captured_roe"] is None:
                # First time fade is detected: freeze what the fade return was!
                cam["fade_captured_roe"] = round(net_roe, 2)
                cam["fade_time_m"] = round(elapsed_m, 1)

            # ------------------------------------------------------------------
            # PROCEDURE A AUDIT: FIXED TARGET / STOP LOSS / TIMEOUT
            # ------------------------------------------------------------------
            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= 8.0

            if hit_target or hit_stop or timed_out:
                # Trade is officially complete. Log both procedures side-by-side!
                won_fixed = hit_target or (timed_out and net_roe > 0.20)
                self.history_fixed_tp_sl.append(1 if won_fixed else 0)
                self.history_fixed_tp_sl = self.history_fixed_tp_sl[-15:]

                # Record fade procedure performance
                fade_roe = cam["fade_captured_roe"] if cam["fade_captured_roe"] is not None else round(net_roe, 2)
                won_fade = fade_roe > 0.15
                self.history_fade_exit.append(1 if won_fade else 0)
                self.history_fade_exit = self.history_fade_exit[-15:]

                fixed_status = "TARGET_HIT (+1.5% ROE)" if hit_target else ("STOP_HIT" if hit_stop else "TIMEOUT")
                fade_status = f"FADED at {fade_roe:+.2f}% ROE in {cam.get('fade_time_m', elapsed_m)}m" if cam["fade_captured_roe"] is not None else "NEVER_FADED"

                print(f"\n=======================================================", flush=True)
                print(f"[PAPER LAB EXPERIMENT FINISHED] {sym} ({side.upper()})", flush=True)
                print(f" * Procedure A (Fixed TP/SL) : {fixed_status} -> Net ROE: {net_roe:+.2f}%", flush=True)
                print(f" * Procedure B (Fade Exit)   : {fade_status}", flush=True)
                if hit_stop and fade_roe > net_roe:
                    print(f" -> VERDICT: Procedure B (Fade Exit) saved capital by cutting before Stop!", flush=True)
                elif hit_target and fade_roe < net_roe:
                    print(f" -> VERDICT: Procedure A (Fixed Target) captured full run!", flush=True)
                print(f"[LAB SCORECARD] Fixed TP/SL: {sum(self.history_fixed_tp_sl)}/{len(self.history_fixed_tp_sl)} wins | Fade Exit: {sum(self.history_fade_exit)}/{len(self.history_fade_exit)} wins", flush=True)
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
        cur_ask_dollars = depth["ask_dollars"]
        cur_bid_dollars = depth["bid_dollars"]

        delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        # Update high/low tracking
        if cur_price > self.live_state["peak_price"]:
            self.live_state["peak_price"] = cur_price
        if cur_price < self.live_state["trough_price"]:
            self.live_state["trough_price"] = cur_price

        if side == "long" and cur_ask_dollars < self.live_state["min_resistance_seen"]:
            self.live_state["min_resistance_seen"] = cur_ask_dollars
        elif side == "short" and cur_bid_dollars < self.live_state["min_resistance_seen"]:
            self.live_state["min_resistance_seen"] = cur_bid_dollars

        # Fade Detection for Live Protection
        long_faded = (
            side == "long"
            and cur_ask_dollars >= (self.live_state["min_resistance_seen"] * 2.0)
            and cur_price < self.live_state["peak_price"] * 0.9990
        )
        short_faded = (
            side == "short"
            and cur_bid_dollars >= (self.live_state["min_resistance_seen"] * 2.0)
            and cur_price > self.live_state["trough_price"] * 1.0010
        )

        close_it = False
        won = False
        reason = ""

        # 1. Target Hit
        if (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target):
            close_it = True
            won = True
            reason = f"Target Hit (+{net_roe:.2f}% ROE)"

        # 2. Stop Hit
        elif (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop):
            close_it = True
            won = False
            reason = f"Stop Loss Hit ({net_roe:.2f}% ROE)"

        # 3. Dynamic Fade Cut (If resistance/support refilled 2x and price stalled)
        elif (long_faded or short_faded) and elapsed_m >= 1.5:
            close_it = True
            won = net_roe > 0
            reason = f"Dynamic Fade Cut (Resistance refilled 2x | Net ROE: {net_roe:+.2f}%)"

        # 4. Timeout
        elif elapsed_m >= self.live_state["max_minutes"]:
            close_it = True
            won = net_roe > 0
            reason = f"Max Duration Elapsed ({elapsed_m:.1f}m)"

        if close_it:
            order_side = 'sell' if side == 'long' else 'buy'
            for _ in range(3):
                try:
                    self.bitget.create_order(sym, 'market', order_side, self.live_state["contracts"], params={'reduceOnly': True, 'tradeSide': 'close'})
                    break
                except Exception:
                    time.sleep(1)

            self.consecutive_losses = 0 if won else self.consecutive_losses + 1
            print(f"\n[LIVE POSITION CLOSED] {sym} ({side.upper()}) | {reason}\n", flush=True)
            self.live_state["active"] = False

    def get_scorecard(self):
        tot_fixed = len(self.history_fixed_tp_sl)
        tot_fade = len(self.history_fade_exit)
        return (
            f"Fixed TP/SL: {sum(self.history_fixed_tp_sl)}/{tot_fixed} wins | "
            f"Fade Exit: {sum(self.history_fade_exit)}/{tot_fade} wins"
        )

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Dual-Procedure Vacuum Lab online.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                # 1. Update Observation Cameras & Live Trade
                self.update_cameras()
                self.poll_live_trade()

                # 2. Capital Safety Check
                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    print(f"[VAULT PAUSE] Balance ${balance:.2f} below ${self.equity_floor:.2f} floor. Sleeping...", flush=True)
                    time.sleep(30)
                    continue

                if self.consecutive_losses >= self.max_losses:
                    print("[VAULT PAUSE] 2 consecutive live losses. Rest period active. Sleeping...", flush=True)
                    time.sleep(60)
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

                        # Targets: +0.50% spot = +1.52% Net ROE on 4x leverage
                        if side == "long":
                            target_p = mid * 1.0050
                            stop_p = mid * 0.9965
                        else:
                            target_p = mid * 0.9950
                            stop_p = mid * 1.0035

                        # Live Promotion Check (Requires 7/10 wins on either procedure)
                        live_qualified = (
                            (len(self.history_fixed_tp_sl) >= 10 and sum(self.history_fixed_tp_sl[-10:]) >= 7)
                            or (len(self.history_fade_exit) >= 10 and sum(self.history_fade_exit[-10:]) >= 7)
                        )

                        if live_qualified and not self.live_state["active"]:
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
                                "start_time": time.time(), "max_minutes": 8.0
                            }
                            print(f"\n[LIVE PROMOTION TRADED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)
                            break
                        else:
                            # Open Paper Camera with Dual-Procedure Tracking
                            self.active_cameras.append({
                                "symbol": sym,
                                "side": side,
                                "entry_p": mid,
                                "target_p": target_p,
                                "stop_p": stop_p,
                                "min_resistance": vacuum["initial_resistance"],
                                "peak_price": mid,
                                "trough_price": mid,
                                "start_t": time.time(),
                                "fade_captured_roe": None,
                                "fade_time_m": None
                            })
                            print(f"\n[PAPER DUAL LAB LOCKED] {sym} ({side.upper()}) | {vacuum['reason']}", flush=True)

                # 5. Heartbeat Status
                if cycle % 6 == 0:
                    print(
                        f"\n[LAB HEARTBEAT] Cameras: {len(self.active_cameras)}/8 | "
                        f"Vault: ${balance:.2f} ({self.leverage}x) | "
                        f"Scorecard -> [{self.get_scorecard()}]",
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
    bot = DualProcedureVacuumBot()
    bot.run()

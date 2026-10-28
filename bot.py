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
BRAIN_FILE = "inertia_cascade_memory.json"

class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        wins = sum(bot.history_records)
        total = len(bot.history_records)
        losses = total - wins
        status = {
            "engine": "APEX-V16 Market Inertia & Cascade Engine",
            "mode": "DEMOTED_TO_PAPER (Needs 6/6 streak)" if bot.is_demoted else ("LIVE_READY" if bot.is_qualified_for_live() else "PAPER_QUALIFYING (Needs 9/10)"),
            "record": f"{wins} WINS / {losses} LOSSES",
            "active_cascades": len(bot.active_cameras),
            "live_trade_active": bot.live_state["active"],
            "tracked_markets": len(bot.cascade_memory)
        }
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] Keep-Alive active on port {PORT}", flush=True)

# ==============================================================================
# 2. MARKET INERTIA & CASCADE ENGINE
# ==============================================================================
class MarketInertiaBot:
    def __init__(self):
        # 1. Capital, Leverage & Risk Vault
        self.leverage = 4
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2
        self.is_demoted = False

        # 2. Cascade Requirements (Real Multi-Minute Inertia)
        self.MIN_10M_VOLUME_USD = 50_000.0   # Must have at least $50k fresh flow
        self.CASCADE_HOLD_MINUTES = 15.0     # 15 minutes natural cascade runtime
        
        # 3. Memory & Tracking
        self.history_records = []
        self.active_cameras = []
        self.cascade_memory = {}             # Multi-minute rolling price & volume history
        self.coin_cooldowns = {}             # Anti-revenge timeout
        self.load_brain()

        # 4. Live Trade State (Bound directly to self)
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

        # 5. Bitget Exchange Setup
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
            # Re-entry rule: 6 consecutive wins in a row (6/6)
            return len(self.history_records) >= 6 and sum(self.history_records[-6:]) == 6
        # Initial rule: 9 out of last 10 wins (9/10)
        return len(self.history_records) >= 10 and sum(self.history_records[-10:]) >= 9

    # --------------------------------------------------------------------------
    # AUDIT 10-MINUTE INERTIA & CASCADES (THE STEAMROLLER EFFECT)
    # --------------------------------------------------------------------------
    def audit_market_inertia(self, symbol, vol_24h, cur_price):
        """
        Audits sustained 10-15 minute trend momentum:
        1. Measures volume churned over the last 10 minutes.
        2. Measures total price displacement over the last 10 minutes.
        3. Identifies coins with heavy momentum where intermediate buyers/sellers
           get steamrolled and price continues moving in the trend direction.
        """
        if time.time() < self.coin_cooldowns.get(symbol, 0):
            return None

        now = time.time()
        if symbol not in self.cascade_memory:
            self.cascade_memory[symbol] = []

        self.cascade_memory[symbol].append({
            "t": now,
            "vol_24h": vol_24h,
            "price": cur_price
        })

        # Keep 25 minutes of history
        self.cascade_memory[symbol] = [s for s in self.cascade_memory[symbol] if now - s["t"] <= 1500.0]
        history = self.cascade_memory[symbol]

        # Find historical snapshot from 8.0 to 14.0 minutes ago
        past_snaps = [s for s in history if 480.0 <= (now - s["t"]) <= 840.0]
        if not past_snaps:
            return None

        baseline = past_snaps[0]
        elapsed_min = (now - baseline["t"]) / 60.0
        delta_vol_10m = vol_24h - baseline["vol_24h"]

        # Must have real sustained volume flow (filtering out dead illiquid coins)
        if delta_vol_10m < self.MIN_10M_VOLUME_USD:
            return None

        # Price displacement over the 10-minute window
        price_change_pct = ((cur_price - baseline["price"]) / baseline["price"]) * 100.0

        # ----------------------------------------------------------------------
        # SETUP 1: SHORT AVALANCHE (Relentless Selling Cascading Downwards)
        # Price has dropped -0.90% to -2.60% over 10 minutes with heavy volume.
        # Even if dip-buyers enter, the cascade momentum will keep dragging it down.
        # ----------------------------------------------------------------------
        if -2.60 <= price_change_pct <= -0.90:
            return {
                "symbol": symbol,
                "side": "short",
                "entry_price": cur_price,
                "reason": (
                    f"10M SHORT AVALANCHE: Price dumped {price_change_pct:.2f}% over {elapsed_min:.1f}m "
                    f"with ${delta_vol_10m:,.0f} volume! Heavy inertia will continue driving down."
                )
            }

        # ----------------------------------------------------------------------
        # SETUP 2: LONG RUNAWAY (Relentless Buying Cascading Upwards)
        # Price has surged +0.90% to +2.60% over 10 minutes with heavy volume.
        # Short-sellers get steamrolled as price continues upward.
        # ----------------------------------------------------------------------
        if 0.90 <= price_change_pct <= 2.60:
            return {
                "symbol": symbol,
                "side": "long",
                "entry_price": cur_price,
                "reason": (
                    f"10M LONG RUNAWAY: Price surged +{price_change_pct:.2f}% over {elapsed_min:.1f}m "
                    f"with ${delta_vol_10m:,.0f} volume! Relentless buying inertia intact."
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

            # Trailing Profit Shield: If trade hits +0.35% spot (+0.92% ROE), move stop to lock in +0.10% profit floor
            if delta >= 0.35 and not cam["trailed"]:
                cam["trailed"] = True
                cam["stop_p"] = entry * 1.0010 if side == "long" else entry * 0.9990
                stop = cam["stop_p"]

            hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
            hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
            timed_out = elapsed_m >= self.CASCADE_HOLD_MINUTES

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
                    print(f"Exit Price : {cur_price} (Entry: {entry})", flush=True)
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

        try:
            cur_price = float(self.bitget.fetch_ticker(sym).get('last', 0) or 0)
        except Exception:
            return

        delta = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        net_roe = (delta * self.leverage) - (0.06 * 2.0 * self.leverage)

        # Trailing Protection on Real Money
        if delta >= 0.35 and not self.live_state["trailed"]:
            self.live_state["trailed"] = True
            self.live_state["stop_price"] = entry * 1.0010 if side == "long" else entry * 0.9990
            stop = self.live_state["stop_price"]

        hit_target = (side == "long" and cur_price >= target) or (side == "short" and cur_price <= target)
        hit_stop = (side == "long" and cur_price <= stop) or (side == "short" and cur_price >= stop)
        timed_out = elapsed_m >= self.CASCADE_HOLD_MINUTES

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
                print(f"Live Strikes: {self.consecutive_live_losses}/{self.max_live_losses}", flush=True)

                if self.consecutive_live_losses >= self.max_live_losses:
                    self.is_demoted = True
                    print(f"\n[DEMOTION ACTIVE] 2 consecutive live losses! Must score 6/6 in paper to re-enter.\n", flush=True)

            self.save_brain()
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX-V16 Market Inertia & Cascade Bot online.", flush=True)

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
                # Prioritize highest volume coins
                candidates.sort(key=lambda s: float(tickers[s].get('quoteVolume', 0) or 0), reverse=True)

                # Scan for True 10-Minute Market Inertia Cascades
                for sym in candidates[:25]:
                    if len(self.active_cameras) >= 4:  # Maximum 4 high-inertia trades at a time
                        break

                    vol_24h = float(tickers[sym].get('quoteVolume', 0) or 0)
                    cur_p = float(tickers[sym].get('last', 0) or 0)
                    if cur_p <= 0:
                        continue

                    cascade = self.audit_market_inertia(sym, vol_24h, cur_p)

                    if cascade:
                        side = cascade["side"]
                        mid = cascade["entry_price"]

                        # Targets: +0.55% spot move = +1.72% Net ROE on 4x leverage
                        target_p = mid * 1.0055 if side == "long" else mid * 0.9945
                        stop_p = mid * 0.9960 if side == "long" else mid * 1.0040

                        # Check Qualification Status (9/10 initial or 6/6 re-entry)
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
                            print(f"\n[LIVE CASCADE EXECUTED] {sym} ({side.upper()}) | {cascade['reason']}", flush=True)
                            break
                        elif sym not in [c["symbol"] for c in self.active_cameras]:
                            self.active_cameras.append({
                                "symbol": sym, "side": side, "entry_p": mid,
                                "target_p": target_p, "stop_p": stop_p,
                                "trailed": False, "start_t": time.time()
                            })
                            print(f"\n[INERTIA CASCADE LOCKED] {sym} ({side.upper()}) | {cascade['reason']}", flush=True)

                if cycle % 6 == 0:
                    wins = sum(self.history_records)
                    losses = len(self.history_records) - wins
                    status = "DEMOTED (Need 6/6)" if self.is_demoted else ("LIVE_READY" if self.is_qualified_for_live() else f"{wins}/10 (Need 9/10)")
                    print(
                        f"[STATUS PULSE] Active Cascades: {len(self.active_cameras)}/4 | "
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
    bot = MarketInertiaBot()
    bot.run()

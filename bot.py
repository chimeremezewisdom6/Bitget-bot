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
BRAIN_FILE = "rotation_radar_memory.json"

bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX Dynamic Rotation & Screenshot Archetype Engine",
                "active_coin": bot.current_trade["symbol"] if bot.current_trade else "SCANNING",
                "standby_runner": bot.standby_runner["symbol"] if bot.standby_runner else "HUNTING",
                "streak_status": f"{bot.consecutive_paper_wins}/{bot.REQUIRED_WIN_STREAK} Wins in a row",
                "mode": "LIVE_AUTHORIZED" if bot.is_qualified_for_live() else "PAPER_QUALIFYING",
                "all_time_record": f"{bot.all_time_wins} Wins / {bot.all_time_losses} Losses",
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
# 2. DYNAMIC ROTATION & SCREENSHOT ARCHETYPE ENGINE
# ==============================================================================
class DynamicRotationBot:
    def __init__(self):
        # 1. Capital & Risk Configuration
        self.leverage = 1                      # Starts at 1x; dynamically adjusted for live
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        # 2. Qualification Controller (8-in-a-row)
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # 3. EMPIRICAL SCREENSHOT DNA (Hardcoded from your live test results)
        self.MAX_SAFE_ADVERSE_DRIFT = 0.35    # Screenshots proved real runs stay within 0.22%-0.26%
        self.MIN_FEE_SHIELD_PROFIT = 0.40     # Guaranteed exit floor to cover 0.12% fees + spread
        self.QUARANTINE_DURATION_SEC = 3600

        # Universe: Mid/Low-Cap Crypto Only ($600k to $10M Volume)
        self.MIN_24H_VOL_USD = 600_000.0
        self.MAX_24H_VOL_USD = 10_000_000.0

        # Strict Blacklist: Blocks all stocks, ETFs, and unlisted synthetics
        self.EXCLUSION_LIST = {
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'AVAX', 
            'LINK', 'SUI', 'PEPE', 'SHIB', 'NEAR', 'LTC', 'BCH', 'DOT', 'ZEC',
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU',
            'SKHYNIX', 'SKHY', 'SNDK', 'SNXX', 'BABA', 'COIN', 'MSTR', 'ARM', 'INTC', 
            'SMSN', 'EWY', 'AAOI', 'CRWV', 'ANTHROPIC', 'TQQQ'
        }

        # 4. Live Rotation & Standby States
        self.current_trade = None             # The active #1 Wildest Mover
        self.standby_runner = None            # The standby #2 Runner-up ready to rotate
        self.coin_cooldowns = {}
        self.load_brain()

        # 5. Live Trade State
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "target_price": 0.0, "stop_price": 0.0,
            "trailed": False, "start_time": 0.0
        }

        # 6. Bitget CCXT Initialization
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

    def record_trade_outcome(self, is_win, symbol, net_spot):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            self.coin_cooldowns[symbol] = time.time() + 600
            print(f"\n🔥 [ROTATION HARVESTED] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} in a row! Net Spot: +{net_spot:.2f}%", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK UNLOCKED] Real capital 90% allocation trading AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            self.consecutive_paper_wins = 0
            self.coin_cooldowns[symbol] = time.time() + self.QUARANTINE_DURATION_SEC
            print(f"\n💥 [FADE / STOPPED OUT] Resetting streak to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"🚫 [QUARANTINE] {symbol} locked out for 60 minutes.", flush=True)
        self.save_brain()

    # --------------------------------------------------------------------------
    # 1. LIVE TAPE RADAR (SCREENSHOT DIAGNOSTIC ENGINE)
    # --------------------------------------------------------------------------
    def get_tape_radar(self, symbol):
        try:
            trades = self.bitget.fetch_trades(symbol, limit=60)
            if not trades or len(trades) < 15:
                return None

            now_ms = time.time() * 1000
            recent = [t for t in trades if (now_ms - t['timestamp']) <= 90_000]
            if len(recent) < 8:
                return None

            buy_vol = sum([float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) for t in recent if t.get('side') == 'buy'])
            sell_vol = sum([float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) for t in recent if t.get('side') == 'sell'])
            total = buy_vol + sell_vol

            if total <= 0:
                return None

            buy_pct = (buy_vol / total) * 100.0
            sell_pct = (sell_vol / total) * 100.0
            cur_p = recent[-1]['price']

            # High-low range in last 90 seconds
            prices = [t['price'] for t in recent]
            range_pct = ((max(prices) - min(prices)) / min(prices)) * 100.0

            seq_code = "S0:CHOP"
            status_code = "BALANCED"

            # Sequence 1: Panic Dump / FOMO Hold ($20k+ volume with 90%+ skew)
            if buy_pct >= 88.0 and total >= 18_000:
                seq_code = "S1:FOMO_HOLD"
                status_code = "URGENT_BUY"
            elif sell_pct >= 88.0 and total >= 18_000:
                seq_code = "S1:PANIC_DUMP"
                status_code = "URGENT_SELL"

            # Sequence 2: Whale Push
            elif any(float(t.get('cost', 0.0) or (t.get('price', 0.0) * t.get('amount', 0.0))) >= 5_000 for t in recent):
                seq_code = "S2:WHALE_PUSH"
                status_code = "FILL_APPROACH"

            # Sequence 3: Underdog Blitz
            elif buy_pct >= 75.0 and total >= 8_000:
                seq_code = "S3:BLITZ_RUN"
                status_code = "RUNNING"
            elif sell_pct >= 75.0 and total >= 8_000:
                seq_code = "S3:BLITZ_BLEED"
                status_code = "RUNNING"

            return {
                "cur_price": cur_p,
                "buy_usd": buy_vol,
                "sell_usd": sell_vol,
                "buy_pct": buy_pct,
                "sell_pct": sell_pct,
                "range_pct": range_pct,
                "seq_code": seq_code,
                "status_code": status_code,
                "total_vol": total
            }
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 2. FIND WILDEST RANGE MOVERS (LEADER & STANDBY RUNNER)
    # --------------------------------------------------------------------------
    def find_wildest_movers(self, candidates):
        """Scans the market and ranks coins by active range displacement + tape velocity."""
        ranked = []
        for sym, vol_24h in candidates[:15]:
            tape = self.get_tape_radar(sym)
            if not tape:
                continue

            # Velocity Score: Range moved x Taker volume
            velocity_score = tape["range_pct"] * (tape["total_vol"] / 1000.0)
            
            # Must be actively bright (Sequence 1, 2, or 3)
            if tape["seq_code"] != "S0:CHOP" and tape["range_pct"] >= 0.35:
                side = "long" if tape["buy_pct"] >= tape["sell_pct"] else "short"
                ranked.append({
                    "symbol": sym,
                    "side": side,
                    "tape": tape,
                    "velocity_score": velocity_score
                })

        ranked.sort(key=lambda x: x["velocity_score"], reverse=True)
        leader = ranked[0] if len(ranked) > 0 else None
        standby = ranked[1] if len(ranked) > 1 else None
        return leader, standby

    # --------------------------------------------------------------------------
    # 3. ACTIVE TRADE SURFING: EXIT ON FADE / ROTATE TO STANDBY
    # --------------------------------------------------------------------------
    def update_active_trade(self):
        if not self.current_trade:
            return

        trade = self.current_trade
        sym = trade["symbol"]
        side = trade["side"]
        entry = trade["entry_p"]
        now = time.time()
        elapsed_s = now - trade["start_t"]

        tape = self.get_tape_radar(sym)
        if not tape:
            return

        cur_p = tape["cur_price"]
        gain_spot = ((cur_p - entry) / entry) * 100.0 if side == "long" else ((entry - cur_p) / entry) * 100.0

        # Update high-water peak
        trade["max_peak"] = max(trade.get("max_peak", 0.0), gain_spot)

        # Check for WALL_HIT / Absorption Trap (From Screenshot 4 & 10)
        # Volume is pouring in, but price progress is flat or slipping backwards
        is_wall_hit = (tape["total_vol"] >= 25_000 and abs(gain_spot - trade.get("last_spot", 0.0)) <= 0.02)
        trade["last_spot"] = gain_spot

        # FADE CONDITIONS:
        # 1. Price reached a peak and pulled back by >= 0.25%
        # 2. It hits a WALL_HIT absorption barrier
        # 3. Adverse drift exceeds the 0.35% Screenshot Shield
        has_faded = (trade["max_peak"] >= 1.0 and (trade["max_peak"] - gain_spot) >= 0.25) or is_wall_hit
        hit_stop = gain_spot <= -self.MAX_SAFE_ADVERSE_DRIFT
        timed_out = elapsed_s >= 600  # Max 10 minutes (wild moves happen fast)

        # Single-Line Compact Telemetry Radar
        b_k = int(tape["buy_usd"] / 1000)
        s_k = int(tape["sell_usd"] / 1000)
        bias_str = f"{int(tape['buy_pct'])}%B" if tape['buy_pct'] >= tape['sell_pct'] else f"{int(tape['sell_pct'])}%S"
        t_str = time.strftime("%H:%M:%S", time.localtime(now))
        base_sym = sym.split('/')[0]

        status_tag = "BRIGHTENING"
        if is_wall_hit:
            status_tag = "WALL_HIT"
        elif has_faded:
            status_tag = "FADING"
        elif gain_spot >= trade["max_peak"] and gain_spot > 0.6:
            status_tag = "PEAK_NEW"

        print(
            f"[{t_str}] {base_sym:<6} | Spot:{gain_spot:+.2f}% (Peak:{trade['max_peak']:+.2f}%) | "
            f"FLOW: B${b_k}k/S${s_k}k ({bias_str}) | {tape['seq_code']} | {status_tag}",
            flush=True
        )

        # EXIT EXECUTION
        if has_faded or hit_stop or timed_out:
            # Fee Shield check: Did we exit with net positive after 0.12% roundtrip fees + spread?
            is_win = (gain_spot >= self.MIN_FEE_SHIELD_PROFIT)

            print(f"\n=======================================================", flush=True)
            if is_win:
                print(f"🟢 [MOMENTUM FADED: EXITING WITH PROFIT!]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Spot Gain: {gain_spot:+.2f}%", flush=True)
                print(f"Duration   : {elapsed_s/60.0:.1f} minutes | Net Fee Shield: CLEARED", flush=True)
            else:
                print(f"🔴 [FADE / ADVERSE STOPPED OUT]", flush=True)
                print(f"Coin       : {sym} ({side.upper()}) | Spot Result: {gain_spot:+.2f}%", flush=True)

            self.record_trade_outcome(is_win, sym, gain_spot)
            print(f"=======================================================\n", flush=True)

            self.current_trade = None

            # INSTANT ROTATION TO STANDBY RUNNER
            if self.standby_runner and time.time() >= self.coin_cooldowns.get(self.standby_runner["symbol"], 0):
                nxt = self.standby_runner
                print(f"⚡ [HOT-SWAP ROTATION] Seamlessly rotating into Standby Leader: {nxt['symbol']} ({nxt['side'].upper()})!\n", flush=True)
                self.current_trade = {
                    "symbol": nxt["symbol"],
                    "side": nxt["side"],
                    "entry_p": nxt["tape"]["cur_price"],
                    "start_t": time.time(),
                    "max_peak": 0.0,
                    "last_spot": 0.0
                }
                self.standby_runner = None

    # --------------------------------------------------------------------------
    # 4. LIVE TRADE CONTROLLER (90% BALANCE & DYNAMIC MINIMUM LEVERAGE)
    # --------------------------------------------------------------------------
    def poll_live_trade(self):
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        side = self.live_state["side"]
        entry = self.live_state["entry_price"]
        elapsed_s = time.time() - self.live_state["start_time"]

        tape = self.get_tape_radar(sym)
        if not tape:
            return

        cur_p = tape["cur_price"]
        gain_spot = ((cur_p - entry) / entry) * 100.0 if side == "long" else ((entry - cur_p) / entry) * 100.0

        is_wall_hit = (tape["total_vol"] >= 25_000 and abs(gain_spot - self.live_state.get("last_spot", 0.0)) <= 0.02)
        self.live_state["last_spot"] = gain_spot

        self.live_state["max_peak"] = max(self.live_state.get("max_peak", 0.0), gain_spot)
        has_faded = (self.live_state["max_peak"] >= 1.0 and (self.live_state["max_peak"] - gain_spot) >= 0.25) or is_wall_hit
        hit_stop = gain_spot <= -self.MAX_SAFE_ADVERSE_DRIFT
        timed_out = elapsed_s >= 600

        if has_faded or hit_stop or timed_out:
            is_win = (gain_spot >= self.MIN_FEE_SHIELD_PROFIT)
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
                print(f"🟢 [LIVE TRADE FADE EXIT: +{gain_spot:.2f}% SPOT]", flush=True)
            else:
                self.consecutive_live_losses += 1
                print(f"🔴 [LIVE TRADE STOPPED: {gain_spot:.2f}% SPOT]", flush=True)
                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] Resetting streak back to paper qualification.\n", flush=True)
                    self.consecutive_paper_wins = 0

            self.record_trade_outcome(is_win, sym, gain_spot)
            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # 5. ENGINE SCANNER LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX Dynamic Rotation & Screenshot Archetype Bot online.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} swap pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load warning: {e}", flush=True)

        cycle = 0

        while True:
            try:
                self.update_active_trade()
                self.poll_live_trade()

                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    time.sleep(20)
                    continue

                try:
                    tickers = self.bitget.fetch_tickers()
                except Exception:
                    time.sleep(3)
                    continue

                # Filter strictly for real mid/low-cap crypto perps ($600k to $10M)
                candidates = []
                for s, t in tickers.items():
                    if not s.endswith(":USDT"):
                        continue
                    base = s.split('/')[0].split(':')[0].upper()
                    if base in self.EXCLUSION_LIST:
                        continue

                    vol = float(t.get('quoteVolume', 0) or 0)
                    if self.MIN_24H_VOL_USD <= vol <= self.MAX_24H_VOL_USD and time.time() >= self.coin_cooldowns.get(s, 0):
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)

                # Scan for wildest range leader and standby runner
                leader, standby = self.find_wildest_movers(candidates)
                if standby:
                    self.standby_runner = standby

                # If no trade is active, enter the brightening leader
                if not self.current_trade and leader:
                    sym = leader["symbol"]
                    side = leader["side"]
                    mid = leader["tape"]["cur_price"]

                    if self.is_qualified_for_live() and not self.live_state["active"]:
                        # 90% Balance Rule & Dynamic Minimum Leverage
                        margin_90 = balance * 0.90
                        exchange_min_notional = 5.25
                        needed_leverage = max(int(exchange_min_notional / margin_90) + 1, 1)

                        try:
                            self.bitget.set_leverage(needed_leverage, sym)
                        except Exception:
                            pass

                        notional_size = margin_90 * needed_leverage
                        amount = float(self.bitget.amount_to_precision(sym, notional_size / mid))
                        order_side = 'buy' if side == 'long' else 'sell'
                        self.bitget.create_order(sym, 'market', order_side, amount)

                        self.live_state = {
                            "active": True, "symbol": sym, "side": side,
                            "contracts": amount, "entry_price": mid,
                            "start_time": time.time(),
                            "max_peak": 0.0, "last_spot": 0.0
                        }
                        print(f"\n[LIVE 90% ALLOCATION] {sym} ({side.upper()}) | Leverage: {needed_leverage}x | Margin: ${margin_90:.2f}", flush=True)

                    else:
                        self.current_trade = {
                            "symbol": sym,
                            "side": side,
                            "entry_p": mid,
                            "start_t": time.time(),
                            "max_peak": 0.0,
                            "last_spot": 0.0
                        }
                        standby_name = self.standby_runner["symbol"] if self.standby_runner else "None"
                        print(f"\n🚀 [BRIGHTEN ENTRY] {sym} ({side.upper()}) | Standby Runner: {standby_name} locked on radar.", flush=True)

                if cycle % 10 == 0:
                    status_desc = "LIVE_AUTHORIZED" if self.is_qualified_for_live() else f"PAPER_QUALIFYING ({self.consecutive_paper_wins}/8)"
                    active_name = self.current_trade["symbol"] if self.current_trade else "SCANNING"
                    standby_name = self.standby_runner["symbol"] if self.standby_runner else "None"
                    print(
                        f"[ROTATION PULSE] Active: {active_name} | Standby: {standby_name} | "
                        f"Vault: ${balance:.2f} | Streak: {self.consecutive_paper_wins}/8 | Status: {status_desc}",
                        flush=True
                    )

                cycle += 1
                time.sleep(3)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(4)

# ==============================================================================
# START BOT
# ==============================================================================
if __name__ == "__main__":
    bot = DynamicRotationBot()
    bot.run()

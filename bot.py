import os
import sys
import time
import json
import math
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. 1-CLICK WEB DASHBOARD (PORT 10000)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
MEMORY_FILE = "multi_big_trade_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "PATROLLING_5_BIG_SETUPS")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            active_setup = bot.current_trade.get("setup", "NONE") if bot.current_trade else (bot.live_state.get("setup", "NONE") if bot.live_state["active"] else "SCANNING")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            streak_seq = " ".join([str(i) for i in range(1, bot.consecutive_paper_wins + 1)]) if bot.consecutive_paper_wins > 0 else "0"
            mode_badge = "LIVE AUTHORIZED (6/6 UNLOCKED)" if bot.is_live_authorized() else f"PAPER QUALIFYING ({bot.consecutive_paper_wins}/6)"

            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Multi Big-Trade Engine</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; background: #080d1a; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #111a2e; border-radius: 12px; padding: 18px; margin-bottom: 15px; border: 1px solid #1e293b; }}
                    .stat {{ font-size: 24px; font-weight: bold; color: #38bdf8; margin: 4px 0; }}
                    .green {{ color: #4ade80; }}
                    .red {{ color: #f87171; }}
                    .gold {{ color: #fbbf24; font-weight: bold; }}
                    .badge {{ background: #2563eb; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold; }}
                    .badge-live {{ background: #16a34a; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold; }}
                    .title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="title">6-Win Qualification Controller</div>
                    <div class="stat"><span class="{'badge-live' if bot.is_live_authorized() else 'badge'}">{mode_badge}</span></div>
                    <div>Streak Sequence: <span class="gold">[{streak_seq}] ({bot.consecutive_paper_wins}/6 in a row)</span></div>
                    <div>All-Time Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">Active Big-Trade Position</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>Setup: <span class="gold">[{active_setup}]</span></div>
                    <div>Current PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b> | State: <b>{bot.current_stage}</b></div>
                </div>
                <div class="card">
                    <div class="title">Account Vault & Market Scope</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Liquid Market Pool: <b>{len(bot.all_liquid_candidates)} Pairs ($1M+)</b></div>
                    <div>Status: <i>{bot.last_10m_summary}</i></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • Multi Big-Trade Engine</div>
            </body>
            </html>"""
        else:
            html = "<h3>Bot Initializing... refresh in 5 seconds.</h3>"
            
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[SYSTEM] 1-Click Dashboard live on port {PORT}", flush=True)

# ==============================================================================
# 2. MULTI BIG-TRADE ENGINE
# ==============================================================================
class MultiBigTradeBot:
    def __init__(self):
        self.equity_floor = 1.05
        self.ROUNDTRIP_FEE_PCT = 0.12

        # 6-WIN-IN-A-ROW QUALIFICATION
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 6       # 1, 2, 3, 4, 5, 6 in a row!
        self.all_time_wins = 0
        self.all_time_losses = 0

        # MARKET SPECIFICATIONS
        self.MIN_24H_VOLUME_USD = 1_000_000.0  # $1,000,000+ Volume Universe
        self.MIN_IMBALANCE_RATIO = 2.2         # Dominant side must be >= 2.2x stronger than opponent
        self.MAX_SPREAD_PCT = 0.0010           # Tight spread <= 0.10% (Anti-Trap)
        self.MIN_RVOL = 1.70                   # Volume >= 1.70x (Anti-Luck)
        self.SMOOTH_MAX_PULLBACK = 0.50        # Pullback during 4% move must be < 0.50%

        self.coin_cooldowns = {}
        self.all_liquid_candidates = []
        self.global_volume_whitelist = set()

        self.last_summary_time = 0.0
        self.last_balance = 1.33
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.current_stage = "PATROLLING_5_BIG_SETUPS"
        self.last_10m_summary = "Patrolling $1M+ pairs across all 5 Big-Trade setups..."

        # Universal Exclusion List (No synthetics or flatline commodities)
        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'EUV', 'CSOP', 'TQQQ', 'PARTI', 'BTW', 'IDOL'
        }

        self.current_trade = None
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "pivot_point": 0.0, "setup": "", "start_time": 0.0,
            "max_peak": 0.0
        }

        self.api_key = (os.environ.get("API_KEY") or "").strip()
        self.secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        self.passphrase = (os.environ.get("PASSPHRASE") or "").strip()

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing credentials in Render!", flush=True)
            sys.exit(1)

        self.bitget = ccxt.bitget({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "defaultMarginMode": "cross"}
        })

        self.enforce_one_way_mode()
        self.load_memory()
        self.recover_existing_position()

        t_global = threading.Thread(target=self.global_volume_worker, daemon=True)
        t_global.start()

    def is_live_authorized(self):
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    def enforce_one_way_mode(self):
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
        except Exception:
            pass

    def recover_existing_position(self):
        try:
            positions = self.bitget.fetch_positions()
            has_live = False
            for p in positions:
                contracts = abs(float(p.get('contracts', 0) or 0))
                sym = p.get('symbol')
                if contracts > 0 and sym not in self.EXCLUSION_LIST:
                    pos_side = str(p.get('side', '')).lower()
                    side = 'short' if pos_side == 'short' else 'long'
                    entry_price = float(p.get('entryPrice') or 0.0)

                    self.live_state = {
                        "active": True, "symbol": sym, "side": side,
                        "contracts": contracts, "entry_price": entry_price,
                        "pivot_point": entry_price, "setup": "RECOVERED_LIVE",
                        "start_time": time.time(), "max_peak": 0.0
                    }
                    has_live = True
                    print(f"\n🔄 [AUTO-RECOVERY] Resumed tracking live {side.upper()} on {sym} ({contracts} contracts)\n", flush=True)
                    break

            if not has_live:
                self.live_state["active"] = False
                self.live_state["symbol"] = None
        except Exception as e:
            print(f"[RECOVERY NOTE] No active position: {e}", flush=True)

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    self.consecutive_paper_wins = data.get("consecutive_paper_wins", 0)
                    self.all_time_wins = data.get("all_time_wins", 0)
                    self.all_time_losses = data.get("all_time_losses", 0)
                    print(f"[MEMORY] Loaded: Streak {self.consecutive_paper_wins}/6 | {self.all_time_wins}W - {self.all_time_losses}L", flush=True)
            except Exception:
                pass

    def save_memory(self):
        tmp_file = f"{MEMORY_FILE}.tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump({
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses
                }, f, indent=2)
            os.replace(tmp_file, MEMORY_FILE)
        except Exception:
            pass

    def global_volume_worker(self):
        while True:
            new_whitelist = set()
            try:
                for start in [0, 100, 200, 300, 400, 500]:
                    url = f"https://api.coinlore.net/api/tickers/?start={start}&limit=100"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=12) as response:
                        res = json.loads(response.read().decode())
                        data = res.get("data", [])
                        if not data:
                            break
                        for item in data:
                            sym = item.get("symbol", "").upper()
                            vol_usd = float(item.get("volume24", 0.0) or 0.0)
                            if vol_usd >= self.MIN_24H_VOLUME_USD:
                                new_whitelist.add(sym)
                    time.sleep(0.35)

                if len(new_whitelist) >= 40:
                    self.global_volume_whitelist = new_whitelist
            except Exception:
                pass
            time.sleep(600)

    # --------------------------------------------------------------------------
    # 1. MEASURE 30-MINUTE INTERNAL BATTLE (LONG VS SHORT ON SAME COIN)
    # --------------------------------------------------------------------------
    def calculate_30m_internal_power(self, symbol):
        try:
            candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=8)
            if not candles_5m or len(candles_5m) < 6:
                return None

            completed_30m = candles_5m[-6:]
            bull_power, bear_power = 0.0, 0.0

            for c in completed_30m:
                o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                total_range = h - l
                if total_range <= 0:
                    continue

                body_ratio = abs(cl - o) / total_range
                if cl > o:
                    bull_power += vol * (0.5 + 0.5 * body_ratio)
                elif cl < o:
                    bear_power += vol * (0.5 + 0.5 * body_ratio)

            if bull_power <= 0 or bear_power <= 0:
                return None

            if bull_power >= bear_power:
                return ("long", bull_power / bear_power)
            else:
                return ("short", bear_power / bull_power)
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 2. SCREEN 5 BIG-PROFIT TRADE SETUPS (NO PARALYSIS)
    # --------------------------------------------------------------------------
    def inspect_5_big_trade_setups(self, symbol, side):
        """
        Screens across 5 institutional big-profit setups:
        1. Smooth 4% Run (<0.50% pullback)
        2. Three 5m Blowout Candles (40-0 Win)
        3. Capitulation V-Rebound (Dumped >= 12% in 24h, climax bottom turn)
        4. Coiled Spring Breakout (Tight <1.8% box for 24h, explosive break)
        5. Gravity Elevator Short (Pumped >= 25% in 2-3 days, 24h floor breaks)
        """
        try:
            # Fetch 5m candles for micro execution
            c_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=24)
            if not c_5m or len(c_5m) < 20:
                return None

            comp_5m = c_5m[:-1]
            last_3_5m = comp_5m[-3:]
            cur_price = comp_5m[-1][4]

            # Fetch 1D / 4H candles for macro setups
            c_1d = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=5)
            if not c_1d or len(c_1d) < 3:
                return None

            high_24h = max(c_1d[-2][2], c_1d[-1][2])
            low_24h = min(c_1d[-2][3], c_1d[-1][3])
            high_48h = max([x[2] for x in c_1d[-3:]])
            low_48h = min([x[3] for x in c_1d[-3:]])

            # ------------------------------------------------------------------
            # SETUP 1: SMOOTH 4% RUN (< 0.50% PULLBACK)
            # ------------------------------------------------------------------
            for i in range(len(comp_5m) - 2, max(len(comp_5m) - 18, 0), -1):
                start_p = comp_5m[i][3] if side == "long" else comp_5m[i][2]
                net_move = ((cur_price - start_p) / start_p) * 100.0 if side == "long" else ((start_p - cur_price) / start_p) * 100.0

                if 3.8 <= net_move <= 6.8:
                    run_bars = comp_5m[i:]
                    running_extreme = run_bars[0][2] if side == "long" else run_bars[0][3]
                    max_pullback = 0.0

                    for c in run_bars:
                        if side == "long":
                            running_extreme = max(running_extreme, c[2])
                            pb = ((running_extreme - c[3]) / running_extreme) * 100.0
                        else:
                            running_extreme = min(running_extreme, c[3])
                            pb = ((c[2] - running_extreme) / running_extreme) * 100.0
                        max_pullback = max(max_pullback, pb)

                    if max_pullback < self.SMOOTH_MAX_PULLBACK:
                        return ("SMOOTH_4_PERCENT_RUN", start_p, net_move)

            # ------------------------------------------------------------------
            # SETUP 2: THREE 5M BLOWOUT CANDLES (40-0 WIN)
            # ------------------------------------------------------------------
            blowout_ok = True
            for c in last_3_5m:
                o, h, l, cl = c[1], c[2], c[3], c[4]
                rng = h - l
                if rng <= 0:
                    blowout_ok = False
                    break
                if side == "long":
                    if cl <= o or ((h - cl) / rng) > 0.18:
                        blowout_ok = False
                        break
                elif side == "short":
                    if cl >= o or ((cl - l) / rng) > 0.18:
                        blowout_ok = False
                        break

            if blowout_ok:
                gain_3b = ((cur_price - last_3_5m[0][1]) / last_3_5m[0][1]) * 100.0 if side == "long" else ((last_3_5m[0][1] - cur_price) / last_3_5m[0][1]) * 100.0
                if gain_3b >= 1.2:
                    pivot = last_3_5m[0][3] if side == "long" else last_3_5m[0][2]
                    return ("3_BLOWOUT_CANDLES", pivot, gain_3b)

            # ------------------------------------------------------------------
            # SETUP 3: CAPITULATION V-REBOUND (LONG ONLY)
            # ------------------------------------------------------------------
            if side == "long":
                drop_24h = ((high_24h - low_24h) / high_24h) * 100.0
                if drop_24h >= 12.0:
                    # Check if 5m is recovering strongly off the floor
                    bounce_from_floor = ((cur_price - low_24h) / low_24h) * 100.0
                    if 1.5 <= bounce_from_floor <= 5.0 and comp_5m[-1][4] > comp_5m[-1][1]:
                        return ("CAPITULATION_V_REBOUND", low_24h, bounce_from_floor)

            # ------------------------------------------------------------------
            # SETUP 4: COILED SPRING BREAKOUT
            # ------------------------------------------------------------------
            # Check if previous 24h was compressed (< 2.2% range)
            range_yesterday = ((c_1d[-2][2] - c_1d[-2][3]) / c_1d[-2][3]) * 100.0
            if range_yesterday <= 2.2:
                # Today breaking out of yesterday's ceiling/floor with momentum
                if side == "long" and cur_price > c_1d[-2][2]:
                    breakout_pct = ((cur_price - c_1d[-2][2]) / c_1d[-2][2]) * 100.0
                    if 0.5 <= breakout_pct <= 3.5:
                        return ("COILED_SPRING_BREAKOUT", c_1d[-2][2], breakout_pct)
                elif side == "short" and cur_price < c_1d[-2][3]:
                    breakout_pct = ((c_1d[-2][3] - cur_price) / c_1d[-2][3]) * 100.0
                    if 0.5 <= breakout_pct <= 3.5:
                        return ("COILED_SPRING_BREAKOUT", c_1d[-2][3], breakout_pct)

            # ------------------------------------------------------------------
            # SETUP 5: POST-PUMP GRAVITY ELEVATOR SHORT (SHORT ONLY)
            # ------------------------------------------------------------------
            if side == "short":
                pump_48h = ((high_48h - low_48h) / low_48h) * 100.0
                if pump_48h >= 25.0:
                    # Price is breaking below the 24h support floor
                    if cur_price < low_24h:
                        breakdown_pct = ((low_24h - cur_price) / low_24h) * 100.0
                        if 0.4 <= breakdown_pct <= 3.0:
                            return ("GRAVITY_ELEVATOR_SHORT", low_24h, breakdown_pct)

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 3. ANTI-TRAP & ANTI-LUCK GAUNTLET
    # --------------------------------------------------------------------------
    def verify_authenticity(self, symbol):
        # 1. Spread Check (No illiquid vacuum traps)
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=5)
            bids, asks = ob.get('bids', []), ob.get('asks', [])
            if not bids or not asks:
                return False, "Empty order book"
            mid = (bids[0][0] + asks[0][0]) / 2.0
            spread = (asks[0][0] - bids[0][0]) / mid
            if spread > self.MAX_SPREAD_PCT:
                return False, f"Spread wide ({spread*100:.2f}%)"
        except Exception:
            return False, "Order book check failed"

        # 2. Volume Check (No fake dead drifts)
        try:
            c_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=18)
            if not c_15m or len(c_15m) < 14:
                return False, "Not enough 15m candles"
            completed = c_15m[:-1]
            avg_vol = sum([x[5] for x in completed[-12:]]) / 12.0
            rvol = completed[-1][5] / avg_vol if avg_vol > 0 else 1.0
            if rvol < self.MIN_RVOL:
                return False, f"Low volume ({rvol:.1f}x)"
        except Exception:
            return False, "Volume check failed"

        return True, "QUALIFIED"

    # --------------------------------------------------------------------------
    # 4. PATROL & SEQUENTIAL SELECTION
    # --------------------------------------------------------------------------
    def scan_for_market_champion(self, candidates):
        ranked = []
        now = time.time()

        for sym, _ in candidates[:45]:
            if now < self.coin_cooldowns.get(sym, 0):
                continue
            res = self.calculate_30m_internal_power(sym)
            if res:
                side, ratio = res
                if ratio >= self.MIN_IMBALANCE_RATIO:
                    ranked.append({"symbol": sym, "side": side, "ratio": ratio})

        if not ranked:
            return None

        ranked.sort(key=lambda x: x["ratio"], reverse=True)

        # Inspect candidates sequentially across the 5 big-profit setups
        for cand in ranked[:8]:
            sym = cand["symbol"]
            side = cand["side"]

            is_valid, _ = self.verify_authenticity(sym)
            if is_valid:
                trigger = self.inspect_5_big_trade_setups(sym, side)
                if trigger:
                    setup_name, pivot, move = trigger
                    return {
                        "symbol": sym, "side": side, "ratio": cand["ratio"],
                        "pivot": pivot, "setup": setup_name, "move": move,
                        "desc": f"{sym} ({side.upper()}) | Power Gap: {cand['ratio']:.1f}x | Setup: {setup_name} ({move:.2f}%)"
                    }

        return None

    # --------------------------------------------------------------------------
    # 5. RECORD RESULT (1, 2, 3, 4, 5, 6 IN A ROW)
    # --------------------------------------------------------------------------
    def record_trade_result(self, is_win, symbol, net_spot):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            streak_seq = ", ".join([str(i) for i in range(1, self.consecutive_paper_wins + 1)])
            print(f"\n🏆 [WIN RECORDED] {symbol} | Result: {net_spot:+.2f}%", flush=True)
            print(f"🔥 STREAK PROGRESS: {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} In a Row ({streak_seq})", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉🎉 [6/6 STREAK UNLOCKED!] (1, 2, 3, 4, 5, 6 IN A ROW ACHIEVED) -> LIVE TRADING AUTHORIZED! 🎉🎉\n", flush=True)
        else:
            self.all_time_losses += 1
            print(f"\n💥 [LOSS RECORDED] {symbol} | Result: {net_spot:+.2f}%", flush=True)
            print(f"⚠️ STREAK RESET: Resetting back to 0/{self.REQUIRED_WIN_STREAK}\n", flush=True)
            self.consecutive_paper_wins = 0

        self.save_memory()

    # --------------------------------------------------------------------------
    # 6. DYNAMIC RUNNER MANAGEMENT (BIG PROFIT ORIENTED)
    # --------------------------------------------------------------------------
    def manage_active_trade(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
            self.current_stage = "PATROLLING_5_BIG_SETUPS"
            return

        sym = trade["symbol"]
        side = trade["side"]
        entry = trade["entry_price"]
        pivot = trade["pivot_point"]
        elapsed_hours = (time.time() - trade["start_time"]) / 3600.0
        self.last_held_hours = elapsed_hours

        try:
            ticker = self.bitget.fetch_ticker(sym)
            cur_price = float(ticker.get('last') or 0.0)
            if cur_price == 0:
                return

            candles_5m = self.bitget.fetch_ohlcv(sym, timeframe='5m', limit=10)
            closes_5m = [x[4] for x in candles_5m]
            ema9_5m = sum(closes_5m[-9:]) / 9.0
        except Exception:
            return

        gain_pct = ((cur_price - entry) / entry) * 100.0 if side == "long" else ((entry - cur_price) / entry) * 100.0
        trade["max_peak"] = max(trade.get("max_peak", 0.0), gain_pct)
        peak = trade["max_peak"]

        self.last_spot_gain = gain_pct
        self.last_peak_gain = peak

        should_exit = False
        is_win = False
        exit_reason = ""

        # DYNAMIC RUNNER EXITS
        # 1. Harvest Big Expansion (Peaked high and begins rolling over)
        if peak >= 4.0 and (peak - gain_pct) >= 1.3:
            self.current_stage = "BIG_PROFIT_HARVEST"
            should_exit = True
            is_win = True
            exit_reason = f"PROFIT HARVEST: Peaked at +{peak:.1f}%, secured at +{gain_pct:.1f}% -> 100% USDT"

        # 2. 5M Trend Inversion (After capturing solid move >= +1.8%)
        elif gain_pct >= 1.8 and ((side == "long" and cur_price < ema9_5m) or (side == "short" and cur_price > ema9_5m)):
            self.current_stage = "TREND_INVERTED"
            should_exit = True
            is_win = True
            exit_reason = f"MOMENTUM EXHAUSTED: 5m EMA inverting at +{gain_pct:.2f}% -> 100% USDT"

        # 3. Pivot Invalidation (Cut loss if entry floor breached)
        elif (side == "long" and cur_price < pivot * 0.991) or (side == "short" and cur_price > pivot * 1.009):
            self.current_stage = "PIVOT_INVALIDATION"
            should_exit = True
            is_win = False
            exit_reason = f"DOMINANCE LOST: Entry floor breached ({gain_pct:+.2f}%)"

        # 4. Stagnant trade (No continuation after 2.5 hours)
        elif elapsed_hours >= 2.5 and gain_pct < 0.2:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"STALLED: No follow-through after {elapsed_hours:.1f}h"

        if should_exit:
            print(f"\n🛑 [EXIT EXECUTED] {sym} | Reason: {exit_reason} | Net: {gain_pct:+.2f}%\n", flush=True)
            self.record_trade_result(is_win, sym, gain_pct)
            self.coin_cooldowns[sym] = time.time() + 900  # 15 min cooldown

            if self.live_state["active"]:
                self.close_live_position(sym)
            self.current_trade = None

    def close_live_position(self, sym):
        try:
            positions = self.bitget.fetch_positions([sym])
            has_open = False
            for p in positions:
                if p.get('symbol') == sym and abs(float(p.get('contracts', 0) or 0)) > 0:
                    has_open = True
                    contracts = abs(float(p.get('contracts', 0) or 0))
                    close_side = 'sell' if self.live_state["side"] == 'long' else 'buy'
                    try:
                        self.bitget.create_order(sym, 'market', close_side, contracts, params={'reduceOnly': True})
                    except Exception:
                        self.bitget.create_order(sym, 'market', close_side, contracts, params={'reduceOnly': True, 'tradeSide': 'close'})
                    print(f"[LIVE CLOSED] Closed {contracts} contracts on {sym} -> 100% USDT", flush=True)
                    break

            if not has_open:
                print(f"[SYNC] {sym} was already closed on Bitget. Memory reset.", flush=True)
        except Exception as e:
            print(f"[EXIT ERROR] {e}. Resetting state.", flush=True)
        finally:
            self.live_state["active"] = False
            self.live_state["symbol"] = None

    # --------------------------------------------------------------------------
    # 7. MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] Multi Big-Trade Engine Online ($1M+ Universe & 5 High-Profit Setups Active).", flush=True)

        try:
            self.bitget.load_markets()
        except Exception:
            pass

        while True:
            try:
                self.manage_active_trade()

                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                self.last_balance = balance

                tickers = self.bitget.fetch_tickers()

                candidates = []
                for s, t in tickers.items():
                    if not s.endswith(":USDT"):
                        continue
                    base = s.split('/')[0].split(':')[0].upper()
                    if base in self.EXCLUSION_LIST:
                        continue
                    vol = float(t.get('quoteVolume', 0) or 0)
                    if (vol >= self.MIN_24H_VOLUME_USD) or (base in self.global_volume_whitelist):
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)
                self.all_liquid_candidates = candidates

                if not self.current_trade and not self.live_state["active"]:
                    champion = self.scan_for_market_champion(candidates)
                    if champion:
                        sym = champion["symbol"]
                        side = champion["side"]
                        setup = champion["setup"]
                        desc = champion["desc"]
                        mid = float(tickers[sym]['last'])

                        print(f"\n🚨 [BIG-TRADE CHAMPION ISOLATED: {side.upper()}] {sym} at ${mid}", flush=True)
                        print(f"📊 {desc}\n", flush=True)

                        if self.is_live_authorized():
                            margin_alloc = balance * 0.90
                            exchange_min = 5.50
                            needed_lev = min(max(math.ceil(exchange_min / margin_alloc), 1), 20)

                            try:
                                self.bitget.set_leverage(needed_lev, sym, params={'marginCoin': 'USDT'})
                            except Exception:
                                try:
                                    self.bitget.set_leverage(needed_lev, sym)
                                except Exception:
                                    pass

                            notional = margin_alloc * needed_lev
                            amount = float(self.bitget.amount_to_precision(sym, notional / mid))
                            order_side = 'buy' if side == 'long' else 'sell'

                            try:
                                try:
                                    self.bitget.create_order(sym, 'market', order_side, amount)
                                except Exception:
                                    self.bitget.create_order(sym, 'market', order_side, amount, params={'tradeSide': 'open'})

                                self.live_state = {
                                    "active": True, "symbol": sym, "side": side,
                                    "contracts": amount, "entry_price": mid,
                                    "pivot_point": champion["pivot"], "setup": setup,
                                    "start_time": time.time(), "max_peak": 0.0
                                }
                                print(f"✅ [LIVE TRADE OPENED] {sym} | Margin: ${margin_alloc:.2f} | Leverage: {needed_lev}x\n", flush=True)
                            except Exception as err:
                                print(f"⚠️ Live order note: {err}. Falling back to paper trade.\n", flush=True)
                                self.current_trade = {
                                    "symbol": sym, "side": side, "setup": setup,
                                    "entry_price": mid, "pivot_point": champion["pivot"],
                                    "start_time": time.time(), "max_peak": 0.0
                                }
                        else:
                            self.current_trade = {
                                "symbol": sym, "side": side, "setup": setup,
                                "entry_price": mid, "pivot_point": champion["pivot"],
                                "start_time": time.time(), "max_peak": 0.0
                            }
                            print(f"📝 [PAPER QUALIFYING TRADE OPENED] {sym} ({side.upper()}) | Setup: {setup} | Goal: {self.consecutive_paper_wins}/6 -> {self.consecutive_paper_wins+1}/6\n", flush=True)

                # CLEAN 10-MINUTE SUMMARY
                now = time.time()
                if now - self.last_summary_time >= 600:
                    self.last_summary_time = now
                    t_str = time.strftime("%H:%M:%S", time.localtime(now))
                    streak_status = "LIVE_AUTHORIZED" if self.is_live_authorized() else f"PAPER_STREAK ({self.consecutive_paper_wins}/6)"
                    streak_seq = " ".join([str(i) for i in range(1, self.consecutive_paper_wins + 1)]) if self.consecutive_paper_wins > 0 else "0"

                    if self.live_state["active"] or self.current_trade:
                        sym = self.live_state["symbol"] if self.live_state["active"] else self.current_trade["symbol"]
                        side = self.live_state["side"] if self.live_state["active"] else self.current_trade["side"]
                        setup_active = self.live_state["setup"] if self.live_state["active"] else self.current_trade.get("setup", "UNKNOWN")
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) [{setup_active}] | PnL: {self.last_spot_gain:+.2f}% | Streak: [{streak_seq}] ({self.consecutive_paper_wins}/6)"
                    else:
                        self.last_10m_summary = f"Patrolling {len(candidates)} $1M+ liquid pairs for 5 Big Setups | Streak: [{streak_seq}] ({self.consecutive_paper_wins}/6)"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                time.sleep(8)

            except Exception as e:
                time.sleep(8)

if __name__ == "__main__":
    bot = MultiBigTradeBot()
    bot.run()

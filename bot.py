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
MEMORY_FILE = "master_30d_eligible_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING_IGNITIONS")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            
            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Bitget Momentum Ignition Engine</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 15px; border: 1px solid #334155; }}
                    .stat {{ font-size: 26px; font-weight: bold; color: #38bdf8; margin: 4px 0; }}
                    .green {{ color: #4ade80; }}
                    .red {{ color: #f87171; }}
                    .title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="title">Active Momentum Runner</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b></div>
                </div>
                <div class="card">
                    <div class="title">Account Vault</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">30-Day Certified Runners</div>
                    <div>Verified 50%+ Coins: <b>{len(bot.eligible_30d_coins)} Coins</b></div>
                    <div>Status: <i>{bot.last_10m_summary}</i></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • Institutional Ignition Engine</div>
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
    print(f"[SYSTEM] Dashboard active on port {PORT}", flush=True)

# ==============================================================================
# 2. BOT ENGINE: ±4% INSTITUTIONAL IGNITION RUNNER
# ==============================================================================
class Strict30dGatedBot:
    def __init__(self):
        self.equity_floor = 1.50
        self.ROUNDTRIP_FEE_PCT = 0.12
        self.LOOKBACK_DAYS = 30
        self.MIN_SINGLE_DAY_MOVE_PCT = 50.0

        # INSTITUTIONAL IGNITION PARAMETERS (THE ±4% RULE)
        self.MIN_DAILY_IGNITION_PCT = 4.0      # Must have moved at least 4% from today's Open
        self.MAX_DAILY_ENTRY_CEILING_PCT = 9.5 # Do not chase if it already pumped > 9.5%
        self.MIN_INSTITUTIONAL_RVOL = 2.8      # Must have 2.8x - 3.0x normal volume

        self.all_time_wins = 0
        self.all_time_losses = 0
        self.eligible_30d_coins = {}
        self.ineligible_quarantine = set()
        self.audited_timestamps = {}
        self.coin_mistakes = {}
        self.global_volume_whitelist = set()

        self.last_summary_time = 0.0
        self.last_balance = 1.78
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.last_10m_summary = "Scanning for ±4% Institutional Ignitions..."

        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META'
        }

        self.current_trade = None
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "pivot_point": 0.0, "start_time": 0.0,
            "max_peak": 0.0, "engine_source": ""
        }

        self.api_key = (os.environ.get("API_KEY") or "").strip()
        self.secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        self.passphrase = (os.environ.get("PASSPHRASE") or "").strip()

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing credentials!", flush=True)
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

    def enforce_one_way_mode(self):
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
        except Exception:
            pass

    def recover_existing_position(self):
        try:
            positions = self.bitget.fetch_positions()
            for p in positions:
                contracts = abs(float(p.get('contracts', 0) or 0))
                if contracts > 0:
                    sym = p.get('symbol')
                    side = 'long' if float(p.get('contracts', 0)) > 0 else 'short'
                    entry_price = float(p.get('entryPrice') or 0.0)
                    self.live_state = {
                        "active": True, "symbol": sym, "side": side,
                        "contracts": contracts, "entry_price": entry_price,
                        "pivot_point": entry_price, "start_time": time.time(),
                        "max_peak": 0.0, "engine_source": "RECOVERED_LIVE"
                    }
                    print(f"\n🔄 [AUTO-RECOVERY] Resumed tracking live {side.upper()} on {sym} ({contracts} contracts)\n", flush=True)
                    break
        except Exception as e:
            print(f"[RECOVERY NOTE] No active position adopted: {e}", flush=True)

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    self.all_time_wins = data.get("all_time_wins", 0)
                    self.all_time_losses = data.get("all_time_losses", 0)
                    self.eligible_30d_coins = data.get("eligible_30d_coins", {})
                    self.ineligible_quarantine = set(data.get("ineligible_quarantine", []))
                    self.audited_timestamps = data.get("audited_timestamps", {})
            except Exception:
                pass

    def save_memory(self):
        tmp_file = f"{MEMORY_FILE}.tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump({
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses,
                    "eligible_30d_coins": self.eligible_30d_coins,
                    "ineligible_quarantine": list(self.ineligible_quarantine),
                    "audited_timestamps": self.audited_timestamps
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
                            if vol_usd >= 1_000_000.0:
                                new_whitelist.add(sym)
                    time.sleep(0.35)

                if len(new_whitelist) >= 40:
                    self.global_volume_whitelist = new_whitelist
            except Exception:
                pass
            time.sleep(600)

    # --------------------------------------------------------------------------
    # 30-DAY PROVEN 50%+ RUNNER AUDITOR
    # --------------------------------------------------------------------------
    def audit_coin_30d_eligibility(self, symbol):
        try:
            candles = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=35)
            if not candles or len(candles) < 25:
                return False

            daily_candles = candles[-30:]
            pumps_50, dumps_50 = [], []

            for i in range(5, len(daily_candles)):
                c = daily_candles[i]
                open_p, high_p, low_p, vol = c[1], c[2], c[3], c[5]
                day_gain = ((high_p - open_p) / open_p) * 100.0
                day_dump = ((open_p - low_p) / open_p) * 100.0

                prior_vols = [x[5] for x in daily_candles[i-5:i]]
                avg_prior = sum(prior_vols) / len(prior_vols) if prior_vols else 1.0
                vol_mult = vol / avg_prior if avg_prior > 0 else 1.0

                if day_gain >= self.MIN_SINGLE_DAY_MOVE_PCT:
                    pumps_50.append(vol_mult)
                if day_dump >= self.MIN_SINGLE_DAY_MOVE_PCT:
                    dumps_50.append(vol_mult)

            total_events = len(pumps_50) + len(dumps_50)
            self.audited_timestamps[symbol] = time.time()

            if total_events == 0:
                self.ineligible_quarantine.add(symbol)
                if symbol in self.eligible_30d_coins:
                    del self.eligible_30d_coins[symbol]
                return False

            self.eligible_30d_coins[symbol] = {
                "total_events": total_events,
                "can_long": len(pumps_50) > 0,
                "can_short": len(dumps_50) > 0
            }
            if symbol in self.ineligible_quarantine:
                self.ineligible_quarantine.remove(symbol)
            return True
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # ACTIVE DIRECTION & BULLDOZER BODY CHECK (5-MINUTE TIME TAPE)
    # --------------------------------------------------------------------------
    def verify_active_tape(self, symbol, side):
        try:
            candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=5)
            if not candles_5m or len(candles_5m) < 3:
                return False

            last_c = candles_5m[-1]
            prev_c = candles_5m[-2]

            o, h, l, c = last_c[1], last_c[2], last_c[3], last_c[4]
            total_range = h - l
            if total_range <= 0:
                return False

            body_size = abs(c - o)
            body_ratio = body_size / total_range

            # Must have at least 65% solid candle body (No big rejection wicks!)
            if body_ratio < 0.65:
                return False

            if side == "short":
                return (c < o) and (c <= prev_c[4])
            elif side == "long":
                return (c > o) and (c >= prev_c[4])

            return False
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # THE INSTITUTIONAL IGNITION INSPECTOR (±4% FROM 00:00 UTC OPEN)
    # --------------------------------------------------------------------------
    def inspect_strong_ignition(self, symbol):
        """
        Confirms a coin has launched a TRUE Institutional Momentum Day:
        1. Has gained >= +4% or dropped <= -4% from the Daily Open.
        2. Has NOT already reached the finish line (> 9.5% is too late).
        3. Relative Volume (RVOL) is >= 2.8x (Heavy money moving the asset).
        4. Active 5m tape confirms continuous bulldozing in that exact direction.
        """
        scenario = self.eligible_30d_coins.get(symbol)
        if not scenario:
            return None

        try:
            # 1. Fetch Daily (1D) candles to anchor 00:00 UTC Open
            d_candles = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=15)
            if not d_candles or len(d_candles) < 12:
                return None

            today_c = d_candles[-1]
            daily_open = today_c[1]
            cur_price = today_c[4]

            # Calculate today's net gain from open
            day_gain_pct = ((cur_price - daily_open) / daily_open) * 100.0

            # 2. Check 1-Hour candles for volume acceleration
            candles_1h = self.bitget.fetch_ohlcv(symbol, timeframe='1h', limit=48)
            if not candles_1h or len(candles_1h) < 30:
                return None

            history_1h = candles_1h[:-1]
            current_1h = candles_1h[-1]
            avg_vol_24 = sum([x[5] for x in history_1h[-24:]]) / 24.0
            rvol = current_1h[5] / avg_vol_24 if avg_vol_24 > 0 else 1.0

            # Check 1H Moving Averages
            closes = [x[4] for x in history_1h] + [cur_price]
            def calc_ema(data, period):
                k = 2 / (period + 1)
                res = [data[0]]
                for p in data[1:]:
                    res.append((p * k) + (res[-1] * (1 - k)))
                return res

            ema9 = calc_ema(closes, 9)[-1]
            ema21 = calc_ema(closes, 21)[-1]

            # ------------------------------------------------------------------
            # LONG IGNITION: Daily +4.0% to +9.5% with 2.8x+ Volume
            # ------------------------------------------------------------------
            if scenario["can_long"]:
                is_in_sweet_spot = self.MIN_DAILY_IGNITION_PCT <= day_gain_pct <= self.MAX_DAILY_ENTRY_CEILING_PCT
                has_volume_thrust = rvol >= self.MIN_INSTITUTIONAL_RVOL
                has_trend_structure = cur_price > ema9 and ema9 > ema21

                if is_in_sweet_spot and has_volume_thrust and has_trend_structure:
                    if self.verify_active_tape(symbol, "long"):
                        return {
                            "side": "long",
                            "day_gain": day_gain_pct,
                            "rvol": round(rvol, 1),
                            "pivot": daily_open
                        }

            # ------------------------------------------------------------------
            # SHORT IGNITION: Daily -4.0% to -9.5% with 2.8x+ Volume
            # ------------------------------------------------------------------
            if scenario["can_short"]:
                day_dump_pct = abs(day_gain_pct)
                is_in_sweet_spot = (day_gain_pct <= -self.MIN_DAILY_IGNITION_PCT) and (day_dump_pct <= self.MAX_DAILY_ENTRY_CEILING_PCT)
                has_volume_thrust = rvol >= self.MIN_INSTITUTIONAL_RVOL
                has_trend_structure = cur_price < ema9 and ema9 < ema21

                if is_in_sweet_spot and has_volume_thrust and has_trend_structure:
                    if self.verify_active_tape(symbol, "short"):
                        return {
                            "side": "short",
                            "day_gain": -day_dump_pct,
                            "rvol": round(rvol, 1),
                            "pivot": daily_open
                        }

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # RIDE TO +20%/+30% & EXIT WHEN MOMENTUM FADES
    # --------------------------------------------------------------------------
    def manage_momentum_and_exits(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
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

            candles_1h = self.bitget.fetch_ohlcv(sym, timeframe='1h', limit=15)
            closes = [x[4] for x in candles_1h]
            def calc_ema(data, period):
                k = 2 / (period + 1)
                res = [data[0]]
                for p in data[1:]:
                    res.append((p * k) + (res[-1] * (1 - k)))
                return res

            ema9 = calc_ema(closes, 9)[-1]
            ema21 = calc_ema(closes, 21)[-1]
            last_vol = candles_1h[-1][5]
            avg_vol = sum([x[5] for x in candles_1h[-10:]]) / 10.0
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

        # --- THE FADING MOMENTUM RULES (WAIT FOR IT TO FADE AT THE TOP) ---

        # 1. Massive Expansion Reached (+25% to +30%+ Target)
        if gain_pct >= 25.0:
            should_exit = True
            is_win = True
            exit_reason = f"TARGET HIT: Massive +{gain_pct:.1f}% Harvested!"

        # 2. Peak Exhaustion Fade (If trade hit +12% or more and pulls back > 4.5%):
        elif peak >= 12.0 and (peak - gain_pct) >= 4.5:
            should_exit = True
            is_win = True
            exit_reason = f"RUNNER FADED: Peaked at +{peak:.1f}% -> Exited at +{gain_pct:.1f}%"

        # 3. 1H Trend Inversion (The winning side lost control):
        elif side == "long" and (cur_price < ema9 or ema9 < ema21):
            should_exit = True
            is_win = gain_pct > 0.5
            exit_reason = f"MOMENTUM DIED: 1H Trend broke (Closed at {gain_pct:+.2f}%)"

        elif side == "short" and (cur_price > ema9 or ema9 > ema21):
            should_exit = True
            is_win = gain_pct > 0.5
            exit_reason = f"MOMENTUM DIED: 1H Trend broke (Closed at {gain_pct:+.2f}%)"

        # 4. Volume Flatline: If held > 4 hours and volume drops below 30% of average:
        elif elapsed_hours >= 4.0 and last_vol < (avg_vol * 0.30) and abs(gain_pct) < 2.0:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"STAGNATION: Volume dried up completely after {elapsed_hours:.1f}h"

        # 5. Daily Open Failure (Price fell back below the 00:00 UTC Open):
        elif (side == "long" and cur_price < pivot) or (side == "short" and cur_price > pivot):
            should_exit = True
            is_win = False
            exit_reason = f"IGNITION FAILED: Returned past Daily Open (Loss: {gain_pct:.1f}%)"

        if should_exit:
            print(f"\n🛑 [EXIT] {sym} | Reason: {exit_reason} | Net Spot: {gain_pct:+.2f}%\n", flush=True)
            if is_win:
                self.all_time_wins += 1
            else:
                self.all_time_losses += 1
            self.save_memory()

            if self.live_state["active"]:
                self.close_live_position(sym)
            self.current_trade = None

    def close_live_position(self, sym):
        try:
            positions = self.bitget.fetch_positions([sym])
            for p in positions:
                contracts = abs(float(p.get('contracts', 0) or 0))
                if contracts > 0:
                    close_side = 'sell' if self.live_state["side"] == 'long' else 'buy'
                    self.bitget.create_order(sym, 'market', close_side, contracts, params={'reduceOnly': True, 'tradeSide': 'close'})
                    print(f"[LIVE CLOSED] Successfully closed {contracts} contracts on {sym}", flush=True)
                    break
        except Exception as e:
            print(f"[EXIT ERROR] {e}", flush=True)
        self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] APEX ±4% Institutional Ignition Engine Online.", flush=True)

        try:
            self.bitget.load_markets()
        except Exception:
            pass

        while True:
            try:
                self.manage_momentum_and_exits()

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
                    has_1m = (base in self.global_volume_whitelist) or (float(t.get('quoteVolume', 0) or 0) >= 1_000_000.0)
                    if has_1m and (s not in self.ineligible_quarantine):
                        vol = float(t.get('quoteVolume', 0) or 0)
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)

                # Background 30d audit
                for sym, _ in candidates[:30]:
                    last_audit = self.audited_timestamps.get(sym, 0)
                    if time.time() - last_audit > 43200:
                        self.audit_coin_30d_eligibility(sym)
                        self.save_memory()
                        time.sleep(0.12)

                # Scan ONLY certified 30-day runners for the ±4% institutional ignition
                if not self.current_trade and not self.live_state["active"]:
                    for sym in list(self.eligible_30d_coins.keys()):
                        if sym in tickers:
                            signal = self.inspect_strong_ignition(sym)
                            if signal:
                                side = signal["side"]
                                day_gain = signal["day_gain"]
                                rvol = signal["rvol"]
                                pivot = signal["pivot"]
                                mid = float(tickers[sym]['last'])

                                print(f"\n🚀 [STRONG IGNITION CONFIRMED] {sym} ({side.upper()})", flush=True)
                                print(f"📊 Day Move: {day_gain:+.1f}% | Relative Volume: {rvol}x | Direction Verified!\n", flush=True)

                                margin_alloc = balance * 0.90
                                exchange_min = 5.50
                                needed_lev = max(math.ceil(exchange_min / margin_alloc), 1)

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
                                    self.bitget.create_order(sym, 'market', order_side, amount, params={'tradeSide': 'open'})
                                    self.live_state = {
                                        "active": True, "symbol": sym, "side": side,
                                        "contracts": amount, "entry_price": mid,
                                        "pivot_point": pivot, "start_time": time.time(),
                                        "max_peak": 0.0, "engine_source": "INSTITUTIONAL_IGNITION"
                                    }
                                    print(f"✅ [LIVE TRADE OPENED] {sym} | Margin: ${margin_alloc:.2f} | Leverage: {needed_lev}x\n", flush=True)
                                    break
                                except Exception as err:
                                    self.current_trade = {
                                        "symbol": sym, "side": side,
                                        "entry_price": mid, "pivot_point": pivot,
                                        "start_time": time.time(), "max_peak": 0.0
                                    }
                                    print(f"⚠️ [PAPER TRADE STARTED] {sym} (Live note: {err})\n", flush=True)
                                    break

                # 10-MINUTE CLEAN SUMMARY
                now = time.time()
                if now - self.last_summary_time >= 600:
                    self.last_summary_time = now
                    t_str = time.strftime("%H:%M:%S", time.localtime(now))
                    
                    if self.live_state["active"] or self.current_trade:
                        sym = self.live_state["symbol"] if self.live_state["active"] else self.current_trade["symbol"]
                        side = self.live_state["side"] if self.live_state["active"] else self.current_trade["side"]
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | Held: {self.last_held_hours:.1f}h"
                    else:
                        self.last_10m_summary = f"Scanning {len(self.eligible_30d_coins)} verified 30d runner coins for ±4% Ignitions"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                time.sleep(10)

            except Exception:
                time.sleep(10)

if __name__ == "__main__":
    bot = Strict30dGatedBot()
    bot.run()

import os
import sys
import time
import json
import math
import threading
import traceback
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER 1-CLICK WEB DASHBOARD (PORT 10000)
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
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE_ACTIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            
            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Bitget Bot Summary</title>
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
                    <div class="title">Active Position</div>
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
                    <div class="title">30-Day Runner Scanner</div>
                    <div>Verified 50%+ Movers: <b>{len(bot.eligible_30d_coins)} Coins</b></div>
                    <div>Quarantined (Excluded): <b>{len(bot.ineligible_quarantine)} Coins</b></div>
                    <div>Status: <i>{bot.last_10m_summary}</i></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • APEX 30D Dual Engine</div>
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
# 2. BOT ENGINE
# ==============================================================================
class Strict30dGatedBot:
    def __init__(self):
        self.equity_floor = 1.50
        self.ROUNDTRIP_FEE_PCT = 0.12
        self.LOOKBACK_DAYS = 30
        self.MIN_SINGLE_DAY_MOVE_PCT = 50.0

        self.MIN_LEAD_DISPLACEMENT_PCT = 1.5
        self.MAX_CHASE_LEAD_PCT = 4.5
        self.MIN_OPEN_RUNWAY_PCT = 10.0

        self.all_time_wins = 0
        self.all_time_losses = 0
        self.eligible_30d_coins = {}
        self.ineligible_quarantine = set()
        self.audited_timestamps = {}
        self.coin_mistakes = {}
        self.global_volume_whitelist = set()

        # Telemetry for Clean 10-Minute Summaries
        self.last_summary_time = 0.0
        self.last_balance = 1.78
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.last_10m_summary = "Scanning 30-day verified runners..."

        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU'
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
            print("[FATAL] Missing Bitget credentials!", flush=True)
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
        self.recover_existing_position()  # AUTO-RECOVERS ANY OPEN TRADE AFTER RESTART

        t_global = threading.Thread(target=self.global_volume_worker, daemon=True)
        t_global.start()

    def enforce_one_way_mode(self):
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
        except Exception:
            pass

    def recover_existing_position(self):
        """Adopts any active position on Bitget if Render restarts."""
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
    # 30-DAY 50%+ AUDITOR (ELIGIBLE ONLY)
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

            all_mults = pumps_50 + dumps_50
            avg_vol_mult = sum(all_mults) / len(all_mults)

            self.eligible_30d_coins[symbol] = {
                "total_events": total_events,
                "required_vol_mult": round(min(max(avg_vol_mult, 1.8), 4.5), 2),
                "can_long": len(pumps_50) > 0,
                "can_short": len(dumps_50) > 0
            }
            if symbol in self.ineligible_quarantine:
                self.ineligible_quarantine.remove(symbol)
            return True
        except Exception:
            return False

    def inspect_eligible_coin(self, symbol):
        scenario = self.eligible_30d_coins.get(symbol)
        if not scenario:
            return None

        try:
            candles_1h = self.bitget.fetch_ohlcv(symbol, timeframe='1h', limit=75)
            if not candles_1h or len(candles_1h) < 65:
                return None

            history = candles_1h[:-1]
            current_c = candles_1h[-1]
            cur_open = current_c[1]
            cur_price = current_c[4]
            cur_vol = current_c[5]
            avg_vol_24 = sum([x[5] for x in history[-24:]]) / 24.0
            vol_mult = cur_vol / avg_vol_24 if avg_vol_24 > 0 else 1.0

            closes = [x[4] for x in history] + [cur_price]
            def calc_ema(data, period):
                k = 2 / (period + 1)
                res = [data[0]]
                for p in data[1:]:
                    res.append((p * k) + (res[-1] * (1 - k)))
                return res

            ema9 = calc_ema(closes, 9)[-1]
            ema21 = calc_ema(closes, 21)[-1]

            # 1. 30d Ignition Match
            if scenario["can_long"] and cur_price > cur_open and cur_price > ema9 and ema9 > ema21:
                gain_1h = ((cur_price - cur_open) / cur_open) * 100.0
                if gain_1h >= 1.5 and vol_mult >= scenario["required_vol_mult"]:
                    return {"side": "long", "engine": "30D_IGNITION", "pivot": cur_open}

            if scenario["can_short"] and cur_price < cur_open and cur_price < ema9 and ema9 < ema21:
                dump_1h = ((cur_open - cur_price) / cur_open) * 100.0
                if dump_1h >= 1.5 and vol_mult >= scenario["required_vol_mult"]:
                    return {"side": "short", "engine": "30D_IGNITION", "pivot": cur_open}

            # 2. James vs David Front-Runner
            if vol_mult >= 1.7:
                recent = history[-60:-1]
                james_ceil = max([x[2] for x in recent])
                james_floor = min([x[3] for x in recent])

                if cur_price > james_ceil and cur_price > ema9 and ema9 > ema21:
                    lead = ((cur_price - james_ceil) / james_ceil) * 100.0
                    if self.MIN_LEAD_DISPLACEMENT_PCT <= lead <= self.MAX_CHASE_LEAD_PCT:
                        return {"side": "long", "engine": "FRONT_RUNNER_DAVID", "pivot": james_ceil}

                if cur_price < james_floor and cur_price < ema9 and ema9 < ema21:
                    lead = ((james_floor - cur_price) / james_floor) * 100.0
                    if self.MIN_LEAD_DISPLACEMENT_PCT <= lead <= self.MAX_CHASE_LEAD_PCT:
                        return {"side": "short", "engine": "FRONT_RUNNER_DAVID", "pivot": james_floor}

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # MOMENTUM DEATH EXITS (NO LOG SPAM)
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

        # Momentum Death Triggers
        if side == "long" and (cur_price < ema9 or ema9 < ema21):
            should_exit = True
            is_win = gain_pct > 0.3
            exit_reason = f"Momentum Died (EMA Inverted at {gain_pct:+.2f}%)"
        elif side == "short" and (cur_price > ema9 or ema9 > ema21):
            should_exit = True
            is_win = gain_pct > 0.3
            exit_reason = f"Momentum Died (EMA Inverted at {gain_pct:+.2f}%)"
        elif peak >= 6.0 and (peak - gain_pct) >= 2.8:
            should_exit = True
            is_win = True
            exit_reason = f"Profit Protected (Peak {peak:.1f}% -> Exited at {gain_pct:.1f}%)"
        elif gain_pct >= 20.0:
            should_exit = True
            is_win = True
            exit_reason = f"Target Hit (+{gain_pct:.1f}%)"
        elif (side == "long" and cur_price < pivot * 0.98) or (side == "short" and cur_price > pivot * 1.02):
            should_exit = True
            is_win = False
            exit_reason = f"Pivot Invalidation (Loss: {gain_pct:.1f}%)"

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
    # 4. CLEAN 10-MINUTE SUMMARY LOGGING LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] APEX Clean 10-Minute Summary Engine Online.", flush=True)

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

                # Scan only eligible coins
                if not self.current_trade and not self.live_state["active"]:
                    for sym in list(self.eligible_30d_coins.keys()):
                        if sym in tickers:
                            entry_signal = self.inspect_eligible_coin(sym)
                            if entry_signal:
                                side = entry_signal["side"]
                                engine = entry_signal["engine"]
                                pivot = entry_signal["pivot"]
                                mid = float(tickers[sym]['last'])

                                print(f"\n🚀 [ENTRY TRIGGERED: {engine}] {sym} ({side.upper()}) at ${mid}", flush=True)

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
                                        "max_peak": 0.0, "engine_source": engine
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

                # CLEAN 10-MINUTE CONSOLE SUMMARY (ZERO SPAM)
                now = time.time()
                if now - self.last_summary_time >= 600:
                    self.last_summary_time = now
                    t_str = time.strftime("%H:%M:%S", time.localtime(now))
                    
                    if self.live_state["active"] or self.current_trade:
                        sym = self.live_state["symbol"] if self.live_state["active"] else self.current_trade["symbol"]
                        side = self.live_state["side"] if self.live_state["active"] else self.current_trade["side"]
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | Held: {self.last_held_hours:.1f}h"
                    else:
                        self.last_10m_summary = f"Scanning {len(self.eligible_30d_coins)} verified 30d runner coins"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                time.sleep(10)

            except Exception as e:
                time.sleep(10)

if __name__ == "__main__":
    bot = Strict30dGatedBot()
    bot.run()

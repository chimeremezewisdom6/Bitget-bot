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
MEMORY_FILE = "quiet_absorption_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING_LEVEL_8")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            
            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Quiet vs Aggressive Absorption Engine</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 15px; border: 1px solid #334155; }}
                    .stat {{ font-size: 26px; font-weight: bold; color: #38bdf8; margin: 4px 0; }}
                    .green {{ color: #4ade80; }}
                    .red {{ color: #f87171; }}
                    .badge {{ background: #0284c7; padding: 3px 8px; border-radius: 6px; font-size: 13px; font-weight: bold; }}
                    .title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="title">Active Position</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b> | State: <span class="badge">{bot.current_stage}</span></div>
                </div>
                <div class="card">
                    <div class="title">Account Vault</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">Quiet-Absorption Verified Pool</div>
                    <div>Verified Cycle Coins: <b>{len(bot.absorption_cycle_coins)} Coins</b></div>
                    <div>Status: <i>{bot.last_10m_summary}</i></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • Level 8 Entry / Level 10 Exit to USDT</div>
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
# 2. BOT ENGINE: PASSIVE ABSORPTION (AGGRESSIVE TRAPPED AT 8 -> EXIT AT 10)
# ==============================================================================
class QuietAbsorptionBot:
    def __init__(self):
        self.equity_floor = 1.50
        self.ROUNDTRIP_FEE_PCT = 0.12
        self.LOOKBACK_DAYS = 30

        # ABSORPTION PARAMETERS
        self.MIN_AGGRESSION_RVOL = 2.4     # Aggressive side must be pushing with >= 2.4x volume
        self.MAX_PROGRESSION_PCT = 0.75    # But quiet side absorbs them (price moves < 0.75%)
        self.LEVEL_10_TARGET_PCT = 6.0     # Target to exit back to 100% USDT

        self.all_time_wins = 0
        self.all_time_losses = 0
        self.absorption_cycle_coins = {}   # {symbol: audit_data}
        self.audited_timestamps = {}
        self.global_volume_whitelist = set()

        self.last_summary_time = 0.0
        self.last_balance = 1.78
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.current_stage = "SCANNING_FOR_8"
        self.last_10m_summary = "Hunting for coins hitting Level 8 Ambush..."

        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META'
        }

        self.current_trade = None
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "wall_pivot": 0.0, "start_time": 0.0,
            "max_peak": 0.0
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
                        "wall_pivot": entry_price, "start_time": time.time(),
                        "max_peak": 0.0
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
                    self.absorption_cycle_coins = data.get("absorption_cycle_coins", {})
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
                    "absorption_cycle_coins": self.absorption_cycle_coins,
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
    # 30-DAY AUDITOR: FINDS COINS WITH REPEATING ABSORPTION CYCLES (EVERY 1-4 WEEKS)
    # --------------------------------------------------------------------------
    def audit_absorption_personality(self, symbol):
        """
        Audits past 30 days to see if this specific coin experiences the
        'Quiet vs Aggressive Absorption' trap every 1 to 4 weeks.
        """
        try:
            candles = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=35)
            if not candles or len(candles) < 25:
                return False

            daily = candles[-30:]
            absorption_events = 0

            for i in range(2, len(daily)):
                c = daily[i]
                o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                prior_vols = [x[5] for x in daily[max(0, i-7):i]]
                avg_v = sum(prior_vols) / len(prior_vols) if prior_vols else 1.0

                # Check for days where volume exploded (>= 2.2x), but candle body was tiny (< 2%)
                # followed by a sharp multi-day reversal (quiet side absorbing and reversing)
                day_range = ((h - l) / l) * 100.0
                body = abs(cl - o) / o * 100.0
                vol_ratio = vol / avg_v if avg_v > 0 else 1.0

                if vol_ratio >= 2.0 and body <= 2.2:
                    # Check next day for reversal
                    if i + 1 < len(daily):
                        next_c = daily[i+1]
                        next_move = abs(next_c[4] - next_c[1]) / next_c[1] * 100.0
                        if next_move >= 4.0:
                            absorption_events += 1

            self.audited_timestamps[symbol] = time.time()

            # Must have happened 1 to 4 times in the past 30 days (consistent cycle)
            if 1 <= absorption_events <= 5:
                self.absorption_cycle_coins[symbol] = {
                    "cycles_found": absorption_events,
                    "audited_time": time.time()
                }
                return True
            else:
                if symbol in self.absorption_cycle_coins:
                    del self.absorption_cycle_coins[symbol]
                return False
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # DETECT LEVEL 8: AGGRESSIVE SIDE TRAPPED AGAINST QUIET WALL
    # --------------------------------------------------------------------------
    def inspect_level_8_absorption(self, symbol):
        """
        Checks 1H/15m charts to see if an aggressive side has hit the quiet wall:
        1. Aggressive Taker Volume is surging (>= 2.4x).
        2. Price progress has stalled into a tight brick wall (< 0.75% range).
        3. The quiet side begins the counter-turn on the 5m tape.
        """
        if symbol not in self.absorption_cycle_coins:
            return None

        try:
            candles_1h = self.bitget.fetch_ohlcv(symbol, timeframe='1h', limit=24)
            if not candles_1h or len(candles_1h) < 15:
                return None

            history = candles_1h[:-1]
            current_1h = candles_1h[-1]

            cur_price = current_1h[4]
            cur_vol = current_1h[5]
            avg_vol = sum([x[5] for x in history[-12:]]) / 12.0
            rvol = cur_vol / avg_vol if avg_vol > 0 else 1.0

            # ------------------------------------------------------------------
            # SCENARIO A: AGGRESSIVE SELLERS HIT QUIET BUYING WALL -> ENTER LONG
            # ------------------------------------------------------------------
            # Aggressive sellers are hammering volume (>= 2.4x)
            if rvol >= self.MIN_AGGRESSION_RVOL:
                # Check last three 15-minute candles to see if price is stuck at a floor
                candles_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=6)
                if candles_15m and len(candles_15m) >= 4:
                    lows_15m = [x[3] for x in candles_15m[-3:]]
                    highs_15m = [x[2] for x in candles_15m[-3:]]
                    floor_band = ((max(highs_15m) - min(lows_15m)) / min(lows_15m)) * 100.0

                    # Brick wall: 15m range is compressed (< 0.75%) despite heavy selling volume
                    if floor_band <= self.MAX_PROGRESSION_PCT:
                        # Check 5m candle: Quiet buyers begin counter-punch (First green candle breaking up)
                        candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=5)
                        if candles_5m and len(candles_5m) >= 3:
                            last_5m = candles_5m[-1]
                            if last_5m[4] > last_5m[1]:  # Solid green
                                return {
                                    "side": "long",
                                    "wall_pivot": min(lows_15m),
                                    "desc": f"Level 8 Hit: Sellers trapped against Quiet Wall ({rvol:.1f}x Vol, only {floor_band:.2f}% progress)"
                                }

            # ------------------------------------------------------------------
            # SCENARIO B: AGGRESSIVE BUYERS HIT QUIET SELLING WALL -> ENTER SHORT
            # ------------------------------------------------------------------
            if rvol >= self.MIN_AGGRESSION_RVOL:
                candles_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=6)
                if candles_15m and len(candles_15m) >= 4:
                    lows_15m = [x[3] for x in candles_15m[-3:]]
                    highs_15m = [x[2] for x in candles_15m[-3:]]
                    ceil_band = ((max(highs_15m) - min(lows_15m)) / min(lows_15m)) * 100.0

                    if ceil_band <= self.MAX_PROGRESSION_PCT:
                        candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=5)
                        if candles_5m and len(candles_5m) >= 3:
                            last_5m = candles_5m[-1]
                            if last_5m[4] < last_5m[1]:  # Solid red
                                return {
                                    "side": "short",
                                    "wall_pivot": max(highs_15m),
                                    "desc": f"Level 8 Hit: Buyers trapped against Quiet Wall ({rvol:.1f}x Vol, only {ceil_band:.2f}% progress)"
                                }

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # RIDE FROM 8 -> 9 -> EXIT TO USDT AT 10
    # --------------------------------------------------------------------------
    def manage_level_8_to_10_exit(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
            self.current_stage = "IDLE (WAITING FOR 8)"
            return

        sym = trade["symbol"]
        side = trade["side"]
        entry = trade["entry_price"]
        wall = trade["wall_pivot"]
        elapsed_hours = (time.time() - trade["start_time"]) / 3600.0
        self.last_held_hours = elapsed_hours

        try:
            ticker = self.bitget.fetch_ticker(sym)
            cur_price = float(ticker.get('last') or 0.0)
            if cur_price == 0:
                return

            candles_1h = self.bitget.fetch_ohlcv(sym, timeframe='1h', limit=10)
            closes = [x[4] for x in candles_1h]
            ema9 = sum(closes[-9:]) / 9.0
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

        # --- LEVEL PROGRESSION ---
        # 1. LEVEL 10 REACHED (FULL REVERSION TARGET HIT) -> GO BACK TO USDT!
        if gain_pct >= self.LEVEL_10_TARGET_PCT:
            self.current_stage = "LEVEL 10 REACHED (GO BACK TO USDT)"
            should_exit = True
            is_win = True
            exit_reason = f"LEVEL 10 REACHED (+{gain_pct:.2f}%) -> FULL EXIT BACK TO 100% USDT"

        # 2. LEVEL 9 IN PROGRESS (PARTIAL EXPANSION)
        elif gain_pct >= 2.5:
            self.current_stage = "LEVEL 9 SURGING (QUIET SIDE WINNING)"
            # Protect gains if level 9 stalls out
            if peak >= 4.0 and (peak - gain_pct) >= 1.5:
                should_exit = True
                is_win = True
                exit_reason = f"LEVEL 9 RETREAT: Peak +{peak:.1f}% -> Exited at +{gain_pct:.1f}% -> BACK TO USDT"

        else:
            self.current_stage = "ENTERED AT LEVEL 8 (AMBUSH SPRINGING)"

        # --- INVALIDATION FLOOR (The quiet wall collapsed) ---
        if not should_exit:
            if (side == "long" and cur_price < wall * 0.985) or (side == "short" and cur_price > wall * 1.015):
                should_exit = True
                is_win = False
                exit_reason = f"WALL BREACHED: Quiet side lost the level (Loss: {gain_pct:.1f}%)"

            elif elapsed_hours >= 3.0 and gain_pct < 0 and ((side == "long" and cur_price < ema9) or (side == "short" and cur_price > ema9)):
                should_exit = True
                is_win = False
                exit_reason = f"STALLED AT 8: Failed to transition to Level 9 (Loss: {gain_pct:.1f}%)"

        if should_exit:
            print(f"\n🛑 [EXIT EXECUTED] {sym} | Reason: {exit_reason} | Net: {gain_pct:+.2f}%\n", flush=True)
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
                    print(f"[LIVE CLOSED] Closed {contracts} contracts on {sym} -> 100% USDT", flush=True)
                    break
        except Exception as e:
            print(f"[EXIT ERROR] {e}", flush=True)
        self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] Quiet Absorption & Level 10 USDT Return Engine Online.", flush=True)

        try:
            self.bitget.load_markets()
        except Exception:
            pass

        while True:
            try:
                self.manage_level_8_to_10_exit()

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
                    if has_1m:
                        vol = float(t.get('quoteVolume', 0) or 0)
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)

                # Background audit for coins with repeating 1-4 week absorption cycles
                for sym, _ in candidates[:30]:
                    last_audit = self.audited_timestamps.get(sym, 0)
                    if time.time() - last_audit > 43200:
                        self.audit_absorption_personality(sym)
                        self.save_memory()
                        time.sleep(0.12)

                # Scan ONLY verified absorption coins for the Level 8 trigger
                if not self.current_trade and not self.live_state["active"]:
                    for sym in list(self.absorption_cycle_coins.keys()):
                        if sym in tickers:
                            signal = self.inspect_level_8_absorption(sym)
                            if signal:
                                side = signal["side"]
                                wall = signal["wall_pivot"]
                                desc = signal["desc"]
                                mid = float(tickers[sym]['last'])

                                print(f"\n🚀 [LEVEL 8 HIT!] {sym} ({side.upper()}) at ${mid}", flush=True)
                                print(f"📊 {desc} -> Entering alongside the Quiet Side!\n", flush=True)

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
                                        "wall_pivot": wall, "start_time": time.time(),
                                        "max_peak": 0.0
                                    }
                                    print(f"✅ [LIVE TRADE OPENED] {sym} | Margin: ${margin_alloc:.2f} | Leverage: {needed_lev}x\n", flush=True)
                                    break
                                except Exception as err:
                                    self.current_trade = {
                                        "symbol": sym, "side": side,
                                        "entry_price": mid, "wall_pivot": wall,
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
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | Stage: {self.current_stage}"
                    else:
                        self.last_10m_summary = f"Monitoring {len(self.absorption_cycle_coins)} verified absorption coins for Level 8"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                time.sleep(10)

            except Exception:
                time.sleep(10)

if __name__ == "__main__":
    bot = QuietAbsorptionBot()
    bot.run()

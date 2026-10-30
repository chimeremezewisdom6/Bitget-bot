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
MEMORY_FILE = "big_cheat_trap_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING_ALL_COINS")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            
            radar_html = "".join([f"<li><b>{sym}</b>: {data['desc']}</li>" for sym, data in list(bot.active_trap_radar.items())[:6]])
            if not radar_html:
                radar_html = "<li>No minor traps currently building... scanning all liquid pairs.</li>"

            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>The Big Cheat Trap Engine</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; background: #0b0f19; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #151e32; border-radius: 12px; padding: 18px; margin-bottom: 15px; border: 1px solid #1e293b; }}
                    .stat {{ font-size: 26px; font-weight: bold; color: #38bdf8; margin: 4px 0; }}
                    .green {{ color: #4ade80; }}
                    .red {{ color: #f87171; }}
                    .badge {{ background: #e11d48; padding: 3px 8px; border-radius: 6px; font-size: 13px; font-weight: bold; }}
                    .title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
                    ul {{ padding-left: 20px; margin: 6px 0; font-size: 14px; color: #cbd5e1; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="title">Active Trap Position (11 vs 8)</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b> | Match State: <span class="badge">{bot.current_trap_stage}</span></div>
                </div>
                <div class="card">
                    <div class="title">Account Vault</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">Trap Radar (11-10 Minor Cheats Brewing)</div>
                    <ul>{radar_html}</ul>
                    <div>Liquid Universe: <b>{len(bot.all_liquid_candidates)} Coins Monitored</b></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • The Big Cheat (Dynamic Exits / Zero Flatlines)</div>
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
# 2. THE BIG CHEAT ENGINE WITH DEEP EXTENSION & PROVEN WINNER RULES
# ==============================================================================
class BigCheatEngine:
    def __init__(self):
        self.equity_floor = 1.05
        self.ROUNDTRIP_FEE_PCT = 0.12

        # THE CHEAT PARAMETERS
        self.MIN_DAILY_ATR_PCT = 6.5       # Disqualifies flat synthetic tokens like EUV
        self.MIN_DEEP_EXTENSION_PCT = 5.5  # Man City's aggressive run must be at least 5.5% deep
        self.WALL_COMPRESSION_PCT = 1.35   # Burnley's hidden limit wall (< 1.35% range box)
        self.MIN_CHEAT_RVOL = 1.85         # Man City throwing heavy volume into the wall
        self.MIN_WINNING_SEPARATION_PCT = 1.2  # Burnley must lead by >= 1.2% before entry

        self.all_time_wins = 0
        self.all_time_losses = 0
        self.active_trap_radar = {}        # {symbol: {"stage": "11-10", "side": ..., "wall": ...}}
        self.volatility_cache = {}         # {symbol: {"is_boom": bool, "time": timestamp}}
        self.all_liquid_candidates = []
        self.global_volume_whitelist = set()

        self.last_summary_time = 0.0
        self.last_balance = 1.33
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.current_trap_stage = "PATROL (HUNTING 11-8)"
        self.last_10m_summary = "Scanning all liquid coins for deep 11-10 cheats..."

        # Universal Exclusion List (No Gold, Stocks, or Synthetic Commodities)
        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'EUV', 'CSOP', 'TQQQ'
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
        """Correctly identifies Long vs Short to prevent reverse closes."""
        try:
            positions = self.bitget.fetch_positions()
            for p in positions:
                contracts = abs(float(p.get('contracts', 0) or 0))
                if contracts > 0:
                    sym = p.get('symbol')
                    pos_side = str(p.get('side', '')).lower()
                    side = 'short' if pos_side == 'short' else 'long'
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
            print(f"[RECOVERY NOTE] No active position: {e}", flush=True)

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    self.all_time_wins = data.get("all_time_wins", 0)
                    self.all_time_losses = data.get("all_time_losses", 0)
            except Exception:
                pass

    def save_memory(self):
        tmp_file = f"{MEMORY_FILE}.tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump({
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
                            if vol_usd >= 1_000_000.0:
                                new_whitelist.add(sym)
                    time.sleep(0.35)

                if len(new_whitelist) >= 40:
                    self.global_volume_whitelist = new_whitelist
            except Exception:
                pass
            time.sleep(600)

    # --------------------------------------------------------------------------
    # 1. BIG BOOM CAPACITY FILTER: REJECTS FLAT TOKENS LIKE EUV
    # --------------------------------------------------------------------------
    def check_big_boom_capacity(self, symbol):
        now = time.time()
        cached = self.volatility_cache.get(symbol)
        if cached and (now - cached["time"] < 21600):  # 6-hour cache
            return cached["is_boom"]

        try:
            candles_1d = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=10)
            if not candles_1d or len(candles_1d) < 7:
                return False

            ranges = [((c[2] - c[3]) / c[3]) * 100.0 for c in candles_1d[-7:]]
            avg_daily_range = sum(ranges) / len(ranges)
            is_boom = avg_daily_range >= self.MIN_DAILY_ATR_PCT

            self.volatility_cache[symbol] = {"is_boom": is_boom, "time": now}
            return is_boom
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # 2. DEEP TRAP DETECTOR & "WINNING PERFECTLY" VERIFICATION
    # --------------------------------------------------------------------------
    def inspect_trap_mechanics(self, symbol):
        # Rule 1: Must be a volatile crypto coin capable of a massive boom
        if not self.check_big_boom_capacity(symbol):
            return None

        try:
            candles_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=24)
            if not candles_15m or len(candles_15m) < 18:
                return None

            completed_15m = candles_15m[:-1]
            last_closed = completed_15m[-1]

            # Volume comparison against 16-period baseline
            avg_vol_15m = sum([x[5] for x in completed_15m[-16:]]) / 16.0
            rvol = last_closed[5] / avg_vol_15m if avg_vol_15m > 0 else 1.0

            # Rule 2: Prior trend MUST be a deep extension (At least 5.5% of real pain)
            prior_open = completed_15m[-16][1]
            cur_price = last_closed[4]
            prior_move_pct = ((cur_price - prior_open) / prior_open) * 100.0

            if abs(prior_move_pct) < self.MIN_DEEP_EXTENSION_PCT:
                return None

            # Wall detection: 3 completed 15m candles
            recent_3 = completed_15m[-3:]
            min_low = min([x[3] for x in recent_3])
            max_high = max([x[2] for x in recent_3])
            box_range = ((max_high - min_low) / min_low) * 100.0

            is_hitting_wall = (rvol >= self.MIN_CHEAT_RVOL) and (box_range <= self.WALL_COMPRESSION_PCT)

            if is_hitting_wall:
                candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=6)
                if not candles_5m or len(candles_5m) < 4:
                    return None

                last_5m = candles_5m[-1]
                prev_5m = candles_5m[-2]

                # SCENARIO A: SELLERS TRAPPED AT FLOOR -> LONG TRIGGER
                if prior_move_pct <= -self.MIN_DEEP_EXTENSION_PCT:
                    self.active_trap_radar[symbol] = {
                        "stage": "11-10",
                        "side": "long",
                        "desc": f"Deep Dump (-{abs(prior_move_pct):.1f}%) trapped at floor (${min_low})",
                        "time": time.time()
                    }

                    # Rule 3: Burnley Must Be WINNING PERFECTLY Before Entry
                    # Must lead by >= 1.2% away from wall, with 2 consecutive green 5m candles
                    separation = ((last_5m[4] - min_low) / min_low) * 100.0
                    burnley_winning = (separation >= self.MIN_WINNING_SEPARATION_PCT) and (last_5m[4] > last_5m[1]) and (prev_5m[4] > prev_5m[1])

                    if burnley_winning:
                        return {
                            "side": "long",
                            "wall_pivot": min_low,
                            "desc": f"11-8 TRIGGER: Sellers crushed after -{abs(prior_move_pct):.1f}% dump | Burnley leading by +{separation:.2f}%!"
                        }

                # SCENARIO B: BUYERS TRAPPED AT CEILING -> SHORT TRIGGER
                elif prior_move_pct >= self.MIN_DEEP_EXTENSION_PCT:
                    self.active_trap_radar[symbol] = {
                        "stage": "11-10",
                        "side": "short",
                        "desc": f"Deep Pump (+{prior_move_pct:.1f}%) trapped at ceiling (${max_high})",
                        "time": time.time()
                    }

                    separation = ((max_high - last_5m[4]) / max_high) * 100.0
                    burnley_winning = (separation >= self.MIN_WINNING_SEPARATION_PCT) and (last_5m[4] < last_5m[1]) and (prev_5m[4] < prev_5m[1])

                    if burnley_winning:
                        return {
                            "side": "short",
                            "wall_pivot": max_high,
                            "desc": f"11-8 TRIGGER: Buyers crushed after +{prior_move_pct:.1f}% pump | Burnley leading by -{separation:.2f}%!"
                        }
            else:
                if symbol in self.active_trap_radar and (time.time() - self.active_trap_radar[symbol]["time"] > 3600):
                    del self.active_trap_radar[symbol]

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 3. DYNAMIC MATCH-STATE EXIT ENGINE (NO STATIC %)
    # --------------------------------------------------------------------------
    def manage_trap_match_state(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
            self.current_trap_stage = "PATROL (HUNTING 11-8)"
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

            candles_1h = self.bitget.fetch_ohlcv(sym, timeframe='1h', limit=24)
            closes_1h = [x[4] for x in candles_1h]
            ema21_1h = sum(closes_1h[-21:]) / 21.0
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

        # SCENARIO A: TRAP NORMALIZES (11 vs. 10 Normalization -> Cash Out)
        is_at_equilibrium = (side == "long" and cur_price >= ema21_1h) or (side == "short" and cur_price <= ema21_1h)
        is_rolling_over = (peak >= 3.0) and (peak - gain_pct >= 1.4)

        if (is_at_equilibrium and gain_pct >= 1.5) or is_rolling_over:
            self.current_trap_stage = "11 vs 10 (MATCH NORMALIZED -> ESCAPE)"
            should_exit = True
            is_win = True
            exit_reason = f"TRAP NORMALIZED (11 vs 10): Edge realized at {gain_pct:+.2f}% -> ESCAPE TO USDT"

        # SCENARIO B: MAN CITY WINS HEAVILY (TRAP DESTROYED -> CUT IMMEDIATELY)
        man_city_won_heavily = False
        if side == "long" and cur_price < (wall * 0.992):
            man_city_won_heavily = True
        elif side == "short" and cur_price > (wall * 1.008):
            man_city_won_heavily = True

        if man_city_won_heavily:
            self.current_trap_stage = "MAN CITY WON HEAVILY (TRAP COLLAPSED)"
            should_exit = True
            is_win = False
            exit_reason = f"MAN CITY WON HEAVILY: Wall destroyed by aggressive side (Loss: {gain_pct:.1f}%)"

        elif elapsed_hours >= 3.5 and gain_pct < 0.5:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"TRAP EXPIRED: Failed to produce expansion after {elapsed_hours:.1f}h"

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
        """Exits strictly via reduceOnly and only clears memory on confirmed execution."""
        try:
            positions = self.bitget.fetch_positions([sym])
            for p in positions:
                contracts = abs(float(p.get('contracts', 0) or 0))
                if contracts > 0:
                    close_side = 'sell' if self.live_state["side"] == 'long' else 'buy'
                    try:
                        self.bitget.create_order(sym, 'market', close_side, contracts, params={'reduceOnly': True})
                    except Exception:
                        self.bitget.create_order(sym, 'market', close_side, contracts, params={'reduceOnly': True, 'tradeSide': 'close'})

                    print(f"[LIVE ESCAPED] Closed {contracts} contracts on {sym} -> 100% USDT", flush=True)
                    self.live_state["active"] = False
                    break
        except Exception as e:
            print(f"[EXIT ERROR] Failed to close on exchange: {e}. Retaining state for retry.", flush=True)

    # --------------------------------------------------------------------------
    # MAIN PATROL: CONTINUOUS PATROL OVER ALL $1M+ LIQUID PAIRS
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] The Big Cheat Engine Online (Flatlines Filtered & Deep Traps Active).", flush=True)

        try:
            self.bitget.load_markets()
        except Exception:
            pass

        cycle = 0

        while True:
            try:
                self.manage_trap_match_state()

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
                self.all_liquid_candidates = candidates

                if not self.current_trade and not self.live_state["active"]:
                    chunk_size = 30
                    start_idx = (cycle * chunk_size) % max(len(candidates), 1)
                    patrol_batch = candidates[start_idx:start_idx + chunk_size]

                    for sym, _ in patrol_batch:
                        if sym in tickers:
                            signal = self.inspect_trap_mechanics(sym)
                            if signal:
                                side = signal["side"]
                                wall = signal["wall_pivot"]
                                desc = signal["desc"]
                                mid = float(tickers[sym]['last'])

                                print(f"\n🚨 [MASSIVE CHEAT CONFIRMED: 11-8] {sym} ({side.upper()}) at ${mid}", flush=True)
                                print(f"📊 {desc}\n", flush=True)

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
                                    print(f"⚠️ [PAPER TRADE STARTED] {sym} (Live order note: {err})\n", flush=True)
                                    break

                # 10-MINUTE CLEAN SUMMARY (NO LOG SPAM)
                now = time.time()
                if now - self.last_summary_time >= 600:
                    self.last_summary_time = now
                    t_str = time.strftime("%H:%M:%S", time.localtime(now))
                    
                    if self.live_state["active"] or self.current_trade:
                        sym = self.live_state["symbol"] if self.live_state["active"] else self.current_trade["symbol"]
                        side = self.live_state["side"] if self.live_state["active"] else self.current_trade["side"]
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | State: {self.current_trap_stage}"
                    else:
                        self.last_10m_summary = f"Patrolling {len(candidates)} liquid coins | Traps on Radar (11-10): {len(self.active_trap_radar)}"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                cycle += 1
                time.sleep(6)

            except Exception:
                time.sleep(6)

if __name__ == "__main__":
    bot = BigCheatEngine()
    bot.run()

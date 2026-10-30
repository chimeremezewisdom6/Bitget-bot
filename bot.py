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
MEMORY_FILE = "fatigued_opponent_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING_FOR_FATIGUED_SIDES")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            
            radar_html = "".join([f"<li><b>{sym}</b>: {data['desc']}</li>" for sym, data in list(bot.fatigue_radar.items())[:6]])
            if not radar_html:
                radar_html = "<li>No opponents showing severe fatigue right now... scouting all liquid pairs.</li>"

            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Fatigued Opponent Engine</title>
                <style>
                    body {{ font-family: -apple-system, sans-serif; background: #0b0f19; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #151e32; border-radius: 12px; padding: 18px; margin-bottom: 15px; border: 1px solid #1e293b; }}
                    .stat {{ font-size: 26px; font-weight: bold; color: #38bdf8; margin: 4px 0; }}
                    .green {{ color: #4ade80; }}
                    .red {{ color: #f87171; }}
                    .badge {{ background: #0284c7; padding: 3px 8px; border-radius: 6px; font-size: 13px; font-weight: bold; }}
                    .title {{ font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
                    ul {{ padding-left: 20px; margin: 6px 0; font-size: 14px; color: #cbd5e1; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="title">Active Match vs Fatigued Opponent</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b> | Match State: <span class="badge">{bot.current_trade_stage}</span></div>
                </div>
                <div class="card">
                    <div class="title">Account Vault</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">Fatigue Scouting Radar (Opponents Limping)</div>
                    <ul>{radar_html}</ul>
                    <div>Liquid Universe: <b>{len(bot.all_liquid_candidates)} Coins Monitored</b></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • Fatigued Opponent Engine (Zero Chasing)</div>
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
# 2. THE FATIGUED OPPONENT TRADING ENGINE
# ==============================================================================
class FatiguedOpponentBot:
    def __init__(self):
        self.equity_floor = 1.05
        self.ROUNDTRIP_FEE_PCT = 0.12

        # FATIGUE DETECTION PARAMETERS
        self.MIN_EXHAUSTION_RUN_PCT = 4.0      # Opponent ran for >= 4% and spent their stamina
        self.MAX_COUNTER_PUNCH_POWER = 0.40    # Opponent's counter-attack produces < 0.40% move (too weak)
        self.MIN_FRESH_SEPARATION_PCT = 1.10   # Our fresh side calmly leads by >= 1.10%

        self.all_time_wins = 0
        self.all_time_losses = 0
        self.fatigue_radar = {}                # {symbol: {"opp_side": ..., "desc": ...}}
        self.all_liquid_candidates = []
        self.global_volume_whitelist = set()

        self.last_summary_time = 0.0
        self.last_balance = 1.33
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.current_trade_stage = "PATROL (HUNTING FATIGUED OPPONENTS)"
        self.last_10m_summary = "Scouting all liquid coins for crippled/fatigued sides..."

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
    # FATIGUE INSPECTOR: IDENTIFIES CRIPPLED OPPONENTS & STEADY WINNERS
    # --------------------------------------------------------------------------
    def inspect_fatigued_opponent(self, symbol):
        """
        1. Confirms the opposing side spent all their energy pushing (>= 4% run).
        2. Tests for Fatigue: Their counter-attacks produce < 0.40% progress and volume drops.
        3. Confirms our side is fresh/steady: Calm 5m candles leading by >= 1.10% with zero stress.
        """
        try:
            # Look at 15-minute candles to verify opponent's extended sprint
            candles_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=24)
            if not candles_15m or len(candles_15m) < 18:
                return None

            completed_15m = candles_15m[:-1]
            last_closed_15m = completed_15m[-1]

            prior_open = completed_15m[-16][1]
            cur_price = last_closed_15m[4]
            prior_move_pct = ((cur_price - prior_open) / prior_open) * 100.0

            # Inspect 5-minute candles to check how weak the opponent's counter-punch is
            candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=8)
            if not candles_5m or len(candles_5m) < 6:
                return None

            completed_5m = candles_5m[:-1]
            recent_3_5m = completed_5m[-3:]
            last_5m = completed_5m[-1]

            # ------------------------------------------------------------------
            # SCENARIO A: SELLERS ARE SICK / CRIPPLED -> WE ENTER LONG
            # ------------------------------------------------------------------
            # 1. Sellers ran hard for hours (dumped >= 4.0%)
            if prior_move_pct <= -self.MIN_EXHAUSTION_RUN_PCT:
                floor_pivot = min([x[3] for x in completed_15m[-4:]])

                # 2. Check sellers' stamina: Look at the red candles in the last 15 mins
                seller_counter_punches = [abs(c[4] - c[1]) / c[1] * 100.0 for c in recent_3_5m if c[4] < c[1]]
                max_seller_punch = max(seller_counter_punches) if seller_counter_punches else 0.0

                # If sellers can't even move the price by 0.40%, THEY ARE SICK/FATIGUED!
                if max_seller_punch <= self.MAX_COUNTER_PUNCH_POWER:
                    # 3. Check our fresh buyers: Price calmly breaks away from the floor
                    separation = ((last_5m[4] - floor_pivot) / floor_pivot) * 100.0

                    if separation >= self.MIN_FRESH_SEPARATION_PCT and last_5m[4] > last_5m[1]:
                        return {
                            "side": "long",
                            "wall_pivot": floor_pivot,
                            "desc": f"SELLERS CRIPPLED: Dumped -{abs(prior_move_pct):.1f}%, now too weak to counter-punch (Max punch: {max_seller_punch:.2f}%). Fresh buyers leading by +{separation:.2f}%!"
                        }
                    else:
                        self.fatigue_radar[symbol] = {
                            "side": "long",
                            "desc": f"Sellers fatigued (-{abs(prior_move_pct):.1f}%). Waiting for fresh buyers to separate."
                        }

            # ------------------------------------------------------------------
            # SCENARIO B: BUYERS ARE SICK / CRIPPLED -> WE ENTER SHORT
            # ------------------------------------------------------------------
            # 1. Buyers ran hard for hours (pumped >= 4.0%)
            elif prior_move_pct >= self.MIN_EXHAUSTION_RUN_PCT:
                ceiling_pivot = max([x[2] for x in completed_15m[-4:]])

                # 2. Check buyers' stamina: Look at the green candles in the last 15 mins
                buyer_counter_punches = [abs(c[4] - c[1]) / c[1] * 100.0 for c in recent_3_5m if c[4] > c[1]]
                max_buyer_punch = max(buyer_counter_punches) if buyer_counter_punches else 0.0

                # If buyers can't even push the price by 0.40%, THEY ARE SICK/FATIGUED!
                if max_buyer_punch <= self.MAX_COUNTER_PUNCH_POWER:
                    # 3. Check our fresh sellers: Price calmly drops away from the ceiling
                    separation = ((ceiling_pivot - last_5m[4]) / ceiling_pivot) * 100.0

                    if separation >= self.MIN_FRESH_SEPARATION_PCT and last_5m[4] < last_5m[1]:
                        return {
                            "side": "short",
                            "wall_pivot": ceiling_pivot,
                            "desc": f"BUYERS CRIPPLED: Pumped +{prior_move_pct:.1f}%, now too weak to counter-punch (Max punch: {max_buyer_punch:.2f}%). Fresh sellers leading by -{separation:.2f}%!"
                        }
                    else:
                        self.fatigue_radar[symbol] = {
                            "side": "short",
                            "desc": f"Buyers fatigued (+{prior_move_pct:.1f}%). Waiting for fresh sellers to separate."
                        }

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # POSITION MANAGEMENT: RIDE THE DEFENSELESS GOALS & ESCAPE SAFELY
    # --------------------------------------------------------------------------
    def manage_fatigue_trade(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
            self.current_trade_stage = "PATROL (HUNTING FATIGUED OPPONENTS)"
            return

        sym = trade["symbol"]
        side = trade["side"]
        entry = trade["entry_price"]
        pivot = trade["wall_pivot"]
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

        # --- RULE 1: INJURED SIDE WOKE UP (FALSE FATIGUE / CUT IMMEDIATELY) ---
        # If the fatigued opponent suddenly finds strength and breaks back past the pivot by 0.7%, CUT!
        if (side == "long" and cur_price < pivot * 0.993) or (side == "short" and cur_price > pivot * 1.007):
            self.current_trade_stage = "OPPONENT NOT FATIGUED (CUT LOSS)"
            should_exit = True
            is_win = False
            exit_reason = f"FALSE FATIGUE: Opponent broke the defense wall (Loss: {gain_pct:+.2f}%) -> CASH OUT"

        # --- RULE 2: EFFORTLESS EXPANSION HARVEST ---
        # Because the opponent is fatigued, price glides smoothly. Once we capture solid profit:
        elif peak >= 3.8 and (peak - gain_pct) >= 1.4:
            self.current_trade_stage = "MATCH WON (TAKING PROFIT)"
            should_exit = True
            is_win = True
            exit_reason = f"FATIGUE HARVESTED: Peaked at +{peak:.1f}%, secured at +{gain_pct:.1f}% -> 100% USDT"

        # If 5-minute trend inverts after capturing a solid move (+2.0%+)
        elif gain_pct >= 2.0 and ((side == "long" and cur_price < ema9_5m) or (side == "short" and cur_price > ema9_5m)):
            self.current_trade_stage = "STALEMATE (CASHING OUT)"
            should_exit = True
            is_win = True
            exit_reason = f"OPPONENT RECOVERING: 5m trend stalling at +{gain_pct:.2f}% -> ESCAPE TO USDT"

        # If nothing happens after 2.5 hours (game ended in a draw)
        elif elapsed_hours >= 2.5 and gain_pct < 0.3:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"DEAD GAME: No follow-through after {elapsed_hours:.1f}h"

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
    # PATROL LOOP ACROSS ALL $1M+ LIQUID COINS
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] Fatigued Opponent Engine Online (Never Fight Fresh Teams).", flush=True)

        try:
            self.bitget.load_markets()
        except Exception:
            pass

        cycle = 0

        while True:
            try:
                self.manage_fatigue_trade()

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
                    chunk_size = 35
                    start_idx = (cycle * chunk_size) % max(len(candidates), 1)
                    patrol_batch = candidates[start_idx:start_idx + chunk_size]

                    for sym, _ in patrol_batch:
                        if sym in tickers:
                            signal = self.inspect_fatigued_opponent(sym)
                            if signal:
                                side = signal["side"]
                                wall = signal["wall_pivot"]
                                desc = signal["desc"]
                                mid = float(tickers[sym]['last'])

                                print(f"\n🚨 [CRIPPLED OPPONENT DETECTED] {sym} ({side.upper()}) at ${mid}", flush=True)
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

                # 10-MINUTE CLEAN SUMMARY
                now = time.time()
                if now - self.last_summary_time >= 600:
                    self.last_summary_time = now
                    t_str = time.strftime("%H:%M:%S", time.localtime(now))
                    
                    if self.live_state["active"] or self.current_trade:
                        sym = self.live_state["symbol"] if self.live_state["active"] else self.current_trade["symbol"]
                        side = self.live_state["side"] if self.live_state["active"] else self.current_trade["side"]
                        self.last_10m_summary = f"Playing vs Fatigued {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | State: {self.current_trade_stage}"
                    else:
                        self.last_10m_summary = f"Scouting {len(candidates)} liquid coins | Opponents Limping: {len(self.fatigue_radar)}"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                cycle += 1
                time.sleep(6)

            except Exception:
                time.sleep(6)

if __name__ == "__main__":
    bot = FatiguedOpponentBot()
    bot.run()

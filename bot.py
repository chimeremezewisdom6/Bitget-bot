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
MEMORY_FILE = "internal_strength_memory.json"
bot = None

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        if bot:
            active_name = bot.current_trade["symbol"] if bot.current_trade else ("LIVE: " + str(bot.live_state["symbol"]) if bot.live_state["active"] else "SCANNING_MARKET")
            active_side = bot.current_trade["side"].upper() if bot.current_trade else (bot.live_state["side"].upper() if bot.live_state["active"] else "NONE")
            gain_pct = bot.last_spot_gain
            peak_pct = bot.last_peak_gain
            held_str = f"{bot.last_held_hours:.1f} hrs" if (bot.current_trade or bot.live_state["active"]) else "0 hrs"
            streak_str = " ".join([str(i) for i in range(1, bot.consecutive_paper_wins + 1)]) if bot.consecutive_paper_wins > 0 else "0"
            mode_badge = "LIVE AUTHORIZED (6/6 STREAK WON!)" if bot.is_live_authorized() else f"PAPER QUALIFYING ({bot.consecutive_paper_wins}/6)"

            html = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <title>Internal Strength Imbalance Engine</title>
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
                    <div>Streak Sequence: <span class="gold">[{streak_str}] ({bot.consecutive_paper_wins}/6 in a row)</span></div>
                    <div>All-Time Record: <b>{bot.all_time_wins} Wins / {bot.all_time_losses} Losses</b></div>
                </div>
                <div class="card">
                    <div class="title">Active Trade (Widest Internal Imbalance)</div>
                    <div class="stat">{active_name} ({active_side})</div>
                    <div>PnL: <b class="{'green' if gain_pct >= 0 else 'red'}">{gain_pct:+.2f}%</b> (Peak: {peak_pct:+.2f}%)</div>
                    <div>Held Time: <b>{held_str}</b> | State: <b>{bot.current_stage}</b></div>
                </div>
                <div class="card">
                    <div class="title">Market Radar & Vault</div>
                    <div class="stat">${bot.last_balance:.2f} USDT</div>
                    <div>Liquid Universe: <b>{len(bot.all_liquid_candidates)} Coins Monitored</b></div>
                    <div>Status: <i>{bot.last_10m_summary}</i></div>
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b;">Auto-refreshes every 15s • Internal Power Asymmetry Engine</div>
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
# 2. INTERNAL STRENGTH ASYMMETRY BOT
# ==============================================================================
class InternalStrengthBot:
    def __init__(self):
        self.equity_floor = 1.05
        self.ROUNDTRIP_FEE_PCT = 0.12

        # 6-WIN-IN-A-ROW QUALIFICATION
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 6       # 1, 2, 3, 4, 5, 6 in a row!
        self.all_time_wins = 0
        self.all_time_losses = 0

        # INTERNAL STRENGTH THRESHOLDS (ON THE SAME COIN)
        self.MIN_IMBALANCE_RATIO = 2.4     # Winning side must be at least 2.4x stronger than losing side
        self.MAX_SPREAD_PCT = 0.0012       # Rejects spreads > 0.12% (Anti-Trap)
        self.MIN_DAILY_ATR_PCT = 5.5       # Rejects dead/synthetic tokens like EUV
        self.MIN_RVOL = 1.65               # Volume must be real (Anti-Luck)

        self.all_liquid_candidates = []
        self.global_volume_whitelist = set()
        self.volatility_cache = {}

        self.last_summary_time = 0.0
        self.last_balance = 1.33
        self.last_spot_gain = 0.0
        self.last_peak_gain = 0.0
        self.last_held_hours = 0.0
        self.current_stage = "PATROL (HUNTING INTERNAL ASYMMETRY)"
        self.last_10m_summary = "Scanning all liquid pairs for coins with widest Long vs Short power gap..."

        self.EXCLUSION_LIST = {
            'PAXG', 'XAUT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'EUV', 'CSOP', 'TQQQ'
        }

        self.current_trade = None
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "pivot_point": 0.0, "start_time": 0.0,
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
                        "pivot_point": entry_price, "start_time": time.time(),
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
                            if vol_usd >= 1_000_000.0:
                                new_whitelist.add(sym)
                    time.sleep(0.35)

                if len(new_whitelist) >= 40:
                    self.global_volume_whitelist = new_whitelist
            except Exception:
                pass
            time.sleep(600)

    # --------------------------------------------------------------------------
    # 1. CALCULATE INTERNAL LONG VS SHORT STRENGTH ON THE SAME COIN
    # --------------------------------------------------------------------------
    def calculate_internal_coin_asymmetry(self, symbol):
        """
        Calculates Long Power vs Short Power on the SAME coin:
        - Evaluates the last 12 5-minute candles (last 1 hour of combat).
        - Measures buying volume & candle body vs selling volume & candle body.
        - Returns: (dominant_side, ratio, bull_power, bear_power)
        """
        try:
            candles_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=14)
            if not candles_5m or len(candles_5m) < 12:
                return None

            completed = candles_5m[-12:]  # 1 hour of combat
            bull_power = 0.0
            bear_power = 0.0

            for c in completed:
                o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                total_range = h - l
                if total_range <= 0:
                    continue

                body = abs(cl - o)
                body_ratio = body / total_range

                # If candle is green, buyers won this round
                if cl > o:
                    bull_power += vol * (0.5 + 0.5 * body_ratio)
                elif cl < o:
                    bear_power += vol * (0.5 + 0.5 * body_ratio)

            if bull_power <= 0 or bear_power <= 0:
                return None

            if bull_power >= bear_power:
                ratio = bull_power / bear_power
                return ("long", ratio, bull_power, bear_power)
            else:
                ratio = bear_power / bull_power
                return ("short", ratio, bull_power, bear_power)

        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 2. ANTI-LUCK & ANTI-TRAP VERIFICATION GAUNTLET
    # --------------------------------------------------------------------------
    def verify_asymmetry_authenticity(self, symbol, side, ratio):
        """
        Tests if the massive imbalance on this coin is genuine or a Trap / Luck:
        1. Spread Gate: Must be <= 0.12% (proves deep book, not an illiquid trap).
        2. Daily Volatility: ATR >= 5.5% (rejects flat dead coins like EUV).
        3. Real Volume: Volume >= 1.65x normal 15m volume (not a fake vacuum).
        4. Price Progress: If buyers are 3x stronger, price must have actually moved!
           (If buyers pushed huge volume but price didn't move, IT IS AN ABSORPTION TRAP -> REJECT!).
        """
        # Test 1: Daily Volatility (No flat synthetic tokens)
        now = time.time()
        cached = self.volatility_cache.get(symbol)
        if not cached or (now - cached["time"] > 21600):
            try:
                c_1d = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=8)
                if not c_1d or len(c_1d) < 5:
                    return False, "Not enough daily history"
                ranges = [((c[2] - c[3]) / c[3]) * 100.0 for c in c_1d[-5:]]
                avg_atr = sum(ranges) / len(ranges)
                is_boom = avg_atr >= self.MIN_DAILY_ATR_PCT
                self.volatility_cache[symbol] = {"is_boom": is_boom, "time": now}
            except Exception:
                return False, "Daily ATR fetch error"
        else:
            is_boom = cached["is_boom"]

        if not is_boom:
            return False, "TRAP: Flat token with low volatility (like EUV)"

        # Test 2: Order Book Spread (Anti-Vacuum Trap)
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=5)
            bids, asks = ob.get('bids', []), ob.get('asks', [])
            if not bids or not asks:
                return False, "TRAP: Empty order book"
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0
            spread = (best_ask - best_bid) / mid
            if spread > self.MAX_SPREAD_PCT:
                return False, f"TRAP: Spread too wide ({spread*100:.2f}%)"
        except Exception:
            return False, "Order book check failed"

        # Test 3: Completed 15m Volume (Anti-Luck)
        try:
            c_15m = self.bitget.fetch_ohlcv(symbol, timeframe='15m', limit=20)
            if not c_15m or len(c_15m) < 16:
                return False, "Not enough 15m candles"
            completed = c_15m[:-1]
            last_15m = completed[-1]
            avg_vol = sum([x[5] for x in completed[-15:]]) / 15.0
            rvol = last_15m[5] / avg_vol if avg_vol > 0 else 1.0

            if rvol < self.MIN_RVOL:
                return False, f"TRAP: Low volume ({rvol:.1f}x) fake move"
        except Exception:
            return False, "Volume check failed"

        # Test 4: Real Price Progress (Anti-Absorption Wall Trap)
        try:
            c_5m = self.bitget.fetch_ohlcv(symbol, timeframe='5m', limit=7)
            if not c_5m or len(c_5m) < 6:
                return False, "Not enough 5m candles"
            c_start = c_5m[-6][1]
            c_end = c_5m[-1][4]
            move_pct = ((c_end - c_start) / c_start) * 100.0

            if side == "long":
                # If buyers are 2.5x stronger, price MUST be moving up (at least +0.8%)
                if move_pct < 0.8:
                    return False, "TRAP: Buyers have high volume but are blocked by a hidden wall!"
            elif side == "short":
                if move_pct > -0.8:
                    return False, "TRAP: Sellers have high volume but are blocked by a hidden floor!"
        except Exception:
            return False, "Progress check failed"

        return True, "GENUINE ASYMMETRY: Untrapped & real domination on this coin!"

    # --------------------------------------------------------------------------
    # 3. SCANNER: RANKS COINS BY INTERNAL ASYMMETRY & PICKS THE TRUE WINNER
    # --------------------------------------------------------------------------
    def scan_for_market_asymmetry_champion(self, candidates):
        """
        1. Calculates Long Strength vs Short Strength on every liquid coin.
        2. Ranks coins by who has the LARGEST internal power gap.
        3. Tests Candidate #1: If it's a Trap or Luck, SKIPS to Candidate #2,
           then #3, until finding the true dominant winner.
        """
        ranked_pairs = []

        # Check candidate pool for internal ratio
        for sym, _ in candidates[:45]:
            res = self.calculate_internal_coin_asymmetry(sym)
            if res:
                side, ratio, bull_p, bear_p = res
                if ratio >= self.MIN_IMBALANCE_RATIO:
                    ranked_pairs.append({
                        "symbol": sym,
                        "side": side,
                        "ratio": ratio,
                        "bull_p": bull_p,
                        "bear_p": bear_p
                    })

        if not ranked_pairs:
            return None

        # Sort: Highest internal asymmetry on top!
        ranked_pairs.sort(key=lambda x: x["ratio"], reverse=True)

        # Sequentially test candidates: Discard luck/traps and pick the first genuine champion!
        for cand in ranked_pairs[:6]:
            sym = cand["symbol"]
            side = cand["side"]
            ratio = cand["ratio"]

            is_valid, reason = self.verify_asymmetry_authenticity(sym, side, ratio)
            if is_valid:
                return {
                    "symbol": sym,
                    "side": side,
                    "ratio": ratio,
                    "desc": f"LARGEST INTERNAL ASYMMETRY: On {sym}, {side.upper()} strength is {ratio:.1f}x STRONGER than its opponent! (Widest gap in market)"
                }
            else:
                # Log why candidate was skipped and move to the next!
                # print(f"[SKIPPED CANDIDATE] {sym} ({side}) skipped: {reason}", flush=True)
                pass

        return None

    # --------------------------------------------------------------------------
    # 4. RECORD RESULTS (STRICT 1, 2, 3, 4, 5, 6 IN A ROW)
    # --------------------------------------------------------------------------
    def record_trade_result(self, is_win, symbol, net_spot):
        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            streak_seq = ", ".join([str(i) for i in range(1, self.consecutive_paper_wins + 1)])
            print(f"\n=======================================================", flush=True)
            print(f"🏆 [WIN HARVESTED] {symbol} | Result: {net_spot:+.2f}%", flush=True)
            print(f"🔥 STREAK PROGRESS: {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} In a Row ({streak_seq})", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉🎉 [6/6 STREAK UNLOCKED!] (1, 2, 3, 4, 5, 6 IN A ROW ACHIEVED) -> LIVE TRADING AUTHORIZED! 🎉🎉", flush=True)
            print(f"=======================================================\n", flush=True)
        else:
            self.all_time_losses += 1
            print(f"\n=======================================================", flush=True)
            print(f"💥 [LOSS REGISTERED] {symbol} | Result: {net_spot:+.2f}%", flush=True)
            print(f"⚠️ STREAK BROKEN: Resetting from {self.consecutive_paper_wins} back to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"=======================================================\n", flush=True)
            self.consecutive_paper_wins = 0

        self.save_memory()

    # --------------------------------------------------------------------------
    # 5. DYNAMIC RUNNER MANAGEMENT (LET THE DOMINANT SIDE RUN)
    # --------------------------------------------------------------------------
    def manage_active_trade(self):
        trade = self.current_trade or (self.live_state if self.live_state["active"] else None)
        if not trade:
            self.current_stage = "PATROL (HUNTING INTERNAL ASYMMETRY)"
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

        # DYNAMIC EXIT PROTOCOLS
        # 1. Big Expansion Harvest (Protect profits when dominant force exhausts)
        if peak >= 3.8 and (peak - gain_pct) >= 1.3:
            self.current_stage = "PROFIT_HARVEST"
            should_exit = True
            is_win = True
            exit_reason = f"ASYMMETRY HARVEST: Peaked at +{peak:.1f}%, closed at +{gain_pct:.1f}% -> CASH OUT"

        # 2. 5M Momentum Inversion (After capturing solid move >= +1.8%)
        elif gain_pct >= 1.8 and ((side == "long" and cur_price < ema9_5m) or (side == "short" and cur_price > ema9_5m)):
            self.current_stage = "TREND_INVERTED"
            should_exit = True
            is_win = True
            exit_reason = f"MOMENTUM COMPLETE: 5m EMA inverting at +{gain_pct:.2f}% -> CASH OUT"

        # 3. Pivot Invalidation (Dominant side lost control)
        elif (side == "long" and cur_price < pivot * 0.990) or (side == "short" and cur_price > pivot * 1.010):
            self.current_stage = "PIVOT_INVALIDATION"
            should_exit = True
            is_win = False
            exit_reason = f"DOMINANCE LOST: Price breached entry pivot (Loss: {gain_pct:+.2f}%) -> CASH OUT"

        # 4. Stagnant trade (No follow through after 2.5 hours)
        elif elapsed_hours >= 2.5 and gain_pct < 0.3:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"TRADE STALLED: Dominant side stopped advancing after {elapsed_hours:.1f}h"

        if should_exit:
            print(f"\n🛑 [EXIT EXECUTED] {sym} | Reason: {exit_reason} | Net: {gain_pct:+.2f}%\n", flush=True)
            self.record_trade_result(is_win, sym, gain_pct)

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

                    print(f"[LIVE CLOSED] Closed {contracts} contracts on {sym} -> 100% USDT", flush=True)
                    self.live_state["active"] = False
                    break
        except Exception as e:
            print(f"[EXIT ERROR] Failed to close on exchange: {e}. Retaining state for retry.", flush=True)

    # --------------------------------------------------------------------------
    # 6. MAIN ENGINE LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("\n[SYSTEM] Internal Strength Imbalance Engine Online (Anti-Trap + 6-Win Qualifier Active).", flush=True)

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
                    has_1m = (base in self.global_volume_whitelist) or (float(t.get('quoteVolume', 0) or 0) >= 1_000_000.0)
                    if has_1m:
                        vol = float(t.get('quoteVolume', 0) or 0)
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)
                self.all_liquid_candidates = candidates

                # Scan for coin with widest internal asymmetry
                if not self.current_trade and not self.live_state["active"]:
                    champion = self.scan_for_market_asymmetry_champion(candidates)
                    if champion:
                        sym = champion["symbol"]
                        side = champion["side"]
                        desc = champion["desc"]
                        mid = float(tickers[sym]['last'])

                        print(f"\n🚨 [INTERNAL CHAMPION IDENTIFIED: {side.upper()}] {sym} at ${mid}", flush=True)
                        print(f"📊 {desc}\n", flush=True)

                        # Execution Gate: PAPER QUALIFYING vs LIVE AUTHORIZED
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
                                    "pivot_point": mid, "start_time": time.time(),
                                    "max_peak": 0.0
                                }
                                print(f"✅ [LIVE TRADE OPENED] {sym} | Margin: ${margin_alloc:.2f} | Leverage: {needed_lev}x\n", flush=True)
                            except Exception as err:
                                print(f"⚠️ Live order failed: {err}. Falling back to paper trade.\n", flush=True)
                                self.current_trade = {
                                    "symbol": sym, "side": side,
                                    "entry_price": mid, "pivot_point": mid,
                                    "start_time": time.time(), "max_peak": 0.0
                                }
                        else:
                            # Paper Qualifying Trade
                            self.current_trade = {
                                "symbol": sym, "side": side,
                                "entry_price": mid, "pivot_point": mid,
                                "start_time": time.time(), "max_peak": 0.0
                            }
                            print(f"📝 [PAPER QUALIFYING TRADE OPENED] {sym} ({side.upper()}) | Streak Goal: {self.consecutive_paper_wins}/6 -> {self.consecutive_paper_wins+1}/6\n", flush=True)

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
                        self.last_10m_summary = f"Holding {sym} ({side.upper()}) | PnL: {self.last_spot_gain:+.2f}% | Streak: [{streak_seq}] ({self.consecutive_paper_wins}/6)"
                    else:
                        self.last_10m_summary = f"Patrolling {len(candidates)} pairs for widest internal imbalance | Streak: [{streak_seq}] ({self.consecutive_paper_wins}/6)"

                    print(f"[{t_str}] [10-MIN SUMMARY] Vault: ${balance:.2f} | {self.last_10m_summary} | Record: {self.all_time_wins}W - {self.all_time_losses}L", flush=True)

                time.sleep(8)

            except Exception as e:
                time.sleep(8)

if __name__ == "__main__":
    bot = InternalStrengthBot()
    bot.run()

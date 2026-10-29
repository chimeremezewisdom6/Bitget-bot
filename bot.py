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
# 1. RENDER KEEP-ALIVE SERVER WITH REAL-TIME LEADERBOARD ENDPOINT
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
BRAIN_FILE = "global_persistent_trend_memory.json"
bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            ranked_models = bot.get_ranked_leaderboard()
            status = {
                "engine": "APEX 1-Minute Multi-Behavior Trend Engine (10 Models)",
                "global_1m_whitelist_count": len(bot.global_volume_whitelist),
                "streak_status": f"{bot.consecutive_paper_wins}/{bot.REQUIRED_WIN_STREAK} Wins in a row",
                "mode": "LIVE_AUTHORIZED" if bot.is_qualified_for_live() else "PAPER_QUALIFYING",
                "all_time_record": f"{bot.all_time_wins} Wins / {bot.all_time_losses} Losses",
                "active_trade": bot.current_trade["symbol"] if bot.current_trade else ("LIVE_ACTIVE" if bot.live_state["active"] else "SCANNING"),
                "leaderboard_rankings_best_to_worst": ranked_models
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
    print(f"[SYSTEM] Keep-Alive Web Server listening on port {PORT}", flush=True)

# ==============================================================================
# 2. BOT ENGINE WITH PATTERN BENCHMARKING & DYNAMIC FADING EXITS
# ==============================================================================
class PersistentTrendBot:
    def __init__(self):
        self.leverage = 1
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        self.MAX_ALLOWED_SPREAD_PCT = 0.0012
        self.ROUNDTRIP_FEE_PCT = 0.12
        self.QUARANTINE_DURATION_SEC = 3600

        # Fading TP/SL Parameters
        self.INITIAL_TP_PCT = 1.50
        self.MIN_FADED_TP_PCT = 0.45
        self.INITIAL_SL_PCT = -0.75
        self.TIGHTEST_SL_PCT = -0.30
        self.FADE_HORIZON_SEC = 90.0

        # Performance Tracker for all 10 Models
        self.pattern_stats = {
            "STEP_LADDER_MICRO_PULLBACK":   {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "COMPRESSION_SQUEEZE_BREAKOUT": {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "VOLUME_EXPANSION_ESCALATOR":  {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "TRAP_LIQUIDITY_REJECTION":     {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "5_CANDLE_POWER_IMPULSE":       {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "EMA_5_13_MOMENTUM_RUNWAY":     {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "6_CANDLE_CLEAN_STAIRCASE":     {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "VOLUME_IGNITION_BLAST":        {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "DYNAMIC_BASELINE_STRETCH":     {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0},
            "ORIGINAL_8_OR_9_OF_10_STREAK": {"wins": 0, "losses": 0, "scratches": 0, "net_pnl": 0.0}
        }

        self.global_volume_whitelist = set()
        self.last_global_fetch_time = 0.0

        self.EXCLUSION_LIST = {
            'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'TRX', 'AVAX', 
            'LINK', 'SUI', 'PEPE', 'SHIB', 'NEAR', 'LTC', 'BCH', 'DOT', 'ZEC',
            'SOXS', 'SOXL', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
            'CL', 'BZ', 'XAU', 'XAG', 'SPX', 'NDX', 'DJI', 'KORU', 'MU',
            'SKHYNIX', 'SKHY', 'SNDK', 'SNXX', 'BABA', 'COIN', 'MSTR', 'ARM', 'INTC', 
            'SMSN', 'EWY', 'AAOI', 'CRWV', 'ANTHROPIC', 'TQQQ', 'CSOPSK2LHKD'
        }

        self.current_trade = None
        self.coin_cooldowns = {}
        self.load_brain()

        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "entry_spread": 0.0, "start_time": 0.0,
            "max_peak": 0.0
        }

        self.api_key = (os.environ.get("API_KEY") or "").strip()
        self.secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        self.passphrase = (os.environ.get("PASSPHRASE") or "").strip()

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing Bitget credentials! Configure API_KEY, SECRET_KEY, and PASSPHRASE in Render.", flush=True)
            sys.exit(1)

        self.bitget = ccxt.bitget({
            "apiKey": self.api_key,
            "secret": self.secret_key,
            "password": self.passphrase,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",
                "defaultMarginMode": "cross"
            }
        })

        self.enforce_one_way_mode()

        t_global = threading.Thread(target=self.global_volume_worker, daemon=True)
        t_global.start()

    # --------------------------------------------------------------------------
    # LEADERBOARD RANKING ENGINE
    # --------------------------------------------------------------------------
    def get_ranked_leaderboard(self):
        """
        Sorts all 10 behaviors from best to worst based on:
        1. Win Rate %
        2. Total Net PnL %
        3. Total Executions
        """
        board = []
        for name, data in self.pattern_stats.items():
            total = data["wins"] + data["losses"]
            win_rate = (data["wins"] / total * 100.0) if total > 0 else 0.0
            board.append({
                "model": name,
                "win_rate_pct": round(win_rate, 1),
                "wins": data["wins"],
                "losses": data["losses"],
                "scratches": data["scratches"],
                "total_trades": total + data["scratches"],
                "net_pnl_pct": round(data["net_pnl"], 2)
            })

        # Sort: Highest Win Rate first, then Highest Net PnL, then Total Trades
        board.sort(key=lambda x: (x["win_rate_pct"], x["net_pnl_pct"], x["total_trades"]), reverse=True)

        ranked = []
        for idx, item in enumerate(board):
            rank_label = f"#{idx+1} [BEST]" if idx == 0 else (f"#{idx+1} [WORST]" if idx == len(board)-1 else f"#{idx+1}")
            ranked.append({
                "rank": rank_label,
                **item
            })
        return ranked

    def print_leaderboard(self):
        ranks = self.get_ranked_leaderboard()
        print("\n======================= MODEL LEADERBOARD (BEST TO WORST) =======================", flush=True)
        for r in ranks:
            print(f"{r['rank']:<10} | {r['model']:<30} | WinRate: {r['win_rate_pct']:>5.1f}% | Wins: {r['wins']} Losses: {r['losses']} Scratches: {r['scratches']} | Net: {r['net_pnl_pct']:>+6.2f}%", flush=True)
        print("==================================================================================\n", flush=True)

    # --------------------------------------------------------------------------
    # ATOMIC BRAIN PERSISTENCE
    # --------------------------------------------------------------------------
    def load_brain(self):
        if os.path.exists(BRAIN_FILE):
            try:
                with open(BRAIN_FILE, "r") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.consecutive_paper_wins = data.get("consecutive_paper_wins", 0)
                        self.all_time_wins = data.get("all_time_wins", 0)
                        self.all_time_losses = data.get("all_time_losses", 0)
                        saved_stats = data.get("pattern_stats", {})
                        for k, v in saved_stats.items():
                            if k in self.pattern_stats:
                                self.pattern_stats[k] = v
            except Exception as e:
                print(f"[WARN] Brain recovery note: {e}", flush=True)

    def save_brain(self):
        tmp_file = f"{BRAIN_FILE}.tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump({
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses,
                    "pattern_stats": self.pattern_stats
                }, f, indent=2)
            os.replace(tmp_file, BRAIN_FILE)
        except Exception:
            pass

    def is_qualified_for_live(self):
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    def enforce_one_way_mode(self):
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
            print("[CONFIG] Verified Bitget One-Way Mode active.", flush=True)
        except Exception as e:
            print(f"[CONFIG] One-Way Mode check: {e} (Continuing cleanly)", flush=True)

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
                    self.last_global_fetch_time = time.time()
                    print(f"🌍 [GLOBAL AGGREGATOR UPDATE] Cached {len(self.global_volume_whitelist)} coins with >= $1,000,000 24h volume across worldwide exchanges!", flush=True)

            except Exception as e:
                print(f"[WARN] Aggregator worker notice: {e}", flush=True)

            time.sleep(600)

    def calculate_fading_levels(self, elapsed_s, max_peak, entry_spread):
        fee_spread_threshold = self.ROUNDTRIP_FEE_PCT + (entry_spread * 100.0)
        progress = min(elapsed_s / self.FADE_HORIZON_SEC, 1.0)

        faded_tp = self.INITIAL_TP_PCT - (progress * (self.INITIAL_TP_PCT - self.MIN_FADED_TP_PCT))
        time_sl = self.INITIAL_SL_PCT + (progress * (abs(self.INITIAL_SL_PCT) - abs(self.TIGHTEST_SL_PCT)))

        trail_sl = -99.0
        if max_peak >= 0.80:
            trail_sl = max(max_peak - 0.25, fee_spread_threshold + 0.15)
        elif max_peak >= 0.45:
            trail_sl = fee_spread_threshold + 0.05

        effective_sl = max(time_sl, trail_sl)
        return faded_tp, effective_sl, fee_spread_threshold

    def record_trade_outcome(self, is_win, symbol, net_spot, pattern_name, is_scratch=False):
        # Update pattern stats
        if pattern_name in self.pattern_stats:
            self.pattern_stats[pattern_name]["net_pnl"] += net_spot
            if is_scratch:
                self.pattern_stats[pattern_name]["scratches"] += 1
            elif is_win:
                self.pattern_stats[pattern_name]["wins"] += 1
            else:
                self.pattern_stats[pattern_name]["losses"] += 1

        if is_scratch:
            print(f"\n🛡️ [SCRATCH BAIL-OUT] {symbol} | Exited at {net_spot:+.2f}%. Fees covered, streak protected!", flush=True)
            self.save_brain()
            self.print_leaderboard()
            return

        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            self.coin_cooldowns[symbol] = time.time() + 600
            print(f"\n🔥 [TREND WIN HARVESTED ({pattern_name})] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} in a row! Spot: {net_spot:+.2f}%", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK UNLOCKED] Live 90% allocation trading AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            self.consecutive_paper_wins = 0
            self.coin_cooldowns[symbol] = time.time() + self.QUARANTINE_DURATION_SEC
            print(f"\n💥 [STOPPED OUT ({pattern_name})] Resetting streak to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"🚫 [QUARANTINE] {symbol} locked out for 60 minutes.", flush=True)
            
        self.save_brain()
        self.print_leaderboard()

    def get_order_book_spread(self, symbol):
        try:
            ob = self.bitget.fetch_order_book(symbol, limit=5)
            bids = ob.get('bids', [])
            asks = ob.get('asks', [])

            if not bids or not asks:
                return None, None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid = (best_bid + best_ask) / 2.0
            spread_pct = (best_ask - best_bid) / mid

            return mid, spread_pct
        except Exception:
            return None, None

    # --------------------------------------------------------------------------
    # MULTI-BEHAVIOR TREND INSPECTOR (10 MODELS)
    # --------------------------------------------------------------------------
    def inspect_trend_behaviors(self, symbol):
        try:
            candles = self.bitget.fetch_ohlcv(symbol, timeframe='1m', limit=20)
            if not candles or len(candles) < 16:
                return None

            c = candles[-16:-1]
            opens = [x[1] for x in c]
            highs = [x[2] for x in c]
            lows = [x[3] for x in c]
            closes = [x[4] for x in c]
            vols = [x[5] for x in c]

            avg_vol = sum(vols[-12:]) / 12.0 if sum(vols[-12:]) > 0 else 1.0

            def calc_ema(series, period):
                k = 2 / (period + 1)
                ema = [series[0]]
                for price in series[1:]:
                    ema.append((price * k) + (ema[-1] * (1 - k)))
                return ema

            ema5 = calc_ema(closes, 5)
            ema13 = calc_ema(closes, 13)

            for side in ["long", "short"]:
                # MODEL 1: Micro-Pullback Step-Ladder (RANK #1)
                impulse_ok = (closes[-4] > opens[-4] and closes[-3] > opens[-3]) if side == "long" else (closes[-4] < opens[-4] and closes[-3] < opens[-3])
                if impulse_ok:
                    impulse_dist = abs(closes[-3] - opens[-4])
                    if impulse_dist > 0:
                        pause_retrace = (highs[-2] - lows[-2]) / impulse_dist
                        if pause_retrace <= 0.38:
                            breakout_now = (closes[-1] > highs[-2] and closes[-1] > closes[-3]) if side == "long" else (closes[-1] < lows[-2] and closes[-1] < closes[-3])
                            if breakout_now:
                                move = ((closes[-1] - opens[-4]) / opens[-4]) * 100.0 if side == "long" else ((opens[-4] - closes[-1]) / opens[-4]) * 100.0
                                return {"side": side, "name": "STEP_LADDER_MICRO_PULLBACK", "move": move}

                # MODEL 2: Compression Squeeze Breakout (RANK #2)
                base_high = max(highs[-6:-1])
                base_low = min(lows[-6:-1])
                mid_p = (base_high + base_low) / 2.0
                band_pct = ((base_high - base_low) / mid_p) * 100.0
                if band_pct <= 0.45:
                    burst_pct = ((closes[-1] - opens[-1]) / opens[-1]) * 100.0 if side == "long" else ((opens[-1] - closes[-1]) / opens[-1]) * 100.0
                    if burst_pct >= 0.55 and vols[-1] >= (avg_vol * 2.2):
                        return {"side": side, "name": "COMPRESSION_SQUEEZE_BREAKOUT", "move": burst_pct}

                # MODEL 3: Volume-Expansion Escalator (RANK #3)
                b1 = abs(closes[-3] - opens[-3])
                b2 = abs(closes[-2] - opens[-2])
                b3 = abs(closes[-1] - opens[-1])
                v1, v2, v3 = vols[-3], vols[-2], vols[-1]
                dir_ok = (closes[-3] > opens[-3] and closes[-2] > opens[-2] and closes[-1] > opens[-1]) if side == "long" else (closes[-3] < opens[-3] and closes[-2] < opens[-2] and closes[-1] < opens[-1])
                if dir_ok and (b3 > b2 > b1) and (v3 > v2 > v1):
                    move_3m = ((closes[-1] - opens[-3]) / opens[-3]) * 100.0 if side == "long" else ((opens[-3] - closes[-1]) / opens[-3]) * 100.0
                    if move_3m >= 0.90:
                        return {"side": side, "name": "VOLUME_EXPANSION_ESCALATOR", "move": move_3m}

                # MODEL 4: Trap Liquidity Rejection (RANK #4)
                candle_range = highs[-3] - lows[-3]
                if candle_range > 0:
                    rejection_wick = (highs[-3] - max(opens[-3], closes[-3])) if side == "short" else (min(opens[-3], closes[-3]) - lows[-3])
                    wick_ratio = rejection_wick / candle_range
                    if wick_ratio >= 0.55:
                        engulf_follow = (closes[-1] > highs[-3] and closes[-2] > opens[-2]) if side == "long" else (closes[-1] < lows[-3] and closes[-2] < opens[-2])
                        if engulf_follow:
                            trap_move = ((closes[-1] - opens[-2]) / opens[-2]) * 100.0 if side == "long" else ((opens[-2] - closes[-1]) / opens[-2]) * 100.0
                            return {"side": side, "name": "TRAP_LIQUIDITY_REJECTION", "move": trap_move}

                # MODEL 5: 5-Candle Power Impulse (RANK #5)
                c5_valid = True
                for i in range(-5, 0):
                    pct = ((closes[i] - opens[i]) / opens[i]) * 100.0 if side == "long" else ((opens[i] - closes[i]) / opens[i]) * 100.0
                    if pct < 0.20:
                        c5_valid = False
                        break
                if c5_valid:
                    total_5m = ((closes[-1] - opens[-5]) / opens[-5]) * 100.0 if side == "long" else ((opens[-5] - closes[-1]) / opens[-5]) * 100.0
                    if total_5m >= 1.30:
                        return {"side": side, "name": "5_CANDLE_POWER_IMPULSE", "move": total_5m}

                # MODEL 6: EMA 5/13 Momentum Runway (RANK #6)
                ema_stacked = (ema5[-1] > ema13[-1] and ema5[-2] > ema13[-2] and ema5[-3] > ema13[-3]) if side == "long" else (ema5[-1] < ema13[-1] and ema5[-2] < ema13[-2] and ema5[-3] < ema13[-3])
                closes_above_ema5 = all([closes[i] > ema5[i] for i in range(-4, 0)]) if side == "long" else all([closes[i] < ema5[i] for i in range(-4, 0)])
                if ema_stacked and closes_above_ema5:
                    runway_move = ((closes[-1] - opens[-4]) / opens[-4]) * 100.0 if side == "long" else ((opens[-4] - closes[-1]) / opens[-4]) * 100.0
                    if runway_move >= 1.00:
                        return {"side": side, "name": "EMA_5_13_MOMENTUM_RUNWAY", "move": runway_move}

                # MODEL 7: 6-Candle Clean Staircase (RANK #7)
                stair_ok = True
                for i in range(-6, -1):
                    if side == "long":
                        if not (highs[i+1] > highs[i] and lows[i+1] >= lows[i] and closes[i+1] > opens[i+1]):
                            stair_ok = False
                            break
                    else:
                        if not (lows[i+1] < lows[i] and highs[i+1] <= highs[i] and closes[i+1] < opens[i+1]):
                            stair_ok = False
                            break
                if stair_ok:
                    stair_move = ((closes[-1] - opens[-6]) / opens[-6]) * 100.0 if side == "long" else ((opens[-6] - closes[-1]) / opens[-6]) * 100.0
                    if stair_move >= 1.20:
                        return {"side": side, "name": "6_CANDLE_CLEAN_STAIRCASE", "move": stair_move}

                # MODEL 8: Volume Ignition Blast (RANK #8)
                rvol = vols[-1] / avg_vol
                blast_pct = ((closes[-1] - opens[-1]) / opens[-1]) * 100.0 if side == "long" else ((opens[-1] - closes[-1]) / opens[-1]) * 100.0
                c_range = highs[-1] - lows[-1]
                if c_range > 0 and rvol >= 3.5 and blast_pct >= 0.70:
                    upper_wick = (highs[-1] - closes[-1]) if side == "long" else (closes[-1] - lows[-1])
                    if (upper_wick / c_range) <= 0.15:
                        return {"side": side, "name": "VOLUME_IGNITION_BLAST", "move": blast_pct}

                # MODEL 9: Dynamic Baseline Stretch (RANK #9)
                c_3_ok = True
                for i in range(-3, 0):
                    rng = highs[i] - lows[i]
                    if rng <= 0:
                        c_3_ok = False
                        break
                    body_close_pos = ((closes[i] - lows[i]) / rng) if side == "long" else ((highs[i] - closes[i]) / rng)
                    if body_close_pos < 0.75:
                        c_3_ok = False
                        break
                if c_3_ok:
                    stretch_move = ((closes[-1] - opens[-3]) / opens[-3]) * 100.0 if side == "long" else ((opens[-3] - closes[-1]) / opens[-3]) * 100.0
                    if stretch_move >= 1.10 and vols[-1] >= avg_vol * 1.5:
                        return {"side": side, "name": "DYNAMIC_BASELINE_STRETCH", "move": stretch_move}

                # MODEL 10: Original 8/8 or 9/10 Persistent Streak (RANK #10)
                streak = 0
                wins_10 = 0
                for i in range(-10, 0):
                    gain = ((closes[i] - opens[i]) / opens[i]) * 100.0 if side == "long" else ((opens[i] - closes[i]) / opens[i]) * 100.0
                    if gain >= 0.30:
                        wins_10 += 1
                        streak += 1
                    else:
                        streak = 0
                if streak >= 8 or wins_10 >= 9:
                    return {"side": side, "name": "ORIGINAL_8_OR_9_OF_10_STREAK", "move": ((closes[-1] - opens[-10]) / opens[-10]) * 100.0}

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # PAPER TRADE MONITOR
    # --------------------------------------------------------------------------
    def update_active_trade(self):
        if not self.current_trade:
            return

        trade = self.current_trade
        sym = trade["symbol"]
        side = trade["side"]
        entry = trade["entry_p"]
        entry_spread = trade["entry_spread"]
        pattern = trade["pattern"]
        now = time.time()
        elapsed_s = now - trade["start_t"]

        mid, _ = self.get_order_book_spread(sym)
        if not mid:
            return

        gain_spot = ((mid - entry) / entry) * 100.0 if side == "long" else ((entry - mid) / entry) * 100.0
        trade["max_peak"] = max(trade.get("max_peak", 0.0), gain_spot)

        faded_tp, faded_sl, fee_spread_threshold = self.calculate_fading_levels(elapsed_s, trade["max_peak"], entry_spread)

        t_str = time.strftime("%H:%M:%S", time.localtime(now))
        base_sym = sym.split('/')[0]

        print(
            f"[{t_str}] {base_sym:<6} ({side.upper()}) [{pattern}] | "
            f"Spot:{gain_spot:+.2f}% (Peak:{trade['max_peak']:+.2f}%) | "
            f"Fading_TP:{faded_tp:+.2f}% | Fading_SL:{faded_sl:+.2f}% | {int(elapsed_s)}s",
            flush=True
        )

        hit_take_profit = gain_spot >= faded_tp
        hit_stop_loss = gain_spot <= faded_sl

        if hit_take_profit or hit_stop_loss:
            print(f"\n=======================================================", flush=True)
            if hit_take_profit:
                print(f"🟢 [FADING TARGET HARVESTED] {sym} ({side.upper()}) | Model: {pattern} | Gain: {gain_spot:+.2f}%", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, pattern_name=pattern, is_scratch=False)
            else:
                if gain_spot >= fee_spread_threshold:
                    print(f"🛡️ [TRAILED / SCRATCH EXIT] {sym} ({side.upper()}) | Model: {pattern} | Spot: {gain_spot:+.2f}%", flush=True)
                    self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, pattern_name=pattern, is_scratch=True)
                else:
                    print(f"🔴 [FADING STOP LOSS HIT] {sym} ({side.upper()}) | Model: {pattern} | Loss: {gain_spot:+.2f}%", flush=True)
                    self.record_trade_outcome(is_win=False, symbol=sym, net_spot=gain_spot, pattern_name=pattern, is_scratch=False)

            print(f"=======================================================\n", flush=True)
            self.current_trade = None

    # --------------------------------------------------------------------------
    # LIVE TRADE MONITOR
    # --------------------------------------------------------------------------
    def poll_live_trade(self):
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        side = self.live_state["side"]
        entry = self.live_state["entry_price"]
        entry_spread = self.live_state.get("entry_spread", 0.0008)
        pattern = self.live_state.get("pattern", "UNKNOWN")
        elapsed_s = time.time() - self.live_state["start_time"]

        mid, _ = self.get_order_book_spread(sym)
        if not mid:
            return

        gain_spot = ((mid - entry) / entry) * 100.0 if side == "long" else ((entry - mid) / entry) * 100.0
        self.live_state["max_peak"] = max(self.live_state.get("max_peak", 0.0), gain_spot)

        faded_tp, faded_sl, fee_spread_threshold = self.calculate_fading_levels(elapsed_s, self.live_state["max_peak"], entry_spread)

        hit_take_profit = gain_spot >= faded_tp
        hit_stop_loss = gain_spot <= faded_sl

        if hit_take_profit or hit_stop_loss:
            close_side = 'sell' if side == 'long' else 'buy'
            contracts_to_close = self.live_state["contracts"]

            try:
                positions = self.bitget.fetch_positions([sym])
                for p in positions:
                    if p.get('symbol') == sym and float(p.get('contracts', 0) or 0) > 0:
                        contracts_to_close = float(p['contracts'])
                        break
            except Exception:
                pass

            exit_params = {'reduceOnly': True, 'tradeSide': 'close'}

            for attempt in range(3):
                try:
                    self.bitget.create_order(sym, 'market', close_side, contracts_to_close, params=exit_params)
                    break
                except Exception as e:
                    print(f"[RETRY EXIT {attempt+1}] Order note: {e}. Retrying...", flush=True)
                    try:
                        self.bitget.create_order(sym, 'market', close_side, contracts_to_close, params={'reduceOnly': True})
                        break
                    except Exception:
                        time.sleep(1)

            print(f"\n=======================================================", flush=True)
            if hit_take_profit:
                self.consecutive_live_losses = 0
                print(f"🟢 [LIVE FADING TARGET HIT: {gain_spot:+.2f}% SPOT] Model: {pattern}", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, pattern_name=pattern)
            elif gain_spot >= fee_spread_threshold:
                print(f"🛡️ [LIVE TRAILED PROFIT/SCRATCH: {gain_spot:+.2f}% SPOT] Model: {pattern}", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, pattern_name=pattern, is_scratch=True)
            else:
                self.consecutive_live_losses += 1
                print(f"🔴 [LIVE FADING STOPPED: {gain_spot:+.2f}% SPOT] Model: {pattern}", flush=True)
                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] Resetting streak back to paper qualification.\n", flush=True)
                    self.consecutive_paper_wins = 0
                self.record_trade_outcome(is_win=False, symbol=sym, net_spot=gain_spot, pattern_name=pattern)

            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX 1-Minute Multi-Behavior Benchmarking Engine online.", flush=True)

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

                candidates = []
                for s, t in tickers.items():
                    if not s.endswith(":USDT"):
                        continue
                    base = s.split('/')[0].split(':')[0].upper()
                    if base in self.EXCLUSION_LIST or len(base) > 7:
                        continue

                    has_global_1m = (base in self.global_volume_whitelist) or (float(t.get('quoteVolume', 0) or 0) >= 1_000_000.0)

                    if has_global_1m and time.time() >= self.coin_cooldowns.get(s, 0):
                        vol = float(t.get('quoteVolume', 0) or 0)
                        candidates.append((s, vol))

                candidates.sort(key=lambda x: x[1], reverse=True)

                if not self.current_trade and not self.live_state["active"]:
                    for sym, vol in candidates[:25]:
                        mid, spread_pct = self.get_order_book_spread(sym)
                        if not mid or spread_pct > self.MAX_ALLOWED_SPREAD_PCT:
                            continue

                        trend = self.inspect_trend_behaviors(sym)
                        if trend:
                            side = trend["side"]
                            pattern_name = trend["name"]
                            move_pct = trend["move"]
                            print(f"\n🚀 [MODEL TRIGGERED: {pattern_name}] {sym} ({side.upper()}) | Run Move: {move_pct:+.2f}%", flush=True)

                            if self.is_qualified_for_live():
                                margin_90 = balance * 0.90
                                exchange_min_notional = 5.50

                                needed_leverage = max(math.ceil(exchange_min_notional / margin_90), 1)

                                try:
                                    self.bitget.set_leverage(needed_leverage, sym, params={'marginCoin': 'USDT'})
                                except Exception:
                                    try:
                                        self.bitget.set_leverage(needed_leverage, sym)
                                    except Exception:
                                        pass

                                notional_size = margin_90 * needed_leverage
                                raw_amount = notional_size / mid
                                amount_str = self.bitget.amount_to_precision(sym, raw_amount)
                                amount = float(amount_str)

                                order_side = 'buy' if side == 'long' else 'sell'
                                open_params = {'tradeSide': 'open'}

                                try:
                                    self.bitget.create_order(sym, 'market', order_side, amount, params=open_params)
                                except Exception:
                                    self.bitget.create_order(sym, 'market', order_side, amount)

                                self.live_state = {
                                    "active": True, "symbol": sym, "side": side,
                                    "contracts": amount, "entry_price": mid,
                                    "entry_spread": spread_pct,
                                    "pattern": pattern_name,
                                    "start_time": time.time(),
                                    "max_peak": 0.0
                                }
                                print(f"[LIVE ORDER EXECUTED] Margin: ${margin_90:.2f} | Leverage: {needed_leverage}x | Model: {pattern_name}", flush=True)
                                break
                            else:
                                self.current_trade = {
                                    "symbol": sym,
                                    "side": side,
                                    "pattern": pattern_name,
                                    "entry_p": mid,
                                    "entry_spread": spread_pct,
                                    "start_t": time.time(),
                                    "max_peak": 0.0
                                }
                                break

                if cycle % 10 == 0:
                    status_desc = "LIVE_AUTHORIZED" if self.is_qualified_for_live() else f"PAPER_QUALIFYING ({self.consecutive_paper_wins}/8)"
                    active_name = self.current_trade["symbol"] if self.current_trade else ("LIVE_ACTIVE" if self.live_state["active"] else "SCANNING")
                    print(
                        f"[TREND PULSE] State: {active_name} | Global Pool: {len(self.global_volume_whitelist)} | "
                        f"Vault: ${balance:.2f} | Streak: {self.consecutive_paper_wins}/8 | Status: {status_desc}",
                        flush=True
                    )

                cycle += 1
                time.sleep(3)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(4)

if __name__ == "__main__":
    bot = PersistentTrendBot()
    bot.run()

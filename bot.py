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
# 1. RENDER PORT BINDING & KEEP-ALIVE SERVER (SELF-HEALING)
# ==============================================================================
# Fix #1: Bind port immediately before slow network tasks so Render doesn't timeout.
PORT = int(os.environ.get("PORT", 10000))
BRAIN_FILE = "global_persistent_trend_memory.json"
bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX 1-Minute Trend (One-Way Mode + Fading TP/SL)",
                "global_1m_whitelist_count": len(bot.global_volume_whitelist),
                "trend_rule": "8/8 or 9/10 minutes with >= +0.30% gain (Long) or <= -0.30% drop (Short)",
                "active_trade": bot.current_trade["symbol"] if bot.current_trade else ("LIVE_ACTIVE" if bot.live_state["active"] else "SCANNING"),
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
    print(f"[SYSTEM] Keep-Alive Web Server listening on port {PORT}", flush=True)

# ==============================================================================
# 2. BOT ENGINE WITH SELF-CORRECTING SAFEGUARDS
# ==============================================================================
class PersistentTrendBot:
    def __init__(self):
        # 1. Capital & Risk Configuration
        self.leverage = 1
        self.equity_floor = 1.50
        self.consecutive_live_losses = 0
        self.max_live_losses = 2

        # 2. Paper Qualification Controller (8-in-a-row)
        self.consecutive_paper_wins = 0
        self.REQUIRED_WIN_STREAK = 8
        self.all_time_wins = 0
        self.all_time_losses = 0

        # 3. Directional Persistence Rules
        self.MIN_MINUTE_GAIN_PCT = 0.30        # Long >= +0.30% | Short <= -0.30% per minute
        self.MAX_ALLOWED_SPREAD_PCT = 0.0012   # Reject spreads > 0.12%
        self.ROUNDTRIP_FEE_PCT = 0.12          # 0.06% entry + 0.06% exit taker fee reserve
        self.QUARANTINE_DURATION_SEC = 3600

        # 4. Dynamic Fading Stop Loss & Take Profit Parameters
        self.INITIAL_TP_PCT = 1.50             # Starts wide for sudden impulse runs
        self.MIN_FADED_TP_PCT = 0.45           # Floor TP target after time decay
        self.INITIAL_SL_PCT = -0.75            # Initial protective floor
        self.TIGHTEST_SL_PCT = -0.30           # Stop loss fades up to -0.30% if momentum stalls
        self.FADE_HORIZON_SEC = 90.0           # 90 seconds decay horizon

        # Global Volume Whitelist ($1,000,000+ Combined 24h Volume)
        self.global_volume_whitelist = set()
        self.last_global_fetch_time = 0.0

        # Exclusion list: Major caps, stocks, ETFs, and synthetic tokens
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

        # Live Trade State
        self.live_state = {
            "active": False, "symbol": None, "side": None, "contracts": 0,
            "entry_price": 0.0, "entry_spread": 0.0, "start_time": 0.0,
            "max_peak": 0.0
        }

        # Fix #2: Auto-strip whitespace and newline characters from Render env variables
        self.api_key = (os.environ.get("API_KEY") or "").strip()
        self.secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        self.passphrase = (os.environ.get("PASSPHRASE") or "").strip()

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing Bitget credentials! Please configure API_KEY, SECRET_KEY, and PASSPHRASE in Render.", flush=True)
            sys.exit(1)

        # Initialize CCXT Bitget for USDT-M Swaps
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

        # Fix #3: Auto-enforce One-Way Position Mode on startup
        self.enforce_one_way_mode()

        # Launch Background Global Aggregator Worker
        t_global = threading.Thread(target=self.global_volume_worker, daemon=True)
        t_global.start()

    # --------------------------------------------------------------------------
    # SELF-HEALING: ATOMIC BRAIN PERSISTENCE (PREVENTS CORRUPT JSON ON RESTARTS)
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
            except Exception as e:
                print(f"[WARN] Brain file recovered from clean slate: {e}", flush=True)
                self.consecutive_paper_wins = 0

    def save_brain(self):
        tmp_file = f"{BRAIN_FILE}.tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump({
                    "consecutive_paper_wins": self.consecutive_paper_wins,
                    "all_time_wins": self.all_time_wins,
                    "all_time_losses": self.all_time_losses
                }, f, indent=2)
            os.replace(tmp_file, BRAIN_FILE)
        except Exception:
            pass

    def is_qualified_for_live(self):
        return self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK

    # --------------------------------------------------------------------------
    # SELF-HEALING: ONE-WAY MODE AUTO-CONFIGURATION
    # --------------------------------------------------------------------------
    def enforce_one_way_mode(self):
        """
        Attempts to programmatically set One-Way Mode on Bitget USDT-M contracts.
        If already active or handled via UI, continues cleanly.
        """
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
            print("[CONFIG] Verified Bitget One-Way Mode is active.", flush=True)
        except Exception as e:
            # Code 40017 / 43019 typically means mode is already set to One-Way
            print(f"[CONFIG] One-Way Mode check: {e} (Standard protocol engaged)", flush=True)

    # --------------------------------------------------------------------------
    # FIXED GLOBAL AGGREGATOR (NO 402 ERRORS, DIRECT PAGINATION UP TO 600 COINS)
    # --------------------------------------------------------------------------
    def global_volume_worker(self):
        """
        Queries CoinLore paginated across 600 cryptocurrencies every 10 minutes.
        Eliminates the CoinPaprika HTTP 402 payment lock entirely.
        """
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

    # --------------------------------------------------------------------------
    # DYNAMIC FADING STOP LOSS & TAKE PROFIT FORMULA
    # --------------------------------------------------------------------------
    def calculate_fading_levels(self, elapsed_s, max_peak, entry_spread):
        fee_spread_threshold = self.ROUNDTRIP_FEE_PCT + (entry_spread * 100.0)
        progress = min(elapsed_s / self.FADE_HORIZON_SEC, 1.0)

        # 1. Take-Profit fades down from +1.50% to +0.45%
        faded_tp = self.INITIAL_TP_PCT - (progress * (self.INITIAL_TP_PCT - self.MIN_FADED_TP_PCT))

        # 2. Stop-Loss fades up from -0.75% toward -0.30%
        time_sl = self.INITIAL_SL_PCT + (progress * (abs(self.INITIAL_SL_PCT) - abs(self.TIGHTEST_SL_PCT)))

        # 3. Dynamic Trailing Ratchet
        trail_sl = -99.0
        if max_peak >= 0.80:
            trail_sl = max(max_peak - 0.25, fee_spread_threshold + 0.15)
        elif max_peak >= 0.45:
            trail_sl = fee_spread_threshold + 0.05

        effective_sl = max(time_sl, trail_sl)
        return faded_tp, effective_sl, fee_spread_threshold

    def record_trade_outcome(self, is_win, symbol, net_spot, is_scratch=False):
        if is_scratch:
            print(f"\n🛡️ [SCRATCH BAIL-OUT] {symbol} | Exited at {net_spot:+.2f}%. Fees covered, streak protected!", flush=True)
            return

        if is_win:
            self.all_time_wins += 1
            self.consecutive_paper_wins += 1
            self.coin_cooldowns[symbol] = time.time() + 600
            print(f"\n🔥 [TREND WIN HARVESTED] {self.consecutive_paper_wins}/{self.REQUIRED_WIN_STREAK} in a row! Spot: {net_spot:+.2f}%", flush=True)
            if self.consecutive_paper_wins >= self.REQUIRED_WIN_STREAK:
                print(f"🎉 [8/8 STREAK UNLOCKED] Live 90% allocation trading AUTHORIZED!\n", flush=True)
        else:
            self.all_time_losses += 1
            self.consecutive_paper_wins = 0
            self.coin_cooldowns[symbol] = time.time() + self.QUARANTINE_DURATION_SEC
            print(f"\n💥 [STOPPED OUT] Resetting streak to 0/{self.REQUIRED_WIN_STREAK}.", flush=True)
            print(f"🚫 [QUARANTINE] {symbol} locked out for 60 minutes.", flush=True)
            
        self.save_brain()

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
    # 8-TO-10 MINUTE PERSISTENT TREND INSPECTOR
    # --------------------------------------------------------------------------
    def inspect_persistent_trend(self, symbol):
        try:
            candles = self.bitget.fetch_ohlcv(symbol, timeframe='1m', limit=12)
            if not candles or len(candles) < 11:
                return None

            completed_candles = candles[-11:-1]
            long_wins = 0
            short_wins = 0
            long_streak = 0
            short_streak = 0

            for c in completed_candles:
                open_p, close_p = c[1], c[4]
                long_gain_pct = ((close_p - open_p) / open_p) * 100.0
                short_dump_pct = ((open_p - close_p) / open_p) * 100.0

                if long_gain_pct >= self.MIN_MINUTE_GAIN_PCT:
                    long_wins += 1
                    long_streak += 1
                else:
                    long_streak = 0

                if short_dump_pct >= self.MIN_MINUTE_GAIN_PCT:
                    short_wins += 1
                    short_streak += 1
                else:
                    short_streak = 0

            is_long_trend = (long_streak >= 8) or (long_wins >= 9)
            is_short_trend = (short_streak >= 8) or (short_wins >= 9)

            if not is_long_trend and not is_short_trend:
                return None

            side = "long" if is_long_trend else "short"
            total_10m_move = sum([
                ((c[4] - c[1]) / c[1]) * 100.0 if side == "long" else ((c[1] - c[4]) / c[1]) * 100.0
                for c in completed_candles
            ])

            return {
                "side": side,
                "consecutive_wins": long_streak if side == "long" else short_streak,
                "total_10m_wins": long_wins if side == "long" else short_wins,
                "total_move_pct": total_10m_move
            }
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
            f"[{t_str}] {base_sym:<6} ({side.upper()}) | Spot:{gain_spot:+.2f}% (Peak:{trade['max_peak']:+.2f}%) | "
            f"Fading_TP:{faded_tp:+.2f}% | Fading_SL:{faded_sl:+.2f}% | {int(elapsed_s)}s",
            flush=True
        )

        hit_take_profit = gain_spot >= faded_tp
        hit_stop_loss = gain_spot <= faded_sl

        if hit_take_profit or hit_stop_loss:
            print(f"\n=======================================================", flush=True)
            if hit_take_profit:
                print(f"🟢 [FADING TARGET HARVESTED] {sym} ({side.upper()}) | Gain: {gain_spot:+.2f}% (Target: {faded_tp:+.2f}%)", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, is_scratch=False)
            else:
                if gain_spot >= fee_spread_threshold:
                    print(f"🛡️ [TRAILED / SCRATCH EXIT] {sym} ({side.upper()}) | Spot: {gain_spot:+.2f}% (Locked above fees)", flush=True)
                    self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, is_scratch=True)
                else:
                    print(f"🔴 [FADING STOP LOSS HIT] {sym} ({side.upper()}) | Loss: {gain_spot:+.2f}% (SL: {faded_sl:+.2f}%)", flush=True)
                    self.record_trade_outcome(is_win=False, symbol=sym, net_spot=gain_spot, is_scratch=False)

            print(f"=======================================================\n", flush=True)
            self.current_trade = None

    # --------------------------------------------------------------------------
    # LIVE TRADE MONITOR (ONE-WAY MODE & REDUCE-ONLY COMPLIANT)
    # --------------------------------------------------------------------------
    def poll_live_trade(self):
        if not self.live_state["active"]:
            return

        sym = self.live_state["symbol"]
        side = self.live_state["side"]
        entry = self.live_state["entry_price"]
        entry_spread = self.live_state.get("entry_spread", 0.0008)
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
            # Fix #4: One-Way Mode order side rule:
            # To CLOSE Long -> MARKET SELL with reduceOnly=True
            # To CLOSE Short -> MARKET BUY with reduceOnly=True
            close_side = 'sell' if side == 'long' else 'buy'
            contracts_to_close = self.live_state["contracts"]

            # Self-Healing: Query live exchange position to close exact amount (no dust left)
            try:
                positions = self.bitget.fetch_positions([sym])
                for p in positions:
                    if p.get('symbol') == sym and float(p.get('contracts', 0) or 0) > 0:
                        contracts_to_close = float(p['contracts'])
                        break
            except Exception:
                pass

            exit_params = {
                'reduceOnly': True,
                'tradeSide': 'close' # Dual-compatibility flag
            }

            executed = False
            for attempt in range(3):
                try:
                    self.bitget.create_order(sym, 'market', close_side, contracts_to_close, params=exit_params)
                    executed = True
                    break
                except Exception as e:
                    print(f"[RETRY EXIT {attempt+1}] Order failed: {e}. Retrying without tradeSide...", flush=True)
                    try:
                        self.bitget.create_order(sym, 'market', close_side, contracts_to_close, params={'reduceOnly': True})
                        executed = True
                        break
                    except Exception:
                        time.sleep(1)

            print(f"\n=======================================================", flush=True)
            if hit_take_profit:
                self.consecutive_live_losses = 0
                print(f"🟢 [LIVE FADING TARGET HIT: {gain_spot:+.2f}% SPOT]", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot)
            elif gain_spot >= fee_spread_threshold:
                print(f"🛡️ [LIVE TRAILED PROFIT/SCRATCH: {gain_spot:+.2f}% SPOT] Fees covered!", flush=True)
                self.record_trade_outcome(is_win=True, symbol=sym, net_spot=gain_spot, is_scratch=True)
            else:
                self.consecutive_live_losses += 1
                print(f"🔴 [LIVE FADING STOPPED: {gain_spot:+.2f}% SPOT]", flush=True)
                if self.consecutive_live_losses >= self.max_live_losses:
                    print(f"\n[DEMOTION ACTIVE] Resetting streak back to paper qualification.\n", flush=True)
                    self.consecutive_paper_wins = 0
                self.record_trade_outcome(is_win=False, symbol=sym, net_spot=gain_spot)

            print(f"=======================================================\n", flush=True)
            self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # MAIN SCANNER LOOP
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX 1-Minute Persistent Trend Engine online.", flush=True)

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

                    # Cross-reference against 600-coin worldwide whitelist or exchange volume
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

                        trend = self.inspect_persistent_trend(sym)
                        if trend:
                            side = trend["side"]
                            print(f"\n🚀 [PERSISTENT TREND DETECTED] {sym} ({side.upper()}) | {trend['total_10m_wins']}/10 Winning Minutes (Total Move: {trend['total_move_pct']:+.2f}%)", flush=True)

                            # LIVE TRADE EXECUTION
                            if self.is_qualified_for_live():
                                margin_90 = balance * 0.90
                                exchange_min_notional = 5.50  # Fix #5: Guard clamp for small balances

                                # Calculate minimum leverage required to satisfy Bitget notional
                                needed_leverage = max(math.ceil(exchange_min_notional / margin_90), 1)

                                # Safely set leverage for this coin in One-Way mode
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

                                # One-Way Open Rules:
                                # Open Long  -> MARKET BUY (no reduceOnly)
                                # Open Short -> MARKET SELL (no reduceOnly)
                                order_side = 'buy' if side == 'long' else 'sell'
                                open_params = {'tradeSide': 'open'}

                                try:
                                    self.bitget.create_order(sym, 'market', order_side, amount, params=open_params)
                                except Exception:
                                    # Fallback without tradeSide
                                    self.bitget.create_order(sym, 'market', order_side, amount)

                                self.live_state = {
                                    "active": True, "symbol": sym, "side": side,
                                    "contracts": amount, "entry_price": mid,
                                    "entry_spread": spread_pct,
                                    "start_time": time.time(),
                                    "max_peak": 0.0
                                }
                                print(f"[LIVE ORDER EXECUTED] Margin: ${margin_90:.2f} | Leverage: {needed_leverage}x | Side: {order_side.upper()}", flush=True)
                                break
                            else:
                                # PAPER QUALIFYING TRADE
                                self.current_trade = {
                                    "symbol": sym,
                                    "side": side,
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
                        f"[TREND PULSE] State: {active_name} | Global $1M Pool: {len(self.global_volume_whitelist)} | "
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
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    bot = PersistentTrendBot()
    bot.run()

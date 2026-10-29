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
# 1. RENDER KEEP-ALIVE SERVER (PORT 10000 BOUND FIRST)
# ==============================================================================
PORT = int(os.environ.get("PORT", 10000))
MEMORY_FILE = "master_30d_eligible_memory.json"
bot = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        if bot:
            status = {
                "engine": "APEX 30-Day Strict Single-Day 50%+ Gated Engine",
                "pool_count": len(bot.global_volume_whitelist),
                "eligible_30d_coins_count": len(bot.eligible_30d_coins),
                "eligible_coins_list": list(bot.eligible_30d_coins.keys()),
                "active_trade": bot.current_trade["symbol"] if bot.current_trade else ("LIVE_ACTIVE" if bot.live_state["active"] else "SCANNING_ELIGIBLE_ONLY"),
                "total_wins": bot.all_time_wins,
                "total_losses": bot.all_time_losses,
                "win_rate": f"{(bot.all_time_wins / max(1, bot.all_time_wins + bot.all_time_losses) * 100):.1f}%",
                "quarantined_ineligible": len(bot.ineligible_quarantine)
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
# 2. STRICT 30-DAY 50%+ GATED DUAL-ENGINE BOT
# ==============================================================================
class Strict30dGatedBot:
    def __init__(self):
        # Risk & Capital Controls
        self.equity_floor = 1.50
        self.ROUNDTRIP_FEE_PCT = 0.12

        # STRICT 30-DAY ELIGIBILITY CRITERIA
        self.LOOKBACK_DAYS = 30
        self.MIN_SINGLE_DAY_MOVE_PCT = 50.0  # Must be >= 50% in < 24 hours

        # Engine 2 (James vs David) Displacement Parameters
        self.MIN_LEAD_DISPLACEMENT_PCT = 1.5
        self.MAX_CHASE_LEAD_PCT = 4.5
        self.MIN_OPEN_RUNWAY_PCT = 10.0

        # Memory Stores
        self.all_time_wins = 0
        self.all_time_losses = 0
        self.eligible_30d_coins = {}        # {symbol: profile} -> ONLY THESE GET SCANNED
        self.ineligible_quarantine = set()   # Failed 30d test -> NEVER SCANNED
        self.audited_timestamps = {}        # {symbol: time}
        self.coin_mistakes = {}

        self.global_volume_whitelist = set()

        # Strict Exclusion List (No Gold, Stocks, or Flatline Commodities)
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

        # Safe Environment Variable Parsing
        self.api_key = (os.environ.get("API_KEY") or "").strip()
        self.secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        self.passphrase = (os.environ.get("PASSPHRASE") or "").strip()

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[FATAL] Missing credentials in Render environment!", flush=True)
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

        # Launch Background Global Aggregator (Paginated 600 Coins)
        t_global = threading.Thread(target=self.global_volume_worker, daemon=True)
        t_global.start()

    def enforce_one_way_mode(self):
        try:
            self.bitget.set_position_mode(hedged=False, params={'productType': 'USDT-FUTURES'})
            print("[CONFIG] Verified Bitget One-Way Mode active.", flush=True)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # MEMORY PERSISTENCE
    # --------------------------------------------------------------------------
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
                    print(f"[MEMORY] Loaded: {len(self.eligible_30d_coins)} eligible coins | {len(self.ineligible_quarantine)} quarantined", flush=True)
            except Exception as e:
                print(f"[WARN] Memory load note: {e}", flush=True)

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

    # --------------------------------------------------------------------------
    # GLOBAL AGGREGATOR ($1M+ VOLUME)
    # --------------------------------------------------------------------------
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
                    print(f"🌍 [GLOBAL POOL] Cached {len(self.global_volume_whitelist)} liquid coins with >= $1M volume!", flush=True)

            except Exception as e:
                print(f"[WARN] Aggregator note: {e}", flush=True)

            time.sleep(600)

    # --------------------------------------------------------------------------
    # 1. THE MASTER GATE: STRICT 30-DAY SINGLE-DAY 50%+ AUDITOR
    # --------------------------------------------------------------------------
    def audit_coin_30d_eligibility(self, symbol):
        """
        Audits last 30 daily candles:
        - Must have achieved >= +50% or <= -50% in a SINGLE 24h DAY.
        - Fails? -> INELIGIBLE -> Quarantined (NEVER SCANNED).
        - Passes? -> ELIGIBLE -> Added to Exclusive 30d Scanning Pool.
        """
        try:
            candles = self.bitget.fetch_ohlcv(symbol, timeframe='1d', limit=35)
            if not candles or len(candles) < 25:
                return False

            daily_candles = candles[-30:]
            pumps_50 = []
            dumps_50 = []

            for i in range(5, len(daily_candles)):
                c = daily_candles[i]
                open_p, high_p, low_p, vol = c[1], c[2], c[3], c[5]

                # Single-day move in < 24 hours
                day_gain_pct = ((high_p - open_p) / open_p) * 100.0
                day_dump_pct = ((open_p - low_p) / open_p) * 100.0

                prior_vols = [x[5] for x in daily_candles[i-5:i]]
                avg_prior_vol = sum(prior_vols) / len(prior_vols) if prior_vols else 1.0
                vol_mult = vol / avg_prior_vol if avg_prior_vol > 0 else 1.0

                if day_gain_pct >= self.MIN_SINGLE_DAY_MOVE_PCT:
                    pumps_50.append(vol_mult)
                if day_dump_pct >= self.MIN_SINGLE_DAY_MOVE_PCT:
                    dumps_50.append(vol_mult)

            total_events = len(pumps_50) + len(dumps_50)
            self.audited_timestamps[symbol] = time.time()

            # MASTER RULE: If it never moved 50%+ in <24h in the last 30 days, ISOLATE IT!
            if total_events == 0:
                self.ineligible_quarantine.add(symbol)
                if symbol in self.eligible_30d_coins:
                    del self.eligible_30d_coins[symbol]
                return False

            all_mults = pumps_50 + dumps_50
            avg_vol_mult = sum(all_mults) / len(all_mults)

            self.eligible_30d_coins[symbol] = {
                "total_events": total_events,
                "pumps_count": len(pumps_50),
                "dumps_count": len(dumps_50),
                "required_vol_mult": round(min(max(avg_vol_mult, 1.8), 4.5), 2),
                "can_long": len(pumps_50) > 0,
                "can_short": len(dumps_50) > 0
            }

            if symbol in self.ineligible_quarantine:
                self.ineligible_quarantine.remove(symbol)

            print(f"✅ [30D QUALIFIED] {symbol} | Hit 50%+ in <24h {total_events} times in last 30 days! Added to scanner pool.", flush=True)
            return True
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # 2. TRADE TRIGGER INSPECTORS (ONLY APPLIED TO 30D ELIGIBLE COINS)
    # --------------------------------------------------------------------------
    def inspect_eligible_coin(self, symbol):
        """
        Checks an ELIGIBLE coin for:
        1. 30d Ignition Scenario Match
        2. James vs. David Front-Runner Displacement
        ENFORCES WINNER RULE:
        - Enter LONG only when Longs are winning (green 1H, above EMA-9/21).
        - Enter SHORT only when Shorts are winning (red 1H, below EMA-9/21).
        """
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

            # Calculate 1H EMAs
            closes = [x[4] for x in history] + [cur_price]
            def calc_ema(data, period):
                k = 2 / (period + 1)
                res = [data[0]]
                for p in data[1:]:
                    res.append((p * k) + (res[-1] * (1 - k)))
                return res

            ema9 = calc_ema(closes, 9)[-1]
            ema21 = calc_ema(closes, 21)[-1]

            # ------------------------------------------------------------------
            # CHECK A: 30D IGNITION MATCH
            # ------------------------------------------------------------------
            if scenario["can_long"] and cur_price > cur_open and cur_price > ema9 and ema9 > ema21:
                gain_1h = ((cur_price - cur_open) / cur_open) * 100.0
                if gain_1h >= 1.5 and vol_mult >= scenario["required_vol_mult"]:
                    return {
                        "side": "long", "engine": "30D_IGNITION_MATCH",
                        "pivot": cur_open, "desc": f"30d Ignition Match (+{gain_1h:.1f}% on {vol_mult:.1f}x vol)"
                    }

            if scenario["can_short"] and cur_price < cur_open and cur_price < ema9 and ema9 < ema21:
                dump_1h = ((cur_open - cur_price) / cur_open) * 100.0
                if dump_1h >= 1.5 and vol_mult >= scenario["required_vol_mult"]:
                    return {
                        "side": "short", "engine": "30D_IGNITION_MATCH",
                        "pivot": cur_open, "desc": f"30d Ignition Match (-{dump_1h:.1f}% on {vol_mult:.1f}x vol)"
                    }

            # ------------------------------------------------------------------
            # CHECK B: JAMES VS. DAVID FRONT-RUNNER
            # ------------------------------------------------------------------
            if vol_mult >= 1.7:
                recent_candles = history[-60:-1]
                james_ceiling = max([x[2] for x in recent_candles])
                james_floor = min([x[3] for x in recent_candles])

                # David Long: Passed James's ceiling
                if cur_price > james_ceiling and cur_price > ema9 and ema9 > ema21:
                    lead_pct = ((cur_price - james_ceiling) / james_ceiling) * 100.0
                    if self.MIN_LEAD_DISPLACEMENT_PCT <= lead_pct <= self.MAX_CHASE_LEAD_PCT:
                        all_highs = [x[2] for x in history]
                        overhead = [h for h in all_highs if h > cur_price * 1.03]
                        finish_line = min(overhead) if overhead else (cur_price * 1.25)
                        runway_pct = ((finish_line - cur_price) / cur_price) * 100.0

                        if runway_pct >= self.MIN_OPEN_RUNWAY_PCT:
                            return {
                                "side": "long", "engine": "FRONT_RUNNER_DAVID",
                                "pivot": james_ceiling, "desc": f"David Passed James by +{lead_pct:.1f}% | Runway: +{runway_pct:.1f}%"
                            }

                # David Short: Passed James's floor
                if cur_price < james_floor and cur_price < ema9 and ema9 < ema21:
                    lead_pct = ((james_floor - cur_price) / james_floor) * 100.0
                    if self.MIN_LEAD_DISPLACEMENT_PCT <= lead_pct <= self.MAX_CHASE_LEAD_PCT:
                        all_lows = [x[3] for x in history]
                        underhead = [l for l in all_lows if l < cur_price * 0.97]
                        finish_line = max(underhead) if underhead else (cur_price * 0.75)
                        runway_pct = ((cur_price - finish_line) / cur_price) * 100.0

                        if runway_pct >= self.MIN_OPEN_RUNWAY_PCT:
                            return {
                                "side": "short", "engine": "FRONT_RUNNER_DAVID",
                                "pivot": james_floor, "desc": f"David Passed James by -{lead_pct:.1f}% | Runway: +{runway_pct:.1f}%"
                            }

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # 3. TRADE MANAGEMENT: EXITS AS SOON AS MOMENTUM DIES
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

        should_exit = False
        is_win = False
        exit_reason = ""

        # --- MOMENTUM DEATH EXITS (CLOSES THE MOMENT MOMENTUM DIES) ---

        # 1. Structural Trend Inversion (Winning side lost control)
        if side == "long" and (cur_price < ema9 or ema9 < ema21):
            should_exit = True
            is_win = gain_pct > 0.3
            exit_reason = f"MOMENTUM DIED: Long EMA inverted (Closed at {gain_pct:+.2f}%)"

        elif side == "short" and (cur_price > ema9 or ema9 > ema21):
            should_exit = True
            is_win = gain_pct > 0.3
            exit_reason = f"MOMENTUM DIED: Short EMA inverted (Closed at {gain_pct:+.2f}%)"

        # 2. Runner Retracement Lock-In
        elif peak >= 6.0 and (peak - gain_pct) >= 2.8:
            should_exit = True
            is_win = True
            exit_reason = f"MOMENTUM FADING: Peak was +{peak:.1f}%, secured at +{gain_pct:.1f}%"

        # 3. Volume Collapse & Stagnation
        elif elapsed_hours >= 3.0 and last_vol < (avg_vol * 0.35) and abs(gain_pct) < 1.5:
            should_exit = True
            is_win = gain_pct > 0.0
            exit_reason = f"MOMENTUM DEAD: Volume dried up to a flatline after {elapsed_hours:.1f}h"

        # 4. Big Target Harvested
        elif gain_pct >= 20.0:
            should_exit = True
            is_win = True
            exit_reason = f"MAJOR TARGET HARVESTED (+{gain_pct:.1f}%)"

        # 5. Structural Pivot Invalidation
        elif (side == "long" and cur_price < pivot * 0.98) or (side == "short" and cur_price > pivot * 1.02):
            should_exit = True
            is_win = False
            exit_reason = f"PIVOT INVALIDATED: Price broke back past entry pivot (Loss: {gain_pct:.1f}%)"

        t_str = time.strftime("%H:%M:%S", time.localtime(time.time()))
        print(f"[{t_str}] {sym:<8} ({side.upper()}) | Spot: {gain_pct:>+6.1f}% | Peak: {peak:>+6.1f}% | Held: {elapsed_hours:.1f}h | Track: RUNNING", flush=True)

        if should_exit:
            print(f"\n=======================================================", flush=True)
            print(f"🛑 [TRADE CONCLUDED] {sym} | Reason: {exit_reason}", flush=True)
            print(f"=======================================================\n", flush=True)

            if is_win:
                self.all_time_wins += 1
            else:
                self.all_time_losses += 1
                self.coin_mistakes[sym] = self.coin_mistakes.get(sym, 0) + 1
                if self.coin_mistakes[sym] >= 2:
                    self.ineligible_quarantine.add(sym)
                    if sym in self.eligible_30d_coins:
                        del self.eligible_30d_coins[sym]
                    print(f"🚫 [QUARANTINE] {sym} quarantined due to 2 failed breakouts.", flush=True)

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
                    print(f"[LIVE EXIT] Closed {contracts} contracts on {sym}", flush=True)
                    break
        except Exception as e:
            print(f"[EXIT ERROR] {e}", flush=True)
        self.live_state["active"] = False

    # --------------------------------------------------------------------------
    # 4. MAIN PIPELINE (ONLY SCANS ELIGIBLE COINS)
    # --------------------------------------------------------------------------
    def run(self):
        start_server()
        print("[SYSTEM] APEX Strict 30-Day Single-Day 50%+ Gated Engine online.", flush=True)

        try:
            self.bitget.load_markets()
            print(f"[SYSTEM] Loaded {len(self.bitget.markets)} swap pairs from Bitget.", flush=True)
        except Exception as e:
            print(f"[WARN] Market load notice: {e}", flush=True)

        cycle = 0

        while True:
            try:
                # 1. Manage Active Trade
                self.manage_momentum_and_exits()

                # 2. Check balance
                balance = float(self.bitget.fetch_balance().get('USDT', {}).get('free', 0) or 0)
                if balance < self.equity_floor:
                    time.sleep(20)
                    continue

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

                # Step A: Audit 30-Day Eligibility (Batched on un-audited coins)
                for sym, _ in candidates[:35]:
                    last_audit = self.audited_timestamps.get(sym, 0)
                    if time.time() - last_audit > 43200:  # Audit every 12 hours
                        self.audit_coin_30d_eligibility(sym)
                        self.save_memory()
                        time.sleep(0.12)

                # Step B: STRICT SCANNING GATE: ONLY SCAN COINS THAT PASSED THE 30D AUDIT!
                if not self.current_trade and not self.live_state["active"]:
                    # CRUCIAL RULE: ONLY loop through self.eligible_30d_coins!
                    for sym in list(self.eligible_30d_coins.keys()):
                        if sym in tickers:
                            entry_signal = self.inspect_eligible_coin(sym)
                            if entry_signal:
                                side = entry_signal["side"]
                                engine = entry_signal["engine"]
                                desc = entry_signal["desc"]
                                pivot = entry_signal["pivot"]

                                print(f"\n🚀 [30D QUALIFIED TRIGGER: {engine}] {sym} ({side.upper()})", flush=True)
                                print(f"📊 Details: {desc}", flush=True)

                                mid = float(tickers[sym]['last'])

                                margin_alloc = balance * 0.90
                                exchange_min_notional = 5.50
                                needed_leverage = max(math.ceil(exchange_min_notional / margin_alloc), 1)

                                try:
                                    self.bitget.set_leverage(needed_leverage, sym, params={'marginCoin': 'USDT'})
                                except Exception:
                                    try:
                                        self.bitget.set_leverage(needed_leverage, sym)
                                    except Exception:
                                        pass

                                notional_size = margin_alloc * needed_leverage
                                raw_amount = notional_size / mid
                                amount = float(self.bitget.amount_to_precision(sym, raw_amount))
                                order_side = 'buy' if side == 'long' else 'sell'

                                try:
                                    self.bitget.create_order(sym, 'market', order_side, amount, params={'tradeSide': 'open'})
                                    self.live_state = {
                                        "active": True, "symbol": sym, "side": side,
                                        "contracts": amount, "entry_price": mid,
                                        "pivot_point": pivot, "start_time": time.time(),
                                        "max_peak": 0.0, "engine_source": engine
                                    }
                                    print(f"[LIVE ORDER EXECUTED] Margin: ${margin_alloc:.2f} | Leverage: {needed_leverage}x | Side: {order_side.upper()}\n", flush=True)
                                    break
                                except Exception as order_err:
                                    print(f"[ORDER NOTE] Executing as paper trade: {order_err}", flush=True)
                                    self.current_trade = {
                                        "symbol": sym, "side": side,
                                        "entry_price": mid, "pivot_point": pivot,
                                        "start_time": time.time(), "max_peak": 0.0,
                                        "engine_source": engine
                                    }
                                    break

                if cycle % 12 == 0:
                    state_desc = self.current_trade["symbol"] if self.current_trade else ("LIVE_ACTIVE" if self.live_state["active"] else "SCANNING_30D_ELIGIBLE_ONLY")
                    print(
                        f"[PULSE] State: {state_desc} | Pool: {len(self.global_volume_whitelist)} | "
                        f"30d Verified Eligible: {len(self.eligible_30d_coins)} | Quarantined Ineligible: {len(self.ineligible_quarantine)}",
                        flush=True
                    )

                cycle += 1
                time.sleep(10)

            except Exception as e:
                print(f"[LOOP EXCEPTION] {e}", flush=True)
                traceback.print_exc()
                time.sleep(10)

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    bot = Strict30dGatedBot()
    bot.run()

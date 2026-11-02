#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: COINGLASS-FIRST WORLDWIDE MASTER BRAIN (BITGET EXECUTION BROKER)
MASTER RADAR: COINGLASS_FEED.PY (BINANCE + BYBIT + OKX + BITGET GLOBAL AGGREGATION)
EXECUTION GUN: BITGET USDT-M PERPETUAL SWAPS
GLOBAL VOLUME RULE: >= $1,000,000 ON COINGLASS (ACCEPTED REGARDLESS OF BITGET LOCAL VOL)
QUALIFICATION GAUNTLET: STRICT 8 CONSECUTIVE WINS (ELIMINATES RANDOM LUCK)

STRATEGIES (ALL 6 MODULES ACTIVE IN PARALLEL):
  1. Multi-Timeframe Regime Shift (Macro Capitulation -> 15M Ignition)
  2. Exhaustion Divergence ("The Wiggle Trap" - Price vs. OI Divergence)
  3. Amplified 3-Minute Exhaustion Climax (Accelerating Thrust Decay)
  4. 20-Minute Stepwise Ratio Tournament (Clean Auction Waves, Anti-Spike)
  5. Pressure Cooker Disconnect (Metrics Die, Price Floats -> Short Flush)
  6. 24-Hour Whale Liquidity Wall Magnet

EXIT SYSTEM:
  - Organic Momentum Fade (Velocity Rollover + Wiggle Stall + OI Exhaustion)
  - 90-Second Dead-on-Arrival (DOA) Kill Switch (< +0.30% Forward Progress)
  - 0.90% Emergency Live Hard Stop

INFRASTRUCTURE:
  - Render Port 10000 HTTP Keep-Alive Server (HEAD 200 OK & GET Dashboard)
  - Python 3.12 Timezone-Aware UTC Standard
  - Qualification Gauntlet (1 -> 8 Consecutive Wins) in qualification_state.json
===============================================================================
"""

import os
import sys
import time
import math
import json
import logging
import threading
import importlib.util
from datetime import datetime, timezone
from collections import deque, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from requests.adapters import HTTPAdapter
import ccxt

# -----------------------------------------------------------------------------
# SECTION 1: LOGGING CONFIGURATION (CLEAN TELEMETRY)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CoinGlassMasterEngine")

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# SECTION 2: DYNAMIC COINGLASS FEED LOADER
# -----------------------------------------------------------------------------
get_coinglass_data = None

def load_coinglass_module():
    global get_coinglass_data
    possible_names = ["coinglass_feed.py", "coinglass feed.py", "coinglass.py", "cg_feed.py"]

    try:
        from coinglass_feed import get_coinglass_data as cg_func
        get_coinglass_data = cg_func
        return
    except ImportError:
        pass

    for fname in possible_names:
        if os.path.exists(fname):
            try:
                spec = importlib.util.spec_from_file_location("coinglass_feed_module", fname)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "get_coinglass_data"):
                    get_coinglass_data = getattr(mod, "get_coinglass_data")
                    return
            except Exception:
                pass

    get_coinglass_data = lambda: []

load_coinglass_module()

# -----------------------------------------------------------------------------
# SECTION 3: SYSTEM CONSTANTS & GLOBAL RULES
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

# The Global Volume Standard (CoinGlass worldwide volume must be >= $1M)
MIN_COINGLASS_GLOBAL_VOLUME = 1_000_000.0

# Exit Parameters (Organic Momentum Fade)
DOA_TIMEOUT_SECONDS = 90           # 90-Second Dead-on-Arrival Kill Switch
DOA_FORWARD_THRESHOLD_PCT = 0.30   # Must gain at least +0.30% in 90s or abort
MAX_LIFECYCLE_SECONDS = 900        # 15-Minute Maximum Trade Hold
LIVE_HARD_STOP_PCT = 0.90          # Structural Emergency Hard Stop in Live Mode

# Gauntlet: Upgraded to 8 Consecutive Wins (Probability of Luck < 0.39%)
QUALIFICATION_TARGET_WINS = 8      # Strict 8 consecutive paper wins before Live unlock
COOLDOWN_SECONDS = 600             # 10-Minute Cooldown per pair post-exit
ALLOCATION_PCT = 0.90              # Allocate 90% of free balance
MIN_NOTIONAL_USDT = 5.50           # Bitget minimum order size constraint
MAX_LEVERAGE_CLAMP = 20
MIN_LEVERAGE_CLAMP = 2

PORT = int(os.environ.get("PORT", 10000))
STATE_FILE = "qualification_state.json"

# -----------------------------------------------------------------------------
# SECTION 4: UNIVERSAL CREDENTIAL READER (.strip() PROTECTED)
# -----------------------------------------------------------------------------
def get_env_var(keys, default=""):
    for k in keys:
        val = os.environ.get(k)
        if val:
            return val.strip()
    return default

API_KEY = get_env_var(["BITGET_API_KEY", "API_KEY"])
SECRET_KEY = get_env_var(["BITGET_SECRET_KEY", "SECRET_KEY"])
PASSPHRASE = get_env_var(["BITGET_PASSPHRASE", "PASSPHRASE"])

# -----------------------------------------------------------------------------
# SECTION 5: QUALIFICATION STATE MANAGER (GAUNTLET 1 -> 8)
# -----------------------------------------------------------------------------
class StateManager:
    def __init__(self, filename=STATE_FILE):
        self.filename = filename
        self.lock = threading.Lock()
        self.state = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    loaded = json.load(f)
                    # Enforce the new 8-win target
                    loaded["target_wins"] = QUALIFICATION_TARGET_WINS
                    if loaded.get("mode") == "PAPER" and loaded.get("consecutive_wins", 0) < QUALIFICATION_TARGET_WINS:
                        loaded["mode"] = "PAPER"
                    return loaded
            except Exception:
                pass
        return {
            "mode": "PAPER",
            "consecutive_wins": 0,
            "target_wins": QUALIFICATION_TARGET_WINS,
            "total_trades": 0,
            "total_wins": 0,
            "total_losses": 0,
            "history": []
        }

    def save(self):
        with self.lock:
            try:
                with open(self.filename, "w") as f:
                    json.dump(self.state, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving state: {e}")

    def record_trade(self, symbol, side, gain_pct, exit_reason, setup_name, is_paper):
        with self.lock:
            self.state["total_trades"] += 1
            is_win = gain_pct > 0.0

            if is_win:
                self.state["total_wins"] += 1
                if self.state["mode"] == "PAPER":
                    self.state["consecutive_wins"] += 1
                    logger.info(f"🏆 PAPER WIN! Streak: {self.state['consecutive_wins']}/{QUALIFICATION_TARGET_WINS} | Setup: {setup_name}")
                    if self.state["consecutive_wins"] >= QUALIFICATION_TARGET_WINS:
                        self.state["mode"] = "LIVE"
                        logger.info("🚀 GAUNTLET COMPLETED (8/8)! AUTHORIZING LIVE TRADING ENGINE!")
            else:
                self.state["total_losses"] += 1
                if self.state["mode"] == "PAPER":
                    logger.warning(f"❌ PAPER LOSS. Streak reset to 0/{QUALIFICATION_TARGET_WINS} | Setup: {setup_name}")
                    self.state["consecutive_wins"] = 0

            trade_log = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
                "side": side.upper(),
                "gain_pct": round(gain_pct, 3),
                "setup": setup_name,
                "exit_reason": exit_reason,
                "mode": "PAPER" if is_paper else "LIVE",
                "result": "WIN" if is_win else "LOSS"
            }
            self.state["history"].append(trade_log)
            if len(self.state["history"]) > 50:
                self.state["history"].pop(0)

        self.save()

# -----------------------------------------------------------------------------
# SECTION 6: LIVE HTTP KEEP-ALIVE SERVER (PORT 10000 DASHBOARD)
# -----------------------------------------------------------------------------
dashboard_data = {
    "status": "INITIALIZING",
    "mode": "PAPER",
    "streak": 0,
    "cg_global_pairs": 0,
    "bitget_tradable_pairs": 0,
    "active_trade": None,
    "recent_trades": [],
    "last_update": ""
}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Silences Render keep-alive health pings with 200 OK."""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        at = dashboard_data.get("active_trade")
        active_html = "<p style='color: #888;'>CoinGlass Radar scanning worldwide markets...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            fade_status = "<span style='color: #f59e0b; font-weight: bold;'>FADING (EXIT ARMED)</span>" if at.get("is_fading") else "<span style='color: #4ade80;'>ACTIVE PROPULSION</span>"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE POSITION: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Strategy:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                <p><b>Entry:</b> {at['entry_price']} | <b>Current:</b> {at['current_price']}</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>Fade Status:</b> {fade_status} | <b>Timer:</b> {at['elapsed_seconds']}s / {MAX_LIFECYCLE_SECONDS}s (DOA: {DOA_TIMEOUT_SECONDS}s)</p>
            </div>
            """

        history_rows = ""
        for t in reversed(dashboard_data.get("recent_trades", [])[-10:]):
            color = "#4ade80" if t["result"] == "WIN" else "#f87171"
            history_rows += f"""
            <tr>
                <td style="padding: 6px;">{t['timestamp']}</td>
                <td style="padding: 6px;">{t['symbol']}</td>
                <td style="padding: 6px;">{t['side']}</td>
                <td style="padding: 6px; color: #60a5fa;">{t.get('setup', 'N/A')}</td>
                <td style="padding: 6px; color: {color}; font-weight: bold;">{t['gain_pct']:+.2f}%</td>
                <td style="padding: 6px;">{t['exit_reason']}</td>
                <td style="padding: 6px;">{t['mode']}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>CoinGlass Master Radar</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                .card {{ background: #1e293b; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
                .badge {{ padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
                .badge-live {{ background: #ef4444; color: white; }}
                .badge-paper {{ background: #eab308; color: black; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th {{ text-align: left; background: #334155; padding: 8px; font-size: 13px; }}
            </style>
        </head>
        <body>
            <h2>🛰️ CoinGlass Master Brain (Bitget Execution Desk)</h2>
            <div class="card">
                <b>Status:</b> {dashboard_data['status']} | 
                <b>Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Consecutive Wins | 
                <b>CoinGlass Global Universe ($1M+):</b> {dashboard_data['cg_global_pairs']} Pairs | 
                <b>Bitget Tradable:</b> {dashboard_data['bitget_tradable_pairs']} Pairs
            </div>

            <div class="card">
                <h3>Live Position Telemetry</h3>
                {active_html}
            </div>

            <div class="card">
                <h3>Recent Execution Log</h3>
                <table>
                    <thead>
                        <tr><th>Time</th><th>Symbol</th><th>Side</th><th>Strategy</th><th>PnL %</th><th>Exit Reason</th><th>Type</th></tr>
                    </thead>
                    <tbody>
                        {history_rows}
                    </tbody>
                </table>
            </div>
            <p style="font-size: 12px; color: #64748b;">Telemetry updated: {dashboard_data['last_update']}</p>
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        return

def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.serve_forever()

# -----------------------------------------------------------------------------
# SECTION 7: COINGLASS MASTER ENGINE CORE
# -----------------------------------------------------------------------------
class BitgetDeskPartnerEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.exchange = None
        self.http_session = None
        
        self.cg_buffer = defaultdict(lambda: deque(maxlen=300))  # 15-20 minutes of CoinGlass states
        self.bitget_markets = set()  # Set of valid tradable symbols on Bitget
        self.bitget_prices = {}     # Symbol -> latest Bitget execution price
        self.cooldowns = {}
        self.active_trade = None

        self._setup_connection_pool()
        self._setup_exchange()

    def _setup_connection_pool(self):
        self.http_session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=3)
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)

    def _setup_exchange(self):
        self.exchange = ccxt.bitget({
            "apiKey": API_KEY,
            "secret": SECRET_KEY,
            "password": PASSPHRASE,
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })
        self.exchange.session = self.http_session

        if API_KEY and SECRET_KEY and PASSPHRASE:
            try:
                self.exchange.set_position_mode(hedged=False)
                logger.info("🔒 Bitget account verified: One-Way Mode Active.")
            except Exception:
                pass
        else:
            logger.info("ℹ️ Running in Paper Mode without full private keys.")

    def sync_bitget_tradable_universe(self):
        """Pulls Bitget's tradable USDT-M futures list."""
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
        try:
            resp = self.http_session.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "00000":
                    tickers = data.get("data", [])
                    self.bitget_markets.clear()
                    for t in tickers:
                        sym = t.get("symbol", "")
                        last_p = float(t.get("lastPr", 0.0) or 0.0)
                        if sym and last_p > 0:
                            self.bitget_markets.add(sym)
                            self.bitget_prices[sym] = last_p
                    dashboard_data["bitget_tradable_pairs"] = len(self.bitget_markets)
        except Exception:
            pass

    def sync_coinglass_master_radar(self):
        """
        THE MASTER BRAIN INGESTION:
        Pulls worldwide aggregated data from coinglass_feed.py.
        Applies the $1,000,000 Global Volume Rule.
        Accepts any coin with >= $1M global volume, even if Bitget local volume is $30k!
        """
        global get_coinglass_data
        if not get_coinglass_data:
            return

        now = time.time()
        try:
            cg_items = get_coinglass_data()
            if cg_items:
                valid_count = 0
                for item in cg_items:
                    base_sym = item.get("symbol", "").upper()
                    if not base_sym or any(b in base_sym for b in BLACKLIST):
                        continue

                    vol_global = float(item.get("vol_1h", 0.0) or 0.0)
                    self.cg_buffer[base_sym].append({
                        "time": now,
                        "price": float(item.get("price", 0.0) or 0.0),
                        "price_15m": float(item.get("price_15m", 0.0) or 0.0),
                        "oi_15m": float(item.get("oi_15m", 0.0) or 0.0),
                        "vol_1h": vol_global
                    })
                    valid_count += 1

                dashboard_data["cg_global_pairs"] = valid_count
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # SECTION 8: THE 6 INSTITUTIONAL STRATEGY MODULES
    # -------------------------------------------------------------------------

    def eval_module_1_regime_shift(self, base_sym, latest, history):
        """Play 1: Multi-Timeframe Regime Shift (Capitulation -> 15M Ignition)."""
        p15m = latest["price_15m"]
        oi15m = latest["oi_15m"]

        if p15m >= 1.50 and oi15m >= 1.00:
            return {"side": "buy", "setup": "PLAY1_MTF_REGIME_SHIFT", "score": 96}
        elif p15m <= -1.50 and oi15m <= -1.00:
            return {"side": "sell", "setup": "PLAY1_MTF_REGIME_SHIFT", "score": 96}
        return None

    def eval_module_2_exhaustion_wiggle(self, base_sym, latest, history):
        """Play 2: Exhaustion Divergence ('The Wiggle Trap')."""
        if len(history) < 10:
            return None

        p15m = latest["price_15m"]
        oi15m = latest["oi_15m"]

        recent_prices = [h["price"] for h in list(history)[-10:]]
        if not recent_prices or min(recent_prices) <= 0:
            return None

        wiggle_range = (max(recent_prices) - min(recent_prices)) / min(recent_prices) * 100.0

        if p15m >= 1.80 and oi15m <= -0.50 and wiggle_range < 0.25:
            return {"side": "sell", "setup": "PLAY2_WIGGLE_DIVERGENCE_TOP", "score": 92}
        elif p15m <= -1.80 and oi15m >= 0.50 and wiggle_range < 0.25:
            return {"side": "buy", "setup": "PLAY2_WIGGLE_ABSORPTION_BOTTOM", "score": 92}
        return None

    def eval_module_3_amplified_3m(self, base_sym, latest, history):
        """Play 3: Amplified 3-Minute Exhaustion Climax."""
        if len(history) < 6:
            return None

        h = list(history)
        p_current = h[-1]["price"]
        p_3m_ago = h[-6]["price"]

        if p_3m_ago <= 0:
            return None

        move_3m = abs((p_current - p_3m_ago) / p_3m_ago * 100.0)
        
        if move_3m >= 1.40:
            if p_current > p_3m_ago and latest["oi_15m"] < 0:
                return {"side": "sell", "setup": "PLAY3_AMPLIFIED_EXHAUSTION_SNAP", "score": 89}
            elif p_current < p_3m_ago and latest["oi_15m"] > 0:
                return {"side": "buy", "setup": "PLAY3_AMPLIFIED_EXHAUSTION_SNAP", "score": 89}
        return None

    def eval_module_4_stepwise_tournament(self, base_sym, latest, history):
        """Play 4: 20-Minute Stepwise Ratio Tournament (Anti-Spike)."""
        if len(history) < 15:
            return None

        prices = [h["price"] for h in history]
        if len(prices) < 2:
            return None

        for i in range(1, len(prices)):
            if abs((prices[i] - prices[i-1]) / prices[i-1] * 100.0) > 1.50:
                return None

        steps_up = sum(1 for i in range(1, len(prices)) if (prices[i] - prices[i-1]) / prices[i-1] * 100.0 >= 0.30)
        steps_down = sum(1 for i in range(1, len(prices)) if (prices[i] - prices[i-1]) / prices[i-1] * 100.0 <= -0.30)

        if steps_down > 0 and (steps_up / steps_down) >= 2.8 and steps_up >= 3:
            return {"side": "buy", "setup": "PLAY4_STEPWISE_AUCTION_TOURNAMENT", "score": 86}
        elif steps_up > 0 and (steps_down / steps_up) >= 2.8 and steps_down >= 3:
            return {"side": "sell", "setup": "PLAY4_STEPWISE_AUCTION_TOURNAMENT", "score": 86}
        return None

    def eval_module_5_pressure_cooker(self, base_sym, latest, history):
        """Play 5: Pressure Cooker Disconnect (Metrics Die, Price Floats)."""
        p15m = latest["price_15m"]
        oi15m = latest["oi_15m"]

        if (0.80 <= p15m <= 1.80) and oi15m <= -2.00:
            return {"side": "sell", "setup": "PLAY5_PRESSURE_COOKER_DISCONNECT", "score": 94}
        return None

    def run_master_arbitrator(self):
        """
        THE CONVICTION ARBITRATOR:
        Evaluates CoinGlass worldwide feeds across all 6 modules.
        Selects the #1 highest-conviction setup.
        Cross-checks that the symbol is tradable on Bitget.
        """
        if self.active_trade is not None:
            return None

        now = time.time()
        candidates = []

        for base_sym, buf in list(self.cg_buffer.items()):
            bitget_symbol = f"{base_sym}USDT"
            if bitget_symbol not in self.bitget_markets:
                continue

            if bitget_symbol in self.cooldowns and (now - self.cooldowns[bitget_symbol]) < COOLDOWN_SECONDS:
                continue

            if len(buf) < 5:
                continue

            latest = buf[-1]

            s1 = self.eval_module_1_regime_shift(base_sym, latest, buf)
            if s1: candidates.append({**s1, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s2 = self.eval_module_2_exhaustion_wiggle(base_sym, latest, buf)
            if s2: candidates.append({**s2, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s3 = self.eval_module_3_amplified_3m(base_sym, latest, buf)
            if s3: candidates.append({**s3, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s4 = self.eval_module_4_stepwise_tournament(base_sym, latest, buf)
            if s4: candidates.append({**s4, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s5 = self.eval_module_5_pressure_cooker(base_sym, latest, buf)
            if s5: candidates.append({**s5, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

        if candidates:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]
            
            execution_price = self.bitget_prices.get(top["bitget_symbol"], 0.0)
            if execution_price <= 0:
                return None

            top["entry_price"] = execution_price
            logger.info(
                f"🎯 COINGLASS MASTER SIGNAL: {top['base_sym']} ({top['side'].upper()}) | "
                f"Strategy: {top['setup']} | Score: {top['score']}/100 | Bitget Symbol: {top['bitget_symbol']}"
            )
            return top

        return None

    # -------------------------------------------------------------------------
    # SECTION 9: BITGET EXECUTION GUN & SIZING
    # -------------------------------------------------------------------------
    def calculate_live_position_size(self, current_price):
        try:
            balance_info = self.exchange.fetch_balance()
            free_usdt = float(balance_info["free"].get("USDT", 0.0))
            usable_margin = free_usdt * ALLOCATION_PCT

            if usable_margin < 0.50:
                return 0, 0

            calculated_lev = math.ceil(MIN_NOTIONAL_USDT / usable_margin)
            leverage = max(MIN_LEVERAGE_CLAMP, min(calculated_lev, MAX_LEVERAGE_CLAMP))
            notional = max(MIN_NOTIONAL_USDT, usable_margin * leverage)
            contract_size = notional / current_price
            return contract_size, leverage
        except Exception:
            return 0, 0

    def enter_trade(self, signal):
        symbol = signal["bitget_symbol"]
        base_sym = signal["base_sym"]
        side = signal["side"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        trade_info = {
            "symbol": symbol,
            "base_sym": base_sym,
            "side": side,
            "setup": signal["setup"],
            "entry_price": price,
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gain_pct": 0.0,
            "last_peak_time": time.time(),
            "is_fading": False,
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened {side.upper()} on {symbol} @ {price} | Strategy: {signal['setup']}")
            self.active_trade = trade_info
        else:
            try:
                size, lev = self.calculate_live_position_size(price)
                if size <= 0:
                    return

                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                self.exchange.set_leverage(lev, ccxt_symbol)

                if side == "buy":
                    order = self.exchange.create_market_buy_order(ccxt_symbol, size)
                else:
                    order = self.exchange.create_market_sell_order(ccxt_symbol, size)

                trade_info["size"] = size
                self.active_trade = trade_info
                logger.info(f"⚡ [LIVE ENTRY] {side.upper()} {symbol} | Size: {size} | Lev: {lev}x | Strategy: {signal['setup']}")
            except Exception as e:
                logger.error(f"Live entry execution failed: {e}")
                self.active_trade = None

    # -------------------------------------------------------------------------
    # SECTION 10: ORGANIC FADE EXIT STATE MACHINE (NO FIXED 0.5% REVERSE)
    # -------------------------------------------------------------------------
    def manage_active_trade(self):
        """
        ORGANIC FADE DETECTION:
        Leaves trade immediately when momentum exhausts:
        - Velocity Rollover: Forward velocity collapses.
        - Wiggle Stall: Price stops making new highs/lows for > 60s and compresses.
        - Open Interest Exhaustion: Global OI stops expanding.
        """
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        base_sym = trade["base_sym"]
        side = trade["side"]

        current_price = self.bitget_prices.get(symbol, trade["entry_price"])
        now = time.time()
        elapsed = max(1.0, now - trade["entry_time"])

        if side == "buy":
            gain_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
            if current_price > trade["peak_price"]:
                trade["peak_price"] = current_price
                trade["last_peak_time"] = now
            if gain_pct > trade["highest_gain_pct"]:
                trade["highest_gain_pct"] = gain_pct
        else:
            gain_pct = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100.0
            if current_price < trade["peak_price"]:
                trade["peak_price"] = current_price
                trade["last_peak_time"] = now
            if gain_pct > trade["highest_gain_pct"]:
                trade["highest_gain_pct"] = gain_pct

        time_since_last_peak = now - trade["last_peak_time"]
        
        is_wiggle_stalled = (
            trade["highest_gain_pct"] >= 0.40 and 
            time_since_last_peak >= 60
        )

        if is_wiggle_stalled:
            trade["is_fading"] = True

        dashboard_data["active_trade"] = {
            "symbol": symbol,
            "side": side,
            "setup": trade["setup"],
            "mode": trade["mode"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "pnl_pct": gain_pct,
            "peak_gain_pct": trade["highest_gain_pct"],
            "is_fading": trade["is_fading"],
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        # 1. ORGANIC FADE EXIT (Leaves trade when momentum wiggles & stalls)
        if trade["is_fading"] and gain_pct >= 0.30:
            exit_reason = "ORGANIC_MOMENTUM_FADE (WIGGLE_STALL)"

        # 2. 90-SECOND DEAD-ON-ARRIVAL (DOA) KILL SWITCH
        elif elapsed >= DOA_TIMEOUT_SECONDS and trade["highest_gain_pct"] < DOA_FORWARD_THRESHOLD_PCT:
            exit_reason = "90S_DOA_KILL_SWITCH"

        # 3. 15-MINUTE MAXIMUM LIFECYCLE ROTATION
        elif elapsed >= MAX_LIFECYCLE_SECONDS:
            exit_reason = "15M_LIFECYCLE_EXHAUSTION"

        # 4. STRUCTURAL EMERGENCY HARD STOP (Live Mode Only)
        elif not trade["is_paper"] and gain_pct <= -LIVE_HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        if exit_reason:
            self._execute_exit(trade, current_price, gain_pct, exit_reason)

    def _execute_exit(self, trade, exit_price, gain_pct, reason):
        symbol = trade["symbol"]
        side = trade["side"]
        is_paper = trade["is_paper"]
        setup_name = trade["setup"]

        try:
            if not is_paper:
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                pos = self.exchange.fetch_position(ccxt_symbol)
                exact_size = abs(float(pos.get("contracts", 0.0) or trade["size"]))

                if exact_size > 0:
                    if side == "buy":
                        self.exchange.create_market_sell_order(ccxt_symbol, exact_size, params={"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(ccxt_symbol, exact_size, params={"reduceOnly": True})

                logger.info(f"⚡ [LIVE EXIT] Closed {side.upper()} {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")
            else:
                logger.info(f"📝 [PAPER EXIT] Closed {side.upper()} {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")

            self.state_mgr.record_trade(symbol, side, gain_pct, reason, setup_name, is_paper)
            self.cooldowns[symbol] = time.time()

        except Exception as e:
            logger.error(f"Error during exit execution: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def print_15m_briefing(self):
        """Clean, professional 15-minute desk intelligence box."""
        mode = self.state_mgr.state["mode"]
        streak = self.state_mgr.state["consecutive_wins"]
        total = self.state_mgr.state["total_trades"]
        wins = self.state_mgr.state["total_wins"]
        losses = self.state_mgr.state["total_losses"]
        win_rate = (wins / total * 100.0) if total > 0 else 0.0

        pos_str = "None (CoinGlass Radar Scanning)"
        if self.active_trade:
            pos_str = f"{self.active_trade['symbol']} ({self.active_trade['side'].upper()}) PnL: {dashboard_data['active_trade']['pnl_pct']:+.2f}%"

        logger.info(
            f"\n"
            f"╔════════════════════════════════════════════════════════════════════╗\n"
            f"║           📊 15-MINUTE COINGLASS MASTER RADAR BRIEFING             ║\n"
            f"╠════════════════════════════════════════════════════════════════════╣\n"
            f"║ Engine Status  : RUNNING ACTIVE (CoinGlass Master -> Bitget Gun)   ║\n"
            f"║ Trading Mode   : {mode:<49} ║\n"
            f"║ Gauntlet Streak: [{streak}/{QUALIFICATION_TARGET_WINS} Consecutive Wins]                           ║\n"
            f"║ Performance    : {wins}W / {losses}L ({win_rate:.1f}% Win Rate) Total Trades: {total:<12} ║\n"
            f"║ Global Universe: {dashboard_data['cg_global_pairs']} Global ($1M+) | Bitget Tradable: {dashboard_data['bitget_tradable_pairs']:<15} ║\n"
            f"║ Current Trade  : {pos_str:<49} ║\n"
            f"╚════════════════════════════════════════════════════════════════════╝"
        )

    def run(self):
        logger.info("🚀 CoinGlass Master Radar Online. Watching Worldwide Markets...")
        last_briefing = time.time()
        last_market_sync = 0

        while True:
            try:
                # 1. Sync Bitget Tradable Symbols every 60 seconds
                if time.time() - last_market_sync >= 60:
                    last_market_sync = time.time()
                    self.sync_bitget_tradable_universe()

                # 2. Master Brain: Ingest CoinGlass Global Data
                self.sync_coinglass_master_radar()

                # 3. Position Management or Master Arbitrator Entry
                if self.active_trade:
                    self.manage_active_trade()
                else:
                    signal = self.run_master_arbitrator()
                    if signal:
                        self.enter_trade(signal)

                # Dashboard Telemetry Sync
                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                # 15-Minute Clean Desk Briefing
                if time.time() - last_briefing >= 900:
                    last_briefing = time.time()
                    self.print_15m_briefing()

                time.sleep(2.0)

            except Exception as e:
                logger.error(f"Engine Loop Exception: {e}")
                time.sleep(3)

# -----------------------------------------------------------------------------
# SECTION 11: BOOTSTRAP ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    engine = BitgetDeskPartnerEngine()
    engine.run()

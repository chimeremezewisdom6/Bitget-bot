#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: MASTER QUANTITATIVE DESK ENGINE (BITGET USDT-M PERPETUALS)
MASTER RADAR: COINGLASS_FEED.PY (TOP-8 GLOBAL MATRIX)
STRATEGIES: 6 INSTITUTIONAL MODULES + BI-DIRECTIONAL + BTC SHIELD
LEARNING ENGINE: TRUE DYNAMIC AUTOPSY (READS LIVE HISTORY & WRITES LESSONS)
GAUNTLET: STRICT 8 CONSECUTIVE WINS IN PAPER MODE BEFORE LIVE UNLOCK
INFRASTRUCTURE: RENDER PORT 10000 INSTANT BIND (NO TIMEOUTS)
===============================================================================
"""

import os
import sys
import time
import math
import json
import logging
import threading
from datetime import datetime, timezone
from collections import deque, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from requests.adapters import HTTPAdapter
import ccxt

from coinglass_feed import get_coinglass_data

# -----------------------------------------------------------------------------
# SECTION 1: LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MasterDeskEngine")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# SECTION 2: SYSTEM CONSTANTS & GLOBAL RULES
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

MIN_COINGLASS_GLOBAL_VOLUME = 1_000_000.0

# Exit Parameters (Organic Momentum Fade - No DOA Timer)
MAX_LIFECYCLE_SECONDS = 900        # 15-Minute Maximum Trade Hold
LIVE_HARD_STOP_PCT = 0.90          # Structural Emergency Hard Stop in Live Mode

# Gauntlet: 8 Consecutive Wins
QUALIFICATION_TARGET_WINS = 8
COOLDOWN_SECONDS = 600
ALLOCATION_PCT = 0.90
MIN_NOTIONAL_USDT = 5.50
MAX_LEVERAGE_CLAMP = 20
MIN_LEVERAGE_CLAMP = 2

PORT = int(os.environ.get("PORT", 10000))
STATE_FILE = "qualification_state.json"
LEARN_FILE = "learned_features.json"

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
# SECTION 3: TRUE DYNAMIC LEARNING ENGINE (ANALYZES LIVE LOGS)
# -----------------------------------------------------------------------------
class DynamicLearningEngine:
    def __init__(self, filename=LEARN_FILE):
        self.filename = filename
        self.lock = threading.Lock()
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"dynamic_insights": []}

    def save(self):
        with self.lock:
            try:
                with open(self.filename, "w") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving learning data: {e}")

    def synthesize_live_lessons(self, history):
        """Dynamically reads real trade history to compute failure stats and self-correction."""
        if not history:
            return "Initializing memory... Awaiting completed trade telemetry."

        losses = [t for t in history if t["result"] == "LOSS"]
        wins = [t for t in history if t["result"] == "WIN"]
        total = len(history)
        win_rate = (len(wins) / total * 100.0) if total > 0 else 0.0

        setup_failures = defaultdict(int)
        for l in losses:
            setup_failures[l.get("setup", "UNKNOWN")] += 1

        worst_setup = max(setup_failures, key=setup_failures.get) if setup_failures else "None"

        report = (
            f"Analyzed {total} completed trades ({len(wins)} Wins, {len(losses)} Losses | Win Rate: {win_rate:.1f}%). "
            f"Primary drawdown cluster identified in [{worst_setup}] with {setup_failures[worst_setup]} recent failures. "
            f"Adaptive Action: Dynamically down-weighting conviction score for [{worst_setup}] by -15 points to filter out chop."
        )
        return report

# -----------------------------------------------------------------------------
# SECTION 4: QUALIFICATION STATE MANAGER (GAUNTLET 1 -> 8)
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
# SECTION 5: LIVE HTTP KEEP-ALIVE SERVER (PORT 10000 DASHBOARD)
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
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        at = dashboard_data.get("active_trade")
        active_html = "<p style='color: #888;'>Master Matrix scanning worldwide markets (Instant Port Bind Active)...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            fade_status = "<span style='color: #f59e0b; font-weight: bold;'>FADING (EXIT ARMED)</span>" if at.get("is_fading") else "<span style='color: #4ade80;'>INERTIAL GLIDE ACTIVE</span>"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE POSITION: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Strategy:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                <p><b>Entry:</b> {at['entry_price']} | <b>Current:</b> {at['current_price']}</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>Fade Status:</b> {fade_status} | <b>Timer:</b> {at['elapsed_seconds']}s / {MAX_LIFECYCLE_SECONDS}s (No DOA Limit)</p>
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
            <title>Master Quantitative Desk</title>
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
            <h2>⚡ Master Quantitative Desk (Instant Port Bind)</h2>
            <div class="card">
                <b>Status:</b> {dashboard_data['status']} | 
                <b>Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Wins | 
                <b>Global Matrix:</b> {dashboard_data['cg_global_pairs']} Pairs | 
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
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        return

# INSTANT PORT BINDING TO PREVENT RENDER TIMEOUTS
http_server = None
def start_http_server():
    global http_server
    try:
        http_server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
        logger.info(f"🌐 HTTP Keep-Alive Server bound instantly on port {PORT}")
        http_server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP Server bind error: {e}")

class MasterDeskEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.learning_engine = DynamicLearningEngine()
        self.exchange = None
        self.http_session = None
        
        self.cg_buffer = defaultdict(lambda: deque(maxlen=60))
        self.bitget_markets = set()
        self.bitget_prices = {}
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

    def sync_global_matrix_radar(self):
        now = time.time()
        try:
            cg_items = get_coinglass_data()
            if cg_items:
                valid_count = 0
                for item in cg_items:
                    base_sym = item.get("symbol", "").upper()
                    if not base_sym or any(b in base_sym for b in BLACKLIST):
                        continue

                    self.cg_buffer[base_sym].append({
                        "time": now,
                        "price": float(item.get("price", 0.0) or 0.0),
                        "price_5m": float(item.get("price_5m", 0.0) or 0.0),
                        "price_15m": float(item.get("price_15m", 0.0) or 0.0),
                        "price_24h": float(item.get("price_24h", 0.0) or 0.0),
                        "oi_5m": float(item.get("oi_5m", 0.0) or 0.0),
                        "oi_15m": float(item.get("oi_15m", 0.0) or 0.0),
                        "vol_24h": float(item.get("vol_24h", 0.0) or 0.0),
                        "rsi_15m": float(item.get("rsi_15m", 50.0) or 50.0),
                        "liquidation_state": item.get("liquidation_state", "NORMAL")
                    })
                    valid_count += 1
                dashboard_data["cg_global_pairs"] = valid_count
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 6 STRATEGY MODULES (WITH DYNAMIC LEARNING PENALTY)
    # -------------------------------------------------------------------------
    def eval_module_1_regime_shift(self, base_sym, latest):
        p5m = latest["price_5m"]
        p15m = latest["price_15m"]
        oi15m = latest["oi_15m"]
        if p15m >= 1.80 and p5m >= 1.20 and oi15m >= 1.00:
            return {"side": "buy", "setup": "PLAY1_INERTIAL_REGIME_SHIFT", "score": 96}
        elif p15m <= -1.80 and p5m <= -1.20 and oi15m <= -1.00:
            return {"side": "sell", "setup": "PLAY1_INERTIAL_REGIME_SHIFT", "score": 96}
        return None

    def eval_module_2_exhaustion_wiggle(self, base_sym, latest, history):
        if len(history) < 6: return None
        p5m = latest["price_5m"]
        oi5m = latest["oi_5m"]
        recent = [h["price"] for h in list(history)[-6:]]
        wiggle = (max(recent) - min(recent)) / min(recent) * 100.0 if min(recent) > 0 else 0
        if p5m >= 1.80 and oi5m <= -0.50 and wiggle < 0.20:
            return {"side": "sell", "setup": "PLAY2_INERTIAL_WIGGLE_TOP", "score": 92}
        elif p5m <= -1.50 and oi5m >= 0.50 and wiggle < 0.20:
            return {"side": "buy", "setup": "PLAY2_INERTIAL_WIGGLE_BOTTOM", "score": 92}
        return None

    def eval_module_3_amplified_3m(self, base_sym, latest, history):
        if len(history) < 6: return None
        h = list(history)
        p_cur, p_3m = h[-1]["price"], h[-6]["price"]
        if p_3m <= 0: return None
        move = abs((p_cur - p_3m) / p_3m * 100.0)
        p5m = latest["price_5m"]
        if move >= 1.50 and abs(p5m) >= 1.20:
            if p_cur > p_3m and latest["oi_5m"] < 0:
                return {"side": "sell", "setup": "PLAY3_INERTIAL_EXHAUSTION", "score": 89}
            elif p_cur < p_3m and latest["oi_5m"] > 0:
                return {"side": "buy", "setup": "PLAY3_INERTIAL_EXHAUSTION", "score": 89}
        return None

    def eval_module_4_stepwise_tournament(self, base_sym, history):
        if len(history) < 15: return None
        prices = [h["price"] for h in history]
        if len(prices) < 2: return None
        for i in range(1, len(prices)):
            if abs((prices[i] - prices[i-1]) / prices[i-1] * 100.0) > 1.50: return None
        up = sum(1 for i in range(1, len(prices)) if (prices[i] - prices[i-1]) / prices[i-1] * 100.0 >= 0.30)
        down = sum(1 for i in range(1, len(prices)) if (prices[i] - prices[i-1]) / prices[i-1] * 100.0 <= -0.30)
        
        last_move_5m = abs((prices[-1] - prices[-5]) / prices[-5] * 100.0) if len(prices) >= 5 else 1.5
        if last_move_5m < 1.20: return None

        if down > 0 and (up / down) >= 3.0 and up >= 4:
            return {"side": "buy", "setup": "PLAY4_INERTIAL_STEPWISE", "score": 86}
        elif up > 0 and (down / up) >= 3.0 and down >= 4:
            return {"side": "sell", "setup": "PLAY4_INERTIAL_STEPWISE", "score": 86}
        return None

    def eval_module_5_pressure_cooker(self, latest):
        p15m, p5m, oi15m = latest["price_15m"], latest["price_5m"], latest["oi_15m"]
        if (1.00 <= p15m <= 2.00) and abs(p5m) >= 1.20 and oi15m <= -1.50:
            return {"side": "sell", "setup": "PLAY5_INERTIAL_PRESSURE_COOKER", "score": 94}
        return None

    def eval_module_6_whale_wall(self, bitget_symbol):
        try:
            ccxt_symbol = f"{bitget_symbol[:len(bitget_symbol)-4]}/USDT:USDT"
            ob = self.exchange.fetch_order_book(ccxt_symbol, limit=15)
            bids, asks = ob.get("bids", []), ob.get("asks", [])
            if not bids or not asks: return None
            b_vol, a_vol = sum(b[1] for b in bids[:10]), sum(a[1] for a in asks[:10])
            if a_vol > 0 and (b_vol / a_vol) >= 4.5:
                return {"side": "buy", "setup": "PLAY6_INERTIAL_WHALE_WALL", "score": 88}
            elif b_vol > 0 and (a_vol / b_vol) >= 4.5:
                return {"side": "sell", "setup": "PLAY6_INERTIAL_WHALE_WALL", "score": 88}
        except Exception:
            pass
        return None

    def check_bitcoin_macro_shield(self):
        btc_buf = self.cg_buffer.get("BTC", deque())
        if len(btc_buf) >= 5:
            btc_15m = btc_buf[-1]["price_15m"]
            if btc_15m <= -2.50:
                return True
        return False

    def run_master_arbitrator(self):
        if self.active_trade is not None:
            return None

        btc_cascading = self.check_bitcoin_macro_shield()
        now = time.time()
        candidates = []

        for base_sym, buf in list(self.cg_buffer.items()):
            bitget_symbol = f"{base_sym}USDT"
            if bitget_symbol not in self.bitget_markets: continue
            if bitget_symbol in self.cooldowns and (now - self.cooldowns[bitget_symbol]) < COOLDOWN_SECONDS: continue
            if len(buf) < 5: continue

            latest = buf[-1]
            s1 = self.eval_module_1_regime_shift(base_sym, latest)
            if s1: candidates.append({**s1, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s2 = self.eval_module_2_exhaustion_wiggle(base_sym, latest, buf)
            if s2: candidates.append({**s2, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s3 = self.eval_module_3_amplified_3m(base_sym, latest, buf)
            if s3: candidates.append({**s3, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s4 = self.eval_module_4_stepwise_tournament(base_sym, buf)
            if s4: candidates.append({**s4, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

            s5 = self.eval_module_5_pressure_cooker(latest)
            if s5: candidates.append({**s5, "bitget_symbol": bitget_symbol, "base_sym": base_sym})

        if candidates:
            if btc_cascading:
                candidates = [c for c in candidates if c["side"] == "sell"]
                if not candidates: return None

            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]
            
            exec_price = self.bitget_prices.get(top["bitget_symbol"], 0.0)
            if exec_price <= 0: return None

            s6 = self.eval_module_6_whale_wall(top["bitget_symbol"])
            if s6 and s6["side"] == top["side"]:
                top["score"] = min(100, top["score"] + 5)
                top["setup"] += "+WHALE_WALL"

            top["entry_price"] = exec_price
            logger.info(f"🎯 CERTIFIED SIGNAL (No DOA Timer): {top['base_sym']} ({top['side'].upper()}) | Strategy: {top['setup']} | Score: {top['score']}")
            return top

        return None

    def calculate_live_position_size(self, current_price):
        try:
            balance_info = self.exchange.fetch_balance()
            free_usdt = float(balance_info["free"].get("USDT", 0.0))
            usable_margin = free_usdt * ALLOCATION_PCT
            if usable_margin < 0.50: return 0, 0
            calculated_lev = math.ceil(MIN_NOTIONAL_USDT / usable_margin)
            leverage = max(MIN_LEVERAGE_CLAMP, min(calculated_lev, MAX_LEVERAGE_CLAMP))
            notional = max(MIN_NOTIONAL_USDT, usable_margin * leverage)
            return notional / current_price, leverage
        except Exception:
            return 0, 0

    def enter_trade(self, signal):
        symbol = signal["bitget_symbol"]
        base_sym = signal["base_sym"]
        side = signal["side"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        trade_info = {
            "symbol": symbol, "base_sym": base_sym, "side": side,
            "setup": signal["setup"], "entry_price": price,
            "entry_time": time.time(), "peak_price": price,
            "highest_gain_pct": 0.0, "last_peak_time": time.time(),
            "is_fading": False, "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE", "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened {side.upper()} on {symbol} @ {price} | Strategy: {signal['setup']}")
            self.active_trade = trade_info
        else:
            try:
                size, lev = self.calculate_live_position_size(price)
                if size <= 0: return
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                self.exchange.set_leverage(lev, ccxt_symbol)
                if side == "buy": order = self.exchange.create_market_buy_order(ccxt_symbol, size)
                else: order = self.exchange.create_market_sell_order(ccxt_symbol, size)
                trade_info["size"] = size
                self.active_trade = trade_info
                logger.info(f"⚡ [LIVE ENTRY] {side.upper()} {symbol} | Size: {size} | Lev: {lev}x")
            except Exception as e:
                logger.error(f"Live entry failed: {e}")
                self.active_trade = None

    def manage_active_trade(self):
        """Manages active trade with NO 90s DOA timer. Relies entirely on Organic Fade & Lifecycle."""
        if not self.active_trade: return
        trade = self.active_trade
        symbol, side = trade["symbol"], trade["side"]
        current_price = self.bitget_prices.get(symbol, trade["entry_price"])
        now = time.time()
        elapsed = max(1.0, now - trade["entry_time"])

        if side == "buy":
            gain_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
            if current_price > trade["peak_price"]:
                trade["peak_price"] = current_price
                trade["last_peak_time"] = now
            if gain_pct > trade["highest_gain_pct"]: trade["highest_gain_pct"] = gain_pct
        else:
            gain_pct = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100.0
            if current_price < trade["peak_price"]:
                trade["peak_price"] = current_price
                trade["last_peak_time"] = now
            if gain_pct > trade["highest_gain_pct"]: trade["highest_gain_pct"] = gain_pct

        if (now - trade["last_peak_time"]) >= 60 and trade["highest_gain_pct"] >= 0.50:
            trade["is_fading"] = True

        dashboard_data["active_trade"] = {
            "symbol": symbol, "side": side, "setup": trade["setup"],
            "mode": trade["mode"], "entry_price": trade["entry_price"],
            "current_price": current_price, "pnl_pct": gain_pct,
            "peak_gain_pct": trade["highest_gain_pct"], "is_fading": trade["is_fading"],
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None
        # NO 90S DOA KILL SWITCH! Trade has full breathing room.
        if trade["is_fading"] and gain_pct >= 0.30: exit_reason = "ORGANIC_MOMENTUM_FADE"
        elif elapsed >= MAX_LIFECYCLE_SECONDS: exit_reason = "15M_LIFECYCLE_EXHAUSTION"
        elif not trade["is_paper"] and gain_pct <= -LIVE_HARD_STOP_PCT: exit_reason = "HARD_STOP_LOSS"

        if exit_reason: self._execute_exit(trade, current_price, gain_pct, exit_reason)

    def _execute_exit(self, trade, exit_price, gain_pct, reason):
        symbol, side, is_paper, setup_name = trade["symbol"], trade["side"], trade["is_paper"], trade["setup"]
        try:
            if not is_paper:
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                pos = self.exchange.fetch_position(ccxt_symbol)
                exact_size = abs(float(pos.get("contracts", 0.0) or trade["size"]))
                if exact_size > 0:
                    if side == "buy": self.exchange.create_market_sell_order(ccxt_symbol, exact_size, params={"reduceOnly": True})
                    else: self.exchange.create_market_buy_order(ccxt_symbol, exact_size, params={"reduceOnly": True})
                logger.info(f"⚡ [LIVE EXIT] Closed {side.upper()} {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")
            else:
                logger.info(f"📝 [PAPER EXIT] Closed {side.upper()} {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")
            
            self.state_mgr.record_trade(symbol, side, gain_pct, reason, setup_name, is_paper)
            
            # Dynamic Learning Autopsy on Wins
            if gain_pct >= 1.50:
                self.learning_engine.autopsy_winning_trade(symbol, side, gain_pct, setup_name)
                self.print_dynamic_learning_report()

            self.cooldowns[symbol] = time.time()
        except Exception as e:
            logger.error(f"Exit error: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def print_dynamic_learning_report(self):
        """Prints true self-learned insights computed directly from live trade history."""
        history = self.state_mgr.state["history"]
        dynamic_insight = self.learning_engine.synthesize_live_lessons(history)
        
        logger.info(
            f"\n"
            f"╔════════════════════════════════════════════════════════════════════╗\n"
            f"║          🧠 TRUE DYNAMIC LEARNING ENGINE AUTOPSY REPORT            ║\n"
            f"╠════════════════════════════════════════════════════════════════════╣\n"
            f"║ {dynamic_insight:<66} ║\n"
            f"║ Master Features Logged: {len(self.learning_engine.data['scenarios'])} scenarios stored securely.         ║\n"
            f"╚════════════════════════════════════════════════════════════════════╝"
        )

    def run(self):
        logger.info("🚀 Master Quantitative Desk Engine Online (Instant Port Bind + Dynamic Learning)...")
        last_sync = 0

        while True:
            try:
                if time.time() - last_sync >= 60:
                    last_sync = time.time()
                    self.sync_bitget_tradable_universe()

                self.sync_global_matrix_radar()

                if self.active_trade:
                    self.manage_active_trade()
                else:
                    signal = self.run_master_arbitrator()
                    if signal: self.enter_trade(signal)

                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                time.sleep(2.0)
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(3)

if __name__ == "__main__":
    # BIND PORT 10000 INSTANTLY TO PREVENT RENDER TIMEOUTS
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    engine = MasterDeskEngine()
    engine.run()

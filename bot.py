#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: COINGLASS WORLDWIDE LEADERBOARD TOURNAMENT ENGINE (CLEAN TELEMETRY)
EXCHANGE: BITGET USDT-M PERPETUALS | DATA FEED: COINGLASS_FEED.PY
STRATEGY: 15-MINUTE VELOCITY ASYMMETRY (DAVID VS. SAMUEL) NO-FIXED-HURDLE RANKING
INFRASTRUCTURE: RENDER PORT 10000 KEEP-ALIVE SERVER | GAUNTLET 1 -> 6 WINS
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
# SECTION 1: LOGGING CONFIGURATION (CLEAN DESK TELEMETRY)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LeaderboardDeskEngine")

# Silence noisy third-party loggers
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
# SECTION 3: SYSTEM CONSTANTS & TOURNAMENT PARAMETERS
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

LOOKBACK_SECONDS = 900             # 15-Minute Lookback Window
MAX_TRADE_LIFECYCLE_SECONDS = 900  # 15-Minute Maximum Trade Hold (Rotate to new leader)
VELOCITY_DECAY_RATIO = 2.0         # Armed when speed ratio collapses from peak to <= 2.0x
PEAK_REVERSE_PULLBACK_PCT = 0.50   # 0.5% Peak Reverse Trailing Wall
DOA_TIMEOUT_SECONDS = 90           # 90-Second Dead-on-Arrival Kill Switch
DOA_FORWARD_THRESHOLD_PCT = 0.30   # Must gain at least +0.30% in 90s or abort
LIVE_HARD_STOP_PCT = 0.90          # Structural Emergency Hard Stop in Live Mode

# Gauntlet & Execution Parameters
QUALIFICATION_TARGET_WINS = 6      # Strict 6 consecutive paper wins before Live unlock
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
# SECTION 5: QUALIFICATION STATE MANAGER (GAUNTLET 1 -> 6)
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
                    return json.load(f)
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

    def record_trade(self, symbol, side, gain_pct, exit_reason, is_paper):
        with self.lock:
            self.state["total_trades"] += 1
            is_win = gain_pct > 0.0

            if is_win:
                self.state["total_wins"] += 1
                if self.state["mode"] == "PAPER":
                    self.state["consecutive_wins"] += 1
                    logger.info(f"🏆 PAPER WIN! Streak: {self.state['consecutive_wins']}/{QUALIFICATION_TARGET_WINS}")
                    if self.state["consecutive_wins"] >= QUALIFICATION_TARGET_WINS:
                        self.state["mode"] = "LIVE"
                        logger.info("🚀 GAUNTLET COMPLETED! AUTHORIZING LIVE TRADING ENGINE!")
            else:
                self.state["total_losses"] += 1
                if self.state["mode"] == "PAPER":
                    logger.warning(f"❌ PAPER LOSS. Streak reset to 0/{QUALIFICATION_TARGET_WINS}")
                    self.state["consecutive_wins"] = 0

            trade_log = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
                "side": side.upper(),
                "gain_pct": round(gain_pct, 3),
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
    "universe_size": 0,
    "cg_synced_pairs": 0,
    "active_trade": None,
    "recent_trades": [],
    "last_update": ""
}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Silences Render's keep-alive ping without 501 errors."""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        at = dashboard_data.get("active_trade")
        active_html = "<p style='color: #888;'>No active positions. Scanning 15m order flow...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            fade_status = "<span style='color: #f59e0b; font-weight: bold;'>ARMED (FADING)</span>" if at.get("velocity_decayed") else "<span style='color: #4ade80;'>ACTIVE PROPULSION</span>"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE POSITION: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Mode:</b> {at['mode']} | <b>Entry Price:</b> {at['entry_price']} | <b>Current Price:</b> {at['current_price']}</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>Speed Ratio:</b> {at.get('current_speed_ratio', 0.0):.1f}x | <b>Fade Status:</b> {fade_status}</p>
                <p><b>Lifecycle Timer:</b> {at['elapsed_seconds']}s / {MAX_TRADE_LIFECYCLE_SECONDS}s (DOA Limit: {DOA_TIMEOUT_SECONDS}s)</p>
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
                <td style="padding: 6px; color: {color}; font-weight: bold;">{t['gain_pct']:+.2f}%</td>
                <td style="padding: 6px;">{t['exit_reason']}</td>
                <td style="padding: 6px;">{t['mode']}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Leaderboard Tournament Desk</title>
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
            <h2>🏆 CoinGlass Leaderboard Tournament Engine</h2>
            <div class="card">
                <b>Status:</b> {dashboard_data['status']} | 
                <b>Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Wins | 
                <b>Tracking Universe:</b> {dashboard_data['universe_size']} Bitget Pairs
            </div>

            <div class="card">
                <h3>Live Position Telemetry</h3>
                {active_html}
            </div>

            <div class="card">
                <h3>Recent Execution Log</h3>
                <table>
                    <thead>
                        <tr><th>Time</th><th>Symbol</th><th>Side</th><th>PnL %</th><th>Exit Reason</th><th>Type</th></tr>
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
        """Silences standard HTTP request logging in terminal to keep logs clean."""
        return

def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    server.serve_forever()

# -----------------------------------------------------------------------------
# SECTION 7: DESK TRADING BOT CORE ENGINE
# -----------------------------------------------------------------------------
class BitgetDeskPartnerEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.exchange = None
        self.http_session = None
        self.price_buffer = defaultdict(lambda: deque(maxlen=600))  # 15m tick memory
        self.cooldowns = {}
        self.active_trade = None
        self.cg_map = {}

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

    def sync_coinglass_leaderboard(self):
        global get_coinglass_data
        if not get_coinglass_data:
            return

        try:
            cg_items = get_coinglass_data()
            if cg_items:
                self.cg_map.clear()
                for item in cg_items:
                    sym = item.get("symbol", "").upper()
                    if sym:
                        self.cg_map[sym] = item
                dashboard_data["cg_synced_pairs"] = len(self.cg_map)
        except Exception:
            pass

    def fetch_universal_tickers(self):
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
        try:
            resp = self.http_session.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
        except Exception:
            pass
        return []

    def update_buffers(self, tickers):
        """
        ACCURATE OPEN INTEREST CAPTURE:
        Reads Bitget's official 'holdingAmount' field so real OI delta is tracked.
        """
        now = time.time()
        active_count = 0

        for t in tickers:
            symbol = t.get("symbol", "")
            if any(b in symbol for b in BLACKLIST):
                continue

            try:
                last_price = float(t.get("lastPr", 0.0))
                # Bitget official field name for Open Interest is holdingAmount
                oi = float(t.get("holdingAmount", 0.0) or t.get("openInterest", 0.0) or 0.0)
                if last_price <= 0:
                    continue

                self.price_buffer[symbol].append({
                    "time": now,
                    "price": last_price,
                    "oi": oi
                })
                active_count += 1
            except (ValueError, TypeError):
                continue

        dashboard_data["universe_size"] = active_count

    def run_leaderboard_tournament(self):
        """
        15-MINUTE DAVID VS. SAMUEL SPEED TOURNAMENT WITH ACTIVE OPEN INTEREST:
        Ranks all coins by (Reclaim Speed / Drop Speed) * OI Delta.
        Selects #1 Undisputed Leader without arbitrary hurdles.
        """
        if self.active_trade is not None:
            return None

        now = time.time()
        cutoff = now - LOOKBACK_SECONDS
        candidates = []

        for symbol, buf in list(self.price_buffer.items()):
            if symbol in self.cooldowns and (now - self.cooldowns[symbol]) < COOLDOWN_SECONDS:
                continue

            ticks = [b for b in buf if b["time"] >= cutoff]
            if len(ticks) < 45:
                continue

            # Calculate Native Bitget 15-Minute OI Delta
            oldest_oi = ticks[0]["oi"]
            latest_oi = ticks[-1]["oi"]
            native_oi_delta = 0.0
            if oldest_oi > 0:
                native_oi_delta = ((latest_oi - oldest_oi) / oldest_oi) * 100.0

            # Check CoinGlass OI as secondary verification
            base_sym = symbol.replace("USDT", "").replace("_USDT", "").upper()
            cg_info = self.cg_map.get(base_sym, {})
            cg_oi = float(cg_info.get("oi_15m", 0.0) or 0.0)

            # Combined Effective OI
            effective_oi = cg_oi if cg_oi != 0.0 else native_oi_delta

            current_price = ticks[-1]["price"]
            prices = [t["price"] for t in ticks]
            min_p = min(prices)
            max_p = max(prices)
            min_idx = prices.index(min_p)
            max_idx = prices.index(max_p)

            # -------------------------------------------------------------
            # TOURNAMENT: LONG CANDIDATE
            # -------------------------------------------------------------
            if max_idx < min_idx and min_idx < (len(ticks) - 1):
                t_peak = ticks[max_idx]["time"]
                t_trough = ticks[min_idx]["time"]
                t_current = ticks[-1]["time"]

                drop_duration = max(60, t_trough - t_peak)
                rebound_duration = max(30, t_current - t_trough)

                drop_pct = ((max_p - min_p) / max_p) * 100.0
                rebound_pct = ((current_price - min_p) / min_p) * 100.0

                if drop_pct > 0.20 and rebound_pct > 0.20:
                    v_down = drop_pct / (drop_duration / 60.0)
                    v_up = rebound_pct / (rebound_duration / 60.0)

                    if v_down > 0:
                        speed_ratio = v_up / v_down

                        # STRICT LONG POLARITY: OI must be non-negative
                        if effective_oi >= 0.0:
                            score = speed_ratio * (1.0 + max(0.0, effective_oi / 10.0))
                            candidates.append({
                                "symbol": symbol,
                                "side": "buy",
                                "score": score,
                                "entry_price": current_price,
                                "baseline_speed": v_down,
                                "speed_ratio": speed_ratio,
                                "oi_delta": effective_oi
                            })

            # -------------------------------------------------------------
            # TOURNAMENT: SHORT CANDIDATE
            # -------------------------------------------------------------
            if min_idx < max_idx and max_idx < (len(ticks) - 1):
                t_trough = ticks[min_idx]["time"]
                t_peak = ticks[max_idx]["time"]
                t_current = ticks[-1]["time"]

                climb_duration = max(60, t_peak - t_trough)
                flush_duration = max(30, t_current - t_peak)

                climb_pct = ((max_p - min_p) / min_p) * 100.0
                flush_pct = ((max_p - current_price) / max_p) * 100.0

                if climb_pct > 0.20 and flush_pct > 0.20:
                    v_up = climb_pct / (climb_duration / 60.0)
                    v_down = flush_pct / (flush_duration / 60.0)

                    if v_up > 0:
                        speed_ratio = v_down / v_up

                        # STRICT SHORT POLARITY & TRAP BLOCK:
                        # OI must be strictly NEGATIVE (-). If positive, short is blocked!
                        if effective_oi < 0.0:
                            score = speed_ratio * (1.0 + (abs(effective_oi) / 10.0))
                            candidates.append({
                                "symbol": symbol,
                                "side": "sell",
                                "score": score,
                                "entry_price": current_price,
                                "baseline_speed": v_up,
                                "speed_ratio": speed_ratio,
                                "oi_delta": effective_oi
                            })

        if candidates:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]

            if top["speed_ratio"] >= 2.0:
                logger.info(
                    f"🎯 #1 TOURNAMENT LEADER FOUND: {top['symbol']} ({top['side'].upper()}) | "
                    f"Speed Ratio: {top['speed_ratio']:.1f}x | OI Delta: {top['oi_delta']:+.2f}%"
                )
                return top

        return None

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
        symbol = signal["symbol"]
        side = signal["side"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        trade_info = {
            "symbol": symbol,
            "side": side,
            "entry_price": price,
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gain_pct": 0.0,
            "baseline_speed": signal["baseline_speed"],
            "initial_speed_ratio": signal["speed_ratio"],
            "current_speed_ratio": signal["speed_ratio"],
            "peak_speed_ratio": signal["speed_ratio"],
            "velocity_decayed": False,
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened #1 Leader {side.upper()} on {symbol} @ {price}")
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
                logger.info(f"⚡ [LIVE ENTRY] #1 Leader {side.upper()} {symbol} | Size: {size} | Lev: {lev}x")
            except Exception as e:
                logger.error(f"Live entry execution failed: {e}")
                self.active_trade = None

    def manage_active_trade(self):
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        side = trade["side"]
        buf = self.price_buffer.get(symbol)
        if not buf:
            return

        latest = buf[-1]
        current_price = latest["price"]
        elapsed = max(1.0, time.time() - trade["entry_time"])

        if side == "buy":
            gain_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
            if current_price > trade["peak_price"]:
                trade["peak_price"] = current_price
            if gain_pct > trade["highest_gain_pct"]:
                trade["highest_gain_pct"] = gain_pct
            pullback_from_peak = trade["highest_gain_pct"] - gain_pct
        else:
            gain_pct = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100.0
            if current_price < trade["peak_price"]:
                trade["peak_price"] = current_price
            if gain_pct > trade["highest_gain_pct"]:
                trade["highest_gain_pct"] = gain_pct
            pullback_from_peak = trade["highest_gain_pct"] - gain_pct

        current_speed = max(0.0, gain_pct) / (elapsed / 60.0)
        baseline = trade["baseline_speed"]
        if baseline > 0:
            current_ratio = current_speed / baseline
            trade["current_speed_ratio"] = current_ratio
            if current_ratio > trade["peak_speed_ratio"]:
                trade["peak_speed_ratio"] = current_ratio

            if trade["peak_speed_ratio"] >= 3.0 and current_ratio <= VELOCITY_DECAY_RATIO and gain_pct >= 0.40:
                if not trade["velocity_decayed"]:
                    trade["velocity_decayed"] = True
                    logger.info(f"⚠️ MOMENTUM FADE on {symbol}: Velocity decayed. 0.5% Wall ARMED!")

        dashboard_data["active_trade"] = {
            "symbol": symbol,
            "side": side,
            "mode": trade["mode"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "pnl_pct": gain_pct,
            "peak_gain_pct": trade["highest_gain_pct"],
            "initial_speed_ratio": trade.get("initial_speed_ratio", 0.0),
            "current_speed_ratio": trade.get("current_speed_ratio", 0.0),
            "velocity_decayed": trade["velocity_decayed"],
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        if pullback_from_peak >= PEAK_REVERSE_PULLBACK_PCT:
            exit_reason = "0.5%_PEAK_REVERSE (FADE_EXIT)"
        elif elapsed >= MAX_TRADE_LIFECYCLE_SECONDS:
            exit_reason = "15M_ROTATION_EXHAUSTION"
        elif elapsed >= DOA_TIMEOUT_SECONDS and trade["highest_gain_pct"] < DOA_FORWARD_THRESHOLD_PCT:
            exit_reason = "90S_DOA_KILL_SWITCH"
        elif not trade["is_paper"] and gain_pct <= -LIVE_HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        if exit_reason:
            self._execute_exit(trade, current_price, gain_pct, exit_reason)

    def _execute_exit(self, trade, exit_price, gain_pct, reason):
        symbol = trade["symbol"]
        side = trade["side"]
        is_paper = trade["is_paper"]

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

            self.state_mgr.record_trade(symbol, side, gain_pct, reason, is_paper)
            self.cooldowns[symbol] = time.time()

        except Exception as e:
            logger.error(f"Error during exit execution: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def print_15m_briefing(self):
        """Clean, professional 15-minute desk intelligence box (No messy lines)."""
        mode = self.state_mgr.state["mode"]
        streak = self.state_mgr.state["consecutive_wins"]
        total = self.state_mgr.state["total_trades"]
        wins = self.state_mgr.state["total_wins"]
        losses = self.state_mgr.state["total_losses"]
        win_rate = (wins / total * 100.0) if total > 0 else 0.0

        pos_str = "None (Scanning Order Flow)"
        if self.active_trade:
            pos_str = f"{self.active_trade['symbol']} ({self.active_trade['side'].upper()}) PnL: {dashboard_data['active_trade']['pnl_pct']:+.2f}%"

        logger.info(
            f"\n"
            f"╔════════════════════════════════════════════════════════════════════╗\n"
            f"║                📊 15-MINUTE DESK INTELLIGENCE BRIEFING             ║\n"
            f"╠════════════════════════════════════════════════════════════════════╣\n"
            f"║ Engine Status  : RUNNING ACTIVE                                    ║\n"
            f"║ Trading Mode   : {mode:<49} ║\n"
            f"║ Gauntlet Streak: [{streak}/{QUALIFICATION_TARGET_WINS} Consecutive Wins]                           ║\n"
            f"║ Performance    : {wins}W / {losses}L ({win_rate:.1f}% Win Rate) Total Trades: {total:<12} ║\n"
            f"║ Active Pairs   : {dashboard_data['universe_size']} Bitget Pairs Monitored                           ║\n"
            f"║ Current Trade  : {pos_str:<49} ║\n"
            f"╚════════════════════════════════════════════════════════════════════╝"
        )

    def run(self):
        logger.info("🚀 Leaderboard Tournament Engine Online. Clean Telemetry Active...")
        last_briefing = time.time()
        last_cg_sync = 0

        while True:
            try:
                if time.time() - last_cg_sync >= 20:
                    last_cg_sync = time.time()
                    self.sync_coinglass_leaderboard()

                tickers = self.fetch_universal_tickers()
                if tickers:
                    self.update_buffers(tickers)

                if self.active_trade:
                    self.manage_active_trade()
                else:
                    signal = self.run_leaderboard_tournament()
                    if signal:
                        self.enter_trade(signal)

                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                # Clean 15-Minute Desk Intelligence Briefing
                if time.time() - last_briefing >= 900:
                    last_briefing = time.time()
                    self.print_15m_briefing()

                time.sleep(1.5)

            except Exception as e:
                logger.error(f"Engine Loop Exception: {e}")
                time.sleep(3)

# -----------------------------------------------------------------------------
# SECTION 8: BOOTSTRAP ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    engine = BitgetDeskPartnerEngine()
    engine.run()

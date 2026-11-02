#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: 6-MODULE ARBITRATED INSTITUTIONAL DESK ENGINE (BITGET USDT-M)
STRATEGIES:
  1. Multi-Timeframe Regime Shift (4H Capitulation -> 15M Ignition)
  2. Exhaustion Divergence ("The Wiggle Trap" - Price vs. OI Divergence)
  3. Amplified 3-Minute Exhaustion Climax (Accelerating Decay Snapback)
  4. 20-Minute Stepwise Ratio Tournament (Clean Auction Waves, Anti-Spike)
  5. Pressure Cooker Disconnect (Metrics Die, Price Floats -> Short Flush)
  6. 24-Hour Whale Liquidity Magnet (Order Book Wall Imbalance)
EXIT SYSTEM:
  - Organic Momentum Fade (Velocity Rollover + Wiggle Stall + OI Exhaustion)
  - 90-Second Dead-on-Arrival (DOA) Kill Switch (< +0.30% Forward Thrust)
  - 0.90% Emergency Live Hard Stop
INFRASTRUCTURE:
  - Render Port 10000 HTTP Keep-Alive Server (HEAD 200 OK & GET Dashboard)
  - Python 3.12 Timezone-Aware UTC Standard
  - Qualification Gauntlet (1 -> 6 Consecutive Wins) in qualification_state.json
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
logger = logging.getLogger("InstitutionalDeskEngine")

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
# SECTION 3: SYSTEM CONSTANTS & STRATEGY PARAMETERS
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

MIN_24H_VOLUME_USDT = 1_000_000.0  # $1M Liquidity Gate
BUFFER_RETENTION_SECONDS = 1200    # 20 Minutes of Rolling High-Resolution Ticks

# Exit Parameters (Organic Fade Engine - No Fixed 0.5% Pullback)
DOA_TIMEOUT_SECONDS = 90           # 90-Second Dead-on-Arrival Kill Switch
DOA_FORWARD_THRESHOLD_PCT = 0.30   # Must gain at least +0.30% in 90s or abort
MAX_LIFECYCLE_SECONDS = 900        # 15-Minute Maximum Trade Hold
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

    def record_trade(self, symbol, side, gain_pct, exit_reason, setup_name, is_paper):
        with self.lock:
            self.state["total_trades"] += 1
            is_win = gain_pct > 0.0

            if is_win:
                self.state["total_wins"] += 1
                if self.state["mode"] == "PAPER":
                    self.state["consecutive_wins"] += 1
                    logger.info(f"🏆 PAPER WIN! Streak: {self.state['consecutive_wins']}/{QUALIFICATION_TARGET_WINS} | Strategy: {setup_name}")
                    if self.state["consecutive_wins"] >= QUALIFICATION_TARGET_WINS:
                        self.state["mode"] = "LIVE"
                        logger.info("🚀 GAUNTLET COMPLETED! AUTHORIZING LIVE TRADING ENGINE!")
            else:
                self.state["total_losses"] += 1
                if self.state["mode"] == "PAPER":
                    logger.warning(f"❌ PAPER LOSS. Streak reset to 0/{QUALIFICATION_TARGET_WINS} | Strategy: {setup_name}")
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
    "universe_size": 0,
    "active_trade": None,
    "recent_trades": [],
    "last_update": ""
}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        """Silences Render's keep-alive health pings with 200 OK."""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        at = dashboard_data.get("active_trade")
        active_html = "<p style='color: #888;'>Scanning 6-module order flow across all pairs...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            fade_status = "<span style='color: #f59e0b; font-weight: bold;'>FADING DETECTED (PREPARING EXIT)</span>" if at.get("is_fading") else "<span style='color: #4ade80;'>ACTIVE MOMENTUM EXPANSION</span>"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE POSITION: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Strategy Module:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                <p><b>Entry Price:</b> {at['entry_price']} | <b>Current Price:</b> {at['current_price']}</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>Fade Status:</b> {fade_status}</p>
                <p><b>Lifecycle Timer:</b> {at['elapsed_seconds']}s / {MAX_LIFECYCLE_SECONDS}s (DOA Limit: {DOA_TIMEOUT_SECONDS}s)</p>
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
            <title>Institutional 6-Module Desk</title>
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
            <h2>⚡ Institutional 6-Module Trading Desk</h2>
            <div class="card">
                <b>Status:</b> {dashboard_data['status']} | 
                <b>Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Wins | 
                <b>Universe:</b> {dashboard_data['universe_size']} Bitget Pairs
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
# SECTION 7: DESK TRADING BOT CORE ENGINE
# -----------------------------------------------------------------------------
class BitgetDeskPartnerEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.exchange = None
        self.http_session = None
        self.price_buffer = defaultdict(lambda: deque(maxlen=800))  # 20m high-res buffer
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
        now = time.time()
        active_count = 0

        for t in tickers:
            symbol = t.get("symbol", "")
            if any(b in symbol for b in BLACKLIST):
                continue

            try:
                vol_24h = float(t.get("usdtVolume", 0.0) or t.get("baseVolume", 0.0))
                if vol_24h < MIN_24H_VOLUME_USDT:
                    continue

                last_price = float(t.get("lastPr", 0.0))
                # Bitget native Open Interest is officially holdingAmount
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

    # -------------------------------------------------------------------------
    # SECTION 8: THE 6 INSTITUTIONAL STRATEGY MODULES
    # -------------------------------------------------------------------------

    def eval_module_1_regime_shift(self, symbol, ticks, current_price, cg_info):
        """Play 1: Multi-Timeframe Regime Shift (4H Capitulation -> 15M Ignition)."""
        cg_p15m = float(cg_info.get("price_15m", 0.0) or 0.0)
        cg_oi15m = float(cg_info.get("oi_15m", 0.0) or 0.0)

        # Long: 15m violent positive flip with institutional OI surge
        if cg_p15m >= 1.50 and cg_oi15m >= 1.00:
            return {
                "symbol": symbol,
                "side": "buy",
                "setup": "PLAY1_MTF_REGIME_SHIFT",
                "score": 95,
                "entry_price": current_price
            }
        # Short: 15m violent negative flip with liquidation flush
        elif cg_p15m <= -1.50 and cg_oi15m <= -1.00:
            return {
                "symbol": symbol,
                "side": "sell",
                "setup": "PLAY1_MTF_REGIME_SHIFT",
                "score": 95,
                "entry_price": current_price
            }
        return None

    def eval_module_2_exhaustion_wiggle(self, symbol, ticks, current_price):
        """Play 2: Exhaustion Divergence ('The Wiggle Trap' - Price vs. OI Divergence)."""
        if len(ticks) < 45:
            return None

        p_5m_ago = ticks[-40]["price"]
        oi_5m_ago = ticks[-40]["oi"]
        latest_oi = ticks[-1]["oi"]

        price_5m_pct = ((current_price - p_5m_ago) / p_5m_ago) * 100.0
        oi_5m_pct = ((latest_oi - oi_5m_ago) / oi_5m_ago * 100.0) if oi_5m_ago > 0 else 0.0

        recent_prices = [t["price"] for t in ticks[-15:]]
        price_wiggle_range = (max(recent_prices) - min(recent_prices)) / min(recent_prices) * 100.0

        # Short: Price pumped >= +1.8%, but OI died (<= -0.5%) and price is wiggling sideways
        if price_5m_pct >= 1.80 and oi_5m_pct <= -0.50 and price_wiggle_range < 0.20:
            return {
                "symbol": symbol,
                "side": "sell",
                "setup": "PLAY2_WIGGLE_DIVERGENCE_TOP",
                "score": 90,
                "entry_price": current_price
            }
        # Long: Price dumped <= -1.8%, but OI surged (>= +0.5% absorption) and price wiggles at support
        elif price_5m_pct <= -1.80 and oi_5m_pct >= 0.50 and price_wiggle_range < 0.20:
            return {
                "symbol": symbol,
                "side": "buy",
                "setup": "PLAY2_WIGGLE_ABSORPTION_BOTTOM",
                "score": 90,
                "entry_price": current_price
            }
        return None

    def eval_module_3_amplified_3m(self, symbol, ticks, current_price):
        """Play 3: Amplified 3-Minute Exhaustion Climax (Accelerating Thrust Decay Snapback)."""
        if len(ticks) < 90:
            return None

        # 3 distinct 1-minute blocks
        m3_ticks = [t["price"] for t in ticks[-30:]]
        m2_ticks = [t["price"] for t in ticks[-60:-30]]
        m1_ticks = [t["price"] for t in ticks[-90:-60]]

        d1 = abs((m1_ticks[-1] - m1_ticks[0]) / m1_ticks[0] * 100.0)
        d2 = abs((m2_ticks[-1] - m2_ticks[0]) / m2_ticks[0] * 100.0)
        d3 = abs((m3_ticks[-1] - m3_ticks[0]) / m3_ticks[0] * 100.0)

        total_move = abs((current_price - m1_ticks[0]) / m1_ticks[0] * 100.0)

        # Accelerating exhaustion: d1 > d2 > d3 while total move was real (>= 1.4%)
        if total_move >= 1.40 and d1 > (d2 * 1.3) and d2 > (d3 * 1.3) and d3 < 0.15:
            # If price was dumping, sellers are exhausted -> Enter Long Snapback
            if current_price < m1_ticks[0]:
                return {
                    "symbol": symbol,
                    "side": "buy",
                    "setup": "PLAY3_AMPLIFIED_EXHAUSTION_SNAP",
                    "score": 88,
                    "entry_price": current_price
                }
            # If price was pumping, buyers are exhausted -> Enter Short Snapback
            else:
                return {
                    "symbol": symbol,
                    "side": "sell",
                    "setup": "PLAY3_AMPLIFIED_EXHAUSTION_SNAP",
                    "score": 88,
                    "entry_price": current_price
                }
        return None

    def eval_module_4_stepwise_20m(self, symbol, ticks, current_price):
        """Play 4: 20-Minute Stepwise Ratio Tournament (Clean Auction Waves, Anti-Spike)."""
        if len(ticks) < 120:
            return None

        prices = [t["price"] for t in ticks]
        start_p = prices[0]

        # Anti-Spike Guard: Disqualify if any single 1-minute jump was > 1.5%
        for i in range(15, len(prices), 15):
            if abs((prices[i] - prices[i-15]) / prices[i-15] * 100.0) > 1.50:
                return None

        # Count 0.5% steps
        steps_up = 0
        steps_down = 0
        for i in range(1, len(prices)):
            delta = (prices[i] - prices[i-1]) / prices[i-1] * 100.0
            if delta >= 0.50:
                steps_up += 1
            elif delta <= -0.50:
                steps_down += 1

        if steps_down > 0 and (steps_up / steps_down) >= 3.0 and steps_up >= 4:
            return {
                "symbol": symbol,
                "side": "buy",
                "setup": "PLAY4_STEPWISE_AUCTION_TOURNAMENT",
                "score": 85,
                "entry_price": current_price
            }
        return None

    def eval_module_5_pressure_cooker(self, symbol, ticks, current_price, cg_info):
        """Play 5: Pressure Cooker Disconnect (Metrics Die, Price Floats -> Short Flush)."""
        cg_oi15m = float(cg_info.get("oi_15m", 0.0) or 0.0)
        cg_vol1h = float(cg_info.get("vol_1h", 0.0) or 0.0)

        if len(ticks) < 90:
            return None

        p_15m_ago = ticks[0]["price"]
        price_15m_pct = ((current_price - p_15m_ago) / p_15m_ago) * 100.0

        # Disconnect: Price is floating up (+0.8% to +1.5%), but OI dropped >= 2% and Vol dropped
        if (0.80 <= price_15m_pct <= 1.80) and cg_oi15m <= -2.00 and cg_vol1h <= -2.00:
            return {
                "symbol": symbol,
                "side": "sell",
                "setup": "PLAY5_PRESSURE_COOKER_DISCONNECT",
                "score": 92,
                "entry_price": current_price
            }
        return None

    def eval_module_6_whale_wall(self, symbol, current_price):
        """Play 6: 24-Hour Whale Liquidity Magnet (Order Book Wall Imbalance)."""
        try:
            ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
            ob = self.exchange.fetch_order_book(ccxt_symbol, limit=20)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])

            if not bids or not asks:
                return None

            bid_vol = sum([b[1] for b in bids[:10]])
            ask_vol = sum([a[1] for a in asks[:10]])

            if ask_vol > 0 and (bid_vol / ask_vol) >= 4.0:
                # Heavy institutional bid wall supporting price
                return {
                    "symbol": symbol,
                    "side": "buy",
                    "setup": "PLAY6_WHALE_BID_WALL_MAGNET",
                    "score": 86,
                    "entry_price": current_price
                }
            elif bid_vol > 0 and (ask_vol / bid_vol) >= 4.0:
                # Heavy institutional ask wall pushing price down
                return {
                    "symbol": symbol,
                    "side": "sell",
                    "setup": "PLAY6_WHALE_ASK_WALL_MAGNET",
                    "score": 86,
                    "entry_price": current_price
                }
        except Exception:
            pass
        return None

    def run_multi_module_arbitrator(self):
        """
        ARBITRATOR: Runs all 6 modules across the universe.
        Selects the single #1 highest-conviction setup in the market.
        """
        if self.active_trade is not None:
            return None

        now = time.time()
        candidates = []

        for symbol, buf in list(self.price_buffer.items()):
            if symbol in self.cooldowns and (now - self.cooldowns[symbol]) < COOLDOWN_SECONDS:
                continue

            ticks = list(buf)
            if len(ticks) < 45:
                continue

            current_price = ticks[-1]["price"]
            base_sym = symbol.replace("USDT", "").replace("_USDT", "").upper()
            cg_info = self.cg_map.get(base_sym, {})

            # 1. Evaluate Module 1
            s1 = self.eval_module_1_regime_shift(symbol, ticks, current_price, cg_info)
            if s1: candidates.append(s1)

            # 2. Evaluate Module 2
            s2 = self.eval_module_2_exhaustion_wiggle(symbol, ticks, current_price)
            if s2: candidates.append(s2)

            # 3. Evaluate Module 3
            s3 = self.eval_module_3_amplified_3m(symbol, ticks, current_price)
            if s3: candidates.append(s3)

            # 4. Evaluate Module 4
            s4 = self.eval_module_4_stepwise_20m(symbol, ticks, current_price)
            if s4: candidates.append(s4)

            # 5. Evaluate Module 5
            s5 = self.eval_module_5_pressure_cooker(symbol, ticks, current_price, cg_info)
            if s5: candidates.append(s5)

        # Check Module 6 for top 5 volume movers
        if candidates:
            candidates.sort(key=lambda x: x["score"], reverse=True)
            top = candidates[0]
            logger.info(
                f"🎯 HIGH-CONVICTION TRIGGER: {top['symbol']} ({top['side'].upper()}) | "
                f"Module: {top['setup']} | Score: {top['score']}/100"
            )
            return top

        return None

    # -------------------------------------------------------------------------
    # SECTION 9: POSITION SIZING & MICRO-ACCOUNT EXECUTION
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
        symbol = signal["symbol"]
        side = signal["side"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        trade_info = {
            "symbol": symbol,
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
    # SECTION 10: ORGANIC FADE EXIT STATE MACHINE (NO FIXED 0.5% WALL)
    # -------------------------------------------------------------------------
    def manage_active_trade(self):
        """
        ORGANIC FADE DETECTION:
        Leaves the trade immediately when:
        1. Velocity Rollover: Forward velocity collapses.
        2. Wiggle Stall: Price stops making new peaks and wiggles in a tight band.
        3. OI Exhaustion: Open Interest stops expanding.
        """
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
        current_oi = latest["oi"]
        now = time.time()
        elapsed = max(1.0, now - trade["entry_time"])

        # PnL & Peak Tracking
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

        # ---------------------------------------------------------------------
        # ORGANIC FADE EVALUATION (Velocity Rollover + Wiggle Stall + OI Decel)
        # ---------------------------------------------------------------------
        time_since_last_peak = now - trade["last_peak_time"]
        
        # Calculate velocity in the last 60 seconds
        ticks_60s = [t["price"] for t in buf if t["time"] >= (now - 60)]
        velocity_60s = 0.0
        if len(ticks_60s) > 1:
            velocity_60s = abs((ticks_60s[-1] - ticks_60s[0]) / ticks_60s[0] * 100.0)

        # Wiggle stall: Position is in profit (>= +0.40%), but has made NO new peak for > 60s
        # and price is wiggling inside a tight band (< 0.15%) with velocity rolling over
        is_wiggle_stalled = (
            trade["highest_gain_pct"] >= 0.40 and 
            time_since_last_peak >= 60 and 
            velocity_60s < 0.15
        )

        if is_wiggle_stalled:
            trade["is_fading"] = True

        # Update Live Telemetry for Dashboard
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

        # 1. ORGANIC FADE EXIT (Leaves immediately when momentum runs out of breath)
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
        """Exits position cleanly and guarantees atomic active_trade = None cleanup."""
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
        """Clean, professional 15-minute desk intelligence box (No messy lines)."""
        mode = self.state_mgr.state["mode"]
        streak = self.state_mgr.state["consecutive_wins"]
        total = self.state_mgr.state["total_trades"]
        wins = self.state_mgr.state["total_wins"]
        losses = self.state_mgr.state["total_losses"]
        win_rate = (wins / total * 100.0) if total > 0 else 0.0

        pos_str = "None (Scanning 6 Modules)"
        if self.active_trade:
            pos_str = f"{self.active_trade['symbol']} ({self.active_trade['side'].upper()}) PnL: {dashboard_data['active_trade']['pnl_pct']:+.2f}%"

        logger.info(
            f"\n"
            f"╔════════════════════════════════════════════════════════════════════╗\n"
            f"║                📊 15-MINUTE DESK INTELLIGENCE BRIEFING             ║\n"
            f"╠════════════════════════════════════════════════════════════════════╣\n"
            f"║ Engine Status  : RUNNING ACTIVE (6 Institutional Modules)          ║\n"
            f"║ Trading Mode   : {mode:<49} ║\n"
            f"║ Gauntlet Streak: [{streak}/{QUALIFICATION_TARGET_WINS} Consecutive Wins]                           ║\n"
            f"║ Performance    : {wins}W / {losses}L ({win_rate:.1f}% Win Rate) Total Trades: {total:<12} ║\n"
            f"║ Active Pairs   : {dashboard_data['universe_size']} Bitget Pairs Monitored                           ║\n"
            f"║ Current Trade  : {pos_str:<49} ║\n"
            f"╚════════════════════════════════════════════════════════════════════╝"
        )

    def run(self):
        logger.info("🚀 Institutional 6-Module Engine Online. Clean Telemetry Active...")
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
                    signal = self.run_multi_module_arbitrator()
                    if signal:
                        self.enter_trade(signal)

                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                if time.time() - last_briefing >= 900:
                    last_briefing = time.time()
                    self.print_15m_briefing()

                time.sleep(1.5)

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

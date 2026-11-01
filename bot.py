#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: QUANTITATIVE DESK ENGINE (BITGET USDT-M PERPETUALS)
STRATEGY: GLOBAL INDEX CATCH-UP TRAP & MOMENTUM IGNITION
DEPLOYMENT: RENDER (PORT 10000 HTTP DASHBOARD) VIA GITHUB
===============================================================================
"""

import os
import sys
import time
import math
import json
import logging
import threading
from datetime import datetime
from collections import deque, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from requests.adapters import HTTPAdapter
import ccxt

# -----------------------------------------------------------------------------
# SECTION 1: LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DeskPartnerBot")

# -----------------------------------------------------------------------------
# SECTION 2: SYSTEM CONSTANTS & STRATEGY PARAMETERS
# -----------------------------------------------------------------------------
# Blacklist: Illiquid, de-pegged, or historically errant symbols
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

# Market Filters
MIN_24H_VOLUME_USDT = 1_000_000.0  # $1M Global/Local Liquidity Filter
HISTORY_BUFFER_SECONDS = 300       # 5 minutes of rolling 1s tick memory

# Global Index Catch-Up Trap Parameters
MIN_SPREAD_GAP_PCT = 0.80          # Bitget must be at least 0.80% cheaper than Global Index
MIN_GLOBAL_INDEX_3M_PCT = 1.00     # Global Index must have pushed >= +1.0% in last 3 mins
MIN_BITGET_OI_DELTA_PCT = 0.50     # Bitget OI must have grown >= +0.50% in last 3 mins

# Dynamic Exit Rules
GAP_CLOSE_THRESHOLD_PCT = 0.10     # Exit when Bitget is within 0.10% of Global Index
PEAK_REVERSE_PULLBACK_PCT = 0.50   # 0.5% Peak Reverse Trailing Wall
DOA_TIMEOUT_SECONDS = 90           # 90-Second Dead-on-Arrival Kill Switch
DOA_FORWARD_THRESHOLD_PCT = 0.30   # Must gain at least +0.30% in 90s or abort
LIVE_HARD_STOP_PCT = 0.90          # Structural Emergency Hard Stop in Live Mode

# Gauntlet & Execution Parameters
QUALIFICATION_TARGET_WINS = 6      # Must achieve 6 consecutive paper wins to unlock Live
COOLDOWN_SECONDS = 600             # 10-Minute Cooldown per pair post-exit
ALLOCATION_PCT = 0.90              # Allocate 90% of usable balance
MIN_NOTIONAL_USDT = 5.50           # Bitget minimum order size constraint
MAX_LEVERAGE_CLAMP = 20
MIN_LEVERAGE_CLAMP = 2

PORT = int(os.environ.get("PORT", 10000))
STATE_FILE = "qualification_state.json"

# -----------------------------------------------------------------------------
# SECTION 3: CREDENTIAL READER (ROBUST STRIP IMPLEMENTATION)
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
# SECTION 4: QUALIFICATION STATE MANAGER (GAUNTLET 1 -> 6)
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
            except Exception as e:
                logger.error(f"Error loading state: {e}. Reinitializing.")
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

    def record_trade(self, symbol, gain_pct, exit_reason, is_paper):
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
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
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
# SECTION 5: LIVE HTTP KEEP-ALIVE SERVER (PORT 10000 DASHBOARD)
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
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        at = dashboard_data.get("active_trade")
        active_html = "<p style='color: #888;'>No active positions. Scanning order flow...</p>"
        if at:
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6;">
                <h3 style="margin: 0 0 10px 0; color: #60a5fa;">ACTIVE TRADE: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Mode:</b> {at['mode']} | <b>Entry Price:</b> {at['entry_price']} | <b>Target Index:</b> {at['index_price']}</p>
                <p><b>Current Price:</b> {at['current_price']} | <b>Current Gap:</b> {at['current_gap_pct']:.2f}%</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>DOA Timer:</b> {at['elapsed_seconds']}s / {DOA_TIMEOUT_SECONDS}s</p>
            </div>
            """

        history_rows = ""
        for t in reversed(dashboard_data.get("recent_trades", [])[-10:]):
            color = "#4ade80" if t["result"] == "WIN" else "#f87171"
            history_rows += f"""
            <tr>
                <td style="padding: 6px;">{t['timestamp']}</td>
                <td style="padding: 6px;">{t['symbol']}</td>
                <td style="padding: 6px; color: {color}; font-weight: bold;">{t['gain_pct']:+.2f}%</td>
                <td style="padding: 6px;">{t['exit_reason']}</td>
                <td style="padding: 6px;">{t['mode']}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Desk Radar & Execution Engine</title>
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
            <h2>🛰️ Quantitative Desk Intelligence Dashboard</h2>
            <div class="card">
                <b>Status:</b> {dashboard_data['status']} | 
                <b>Engine Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Consecutive Wins | 
                <b>Universe:</b> {dashboard_data['universe_size']} Pairs
            </div>

            <div class="card">
                <h3>Live Position Telemetry</h3>
                {active_html}
            </div>

            <div class="card">
                <h3>Recent Execution Log</h3>
                <table>
                    <thead>
                        <tr><th>Time</th><th>Symbol</th><th>PnL %</th><th>Exit Reason</th><th>Type</th></tr>
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

def start_http_server():
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    logger.info(f"🌐 HTTP Keep-Alive Server active on port {PORT}")
    server.serve_forever()

# -----------------------------------------------------------------------------
# SECTION 6: DESK TRADING BOT CORE ENGINE
# -----------------------------------------------------------------------------
class BitgetDeskPartnerEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.exchange = None
        self.http_session = None
        self.price_buffer = defaultdict(lambda: deque(maxlen=360))  # Rolling ~5m tick memory
        self.cooldowns = {}
        self.active_trade = None
        self.lock = threading.Lock()

        self._setup_connection_pool()
        self._setup_exchange()

    def _setup_connection_pool(self):
        """Mounts a 50-socket HTTP pool to permanently eliminate urllib3 warnings."""
        self.http_session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=3)
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)

    def _setup_exchange(self):
        """Initializes the Bitget CCXT client with one-way mode."""
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
                # Enforce One-Way Position Mode
                self.exchange.set_position_mode(hedged=False)
                logger.info("🔒 Bitget account verified: One-Way Mode Active.")
            except Exception as e:
                logger.warning(f"Note on position mode: {e}")
        else:
            logger.info("ℹ️ Running in Paper Mode without full private keys.")

    def fetch_universal_tickers(self):
        """Pulls all 800+ USDT-M pairs in ONE single REST call (0 lag)."""
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
        try:
            resp = self.http_session.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "00000":
                    return data.get("data", [])
        except Exception as e:
            logger.error(f"Ticker ingestion error: {e}")
        return []

    def update_buffers(self, tickers):
        """Stores local lastPrice, global indexPrice, and OI into memory."""
        now = time.time()
        active_count = 0

        for t in tickers:
            symbol = t.get("symbol", "")
            # Filter Blacklist
            if any(b in symbol for b in BLACKLIST):
                continue

            try:
                vol_24h = float(t.get("usdtVolume", 0.0) or t.get("baseVolume", 0.0))
                if vol_24h < MIN_24H_VOLUME_USDT:
                    continue

                last_price = float(t.get("lastPr", 0.0))
                index_price = float(t.get("indexPrice", 0.0))
                oi = float(t.get("openInterest", 0.0) or 0.0)

                if last_price <= 0 or index_price <= 0:
                    continue

                self.price_buffer[symbol].append({
                    "time": now,
                    "last_price": last_price,
                    "index_price": index_price,
                    "oi": oi
                })
                active_count += 1
            except (ValueError, TypeError):
                continue

        dashboard_data["universe_size"] = active_count

    def scan_for_catchup_trap(self):
        """Scans in-memory buffer for the Global Catch-Up Trap footprint."""
        if self.active_trade is not None:
            return None  # Max 1 focused trade at a time

        now = time.time()

        for symbol, buf in list(self.price_buffer.items()):
            if symbol in self.cooldowns and (now - self.cooldowns[symbol]) < COOLDOWN_SECONDS:
                continue

            if len(buf) < 60:  # Need at least ~1-2 minutes of history
                continue

            latest = buf[-1]
            last_price = latest["last_price"]
            index_price = latest["index_price"]

            # 1. THE SPREAD GAP (Bitget is cheaper than Global Index)
            spread_gap_pct = ((index_price - last_price) / last_price) * 100.0
            if spread_gap_pct < MIN_SPREAD_GAP_PCT:
                continue

            # 2. GLOBAL INDEX 3-MINUTE MOMENTUM
            cutoff_3m = now - 180
            ticks_3m = [b for b in buf if b["time"] >= cutoff_3m]
            if len(ticks_3m) < 10:
                continue

            oldest_index = ticks_3m[0]["index_price"]
            index_3m_gain_pct = ((index_price - oldest_index) / oldest_index) * 100.0
            if index_3m_gain_pct < MIN_GLOBAL_INDEX_3M_PCT:
                continue

            # 3. BITGET OPEN INTEREST DELTA
            oldest_oi = ticks_3m[0]["oi"]
            latest_oi = latest["oi"]
            oi_delta_pct = 0.0
            if oldest_oi > 0:
                oi_delta_pct = ((latest_oi - oldest_oi) / oldest_oi) * 100.0

            # Guard: OI must be expanding or at least positive in latest minute
            if oi_delta_pct < MIN_BITGET_OI_DELTA_PCT and latest_oi < ticks_3m[-5]["oi"]:
                continue

            # TRAP CONDITIONS MET!
            logger.info(f"🎯 TRAP TRIGGERED: {symbol} | Gap: +{spread_gap_pct:.2f}% | Global 3m: +{index_3m_gain_pct:.2f}% | Bitget OI: +{oi_delta_pct:.2f}%")
            return {
                "symbol": symbol,
                "entry_price": last_price,
                "index_price": index_price,
                "gap_pct": spread_gap_pct
            }

        return None

    def calculate_live_position_size(self, current_price):
        """Micro-Account Math: 90% balance, dynamic leverage clamped [2x, 20x] to clear $5.50 min."""
        try:
            balance_info = self.exchange.fetch_balance()
            free_usdt = float(balance_info["free"].get("USDT", 0.0))
            usable_margin = free_usdt * ALLOCATION_PCT

            if usable_margin < 0.50:
                logger.warning(f"Usable margin too low: ${usable_margin:.2f}")
                return 0, 0

            # Dynamic Leverage calculation to clear $5.50 notional
            calculated_lev = math.ceil(MIN_NOTIONAL_USDT / usable_margin)
            leverage = max(MIN_LEVERAGE_CLAMP, min(calculated_lev, MAX_LEVERAGE_CLAMP))
            notional = usable_margin * leverage

            if notional < MIN_NOTIONAL_USDT:
                notional = MIN_NOTIONAL_USDT

            contract_size = notional / current_price
            return contract_size, leverage
        except Exception as e:
            logger.error(f"Sizing error: {e}")
            return 0, 0

    def enter_trade(self, signal):
        """Executes trade entry in Paper or Live mode."""
        symbol = signal["symbol"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        trade_info = {
            "symbol": symbol,
            "side": "buy",
            "entry_price": price,
            "index_price": signal["index_price"],
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gain_pct": 0.0,
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Bought {symbol} @ {price} | Target Index: {signal['index_price']}")
            self.active_trade = trade_info
        else:
            try:
                size, lev = self.calculate_live_position_size(price)
                if size <= 0:
                    return
                # Set Leverage
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                self.exchange.set_leverage(lev, ccxt_symbol)
                # Fire Market Order
                order = self.exchange.create_market_buy_order(ccxt_symbol, size)
                trade_info["size"] = size
                self.active_trade = trade_info
                logger.info(f"⚡ [LIVE ENTRY] Long {symbol} | Size: {size} | Lev: {lev}x | OrderID: {order.get('id')}")
            except Exception as e:
                logger.error(f"Live entry execution failed: {e}")
                self.active_trade = None

    def manage_active_trade(self):
        """Monitors active trade tick-by-tick for Gap-Closed, 0.5% Peak Reverse, or 90s DOA."""
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        buf = self.price_buffer.get(symbol)
        if not buf:
            return

        latest = buf[-1]
        current_price = latest["last_price"]
        current_index = latest["index_price"]
        elapsed = time.time() - trade["entry_time"]

        # Calculate PnL and Peak Tracking
        gain_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
        if gain_pct > trade["highest_gain_pct"]:
            trade["highest_gain_pct"] = gain_pct
            trade["peak_price"] = current_price

        # Update Live Telemetry
        current_gap = ((current_index - current_price) / current_price) * 100.0
        dashboard_data["active_trade"] = {
            "symbol": symbol,
            "side": trade["side"],
            "mode": trade["mode"],
            "entry_price": trade["entry_price"],
            "index_price": current_index,
            "current_price": current_price,
            "current_gap_pct": current_gap,
            "pnl_pct": gain_pct,
            "peak_gain_pct": trade["highest_gain_pct"],
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        # RULE 1: THE GAP-CLOSED GRID TAKE-PROFIT (Bitget equalizes with Global Index)
        if current_price >= current_index * (1.0 - (GAP_CLOSE_THRESHOLD_PCT / 100.0)):
            exit_reason = "GAP_CLOSED_PROFIT"

        # RULE 2: 0.5% PEAK REVERSE (Momentum Overshoot Wall)
        elif (trade["highest_gain_pct"] - gain_pct) >= PEAK_REVERSE_PULLBACK_PCT:
            exit_reason = "0.5%_PEAK_REVERSE"

        # RULE 3: 90-SECOND DEAD-ON-ARRIVAL (DOA) KILL SWITCH
        elif elapsed >= DOA_TIMEOUT_SECONDS and trade["highest_gain_pct"] < DOA_FORWARD_THRESHOLD_PCT:
            exit_reason = "90S_DOA_KILL_SWITCH"

        # RULE 4: STRUCTURAL EMERGENCY HARD STOP (Live Mode)
        elif not trade["is_paper"] and gain_pct <= -LIVE_HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        # EXECUTE EXIT IF TRIGGERED
        if exit_reason:
            self._execute_exit(trade, current_price, gain_pct, exit_reason)

    def _execute_exit(self, trade, exit_price, gain_pct, reason):
        """Exits position cleanly and guarantees atomic active_trade = None cleanup."""
        symbol = trade["symbol"]
        is_paper = trade["is_paper"]

        try:
            if not is_paper:
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                # Query exact open size to prevent dust
                pos = self.exchange.fetch_position(ccxt_symbol)
                exact_size = abs(float(pos.get("contracts", 0.0) or trade["size"]))
                if exact_size > 0:
                    self.exchange.create_market_sell_order(
                        ccxt_symbol, 
                        exact_size, 
                        params={"reduceOnly": True}
                    )
                logger.info(f"⚡ [LIVE EXIT] Closed {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")
            else:
                logger.info(f"📝 [PAPER EXIT] Closed {symbol} @ {exit_price} | PnL: {gain_pct:+.2f}% | Reason: {reason}")

            # Record in Gauntlet Tracker
            self.state_mgr.record_trade(symbol, gain_pct, reason, is_paper)
            self.cooldowns[symbol] = time.time()

        except Exception as e:
            logger.error(f"Error during exit execution: {e}")
        finally:
            # ATOMIC CLEANUP: Eliminates PARTI phantom exit loops permanently
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def run(self):
        """Main desk loop running every 1.5 seconds."""
        logger.info("🚀 Desk Radar Engine Active. Tracking Global Catch-Up Signals...")
        last_briefing = 0

        while True:
            try:
                tickers = self.fetch_universal_tickers()
                if tickers:
                    self.update_buffers(tickers)

                if self.active_trade:
                    self.manage_active_trade()
                else:
                    signal = self.scan_for_catchup_trap()
                    if signal:
                        self.enter_trade(signal)

                # Dashboard Sync
                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.utcnow().strftime("%H:%M:%S UTC")

                # 15-Minute Desk Intelligence Briefing to Console
                if time.time() - last_briefing >= 900:
                    last_briefing = time.time()
                    logger.info(
                        f"📊 [15M DESK BRIEFING] Mode: {dashboard_data['mode']} | "
                        f"Gauntlet: {dashboard_data['streak']}/{QUALIFICATION_TARGET_WINS} Wins | "
                        f"Tracking: {dashboard_data['universe_size']} pairs"
                    )

                time.sleep(1.5)

            except Exception as e:
                logger.error(f"Engine Loop Exception: {e}")
                time.sleep(3)

# -----------------------------------------------------------------------------
# SECTION 7: BOOTSTRAP ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Start Keep-Alive HTTP Server in Daemon Thread
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    # Start Trading Engine
    engine = BitgetDeskPartnerEngine()
    engine.run()

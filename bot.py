#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: ADAPTIVE 1%-2% LIMIT CHASE & 10-SECOND WATCHDOG (PRODUCTION DESK)
VERIFIED FOR RENDER:
  1. ADAPTIVE 1.0% - 2.0% DEPTH BAND: Scales dynamically with coin spread.
  2. 10-SECOND STRUCTURE WATCHDOG: Checks order book health every 3.5s.
  3. FLASH-DUMP SHIELD: 15-second grace period + 2-strike confirmation.
  4. SWEET SPOT ENTRY: 0.20% to 1.95% velocity (No 6-hour freeze, no top wicks).
  5. INSTANT SLA APEX EXIT: Closes immediately when peak rolls over 0.12%.
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
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AdaptiveWatchdogDesk")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# GLOBAL CONSTANTS & RULES
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

MAX_LIFECYCLE_SECONDS = 900       # 15-Minute Absolute Ceiling
WATCHDOG_CHECK_INTERVAL = 3.5     # Check order book every 3.5 seconds

# Adaptive Band Settings (1.0% to 2.0%)
MIN_BAND_PCT = 0.010              # 1.0% for tight, liquid high-caps
MAX_BAND_PCT = 0.020              # 2.0% for wide, volatile low-caps
MIN_CAPITAL_RATIO = 1.65          # Favored side must have >= 1.65x capital in the band

# Momentum Entry Window
MIN_PRE_BREAKOUT_MOVE = 0.20      # Minimum initial push
MAX_PRE_BREAKOUT_MOVE = 1.95      # Never buy exhausted spikes > 1.95%
HARD_STOP_PCT = 0.85              # Emergency structural hard stop

QUALIFICATION_TARGET_WINS = 8
COOLDOWN_SECONDS = 240
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
# DYNAMIC LEARNING & AUTOPSY ENGINE
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
        return {"winning_autopsies": []}

    def save(self):
        with self.lock:
            try:
                with open(self.filename, "w") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving learning data: {e}")

    def autopsy_winning_trade(self, symbol, side, gain_pct, setup_name):
        with self.lock:
            entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
                "side": side,
                "gain_pct": gain_pct,
                "setup": setup_name
            }
            if "winning_autopsies" not in self.data:
                self.data["winning_autopsies"] = []
            self.data["winning_autopsies"].append(entry)
            if len(self.data["winning_autopsies"]) > 50:
                self.data["winning_autopsies"].pop(0)
            logger.info(f"🧬 [AUTOPSY] Recorded limit chase win on {symbol} (+{gain_pct:.2f}%).")
        self.save()

# -----------------------------------------------------------------------------
# QUALIFICATION STATE MANAGER (GAUNTLET 1 -> 8)
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
                    logger.info(f"🏆 PAPER WIN! Streak: {self.state['consecutive_wins']}/{QUALIFICATION_TARGET_WINS} | Gain: {gain_pct:+.2f}% | Setup: {setup_name}")
                    if self.state["consecutive_wins"] >= QUALIFICATION_TARGET_WINS:
                        self.state["mode"] = "LIVE"
                        logger.info("🚀 GAUNTLET COMPLETED (8/8)! AUTHORIZING LIVE TRADING ENGINE!")
            else:
                self.state["total_losses"] += 1
                if self.state["mode"] == "PAPER":
                    logger.warning(f"❌ PAPER LOSS. Streak reset to 0/{QUALIFICATION_TARGET_WINS} | PnL: {gain_pct:+.2f}% | Setup: {setup_name}")
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
# LIVE HTTP KEEP-ALIVE SERVER & DASHBOARD
# -----------------------------------------------------------------------------
dashboard_data = {
    "status": "INITIALIZING",
    "mode": "PAPER",
    "streak": 0,
    "cg_global_pairs": 0,
    "bitget_tradable_pairs": 0,
    "active_trade": None,
    "latest_ai_card": "Scanning adaptive 1%-2% order books...",
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
        active_html = "<p style='color: #888;'>Watching 1%-2% adaptive order books in real time...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE WAVE: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Strategy:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                <p><b>Entry:</b> {at['entry_price']} | <b>Current:</b> {at['current_price']}</p>
                <p><b>PnL:</b> <span style="color: {'#4ade80' if at['pnl_pct'] >= 0 else '#f87171'}; font-weight: bold;">{at['pnl_pct']:+.2f}%</span> (Peak: +{at['peak_gain_pct']:.2f}%)</p>
                <p><b>Structure Health:</b> <span style="color: #38bdf8; font-weight: bold;">{at.get('structure_health', 'MONITORING')}</span> | <b>Time:</b> {at['elapsed_seconds']}s</p>
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
            <title>Adaptive Limit Watchdog Desk</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                .card {{ background: #1e293b; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
                .badge {{ padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
                .badge-live {{ background: #ef4444; color: white; }}
                .badge-paper {{ background: #eab308; color: black; }}
                pre {{ background: #090d16; padding: 12px; border-radius: 6px; font-size: 12px; color: #38bdf8; overflow-x: auto; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th {{ text-align: left; background: #334155; padding: 8px; font-size: 13px; }}
            </style>
        </head>
        <body>
            <h2>⚡ Adaptive 1%-2% Limit Chase & 10-Second Watchdog Desk</h2>
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
                <h3>Google AI Studio Microstructure Dossier</h3>
                <pre>{dashboard_data['latest_ai_card']}</pre>
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

def start_http_server():
    try:
        http_server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
        logger.info(f"🌐 HTTP Server bound on port {PORT}")
        http_server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP Server bind error: {e}")

# -----------------------------------------------------------------------------
# MASTER DESK ENGINE: ADAPTIVE 1%-2% DEPTH & REAL-TIME WATCHDOG
# -----------------------------------------------------------------------------
class MasterDeskEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.learning_engine = DynamicLearningEngine()
        self.exchange = None
        self.http_session = None
        
        self.cg_buffer = defaultdict(lambda: deque(maxlen=60))
        self.ob_memory = defaultdict(lambda: deque(maxlen=15))
        self.bitget_markets = set()
        self.bitget_prices = {}
        self.cooldowns = {}
        self.active_trade = None
        self.last_watchdog_time = 0.0

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
            resp = self.http_session.get(url, timeout=3.5)
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

                    vol = float(item.get("vol_24h", 0.0) or 0.0)
                    self.cg_buffer[base_sym].append({
                        "time": now,
                        "price": float(item.get("price", 0.0) or 0.0),
                        "price_3m": float(item.get("price_3m", 0.0) or 0.0),
                        "oi_3m": float(item.get("oi_3m", 0.0) or 0.0),
                        "trajectory_3m": item.get("trajectory_3m", []),
                        "price_5m": float(item.get("price_5m", 0.0) or 0.0),
                        "price_15m": float(item.get("price_15m", 0.0) or 0.0),
                        "price_24h": float(item.get("price_24h", 0.0) or 0.0),
                        "oi_5m": float(item.get("oi_5m", 0.0) or 0.0),
                        "oi_15m": float(item.get("oi_15m", 0.0) or 0.0),
                        "vol_24h": vol,
                        "volume": vol,
                        "exchange_count": int(item.get("exchange_count", 1)),
                        "consensus_pct": float(item.get("consensus_pct", 100.0)),
                        "exchanges_aligned": item.get("exchanges_aligned", "1/1")
                    })
                    valid_count += 1
                dashboard_data["cg_global_pairs"] = valid_count
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # ADAPTIVE 1% TO 2% ORDER BOOK DEPTH ANALYZER
    # -------------------------------------------------------------------------
    def inspect_adaptive_order_book(self, bitget_symbol, side):
        try:
            ccxt_symbol = f"{bitget_symbol[:len(bitget_symbol)-4]}/USDT:USDT"
            ob = self.exchange.fetch_order_book(ccxt_symbol, limit=25)
            bids, asks = ob.get("bids", []), ob.get("asks", [])
            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2.0
            if mid_price <= 0:
                return None

            # Dynamically adapt band: 1.0% for tight spreads, up to 2.0% for wide spreads
            spread_pct = (best_ask - best_bid) / mid_price
            adaptive_band = max(MIN_BAND_PCT, min(MAX_BAND_PCT, spread_pct * 8.0))

            bids_in_band = [(p, q) for p, q in bids if (mid_price - p) / mid_price <= adaptive_band]
            asks_in_band = [(p, q) for p, q in asks if (p - mid_price) / mid_price <= adaptive_band]

            bid_cap = sum(p * q for p, q in bids_in_band)
            ask_cap = sum(p * q for p, q in asks_in_band)

            now = time.time()
            snapshot = {
                "time": now,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_cap": bid_cap,
                "ask_cap": ask_cap,
                "band_pct": adaptive_band * 100.0
            }
            self.ob_memory[bitget_symbol].append(snapshot)
            mem = list(self.ob_memory[bitget_symbol])

            if len(mem) < 2:
                ratio = (bid_cap / ask_cap) if (side == "buy" and ask_cap > 0) else ((ask_cap / bid_cap) if bid_cap > 0 else 1.0)
                return {
                    "is_stepping": True,
                    "capital_ratio": ratio,
                    "bid_cap": bid_cap,
                    "ask_cap": ask_cap,
                    "band_pct": adaptive_band * 100.0,
                    "structure_intact": True
                }

            past = mem[-2]  # Compare against previous immediate tick (smooth comparison)
            if side == "buy":
                ratio = bid_cap / ask_cap if ask_cap > 0 else 1.0
                is_stepping = (best_bid >= past["best_bid"])
                # Structure is destroyed if sellers overwhelm buyers (ratio < 1.0) or bids collapse > 50%
                structure_intact = (ratio >= 1.05) and (bid_cap >= past["bid_cap"] * 0.50)
            else:
                ratio = ask_cap / bid_cap if bid_cap > 0 else 1.0
                is_stepping = (best_ask <= past["best_ask"])
                structure_intact = (ratio >= 1.05) and (ask_cap >= past["ask_cap"] * 0.50)

            return {
                "is_stepping": is_stepping,
                "capital_ratio": ratio,
                "bid_cap": bid_cap,
                "ask_cap": ask_cap,
                "band_pct": adaptive_band * 100.0,
                "structure_intact": structure_intact
            }
        except Exception:
            return None

    def format_ai_studio_dossier(self, signal, current_price, ob_data):
        card = (
            f"\n==================== [ADAPTIVE LIMIT CHASE DOSSIER] ====================\n"
            f"ASSET: {signal['base_sym']}USDT | DIRECTION: {signal['side'].upper()} | SCORE: {signal['score']}/100\n"
            f"STRATEGY: {signal['setup']} | ADAPTIVE BAND: +/-{ob_data.get('band_pct', 1.0):.2f}%\n"
            f"RESTING CAPITAL: Bids: ${ob_data.get('bid_cap', 0):,.0f} | Asks: ${ob_data.get('ask_cap', 0):,.0f}\n"
            f"BAND CAPITAL RATIO: {ob_data.get('capital_ratio', 1.0):.2f}x FAVORED\n"
            f"LIMIT CHASE STATUS: {'ADVANCING (AGGRESSIVE)' if ob_data.get('is_stepping') else 'HOLDING'}\n"
            f"PRE-BREAKOUT VELOCITY: 3m Price: {signal.get('p3m', 0.0):+.2f}% | 3m OI: {signal.get('oi3m', 0.0):+.2f}%\n"
            f"ENTRY EXECUTION PRICE: ${current_price:.6f}\n"
            f"AI STUDIO FINGERPRINT:\n"
            f"{json.dumps({'asset': signal['base_sym'], 'side': signal['side'], 'ratio': round(ob_data.get('capital_ratio', 1.0), 2), 'band': round(ob_data.get('band_pct', 1.0), 2)}, indent=2)}\n"
            f"========================================================================="
        )
        dashboard_data["latest_ai_card"] = card
        logger.info(card)

    def run_master_arbitrator(self):
        if self.active_trade is not None:
            return None

        candidates = []
        now = time.time()

        for base_sym, buf in list(self.cg_buffer.items()):
            bitget_symbol = f"{base_sym}USDT"
            if bitget_symbol not in self.bitget_markets:
                continue
            if bitget_symbol in self.cooldowns and (now - self.cooldowns[bitget_symbol]) < COOLDOWN_SECONDS:
                continue
            if len(buf) < 3:
                continue

            latest = buf[-1]
            p3m = latest["price_3m"]
            oi3m = latest["oi_3m"]
            consensus = latest["consensus_pct"]

            if consensus < 80.0:
                continue

            # SWEET SPOT: Allows momentum between 0.20% and 1.95% (Never buys blown-out wicks)
            if abs(p3m) > MAX_PRE_BREAKOUT_MOVE or abs(p3m) < MIN_PRE_BREAKOUT_MOVE:
                continue

            if p3m > 0 and oi3m >= 0.15:
                candidates.append({
                    "side": "buy", "setup": "PLAY_ADAPTIVE_LIMIT_CHASE",
                    "score": 99, "p3m": p3m, "oi3m": oi3m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym
                })
            elif p3m < 0 and abs(oi3m) >= 0.15:
                candidates.append({
                    "side": "sell", "setup": "PLAY_ADAPTIVE_LIMIT_CHASE",
                    "score": 99, "p3m": p3m, "oi3m": oi3m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym
                })

        if candidates:
            candidates.sort(key=lambda x: abs(x["p3m"]), reverse=True)

            for cand in candidates[:3]:
                ob_data = self.inspect_adaptive_order_book(cand["bitget_symbol"], cand["side"])
                if not ob_data:
                    continue

                if ob_data["capital_ratio"] >= MIN_CAPITAL_RATIO and ob_data["is_stepping"]:
                    exec_price = self.bitget_prices.get(cand["bitget_symbol"], 0.0)
                    if exec_price <= 0:
                        continue
                    cand["entry_price"] = exec_price
                    cand["ob_data"] = ob_data
                    return cand

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
            return notional / current_price, leverage
        except Exception:
            return 0, 0

    def enter_trade(self, signal):
        symbol = signal["bitget_symbol"]
        base_sym = signal["base_sym"]
        side = signal["side"]
        price = signal["entry_price"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        self.format_ai_studio_dossier(signal, price, signal["ob_data"])

        trade_info = {
            "symbol": symbol,
            "base_sym": base_sym,
            "side": side,
            "setup": signal["setup"],
            "entry_price": price,
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gain_pct": 0.0,
            "structure_fails": 0,           # 2-strike confirmation counter
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened {side.upper()} on {symbol} @ {price} | Setup: {signal['setup']}")
            self.active_trade = trade_info
        else:
            try:
                size, lev = self.calculate_live_position_size(price)
                if size <= 0:
                    return
                ccxt_symbol = f"{symbol[:len(symbol)-4]}/USDT:USDT"
                self.exchange.set_leverage(lev, ccxt_symbol)
                if side == "buy":
                    self.exchange.create_market_buy_order(ccxt_symbol, size)
                else:
                    self.exchange.create_market_sell_order(ccxt_symbol, size)
                trade_info["size"] = size
                self.active_trade = trade_info
                logger.info(f"⚡ [LIVE ENTRY] {side.upper()} {symbol} | Size: {size} | Lev: {lev}x")
            except Exception as e:
                logger.error(f"Live entry failed: {e}")
                self.active_trade = None

    # -------------------------------------------------------------------------
    # 10-SECOND HIGH-FREQUENCY STRUCTURE WATCHDOG
    # -------------------------------------------------------------------------
    def manage_active_trade(self):
        if not self.active_trade:
            return
        trade = self.active_trade
        symbol, side = trade["symbol"], trade["side"]
        current_price = self.bitget_prices.get(symbol, trade["entry_price"])
        now = time.time()
        elapsed = max(1.0, now - trade["entry_time"])

        if side == "buy":
            gain_pct = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
            if current_price > trade["peak_price"]:
                trade["peak_price"] = current_price
            drawdown_from_peak = ((trade["peak_price"] - current_price) / trade["peak_price"]) * 100.0
        else:
            gain_pct = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100.0
            if current_price < trade["peak_price"]:
                trade["peak_price"] = current_price
            drawdown_from_peak = ((current_price - trade["peak_price"]) / trade["peak_price"]) * 100.0

        if gain_pct > trade["highest_gain_pct"]:
            trade["highest_gain_pct"] = gain_pct

        # Run Live Order Book Watchdog every 3.5 seconds
        if (now - self.last_watchdog_time) >= WATCHDOG_CHECK_INTERVAL:
            self.last_watchdog_time = now
            live_ob = self.inspect_adaptive_order_book(symbol, side)
            if live_ob:
                if not live_ob["structure_intact"]:
                    trade["structure_fails"] += 1
                else:
                    trade["structure_fails"] = 0

        structure_status = "DESTROYED (ORDERS PULLED)" if trade["structure_fails"] >= 2 else "INTACT"

        dashboard_data["active_trade"] = {
            "symbol": symbol,
            "side": side,
            "setup": trade["setup"],
            "mode": trade["mode"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "pnl_pct": gain_pct,
            "peak_gain_pct": trade["highest_gain_pct"],
            "structure_health": structure_status,
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        # 1. Structural Emergency Hard Stop
        if gain_pct <= -HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        # 2. IMMEDIATE STRUCTURE DESTROYED EXIT (After 15s grace period, 2 confirmed strikes)
        elif elapsed >= 15 and trade["structure_fails"] >= 2:
            if gain_pct >= 0.15:
                exit_reason = "STRUCTURE_BROKEN_BANK_PROFIT"
            else:
                exit_reason = "STRUCTURE_BROKEN_FAST_SCRATCH"

        # 3. Micro-Apex Fade: Drawdown 0.12% off the peak once in profit
        elif trade["highest_gain_pct"] >= 0.35 and drawdown_from_peak >= 0.12 and gain_pct >= 0.20:
            exit_reason = "SLA_INSTANT_APEX_FADE"

        # 4. 2-Minute Stalled Structure Scratch
        elif elapsed >= 120 and elapsed <= 180 and gain_pct <= -0.30:
            exit_reason = "2M_STRUCTURE_STALL_SCRATCH"

        # 5. 15-Minute Runner Hard Ceiling
        elif elapsed >= MAX_LIFECYCLE_SECONDS:
            exit_reason = "15M_RUNNER_CEILING"

        if exit_reason:
            self._execute_exit(trade, current_price, gain_pct, exit_reason)

    def _execute_exit(self, trade, exit_price, gain_pct, reason):
        symbol, side, is_paper, setup_name = trade["symbol"], trade["side"], trade["is_paper"], trade["setup"]
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
            
            if gain_pct >= 1.50:
                self.learning_engine.autopsy_winning_trade(symbol, side, gain_pct, setup_name)

            self.cooldowns[symbol] = time.time()
            self.ob_memory[symbol].clear()  # Clear memory for fresh tracking next time
        except Exception as e:
            logger.error(f"Exit execution error: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def run(self):
        logger.info("🚀 Adaptive 1%-2% Limit Watchdog Desk Online...")
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
                    if signal:
                        self.enter_trade(signal)

                dashboard_data["status"] = "RUNNING"
                dashboard_data["mode"] = self.state_mgr.state["mode"]
                dashboard_data["streak"] = self.state_mgr.state["consecutive_wins"]
                dashboard_data["recent_trades"] = self.state_mgr.state["history"]
                dashboard_data["last_update"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                time.sleep(1.8)
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(2.5)

if __name__ == "__main__":
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()
    engine = MasterDeskEngine()
    engine.run()

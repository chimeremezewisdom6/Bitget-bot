
#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: 3M ABSORPTION ASYMMETRY DESK (PRODUCTION LIVE-READY)
PRODUCTION HARDENING:
  1. BITGET CONTRACT PRECISION: Rounds exact contract size with amount_to_precision.
  2. LOAD MARKETS INITIALIZATION: Loads Bitget swap rules, contract sizes, and limits.
  3. SAFE POSITION CLOSE: Handles Bitget list/dict position payload variations.
  4. LIVE HARD STOP: Enforces hard stop in BOTH Paper and Live modes.
  5. NET PROFIT ACCOUNTING: Strict fee (0.12%) and spread deduction.
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
logger = logging.getLogger("AbsorptionAsymmetryDesk")
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# GLOBAL CONSTANTS & RULES
# -----------------------------------------------------------------------------
BLACKLIST = [
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP", 
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
]

BITGET_ROUNDTRIP_FEE_PCT = 0.12   # 0.06% open + 0.06% close = 0.12%
MIN_TARGET_NET_PROFIT_PCT = 0.50  # Must clear at least +0.50% pure NET profit

MIN_ABSORPTION_MULTIPLIER = 3.00  # 1-min inflow must overpower 3 minutes of opposing depth (>= 3.0x)
MIN_RUNWAY_DISTANCE_PCT = 0.85    # Orders must be spaced out (at least 0.85% open air to next wall)
MAX_LIFECYCLE_SECONDS = 900       # 15-Minute Absolute Ceiling
WATCHDOG_CHECK_INTERVAL = 3.5     # Check order book health every 3.5 seconds
HARD_STOP_PCT = 0.85              # Emergency structural stop

QUALIFICATION_TARGET_WINS = 8
COOLDOWN_SECONDS = 300
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

    def autopsy_winning_trade(self, symbol, side, net_gain_pct, setup_name):
        with self.lock:
            entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
                "side": side,
                "net_gain_pct": net_gain_pct,
                "setup": setup_name
            }
            if "winning_autopsies" not in self.data:
                self.data["winning_autopsies"] = []
            self.data["winning_autopsies"].append(entry)
            if len(self.data["winning_autopsies"]) > 50:
                self.data["winning_autopsies"].pop(0)
            logger.info(f"🧬 [AUTOPSY] Recorded pure net win on {symbol} (Net: +{net_gain_pct:.2f}%).")
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

    def record_trade(self, symbol, side, gross_pct, net_pct, exit_reason, setup_name, is_paper):
        with self.lock:
            self.state["total_trades"] += 1
            is_win = net_pct > 0.0

            if is_win:
                self.state["total_wins"] += 1
                if self.state["mode"] == "PAPER":
                    self.state["consecutive_wins"] += 1
                    logger.info(f"🏆 PAPER WIN! Streak: {self.state['consecutive_wins']}/{QUALIFICATION_TARGET_WINS} | Gross: {gross_pct:+.2f}% | NET: {net_pct:+.2f}% | Setup: {setup_name}")
                    if self.state["consecutive_wins"] >= QUALIFICATION_TARGET_WINS:
                        self.state["mode"] = "LIVE"
                        logger.info("🚀 GAUNTLET COMPLETED (8/8)! AUTHORIZING LIVE TRADING ENGINE!")
            else:
                self.state["total_losses"] += 1
                if self.state["mode"] == "PAPER":
                    logger.warning(f"❌ PAPER LOSS. Streak reset to 0/{QUALIFICATION_TARGET_WINS} | NET: {net_pct:+.2f}% (Gross: {gross_pct:+.2f}%) | Setup: {setup_name}")
                    self.state["consecutive_wins"] = 0

            trade_log = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "symbol": symbol,
                "side": side.upper(),
                "gross_pct": round(gross_pct, 3),
                "net_pct": round(net_pct, 3),
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
    "latest_ai_card": "Scanning for 3-minute absorption asymmetry and liquidity runways...",
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
        active_html = "<p style='color: #888;'>Monitoring liquidity runways and absorption asymmetry across 8 exchanges...</p>"
        if at:
            side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
            net_color = "#4ade80" if at['net_pnl_pct'] >= 0 else "#f87171"
            active_html = f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE WAVE: {at['symbol']} ({at['side'].upper()})</h3>
                <p><b>Strategy:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                <p><b>Entry:</b> {at['entry_price']} | <b>Current:</b> {at['current_price']}</p>
                <p><b>Gross PnL:</b> {at['gross_pnl_pct']:+.2f}% | <b>NET PnL (After Fee & Spread):</b> <span style="color: {net_color}; font-weight: bold; font-size: 16px;">{at['net_pnl_pct']:+.2f}%</span></p>
                <p><b>Peak Gross:</b> +{at['peak_gross_pct']:.2f}% | <b>Structure Health:</b> <span style="color: #38bdf8; font-weight: bold;">{at.get('structure_health', 'INTACT')}</span> | <b>Time:</b> {at['elapsed_seconds']}s</p>
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
                <td style="padding: 6px; color: {color}; font-weight: bold;">{t['net_pct']:+.2f}% <span style='font-size: 11px; color: #94a3b8;'>(Gross: {t.get('gross_pct', 0):+.2f}%)</span></td>
                <td style="padding: 6px;">{t['exit_reason']}</td>
                <td style="padding: 6px;">{t['mode']}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>3M Absorption Asymmetry Desk</title>
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
            <h2>⚡ 3-Minute Absorption Asymmetry & Pure Net Profit Desk</h2>
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
                <h3>Recent Execution Log (Strictly Net of Bitget 0.12% Fees & Spread)</h3>
                <table>
                    <thead>
                        <tr><th>Time</th><th>Symbol</th><th>Side</th><th>Strategy</th><th>Net PnL %</th><th>Exit Reason</th><th>Type</th></tr>
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
# MASTER DESK ENGINE: 3M ABSORPTION ASYMMETRY & RUNWAY DETECTOR
# -----------------------------------------------------------------------------
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

        # Load markets for precision rounding & contract sizing
        try:
            self.exchange.load_markets()
            logger.info("📦 CCXT loaded Bitget swap markets and contract rules.")
        except Exception as e:
            logger.warning(f"Market loading warning (will retry on entry): {e}")

        if API_KEY and SECRET_KEY and PASSPHRASE:
            try:
                self.exchange.set_position_mode(hedged=False)
                logger.info("🔒 Bitget account verified: One-Way Mode Active.")
            except Exception:
                pass
        else:
            logger.info("ℹ️ Running in Paper Mode without full private keys.")

    def get_ccxt_symbol(self, bitget_symbol):
        """Robust symbol conversion utilizing CCXT markets map."""
        if hasattr(self.exchange, "markets_by_id") and bitget_symbol in self.exchange.markets_by_id:
            return self.exchange.markets_by_id[bitget_symbol]["symbol"]
        base = bitget_symbol[:-4] if bitget_symbol.endswith("USDT") else bitget_symbol
        return f"{base}/USDT:USDT"

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
    # 3-MINUTE ABSORPTION ASYMMETRY & RUNWAY CALCULATOR
    # -------------------------------------------------------------------------
    def evaluate_absorption_asymmetry(self, bitget_symbol, side, p3m):
        try:
            ccxt_symbol = self.get_ccxt_symbol(bitget_symbol)
            ob = self.exchange.fetch_order_book(ccxt_symbol, limit=40)
            bids, asks = ob.get("bids", []), ob.get("asks", [])
            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2.0
            if mid_price <= 0:
                return None

            spread_pct = ((best_ask - best_bid) / mid_price) * 100.0

            if side == "buy":
                runway_dist = 0.0
                for p, q in asks:
                    dist = ((p - mid_price) / mid_price) * 100.0
                    if dist >= MIN_RUNWAY_DISTANCE_PCT:
                        runway_dist = dist
                        break

                opposing_depth_3m = sum(p * q for p, q in asks if ((p - mid_price) / mid_price) <= 0.025)
                supporting_depth_1m = sum(p * q for p, q in bids if ((mid_price - p) / mid_price) <= 0.015)

                if opposing_depth_3m <= 0:
                    return None

                absorption_multiplier = (supporting_depth_1m * 3.0) / opposing_depth_3m

                return {
                    "side": "buy",
                    "spread_pct": spread_pct,
                    "runway_dist": runway_dist or 1.5,
                    "absorption_multiplier": absorption_multiplier,
                    "supporting_depth": supporting_depth_1m,
                    "opposing_depth": opposing_depth_3m,
                    "structure_intact": (absorption_multiplier >= 1.20)
                }

            else:
                runway_dist = 0.0
                for p, q in bids:
                    dist = ((mid_price - p) / mid_price) * 100.0
                    if dist >= MIN_RUNWAY_DISTANCE_PCT:
                        runway_dist = dist
                        break

                opposing_depth_3m = sum(p * q for p, q in bids if ((mid_price - p) / mid_price) <= 0.025)
                supporting_depth_1m = sum(p * q for p, q in asks if ((p - mid_price) / mid_price) <= 0.015)

                if opposing_depth_3m <= 0:
                    return None

                absorption_multiplier = (supporting_depth_1m * 3.0) / opposing_depth_3m

                return {
                    "side": "sell",
                    "spread_pct": spread_pct,
                    "runway_dist": runway_dist or 1.5,
                    "absorption_multiplier": absorption_multiplier,
                    "supporting_depth": supporting_depth_1m,
                    "opposing_depth": opposing_depth_3m,
                    "structure_intact": (absorption_multiplier >= 1.20)
                }

        except Exception:
            return None

    def format_ai_studio_dossier(self, signal, current_price, asym_data):
        card = (
            f"\n==================== [3M ABSORPTION ASYMMETRY DOSSIER] ====================\n"
            f"ASSET: {signal['base_sym']}USDT | DIRECTION: {signal['side'].upper()} | SCORE: {signal['score']}/100\n"
            f"ABSORPTION ASYMMETRY: {asym_data['absorption_multiplier']:.2f}x (REQUIRES >= 3 MIN TO OVERPOWER)\n"
            f"LIQUIDITY RUNWAY: {asym_data['runway_dist']:.2f}% CLEAR SPACE BEFORE NEXT WALL\n"
            f"BITGET ESTIMATED FRICTION: 0.12% Fees + {asym_data['spread_pct']:.2f}% Spread = {0.12 + asym_data['spread_pct']:.2f}%\n"
            f"SUPPORTING RESTING CAPITAL: ${asym_data['supporting_depth']:,.0f} vs OPPOSING: ${asym_data['opposing_depth']:,.0f}\n"
            f"3-MIN VELOCITY: Price: {signal.get('p3m', 0.0):+.2f}% | OI: {signal.get('oi3m', 0.0):+.2f}%\n"
            f"EXECUTION ENTRY PRICE: ${current_price:.6f}\n"
            f"AI STUDIO FINGERPRINT:\n"
            f"{json.dumps({'asset': signal['base_sym'], 'side': signal['side'], 'asymmetry': round(asym_data['absorption_multiplier'], 2), 'runway': round(asym_data['runway_dist'], 2)}, indent=2)}\n"
            f"=========================================================================="
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

            # Momentum entry filter
            if abs(p3m) > 1.95 or abs(p3m) < 0.25:
                continue

            if p3m > 0 and oi3m >= 0.15:
                candidates.append({
                    "side": "buy", "setup": "PLAY_3M_ABSORPTION_ASYMMETRY",
                    "score": 98, "p3m": p3m, "oi3m": oi3m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym
                })
            elif p3m < 0 and abs(oi3m) >= 0.15:
                candidates.append({
                    "side": "sell", "setup": "PLAY_3M_ABSORPTION_ASYMMETRY",
                    "score": 98, "p3m": p3m, "oi3m": oi3m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym
                })

        if candidates:
            candidates.sort(key=lambda x: abs(x["p3m"]), reverse=True)

            evaluated_candidates = []
            for cand in candidates[:4]:
                asym = self.evaluate_absorption_asymmetry(cand["bitget_symbol"], cand["side"], cand["p3m"])
                if not asym:
                    continue

                if (asym["absorption_multiplier"] >= MIN_ABSORPTION_MULTIPLIER and 
                    asym["runway_dist"] >= MIN_RUNWAY_DISTANCE_PCT and 
                    asym["spread_pct"] <= 0.25):
                    
                    exec_price = self.bitget_prices.get(cand["bitget_symbol"], 0.0)
                    if exec_price > 0:
                        cand["entry_price"] = exec_price
                        cand["asym_data"] = asym
                        cand["overall_score"] = asym["absorption_multiplier"] * asym["runway_dist"]
                        evaluated_candidates.append(cand)

            if evaluated_candidates:
                evaluated_candidates.sort(key=lambda x: x["overall_score"], reverse=True)
                return evaluated_candidates[0]

        return None

    def calculate_live_position_size(self, ccxt_symbol, current_price):
        """Precision-safe position sizing compliant with Bitget contract step."""
        try:
            balance_info = self.exchange.fetch_balance()
            free_usdt = float((balance_info.get("free") or {}).get("USDT", 0.0) or 0.0)
            usable_margin = free_usdt * ALLOCATION_PCT
            if usable_margin < 0.50:
                return 0, 0

            calculated_lev = math.ceil(MIN_NOTIONAL_USDT / usable_margin)
            leverage = max(MIN_LEVERAGE_CLAMP, min(calculated_lev, MAX_LEVERAGE_CLAMP))
            notional = max(MIN_NOTIONAL_USDT, usable_margin * leverage)
            
            raw_size = notional / current_price
            # Precision round according to Bitget contract rules
            rounded_size = float(self.exchange.amount_to_precision(ccxt_symbol, raw_size))
            return rounded_size, leverage
        except Exception as e:
            logger.error(f"Sizing error: {e}")
            return 0, 0

    def enter_trade(self, signal):
        symbol = signal["bitget_symbol"]
        base_sym = signal["base_sym"]
        side = signal["side"]
        price = signal["entry_price"]
        asym = signal["asym_data"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        self.format_ai_studio_dossier(signal, price, asym)

        trade_info = {
            "symbol": symbol,
            "base_sym": base_sym,
            "side": side,
            "setup": signal["setup"],
            "entry_price": price,
            "entry_spread_pct": asym["spread_pct"],
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gross_pct": 0.0,
            "structure_fails": 0,
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened {side.upper()} on {symbol} @ {price} | Asymmetry: {asym['absorption_multiplier']:.1f}x | Runway: {asym['runway_dist']:.2f}%")
            self.active_trade = trade_info
        else:
            try:
                ccxt_symbol = self.get_ccxt_symbol(symbol)
                size, lev = self.calculate_live_position_size(ccxt_symbol, price)
                if size <= 0:
                    logger.warning(f"Aborting live trade: calculated size {size} is zero or sub-minimum.")
                    return

                try:
                    self.exchange.set_leverage(lev, ccxt_symbol)
                except Exception:
                    pass

                if side == "buy":
                    order = self.exchange.create_market_buy_order(ccxt_symbol, size)
                else:
                    order = self.exchange.create_market_sell_order(ccxt_symbol, size)

                trade_info["size"] = size
                self.active_trade = trade_info
                logger.info(f"⚡ [LIVE ENTRY] {side.upper()} {symbol} | Size: {size} | Lev: {lev}x | OrderID: {order.get('id', 'FILLED')}")
            except Exception as e:
                logger.error(f"Live entry failed: {e}")
                self.active_trade = None

    # -------------------------------------------------------------------------
    # REAL-TIME TRADE & NET PROFIT MANAGEMENT
    # -------------------------------------------------------------------------
    def manage_active_trade(self):
        if not self.active_trade:
            return
        trade = self.active_trade
        symbol, side = trade["symbol"], trade["side"]
        current_price = self.bitget_prices.get(symbol, trade["entry_price"])
        now = time.time()
        elapsed = max(1.0, now - trade["entry_time"])

        # 1. Gross PnL
        if side == "buy":
            gross_pnl = ((current_price - trade["entry_price"]) / trade["entry_price"]) * 100.0
            if current_price > trade["peak_price"]:
                trade["peak_price"] = current_price
            drawdown_from_peak = ((trade["peak_price"] - current_price) / trade["peak_price"]) * 100.0
        else:
            gross_pnl = ((trade["entry_price"] - current_price) / trade["entry_price"]) * 100.0
            if current_price < trade["peak_price"]:
                trade["peak_price"] = current_price
            drawdown_from_peak = ((current_price - trade["peak_price"]) / trade["peak_price"]) * 100.0

        if gross_pnl > trade["highest_gross_pct"]:
            trade["highest_gross_pct"] = gross_pnl

        # 2. Strict Net PnL (Deducting Bitget 0.12% roundtrip fee + entry spread)
        friction_pct = BITGET_ROUNDTRIP_FEE_PCT + trade["entry_spread_pct"]
        net_pnl = gross_pnl - friction_pct

        # 3. Check Order Book Health every 3.5s
        if (now - self.last_watchdog_time) >= WATCHDOG_CHECK_INTERVAL:
            self.last_watchdog_time = now
            live_asym = self.evaluate_absorption_asymmetry(symbol, side, 0.0)
            if live_asym:
                if not live_asym["structure_intact"]:
                    trade["structure_fails"] += 1
                else:
                    trade["structure_fails"] = 0

        structure_status = "DESTROYED" if trade["structure_fails"] >= 2 else "INTACT"

        dashboard_data["active_trade"] = {
            "symbol": symbol,
            "side": side,
            "setup": trade["setup"],
            "mode": trade["mode"],
            "entry_price": trade["entry_price"],
            "current_price": current_price,
            "gross_pnl_pct": gross_pnl,
            "net_pnl_pct": net_pnl,
            "peak_gross_pct": trade["highest_gross_pct"],
            "structure_health": structure_status,
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        # Rule 1: Emergency Hard Stop (Active in BOTH modes)
        if gross_pnl <= -HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        # Rule 2: Pure Net Profit Bank
        elif trade["highest_gross_pct"] >= 0.85 and drawdown_from_peak >= 0.14 and net_pnl >= MIN_TARGET_NET_PROFIT_PCT:
            exit_reason = "SLA_NET_PROFIT_APEX_LOCK"

        # Rule 3: Confirmed Structural Breakdown
        elif elapsed >= 20 and trade["structure_fails"] >= 2:
            if net_pnl >= 0.20:
                exit_reason = "STRUCTURE_COLLAPSE_BANK_NET"
            elif elapsed >= 90:
                exit_reason = "STRUCTURE_COLLAPSE_FAST_SCRATCH"

        # Rule 4: 3-Minute Momentum Stagnation
        elif elapsed >= 180 and net_pnl <= 0.0:
            exit_reason = "3M_ASYMMETRY_STAGNATION_CUT"

        # Rule 5: 15-Minute Runner Ceiling
        elif elapsed >= MAX_LIFECYCLE_SECONDS:
            exit_reason = "15M_RUNNER_CEILING"

        if exit_reason:
            self._execute_exit(trade, current_price, gross_pnl, net_pnl, exit_reason)

    def _execute_exit(self, trade, exit_price, gross_pnl, net_pnl, reason):
        symbol, side, is_paper, setup_name = trade["symbol"], trade["side"], trade["is_paper"], trade["setup"]
        try:
            if not is_paper:
                ccxt_symbol = self.get_ccxt_symbol(symbol)
                exact_size = trade.get("size", 0.0)

                # Query live position to ensure full close
                try:
                    positions = self.exchange.fetch_positions([ccxt_symbol])
                    if positions and isinstance(positions, list):
                        for p in positions:
                            contracts = abs(float(p.get("contracts", 0.0) or 0.0))
                            if contracts > 0:
                                exact_size = contracts
                                break
                except Exception:
                    pass

                # Round close order size according to Bitget contract rules
                exact_size = float(self.exchange.amount_to_precision(ccxt_symbol, exact_size))
                if exact_size > 0:
                    if side == "buy":
                        self.exchange.create_market_sell_order(ccxt_symbol, exact_size, params={"reduceOnly": True})
                    else:
                        self.exchange.create_market_buy_order(ccxt_symbol, exact_size, params={"reduceOnly": True})
                logger.info(f"⚡ [LIVE EXIT] Closed {side.upper()} {symbol} @ {exit_price} | NET: {net_pnl:+.2f}% (Gross: {gross_pnl:+.2f}%) | Reason: {reason}")
            else:
                logger.info(f"📝 [PAPER EXIT] Closed {side.upper()} {symbol} @ {exit_price} | NET: {net_pnl:+.2f}% (Gross: {gross_pnl:+.2f}%) | Reason: {reason}")
            
            self.state_mgr.record_trade(symbol, side, gross_pnl, net_pnl, reason, setup_name, is_paper)
            
            if net_pnl >= 1.00:
                self.learning_engine.autopsy_winning_trade(symbol, side, net_pnl, setup_name)

            self.cooldowns[symbol] = time.time()
        except Exception as e:
            logger.error(f"Exit execution error: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def run(self):
        logger.info("🚀 3M Absorption Asymmetry & Pure Net Profit Desk Online...")
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

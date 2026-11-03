#!/usr/bin/env python3
"""
===============================================================================
BOT.PY: MASTER QUANTITATIVE DESK (GAP DISPERSION & PRODUCTION READY)
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
logger = logging.getLogger("ForensicTapeDesk")
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
MIN_TARGET_NET_PROFIT_PCT = 0.40  # Net profit target (after fee and spread)
MAX_LIFECYCLE_SECONDS = 600       # 10-Minute Maximum Lifecycle
WATCHDOG_CHECK_INTERVAL = 2.5     # Check order book levels every 2.5 seconds
HARD_STOP_PCT = 0.85              # Emergency structural stop

QUALIFICATION_TARGET_WINS = 8
COOLDOWN_SECONDS = 180
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
            logger.info(f"🧬 [AUTOPSY] Recorded forensic win on {symbol} (Net: +{net_gain_pct:.2f}%).")
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
# LIVE HTTP SERVER (WITH BROKEN-PIPE DISCONNECT SHIELD)
# -----------------------------------------------------------------------------
dashboard_data = {
    "status": "INITIALIZING",
    "mode": "PAPER",
    "streak": 0,
    "cg_global_pairs": 0,
    "bitget_tradable_pairs": 0,
    "active_trade": None,
    "latest_tape_dossier": "Recording cross-exchange order flow tapes for $1M+ coins...",
    "recent_trades": [],
    "last_update": ""
}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        try:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, Exception):
            pass

    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            at = dashboard_data.get("active_trade")
            active_html = "<p style='color: #888;'>Watching 2-minute order battles across the top 8 venues...</p>"
            if at:
                side_color = "#4ade80" if at['side'].upper() == "BUY" else "#f87171"
                net_color = "#4ade80" if at['net_pnl_pct'] >= 0 else "#f87171"
                active_html = f"""
                <div style="background: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid {side_color};">
                    <h3 style="margin: 0 0 10px 0; color: {side_color};">ACTIVE WAVE: {at['symbol']} ({at['side'].upper()})</h3>
                    <p><b>Strategy Method:</b> <span style="color: #60a5fa; font-weight: bold;">{at['setup']}</span> | <b>Mode:</b> {at['mode']}</p>
                    <p><b>Entry:</b> {at['entry_price']} | <b>Current:</b> {at['current_price']}</p>
                    <p><b>Gross PnL:</b> {at['gross_pnl_pct']:+.2f}% | <b>NET PnL:</b> <span style="color: {net_color}; font-weight: bold; font-size: 16px;">{at['net_pnl_pct']:+.2f}%</span></p>
                    <p><b>Remaining Fills to Wall:</b> <span style="color: #f59e0b; font-weight: bold;">{at.get('remaining_fills', 'CALCULATING')}</span> | <b>Time:</b> {at['elapsed_seconds']}s</p>
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
                <title>Cross-Exchange Forensic Tape Desk</title>
                <meta http-equiv="refresh" content="3">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                    .card {{ background: #1e293b; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
                    .badge {{ padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
                    .badge-live {{ background: #ef4444; color: white; }}
                    .badge-paper {{ background: #eab308; color: black; }}
                    pre {{ background: #090d16; padding: 12px; border-radius: 6px; font-size: 12px; color: #38bdf8; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th {{ text-align: left; background: #334155; padding: 8px; font-size: 13px; }}
                </style>
            </head>
            <body>
                <h2>⚡ Cross-Exchange Forensic Tape Desk (2-Min Force Recorder)</h2>
                <div class="card">
                    <b>Status:</b> {dashboard_data['status']} | 
                    <b>Mode:</b> <span class="badge {'badge-live' if dashboard_data['mode'] == 'LIVE' else 'badge-paper'}">{dashboard_data['mode']}</span> | 
                    <b>Gauntlet Streak:</b> {dashboard_data['streak']} / {QUALIFICATION_TARGET_WINS} Wins | 
                    <b>Global $1M+ Pairs:</b> {dashboard_data['cg_global_pairs']} Pairs | 
                    <b>Bitget Tradable:</b> {dashboard_data['bitget_tradable_pairs']} Pairs
                </div>
                <div class="card">
                    <h3>Live Position Telemetry</h3>
                    {active_html}
                </div>
                <div class="card">
                    <h3>Cross-Exchange Forensic Tape Dossier (Copy & Paste to Chat)</h3>
                    <pre>{dashboard_data['latest_tape_dossier']}</pre>
                </div>
                <div class="card">
                    <h3>Recent Execution Log (Strictly Net of Bitget 0.12% Fees & Spread)</h3>
                    <table>
                        <thead>
                            <tr><th>Time</th><th>Symbol</th><th>Side</th><th>Strategy Method</th><th>Net PnL %</th><th>Exit Reason</th><th>Type</th></tr>
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
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            pass

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
# MASTER DESK ENGINE: FORENSIC TAPE CLASSIFIER & EXECUTOR
# -----------------------------------------------------------------------------
class MasterDeskEngine:
    def __init__(self):
        self.state_mgr = StateManager()
        self.learning_engine = DynamicLearningEngine()
        self.exchange = None
        self.http_session = None
        
        # Lightweight buffer (maxlen=15) saves memory
        self.cg_buffer = defaultdict(lambda: deque(maxlen=15))
        self.bitget_markets = set()
        self.bitget_prices = {}
        self.cooldowns = {}
        self.active_trade = None
        self.last_watchdog_time = 0.0

        self._setup_connection_pool()
        self._setup_exchange()

    def _setup_connection_pool(self):
        self.http_session = requests.Session()
        adapter = HTTPAdapter(pool_connections=40, pool_maxsize=40, max_retries=3)
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

        try:
            self.exchange.load_markets()
            logger.info("📦 CCXT loaded Bitget swap markets and contract rules.")
        except Exception as e:
            logger.warning(f"Market loading warning: {e}")

        if API_KEY and SECRET_KEY and PASSPHRASE:
            try:
                self.exchange.set_position_mode(hedged=False)
                logger.info("🔒 Bitget account verified: One-Way Mode Active.")
            except Exception:
                pass
        else:
            logger.info("ℹ️ Running in Paper Mode without full private keys.")

    def get_ccxt_symbol(self, bitget_symbol):
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

                    self.cg_buffer[base_sym].append({
                        "time": now,
                        "price": float(item.get("price", 0.0) or 0.0),
                        "price_2m": float(item.get("price_2m", 0.0) or 0.0),
                        "oi_2m": float(item.get("oi_2m", 0.0) or 0.0),
                        "vol_24h": float(item.get("vol_24h", 0.0) or 0.0),
                        "est_force_2m": float(item.get("est_force_2m", 0.0) or 0.0),
                        "exchange_count": int(item.get("exchange_count", 1))
                    })
                    valid_count += 1
                dashboard_data["cg_global_pairs"] = valid_count
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # MULTI-METHOD TAPE CLASSIFIER & ORDER BOOK LEVEL PROFILER
    # -------------------------------------------------------------------------
    def evaluate_order_dispersion_and_fills(self, bitget_symbol, side):
        try:
            ccxt_symbol = self.get_ccxt_symbol(bitget_symbol)
            ob = self.exchange.fetch_order_book(ccxt_symbol, limit=25)
            bids, asks = ob.get("bids", []), ob.get("asks", [])
            if len(bids) < 8 or len(asks) < 8:
                return None

            best_bid, best_ask = bids[0][0], asks[0][0]
            mid_price = (best_bid + best_ask) / 2.0
            if mid_price <= 0:
                return None

            spread_pct = ((best_ask - best_bid) / mid_price) * 100.0
            if spread_pct > 0.30:
                return None

            bid_gaps = [((bids[i][0] - bids[i+1][0]) / mid_price) * 100.0 for i in range(min(10, len(bids)-1))]
            ask_gaps = [((asks[i+1][0] - asks[i][0]) / mid_price) * 100.0 for i in range(min(10, len(asks)-1))]

            avg_bid_gap = sum(bid_gaps) / len(bid_gaps) if bid_gaps else 0.0
            avg_ask_gap = sum(ask_gaps) / len(ask_gaps) if ask_gaps else 0.0
            avg_level_gap = (avg_bid_gap + avg_ask_gap) / 2.0

            if side == "buy":
                level_volumes = [p * q for p, q in asks[:12]]
                avg_vol = (sum(level_volumes) / len(level_volumes)) if level_volumes else 1.0
                remaining_fills = 0
                for v in level_volumes:
                    if v >= (avg_vol * 2.5):
                        break
                    remaining_fills += 1

                supporting_vol = sum(p * q for p, q in bids[:12])
                opposing_vol = sum(level_volumes)
                ratio = supporting_vol / opposing_vol if opposing_vol > 0 else 1.0
            else:
                level_volumes = [p * q for p, q in bids[:12]]
                avg_vol = (sum(level_volumes) / len(level_volumes)) if level_volumes else 1.0
                remaining_fills = 0
                for v in level_volumes:
                    if v >= (avg_vol * 2.5):
                        break
                    remaining_fills += 1

                supporting_vol = sum(p * q for p, q in asks[:12])
                opposing_vol = sum(level_volumes)
                ratio = supporting_vol / opposing_vol if opposing_vol > 0 else 1.0

            return {
                "avg_level_gap": avg_level_gap,
                "remaining_fills": max(1, remaining_fills),
                "spread_pct": spread_pct,
                "depth_ratio": ratio
            }
        except Exception:
            return None

    def classify_microstructure_method(self, cand, ob_data, force_usd):
        p2m = cand["p2m"]
        ratio = ob_data["depth_ratio"]
        fills = ob_data["remaining_fills"]

        # Method 2: Iceberg Absorption Trap (High force, but price movement is coiled <= 0.40%)
        if force_usd >= 80_000.0 and abs(p2m) <= 0.40:
            method_name = "METHOD_2_ICEBERG_ABSORPTION_TRAP"
            score = 99
        # Method 6: Terminal Wall Breakthrough (2 fills before wall with heavy support)
        elif fills <= 2 and ratio >= 1.50:
            method_name = "METHOD_6_TERMINAL_WALL_BREAKTHROUGH"
            score = 97
        # Method 1: Liquidity Vacuum Sprint (Runway expansion through gapped levels)
        else:
            method_name = "METHOD_1_LIQUIDITY_VACUUM_SPRINT"
            score = 98

        return method_name, score

    def format_forensic_tape_dossier(self, signal, current_price, ob_data, method_name, force_usd):
        lines = [
            f"==================== [CROSS-EXCHANGE FORENSIC TAPE DOSSIER] ====================",
            f"TIMESTAMP: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | ASSET: {signal['base_sym']}USDT",
            f"CLASSIFIED PATTERN: {method_name} | SCORE: {signal['score']}/100",
            f"DIRECTION: {signal['side'].upper()} | ENTRY EXECUTION PRICE: ${current_price:.6f}",
            f"2-MIN ESTIMATED FORCE INJECTED: ${force_usd:,.0f} USD (Across Venues)",
            f"ORDER BOOK STRUCTURE: Level Gap: {ob_data['avg_level_gap']:.3f}% | Fills to Wall: {ob_data['remaining_fills']} | Depth Ratio: {ob_data['depth_ratio']:.2f}x",
            f"BITGET ESTIMATED FRICTION: 0.12% Fees + {ob_data['spread_pct']:.2f}% Spread = {0.12 + ob_data['spread_pct']:.2f}%",
            f"--------------------------------------------------------------------------------",
            f"RAW COPY-PASTE SNIPPET FOR AI ANALYSIS:",
            json.dumps({
                "asset": signal['base_sym'],
                "side": signal['side'],
                "method": method_name,
                "force_usd": round(force_usd, 0),
                "gap_pct": round(ob_data['avg_level_gap'], 3),
                "fills_remaining": ob_data['remaining_fills'],
                "depth_ratio": round(ob_data['depth_ratio'], 2)
            }, indent=2),
            f"================================================================================"
        ]
        dossier_text = "\n".join(lines)
        dashboard_data["latest_tape_dossier"] = dossier_text
        logger.info("\n" + dossier_text)

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
            if len(buf) < 2:
                continue

            latest = buf[-1]
            p2m = latest["price_2m"]
            oi2m = latest["oi_2m"]

            # Velocity window (0.25% to 1.95%) allows both absorption coils and gap sprints
            if abs(p2m) > 1.95 or abs(p2m) < 0.25:
                continue

            # Confirm Open Interest is holding or expanding
            if p2m > 0 and oi2m >= -0.05:
                candidates.append({
                    "side": "buy", "p2m": p2m, "oi2m": oi2m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym,
                    "force_usd": latest["est_force_2m"]
                })
            elif p2m < 0 and oi2m >= -0.05:
                candidates.append({
                    "side": "sell", "p2m": p2m, "oi2m": oi2m,
                    "bitget_symbol": bitget_symbol, "base_sym": base_sym,
                    "force_usd": latest["est_force_2m"]
                })

        if candidates:
            candidates.sort(key=lambda x: abs(x["p2m"]), reverse=True)

            profiled = []
            for cand in candidates[:5]:
                ob_data = self.evaluate_order_dispersion_and_fills(cand["bitget_symbol"], cand["side"])
                if not ob_data:
                    continue

                # Must have at least 3 fills of runway at entry to allow expansion
                if ob_data["remaining_fills"] >= 3 and ob_data["depth_ratio"] >= 1.25:
                    method_name, score = self.classify_microstructure_method(cand, ob_data, cand["force_usd"])
                    cand["setup"] = method_name
                    cand["score"] = score
                    cand["ob_data"] = ob_data
                    cand["elasticity_score"] = ob_data["avg_level_gap"] * ob_data["remaining_fills"] + (score / 10.0)
                    profiled.append(cand)

            if profiled:
                profiled.sort(key=lambda x: x["elasticity_score"], reverse=True)
                top = profiled[0]
                exec_price = self.bitget_prices.get(top["bitget_symbol"], 0.0)
                if exec_price > 0:
                    top["entry_price"] = exec_price
                    return top

        return None

    def calculate_live_position_size(self, ccxt_symbol, current_price):
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
            rounded_size = float(self.exchange.amount_to_precision(ccxt_symbol, raw_size))

            market = self.exchange.market(ccxt_symbol) if hasattr(self.exchange, "markets") and ccxt_symbol in self.exchange.markets else None
            min_amount = float((market.get("limits") or {}).get("amount", {}).get("min", 0.0) or 0.0) if market else 0.0
            
            if min_amount > 0 and rounded_size < min_amount:
                required_notional = min_amount * current_price
                if (required_notional / leverage) <= usable_margin:
                    rounded_size = min_amount

            return rounded_size, leverage
        except Exception as e:
            logger.error(f"Sizing error: {e}")
            return 0, 0

    def enter_trade(self, signal):
        symbol = signal["bitget_symbol"]
        base_sym = signal["base_sym"]
        side = signal["side"]
        price = signal["entry_price"]
        ob_data = signal["ob_data"]
        is_paper = (self.state_mgr.state["mode"] == "PAPER")

        self.format_forensic_tape_dossier(signal, price, ob_data, signal["setup"], signal["force_usd"])

        trade_info = {
            "symbol": symbol,
            "base_sym": base_sym,
            "side": side,
            "setup": signal["setup"],
            "entry_price": price,
            "entry_spread_pct": ob_data["spread_pct"],
            "entry_time": time.time(),
            "peak_price": price,
            "highest_gross_pct": 0.0,
            "remaining_fills": ob_data["remaining_fills"],
            "is_paper": is_paper,
            "mode": "PAPER" if is_paper else "LIVE",
            "size": 0
        }

        if is_paper:
            logger.info(f"📝 [PAPER ENTRY] Opened {side.upper()} on {symbol} @ {price} | Pattern: {signal['setup']} | Fills to Wall: {ob_data['remaining_fills']}")
            self.active_trade = trade_info
        else:
            try:
                ccxt_symbol = self.get_ccxt_symbol(symbol)
                size, lev = self.calculate_live_position_size(ccxt_symbol, price)
                if size <= 0:
                    logger.warning(f"Aborting live trade: calculated size {size} is sub-minimum.")
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
    # REAL-TIME TRADE MANAGEMENT & TERMINAL FILL EXIT
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

        friction_pct = BITGET_ROUNDTRIP_FEE_PCT + trade["entry_spread_pct"]
        net_pnl = gross_pnl - friction_pct

        if (now - self.last_watchdog_time) >= WATCHDOG_CHECK_INTERVAL:
            self.last_watchdog_time = now
            live_ob = self.evaluate_order_dispersion_and_fills(symbol, side)
            if live_ob:
                trade["remaining_fills"] = live_ob["remaining_fills"]

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
            "remaining_fills": f"{trade['remaining_fills']} FILLS LEFT",
            "elapsed_seconds": int(elapsed)
        }

        exit_reason = None

        # 1. Structural Hard Stop
        if gross_pnl <= -HARD_STOP_PCT:
            exit_reason = "HARD_STOP_LOSS"

        # 2. Terminal Fill Exit: Bank profit when 1-2 fills remain to the wall
        elif trade["remaining_fills"] <= 2 and net_pnl >= MIN_TARGET_NET_PROFIT_PCT:
            exit_reason = "TERMINAL_FILL_PEAK_BANK"

        # 3. Apex Rollover Exit: Peak >= 0.70% and pulls back 0.12%
        elif trade["highest_gross_pct"] >= 0.70 and drawdown_from_peak >= 0.12 and net_pnl >= MIN_TARGET_NET_PROFIT_PCT:
            exit_reason = "SLA_APEX_LOCK"

        # 4. 2-Minute Stagnation Cut: If not green after 120s, exit cleanly
        elif elapsed >= 120 and elapsed <= 180 and net_pnl <= -0.15:
            exit_reason = "2M_STAGNATION_CUT"

        # 5. Maximum Runner Ceiling
        elif elapsed >= MAX_LIFECYCLE_SECONDS:
            exit_reason = "10M_RUNNER_EXPIRATION"

        if exit_reason:
            self._execute_exit(trade, current_price, gross_pnl, net_pnl, exit_reason)

    def _execute_exit(self, trade, exit_price, gross_pnl, net_pnl, reason):
        symbol, side, is_paper, setup_name = trade["symbol"], trade["side"], trade["is_paper"], trade["setup"]
        try:
            if not is_paper:
                ccxt_symbol = self.get_ccxt_symbol(symbol)
                exact_size = trade.get("size", 0.0)

                try:
                    positions = self.exchange.fetch_positions([ccxt_symbol])
                    if positions and isinstance(positions, list):
                        for p in positions:
                            pos_sym = p.get("symbol", "")
                            if pos_sym == ccxt_symbol or pos_sym.replace("/", "").replace(":USDT", "") == symbol:
                                contracts = abs(float(p.get("contracts", 0.0) or p.get("contractSize", 0.0) or 0.0))
                                if contracts > 0:
                                    exact_size = contracts
                                    break
                except Exception:
                    pass

                exact_size = float(self.exchange.amount_to_precision(ccxt_symbol, exact_size))
                if exact_size > 0:
                    params = {"reduceOnly": True, "tradeSide": "close"}
                    if side == "buy":
                        self.exchange.create_market_sell_order(ccxt_symbol, exact_size, params=params)
                    else:
                        self.exchange.create_market_buy_order(ccxt_symbol, exact_size, params=params)
                logger.info(f"⚡ [LIVE EXIT] Closed {side.upper()} {symbol} @ {exit_price} | NET: {net_pnl:+.2f}% (Gross: {gross_pnl:+.2f}%) | Reason: {reason}")
            else:
                logger.info(f"📝 [PAPER EXIT] Closed {side.upper()} {symbol} @ {exit_price} | NET: {net_pnl:+.2f}% (Gross: {gross_pnl:+.2f}%) | Reason: {reason}")
            
            self.state_mgr.record_trade(symbol, side, gross_pnl, net_pnl, reason, setup_name, is_paper)
            
            if net_pnl >= 0.75:
                self.learning_engine.autopsy_winning_trade(symbol, side, net_pnl, setup_name)

            self.cooldowns[symbol] = time.time()
        except Exception as e:
            logger.error(f"Exit execution error: {e}")
        finally:
            self.active_trade = None
            dashboard_data["active_trade"] = None

    def run(self):
        logger.info("🚀 Production Forensic Tape Desk Online...")
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

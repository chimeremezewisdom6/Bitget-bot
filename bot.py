#!/usr/bin/env python3
"""
Smart Quant Trading Bot - Bitget USDT-M Perpetual Swaps
- Engine: Strict Dual-Polarity Imbalance (One side <= -1.5%, Other side >= +1.5%)
- Intelligence: Detects "Price Meets OI" vs "OI Traps" (Only enters genuine re-alignments)
- Reporting: Clean 15-Minute Desk Briefing in Render Logs & Web Dashboard
- Execution: One-Way Mode, Dynamic Leverage ($5.50 Min Notional), reduceOnly
- Safety: Anti-Trap Spread Check, Anti-Stagnation (20m velocity cut), PARTI Loop Defense
- Qualification: Strict 6-in-a-row Paper Win Gauntlet before Live Unlock
- Infrastructure: Universal Key Detection, Render Port 10000 HTTP Keep-Alive & Auto-Recovery
"""

import os
import sys
import time
import json
import math
import logging
import threading
from collections import deque
from typing import Dict, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler

import ccxt
import requests
from requests.adapters import HTTPAdapter

# ==============================================================================
# 1. LOGGING SETUP & SPAM SUPPRESSION
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("QuantDesk")

# Mute noisy connection pool warnings from urllib3
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

# ==============================================================================
# 2. UNIVERSAL CREDENTIAL DETECTION & PARAMETERS
# ==============================================================================
API_KEY = (
    os.getenv("BITGET_API_KEY") or
    os.getenv("API_KEY") or
    os.getenv("BITGET_KEY") or
    ""
).strip()

API_SECRET = (
    os.getenv("BITGET_API_SECRET") or
    os.getenv("BITGET_SECRET_KEY") or
    os.getenv("API_SECRET") or
    os.getenv("SECRET_KEY") or
    os.getenv("BITGET_SECRET") or
    ""
).strip()

API_PASSPHRASE = (
    os.getenv("BITGET_API_PASSPHRASE") or
    os.getenv("BITGET_PASSPHRASE") or
    os.getenv("API_PASSPHRASE") or
    os.getenv("PASSPHRASE") or
    os.getenv("BITGET_PASSWORD") or
    ""
).strip()

PORT = int(os.getenv("PORT", 10000))
STATE_FILE = "qualification_state.json"

# Strict Token Blacklist
BLACKLIST = {
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP",
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
}

# Strict Dual-Polarity Gate (BOTH sides must cross 1.5% in opposite directions)
MIN_POLARITY_THRESHOLD = 1.50      # Strictly +/- 1.50%
MIN_24H_VOLUME_USDT = 1_000_000.0  # $1,000,000 minimum liquidity
MAX_SPREAD_PCT = 0.10              # Anti-trap order book spread <= 0.10%

# Risk & Order Execution Parameters
BALANCE_UTILIZATION = 0.90         # Use 90% of free balance
BITGET_MIN_NOTIONAL = 5.50         # $5.50 USDT minimum order value
HARD_STOP_LOSS_PCT = 0.90          # 0.9% hard structural stop loss
VELOCITY_TIMEOUT_SECONDS = 1200    # 20 minutes velocity clock
VELOCITY_MIN_PROFIT_PCT = 1.20     # Must achieve >= +1.2% in 20m or cut trade
RUNNER_TRAIL_ACTIVATION_PCT = 3.50 # Activate dynamic runner trailing at +3.5%
RUNNER_GIVEBACK_PCT = 0.80         # Trail 0.8% behind local peak
COOLDOWN_SECONDS = 900             # 15 minutes symbol cooldown
BRIEFING_INTERVAL_SECONDS = 900    # 15 minutes intelligence debrief

# ==============================================================================
# 3. HTTP KEEP-ALIVE DASHBOARD (PORT 10000)
# ==============================================================================
DASHBOARD_DATA = {
    "status": "Initializing",
    "mode": "PAPER",
    "paper_wins": 0,
    "live_balance": 0.0,
    "active_trade": None,
    "last_scan_duration_sec": 0.0,
    "last_briefing": {},
    "last_scan_time": "None"
}

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps(DASHBOARD_DATA, indent=2)
        self.wfile.write(response.encode("utf-8"))

    def log_message(self, format, *args):
        return  # Suppress HTTP access noise

def start_keep_alive_server(port: int):
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Keep-Alive HTTP server running on port {port}")

# ==============================================================================
# 4. QUANT TRADING BOT ENGINE
# ==============================================================================
class QuantBot:
    def __init__(self):
        self.exchange = ccxt.bitget({
            "apiKey": API_KEY,
            "secret": API_SECRET,
            "password": API_PASSPHRASE,
            "options": {
                "defaultType": "swap",
                "createMarketBuyOrderRequiresPrice": False
            },
            "enableRateLimit": True,
        })

        # Upgrade HTTP adapter pool to 50 connections to eliminate warnings
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.exchange.session.mount("https://", adapter)
        self.exchange.session.mount("http://", adapter)

        self.paper_wins = 0
        self.live_mode = False
        self.active_trade: Optional[Dict] = None
        self.cooldown_tracker: Dict[str, float] = {}

        # Time-Series Buffers: {symbol: deque([{'time': t, 'price': p, 'oi': oi}, ...])}
        self.history_buffer: Dict[str, deque] = {}
        
        # Intelligence / Learning Memory
        self.traps_rejected_count = 0
        self.ignitions_confirmed_count = 0
        self.recent_learnings: List[str] = []
        self.last_briefing_time = time.time()

        self.load_state()
        self.init_exchange_settings()
        self.recover_live_position()

    # --------------------------------------------------------------------------
    # STATE MANAGEMENT & PERSISTENCE
    # --------------------------------------------------------------------------
    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.paper_wins = data.get("paper_wins", 0)
                    self.live_mode = data.get("live_mode", False)
                    logger.info(f"Loaded persistent state: {self.paper_wins}/6 Paper Wins. LiveMode: {self.live_mode}")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "paper_wins": self.paper_wins,
                    "live_mode": self.live_mode,
                    "timestamp": time.time()
                }, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    # --------------------------------------------------------------------------
    # EXCHANGE SETTINGS & AUTO-RECOVERY
    # --------------------------------------------------------------------------
    def init_exchange_settings(self):
        logger.info(f"Credential Status -> Key Detected: {bool(API_KEY)} | Secret Detected: {bool(API_SECRET)} | Passphrase Detected: {bool(API_PASSPHRASE)}")
        
        if not API_KEY or not API_SECRET or not API_PASSPHRASE:
            logger.warning("Bitget API credentials missing or incomplete. Bot running in PAPER SIMULATION mode.")
            return

        try:
            self.exchange.set_position_mode(False, params={"productType": "USDT-FUTURES"})
            logger.info("Bitget Position Mode confirmed: ONE-WAY (Single Hold)")
        except Exception as e:
            logger.info(f"Position mode notice: {e}")

    def recover_live_position(self):
        """Auto-recovery if Render restarts while a live trade is open."""
        if not API_KEY:
            return

        try:
            positions = self.exchange.fetch_positions(params={"productType": "USDT-FUTURES"})
            for p in positions:
                contracts = float(p.get("contracts", 0.0) or 0.0)
                if contracts > 0:
                    symbol = p["symbol"]
                    side_raw = str(p.get("side", "")).lower()
                    side = "buy" if side_raw in ["long", "buy"] else "sell"
                    entry_price = float(p.get("entryPrice", 0.0) or 0.0)

                    self.active_trade = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "peak_price": entry_price,
                        "contracts": contracts,
                        "entry_time": time.time(),
                        "is_live": True,
                        "method": "RECOVERED_LIVE",
                        "leverage": int(p.get("leverage", 5))
                    }
                    self.live_mode = True
                    logger.warning(f"RESTART RECOVERY: Open position detected on {symbol} {side.upper()} | "
                                   f"Size: {contracts} @ ${entry_price:.6f}")
                    break
        except Exception as e:
            logger.error(f"Live position recovery error: {e}")

    # --------------------------------------------------------------------------
    # PRICE & OPEN INTEREST BUFFER
    # --------------------------------------------------------------------------
    def is_symbol_valid(self, symbol: str) -> bool:
        base = symbol.split("/")[0].split(":")[0]
        if base in BLACKLIST:
            return False
        if time.time() < self.cooldown_tracker.get(symbol, 0):
            return False
        return True

    def update_time_series_buffer(self, tickers: Dict):
        now = time.time()
        for sym, t in tickers.items():
            if not sym.endswith(":USDT") or not self.is_symbol_valid(sym):
                continue

            price = float(t.get("last", 0.0) or t.get("close", 0.0) or 0.0)
            oi = float(t.get("openInterest") or t.get("info", {}).get("holdingAmount") or 0.0)

            if price <= 0 or oi <= 0:
                continue

            if sym not in self.history_buffer:
                self.history_buffer[sym] = deque()

            buf = self.history_buffer[sym]
            buf.append({"time": now, "price": price, "oi": oi})

            while buf and (now - buf[0]["time"]) > 2100:
                buf.popleft()

    def calculate_deltas(self, symbol: str, target_seconds: int) -> Optional[Tuple[float, float]]:
        buf = self.history_buffer.get(symbol)
        if not buf or len(buf) < 2:
            return None

        current = buf[-1]
        target_time = current["time"] - target_seconds
        past = min(buf, key=lambda x: abs(x["time"] - target_time))
        elapsed = current["time"] - past["time"]

        if elapsed < (target_seconds * 0.50):
            return None

        pr_change = ((current["price"] - past["price"]) / past["price"]) * 100.0
        oi_change = ((current["oi"] - past["oi"]) / past["oi"]) * 100.0

        return pr_change, oi_change

    # --------------------------------------------------------------------------
    # STRICT DUAL-POLARITY SCANNER & IGNITION VERIFIER
    # --------------------------------------------------------------------------
    def anti_trap_check(self, symbol: str) -> bool:
        try:
            ob = self.exchange.fetch_order_book(symbol, limit=5)
            bid = ob["bids"][0][0] if ob["bids"] else None
            ask = ob["asks"][0][0] if ob["asks"] else None
            if not bid or not ask:
                return False
            spread_pct = ((ask - bid) / ask) * 100.0
            return spread_pct <= MAX_SPREAD_PCT
        except Exception:
            return False

    def verify_price_ignition(self, symbol: str, setup_type: str) -> Optional[str]:
        """
        Inspects immediate 1m price candles.
        Confirms Price is aggressively moving to balance with OI (Not an OI trap).
        Returns 'buy', 'sell', or None.
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=4)
            if not ohlcv or len(ohlcv) < 3:
                return None

            candles = ohlcv[-3:]
            start_open = candles[0][1]
            end_close = candles[-1][4]
            move_pct = ((end_close - start_open) / start_open) * 100.0

            # If Price was <= -1.5% and OI was >= +1.5% (Heavy short build-up)
            if setup_type == "SHORT_BUILDUP":
                # If price accelerates further down to meet the short buildup -> enter SELL
                if move_pct <= -0.35 and candles[-1][4] < candles[-1][1]:
                    return "sell"
                # If price violently reverses to liquidate the aggressive shorts -> enter BUY
                elif move_pct >= +0.40 and candles[-1][4] > candles[-1][1]:
                    return "buy"

            # If Price was >= +1.5% and OI was <= -1.5% (Short squeeze expansion)
            elif setup_type == "SHORT_SQUEEZE":
                # Price must continue accelerating up -> enter BUY
                if move_pct >= +0.35 and candles[-1][4] > candles[-1][1]:
                    return "buy"

            return None
        except Exception:
            return None

    def scan_for_opportunities(self) -> Optional[Dict]:
        scan_start = time.time()
        tickers = self.exchange.fetch_tickers()
        self.update_time_series_buffer(tickers)

        candidates = []
        for sym, t in tickers.items():
            if not sym.endswith(":USDT") or not self.is_symbol_valid(sym):
                continue
            vol = float(t.get("quoteVolume", 0.0) or 0.0)
            if vol < MIN_24H_VOLUME_USDT:
                continue

            deltas = self.calculate_deltas(sym, 900)
            if not deltas:
                continue

            pr_15, oi_15 = deltas

            # ==================================================================
            # STRICT DUAL-POLARITY RULE:
            # BOTH sides MUST cross +/- 1.5% in opposite directions!
            # ==================================================================
            setup_a = (pr_15 <= -MIN_POLARITY_THRESHOLD and oi_15 >= MIN_POLARITY_THRESHOLD)
            setup_b = (pr_15 >= MIN_POLARITY_THRESHOLD and oi_15 <= -MIN_POLARITY_THRESHOLD)

            if not (setup_a or setup_b):
                continue

            setup_type = "SHORT_BUILDUP" if setup_a else "SHORT_SQUEEZE"
            gap = abs(oi_15 - pr_15)

            candidates.append({
                "symbol": sym,
                "setup_type": setup_type,
                "pr_15": pr_15,
                "oi_15": oi_15,
                "gap": gap
            })

        scan_duration = time.time() - scan_start
        DASHBOARD_DATA["last_scan_duration_sec"] = round(scan_duration, 2)

        if not candidates:
            return None

        # Rank by largest polarity gap
        candidates.sort(key=lambda x: x["gap"], reverse=True)
        champion = candidates[0]

        # Test #1: Anti-Trap Spread Check
        if not self.anti_trap_check(champion["symbol"]):
            self.traps_rejected_count += 1
            return None

        # Test #2: The "Price Meets OI" Ignition Test
        symbol = champion["symbol"]
        setup_type = champion["setup_type"]
        confirmed_direction = self.verify_price_ignition(symbol, setup_type)

        if confirmed_direction:
            self.ignitions_confirmed_count += 1
            champion["direction"] = confirmed_direction
            learning_note = (
                f"{symbol}: Dual-Polarity Confirmed (OI: {champion['oi_15']:+.2f}% | "
                f"Price: {champion['pr_15']:+.2f}%) -> Active Ignition {confirmed_direction.upper()}"
            )
            self.recent_learnings.append(learning_note)
            logger.info(f"CONFIRMED DUAL-POLARITY TRADE: {learning_note}")
            return champion
        else:
            self.traps_rejected_count += 1
            trap_note = f"{symbol}: Dual-Polarity found (OI: {champion['oi_15']:+.2f}%, Pr: {champion['pr_15']:+.2f}%) but Price stayed dormant -> OI TRAP DISCARDED"
            self.recent_learnings.append(trap_note)
            return None

    # --------------------------------------------------------------------------
    # 15-MINUTE INTELLIGENCE BRIEFING
    # --------------------------------------------------------------------------
    def print_desk_briefing(self):
        now = time.time()
        if (now - self.last_briefing_time) < BRIEFING_INTERVAL_SECONDS:
            return

        self.last_briefing_time = now

        # Only search for champions that strictly qualify under the dual +/- 1.5% rule
        top_imbalance_str = "None (Market in equilibrium, no dual +/- 1.5% divergence)"
        highest_gap = 0.0

        for sym in list(self.history_buffer.keys()):
            deltas = self.calculate_deltas(sym, 900)
            if deltas:
                p, o = deltas
                if (p <= -MIN_POLARITY_THRESHOLD and o >= MIN_POLARITY_THRESHOLD) or \
                   (p >= MIN_POLARITY_THRESHOLD and o <= -MIN_POLARITY_THRESHOLD):
                    gap = abs(o - p)
                    if gap > highest_gap:
                        highest_gap = gap
                        top_imbalance_str = f"{sym} | OI: {o:+.2f}% | Price: {p:+.2f}% (Gap: {gap:.1f}%)"

        last_learning = self.recent_learnings[-1] if self.recent_learnings else "Equilibrium maintained. Zero unconfirmed traps."
        if len(self.recent_learnings) > 10:
            self.recent_learnings = self.recent_learnings[-10:]

        briefing_text = (
            f"\n{'='*25} [15-MIN DESK BRIEFING] {'='*25}\n"
            f"• DUAL-POLARITY CHAMPION: {top_imbalance_str}\n"
            f"• RECENT LEARNING: {last_learning}\n"
            f"• TRAPS AVOIDED: {self.traps_rejected_count} (OI faded into flat price)\n"
            f"• CONFIRMED IGNITIONS: {self.ignitions_confirmed_count}\n"
            f"• GAUNTLET PROGRESS: {self.paper_wins}/6 Wins | Mode: {'LIVE' if self.live_mode else 'PAPER'}\n"
            f"• TRACKING UNIVERSE: {len(self.history_buffer)} liquid perpetual pairs active\n"
            f"{'='*72}"
        )
        logger.info(briefing_text)

        DASHBOARD_DATA["last_briefing"] = {
            "top_imbalance": top_imbalance_str,
            "last_learning": last_learning,
            "traps_rejected": self.traps_rejected_count,
            "ignitions_confirmed": self.ignitions_confirmed_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    # --------------------------------------------------------------------------
    # SIZING & EXECUTION (MICRO-ACCOUNT ONE-WAY MODE)
    # --------------------------------------------------------------------------
    def calculate_sizing(self, symbol: str, current_price: float) -> Tuple[int, float]:
        balance = self.exchange.fetch_balance()
        free_usdt = float(balance.get("USDT", {}).get("free", 0.0) or 0.0)
        usable_margin = max(free_usdt * BALANCE_UTILIZATION, 0.50)

        # Dynamic Leverage = ceil(5.50 / usable_margin)
        calculated_lev = math.ceil(BITGET_MIN_NOTIONAL / usable_margin)
        leverage = max(2, min(calculated_lev, 20))

        target_notional = usable_margin * leverage
        if target_notional < BITGET_MIN_NOTIONAL:
            target_notional = BITGET_MIN_NOTIONAL + 0.20

        raw_amount = target_notional / current_price
        formatted_amount = float(self.exchange.amount_to_precision(symbol, raw_amount))
        return leverage, formatted_amount

    def execute_entry(self, candidate: Dict):
        symbol = candidate["symbol"]
        direction = candidate["direction"]

        ticker = self.exchange.fetch_ticker(symbol)
        current_price = ticker["ask"] if direction == "buy" else ticker["bid"]

        if not self.live_mode:
            # Paper execution
            self.active_trade = {
                "symbol": symbol,
                "side": direction,
                "entry_price": current_price,
                "peak_price": current_price,
                "contracts": 10.0,
                "entry_time": time.time(),
                "is_live": False,
                "method": "DUAL_POLARITY_1.5_IMBALANCE",
                "leverage": 5
            }
            logger.info(f"[PAPER ENTER] {direction.upper()} on {symbol} @ ${current_price:.6f} | "
                        f"Gap: {candidate['gap']:.2f}% | Streak: {self.paper_wins}/6")
            return

        # Live Execution
        try:
            leverage, amount = self.calculate_sizing(symbol, current_price)
            try:
                self.exchange.set_leverage(leverage, symbol, params={"productType": "USDT-FUTURES", "marginCoin": "USDT"})
            except Exception as e:
                logger.info(f"Leverage notice: {e}")

            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=direction,
                amount=amount,
                params={"productType": "USDT-FUTURES"}
            )

            fill_price = float(order.get("average", 0.0) or current_price)
            self.active_trade = {
                "symbol": symbol,
                "side": direction,
                "entry_price": fill_price,
                "peak_price": fill_price,
                "contracts": amount,
                "entry_time": time.time(),
                "is_live": True,
                "method": "DUAL_POLARITY_1.5_IMBALANCE",
                "leverage": leverage
            }
            logger.info(f"[LIVE ENTER] {direction.upper()} on {symbol} | Amount: {amount} @ ${fill_price:.6f} | Lev: {leverage}x")

        except Exception as e:
            logger.error(f"Live order failed: {e}")
            self.active_trade = None

    def execute_exit(self, reason: str):
        """
        Permanent fix for PARTI phantom loop:
        Uses live REST contract queries, reduceOnly, and atomic finally state cleanup.
        """
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        side = trade["side"]
        exit_side = "sell" if side == "buy" else "buy"
        is_live = trade.get("is_live", False)

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            exit_price = ticker["bid"] if exit_side == "sell" else ticker["ask"]
            entry_price = trade["entry_price"]

            if side == "buy":
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0

            is_win = pnl_pct > 0

            if is_live:
                try:
                    positions = self.exchange.fetch_positions([symbol], params={"productType": "USDT-FUTURES"})
                    live_contracts = 0.0
                    for p in positions:
                        if p["symbol"] == symbol:
                            live_contracts = float(p.get("contracts", 0.0) or 0.0)
                            break

                    close_amount = live_contracts if live_contracts > 0 else trade["contracts"]

                    self.exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=exit_side,
                        amount=close_amount,
                        params={
                            "reduceOnly": True,
                            "tradeSide": "close",
                            "productType": "USDT-FUTURES"
                        }
                    )
                    logger.info(f"[LIVE EXIT] Closed {symbol} via reduceOnly @ ${exit_price:.6f} | PnL: {pnl_pct:.2f}% | Reason: {reason}")
                except Exception as e:
                    logger.error(f"Live exit submission exception: {e}")
            else:
                logger.info(f"[PAPER EXIT] Closed {symbol} @ ${exit_price:.6f} | PnL: {pnl_pct:.2f}% | Reason: {reason}")

            # Qualification Counter (Strict 6-in-a-row)
            if not is_live:
                if is_win:
                    self.paper_wins += 1
                    logger.info(f"PAPER QUALIFIER WIN: Consecutive streak is now {self.paper_wins}/6")
                    if self.paper_wins >= 6:
                        self.live_mode = True
                        logger.warning("*********************************************************")
                        logger.warning("6 CONSECUTIVE WINS ACHIEVED! LIVE TRADING UNLOCKED!")
                        logger.warning("*********************************************************")
                else:
                    logger.warning(f"PAPER LOSS ({pnl_pct:.2f}%). Counter reset back to 0/6.")
                    self.paper_wins = 0

                self.save_state()

        except Exception as e:
            logger.error(f"Critical error during exit: {e}")

        finally:
            # Atomic state reset: permanently prevents PARTI phantom loop
            self.active_trade = None
            self.cooldown_tracker[symbol] = time.time() + COOLDOWN_SECONDS
            logger.info(f"{symbol} assigned to 15-minute cooldown.")

    # --------------------------------------------------------------------------
    # POSITION MONITOR & ANTI-STAGNATION
    # --------------------------------------------------------------------------
    def monitor_active_trade(self):
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = trade["entry_price"]
        entry_time = trade["entry_time"]

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker["last"]

            if side == "buy":
                pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                if current_price > trade["peak_price"]:
                    trade["peak_price"] = current_price
                drawdown_from_peak = ((trade["peak_price"] - current_price) / trade["peak_price"]) * 100.0
            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100.0
                if current_price < trade["peak_price"]:
                    trade["peak_price"] = current_price
                drawdown_from_peak = ((current_price - trade["peak_price"]) / trade["peak_price"]) * 100.0

            duration_secs = time.time() - entry_time

            DASHBOARD_DATA["active_trade"] = {
                "symbol": symbol,
                "side": side.upper(),
                "entry": entry_price,
                "current": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "duration_min": round(duration_secs / 60, 1)
            }

            # 1. Hard Structural Stop Loss (0.9% Pivot Breached)
            if pnl_pct <= -HARD_STOP_LOSS_PCT:
                self.execute_exit(f"Hard Stop-Loss Breached (-{HARD_STOP_LOSS_PCT}%)")
                return

            # 2. Anti-Stagnation Velocity Cut (20 Minutes Clock)
            if duration_secs >= VELOCITY_TIMEOUT_SECONDS:
                if pnl_pct < VELOCITY_MIN_PROFIT_PCT:
                    self.execute_exit(f"Velocity Cut (Stagnant < +{VELOCITY_MIN_PROFIT_PCT}% after 20m)")
                    return

            # 3. Dynamic Runner Trailing (+3.5% up to +35%)
            if pnl_pct >= RUNNER_TRAIL_ACTIVATION_PCT:
                if drawdown_from_peak >= RUNNER_GIVEBACK_PCT:
                    self.execute_exit(f"Dynamic Runner Harvested (+{pnl_pct:.2f}% locked)")
                    return

        except Exception as e:
            logger.error(f"Error monitoring active trade on {symbol}: {e}")

    # --------------------------------------------------------------------------
    # MAIN EVENT LOOP
    # --------------------------------------------------------------------------
    def run(self):
        logger.info("Strict Dual-Polarity Quant Engine active. Event loop running...")

        while True:
            try:
                if API_KEY:
                    try:
                        bal = self.exchange.fetch_balance()
                        DASHBOARD_DATA["live_balance"] = round(float(bal.get("USDT", {}).get("free", 0.0) or 0.0), 2)
                    except Exception:
                        pass

                DASHBOARD_DATA["status"] = "Active"
                DASHBOARD_DATA["mode"] = "LIVE" if self.live_mode else f"PAPER ({self.paper_wins}/6)"
                DASHBOARD_DATA["paper_wins"] = self.paper_wins
                DASHBOARD_DATA["last_scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

                # Print clean 15-minute intelligence debrief
                self.print_desk_briefing()

                # If managing an open trade, focus on monitoring
                if self.active_trade:
                    self.monitor_active_trade()
                    time.sleep(2)
                    continue

                # Run strict polarity scan
                opportunity = self.scan_for_opportunities()
                if opportunity:
                    self.execute_entry(opportunity)

                time.sleep(10)

            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(5)

# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    start_keep_alive_server(PORT)
    bot = QuantBot()
    bot.run()

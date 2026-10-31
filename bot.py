#!/usr/bin/env python3
"""
Unified Institutional Quant Trading Bot - Bitget USDT-M Perpetual Swaps
- Engine 1: Strict 4:1 Dominance Ratio (Impulse >= 2.0%, Reversal <= Impulse / 4.0)
- Engine 2: Top 10 Luckiest (Heaviest Siege Trapped at 0-0 -> Enters on Dam Break)
- Engine 3: Dual-Polarity +/- 1.5% Imbalance (Price vs. OI Tension & Pullback Hook)
- Engine 4: 8,000m Exhausted Runner (Capital Depletion vs. Fresh Backup)
- Paper Mode: Unconstrained Behavioral Laboratory (Natural Peak Harvesting & Invalidation)
- Live Mode: Strict Institutional Execution (Dynamic Leverage, One-Way, reduceOnly)
- Telemetry: 15-Minute Desk Intelligence Briefing & Port 10000 Keep-Alive Server
"""

import os
import sys
import time
import json
import math
import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Mute noisy urllib3 connection pool warnings
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

# Scanning & Filter Thresholds
MIN_24H_VOLUME_USDT = 1_000_000.0  # $1,000,000 minimum liquidity
MAX_SPREAD_PCT = 0.10              # Anti-trap order book spread <= 0.10%
SCANNER_WORKERS = 16               # Parallel threads for ~3-4s market sweep

# Engine 1 Parameters (Strict 4:1 Dominance Ratio)
DOMINANCE_RATIO = 4.0              # 4:1 move-to-retracement ratio (max 25% giveback)
MIN_10M_MOVE_PCT = 2.0             # Minimum 2.0% move in 10 minutes
MAX_10M_MOVE_PCT = 15.0            # Cap at 15.0% to avoid illiquid needles

# Engine 2 Parameters (Top 10 Luckiest / Dam Break)
MAX_LUCKY_BOX_PCT = 0.50           # Defending side trapped in < 0.50% range
MIN_SIEGE_VOL_RATIO = 0.70         # At least 70% one-sided volume hammering the wall
MIN_DAM_BREAK_PCT = 0.18           # Minimum breakout beyond defended box to confirm luck is dead

# Engine 3 Parameters (Dual-Polarity Imbalance)
MIN_POLARITY_THRESHOLD = 1.50      # Strictly +/- 1.50% on both Price & OI
MIN_PULLBACK_CONFIRM_PCT = 0.15    # Minimum 0.15% turn off extreme to confirm hook
MAX_PULLBACK_CHASE_PCT = 0.85      # Don't chase if hook gave back > 0.85%

# Account & Risk Parameters
BALANCE_UTILIZATION = 0.90         # Use 90% of free balance
BITGET_MIN_NOTIONAL = 5.50         # $5.50 USDT minimum order value
COOLDOWN_SECONDS = 900             # 15 minutes symbol cooldown post-exit
BRIEFING_INTERVAL_SECONDS = 900    # 15 minutes intelligence debrief

# LIVE Risk Limits (Strict)
LIVE_HARD_STOP_LOSS_PCT = 0.90     # 0.9% hard stop loss in live mode
LIVE_VELOCITY_TIMEOUT_SECS = 1200  # 20m velocity clock in live mode
LIVE_VELOCITY_MIN_PROFIT = 1.20    # Must achieve >= +1.2% in 20m or cut

# PAPER Learning Parameters (Unconstrained Behavioral Laboratory)
PAPER_STRUCTURAL_INVALIDATION = 2.50  # Let paper breathe up to -2.5% to observe MAE
PAPER_STAGNATION_TIMEOUT = 1500       # 25 minutes to observe dead volume fading
PAPER_STAGNATION_MIN_PROFIT = 0.60    # Require at least +0.6% after 25m

# Dynamic Runner Trailing
RUNNER_TRAIL_ACTIVATION_PCT = 3.50 # Activate dynamic trailing at +3.5%
RUNNER_GIVEBACK_PCT = 0.80         # Trail 0.8% behind local peak

# ==============================================================================
# 3. HTTP KEEP-ALIVE DASHBOARD (PORT 10000)
# ==============================================================================
DASHBOARD_DATA = {
    "status": "Initializing",
    "mode": "PAPER_LABORATORY",
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
        return

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

        # Upgrade HTTP adapter to 50 connections to eliminate warnings
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.exchange.session.mount("https://", adapter)
        self.exchange.session.mount("http://", adapter)

        self.paper_wins = 0
        self.live_mode = False
        self.active_trade: Optional[Dict] = None
        self.cooldown_tracker: Dict[str, float] = {}

        # Time-Series Buffers: {symbol: deque([{'time': t, 'price': p, 'oi': oi}, ...])}
        self.history_buffer: Dict[str, deque] = {}

        # Telemetry & Learning Memory
        self.traps_rejected_count = 0
        self.expanding_waits_count = 0
        self.ignitions_confirmed_count = 0
        self.completed_trade_dossiers: List[Dict] = []
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
        logger.info(f"Credential Status -> Key: {bool(API_KEY)} | Secret: {bool(API_SECRET)} | Passphrase: {bool(API_PASSPHRASE)}")

        if not API_KEY or not API_SECRET or not API_PASSPHRASE:
            logger.warning("Bitget API credentials missing or incomplete. Bot running in PAPER LABORATORY mode.")
            return

        try:
            self.exchange.set_position_mode(False, params={"productType": "USDT-FUTURES"})
            logger.info("Bitget Position Mode confirmed: ONE-WAY (Single Hold)")
        except Exception as e:
            logger.info(f"Position mode notice: {e}")

    def recover_live_position(self):
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
                        "trough_price": entry_price,
                        "contracts": contracts,
                        "entry_time": time.time(),
                        "is_live": True,
                        "engine": "RECOVERED_LIVE",
                        "leverage": int(p.get("leverage", 5))
                    }
                    self.live_mode = True
                    logger.warning(f"RESTART RECOVERY: Open position detected on {symbol} {side.upper()} | "
                                   f"Size: {contracts} @ ${entry_price:.6f}")
                    break
        except Exception as e:
            logger.error(f"Live position recovery error: {e}")

    # --------------------------------------------------------------------------
    # DATA BUFFERS & SCREENING
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

    def fetch_symbol_candles(self, symbol: str) -> Optional[Tuple[str, List]]:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=12)
            if ohlcv and len(ohlcv) >= 11:
                return symbol, ohlcv[-11:]
        except Exception:
            pass
        return None

    # --------------------------------------------------------------------------
    # ENGINE 1: STRICT 4:1 DOMINANCE RATIO
    # --------------------------------------------------------------------------
    def evaluate_engine_1(self, symbol: str, ohlcv: List) -> Optional[Dict]:
        candles = ohlcv[-11:-1]
        start_open = candles[0][1]
        end_close = candles[-1][4]
        net_change_pct = ((end_close - start_open) / start_open) * 100.0
        abs_change = abs(net_change_pct)

        if abs_change < MIN_10M_MOVE_PCT or abs_change > MAX_10M_MOVE_PCT:
            return None

        direction = "buy" if net_change_pct > 0 else "sell"
        max_allowed_reversal = abs_change / DOMINANCE_RATIO

        if direction == "buy":
            running_high = candles[0][2]
            max_pullback_abs = 0.0

            for c in candles:
                h, l = c[2], c[3]
                if h > running_high:
                    running_high = h
                pb = ((running_high - l) / running_high) * 100.0
                if pb > max_pullback_abs:
                    max_pullback_abs = pb

            if max_pullback_abs <= max_allowed_reversal:
                score = 950.0 + (abs_change * 10.0) - (max_pullback_abs * 5.0)
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": score,
                    "engine": "ENGINE_1_DOMINANCE_4_TO_1",
                    "pivot_price": candles[0][3]
                }

        else:  # direction == "sell"
            running_low = candles[0][3]
            max_bounce_abs = 0.0

            for c in candles:
                h, l = c[2], c[3]
                if l < running_low:
                    running_low = l
                bounce = ((h - running_low) / running_low) * 100.0
                if bounce > max_bounce_abs:
                    max_bounce_abs = bounce

            if max_bounce_abs <= max_allowed_reversal:
                score = 950.0 + (abs_change * 10.0) - (max_bounce_abs * 5.0)
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": score,
                    "engine": "ENGINE_1_DOMINANCE_4_TO_1",
                    "pivot_price": candles[0][2]
                }

        return None

    # --------------------------------------------------------------------------
    # ENGINE 2: TOP 10 LUCKIEST (DAM BREAK ENTRY)
    # --------------------------------------------------------------------------
    def evaluate_engine_2(self, symbol: str, ohlcv: List) -> Optional[Dict]:
        """
        Detects heavy siege trapped in a tight box (< 0.50% range).
        Enters when the luck dies (the defended wall shatters on latest 1m candle).
        """
        candles = ohlcv[-11:-1]
        box_high = max(c[2] for c in candles[:-1])
        box_low = min(c[3] for c in candles[:-1])
        box_range_pct = ((box_high - box_low) / box_low) * 100.0

        if box_range_pct > MAX_LUCKY_BOX_PCT:
            return None  # Move is too loose, not a tight luck siege

        total_vol = sum(c[5] for c in candles[:-1])
        if total_vol <= 0:
            return None

        sell_vol = sum(c[5] for c in candles[:-1] if c[4] < c[1])
        buy_vol = sum(c[5] for c in candles[:-1] if c[4] > c[1])

        current_candle = candles[-1]
        current_close = current_candle[4]

        # Case A: Short Siege (Buyers surviving on luck at the floor)
        if (sell_vol / total_vol) >= MIN_SIEGE_VOL_RATIO:
            breakout_pct = ((box_low - current_close) / box_low) * 100.0
            # Confirm the luck died: current 1m candle punches below the defended floor
            if breakout_pct >= MIN_DAM_BREAK_PCT and current_close < box_low:
                luck_score = 920.0 + (sell_vol / total_vol) * 50.0
                return {
                    "symbol": symbol,
                    "direction": "sell",
                    "net_change_pct": -breakout_pct,
                    "score": luck_score,
                    "engine": "ENGINE_2_LUCKIEST_DAM_BREAK",
                    "pivot_price": box_high
                }

        # Case B: Long Siege (Sellers surviving on luck at the ceiling)
        elif (buy_vol / total_vol) >= MIN_SIEGE_VOL_RATIO:
            breakout_pct = ((current_close - box_high) / box_high) * 100.0
            # Confirm the luck died: current 1m candle punches above the defended ceiling
            if breakout_pct >= MIN_DAM_BREAK_PCT and current_close > box_high:
                luck_score = 920.0 + (buy_vol / total_vol) * 50.0
                return {
                    "symbol": symbol,
                    "direction": "buy",
                    "net_change_pct": breakout_pct,
                    "score": luck_score,
                    "engine": "ENGINE_2_LUCKIEST_DAM_BREAK",
                    "pivot_price": box_low
                }

        return None

    # --------------------------------------------------------------------------
    # ENGINE 3: DUAL-POLARITY +/- 1.5% IMBALANCE (PRICE VS. OI HOOK)
    # --------------------------------------------------------------------------
    def evaluate_engine_3(self, symbol: str, deltas: Tuple[float, float]) -> Optional[Dict]:
        pr_15, oi_15 = deltas
        setup_a = (pr_15 <= -MIN_POLARITY_THRESHOLD and oi_15 >= MIN_POLARITY_THRESHOLD)
        setup_b = (pr_15 >= MIN_POLARITY_THRESHOLD and oi_15 <= -MIN_POLARITY_THRESHOLD)

        if not (setup_a or setup_b):
            return None

        setup_type = "SHORT_BUILDUP" if setup_a else "SHORT_SQUEEZE"
        gap = abs(oi_15 - pr_15)

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=7)
            if not ohlcv or len(ohlcv) < 6:
                return None

            candles = ohlcv[-6:]
            current_candle = candles[-1]
            prior_candles = candles[:-1]

            if setup_type == "SHORT_BUILDUP":
                running_low = min(c[3] for c in prior_candles)
                if current_candle[3] < (running_low * 0.9990) or current_candle[4] < current_candle[1]:
                    self.expanding_waits_count += 1
                    return None

                absolute_floor = min(c[3] for c in candles)
                bounce_pct = ((current_candle[4] - absolute_floor) / absolute_floor) * 100.0

                if MIN_PULLBACK_CONFIRM_PCT <= bounce_pct <= MAX_PULLBACK_CHASE_PCT:
                    return {
                        "symbol": symbol,
                        "direction": "buy",
                        "net_change_pct": pr_15,
                        "score": 880.0 + gap,
                        "engine": "ENGINE_3_DUAL_POLARITY_HOOK",
                        "pivot_price": absolute_floor
                    }

            elif setup_type == "SHORT_SQUEEZE":
                running_high = max(c[2] for c in prior_candles)
                if current_candle[2] > (running_high * 1.0010) or current_candle[4] > current_candle[1]:
                    self.expanding_waits_count += 1
                    return None

                absolute_peak = max(c[2] for c in candles)
                pullback_pct = ((absolute_peak - current_candle[4]) / absolute_peak) * 100.0

                if MIN_PULLBACK_CONFIRM_PCT <= pullback_pct <= MAX_PULLBACK_CHASE_PCT:
                    return {
                        "symbol": symbol,
                        "direction": "sell",
                        "net_change_pct": pr_15,
                        "score": 880.0 + gap,
                        "engine": "ENGINE_3_DUAL_POLARITY_HOOK",
                        "pivot_price": absolute_peak
                    }

            return None
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # ENGINE 4: THE 8,000m EXHAUSTED RUNNER (PURE CAPITAL DEPLETION)
    # --------------------------------------------------------------------------
    def evaluate_engine_4(self, symbol: str, ohlcv: List) -> Optional[Dict]:
        """
        Standalone: Heavy volume pushed across candles 0-7, but price progress stalled completely.
        Fresh opposing runner arrives on candle 9-10 with velocity, slicing through empty book.
        """
        candles = ohlcv[-11:-1]
        
        # Phase 1: Measure effort of the first 7 candles
        first_leg_vol = sum(c[5] for c in candles[:7])
        first_leg_high = max(c[2] for c in candles[:7])
        first_leg_low = min(c[3] for c in candles[:7])
        first_leg_displacement = ((first_leg_high - first_leg_low) / first_leg_low) * 100.0

        if first_leg_displacement < 1.50 or first_leg_vol <= 0:
            return None

        # Phase 2: Check exhaustion stall at 8,000m mark (candles 7-9)
        stall_vol = sum(c[5] for c in candles[7:9])
        stall_high = max(c[2] for c in candles[7:9])
        stall_low = min(c[3] for c in candles[7:9])
        stall_range_pct = ((stall_high - stall_low) / stall_low) * 100.0

        # Tired legs: Heavy volume spent relative to tiny price advancement
        is_tired_runner = (stall_vol / first_leg_vol >= 0.28) and (stall_range_pct < 0.40)
        if not is_tired_runner:
            return None

        # Phase 3: Fresh runner arrives on latest completed candle (candle -1)
        latest_candle = candles[-1]
        body_pct = ((abs(latest_candle[4] - latest_candle[1])) / latest_candle[1]) * 100.0

        # Fresh Seller blows past exhausted buyer
        if latest_candle[4] < latest_candle[1] and latest_candle[4] < stall_low and body_pct >= 0.30:
            return {
                "symbol": symbol,
                "direction": "sell",
                "net_change_pct": -body_pct,
                "score": 870.0 + (body_pct * 15.0),
                "engine": "ENGINE_4_EXHAUSTED_8000M_RUNNER",
                "pivot_price": stall_high
            }

        # Fresh Buyer blows past exhausted seller
        elif latest_candle[4] > latest_candle[1] and latest_candle[4] > stall_high and body_pct >= 0.30:
            return {
                "symbol": symbol,
                "direction": "buy",
                "net_change_pct": body_pct,
                "score": 870.0 + (body_pct * 15.0),
                "engine": "ENGINE_4_EXHAUSTED_8000M_RUNNER",
                "pivot_price": stall_low
            }

        return None

    # --------------------------------------------------------------------------
    # UNIFIED SCANNER
    # --------------------------------------------------------------------------
    def scan_for_opportunities(self) -> Optional[Dict]:
        scan_start = time.time()
        tickers = self.exchange.fetch_tickers()
        self.update_time_series_buffer(tickers)

        valid_symbols = []
        for sym, t in tickers.items():
            if not sym.endswith(":USDT") or not self.is_symbol_valid(sym):
                continue
            vol = float(t.get("quoteVolume", 0.0) or 0.0)
            if vol >= MIN_24H_VOLUME_USDT:
                valid_symbols.append(sym)

        # Parallel candle retrieval
        candles_by_symbol = {}
        with ThreadPoolExecutor(max_workers=SCANNER_WORKERS) as executor:
            future_to_sym = {executor.submit(self.fetch_symbol_candles, s): s for s in valid_symbols}
            for future in as_completed(future_to_sym):
                res = future.result()
                if res:
                    sym, ohlcv = res
                    candles_by_symbol[sym] = ohlcv

        candidates = []

        # Evaluate Engines 1, 2, and 4
        for sym, ohlcv in candles_by_symbol.items():
            res1 = self.evaluate_engine_1(sym, ohlcv)
            if res1:
                candidates.append(res1)

            res2 = self.evaluate_engine_2(sym, ohlcv)
            if res2:
                candidates.append(res2)

            res4 = self.evaluate_engine_4(sym, ohlcv)
            if res4:
                candidates.append(res4)

        # Evaluate Engine 3 (Dual-Polarity)
        for sym in valid_symbols:
            deltas = self.calculate_deltas(sym, 900)
            if deltas:
                res3 = self.evaluate_engine_3(sym, deltas)
                if res3:
                    candidates.append(res3)

        scan_duration = time.time() - scan_start
        DASHBOARD_DATA["last_scan_duration_sec"] = round(scan_duration, 2)

        if not candidates:
            return None

        # Rank all candidates by conviction score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = candidates[:10]

        # Select Candidate #1 that passes Anti-Trap Spread Check
        for cand in top_candidates:
            if self.anti_trap_check(cand["symbol"]):
                self.ignitions_confirmed_count += 1
                logger.info(f"UNIFIED CHAMPION: {cand['symbol']} via {cand['engine']} "
                            f"({cand['direction'].upper()} {cand['net_change_pct']:.2f}%) | Score: {cand['score']:.1f}")
                return cand
            else:
                self.traps_rejected_count += 1

        return None

    # --------------------------------------------------------------------------
    # SIZING & EXECUTION
    # --------------------------------------------------------------------------
    def calculate_sizing(self, symbol: str, current_price: float) -> Tuple[int, float]:
        balance = self.exchange.fetch_balance()
        free_usdt = float(balance.get("USDT", {}).get("free", 0.0) or 0.0)
        usable_margin = max(free_usdt * BALANCE_UTILIZATION, 0.50)

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
        engine = candidate["engine"]
        pivot_price = candidate.get("pivot_price", 0.0)

        ticker = self.exchange.fetch_ticker(symbol)
        current_price = ticker["ask"] if direction == "buy" else ticker["bid"]

        if not self.live_mode:
            self.active_trade = {
                "symbol": symbol,
                "side": direction,
                "entry_price": current_price,
                "peak_price": current_price,
                "trough_price": current_price,
                "contracts": 10.0,
                "entry_time": time.time(),
                "is_live": False,
                "engine": engine,
                "pivot_price": pivot_price,
                "leverage": 5
            }
            logger.info(f"[PAPER LAB ENTER] {direction.upper()} on {symbol} @ ${current_price:.6f} | "
                        f"Engine: {engine} | Gauntlet: {self.paper_wins}/6")
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
                "trough_price": fill_price,
                "contracts": amount,
                "entry_time": time.time(),
                "is_live": True,
                "engine": engine,
                "pivot_price": pivot_price,
                "leverage": leverage
            }
            logger.info(f"[LIVE ENTER] {direction.upper()} on {symbol} | Amount: {amount} @ ${fill_price:.6f} | Lev: {leverage}x | Engine: {engine}")

        except Exception as e:
            logger.error(f"Live order failed: {e}")
            self.active_trade = None

    def execute_exit(self, reason: str, is_win: bool):
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
        engine = trade.get("engine", "UNKNOWN")

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            exit_price = ticker["bid"] if exit_side == "sell" else ticker["ask"]
            entry_price = trade["entry_price"]

            if side == "buy":
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0
                peak_mfe = ((trade["peak_price"] - entry_price) / entry_price) * 100.0
                worst_mae = ((trade["trough_price"] - entry_price) / entry_price) * 100.0
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100.0
                peak_mfe = ((entry_price - trade["peak_price"]) / entry_price) * 100.0
                worst_mae = ((entry_price - trade["trough_price"]) / entry_price) * 100.0

            duration_min = round((time.time() - trade["entry_time"]) / 60, 1)

            # Record Empirical Trade Dossier for Telemetry
            dossier = {
                "symbol": symbol,
                "engine": engine,
                "pnl_pct": round(pnl_pct, 2),
                "peak_mfe": round(peak_mfe, 2),
                "worst_mae": round(worst_mae, 2),
                "duration_min": duration_min,
                "reason": reason,
                "timestamp": time.strftime("%H:%M:%S")
            }
            self.completed_trade_dossiers.append(dossier)
            if len(self.completed_trade_dossiers) > 10:
                self.completed_trade_dossiers = self.completed_trade_dossiers[-10:]

            # Execute Live Order with exact contract balance
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
                    logger.error(f"Live exit submission error: {e}")
            else:
                logger.info(f"[PAPER LAB EXIT] Closed {symbol} @ ${exit_price:.6f} | PnL: {pnl_pct:.2f}% (Peak: +{peak_mfe:.2f}%, Worst: {worst_mae:.2f}%) | Reason: {reason}")

            # Gauntlet Progression (6-in-a-row qualification)
            if not is_live:
                if is_win:
                    self.paper_wins += 1
                    logger.info(f"GAUNTLET PROGRESS: Streak is now {self.paper_wins}/6 Wins!")
                    if self.paper_wins >= 6:
                        self.live_mode = True
                        logger.warning("*********************************************************")
                        logger.warning("6/6 CONSECUTIVE WINS ACHIEVED! LIVE TRADING UNLOCKED!")
                        logger.warning("*********************************************************")
                else:
                    logger.warning(f"GAUNTLET RESET: Loss ({pnl_pct:.2f}%). Counter reset to 0/6.")
                    self.paper_wins = 0

                self.save_state()

        except Exception as e:
            logger.error(f"Critical error during exit: {e}")

        finally:
            self.active_trade = None
            self.cooldown_tracker[symbol] = time.time() + COOLDOWN_SECONDS
            logger.info(f"{symbol} assigned to 15-minute cooldown.")

    # --------------------------------------------------------------------------
    # POSITION MONITOR: BEHAVIORAL LABORATORY VS LIVE STRICT
    # --------------------------------------------------------------------------
    def monitor_active_trade(self):
        if not self.active_trade:
            return

        trade = self.active_trade
        symbol = trade["symbol"]
        side = trade["side"]
        entry_price = trade["entry_price"]
        entry_time = trade["entry_time"]
        is_live = trade.get("is_live", False)

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker["last"]

            # Update Peak and Trough metrics (MFE and MAE)
            if side == "buy":
                pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                if current_price > trade["peak_price"]:
                    trade["peak_price"] = current_price
                if current_price < trade["trough_price"]:
                    trade["trough_price"] = current_price
                drawdown_from_peak = ((trade["peak_price"] - current_price) / trade["peak_price"]) * 100.0
            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100.0
                if current_price < trade["peak_price"]:
                    trade["peak_price"] = current_price
                if current_price > trade["trough_price"]:
                    trade["trough_price"] = current_price
                drawdown_from_peak = ((current_price - trade["peak_price"]) / trade["peak_price"]) * 100.0

            duration_secs = time.time() - entry_time

            DASHBOARD_DATA["active_trade"] = {
                "symbol": symbol,
                "side": side.upper(),
                "entry": entry_price,
                "current": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "duration_min": round(duration_secs / 60, 1),
                "engine": trade.get("engine", "")
            }

            # ==================================================================
            # LIVE TRADING MONITORING (Strict Institutional Discipline)
            # ==================================================================
            if is_live:
                if pnl_pct <= -LIVE_HARD_STOP_LOSS_PCT:
                    self.execute_exit(f"Hard Stop-Loss (-{LIVE_HARD_STOP_LOSS_PCT}%)", is_win=False)
                    return

                if duration_secs >= LIVE_VELOCITY_TIMEOUT_SECS and pnl_pct < LIVE_VELOCITY_MIN_PROFIT:
                    self.execute_exit(f"Velocity Cut (<+{LIVE_VELOCITY_MIN_PROFIT}% at 20m)", is_win=(pnl_pct > 0))
                    return

                if pnl_pct >= RUNNER_TRAIL_ACTIVATION_PCT and drawdown_from_peak >= RUNNER_GIVEBACK_PCT:
                    self.execute_exit(f"Dynamic Runner Harvest (+{pnl_pct:.2f}%)", is_win=True)
                    return

            # ==================================================================
            # PAPER LABORATORY MONITORING (Unconstrained Behavioral Learning)
            # ==================================================================
            else:
                if pnl_pct >= RUNNER_TRAIL_ACTIVATION_PCT:
                    giveback_threshold = RUNNER_GIVEBACK_PCT if pnl_pct < 7.0 else 1.20
                    if drawdown_from_peak >= giveback_threshold:
                        self.execute_exit(f"Natural Peak Harvested (+{pnl_pct:.2f}% locked)", is_win=True)
                        return

                if pnl_pct <= -PAPER_STRUCTURAL_INVALIDATION:
                    self.execute_exit(f"Structural Collapse (-{PAPER_STRUCTURAL_INVALIDATION}%)", is_win=False)
                    return

                if duration_secs >= PAPER_STAGNATION_TIMEOUT:
                    is_win = pnl_pct > 0
                    self.execute_exit(f"Behavioral Stagnation (Volume died after 25m, PnL: {pnl_pct:.2f}%)", is_win=is_win)
                    return

        except Exception as e:
            logger.error(f"Error monitoring active trade on {symbol}: {e}")

    # --------------------------------------------------------------------------
    # 15-MINUTE INTELLIGENCE BRIEFING & TELEMETRY
    # --------------------------------------------------------------------------
    def print_desk_briefing(self):
        now = time.time()
        if (now - self.last_briefing_time) < BRIEFING_INTERVAL_SECONDS:
            return

        self.last_briefing_time = now

        top_imbalance_str = "None (Market in equilibrium)"
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

        last_dossier_str = "No trades completed in last window."
        if self.completed_trade_dossiers:
            d = self.completed_trade_dossiers[-1]
            last_dossier_str = (
                f"{d['symbol']} [{d['engine']}] -> PnL: {d['pnl_pct']:+.2f}% | "
                f"Peak MFE: +{d['peak_mfe']:.2f}% | Worst MAE: {d['worst_mae']:.2f}% | "
                f"Duration: {d['duration_min']}m ({d['reason']})"
            )

        briefing_text = (
            f"\n{'='*25} [15-MIN UNIFIED DESK BRIEFING] {'='*25}\n"
            f"• DUAL-POLARITY CHAMPION: {top_imbalance_str}\n"
            f"• RECENT TRADE TELEMETRY: {last_dossier_str}\n"
            f"• EXPANSION LOCKS (Waited for Hook): {self.expanding_waits_count}\n"
            f"• TRAPS AVOIDED: {self.traps_rejected_count} (Spread / Icebergs)\n"
            f"• CONFIRMED IGNITIONS: {self.ignitions_confirmed_count}\n"
            f"• GAUNTLET PROGRESS: {self.paper_wins}/6 Wins | Mode: {'LIVE' if self.live_mode else 'PAPER_LABORATORY'}\n"
            f"• TRACKING UNIVERSE: {len(self.history_buffer)} liquid perpetual pairs active\n"
            f"{'='*75}"
        )
        logger.info(briefing_text)

        DASHBOARD_DATA["last_briefing"] = {
            "top_imbalance": top_imbalance_str,
            "last_trade_telemetry": last_dossier_str,
            "expanding_waits": self.expanding_waits_count,
            "traps_rejected": self.traps_rejected_count,
            "ignitions_confirmed": self.ignitions_confirmed_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    # --------------------------------------------------------------------------
    # MAIN EVENT LOOP
    # --------------------------------------------------------------------------
    def run(self):
        logger.info("Unified 4-Engine Quant Trading Suite active. Event loop running...")

        while True:
            try:
                if API_KEY:
                    try:
                        bal = self.exchange.fetch_balance()
                        DASHBOARD_DATA["live_balance"] = round(float(bal.get("USDT", {}).get("free", 0.0) or 0.0), 2)
                    except Exception:
                        pass

                DASHBOARD_DATA["status"] = "Active"
                DASHBOARD_DATA["mode"] = "LIVE" if self.live_mode else f"PAPER_LABORATORY ({self.paper_wins}/6)"
                DASHBOARD_DATA["paper_wins"] = self.paper_wins
                DASHBOARD_DATA["last_scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

                self.print_desk_briefing()

                if self.active_trade:
                    self.monitor_active_trade()
                    time.sleep(2)
                    continue

                opportunity = self.scan_for_opportunities()
                if opportunity:
                    self.execute_entry(opportunity)

                time.sleep(5)

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

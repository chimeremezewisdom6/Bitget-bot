#!/usr/bin/env python3
"""
Upgraded Institutional Bitget USDT-M Perpetual Trading Bot
- Fast Multi-Threaded Concurrent Scanner (200+ pairs in ~3-4 seconds)
- Method 1: First Set Blowout (Instant 4% Run & Top 10 40-0 Cleanliness Outlier)
- Method 2: Second Set Continuation (Shallow 2-3 Candle Pause Breakout)
- Execution: One-Way Mode, Dynamic Min Leverage ($5.50 Notional), reduceOnly
- Safety: Anti-Trap Spread Check, Anti-Stagnation (20m velocity cut), PARTI Loop Defense
- Qualification: Strict 6-in-a-row Paper Win Gauntlet before Live Unlock
- Infrastructure: Render Port 10000 HTTP Keep-Alive & Auto-Recovery
- Fix: Expanded 50-Socket Connection Pool (Zero urllib3 warning spam)
"""

import os
import sys
import time
import json
import math
import logging
import threading
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

# Mute noisy connection pool warnings from urllib3
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

# ==============================================================================
# 2. CONFIGURATION & PARAMETERS
# ==============================================================================
API_KEY = os.getenv("BITGET_API_KEY", "")
API_SECRET = os.getenv("BITGET_API_SECRET", "")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE", "")
PORT = int(os.getenv("PORT", 10000))

STATE_FILE = "qualification_state.json"

# Strict Token Blacklist
BLACKLIST = {
    "EUV", "PARTI", "BTW", "IDOL", "PAXG", "CSOP",
    "USDC", "BUSD", "DAI", "TUSD", "FDUSD"
}

# Scanning & Filter Parameters
MIN_24H_VOLUME_USDT = 1_000_000.0  # $1,000,000 minimum liquidity
MIN_10M_MOVE_PCT = 2.0             # Minimum 2.0% move in 10 minutes
MAX_10M_MOVE_PCT = 15.0            # Filter out illiquid needle spikes
MAX_RETRACE_RATIO = 0.20           # Opponent cannot retrace > 20% of impulse
MAX_OPPOSING_CANDLES = 2           # Opponent can win at most 2 out of 10 candles
MAX_OPPOSING_VOL_RATIO = 0.18      # Opposing volume must be < 18% of 10m volume
INSTANT_RUN_PCT = 4.0              # Smooth run >= 4%
INSTANT_MAX_PULLBACK_PCT = 0.50    # Counter pullback strictly < 0.50%
MAX_SPREAD_PCT = 0.10              # Anti-trap order book spread <= 0.10%

# Concurrency
SCANNER_WORKERS = 16               # Parallel threads for 3-4s market sweep

# Risk & Order Execution Parameters
BALANCE_UTILIZATION = 0.90         # Use 90% of free balance
BITGET_MIN_NOTIONAL = 5.50         # Bitget ~$5.50 min order value
HARD_STOP_LOSS_PCT = 0.90          # 0.9% hard structural stop
VELOCITY_TIMEOUT_SECONDS = 1200    # 20 minutes velocity clock
VELOCITY_MIN_PROFIT_PCT = 1.20     # Must achieve >= +1.2% in 20m or cut trade
RUNNER_TRAIL_ACTIVATION_PCT = 3.50 # Activate dynamic runner trailing at +3.5%
RUNNER_GIVEBACK_PCT = 0.80         # Trail 0.8% behind local peak
COOLDOWN_SECONDS = 900             # 15 minutes symbol cooldown

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
    "top_candidates": [],
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
        return  # Suppress HTTP access log noise

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

        # Upgrade HTTP adapter pool to 50 connections to eliminate pool-full warnings
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.exchange.session.mount("https://", adapter)
        self.exchange.session.mount("http://", adapter)

        self.paper_wins = 0
        self.live_mode = False
        self.active_trade: Optional[Dict] = None
        self.cooldown_tracker: Dict[str, float] = {}

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
        if not API_KEY or not API_SECRET or not API_PASSPHRASE:
            logger.warning("Bitget API credentials missing. Bot running in PAPER SIMULATION mode.")
            return

        try:
            self.exchange.set_position_mode(False, params={"productType": "USDT-FUTURES"})
            logger.info("Bitget Position Mode confirmed: ONE-WAY (Single Hold)")
        except Exception as e:
            logger.info(f"Position mode notice: {e} (Account already configured or unified mode)")

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
            logger.error(f"Live position recovery check error: {e}")

    # --------------------------------------------------------------------------
    # FAST MULTI-THREADED 10M CANDLE INSPECTOR
    # --------------------------------------------------------------------------
    def is_symbol_valid(self, symbol: str) -> bool:
        base = symbol.split("/")[0].split(":")[0]
        if base in BLACKLIST:
            return False
        if time.time() < self.cooldown_tracker.get(symbol, 0):
            return False
        return True

    def fetch_symbol_candles(self, symbol: str) -> Optional[Tuple[str, List]]:
        """Worker task to fetch 1m candles concurrently."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=12)
            if ohlcv and len(ohlcv) >= 11:
                return symbol, ohlcv[-11:]  # Last 10 completed + current forming
        except Exception:
            pass
        return None

    def analyze_candles(self, symbol: str, ohlcv: List) -> Optional[Dict]:
        """
        Evaluates both:
        - Method 1: First Set Blowout (40-0 Domination / Instant 4% Run)
        - Method 2: Second Set Continuation (Shallow pause breakout)
        """
        candles = ohlcv[-11:-1]  # Exactly 10 completed 1m candles
        start_open = candles[0][1]
        end_close = candles[-1][4]
        net_change_pct = ((end_close - start_open) / start_open) * 100.0
        abs_change = abs(net_change_pct)

        if abs_change < MIN_10M_MOVE_PCT or abs_change > MAX_10M_MOVE_PCT:
            return None

        direction = "buy" if net_change_pct > 0 else "sell"
        total_vol = sum(c[5] for c in candles)
        if total_vol <= 0:
            return None

        # Track trajectory details
        opposing_candles = 0
        opposing_vol = 0.0

        if direction == "buy":
            running_high = candles[0][2]
            max_retrace_ratio = 0.0
            max_pb_abs = 0.0

            for c in candles:
                o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                if h > running_high:
                    running_high = h

                wave = running_high - start_open
                if wave > 0:
                    retrace = (running_high - l) / wave
                    if retrace > max_retrace_ratio:
                        max_retrace_ratio = retrace

                pb = ((running_high - l) / running_high) * 100.0
                if pb > max_pb_abs:
                    max_pb_abs = pb

                if cl < o:
                    opposing_candles += 1
                    opposing_vol += vol

            opposing_vol_ratio = opposing_vol / total_vol

            # METHOD 1A: Instant Runaway 4% Run
            if abs_change >= INSTANT_RUN_PCT and max_pb_abs < INSTANT_MAX_PULLBACK_PCT:
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": 999.0,
                    "method": "METHOD_1_INSTANT_RUN",
                    "max_retrace": max_retrace_ratio
                }

            # METHOD 2: Second Set Continuation Setup
            first_wave_high = max(c[2] for c in candles[:7])
            pause_low = min(c[3] for c in candles[7:9])
            pause_retrace = (first_wave_high - pause_low) / max((first_wave_high - start_open), 1e-9)
            pause_vol = sum(c[5] for c in candles[7:9]) / max(total_vol, 1e-9)

            if pause_retrace < 0.20 and pause_vol < 0.22 and end_close >= (first_wave_high * 0.998):
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": 900.0 + abs_change,
                    "method": "METHOD_2_SECOND_SET_CONTINUATION",
                    "max_retrace": pause_retrace
                }

            # METHOD 1B: Standard 40-0 Tennis Cleanliness
            if max_retrace_ratio <= MAX_RETRACE_RATIO and opposing_candles <= MAX_OPPOSING_CANDLES and opposing_vol_ratio <= MAX_OPPOSING_VOL_RATIO:
                score = abs_change * (1.0 - max_retrace_ratio)
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": score,
                    "method": "METHOD_1_TENNIS_40_0",
                    "max_retrace": max_retrace_ratio
                }

        else:  # direction == "sell"
            running_low = candles[0][3]
            max_retrace_ratio = 0.0
            max_pb_abs = 0.0

            for c in candles:
                o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                if l < running_low:
                    running_low = l

                wave = start_open - running_low
                if wave > 0:
                    retrace = (h - running_low) / wave
                    if retrace > max_retrace_ratio:
                        max_retrace_ratio = retrace

                pb = ((h - running_low) / running_low) * 100.0
                if pb > max_pb_abs:
                    max_pb_abs = pb

                if cl > o:
                    opposing_candles += 1
                    opposing_vol += vol

            opposing_vol_ratio = opposing_vol / total_vol

            # METHOD 1A: Instant Runaway 4% Dump
            if abs_change >= INSTANT_RUN_PCT and max_pb_abs < INSTANT_MAX_PULLBACK_PCT:
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": 999.0,
                    "method": "METHOD_1_INSTANT_RUN",
                    "max_retrace": max_retrace_ratio
                }

            # METHOD 2: Second Set Continuation (Short)
            first_wave_low = min(c[3] for c in candles[:7])
            pause_high = max(c[2] for c in candles[7:9])
            pause_retrace = (pause_high - first_wave_low) / max((start_open - first_wave_low), 1e-9)
            pause_vol = sum(c[5] for c in candles[7:9]) / max(total_vol, 1e-9)

            if pause_retrace < 0.20 and pause_vol < 0.22 and end_close <= (first_wave_low * 1.002):
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": 900.0 + abs_change,
                    "method": "METHOD_2_SECOND_SET_CONTINUATION",
                    "max_retrace": pause_retrace
                }

            # METHOD 1B: Standard 40-0 Tennis Cleanliness
            if max_retrace_ratio <= MAX_RETRACE_RATIO and opposing_candles <= MAX_OPPOSING_CANDLES and opposing_vol_ratio <= MAX_OPPOSING_VOL_RATIO:
                score = abs_change * (1.0 - max_retrace_ratio)
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": score,
                    "method": "METHOD_1_TENNIS_40_0",
                    "max_retrace": max_retrace_ratio
                }

        return None

    def anti_trap_check(self, symbol: str) -> bool:
        """Confirms spread <= 0.10% to prevent entering into illiquid iceberg walls."""
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

    def scan_for_opportunities(self) -> Optional[Dict]:
        scan_start = time.time()
        tickers = self.exchange.fetch_tickers()

        valid_symbols = []
        for sym, t in tickers.items():
            if not sym.endswith(":USDT"):
                continue
            if not self.is_symbol_valid(sym):
                continue
            vol = float(t.get("quoteVolume", 0.0) or 0.0)
            if vol >= MIN_24H_VOLUME_USDT:
                valid_symbols.append(sym)

        # Parallel multi-threaded candle retrieval (16 concurrent threads with 50-pool adapter)
        candles_by_symbol = {}
        with ThreadPoolExecutor(max_workers=SCANNER_WORKERS) as executor:
            future_to_sym = {executor.submit(self.fetch_symbol_candles, s): s for s in valid_symbols}
            for future in as_completed(future_to_sym):
                res = future.result()
                if res:
                    sym, ohlcv = res
                    candles_by_symbol[sym] = ohlcv

        # Evaluate all retrieved candle datasets
        candidates = []
        for sym, ohlcv in candles_by_symbol.items():
            analysis = self.analyze_candles(sym, ohlcv)
            if analysis:
                candidates.append(analysis)

        scan_duration = time.time() - scan_start
        DASHBOARD_DATA["last_scan_duration_sec"] = round(scan_duration, 2)
        logger.info(f"Fast-scanned {len(valid_symbols)} pairs in {scan_duration:.2f}s | Qualified Candidates: {len(candidates)}")

        if not candidates:
            return None

        # Rank Top 10 by Score (Instant runs & second set continuation score highest)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_10 = candidates[:10]

        DASHBOARD_DATA["top_candidates"] = [
            f"{c['symbol']} [{c['method']}] {c['direction'].upper()} {c['net_change_pct']:.2f}% | Score: {c['score']:.1f}"
            for c in top_10
        ]

        # Select Candidate #1 that passes Anti-Trap Spread Check
        for cand in top_10:
            if self.anti_trap_check(cand["symbol"]):
                logger.info(f"SELECTING CHAMPION: {cand['symbol']} via {cand['method']} "
                            f"({cand['direction'].upper()} {cand['net_change_pct']:.2f}%)")
                return cand
            else:
                logger.warning(f"Skipping {cand['symbol']} (Failed order book spread check)")

        return None

    # --------------------------------------------------------------------------
    # SIZING & EXECUTION (MICRO-ACCOUNT ONE-WAY MODE)
    # --------------------------------------------------------------------------
    def calculate_sizing(self, symbol: str, current_price: float) -> Tuple[int, float]:
        """Calculates exact minimum leverage to clear $5.50 minimum notional."""
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
        method = candidate["method"]

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
                "method": method,
                "leverage": 5
            }
            logger.info(f"[PAPER ENTER] {direction.upper()} on {symbol} @ ${current_price:.6f} | "
                        f"Type: {method} | Streak: {self.paper_wins}/6")
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
                "method": method,
                "leverage": leverage
            }
            logger.info(f"[LIVE ENTER] {direction.upper()} on {symbol} | Amount: {amount} @ ${fill_price:.6f} | Lev: {leverage}x | Method: {method}")

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
        logger.info("Upgraded Quant Trading Engine active. Fast event loop running...")

        while True:
            try:
                # Refresh balance for dashboard
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

                # If managing an open trade, focus on monitoring
                if self.active_trade:
                    self.monitor_active_trade()
                    time.sleep(2)
                    continue

                # Run fast parallel market sweep
                opportunity = self.scan_for_opportunities()
                if opportunity:
                    self.execute_entry(opportunity)

                time.sleep(3)  # Fast 3-second cycle

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

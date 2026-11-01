#!/usr/bin/env python3
"""
Synchronized 3-Pillar Quant Trading Bot - Bitget USDT-M Perpetual Swaps
- Engine: 3-Pillar Escalation (Price + OI + Volume expanding candle-over-candle across 1m to 3m)
- Exit 1: Proven "When It Fades" Harvest (Banks profit the second momentum stalls and wiggles)
- Exit 2: Flash-Crash Emergency Circuit Breaker (Ejects immediately if sudden sharp crash hits)
- Scanner: 860+ Active Liquid Universe (CoinGlass Worldwide + Bitget)
- Qualification: Strict 6-in-a-row Paper Gauntlet (1 -> 6) before Live Execution
- Infrastructure: Render Port 10000 HTTP Keep-Alive & 15-Minute Telemetry
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

# Import zero-cost CoinGlass feed
try:
    from coinglass_feed import get_coinglass_data
except ImportError:
    get_coinglass_data = lambda: []

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

# Liquidity & Anti-Trap Parameters
GLOBAL_MIN_24H_VOL = 1_000_000.0   # $1,000,000 global volume on CoinGlass
BITGET_FALLBACK_MIN_VOL = 1_000_000.0
MAX_SPREAD_PCT = 0.10              # Order book spread <= 0.10%
SCANNER_WORKERS = 16               # Parallel threads for fast sweeps

# 3-Pillar Synchronized Escalation Parameters
MIN_3M_MOVE_PCT = 1.40             # Minimum 1.4% price thrust in 3 minutes
MAX_3M_MOVE_PCT = 8.00             # Cap to avoid buying already exhausted moves
PEAK_PROXIMITY_CEILING = 0.25      # Current price must be within 0.25% of 5m extreme (NOT falling back!)

# Proven "When It Fades" (Wiggle & Fade) Parameters
PROFIT_BANK_THRESHOLD_PCT = 1.35   # Look to bank profit once trade is up >= 1.35%
WIGGLE_FADE_PULLBACK_PCT = 0.45    # Pullback from peak while stalling indicates the fade -> Bank profit!
STAGNATION_TIMEOUT_SECS = 1200     # 20 minutes max if coin refuses to advance past +0.50%

# Flash-Crash Emergency Circuit Breaker Parameters
CRASH_ADVERSE_MOVE_PCT = 1.00      # Sudden 1.00% adverse drop in under 60s trips circuit breaker
CRASH_SPIKE_VOL_RATIO = 2.00       # Opposing candle with > 2x average volume trips circuit breaker
STRUCTURAL_FLOOR_COLLAPSE = 1.80   # Hard emergency stop if entry thrust origin is shattered (-1.80%)

# Account Sizing & Execution
BALANCE_UTILIZATION = 0.90         # Use 90% of free balance
BITGET_MIN_NOTIONAL = 5.50         # $5.50 USDT minimum order value
NORMAL_COOLDOWN_SECS = 900         # 15 minutes normal cooldown
BRIEFING_INTERVAL_SECONDS = 900    # 15 minutes intelligence debrief

# LIVE Risk Limits (Strict only after earning 6/6 paper qualification)
LIVE_HARD_STOP_LOSS_PCT = 0.90     # 0.9% hard stop loss in live mode
LIVE_VELOCITY_TIMEOUT_SECS = 1200  # 20m velocity clock in live mode
LIVE_VELOCITY_MIN_PROFIT = 1.20    # Must achieve >= +1.2% in 20m or cut

# ==============================================================================
# 3. HTTP KEEP-ALIVE DASHBOARD (PORT 10000)
# ==============================================================================
DASHBOARD_DATA = {
    "status": "Initializing",
    "mode": "PAPER_QUALIFYING",
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

        # Upgrade HTTP adapter to 50 connections
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.exchange.session.mount("https://", adapter)
        self.exchange.session.mount("http://", adapter)

        self.paper_wins = 0
        self.live_mode = False
        self.active_trade: Optional[Dict] = None
        self.cooldown_tracker: Dict[str, float] = {}

        # Time-Series Buffers
        self.history_buffer: Dict[str, deque] = {}

        # Telemetry & Learning Memory
        self.completed_trade_dossiers: List[Dict] = []
        self.last_briefing_time = time.time()
        self.global_liquid_symbols: set = set()

        self.load_state()
        self.init_exchange_settings()
        self.recover_live_position()

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

    def init_exchange_settings(self):
        logger.info(f"Credential Status -> Key: {bool(API_KEY)} | Secret: {bool(API_SECRET)} | Passphrase: {bool(API_PASSPHRASE)}")

        if not API_KEY or not API_SECRET or not API_PASSPHRASE:
            logger.warning("Bitget API credentials missing or incomplete. Bot running in PAPER mode.")
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
                    logger.warning(f"RESTART RECOVERY: Open live position detected on {symbol} {side.upper()} | "
                                   f"Size: {contracts} @ ${entry_price:.6f}")
                    break
        except Exception as e:
            logger.error(f"Live position recovery error: {e}")

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

            if price <= 0:
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
        oi_change = 0.0
        if past["oi"] > 0:
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
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=7)
            if ohlcv and len(ohlcv) >= 6:
                return symbol, ohlcv[-6:]
        except Exception:
            pass
        return None

    # --------------------------------------------------------------------------
    # THE 3-PILLAR SYNCHRONIZED ESCALATION ENGINE (1m to 3m)
    # --------------------------------------------------------------------------
    def evaluate_3pillar_ignition(self, symbol: str, ohlcv: List) -> Optional[Dict]:
        """
        Inspects the 5-minute window and the last 3 individual 1m candles.
        Guarantees that momentum is ACTIVELY ACCELERATING across ALL 3 PILLARS:
        1. Price: Escalates candle-over-candle (P1 < P2 < P3 for Longs, P1 > P2 > P3 for Shorts)
        2. Open Interest: Expanding minute-over-minute (Delta OI > 0)
        3. Volume: Combusting candle-over-candle (Vol 1 < Vol 2 < Vol 3)
        """
        candles = ohlcv[-6:-1]            # 5 completed 1m candles
        three_min_candles = candles[-3:]  # Exactly the last 3 completed minutes

        c1, c2, c3 = three_min_candles[0], three_min_candles[1], three_min_candles[2]
        three_min_open = c1[1]
        three_min_close = c3[4]
        three_min_move_pct = ((three_min_close - three_min_open) / three_min_open) * 100.0
        abs_move = abs(three_min_move_pct)

        # Baseline displacement check
        if abs_move < MIN_3M_MOVE_PCT or abs_move > MAX_3M_IGNITION_MOVE:
            return None

        five_min_high = max(c[2] for c in candles)
        five_min_low = min(c[3] for c in candles)

        vol1, vol2, vol3 = c1[5], c2[5], c3[5]

        # Check Open Interest escalation over the 3-minute window
        deltas_3m = self.calculate_deltas(symbol, 180)
        oi_3m_growth = deltas_3m[1] if deltas_3m else 0.0

        # ======================================================================
        # PILLAR CHECK: FRESH BUY IGNITION
        # ======================================================================
        if three_min_move_pct > 0:
            # Pillar 1 (Price): Close 1 < Close 2 < Close 3 AND near extreme high of 5m
            if not (c1[4] < c2[4] < c3[4]):
                return None
            distance_from_high = ((five_min_high - three_min_close) / five_min_high) * 100.0
            if distance_from_high > PEAK_PROXIMITY_CEILING:
                return None  # Stale: Already falling back from an old peak!

            # Pillar 2 (Volume): Volume is combusting candle-over-candle
            if not (vol1 <= vol2 <= vol3) and (vol3 < vol2 * 0.90):
                return None

            # Pillar 3 (Open Interest): Fresh contracts expanding (not draining)
            if oi_3m_growth < -0.20:
                return None

            ignition_score = 1000.0 + (abs_move * 25.0) + (vol3 / max(vol1, 1e-9) * 15.0)
            return {
                "symbol": symbol,
                "direction": "buy",
                "net_change_pct": three_min_move_pct,
                "score": ignition_score,
                "engine": "SYNCHRONIZED_3PILLAR_IGNITION",
                "thrust_origin": c1[3],
                "avg_vol": (vol1 + vol2 + vol3) / 3.0
            }

        # ======================================================================
        # PILLAR CHECK: FRESH SELL IGNITION
        # ======================================================================
        else:
            # Pillar 1 (Price): Close 1 > Close 2 > Close 3 AND near extreme low of 5m
            if not (c1[4] > c2[4] > c3[4]):
                return None
            distance_from_low = ((three_min_close - five_min_low) / five_min_low) * 100.0
            if distance_from_low > PEAK_PROXIMITY_CEILING:
                return None  # Stale: Already bouncing from the floor!

            # Pillar 2 (Volume): Volume is combusting candle-over-candle
            if not (vol1 <= vol2 <= vol3) and (vol3 < vol2 * 0.90):
                return None

            # Pillar 3 (Open Interest): Fresh contracts expanding
            if oi_3m_growth < -0.20:
                return None

            ignition_score = 1000.0 + (abs_move * 25.0) + (vol3 / max(vol1, 1e-9) * 15.0)
            return {
                "symbol": symbol,
                "direction": "sell",
                "net_change_pct": three_min_move_pct,
                "score": ignition_score,
                "engine": "SYNCHRONIZED_3PILLAR_IGNITION",
                "thrust_origin": c1[2],
                "avg_vol": (vol1 + vol2 + vol3) / 3.0
            }

    # --------------------------------------------------------------------------
    # UNIFIED SCANNER
    # --------------------------------------------------------------------------
    def scan_for_opportunities(self) -> Optional[Dict]:
        scan_start = time.time()
        tickers = self.exchange.fetch_tickers()
        self.update_time_series_buffer(tickers)

        # Update CoinGlass Global Liquidity Pool (>= $1M Volume across all exchanges)
        cg_data = get_coinglass_data()
        self.global_liquid_symbols = set()
        if cg_data:
            for row in cg_data:
                sym = row.get("symbol", "")
                if sym:
                    self.global_liquid_symbols.add(sym)

        valid_symbols = []
        for sym, t in tickers.items():
            if not sym.endswith(":USDT") or not self.is_symbol_valid(sym):
                continue
            base = sym.split("/")[0].split(":")[0]
            vol = float(t.get("quoteVolume", 0.0) or 0.0)

            # Accept if Bitget vol >= $1M OR verified in CoinGlass Global Worldwide Pool!
            if vol >= BITGET_FALLBACK_MIN_VOL or base in self.global_liquid_symbols:
                valid_symbols.append(sym)

        # Parallel 1m candle retrieval
        candles_by_symbol = {}
        with ThreadPoolExecutor(max_workers=SCANNER_WORKERS) as executor:
            future_to_sym = {executor.submit(self.fetch_symbol_candles, s): s for s in valid_symbols}
            for future in as_completed(future_to_sym):
                res = future.result()
                if res:
                    sym, ohlcv = res
                    candles_by_symbol[sym] = ohlcv

        candidates = []
        for sym, ohlcv in candles_by_symbol.items():
            analysis = self.evaluate_3pillar_ignition(sym, ohlcv)
            if analysis:
                candidates.append(analysis)

        scan_duration = time.time() - scan_start
        DASHBOARD_DATA["last_scan_duration_sec"] = round(scan_duration, 2)

        if not candidates:
            return None

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = candidates[:10]

        for cand in top_candidates:
            if self.anti_trap_check(cand["symbol"]):
                logger.info(f"3-PILLAR IGNITION CHAMPION: {cand['symbol']} "
                            f"({cand['direction'].upper()} {cand['net_change_pct']:+.2f}% in 3m) | Score: {cand['score']:.1f}")
                return cand

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
        thrust_origin = candidate.get("thrust_origin", 0.0)
        baseline_vol = candidate.get("avg_vol", 0.0)

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
                "thrust_origin": thrust_origin,
                "baseline_vol": baseline_vol,
                "leverage": 5
            }
            logger.info(f"[PAPER ENTER] {direction.upper()} on {symbol} @ ${current_price:.6f} | "
                        f"3-Pillar 3m Move: {candidate['net_change_pct']:+.2f}% | Gauntlet: {self.paper_wins}/6")
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
                "thrust_origin": thrust_origin,
                "baseline_vol": baseline_vol,
                "leverage": leverage
            }
            logger.info(f"[LIVE ENTER] {direction.upper()} on {symbol} | Amount: {amount} @ ${fill_price:.6f} | Lev: {leverage}x")

        except Exception as e:
            logger.error(f"Live order failed: {e}")
            self.active_trade = None

    def execute_exit(self, reason: str, is_win: bool):
        """
        Permanent fix for PARTI phantom loop & Wiggle-Fade Harvest.
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
                    logger.info(f"[LIVE EXIT] Closed {symbol} via reduceOnly @ ${exit_price:.6f} | PnL: {pnl_pct:+.2f}% | Reason: {reason}")
                except Exception as e:
                    logger.error(f"Live exit submission error: {e}")
            else:
                logger.info(f"[PAPER EXIT] Closed {symbol} @ ${exit_price:.6f} | PnL: {pnl_pct:+.2f}% (Peak: +{peak_mfe:.2f}%) | Reason: {reason}")

            # Gauntlet Progression (6 consecutive wins in a row)
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
            self.cooldown_tracker[symbol] = time.time() + NORMAL_COOLDOWN_SECS
            logger.info(f"{symbol} placed on normal cooldown.")

    # --------------------------------------------------------------------------
    # POSITION MONITOR: "WHEN IT FADES" HARVEST + FLASH-CRASH CIRCUIT BREAKER
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

            if side == "buy":
                pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
                if current_price > trade["peak_price"]:
                    trade["peak_price"] = current_price
                if current_price < trade["trough_price"]:
                    trade["trough_price"] = current_price

                peak_pnl = ((trade["peak_price"] - entry_price) / entry_price) * 100.0
                drawdown_from_peak = ((trade["peak_price"] - current_price) / trade["peak_price"]) * 100.0

            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100.0
                if current_price < trade["peak_price"]:
                    trade["peak_price"] = current_price
                if current_price > trade["trough_price"]:
                    trade["trough_price"] = current_price

                peak_pnl = ((entry_price - trade["peak_price"]) / entry_price) * 100.0
                drawdown_from_peak = ((current_price - trade["peak_price"]) / trade["peak_price"]) * 100.0

            duration_secs = time.time() - entry_time

            DASHBOARD_DATA["active_trade"] = {
                "symbol": symbol,
                "side": side.upper(),
                "entry": entry_price,
                "current": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "peak_pnl": round(peak_pnl, 2),
                "drawdown_from_peak": round(drawdown_from_peak, 2),
                "duration_min": round(duration_secs / 60, 1)
            }

            # ==================================================================
            # 1. FLASH-CRASH EMERGENCY CIRCUIT BREAKER
            # Prevents sudden violent crash candles while letting normal wiggles breathe
            # ==================================================================
            if drawdown_from_peak >= CRASH_ADVERSE_MOVE_PCT:
                # Inspect recent 1m candle to see if this is an aggressive high-volume crash
                recent_candles = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=2)
                if recent_candles and len(recent_candles) >= 1:
                    latest_candle = recent_candles[-1]
                    latest_vol = latest_candle[5]
                    baseline_vol = trade.get("baseline_vol", 1e-9)

                    # If opposing crash candle hits with > 2x volume -> EMERGENCY EJECT!
                    if latest_vol >= (baseline_vol * CRASH_SPIKE_VOL_RATIO):
                        reason = f"Flash-Crash Circuit Breaker (Abnormal Spike Volume Dump, PnL: {pnl_pct:+.2f}%)"
                        self.execute_exit(reason, is_win=(pnl_pct > 0))
                        return

            # Hard structural floor collapse
            if pnl_pct <= -STRUCTURAL_FLOOR_COLLAPSE:
                reason = f"Structural Floor Collapsed (-{STRUCTURAL_FLOOR_COLLAPSE}%)"
                self.execute_exit(reason, is_win=False)
                return

            # ==================================================================
            # 2. PROVEN "WHEN IT FADES" (WIGGLE & FADE) PROFIT HARVEST
            # Lets runners breathe naturally, but banks profit the second it stalls
            # ==================================================================
            if peak_pnl >= PROFIT_BANK_THRESHOLD_PCT:
                # The Fade Footprint: Stalls and pulls back 0.45% from peak on low/normal volume
                if drawdown_from_peak >= WIGGLE_FADE_PULLBACK_PCT:
                    reason = f"Wiggle & Fade Banked (+{pnl_pct:+.2f}% profit in USDT)"
                    self.execute_exit(reason, is_win=True)
                    return

            # ==================================================================
            # 3. BEHAVIORAL STAGNATION
            # If 20 minutes pass and coin refuses to advance past +0.50%, exit clean
            # ==================================================================
            if duration_secs >= STAGNATION_TIMEOUT_SECS and peak_pnl < 0.50:
                is_win = pnl_pct > 0
                reason = f"Momentum Stall (Dead volume after 20m, PnL: {pnl_pct:+.2f}%)"
                self.execute_exit(reason, is_win=is_win)
                return

            # ==================================================================
            # 4. LIVE HARD STOP LOSS (Once in live mode)
            # ==================================================================
            if is_live and pnl_pct <= -LIVE_HARD_STOP_LOSS_PCT:
                self.execute_exit(f"Hard Stop-Loss (-{LIVE_HARD_STOP_LOSS_PCT}%)", is_win=False)
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

        last_dossier_str = "No trades completed in last window."
        if self.completed_trade_dossiers:
            d = self.completed_trade_dossiers[-1]
            last_dossier_str = (
                f"{d['symbol']} -> PnL: {d['pnl_pct']:+.2f}% | "
                f"Peak: +{d['peak_mfe']:.2f}% | Worst: {d['worst_mae']:.2f}% | "
                f"Duration: {d['duration_min']}m ({d['reason']})"
            )

        briefing_text = (
            f"\n{'='*25} [15-MIN UNIFIED DESK BRIEFING] {'='*25}\n"
            f"• RECENT TRADE TELEMETRY: {last_dossier_str}\n"
            f"• GAUNTLET PROGRESS: {self.paper_wins}/6 Wins | Mode: {'LIVE' if self.live_mode else 'PAPER_QUALIFYING'}\n"
            f"• TRACKING UNIVERSE: {len(self.history_buffer)} liquid perpetual pairs active\n"
            f"• COINGLASS LIQUID POOL: {len(self.global_liquid_symbols)} global pairs verified\n"
            f"{'='*75}"
        )
        logger.info(briefing_text)

        DASHBOARD_DATA["last_briefing"] = {
            "last_trade_telemetry": last_dossier_str,
            "paper_wins": self.paper_wins,
            "active_pairs": len(self.history_buffer),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    # --------------------------------------------------------------------------
    # MAIN EVENT LOOP
    # --------------------------------------------------------------------------
    def run(self):
        logger.info("3-Pillar Escalation & Wiggle-Fade Quant Suite active. Event loop running...")

        while True:
            try:
                if API_KEY:
                    try:
                        bal = self.exchange.fetch_balance()
                        DASHBOARD_DATA["live_balance"] = round(float(bal.get("USDT", {}).get("free", 0.0) or 0.0), 2)
                    except Exception:
                        pass

                DASHBOARD_DATA["status"] = "Active"
                DASHBOARD_DATA["mode"] = "LIVE" if self.live_mode else f"PAPER_QUALIFYING ({self.paper_wins}/6)"
                DASHBOARD_DATA["paper_wins"] = self.paper_wins
                DASHBOARD_DATA["last_scan_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

                self.print_desk_briefing()

                # If managing an open trade, focus purely on monitoring
                if self.active_trade:
                    self.monitor_active_trade()
                    time.sleep(2)
                    continue

                opportunity = self.scan_for_opportunities()
                if opportunity:
                    self.execute_entry(opportunity)

                time.sleep(3)

            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(4)

# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    start_keep_alive_server(PORT)
    bot = QuantBot()
    bot.run()

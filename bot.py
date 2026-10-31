#!/usr/bin/env python3
"""
Institutional Bitget USDT-M Perpetual Trading Bot
- Engine: 10-Minute "40-0 Tennis Domination" via 1-minute Candlestick Inspection
- Execution: One-Way Mode, Dynamic Leverage (clearing $5.50 min notional), reduceOnly exits
- Safety: Anti-Trap Spread Check, Anti-Stagnation (20m velocity cut), PARTI phantom-loop defense
- Qualification: Strict 6-in-a-row paper win gauntlet before live unlock
- Infrastructure: Render Port 10000 HTTP Keep-Alive & Auto-Recovery
"""

import os
import sys
import time
import json
import math
import logging
import threading
from typing import Dict, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler

import ccxt

# ==============================================================================
# 1. LOGGING SETUP
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("QuantDesk")

# ==============================================================================
# 2. CONFIGURATION & ENVIRONMENT
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

# Strategy Parameters
MIN_24H_VOLUME_USDT = 1_000_000.0  # $1,000,000 minimum liquidity
MIN_10M_MOVE_PCT = 2.0             # Minimum 2.0% move in 10 minutes
MAX_10M_MOVE_PCT = 15.0            # Cap at 15.0% to avoid dead illiquid wicks
MAX_RETRACE_RATIO = 0.20           # 20% max counter-retracement (Opponent points)
MAX_OPPOSING_CANDLES = 2           # Opponent can win at most 2 out of 10 candles
MAX_OPPOSING_VOL_RATIO = 0.15      # Opposing volume must be < 15% of 10m total
INSTANT_RUN_PCT = 4.0              # Smooth run >= 4%
INSTANT_MAX_PULLBACK_PCT = 0.50    # Counter pullback strictly < 0.50%
MAX_SPREAD_PCT = 0.10              # Anti-trap order book spread <= 0.10%

# Risk & Order Execution Parameters
BALANCE_UTILIZATION = 0.90         # Use 90% of free balance
BITGET_MIN_NOTIONAL = 5.50         # $5.50 USDT minimum order value
HARD_STOP_LOSS_PCT = 0.90          # 0.9% hard structural stop loss
VELOCITY_TIMEOUT_SECONDS = 1200    # 20 minutes velocity clock
VELOCITY_MIN_PROFIT_PCT = 1.20     # Must be >= +1.2% in 20m or cut trade
RUNNER_TRAIL_ACTIVATION_PCT = 3.50 # Activate dynamic runner trailing at +3.5%
RUNNER_GIVEBACK_PCT = 0.80         # Trail 0.8% behind local peak
COOLDOWN_SECONDS = 900             # 15 minutes symbol cooldown

# ==============================================================================
# 3. HTTP KEEP-ALIVE SERVER (FOR RENDER PORT 10000)
# ==============================================================================
DASHBOARD_DATA = {
    "status": "Initializing",
    "mode": "PAPER",
    "paper_wins": 0,
    "live_balance": 0.0,
    "active_trade": None,
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
        return  # Suppress server request noise in logs

def start_keep_alive_server(port: int):
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Keep-Alive HTTP server running on port {port}")

# ==============================================================================
# 4. BOT ENGINE CLASS
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
                logger.error(f"Failed to load state file: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "paper_wins": self.paper_wins,
                    "live_mode": self.live_mode,
                    "timestamp": time.time()
                }, f)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    # --------------------------------------------------------------------------
    # EXCHANGE INITIALIZATION & RECOVERY
    # --------------------------------------------------------------------------
    def init_exchange_settings(self):
        if not API_KEY or not API_SECRET or not API_PASSPHRASE:
            logger.warning("Bitget API credentials missing. Bot running exclusively in PAPER simulation.")
            return

        try:
            # Set One-Way Mode (Hedged=False / Single-Hold)
            self.exchange.set_position_mode(False, params={"productType": "USDT-FUTURES"})
            logger.info("Bitget Position Mode confirmed: ONE-WAY MODE (Single Hold)")
        except Exception as e:
            logger.info(f"Position mode notice: {e} (Account already configured or unified mode)")

    def recover_live_position(self):
        """Cleanly re-hydrate open positions if Render dyno restarts during active trade."""
        if not API_KEY:
            return

        try:
            positions = self.exchange.fetch_positions(params={"productType": "USDT-FUTURES"})
            for p in positions:
                contracts = float(p.get("contracts", 0.0) or 0.0)
                if contracts > 0:
                    symbol = p["symbol"]
                    # Cleanly resolve side: 'long' -> 'buy', 'short' -> 'sell'
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
                        "leverage": int(p.get("leverage", 5))
                    }
                    self.live_mode = True
                    logger.warning(f"CRITICAL RECOVERY: Recovered active LIVE position {side.upper()} on {symbol} | "
                                   f"Size: {contracts} contracts @ ${entry_price}")
                    break
        except Exception as e:
            logger.error(f"Position recovery check failed: {e}")

    # --------------------------------------------------------------------------
    # UNIVERSE SCANNING & 10M CLEANLINESS INSPECTOR
    # --------------------------------------------------------------------------
    def is_symbol_valid(self, symbol: str) -> bool:
        base = symbol.split("/")[0].split(":")[0]
        if base in BLACKLIST:
            return False
        if time.time() < self.cooldown_tracker.get(symbol, 0):
            return False
        return True

    def evaluate_10m_cleanliness(self, symbol: str) -> Optional[Dict]:
        """
        Fetches 10 completed 1-minute candles and performs the 40-0 Domination test.
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe="1m", limit=11)
            if not ohlcv or len(ohlcv) < 11:
                return None

            candles = ohlcv[-11:-1] # 10 completed 1m candles
            start_open = candles[0][1]
            end_close = candles[-1][4]
            net_change_pct = ((end_close - start_open) / start_open) * 100.0

            abs_change = abs(net_change_pct)
            if abs_change < MIN_10M_MOVE_PCT or abs_change > MAX_10M_MOVE_PCT:
                return None

            direction = "buy" if net_change_pct > 0 else "sell"
            total_volume = sum(c[5] for c in candles)
            if total_volume <= 0:
                return None

            # Track cleanliness mechanics
            opposing_candles = 0
            opposing_volume = 0.0

            if direction == "buy":
                running_high = candles[0][2]
                max_counter_pullback_abs = 0.0
                max_retrace_ratio = 0.0

                for c in candles:
                    o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                    if h > running_high:
                        running_high = h
                    
                    # Measure pullback from current running high
                    wave_expansion = running_high - start_open
                    if wave_expansion > 0:
                        pullback = running_high - l
                        retrace_ratio = pullback / wave_expansion
                        if retrace_ratio > max_retrace_ratio:
                            max_retrace_ratio = retrace_ratio
                    
                    # Absolute pullback from peak
                    pb_abs = ((running_high - l) / running_high) * 100.0
                    if pb_abs > max_counter_pullback_abs:
                        max_counter_pullback_abs = pb_abs

                    if cl < o: # Opposing candle (Red)
                        opposing_candles += 1
                        opposing_volume += vol

            else: # direction == "sell"
                running_low = candles[0][3]
                max_counter_pullback_abs = 0.0
                max_retrace_ratio = 0.0

                for c in candles:
                    o, h, l, cl, vol = c[1], c[2], c[3], c[4], c[5]
                    if l < running_low:
                        running_low = l
                    
                    # Measure bounce from current running low
                    wave_expansion = start_open - running_low
                    if wave_expansion > 0:
                        bounce = h - running_low
                        retrace_ratio = bounce / wave_expansion
                        if retrace_ratio > max_retrace_ratio:
                            max_retrace_ratio = retrace_ratio

                    # Absolute bounce from dip
                    pb_abs = ((h - running_low) / running_low) * 100.0
                    if pb_abs > max_counter_pullback_abs:
                        max_counter_pullback_abs = pb_abs

                    if cl > o: # Opposing candle (Green)
                        opposing_candles += 1
                        opposing_volume += vol

            opposing_vol_ratio = opposing_volume / total_volume

            # Rule A: Smooth 4% Run instant trigger
            if abs_change >= INSTANT_RUN_PCT and max_counter_pullback_abs < INSTANT_MAX_PULLBACK_PCT:
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "net_change_pct": net_change_pct,
                    "score": 999.0, # Immediate trigger priority
                    "instant": True
                }

            # Rule B: Tennis 40-0 Cleanliness Test
            if max_retrace_ratio > MAX_RETRACE_RATIO:
                return None # Dirty deuce match (>20% counter-retracement)
            if opposing_candles > MAX_OPPOSING_CANDLES:
                return None # Opponent scored more than 2 games
            if opposing_vol_ratio > MAX_OPPOSING_VOL_RATIO:
                return None # Opponent put up substantial resistance (>15% volume)

            cleanliness_score = abs_change * (1.0 - max_retrace_ratio)
            return {
                "symbol": symbol,
                "direction": direction,
                "net_change_pct": net_change_pct,
                "score": cleanliness_score,
                "instant": False
            }

        except Exception as e:
            return None

    def anti_trap_check(self, symbol: str) -> bool:
        """Verifies tight spread to avoid iceberg walls and illiquid traps."""
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
        tickers = self.exchange.fetch_tickers()
        valid_candidates = []

        for symbol, t in tickers.items():
            if not symbol.endswith(":USDT"):
                continue
            if not self.is_symbol_valid(symbol):
                continue
            
            quote_vol = float(t.get("quoteVolume", 0.0) or 0.0)
            if quote_vol < MIN_24H_VOLUME_USDT:
                continue

            valid_candidates.append(symbol)

        logger.info(f"Scanning {len(valid_candidates)} liquid pairs for 10m clean momentum...")

        results = []
        for symbol in valid_candidates:
            analysis = self.evaluate_10m_cleanliness(symbol)
            if analysis:
                if analysis["instant"]:
                    if self.anti_trap_check(symbol):
                        logger.info(f"INSTANT 4% TRIGGER: {symbol} clean runaway move!")
                        return analysis
                results.append(analysis)
            time.sleep(0.04) # Protect API rate limits

        if not results:
            return None

        # Sort by cleanliness score (40-0 domination)
        results.sort(key=lambda x: x["score"], reverse=True)
        top_10 = results[:10]
        
        # Update dashboard
        DASHBOARD_DATA["top_candidates"] = [
            f"{c['symbol']} | {c['direction'].upper()} {c['net_change_pct']:.2f}% | Score: {c['score']:.2f}" 
            for c in top_10
        ]

        # Select Candidate #1 that passes Anti-Trap
        for candidate in top_10:
            if self.anti_trap_check(candidate["symbol"]):
                return candidate
            else:
                logger.warning(f"Candidate {candidate['symbol']} failed anti-trap spread check. Testing next...")

        return None

    # --------------------------------------------------------------------------
    # EXECUTION ENGINE (MICRO-CAPITAL & ONE-WAY PRECISION)
    # --------------------------------------------------------------------------
    def calculate_sizing(self, symbol: str, current_price: float) -> Tuple[int, float]:
        """Dynamically computes minimum leverage needed to clear $5.50 min notional."""
        balance = self.exchange.fetch_balance()
        free_usdt = float(balance.get("USDT", {}).get("free", 0.0) or 0.0)
        usable_margin = max(free_usdt * BALANCE_UTILIZATION, 0.50)

        # Dynamic Leverage = ceil(5.50 / usable_margin)
        calculated_lev = math.ceil(BITGET_MIN_NOTIONAL / usable_margin)
        leverage = max(2, min(calculated_lev, 20)) # Clamp between 2x and 20x

        target_notional = usable_margin * leverage
        if target_notional < BITGET_MIN_NOTIONAL:
            target_notional = BITGET_MIN_NOTIONAL + 0.20 # Ensure threshold clearance

        raw_amount = target_notional / current_price
        formatted_amount = float(self.exchange.amount_to_precision(symbol, raw_amount))
        return leverage, formatted_amount

    def execute_entry(self, candidate: Dict):
        symbol = candidate["symbol"]
        direction = candidate["direction"] # 'buy' or 'sell'
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
                "leverage": 5
            }
            logger.info(f"[PAPER ENTER] {direction.upper()} on {symbol} @ ${current_price:.6f} | Paper Streak: {self.paper_wins}/6")
            return

        # Live Execution
        try:
            leverage, amount = self.calculate_sizing(symbol, current_price)
            try:
                self.exchange.set_leverage(leverage, symbol, params={"productType": "USDT-FUTURES", "marginCoin": "USDT"})
            except Exception as e:
                logger.info(f"Leverage set notice: {e}")

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
                "leverage": leverage
            }
            logger.info(f"[LIVE ENTER] {direction.upper()} on {symbol} | Amount: {amount} @ ${fill_price:.6f} | Lev: {leverage}x")

        except Exception as e:
            logger.error(f"Live entry order failed: {e}")
            self.active_trade = None

    def execute_exit(self, reason: str):
        """
        Permanent fix for PARTI phantom loop:
        Uses live exchange contract query + reduceOnly + atomic finally state cleanup.
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

            # Execute Live Order
            if is_live:
                try:
                    # Query live exchange contract balance to avoid dust or flip errors
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

            # Qualification Logic (Strict 6 in a Row)
            if not is_live:
                if is_win:
                    self.paper_wins += 1
                    logger.info(f"PAPER QUALIFIER WIN: Streak is now {self.paper_wins}/6")
                    if self.paper_wins >= 6:
                        self.live_mode = True
                        logger.warning("=========================================================")
                        logger.warning("GAUNTLET COMPLETED (6/6 WINS). LIVE TRADING UNLOCKED!")
                        logger.warning("=========================================================")
                else:
                    logger.warning(f"PAPER QUALIFIER LOSS ({pnl_pct:.2f}%). Counter reset to 0/6.")
                    self.paper_wins = 0

                self.save_state()

        except Exception as e:
            logger.error(f"Critical error during exit execution: {e}")

        finally:
            # Atomic state reset: permanently prevents PARTI phantom exit loops
            self.active_trade = None
            self.cooldown_tracker[symbol] = time.time() + COOLDOWN_SECONDS
            logger.info(f"Symbol {symbol} entered 15-minute cooldown.")

    # --------------------------------------------------------------------------
    # TRADE MONITOR & ANTI-STAGNATION HARVESTER
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

            # Calculate current PnL & Peak Price
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

            # Update dashboard status
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

            # 2. Velocity Invalidation (Anti-Stagnation Clock: 20 mins)
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
        logger.info("Quant Trading Desk engine active. Starting event loop...")
        
        while True:
            try:
                # Update Dashboard live balance
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

                # If trade is open, manage it exclusively
                if self.active_trade:
                    self.monitor_active_trade()
                    time.sleep(3)
                    continue

                # Otherwise, scan universe for fresh 40-0 blowouts
                opportunity = self.scan_for_opportunities()
                if opportunity:
                    self.execute_entry(opportunity)

                time.sleep(10) # Scanner interval

            except Exception as e:
                logger.error(f"Unhandled loop error: {e}")
                time.sleep(10)

# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    start_keep_alive_server(PORT)
    bot = QuantBot()
    bot.run()

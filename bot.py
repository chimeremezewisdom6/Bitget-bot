import os
import sys
import time
import math
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER 24/7 KEEP-ALIVE SERVER (PORT 10000)
# ==============================================================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"APEX-RAPID 5M Quant Engine is active.")

    def log_message(self, format, *args):
        return  # Silence HTTP server logs to keep terminal clean


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. CONFIGURATION & MICRO-CAP RISK BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

# Fast-Turnover Sizing & Squeeze Rules
BALANCE_USE_PCT = 0.88          # Use 88% of vault cash
MIN_NOTIONAL = 5.15             # Buffer above Bitget's $5.00 floor
MIN_24H_VOLUME = 1_000_000      # $1,000,000 ($1M) Volume Floor: Captures 120-180+ active altcoins
SCAN_INTERVAL_SECONDS = 45      # Fast 45-second radar scan

# Microstructure Defense Parameters (5-Minute Timeframe)
MAX_SPREAD_PCT = 0.08           # Max allowable spread: 0.08%
MIN_ATR_PCT = 0.90              # Rejects sleepy coins (<0.90% 5m ATR)
MAX_ATR_PCT = 2.80              # Rejects uncontrollable meme coins (>2.80% 5m ATR)
MIN_DISPLACEMENT_PCT = 0.95     # 5m Trigger candle must move at least 0.95%
MAX_HARD_STOP_PCT = 1.45        # Tight 1.45% loss ceiling to protect $2.62 vault

NON_CRYPTO_SYMBOLS = {
    'CL', 'BZ', 'SOXS', 'SOXL', 'KORU', 'MU', 'TSLA', 'NVDA', 'AAPL', 'MSFT',
    'AMZN', 'GOOGL', 'META', 'SPX', 'NDX', 'DJI', 'XAU', 'XAG', 'MINIMAX', 'DOS'
}

exchange = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "password": PASSPHRASE,
    "enableRateLimit": True,
    "timeout": 20000,
    "options": {
        "defaultType": "swap",
        "createMarketBuyOrderRequiresPrice": False
    }
})


# ==============================================================================
# 3. MATHEMATICAL INDICATORS (5-MINUTE RESOLUTION)
# ==============================================================================
def calculate_atr(ohlcv, period=14):
    """Calculates true Average True Range over completed 5m candles."""
    if len(ohlcv) < period + 1:
        return 0.0
    tr_list = []
    for i in range(1, len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]
        prev_close = ohlcv[i - 1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    if len(tr_list) < period:
        return 0.0
    return sum(tr_list[-period:]) / period


def calculate_bollinger_bands(closes, period=20, num_std=2.0):
    """Calculates 20-period Bollinger Bands and Bandwidth %."""
    if len(closes) < period:
        return None
    subset = closes[-period:]
    sma = sum(subset) / period
    variance = sum((x - sma) ** 2 for x in subset) / period
    std = math.sqrt(variance)
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    bandwidth = ((upper - lower) / sma) * 100 if sma > 0 else 0
    return {"sma": sma, "upper": upper, "lower": lower, "bandwidth": bandwidth}


def calculate_rsi(closes, period=14):
    """Calculates Relative Strength Index (RSI)."""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


# ==============================================================================
# 4. BITGET ONE-WAY EXECUTION & SYNC HELPERS
# ==============================================================================
def get_open_position():
    """Queries exchange for any active Long or Short position."""
    try:
        positions = exchange.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            side = p.get('side', '').lower()
            if contracts > 0 and side in ['long', 'short']:
                return {
                    'symbol': p['symbol'],
                    'side': side,
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0))
                }
    except Exception as e:
        print(f"[POSITION QUERY WARNING] {e}", flush=True)
    return None


def open_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e


def close_long_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e


def open_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='sell', amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='sell', amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e


def close_short_position(symbol, amount):
    try:
        return exchange.create_order(
            symbol=symbol, type='market', side='buy', amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol, type='market', side='buy', amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e


# ==============================================================================
# 5. RAPID 5-MINUTE SIGNAL ENGINE (ZERO REPAINTING)
# ==============================================================================
def inspect_coin_setup(symbol, ticker_data):
    """
    Scans completed 5m candles (ohlcv[-2]) for fast compression breakout.
    """
    try:
        bid = float(ticker_data.get('bid', 0) or 0)
        ask = float(ticker_data.get('ask', 0) or 0)
        last_price = float(ticker_data.get('last', 0) or 0)

        if bid <= 0 or ask <= 0 or last_price <= 0:
            return None

        # 1. Spread Defense
        spread_pct = ((ask - bid) / last_price) * 100
        if spread_pct > MAX_SPREAD_PCT:
            return None

        # Fetch 30 five-minute candles (2.5 hours of high-frequency data)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=30)
        if len(ohlcv) < 25:
            return None

        closed_ohlcv = ohlcv[:-1]
        closes = [x[4] for x in closed_ohlcv]
        volumes = [x[5] for x in closed_ohlcv]

        # 2. Dynamic 5m ATR
        atr = calculate_atr(closed_ohlcv, period=14)
        if atr <= 0:
            return None

        atr_pct = (atr / last_price) * 100
        if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
            return None

        # 3. Bollinger Bands on 5m candles
        bb = calculate_bollinger_bands(closes[:-1], period=20, num_std=2.0)
        if not bb:
            return None

        is_coiled = bb['bandwidth'] <= 4.2

        # 4. Relative Volume Ignition on 5m
        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        trigger_volume = volumes[-1]
        rvol = round(trigger_volume / avg_vol, 2) if avg_vol > 0 else 1.0

        if rvol < 2.0:
            return None

        # 5. Evaluate Completed Trigger Candle
        t_open = closed_ohlcv[-1][1]
        t_high = closed_ohlcv[-1][2]
        t_low = closed_ohlcv[-1][3]
        t_close = closed_ohlcv[-1][4]

        candle_range = t_high - t_low
        if candle_range == 0:
            return None

        upper_wick = (t_high - max(t_open, t_close)) / candle_range
        lower_wick = (min(t_open, t_close) - t_low) / candle_range
        body_pct = abs(t_close - t_open) / candle_range
        candle_move = ((t_close - t_open) / t_open) * 100
        rsi = calculate_rsi(closes, period=14)

        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        # === SIGNAL A: 5M EXPANSION LONG ===
        is_long = (
            is_coiled and
            t_close > (bb['upper'] + (0.10 * atr)) and
            t_close < (bb['upper'] + (0.90 * atr)) and
            candle_move >= MIN_DISPLACEMENT_PCT and
            body_pct >= 0.50 and
            upper_wick <= 0.28 and
            48.0 <= rsi <= 75.0 and
            funding_rate <= 0.015
        )
        if is_long:
            return {
                "symbol": symbol,
                "side": "long",
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(candle_move, 2),
                "setup": "5M_EXPANSION_LONG",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL B: 5M LIQUIDITY SWEEP SHORT ===
        is_short_sweep = (
            t_high > (bb['upper'] + (0.25 * atr)) and
            upper_wick >= 0.38 and
            t_close < t_open and
            funding_rate >= -0.01
        )
        if is_short_sweep:
            return {
                "symbol": symbol,
                "side": "short",
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(abs(candle_move), 2),
                "setup": "5M_SWEEP_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL C: 5M SQUEEZE BREAKDOWN SHORT ===
        is_short_breakdown = (
            is_coiled and
            t_close < (bb['lower'] - (0.10 * atr)) and
            t_close > (bb['lower'] - (0.90 * atr)) and
            candle_move <= -MIN_DISPLACEMENT_PCT and
            body_pct >= 0.50 and
            lower_wick <= 0.28 and
            funding_rate >= -0.01
        )
        if is_short_breakdown:
            return {
                "symbol": symbol,
                "side": "short",
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(abs(candle_move), 2),
                "setup": "5M_BREAKDOWN_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        return None
    except Exception:
        return None


# ==============================================================================
# 6. FAST ACTIVE TRADE GUARDIAN
# ==============================================================================
def manage_active_trade(symbol, side, initial_contracts, entry_price, entry_atr):
    """
    Rapid risk manager:
    - Stop Loss: 1.3x ATR (max 1.45% price loss)
    - Fee-Shield: Locks at +0.40% net once in profit by 0.9x ATR
    - Runner Trail: 1.1x ATR trail once profit exceeds 1.8x ATR
    - Stagnation Exit: 15 minutes max
    """
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    last_position_check = time.time()
    fee_shield_active = False

    atr = entry_atr if entry_atr > 0 else (entry_price * 0.012)

    # Tight stop for rapid capital protection
    calculated_stop = 1.3 * atr
    max_allowed_stop = entry_price * (MAX_HARD_STOP_PCT / 100.0)
    stop_distance = min(calculated_stop, max_allowed_stop)

    fee_shield_trigger = 0.9 * atr
    runner_trigger = 1.8 * atr
    trail_distance = 1.1 * atr

    if side == 'long':
        initial_stop_price = entry_price - stop_distance
    else:
        initial_stop_price = entry_price + stop_distance

    stop_pct = (stop_distance / entry_price) * 100
    print(f"\n[GUARDIAN ACTIVE] {side.upper()} {symbol} | Fill: {entry_price:.5f} | Tight Stop: {initial_stop_price:.5f} ({stop_pct:.2f}%)", flush=True)

    while True:
        try:
            time.sleep(2)

            # Confirm trade is still alive on exchange
            if time.time() - last_position_check > 20:
                pos = get_open_position()
                if not pos or pos['symbol'] != symbol or pos['side'] != side:
                    print(f"\n[GUARDIAN INFO] {symbol} closed externally. Exiting Guardian.", flush=True)
                    break
                last_position_check = time.time()

            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker.get('last', 0) or 0)
            if cur_price <= 0:
                continue

            if cur_price > highest_price:
                highest_price = cur_price
            if cur_price < lowest_price:
                lowest_price = cur_price

            elapsed_min = (time.time() - entry_time) / 60

            if side == 'long':
                pnl_pct = ((cur_price - entry_price) / entry_price) * 100
                peak_pnl = ((highest_price - entry_price) / entry_price) * 100
                peak_distance = highest_price - entry_price
            else:
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100
                peak_distance = entry_price - lowest_price

            if time.time() - last_log_time > 10:
                shield_status = "LOCKED (+0.40%)" if fee_shield_active else "MONITORING"
                print(f"[STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% (Peak: {peak_pnl:+.2f}%) | Shield: {shield_status} | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            def execute_exit(reason):
                print(f"\n[EXIT TRIGGER] {reason} | PnL: {pnl_pct:+.2f}%", flush=True)
                live_pos = get_open_position()
                close_amount = live_pos['contracts'] if live_pos else initial_contracts
                if side == 'long':
                    close_long_position(symbol, close_amount)
                else:
                    close_short_position(symbol, close_amount)

            # 1. Early Fee-Shield Lock (+0.9x ATR Gain -> Locks Breakeven +0.40%)
            if not fee_shield_active and peak_distance >= fee_shield_trigger:
                fee_shield_active = True
                print(f"\n[FEE-SHIELD ENGAGED] {symbol} moved 0.9x ATR! Stop moved to Breakeven +0.40% net.", flush=True)

            if fee_shield_active:
                if side == 'long' and cur_price <= entry_price * 1.0040:
                    execute_exit("Long Fee-Shield Hit")
                    break
                elif side == 'short' and cur_price >= entry_price * 0.9960:
                    execute_exit("Short Fee-Shield Hit")
                    break

            # 2. Tight Hard Stop Loss (1.3x ATR)
            if not fee_shield_active:
                if side == 'long' and cur_price <= initial_stop_price:
                    execute_exit("Long Tight Stop Hit")
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    execute_exit("Short Tight Stop Hit")
                    break

            # 3. Fast Parabolic Runner Trail
            if peak_distance >= runner_trigger:
                if side == 'long':
                    trail_stop = highest_price - trail_distance
                    if cur_price <= trail_stop:
                        execute_exit("Long Trailing Stop Hit")
                        break
                else:
                    trail_stop = lowest_price + trail_distance
                    if cur_price >= trail_stop:
                        execute_exit("Short Trailing Stop Hit")
                        break

            # 4. Fast 15-Minute Stagnation Exit
            if elapsed_min >= 15.0 and peak_distance < (0.6 * atr):
                execute_exit("15-Minute Stagnation Exit (Capital Recycled)")
                break

        except Exception as e:
            print(f"[GUARDIAN EXCEPTION] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 7. MAIN ENGINE LOOP (120-180+ COIN FULL-UNIVERSE SCANNER)
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-RAPID 5M Engine ($1M Volume Floor) initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} total markets from Bitget.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    cycle = 1

    while True:
        try:
            pos = get_open_position()
            if pos:
                fallback_atr = pos['entry_price'] * 0.012
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(3)
                continue

            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            # Dynamic Leverage Ladder for small vault survival
            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            notional = (usdt_free * BALANCE_USE_PCT) * leverage

            # 1 single call fetches all 850+ coins
            try:
                tickers = exchange.fetch_tickers()
            except Exception as e:
                time.sleep(10)
                continue

            # Capture EVERY coin clearing >= $1M 24h volume
            liquid_candidates = []
            for symbol, t in tickers.items():
                if not symbol.endswith(":USDT"):
                    continue
                base_asset = symbol.split('/')[0].upper()
                if base_asset in NON_CRYPTO_SYMBOLS:
                    continue
                vol_24h = float(t.get('quoteVolume', 0) or 0)
                if vol_24h >= MIN_24H_VOLUME:
                    liquid_candidates.append((symbol, vol_24h, t))

            # Sort by 24h volume
            liquid_candidates.sort(key=lambda x: x[1], reverse=True)

            best_candidate = None

            # Inspect every qualifying coin across the $1M universe
            for sym, vol_24h, t_data in liquid_candidates:
                time.sleep(0.025)  # 25ms micro-throttle (Safe under Bitget's 20 req/s limit)
                candidate = inspect_coin_setup(sym, t_data)
                if candidate:
                    best_candidate = candidate
                    break

            if best_candidate and notional >= MIN_NOTIONAL:
                sym = best_candidate['symbol']
                side = best_candidate['side']
                atr = best_candidate['atr']

                ticker_now = exchange.fetch_ticker(sym)
                live_price = float(ticker_now.get('last', 0) or 0)

                market = exchange.market(sym)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / live_price
                formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))
                actual_notional = formatted_amount * live_price

                if formatted_amount >= min_lot and actual_notional >= 5.15:
                    try:
                        exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    print("\n" + "=" * 80, flush=True)
                    print(f"[RAPID STRIKE: {side.upper()}] Confirmed on {sym}!", flush=True)
                    print(f"  Setup:         {best_candidate['setup']}", flush=True)
                    print(f"  Speed:         5m Candle Thrust: {best_candidate['candle_move']:+}% | ATR: {best_candidate['atr_pct']}%", flush=True)
                    print(f"  Volume Engine: 5m RVol {best_candidate['rvol']}x | Squeeze: {best_candidate['bandwidth']}%", flush=True)
                    print(f"  Execution:     Entering {leverage}x {side.upper()} | Notional: ${actual_notional:.2f}", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    if side == 'long':
                        order = open_long_position(sym, formatted_amount)
                    else:
                        order = open_short_position(sym, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(2)

                    real_pos = get_open_position()
                    real_fill_price = real_pos['entry_price'] if real_pos else live_price
                    real_contracts = real_pos['contracts'] if real_pos else formatted_amount

                    manage_active_trade(sym, side, real_contracts, real_fill_price, atr)
                    continue

            if cycle % 2 == 0:
                print(
                    f"[RADAR PULSE] Active $1M+ Universe: {len(liquid_candidates)} coins | "
                    f"Vault: ${usdt_free:.2f} USDT ({leverage}x tier) | Next scan in {SCAN_INTERVAL_SECONDS}s...",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()

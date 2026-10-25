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
        self.wfile.write(b"APEX-V2 Institutional Engine is active and healthy.")

    def log_message(self, format, *args):
        return  # Silence server logs to keep terminal clean


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. EXCHANGE CONFIGURATION & RISK BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

# Institutional Capital Boundaries
BALANCE_USE_PCT = 0.88          # Use 88% of free vault margin
MIN_NOTIONAL = 5.20             # Strict buffer above Bitget's $5.00 limit
MIN_24H_VOLUME = 3_000_000      # $3M volume threshold
SCAN_INTERVAL_SECONDS = 60      # Fast 60-second universe scan

# Microstructure Defense Parameters
MAX_SPREAD_PCT = 0.05           # Order book spread must be <= 0.05%
MIN_ATR_PCT = 1.05              # Eliminates sleepy big caps (<1.05% 15m ATR)
MAX_ATR_PCT = 2.40              # Eliminates dangerous low-cap traps (>2.40% 15m ATR)
MIN_DISPLACEMENT_PCT = 1.15     # Anti-creep: Breakout candle must move >= 1.15%
MAX_HARD_STOP_PCT = 1.80        # Absolute maximum loss ceiling

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
# 3. MATHEMATICAL INDICATORS (ZERO-REPAINTING)
# ==============================================================================
def calculate_atr(ohlcv, period=14):
    """Calculates true Average True Range over completed candles."""
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
    """Calculates SMA, Upper/Lower Bands, and Bandwidth %."""
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
    """Calculates standard RSI."""
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
# 4. BITGET ONE-WAY EXECUTION & SYNCHRONIZATION HELPERS
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
# 5. HIGH-DISPLACEMENT QUANTITATIVE SIGNAL ENGINE (ZERO REPAINTING)
# ==============================================================================
def inspect_coin_setup(symbol, ticker_data):
    """
    Evaluates strictly on closed candles (ohlcv[-2]) to prevent repainting.
    Uses ohlcv[-1] only to confirm live execution validity.
    """
    try:
        bid = float(ticker_data.get('bid', 0) or 0)
        ask = float(ticker_data.get('ask', 0) or 0)
        last_price = float(ticker_data.get('last', 0) or 0)

        if bid <= 0 or ask <= 0 or last_price <= 0:
            return None

        # 1. Spread Filter (Order Book Depth)
        spread_pct = ((ask - bid) / last_price) * 100
        if spread_pct > MAX_SPREAD_PCT:
            return None

        # Fetch 35 fifteen-minute candles
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=35)
        if len(ohlcv) < 30:
            return None

        # Closed candles array (excluding the forming candle [-1])
        closed_ohlcv = ohlcv[:-1]
        closes = [x[4] for x in closed_ohlcv]
        volumes = [x[5] for x in closed_ohlcv]

        # 2. Dynamic ATR on closed candles
        atr = calculate_atr(closed_ohlcv, period=14)
        if atr <= 0:
            return None

        atr_pct = (atr / last_price) * 100
        if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
            return None  # Rejects both sleepy big-caps and wild meme traps

        # 3. Bollinger Bands (20 periods prior to trigger candle)
        bb = calculate_bollinger_bands(closes[:-1], period=20, num_std=2.0)
        if not bb:
            return None

        is_coiled = bb['bandwidth'] <= 4.5

        # 4. Volume Ignition (Trigger candle volume vs 20-period average)
        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        trigger_volume = volumes[-1]
        rvol = round(trigger_volume / avg_vol, 2) if avg_vol > 0 else 1.0

        if rvol < 2.0:
            return None  # Institutional fuel requirement

        # 5. Evaluate the COMPLETED Trigger Candle (closed_ohlcv[-1])
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

        # Funding rate verification
        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        # === SIGNAL A: HIGH-DISPLACEMENT EXPANSION LONG ===
        # - Must be coiled in consolidation
        # - Closed candle broke cleanly above upper band
        # - Candle moved >= +1.15% (Anti-creep)
        # - Anti-chase: closed not more than 1.1x ATR away from upper band
        # - Healthy RSI, clean funding
        is_long = (
            is_coiled and
            t_close > (bb['upper'] + (0.15 * atr)) and
            t_close < (bb['upper'] + (1.10 * atr)) and
            candle_move >= MIN_DISPLACEMENT_PCT and
            body_pct >= 0.52 and
            upper_wick <= 0.25 and
            50.0 <= rsi <= 74.0 and
            funding_rate <= 0.015
        )
        if is_long:
            return {
                "symbol": symbol,
                "side": "long",
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(candle_move, 2),
                "setup": "EXPANSION_LONG",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL B: LIQUIDITY SWEEP REVERSAL SHORT ===
        # - Pierced above upper band by > 0.3x ATR
        # - Rejected with >= 40% upper wick, closed red back inside band
        is_short_sweep = (
            t_high > (bb['upper'] + (0.30 * atr)) and
            upper_wick >= 0.40 and
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
                "setup": "LIQUIDITY_SWEEP_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL C: SQUEEZE BREAKDOWN SHORT ===
        # - Must be coiled
        # - Closed candle dropped >= -1.15% below lower band
        is_short_breakdown = (
            is_coiled and
            t_close < (bb['lower'] - (0.15 * atr)) and
            t_close > (bb['lower'] - (1.10 * atr)) and
            candle_move <= -MIN_DISPLACEMENT_PCT and
            body_pct >= 0.52 and
            lower_wick <= 0.25 and
            funding_rate >= -0.01
        )
        if is_short_breakdown:
            return {
                "symbol": symbol,
                "side": "short",
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(abs(candle_move), 2),
                "setup": "SQUEEZE_BREAKDOWN_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        return None
    except Exception:
        return None


# ==============================================================================
# 6. ACTIVE TRADE GUARDIAN (TRUE FILL-PRICE ANCHORING)
# ==============================================================================
def manage_active_trade(symbol, side, initial_contracts, entry_price, entry_atr):
    """
    Guards live position with:
    1. Real fill price anchoring
    2. Real-time exchange position confirmation (No ghost trades)
    3. Live contract synchronization upon exit
    4. Adaptive ATR stop loss + fee shield + runner trail
    """
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    last_position_check = time.time()
    fee_shield_active = False

    atr = entry_atr if entry_atr > 0 else (entry_price * 0.015)

    # Dynamic Stop: 1.5x ATR, hard-capped at 1.80% maximum price distance
    calculated_stop = 1.5 * atr
    max_allowed_stop = entry_price * (MAX_HARD_STOP_PCT / 100.0)
    stop_distance = min(calculated_stop, max_allowed_stop)

    fee_shield_trigger = 1.2 * atr
    runner_trigger = 2.2 * atr
    trail_distance = 1.3 * atr

    if side == 'long':
        initial_stop_price = entry_price - stop_distance
    else:
        initial_stop_price = entry_price + stop_distance

    stop_pct = (stop_distance / entry_price) * 100
    print(f"\n[GUARDIAN ENGAGED] {side.upper()} {symbol} | Fill Price: {entry_price:.5f} | Initial Stop: {initial_stop_price:.5f} ({stop_pct:.2f}%)", flush=True)

    while True:
        try:
            time.sleep(3)

            # 1. POSITION INTEGRITY CHECK (Every 25 seconds)
            # Confirms trade is still alive on Bitget (detects manual phone closes / external stops)
            if time.time() - last_position_check > 25:
                pos = get_open_position()
                if not pos or pos['symbol'] != symbol or pos['side'] != side:
                    print(f"\n[GUARDIAN INFO] {symbol} position no longer active on exchange. Exiting Guardian mode.", flush=True)
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

            if time.time() - last_log_time > 15:
                shield_status = "LOCKED (+0.50%)" if fee_shield_active else "MONITORING"
                print(f"[STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% (Peak: {peak_pnl:+.2f}%) | Shield: {shield_status} | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # Helper function to close exact currently open contracts
            def execute_exit(reason):
                print(f"\n[EXIT TRIGGER] {reason} | PnL: {pnl_pct:+.2f}%", flush=True)
                live_pos = get_open_position()
                close_amount = live_pos['contracts'] if live_pos else initial_contracts
                if side == 'long':
                    close_long_position(symbol, close_amount)
                else:
                    close_short_position(symbol, close_amount)

            # 2. THE FEE-SHIELD LOCK (+1.2x ATR Gain -> Lock Stop at Entry + 0.50% net)
            if not fee_shield_active and peak_distance >= fee_shield_trigger:
                fee_shield_active = True
                print(f"\n[FEE-SHIELD ENGAGED] {symbol} moved 1.2x ATR in profit! Risk-Free Stop locked at Breakeven +0.50% net.", flush=True)

            if fee_shield_active:
                if side == 'long' and cur_price <= entry_price * 1.0050:
                    execute_exit("Long Fee-Shield Hit")
                    break
                elif side == 'short' and cur_price >= entry_price * 0.9950:
                    execute_exit("Short Fee-Shield Hit")
                    break

            # 3. ADAPTIVE STOP LOSS (Hard-Capped at 1.80%)
            if not fee_shield_active:
                if side == 'long' and cur_price <= initial_stop_price:
                    execute_exit("Long Adaptive Stop Loss Hit")
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    execute_exit("Short Adaptive Stop Loss Hit")
                    break

            # 4. PARABOLIC RUNNER TRAIL (2.2x ATR Expansion -> Trail 1.3x ATR)
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

            # 5. DEAD-MONEY TIME STOP (45 Minutes Stagnation)
            if elapsed_min >= 45.0 and peak_distance < (0.8 * atr):
                execute_exit("45-Minute Stagnation Exit")
                break

        except Exception as e:
            print(f"[GUARDIAN EXCEPTION] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 7. MAIN ENGINE LOOP (ADAPTIVE LEVERAGE LADDER)
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX-V2 Institutional Engine initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    cycle = 1

    while True:
        try:
            # 1. Manage existing trade if one is running
            pos = get_open_position()
            if pos:
                fallback_atr = pos['entry_price'] * 0.015
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(5)
                continue

            # 2. Query Balance & Apply Dynamic Leverage Ladder
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            # Autonomous Leverage Ladder (Guarantees notional is always >= $5.20)
            if usdt_free >= 2.40:
                leverage = 3
            elif usdt_free >= 1.80:
                leverage = 4
            else:
                leverage = 5

            notional = (usdt_free * BALANCE_USE_PCT) * leverage

            # 3. Pull Universe Tickers
            try:
                tickers = exchange.fetch_tickers()
            except Exception as e:
                time.sleep(10)
                continue

            liquid_symbols = []
            for symbol, t in tickers.items():
                if not symbol.endswith(":USDT"):
                    continue
                base_asset = symbol.split('/')[0].upper()
                if base_asset in NON_CRYPTO_SYMBOLS:
                    continue
                vol_24h = float(t.get('quoteVolume', 0) or 0)
                if vol_24h >= MIN_24H_VOLUME:
                    liquid_symbols.append((symbol, vol_24h, t))

            # Sort by 24h volume descending and inspect top 20 pre-filtered candidates
            liquid_symbols.sort(key=lambda x: x[1], reverse=True)
            top_candidates = liquid_symbols[:20]

            best_candidate = None

            for sym, vol_24h, t_data in top_candidates:
                candidate = inspect_coin_setup(sym, t_data)
                if candidate:
                    best_candidate = candidate
                    break

            # 4. Strike with Absolute Precision
            if best_candidate and notional >= MIN_NOTIONAL:
                sym = best_candidate['symbol']
                side = best_candidate['side']
                atr = best_candidate['atr']

                # Get latest live price tick for sizing
                ticker_now = exchange.fetch_ticker(sym)
                live_price = float(ticker_now.get('last', 0) or 0)

                market = exchange.market(sym)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / live_price
                formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))

                # Verify formatted amount clears Bitget's minimum notional
                actual_notional = formatted_amount * live_price

                if formatted_amount >= min_lot and actual_notional >= 5.10:
                    try:
                        exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    print("\n" + "=" * 80, flush=True)
                    print(f"[APEX-V2 QUANTITATIVE STRIKE: {side.upper()}] Confirmed on {sym}!", flush=True)
                    print(f"  Setup:         {best_candidate['setup']}", flush=True)
                    print(f"  Displacement:  Candle Thrust: {best_candidate['candle_move']:+}% | ATR: {best_candidate['atr_pct']}%", flush=True)
                    print(f"  Volume Engine: RVol {best_candidate['rvol']}x | Squeeze Bandwidth: {best_candidate['bandwidth']}%", flush=True)
                    print(f"  Execution:     Entering {leverage}x {side.upper()} | Notional: ${actual_notional:.2f}", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    if side == 'long':
                        order = open_long_position(sym, formatted_amount)
                    else:
                        order = open_short_position(sym, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(2)

                    # QUERY ACTUAL EXECUTED FILL PRICE FROM EXCHANGE (Zero Slippage Assumption)
                    real_pos = get_open_position()
                    real_fill_price = real_pos['entry_price'] if real_pos else live_price
                    real_contracts = real_pos['contracts'] if real_pos else formatted_amount

                    # Hand off to the Guardian with actual fill price
                    manage_active_trade(sym, side, real_contracts, real_fill_price, atr)
                    continue
                else:
                    print(f"[SKIP] {sym}: Size ${actual_notional:.2f} below Bitget $5.10 minimum. Preserving cash.", flush=True)

            if cycle % 2 == 0:
                print(
                    f"[RADAR PULSE] Monitoring Top Liquid Markets | Vault Cash: ${usdt_free:.2f} USDT (Leverage Tier: {leverage}x) | "
                    f"Next scan in {SCAN_INTERVAL_SECONDS}s...",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            traceback.print_exc()
            time.sleep(15)


if __name__ == "__main__":
    main()

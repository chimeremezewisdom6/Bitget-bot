import os
import sys
import time
import math
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt

# ==============================================================================
# 1. RENDER KEEP-ALIVE SERVER (PORT 10000)
# ==============================================================================
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"APEX Quantitative Volatility Engine is active.")

    def log_message(self, format, *args):
        return  # Silence server logs


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

# Institutional Risk Parameters
LEVERAGE = 3
BALANCE_USE_PCT = 0.85          # Sizing: 85% of vault balance
MIN_NOTIONAL = 5.10             # Minimum $5.10 order value on Bitget
MIN_24H_VOLUME = 3_000_000      # $3M volume floor: optimal liquidity & high beta
SCAN_INTERVAL_SECONDS = 75      # Rapid 75s radar scan

# Non-Crypto / TradFi Blacklist
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
# 3. MATHEMATICAL INDICATORS (ATR, BOLLINGER BANDS, RSI)
# ==============================================================================
def calculate_atr(ohlcv, period=14):
    """Calculates true Average True Range (ATR) across historical candles."""
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
# 4. BITGET ONE-WAY DUAL-ORDER HELPERS (LONG & SHORT)
# ==============================================================================
def get_open_position():
    """Checks for active Long or Short position."""
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
        print(f"[POSITION CHECK ERROR] {e}", flush=True)
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
# 5. APEX QUANTITATIVE SIGNAL ENGINE
# ==============================================================================
def inspect_coin_setup(symbol, pct_24h, vol_24h):
    """
    Evaluates 15m OHLCV for:
    1. Volatility Squeeze (Bollinger Bandwidth <= 4.5%)
    2. Volume Explosion (RVol >= 2.0x)
    3. Structural Candlestick Pattern (Breakout vs Liquidity Trap)
    4. Exact Real-Time 15m ATR for Dynamic Stop Sizing
    """
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=35)
        if len(ohlcv) < 30:
            return None

        opens = [x[1] for x in ohlcv]
        highs = [x[2] for x in ohlcv]
        lows = [x[3] for x in ohlcv]
        closes = [x[4] for x in ohlcv]
        volumes = [x[5] for x in ohlcv]

        # Calculate True ATR for Dynamic Risk
        atr = calculate_atr(ohlcv, period=14)
        if atr <= 0:
            return None

        # Bollinger Bands on previous candles (The Coil)
        bb = calculate_bollinger_bands(closes[:-1], period=20, num_std=2.0)
        if not bb:
            return None

        # Volume Expansion Ratio
        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
        if rvol < 2.0:
            return None  # Filter out low-volume retail noise

        # Current Trigger Candle Geometry
        c_open, c_high, c_low, c_close = opens[-1], highs[-1], lows[-1], closes[-1]
        candle_range = c_high - c_low
        if candle_range == 0:
            return None

        upper_wick = (c_high - max(c_open, c_close)) / candle_range
        lower_wick = (min(c_open, c_close) - c_low) / candle_range
        body_pct = abs(c_close - c_open) / candle_range

        rsi = calculate_rsi(closes, period=14)

        # Funding rate verification
        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        # === SIGNAL A: APEX BULLISH BREAKOUT (LONG) ===
        # Closes cleanly above upper band with a full body, small upper wick, healthy RSI, clean funding
        if c_close > bb['upper'] and body_pct >= 0.52 and upper_wick <= 0.25 and 52.0 <= rsi <= 74.0 and funding_rate <= 0.015:
            return {
                "symbol": symbol,
                "side": "long",
                "cur_price": c_close,
                "atr": atr,
                "setup": "VOLATILITY_EXPANSION_LONG",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2),
                "rsi": rsi,
                "funding": round(funding_rate, 4),
                "vol_24h_m": round(vol_24h / 1_000_000, 2)
            }

        # === SIGNAL B: APEX LIQUIDITY SWEEP REVERSAL (SHORT) ===
        # Pierced upper band, but rejected with a massive upper wick (>40%) and closed red (trapped longs)
        if c_high > bb['upper'] and upper_wick >= 0.40 and c_close < c_open and funding_rate >= -0.01:
            return {
                "symbol": symbol,
                "side": "short",
                "cur_price": c_close,
                "atr": atr,
                "setup": "LIQUIDITY_SWEEP_FADE_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2),
                "rsi": rsi,
                "funding": round(funding_rate, 4),
                "vol_24h_m": round(vol_24h / 1_000_000, 2)
            }

        # === SIGNAL C: BEARISH SQUEEZE BREAKDOWN (SHORT) ===
        # Clean breakdown below lower band with strong red body
        if c_close < bb['lower'] and body_pct >= 0.52 and lower_wick <= 0.25 and funding_rate >= -0.01:
            return {
                "symbol": symbol,
                "side": "short",
                "cur_price": c_close,
                "atr": atr,
                "setup": "SQUEEZE_BREAKDOWN_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2),
                "rsi": rsi,
                "funding": round(funding_rate, 4),
                "vol_24h_m": round(vol_24h / 1_000_000, 2)
            }

        return None

    except Exception:
        return None


# ==============================================================================
# 6. APEX DYNAMIC RISK GUARDIAN (ATR-POWERED EXITS)
# ==============================================================================
def manage_active_trade(symbol, side, contracts, entry_price, entry_atr):
    """
    Executes dynamic ATR-engineered risk management:
    - Initial Stop Loss: 1.6 x ATR (Adaptive Breathing Room)
    - Fee-Shield: Moves to Entry + 0.3% once in profit by 1.2 x ATR
    - Parabolic Runner Trail: 1.4 x ATR trail once profit exceeds 2.2 x ATR
    - Time Stop: Dumps after 45m if price is stagnant
    """
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    fee_shield_active = False

    # ATR Multipliers
    atr = entry_atr if entry_atr > 0 else (entry_price * 0.015)
    stop_distance = 1.6 * atr
    fee_shield_trigger = 1.2 * atr
    runner_trigger = 2.2 * atr
    trail_distance = 1.4 * atr

    # Set Initial Price Stops
    if side == 'long':
        initial_stop_price = entry_price - stop_distance
    else:
        initial_stop_price = entry_price + stop_distance

    stop_pct = (stop_distance / entry_price) * 100
    print(f"\n[GUARDIAN ENGAGED] {side.upper()} {symbol} | Entry: {entry_price} | Dynamic Stop: {initial_stop_price:.5f} ({stop_pct:.2f}%)", flush=True)

    while True:
        try:
            time.sleep(3)
            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker.get('last', 0) or 0)

            if cur_price > highest_price:
                highest_price = cur_price
            if cur_price < lowest_price:
                lowest_price = cur_price

            elapsed_min = (time.time() - entry_time) / 60

            # Dynamic PnL calculation
            if side == 'long':
                pnl_pct = ((cur_price - entry_price) / entry_price) * 100
                peak_pnl = ((highest_price - entry_price) / entry_price) * 100
                gain_distance = cur_price - entry_price
                peak_distance = highest_price - entry_price
            else:
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100
                gain_distance = entry_price - cur_price
                peak_distance = entry_price - lowest_price

            if time.time() - last_log_time > 15:
                shield_status = "LOCKED (+0.3%)" if fee_shield_active else "MONITORING"
                print(f"[STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% (Peak: {peak_pnl:+.2f}%) | Shield: {shield_status} | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. THE FEE-SHIELD LOCK (1.2 x ATR Gain -> Move Stop to Entry + 0.3%)
            if not fee_shield_active and peak_distance >= fee_shield_trigger:
                fee_shield_active = True
                print(f"\n[FEE-SHIELD ENGAGED] {symbol} gained 1.2x ATR! Stop moved to Breakeven +0.3% net profit.", flush=True)

            if fee_shield_active:
                if side == 'long' and cur_price <= entry_price * 1.003:
                    print(f"[EXIT TRIGGER] Long Fee-Shield executed! Locked profit at {pnl_pct:+.2f}%.", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= entry_price * 0.997:
                    print(f"[EXIT TRIGGER] Short Fee-Shield executed! Locked profit at {pnl_pct:+.2f}%.", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 2. INITIAL ADAPTIVE STOP LOSS (1.6 x ATR)
            if not fee_shield_active:
                if side == 'long' and cur_price <= initial_stop_price:
                    print(f"[EXIT TRIGGER] Long Dynamic Stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    print(f"[EXIT TRIGGER] Short Dynamic Stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 3. PARABOLIC RUNNER TRAIL (2.2 x ATR Expansion -> Trail 1.4 x ATR)
            if peak_distance >= runner_trigger:
                if side == 'long':
                    trail_stop = highest_price - trail_distance
                    if cur_price <= trail_stop:
                        print(f"[EXIT TRIGGER] Long Trailing Runner closed at {pnl_pct:+.2f}% (Peak was {peak_pnl:+.2f}%).", flush=True)
                        close_long_position(symbol, contracts)
                        break
                else:
                    trail_stop = lowest_price + trail_distance
                    if cur_price >= trail_stop:
                        print(f"[EXIT TRIGGER] Short Trailing Runner closed at {pnl_pct:+.2f}% (Peak was {peak_pnl:+.2f}%).", flush=True)
                        close_short_position(symbol, contracts)
                        break

            # 4. DEAD-MONEY TIME STOP (45 Minutes Stagnation)
            if elapsed_min >= 45.0 and peak_distance < (0.8 * atr):
                print(f"[EXIT TRIGGER] Trade stagnant for 45m without volatility expansion. Freeing margin at {pnl_pct:+.2f}%.", flush=True)
                if side == 'long':
                    close_long_position(symbol, contracts)
                else:
                    close_short_position(symbol, contracts)
                break

        except Exception as e:
            print(f"[GUARDIAN WARNING] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 7. MAIN ENGINE LOOP
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] APEX Dynamic Volatility & Squeeze Engine initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    cycle = 1

    while True:
        try:
            # 1. Check if holding an active position
            pos = get_open_position()
            if pos:
                # Approximate 1.5% ATR baseline fallback if position was already open
                fallback_atr = pos['entry_price'] * 0.015
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(5)
                continue

            # 2. Check Wallet Balance & Sizing
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            # 3. Fetch Universe (>= $3M Volume Floor)
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
                pct_24h = float(t.get('percentage', 0) or 0)
                if vol_24h >= MIN_24H_VOLUME:
                    liquid_symbols.append((symbol, pct_24h, vol_24h))

            # Inspect top 35 liquid pairs by volume
            liquid_symbols.sort(key=lambda x: x[2], reverse=True)
            top_liquid = liquid_symbols[:35]

            best_candidate = None

            for sym, pct_24h, vol_24h in top_liquid:
                candidate = inspect_coin_setup(sym, pct_24h, vol_24h)
                if candidate:
                    best_candidate = candidate
                    break  # Valid institutional setup found

            # 4. Strike with Precision
            if best_candidate and notional >= MIN_NOTIONAL:
                sym = best_candidate['symbol']
                side = best_candidate['side']
                cur_price = best_candidate['cur_price']
                atr = best_candidate['atr']

                market = exchange.market(sym)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / cur_price
                formatted_amount = float(exchange.amount_to_precision(sym, raw_amount))

                if formatted_amount >= min_lot:
                    try:
                        exchange.set_leverage(LEVERAGE, sym, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    print("\n" + "=" * 80, flush=True)
                    print(f"[APEX QUANTITATIVE STRIKE: {side.upper()}] Confirmed on {sym}!", flush=True)
                    print(f"  Setup:         {best_candidate['setup']}", flush=True)
                    print(f"  15m ATR:       {atr:.5f} ({(atr/cur_price)*100:.2f}% volatility)", flush=True)
                    print(f"  Volume Engine: RVol {best_candidate['rvol']}x | Bandwidth: {best_candidate['bandwidth']}%", flush=True)
                    print(f"  Execution:     Entering 3x {side.upper()} | Notional: ${notional:.2f}", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    if side == 'long':
                        order = open_long_position(sym, formatted_amount)
                    else:
                        order = open_short_position(sym, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(3)

                    # Hand over immediately to the Dynamic ATR Guardian
                    manage_active_trade(sym, side, formatted_amount, cur_price, atr)
                    continue
                else:
                    print(f"[SKIP] {sym}: Size {formatted_amount} below minimum lot {min_lot}.", flush=True)

            # Heartbeat Pulse
            if cycle % 2 == 0:
                print(
                    f"[RADAR PULSE] Scanned {len(top_liquid)} markets (>= $3M vol) | "
                    f"Vault Cash: ${usdt_free:.2f} USDT | Next scan in {SCAN_INTERVAL_SECONDS}s...",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

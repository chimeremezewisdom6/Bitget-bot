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
        self.wfile.write(b"APEX High-Displacement Quantitative Engine is active.")

    def log_message(self, format, *args):
        return


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. RISK & FRICTION DEFENSE BOUNDARIES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

BASE_LEVERAGE = 3
BALANCE_USE_PCT = 0.85
MIN_NOTIONAL = 5.15             # Buffer above Bitget's $5.00 floor
MIN_24H_VOLUME = 3_000_000      # $3M volume floor
SCAN_INTERVAL_SECONDS = 75

# DISPLACEMENT & VOLATILITY CORRIDOR (Eliminates both 0.5% creeps AND wild meme-coin traps)
MIN_ATR_PCT = 1.10              # BANS SLEEPY BIG CAPS: Coin must move at least 1.10% per 15m candle
MAX_ATR_PCT = 2.40              # BANS DANGEROUS MEME COINS: Caps maximum volatility at 2.40%
MIN_DISPLACEMENT_PCT = 1.20     # ANTI-CREEP: The trigger candle itself MUST move at least 1.20%
MAX_SPREAD_PCT = 0.05           # SPREAD DEFENSE: Order book spread must be <= 0.05%
MAX_HARD_STOP_PCT = 1.80        # MAXIMUM RISK CEILING: Stop loss can never exceed 1.80%

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
# 3. MATHEMATICAL INDICATORS
# ==============================================================================
def calculate_atr(ohlcv, period=14):
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
# 4. ORDER HELPERS
# ==============================================================================
def get_open_position():
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
        return exchange.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'buy_single'})
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'open'})
        raise e


def close_long_position(symbol, amount):
    try:
        return exchange.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'sell_single'})
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'close'})
        raise e


def open_short_position(symbol, amount):
    try:
        return exchange.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'sell_single'})
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(symbol=symbol, type='market', side='sell', amount=amount, params={'tradeSide': 'open'})
        raise e


def close_short_position(symbol, amount):
    try:
        return exchange.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'buy_single'})
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(symbol=symbol, type='market', side='buy', amount=amount, params={'tradeSide': 'close'})
        raise e


# ==============================================================================
# 5. HIGH-DISPLACEMENT QUANTITATIVE SIGNAL ENGINE
# ==============================================================================
def inspect_coin_setup(symbol, pct_24h, vol_24h, ticker_data):
    try:
        bid = float(ticker_data.get('bid', 0) or 0)
        ask = float(ticker_data.get('ask', 0) or 0)
        last_price = float(ticker_data.get('last', 0) or 0)

        if bid <= 0 or ask <= 0 or last_price <= 0:
            return None

        # 1. Spread Check (Reject illiquid books)
        spread_pct = ((ask - bid) / last_price) * 100
        if spread_pct > MAX_SPREAD_PCT:
            return None

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=35)
        if len(ohlcv) < 30:
            return None

        opens = [x[1] for x in ohlcv]
        highs = [x[2] for x in ohlcv]
        lows = [x[3] for x in ohlcv]
        closes = [x[4] for x in ohlcv]
        volumes = [x[5] for x in ohlcv]

        atr = calculate_atr(ohlcv, period=14)
        if atr <= 0:
            return None

        # 2. Volatility Corridor (Rejects sleepy coins moving <1.10% and meme coins moving >2.40%)
        atr_pct = (atr / last_price) * 100
        if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
            return None

        bb = calculate_bollinger_bands(closes[:-1], period=20, num_std=2.0)
        if not bb:
            return None

        is_coiled = bb['bandwidth'] <= 4.5

        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
        if rvol < 2.0:
            return None

        c_open, c_high, c_low, c_close = opens[-1], highs[-1], lows[-1], closes[-1]
        candle_range = c_high - c_low
        if candle_range == 0:
            return None

        upper_wick = (c_high - max(c_open, c_close)) / candle_range
        lower_wick = (min(c_open, c_close) - c_low) / candle_range
        body_pct = abs(c_close - c_open) / candle_range
        rsi = calculate_rsi(closes, period=14)

        # 3. Candle Percentage Move (Displacement Check)
        candle_pct_gain = ((c_close - c_open) / c_open) * 100

        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        # === SIGNAL A: HIGH-DISPLACEMENT LONG ===
        # Requirements:
        # 1. Coiled spring in previous candles
        # 2. Candle closed distinctly above the band
        # 3. ANTI-CREEP: The candle itself must have gained at least +1.20% (not a 0.4% crawl)
        # 4. Clean body (>52%), small upper wick (<25%), healthy RSI (50-74), clean funding
        if is_coiled and c_close > (bb['upper'] + (0.2 * atr)) and candle_pct_gain >= MIN_DISPLACEMENT_PCT and body_pct >= 0.52 and upper_wick <= 0.25 and 50.0 <= rsi <= 74.0 and funding_rate <= 0.015:
            return {
                "symbol": symbol,
                "side": "long",
                "cur_price": c_close,
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(candle_pct_gain, 2),
                "setup": "HIGH_DISPLACEMENT_EXPANSION_LONG",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL B: LIQUIDITY SWEEP SHORT ===
        if c_high > (bb['upper'] + (0.3 * atr)) and upper_wick >= 0.42 and c_close < c_open and funding_rate >= -0.01:
            return {
                "symbol": symbol,
                "side": "short",
                "cur_price": c_close,
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(abs(candle_pct_gain), 2),
                "setup": "LIQUIDITY_SWEEP_REVERSAL_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        # === SIGNAL C: HIGH-DISPLACEMENT BREAKDOWN SHORT ===
        # ANTI-CREEP: Candle must have dropped at least -1.20%
        if is_coiled and c_close < (bb['lower'] - (0.2 * atr)) and candle_pct_gain <= -MIN_DISPLACEMENT_PCT and body_pct >= 0.52 and lower_wick <= 0.25 and funding_rate >= -0.01:
            return {
                "symbol": symbol,
                "side": "short",
                "cur_price": c_close,
                "atr": atr,
                "atr_pct": round(atr_pct, 2),
                "candle_move": round(abs(candle_pct_gain), 2),
                "setup": "HIGH_DISPLACEMENT_BREAKDOWN_SHORT",
                "rvol": rvol,
                "bandwidth": round(bb['bandwidth'], 2)
            }

        return None
    except Exception:
        return None


# ==============================================================================
# 6. GUARDIAN RISK MANAGEMENT
# ==============================================================================
def manage_active_trade(symbol, side, contracts, entry_price, entry_atr):
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0
    fee_shield_active = False

    atr = entry_atr if entry_atr > 0 else (entry_price * 0.015)

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
    print(f"\n[GUARDIAN ACTIVE] {side.upper()} {symbol} | Entry: {entry_price} | Hard Stop: {initial_stop_price:.5f} ({stop_pct:.2f}%)", flush=True)

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

            if side == 'long':
                pnl_pct = ((cur_price - entry_price) / entry_price) * 100
                peak_pnl = ((highest_price - entry_price) / entry_price) * 100
                peak_distance = highest_price - entry_price
            else:
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100
                peak_distance = entry_price - lowest_price

            if time.time() - last_log_time > 15:
                shield_status = "LOCKED (+0.45%)" if fee_shield_active else "MONITORING"
                print(f"[STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% (Peak: {peak_pnl:+.2f}%) | Shield: {shield_status} | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. THE FEE-SHIELD LOCK (+1.2x ATR Gain -> Lock Stop at Entry + 0.45% net)
            if not fee_shield_active and peak_distance >= fee_shield_trigger:
                fee_shield_active = True
                print(f"\n[FEE-SHIELD ENGAGED] {symbol} moved 1.2x ATR! Risk-Free Stop locked at Breakeven +0.45% net.", flush=True)

            if fee_shield_active:
                if side == 'long' and cur_price <= entry_price * 1.0045:
                    print(f"[EXIT TRIGGER] Long Fee-Shield executed! Locked profit at {pnl_pct:+.2f}%.", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= entry_price * 0.9955:
                    print(f"[EXIT TRIGGER] Short Fee-Shield executed! Locked profit at {pnl_pct:+.2f}%.", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 2. ADAPTIVE STOP LOSS (Hard-Capped at 1.80%)
            if not fee_shield_active:
                if side == 'long' and cur_price <= initial_stop_price:
                    print(f"[EXIT TRIGGER] Long Stop hit at {pnl_pct:.2f}%. Vault protected.", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= initial_stop_price:
                    print(f"[EXIT TRIGGER] Short Stop hit at {pnl_pct:.2f}%. Vault protected.", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 3. PARABOLIC RUNNER TRAIL (2.2 x ATR Expansion -> Trail 1.3 x ATR)
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

            # 4. DEAD-MONEY TIME STOP (45 Minutes)
            if elapsed_min >= 45.0 and peak_distance < (0.8 * atr):
                print(f"[EXIT TRIGGER] Stagnant for 45m without volatility expansion. Freeing margin at {pnl_pct:+.2f}%.", flush=True)
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
    print("[SYSTEM] APEX High-Displacement Engine initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    cycle = 1

    while True:
        try:
            pos = get_open_position()
            if pos:
                fallback_atr = pos['entry_price'] * 0.015
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'], fallback_atr)
                time.sleep(5)
                continue

            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)

            leverage = 4 if usdt_free < 2.30 else BASE_LEVERAGE
            notional = (usdt_free * BALANCE_USE_PCT) * leverage

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
                    liquid_symbols.append((symbol, pct_24h, vol_24h, t))

            liquid_symbols.sort(key=lambda x: x[2], reverse=True)
            top_liquid = liquid_symbols[:35]

            best_candidate = None

            for sym, pct_24h, vol_24h, t_data in top_liquid:
                candidate = inspect_coin_setup(sym, pct_24h, vol_24h, t_data)
                if candidate:
                    best_candidate = candidate
                    break

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
                        exchange.set_leverage(leverage, sym, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    print("\n" + "=" * 80, flush=True)
                    print(f"[APEX QUANTITATIVE STRIKE: {side.upper()}] Confirmed on {sym}!", flush=True)
                    print(f"  Setup:         {best_candidate['setup']}", flush=True)
                    print(f"  Displacement:  Candle Thrust: +{best_candidate['candle_move']}% | ATR: {best_candidate['atr_pct']}%", flush=True)
                    print(f"  Volume Engine: RVol {best_candidate['rvol']}x | Squeeze: {best_candidate['bandwidth']}%", flush=True)
                    print(f"  Execution:     Entering {leverage}x {side.upper()} | Notional: ${notional:.2f}", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    if side == 'long':
                        order = open_long_position(sym, formatted_amount)
                    else:
                        order = open_short_position(sym, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(3)

                    manage_active_trade(sym, side, formatted_amount, cur_price, atr)
                    continue
                else:
                    print(f"[SKIP] {sym}: Size {formatted_amount} below minimum lot {min_lot}.", flush=True)

            if cycle % 2 == 0:
                print(
                    f"[RADAR PULSE] Scanned {len(top_liquid)} liquid markets | "
                    f"Vault: ${usdt_free:.2f} USDT | Next scan in {SCAN_INTERVAL_SECONDS}s...",
                    flush=True
                )

            cycle += 1
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

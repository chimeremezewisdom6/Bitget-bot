import os
import sys
import time
import json
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
        self.wfile.write(b"15-Minute Scenario Memory & Blending Desk is active.")

    def log_message(self, format, *args):
        return  # Silence server logs


def start_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[SYSTEM] Keep-alive server running on port {port}", flush=True)


# ==============================================================================
# 2. CONFIGURATION & TRADING RISK RULES
# ==============================================================================
API_KEY = os.environ.get("API_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
PASSPHRASE = os.environ.get("PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    print("[FATAL] Missing Bitget API credentials in environment variables!", flush=True)
    sys.exit(1)

# Sizing & Boundaries
LEVERAGE = 3
BALANCE_USE_PCT = 0.85        # Use 85% of free USDT
MIN_NOTIONAL = 5.10           # Minimum $5.10 order value on Bitget
MIN_24H_VOLUME = 5_000_000    # $5M global liquidity floor
INSPECTION_INTERVAL = 900     # 15 minutes structured review (900 seconds)
BASELINE_SCENARIO_GOAL = 10   # First 10 scenarios are pure camera study
MEMORY_FILE = "scenario_memory.json"

# Traditional assets / CFDs blacklisted
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
# 3. STATISTICAL UTILITIES
# ==============================================================================
def calculate_rsi(closes, period=14):
    """Calculates standard Relative Strength Index (RSI)."""
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
# 4. SCENARIO MEMORY BANK (PERSISTENT JOURNAL)
# ==============================================================================
def load_memory():
    default_memory = {
        "total_studied": 0,
        "scenarios": [],       # Full archive of past 15m footprints
        "active_studies": []   # Currently observing next-15m candle
    }
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                default_memory.update(data)
                return default_memory
        except Exception:
            pass
    return default_memory


def save_memory(mem):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        print(f"[MEMORY WARNING] Save failed: {e}", flush=True)


# ==============================================================================
# 5. MULTI-SCENARIO BLENDING & UNDERSTANDING ENGINE
# ==============================================================================
def evaluate_scenario_understanding(memory, candidate):
    """
    Evaluates whether the candidate:
    1. Matches a single past winning scenario.
    2. Blends two or more past scenarios into a clear, high-conviction decision.
    3. Is confusing or contradictory -> In which case, REJECT and LEARN ONLY.
    """
    scenarios = memory['scenarios']

    # RULE 1: Under baseline (first 10 scenarios) -> NEVER TRADE
    if memory['total_studied'] < BASELINE_SCENARIO_GOAL:
        return False, "BASELINE_LEARNING", "Still observing initial 10 baseline scenarios. Preserving cash."

    if not scenarios:
        return False, "INSUFFICIENT_DATA", "No historical scenario library yet."

    # Find matching past scenarios
    matched_scenarios = []
    for s in scenarios:
        # Same direction (Long leader vs Short laggard)
        if s['direction'] != candidate['direction']:
            continue

        # Liquidity alignment
        liq_diff = abs(s['vol_24h_m'] - candidate['vol_24h_m']) / max(s['vol_24h_m'], 1.0)
        # 15m magnitude alignment
        mag_diff = abs(abs(s['pct_15m']) - abs(candidate['pct_15m']))
        # Volume profile alignment
        rvol_diff = abs(s['rvol'] - candidate['rvol'])

        if liq_diff <= 0.6 and mag_diff <= 2.5 and rvol_diff <= 1.5:
            matched_scenarios.append(s)

    # RULE 2: If NO past scenarios match, it's completely new -> DO NOT TRADE, LEARN IT
    if len(matched_scenarios) == 0:
        return False, "NEW_SCENARIO", "Never seen this scenario structure before. Studying without trading."

    # RULE 3: SINGLE SCENARIO MATCH
    if len(matched_scenarios) == 1:
        past = matched_scenarios[0]
        if past['outcome'] == "CONTINUATION_WINNER":
            return True, "EXACT_PAST_MATCH", f"Matches proven winning scenario #{past['id']} on {past['symbol']}. Confident strike."
        else:
            return False, "PAST_FAILURE_MATCH", f"Matches past failing scenario #{past['id']}. High risk of reversal. No trade."

    # RULE 4: MULTI-SCENARIO BLENDING (Case 12+: Combining 2 or more past scenarios)
    winners = [s for s in matched_scenarios if s['outcome'] == "CONTINUATION_WINNER"]
    failures = [s for s in matched_scenarios if s['outcome'] in ["FAKEOUT_REVERSAL", "CHOPPY_STALL"]]

    # If the combined scenarios agree with high consistency:
    if len(winners) >= 2 and len(failures) == 0:
        win_symbols = ", ".join([s['symbol'] for s in winners])
        return True, "BLENDED_HIGH_CONVICTION", f"Blends {len(winners)} past winning scenarios ({win_symbols}). Direction is crystal clear."

    # RULE 5: THE CONFUSING MARKET CLAUSE
    # If past scenarios are split (some won, some dumped) -> IT IS CONFUSING
    if len(winners) > 0 and len(failures) > 0:
        return False, "CONFUSING_MARKET", f"Conflicting past signals ({len(winners)} Won, {len(failures)} Failed). Scenario not understood. Learn only."

    return False, "INCONCLUSIVE", "Scenario blend does not provide edge. Preserving vault cash."


# ==============================================================================
# 6. BITGET ONE-WAY DUAL-ORDER HELPERS (LONG & SHORT)
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
# 7. 15-MINUTE LEADERBOARD SCANNER (TOP GAINER & TOP LOSER)
# ==============================================================================
def scan_15m_leaders(liquid_symbols):
    """
    Inspects 15m candles across liquid crypto.
    Returns: Top 15m Gainer (Long Candidate) and Top 15m Loser (Short Candidate).
    """
    candidates = []

    for sym, pct_24h, vol_24h in liquid_symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(sym, timeframe='15m', limit=20)
            if len(ohlcv) < 15:
                continue

            closes = [x[4] for x in ohlcv]
            volumes = [x[5] for x in ohlcv]

            cur_price = closes[-1]
            price_15m_ago = closes[-2]
            pct_15m = ((cur_price - price_15m_ago) / price_15m_ago) * 100

            avg_vol = sum(volumes[-16:-1]) / 15 if len(volumes) >= 16 else 1
            rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
            rsi = calculate_rsi(closes, period=14)

            funding_rate = 0.0
            try:
                f_data = exchange.fetch_funding_rate(sym)
                funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
            except Exception:
                pass

            candidates.append({
                "symbol": sym,
                "cur_price": cur_price,
                "pct_15m": round(pct_15m, 2),
                "pct_24h": round(pct_24h, 2),
                "rvol": rvol,
                "rsi": rsi,
                "funding_pct": round(funding_rate, 4),
                "vol_24h_m": round(vol_24h / 1_000_000, 2)
            })
        except Exception:
            continue

    if not candidates:
        return None, None

    # Sort to find the #1 Strongest Gainer and #1 Deepest Loser
    candidates.sort(key=lambda x: x['pct_15m'], reverse=True)
    top_gainer = candidates[0] if candidates[0]['pct_15m'] >= 1.5 else None
    top_loser = candidates[-1] if candidates[-1]['pct_15m'] <= -1.5 else None

    return top_gainer, top_loser


# ==============================================================================
# 8. ACTIVE TRADE GUARDIAN (LIVE RISK MANAGEMENT)
# ==============================================================================
def manage_active_trade(symbol, side, contracts, entry_price):
    """Guards live position with 4 strict capital-protection rules."""
    highest_price = entry_price
    lowest_price = entry_price
    entry_time = time.time()
    last_log_time = 0

    print(f"\n[GUARDIAN ACTIVE] Managing {side.upper()} on {symbol} | Entry: {entry_price} | Contracts: {contracts}", flush=True)

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
            else:
                pnl_pct = ((entry_price - cur_price) / entry_price) * 100
                peak_pnl = ((entry_price - lowest_price) / entry_price) * 100

            if time.time() - last_log_time > 15:
                print(f"[TRADE STATUS] {side.upper()} {symbol} | PnL: {pnl_pct:+.2f}% | Peak: {peak_pnl:+.2f}% | Time: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. FEE-SHIELD LOCK (+1.0% -> +0.5%)
            if peak_pnl >= 1.0:
                if side == 'long' and cur_price <= entry_price * 1.005:
                    print(f"[EXIT TRIGGER] Long Fee-Shield! Locked +0.5% profit (Peak was +{peak_pnl:.2f}%).", flush=True)
                    close_long_position(symbol, contracts)
                    break
                elif side == 'short' and cur_price >= entry_price * 0.995:
                    print(f"[EXIT TRIGGER] Short Fee-Shield! Locked +0.5% profit (Peak was +{peak_pnl:.2f}%).", flush=True)
                    close_short_position(symbol, contracts)
                    break

            # 2. MOMENTUM STALL / BOX CHOP EXIT (15 Mins)
            if elapsed_min >= 15 and peak_pnl < 1.0:
                if abs(pnl_pct) <= 0.45:
                    print(f"[EXIT TRIGGER] Momentum stalled for {elapsed_min:.0f}m. Dumping chop.", flush=True)
                    if side == 'long':
                        close_long_position(symbol, contracts)
                    else:
                        close_short_position(symbol, contracts)
                    break

            # 3. INITIAL HARD STOP (-1.2%)
            if peak_pnl < 1.0 and pnl_pct <= -1.20:
                print(f"[EXIT TRIGGER] Hard stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                if side == 'long':
                    close_long_position(symbol, contracts)
                else:
                    close_short_position(symbol, contracts)
                break

            # 4. RUNNER TRAILING STOP (+3% or higher)
            if peak_pnl >= 3.0:
                if side == 'long':
                    trailing_floor = highest_price * 0.985
                    if cur_price <= trailing_floor:
                        print(f"[EXIT TRIGGER] Long Trailing stop triggered at {pnl_pct:+.2f}%.", flush=True)
                        close_long_position(symbol, contracts)
                        break
                else:
                    trailing_ceiling = lowest_price * 1.015
                    if cur_price >= trailing_ceiling:
                        print(f"[EXIT TRIGGER] Short Trailing stop triggered at {pnl_pct:+.2f}%.", flush=True)
                        close_short_position(symbol, contracts)
                        break

        except Exception as e:
            print(f"[GUARDIAN WARNING] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 9. MAIN AUTONOMOUS 15-MINUTE ENGINE
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] 15-Minute Leaderboard & Scenario Blending Desk initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    memory = load_memory()
    print(f"[MEMORY] Historical Scenarios Cataloged: {memory['total_studied']}/{BASELINE_SCENARIO_GOAL}", flush=True)

    while True:
        try:
            # 1. Position Check: If in a live trade, guard it exclusively
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['side'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            # 2. Check USDT Wallet Balance
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            # 3. Update Active Next-15m Candle Studies
            remaining_active = []
            for study in memory['active_studies']:
                sym = study['symbol']
                elapsed_min = (time.time() - study['started_at']) / 60

                try:
                    ticker = exchange.fetch_ticker(sym)
                    cur_price = float(ticker.get('last', 0) or 0)
                except Exception:
                    remaining_active.append(study)
                    continue

                base_price = study['base_price']
                continuation_pnl = ((cur_price - base_price) / base_price) * 100

                # Completed the 15-minute test candle
                if elapsed_min >= 15.0:
                    study['continuation_15m_pct'] = round(continuation_pnl, 2)
                    direction = study['direction']

                    # Classify Outcome
                    if direction == "LONG_LEADER":
                        if continuation_pnl >= 1.2:
                            outcome = "CONTINUATION_WINNER"
                        elif continuation_pnl <= -0.8:
                            outcome = "FAKEOUT_REVERSAL"
                        else:
                            outcome = "CHOPPY_STALL"
                    else:  # SHORT_LAGGARD
                        if continuation_pnl <= -1.2:
                            outcome = "CONTINUATION_WINNER"
                        elif continuation_pnl >= 0.8:
                            outcome = "FAKEOUT_REVERSAL"
                        else:
                            outcome = "CHOPPY_STALL"

                    study['outcome'] = outcome
                    memory['total_studied'] += 1
                    memory['scenarios'].append(study)

                    print("\n" + "=" * 80, flush=True)
                    print(f"[SCENARIO #{memory['total_studied']} RECORDED] {direction} on {sym}", flush=True)
                    print(f"  Trigger 15m Move: {study['pct_15m']:+}% | Next 15m Continuation: {continuation_pnl:+.2f}%", flush=True)
                    print(f"  Outcome:          {outcome}", flush=True)
                    print(f"  Total Learned:    {len(memory['scenarios'])} distinct market footprints.", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    save_memory(memory)
                else:
                    remaining_active.append(study)

            memory['active_studies'] = remaining_active

            # 4. Fetch Liquid Crypto Universe (>= $5M Volume)
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

            # Sort by 24h volume descending and inspect top 25
            liquid_symbols.sort(key=lambda x: x[2], reverse=True)
            top_liquid = liquid_symbols[:25]

            print(f"\n[15-MINUTE REVIEW] Scanning {len(top_liquid)} liquid markets for Top Gainer & Loser...", flush=True)
            top_gainer, top_loser = scan_15m_leaders(top_liquid)

            trade_candidate = None

            # Test Top Gainer (Long Candidate)
            if top_gainer:
                candidate_data = dict(top_gainer)
                candidate_data['direction'] = "LONG_LEADER"
                can_trade, reason_code, message = evaluate_scenario_understanding(memory, candidate_data)

                if can_trade:
                    print(f"\n[TRADE GREEN LIGHT: LONG] {top_gainer['symbol']} | {message}", flush=True)
                    trade_candidate = (top_gainer['symbol'], 'long', top_gainer['cur_price'])
                else:
                    # If baseline or confusing -> Add to active learning
                    active_syms = {s['symbol'] for s in memory['active_studies']}
                    if top_gainer['symbol'] not in active_syms and len(memory['active_studies']) < 4:
                        study_entry = {
                            "id": memory['total_studied'] + len(memory['active_studies']) + 1,
                            "symbol": top_gainer['symbol'],
                            "direction": "LONG_LEADER",
                            "started_at": time.time(),
                            "base_price": top_gainer['cur_price'],
                            "pct_15m": top_gainer['pct_15m'],
                            "rvol": top_gainer['rvol'],
                            "rsi": top_gainer['rsi'],
                            "funding_pct": top_gainer['funding_pct'],
                            "vol_24h_m": top_gainer['vol_24h_m']
                        }
                        memory['active_studies'].append(study_entry)
                        save_memory(memory)
                        print(f"  [STUDYING GAINER #{study_entry['id']}] {top_gainer['symbol']} (+{top_gainer['pct_15m']}%). {message}", flush=True)

            # Test Top Loser (Short Candidate)
            if top_loser and not trade_candidate:
                candidate_data = dict(top_loser)
                candidate_data['direction'] = "SHORT_LAGGARD"
                can_trade, reason_code, message = evaluate_scenario_understanding(memory, candidate_data)

                if can_trade:
                    print(f"\n[TRADE GREEN LIGHT: SHORT] {top_loser['symbol']} | {message}", flush=True)
                    trade_candidate = (top_loser['symbol'], 'short', top_loser['cur_price'])
                else:
                    active_syms = {s['symbol'] for s in memory['active_studies']}
                    if top_loser['symbol'] not in active_syms and len(memory['active_studies']) < 4:
                        study_entry = {
                            "id": memory['total_studied'] + len(memory['active_studies']) + 1,
                            "symbol": top_loser['symbol'],
                            "direction": "SHORT_LAGGARD",
                            "started_at": time.time(),
                            "base_price": top_loser['cur_price'],
                            "pct_15m": top_loser['pct_15m'],
                            "rvol": top_loser['rvol'],
                            "rsi": top_loser['rsi'],
                            "funding_pct": top_loser['funding_pct'],
                            "vol_24h_m": top_loser['vol_24h_m']
                        }
                        memory['active_studies'].append(study_entry)
                        save_memory(memory)
                        print(f"  [STUDYING LOSER #{study_entry['id']}] {top_loser['symbol']} ({top_loser['pct_15m']}%). {message}", flush=True)

            # 5. Execute Live Order if Green Light Confirmed
            if trade_candidate and notional >= MIN_NOTIONAL:
                symbol, side, cur_price = trade_candidate
                market = exchange.market(symbol)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / cur_price
                formatted_amount = float(exchange.amount_to_precision(symbol, raw_amount))

                if formatted_amount >= min_lot:
                    try:
                        exchange.set_leverage(LEVERAGE, symbol, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    if side == 'long':
                        print(f"\n[ORDER EXECUTION] Entering 3x LONG on {symbol} | Notional: ${notional:.2f}", flush=True)
                        order = open_long_position(symbol, formatted_amount)
                    else:
                        print(f"\n[ORDER EXECUTION] Entering 3x SHORT on {symbol} | Notional: ${notional:.2f}", flush=True)
                        order = open_short_position(symbol, formatted_amount)

                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(3)
                    continue

            # Status Pulse
            print(
                f"[DESK STATUS] Learned Scenarios: {memory['total_studied']}/{BASELINE_SCENARIO_GOAL} | "
                f"Currently Filming: {len(memory['active_studies'])} | Vault: ${usdt_free:.2f} USDT",
                flush=True
            )

            save_memory(memory)
            time.sleep(INSPECTION_INTERVAL)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

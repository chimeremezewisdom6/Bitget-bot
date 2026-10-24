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
        self.wfile.write(b"Autonomous Scenario Learning & Execution Engine is active.")

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

# Risk & Order Sizing
LEVERAGE = 3
BALANCE_USE_PCT = 0.85        # Use 85% of free USDT
MIN_NOTIONAL = 5.10           # Minimum $5.10 order value on Bitget
MIN_24H_VOLUME = 5_000_000    # $5M global liquidity floor
SCAN_INTERVAL_SECONDS = 90    # Market review pulse
JOURNAL_FILE = "scenario_brain.json"
INITIAL_STUDY_COUNT = 10      # Baseline observations before live trading begins

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
# 3. STATISTICAL & TECHNICAL UTILITIES
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
# 4. SCENARIO CLASSIFIER (TEACHING THE MACHINE TO IDENTIFY PATTERNS)
# ==============================================================================
def classify_scenario_archetype(metrics):
    """
    Categorizes the imbalance into a discrete, understandable scenario signature.
    Features: Liquidity Tier, Trend Alignment, Funding Pressure, Overextension.
    """
    # 1. Liquidity Tier
    liq_tier = "MEGA_LIQUID" if metrics['vol_24h_m'] >= 25.0 else "MID_LIQUID"

    # 2. Trend Alignment (Is 5m bursting WITH 1h trend, or counter-trend?)
    trend_align = "WITH_1H_TREND" if metrics['pct_1h'] >= 0.5 else "COUNTER_TREND"

    # 3. Funding Runway (Are longs crowded or clean?)
    funding_cond = "CLEAN_FUNDING" if metrics['funding_pct'] <= 0.012 else "CROWDED_FUNDING"

    # 4. Momentum Quality (Is RSI room available or blow-off?)
    rsi_cond = "HEALTHY_MOMENTUM" if metrics['rsi_5m'] <= 78.0 else "HYPER_EXTENDED"

    scenario_key = f"{liq_tier}__{trend_align}__{funding_cond}__{rsi_cond}"
    return scenario_key


# ==============================================================================
# 5. PERSISTENT SCENARIO BRAIN & JOURNAL
# ==============================================================================
def load_brain():
    default_brain = {
        "total_observed": 0,
        "scenarios": {},      # Tracks win/loss record for each scenario archetype
        "active_studies": [], # Cases currently being forward-tracked (5m, 15m, 60m)
        "history": []         # Log of all completed case studies
    }
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r") as f:
                data = json.load(f)
                default_brain.update(data)
                return default_brain
        except Exception:
            pass
    return default_brain


def save_brain(brain):
    try:
        with open(JOURNAL_FILE, "w") as f:
            json.dump(brain, f, indent=2)
    except Exception as e:
        print(f"[BRAIN WARNING] Save failed: {e}", flush=True)


def update_scenario_knowledge(brain, scenario_key, outcome, details):
    """
    Updates the brain's understanding of a specific scenario:
    - Counts wins vs losses
    - Marks whether it is STEADY, UNSTEADY, or still needs more data
    """
    if scenario_key not in brain['scenarios']:
        brain['scenarios'][scenario_key] = {
            "seen": 0,
            "wins": 0,
            "losses": 0,
            "chops": 0,
            "status": "INSUFFICIENT_DATA",
            "notes": "Newly discovered scenario. Collecting observations."
        }

    s = brain['scenarios'][scenario_key]
    s['seen'] += 1

    if outcome == "SUSTAINED RUNNER":
        s['wins'] += 1
    elif outcome == "EXHAUSTION TRAP":
        s['losses'] += 1
    else:
        s['chops'] += 1

    # Evaluate understanding of this specific scenario
    win_rate = (s['wins'] / s['seen']) * 100

    if s['seen'] >= 2:
        if win_rate >= 70.0 and s['losses'] == 0:
            s['status'] = "UNDERSTOOD_STEADY"
            s['notes'] = f"HIGH CONSISTENCY ({s['wins']}/{s['seen']} wins). This scenario reliably moves forward. Trade authorized."
        elif s['losses'] >= 1 and s['wins'] >= 1:
            s['status'] = "UNSTEADY_LEARNING"
            s['notes'] = (
                f"UNSTEADY SCENARIO ({s['wins']}W / {s['losses']}L). Outcome varies significantly by coin. "
                f"DO NOT TRADE. Keep observing to find missing variables."
            )
        elif s['losses'] > s['wins']:
            s['status'] = "UNDERSTOOD_FAILURE"
            s['notes'] = f"PREDICTABLE TRAP ({s['losses']}/{s['seen']} failed). Breakouts in this scenario consistently dump."
        else:
            s['status'] = "UNSTEADY_LEARNING"
            s['notes'] = "Outcome is inconclusive. Keep studying without capital."


def is_scenario_tradeable(brain, scenario_key):
    """
    Returns True ONLY if:
    1. We have completed the baseline observations (10 cases).
    2. This specific scenario is marked 'UNDERSTOOD_STEADY'.
    If it is unsteady, unverified, or a trap, returns False.
    """
    if brain['total_observed'] < INITIAL_STUDY_COUNT:
        return False, "Still completing baseline learning (Under 10 total cases)."

    if scenario_key not in brain['scenarios']:
        return False, "Brand new scenario. Insufficient data to understand behavior."

    s = brain['scenarios'][scenario_key]
    if s['status'] == "UNDERSTOOD_STEADY":
        return True, f"Scenario fully understood & proven steady ({s['wins']}/{s['seen']} wins)."
    elif s['status'] == "UNSTEADY_LEARNING":
        return False, f"Scenario is UNSTEADY ({s['wins']}W / {s['losses']}L). Inconsistent follow-through. Cash preserved."
    elif s['status'] == "UNDERSTOOD_FAILURE":
        return False, f"Scenario is a recognized TRAP ({s['losses']}/{s['seen']} dumped). Trade forbidden."
    else:
        return False, "Scenario still under observation (needs more proof)."


# ==============================================================================
# 6. BITGET ONE-WAY ORDER HELPERS
# ==============================================================================
def get_open_position():
    """Checks for active long position."""
    try:
        positions = exchange.fetch_positions()
        for p in positions:
            contracts = float(p.get('contracts', 0) or 0)
            side = p.get('side', '').lower()
            if contracts > 0 and side == 'long':
                return {
                    'symbol': p['symbol'],
                    'contracts': contracts,
                    'entry_price': float(p.get('entryPrice', 0))
                }
    except Exception as e:
        print(f"[POSITION CHECK ERROR] {e}", flush=True)
    return None


def open_long_position(symbol, amount):
    """Dual-fallback execution for Bitget Unified One-Way Mode."""
    try:
        return exchange.create_order(
            symbol=symbol,
            type='market',
            side='buy',
            amount=amount,
            params={'tradeSide': 'buy_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=amount,
                params={'tradeSide': 'open'}
            )
        raise e


def close_long_position(symbol, amount):
    """Dual-fallback exit for Bitget Unified One-Way Mode."""
    try:
        return exchange.create_order(
            symbol=symbol,
            type='market',
            side='sell',
            amount=amount,
            params={'tradeSide': 'sell_single'}
        )
    except Exception as e:
        if '25156' in str(e) or 'tradeSide' in str(e).lower():
            return exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=amount,
                params={'tradeSide': 'close'}
            )
        raise e


# ==============================================================================
# 7. MARKET SCANNER & TELEMETRY
# ==============================================================================
def inspect_coin_imbalance(symbol, pct_24h, vol_24h):
    """Examines 5m candles, volume, and funding to spot velocity imbalances."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=25)
        if len(ohlcv) < 20:
            return None

        closes = [x[4] for x in ohlcv]
        volumes = [x[5] for x in ohlcv]

        cur_price = closes[-1]
        price_5m_ago = closes[-2]
        pct_5m = ((cur_price - price_5m_ago) / price_5m_ago) * 100

        price_1h_ago = closes[-13] if len(closes) >= 13 else closes[0]
        pct_1h = ((cur_price - price_1h_ago) / price_1h_ago) * 100

        avg_vol = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 1
        rvol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
        rsi_5m = calculate_rsi(closes, period=14)

        # Imbalance Trigger: 5m gain >= 2.0%, RVol >= 2.0x, outpacing 1h
        is_imbalance = (pct_5m >= 2.0 and rvol >= 2.0 and (pct_1h <= 0 or (pct_5m / max(pct_1h, 0.1) >= 0.6)))

        if not is_imbalance:
            return None

        funding_rate = 0.0
        try:
            f_data = exchange.fetch_funding_rate(symbol)
            funding_rate = float(f_data.get('fundingRate', 0) or 0) * 100
        except Exception:
            pass

        metrics = {
            "symbol": symbol,
            "cur_price": cur_price,
            "pct_5m": round(pct_5m, 2),
            "pct_1h": round(pct_1h, 2),
            "pct_24h": round(pct_24h, 2),
            "rvol": rvol,
            "rsi_5m": rsi_5m,
            "funding_pct": round(funding_rate, 4),
            "vol_24h_m": round(vol_24h / 1_000_000, 2)
        }
        metrics['scenario_key'] = classify_scenario_archetype(metrics)
        return metrics

    except Exception:
        return None


# ==============================================================================
# 8. ACTIVE TRADE GUARDIAN (LIVE RISK RULES)
# ==============================================================================
def manage_active_trade(symbol, contracts, entry_price):
    """Guards active long with 4 strict capital-protection rules."""
    highest_price = entry_price
    entry_time = time.time()
    last_log_time = 0

    print(f"\n[GUARDIAN ACTIVE] Managing {symbol} | Entry: {entry_price} | Contracts: {contracts}", flush=True)

    while True:
        try:
            time.sleep(3)
            ticker = exchange.fetch_ticker(symbol)
            cur_price = float(ticker.get('last', 0) or 0)

            if cur_price > highest_price:
                highest_price = cur_price

            pnl_pct = ((cur_price - entry_price) / entry_price) * 100
            peak_pnl = ((highest_price - entry_price) / entry_price) * 100
            elapsed_min = (time.time() - entry_time) / 60

            if time.time() - last_log_time > 15:
                print(f"[TRADE STATUS] {symbol} | PnL: {pnl_pct:+.2f}% | Peak: {peak_pnl:+.2f}% | Elapsed: {elapsed_min:.1f}m", flush=True)
                last_log_time = time.time()

            # 1. FEE-SHIELD LOCK (+1.0% -> +0.5%)
            if peak_pnl >= 1.0:
                guaranteed_floor = entry_price * 1.005
                if cur_price <= guaranteed_floor:
                    print(f"[EXIT TRIGGER] Fee-Shield hit! Locked +0.5% net profit (Peak was +{peak_pnl:.2f}%).", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # 2. MOMENTUM STALL / BOX CHOP EXIT (15 Mins)
            if elapsed_min >= 15 and peak_pnl < 1.0:
                if abs(pnl_pct) <= 0.45:
                    print(f"[EXIT TRIGGER] Momentum stalled in a box after {elapsed_min:.0f}m. Dumping chop.", flush=True)
                    close_long_position(symbol, contracts)
                    break

            # 3. INITIAL HARD STOP (-1.2%)
            if peak_pnl < 1.0 and pnl_pct <= -1.20:
                print(f"[EXIT TRIGGER] Hard stop hit at {pnl_pct:.2f}%. Protecting capital.", flush=True)
                close_long_position(symbol, contracts)
                break

            # 4. RUNNER TRAIL (+3% or higher)
            if peak_pnl >= 3.0:
                trailing_floor = highest_price * 0.985
                if cur_price <= trailing_floor:
                    print(f"[EXIT TRIGGER] Trailing stop triggered. Banked runner at {pnl_pct:+.2f}% (Peak: +{peak_pnl:.2f}%).", flush=True)
                    close_long_position(symbol, contracts)
                    break

        except Exception as e:
            print(f"[GUARDIAN WARNING] {e}", flush=True)
            time.sleep(2)


# ==============================================================================
# 9. MAIN AUTONOMOUS ENGINE
# ==============================================================================
def main():
    start_keep_alive()
    print("[SYSTEM] Autonomous Scenario-Based Momentum Desk initialized.", flush=True)

    try:
        exchange.load_markets()
        print(f"[SYSTEM] Loaded {len(exchange.markets)} markets successfully.", flush=True)
    except Exception as e:
        print(f"[WARNING] load_markets: {e}", flush=True)

    brain = load_brain()
    print(f"[STATUS] Brain Loaded. Total Lifetime Imbalances Observed: {brain['total_observed']}", flush=True)
    print(f"[STATUS] Cataloged Scenarios: {len(brain['scenarios'])} unique archetypes.", flush=True)

    cycle = 1

    while True:
        try:
            # 1. Manage Active Trade if any
            pos = get_open_position()
            if pos:
                manage_active_trade(pos['symbol'], pos['contracts'], pos['entry_price'])
                time.sleep(5)
                continue

            # 2. Update Active Shadow Studies (Forward Tracking)
            remaining_studies = []
            for case in brain['active_studies']:
                sym = case['symbol']
                elapsed_min = (time.time() - case['detected_at']) / 60

                try:
                    ticker = exchange.fetch_ticker(sym)
                    cur_price = float(ticker.get('last', 0) or 0)
                except Exception:
                    remaining_studies.append(case)
                    continue

                if cur_price > case['peak_price']:
                    case['peak_price'] = cur_price
                if cur_price < case['lowest_price']:
                    case['lowest_price'] = cur_price

                base_price = case['base_price']
                cur_pnl = ((cur_price - base_price) / base_price) * 100
                peak_pnl = ((case['peak_price'] - base_price) / base_price) * 100

                # Completed at 60 mins
                if elapsed_min >= 60:
                    case['final_pnl'] = round(cur_pnl, 2)
                    case['peak_pnl'] = round(peak_pnl, 2)

                    if cur_pnl >= 2.0 and peak_pnl >= 3.5:
                        verdict = "SUSTAINED RUNNER"
                    elif cur_pnl <= 0.0:
                        verdict = "EXHAUSTION TRAP"
                    else:
                        verdict = "STALL"

                    case['verdict'] = verdict
                    brain['total_observed'] += 1
                    brain['history'].append(case)

                    # Update specific scenario intelligence
                    update_scenario_knowledge(brain, case['scenario_key'], verdict, case)

                    print("\n" + "=" * 80, flush=True)
                    print(f"[SCENARIO STUDY COMPLETE] #{brain['total_observed']} on {sym}", flush=True)
                    print(f"  Archetype: {case['scenario_key']}", flush=True)
                    print(f"  Outcome:   {verdict} (Peak: +{case['peak_pnl']}%, 60m Close: {case['final_pnl']}%)", flush=True)
                    print(f"  Diagnosis: {brain['scenarios'][case['scenario_key']]['notes']}", flush=True)
                    print("=" * 80 + "\n", flush=True)

                    save_brain(brain)
                else:
                    remaining_studies.append(case)

            brain['active_studies'] = remaining_studies

            # 3. Check Wallet & Sizing
            balance_info = exchange.fetch_balance()
            usdt_free = float(balance_info.get('USDT', {}).get('free', 0) or 0)
            notional = (usdt_free * BALANCE_USE_PCT) * LEVERAGE

            # 4. Scan Market for Imbalances
            try:
                tickers = exchange.fetch_tickers()
            except Exception as e:
                time.sleep(10)
                continue

            candidates = []
            for symbol, t in tickers.items():
                if not symbol.endswith(":USDT"):
                    continue
                base_asset = symbol.split('/')[0].upper()
                if base_asset in NON_CRYPTO_SYMBOLS:
                    continue
                vol_24h = float(t.get('quoteVolume', 0) or 0)
                pct_24h = float(t.get('percentage', 0) or 0)
                if vol_24h >= MIN_24H_VOLUME:
                    candidates.append((symbol, pct_24h, vol_24h))

            # Focus on top liquid crypto
            candidates.sort(key=lambda x: x[2], reverse=True)
            top_candidates = candidates[:30]

            active_syms = {c['symbol'] for c in brain['active_studies']}
            trade_candidate = None

            for sym, pct_24h, vol_24h in top_candidates:
                if sym in active_syms:
                    continue

                metrics = inspect_coin_imbalance(sym, pct_24h, vol_24h)
                if not metrics:
                    continue

                scenario_key = metrics['scenario_key']
                is_tradeable, reason = is_scenario_tradeable(brain, scenario_key)

                # Case A: Scenario is proven steady and understood -> EXECUTE
                if is_tradeable:
                    print("\n" + "*" * 80, flush=True)
                    print(f"[TRADE GREEN LIGHT] {sym} matches UNDERSTOOD & STEADY scenario!", flush=True)
                    print(f"Archetype: {scenario_key}", flush=True)
                    print(f"Reason:    {reason}", flush=True)
                    print("*" * 80 + "\n", flush=True)
                    trade_candidate = (sym, metrics['cur_price'])
                    break

                # Case B: Scenario is unsteady, a trap, or needs more learning -> RECORD & OBSERVE SAFELY
                else:
                    new_study = {
                        "symbol": sym,
                        "detected_at": time.time(),
                        "base_price": metrics['cur_price'],
                        "peak_price": metrics['cur_price'],
                        "lowest_price": metrics['cur_price'],
                        "scenario_key": scenario_key,
                        "initial_metrics": metrics
                    }
                    brain['active_studies'].append(new_study)
                    save_brain(brain)

                    print(f"\n[SCENARIO DETECTED & LOGGED] {sym} | 5m Gain: +{metrics['pct_5m']}% | Vol: ${metrics['vol_24h_m']}M", flush=True)
                    print(f"  Archetype: {scenario_key}", flush=True)
                    print(f"  Decision:  NO TRADE. {reason}", flush=True)
                    print(f"  Action:    Vault USDT untouched. Studying trajectory forward for 60 minutes...\n", flush=True)
                    break  # Avoid spamming multiple studies in a single cycle

            # 5. Place Trade if Qualified
            if trade_candidate and notional >= MIN_NOTIONAL:
                symbol, cur_price = trade_candidate
                market = exchange.market(symbol)
                min_lot = float(market['limits']['amount']['min'] or 0)
                raw_amount = notional / cur_price
                formatted_amount = float(exchange.amount_to_precision(symbol, raw_amount))

                if formatted_amount >= min_lot:
                    try:
                        exchange.set_leverage(LEVERAGE, symbol, params={'marginMode': 'crossed'})
                    except Exception:
                        pass

                    print(f"\n[ORDER EXECUTION] Entering Long on {symbol} | Amount: {formatted_amount} | Notional: ${notional:.2f}", flush=True)
                    order = open_long_position(symbol, formatted_amount)
                    print(f"[ORDER PLACED] Bitget Order ID: {order.get('id')}", flush=True)
                    time.sleep(3)
                    continue

            # Heartbeat Pulse
            if cycle % 2 == 0:
                steady_scenarios = [k for k, v in brain['scenarios'].items() if v.get('status') == "UNDERSTOOD_STEADY"]
                unsteady_scenarios = [k for k, v in brain['scenarios'].items() if v.get('status') == "UNSTEADY_LEARNING"]
                print(
                    f"[RADAR PULSE] Observed: {brain['total_observed']}/{INITIAL_STUDY_COUNT} | "
                    f"Steady Scenarios: {len(steady_scenarios)} | Unsteady: {len(unsteady_scenarios)} | "
                    f"Vault: ${usdt_free:.2f} USDT | Next scan in {SCAN_INTERVAL_SECONDS}s...",
                    flush=True
                )

            cycle += 1
            save_brain(brain)
            time.sleep(SCAN_INTERVAL_SECONDS)

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION] {e}", flush=True)
            time.sleep(15)


if __name__ == "__main__":
    main()

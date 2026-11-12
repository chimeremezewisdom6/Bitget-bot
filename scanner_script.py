import requests
import json
import urllib.parse
import os
import asyncio
import aiohttp

POLLINATIONS_KEY = os.environ.get("POLLINATIONS_KEY", "")
FEE_ROUND_TRIP = 0.0012

async def fetch_binance_candles(session, sem, sym):
    async with sem:
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1m&limit=60"
            async with session.get(url) as resp:
                if resp.status != 200: return sym, None
                data = await resp.json()
                if len(data) < 60: return sym, None
                parsed = [[int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in data]
                return sym, parsed
        except Exception:
            return sym, None

async def get_global_mover():
    try:
        res = requests.get("https://api.coinpaprika.com/v1/tickers", timeout=10)
        tickers = res.json()
    except Exception as e:
        print(f"CoinPaprika failed: {e}")
        return None

    valid_symbols = []
    for t in tickers:
        vol = t.get('quotes', {}).get('USD', {}).get('volume_24h', 0)
        if vol and vol >= 1_000_000:
            valid_symbols.append(t['symbol'])

    print(f"Found {len(valid_symbols)} coins with >$1M volume.")

    sem = asyncio.Semaphore(10)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_binance_candles(session, sem, sym) for sym in valid_symbols]
        results = await asyncio.gather(*tasks)

    top_movers = []
    for sym, candles in results:
        if not candles: continue
        open_10m = candles[-11][1]
        close_now = candles[-1][4]
        price_change = ((close_now - open_10m) / open_10m) * 100
        vol_10m = sum(k[5] for k in candles[-10:]) / 10
        vol_50m = sum(k[5] for k in candles[:-10]) / 50
        surge = vol_10m / vol_50m if vol_50m > 0 else 1
        score = abs(price_change) * surge
        top_movers.append({"symbol": sym, "price_change": price_change, "candles": candles, "score": score})

    if not top_movers: return None
    top_movers.sort(key=lambda x: x['score'], reverse=True)
    return top_movers[0]

def run_backtest(candles):
    best_seq = None
    best_win_rate = -1
    best_net_pnl = -999
    for ratio_trig in [3, 4, 5, 6, 7]:
        for strength_trig in [0.70, 0.75, 0.80, 0.85, 0.90]:
            for fade_trig in [1.5, 2.0, 2.5, 3.0]:
                trades = []
                for i in range(5, len(candles)-1):
                    c = candles[i]
                    c_next = candles[i+1]
                    rng = c[2] - c[3]
                    clv = (c[4] - c[3]) / rng if rng > 0 else 0.5
                    b = c[5] * clv
                    s = c[5] - b
                    strength = max(b, s) / (b + s) if (b+s) > 0 else 0
                    ratio = max(b, s) / min(b, s) if min(b, s) > 0 else 999
                    if ratio >= ratio_trig and strength >= strength_trig:
                        side = 1 if b >= s else -1
                        entry = c_next[1]
                        exit_px = c_next[4]
                        gross = side * ((exit_px - entry) / entry)
                        trades.append(gross - FEE_ROUND_TRIP)
                if len(trades) >= 3:
                    wins = sum(1 for x in trades if x > 0)
                    win_rate = wins / len(trades)
                    net_pnl = sum(trades)
                    if win_rate > best_win_rate or (win_rate == best_win_rate and net_pnl > best_net_pnl):
                        best_win_rate = win_rate
                        best_net_pnl = net_pnl
                        best_seq = {"ratio": ratio_trig, "strength": strength_trig, "fade": fade_trig}
    return best_seq

def ask_ai_debugger(error_msg):
    if not POLLINATIONS_KEY: return f"Code Error: {error_msg}"
    prompt = f"You are an expert Python developer. My scanner crashed with this exact error: '{error_msg}'. Explain in a short paragraph what mistake was made in the code and how to fix it."
    try:
        url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?model=openai"
        return requests.get(url, timeout=10).text.strip()
    except Exception:
        return f"Code Error: {error_msg}"

if __name__ == "__main__":
    try:
        mover = asyncio.run(get_global_mover())
        if mover:
            best_seq = run_backtest(mover['candles'])
            if best_seq:
                with open("candidate.json", "w") as f:
                    json.dump({
                        "symbol": mover['symbol'],
                        "direction": "LONG" if mover['price_change'] > 0 else "SHORT",
                        "entry_px": mover['candles'][-1][4],
                        "params": best_seq
                    }, f, indent=2)
                print("✅ Candidate saved")
            else:
                with open("candidate.json", "w") as f: json.dump({}, f)
        else:
            with open("candidate.json", "w") as f: json.dump({}, f)
    except Exception as e:
        print(f"❌ CRASHED: {e}")
        print(ask_ai_debugger(str(e)))
        with open("candidate.json", "w") as f: json.dump({}, f)

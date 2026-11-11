import asyncio
import os
import random
import tempfile
import time

from backtester import Params, generate_grid, optimize, simulate
from config import Config
from executor import Gate
from models import CoinImbalance
from ratelimit import ExchangeLimiter, TokenBucket
from scanner import depth_within

def test_depth_within():
    book = {"bids": [[100.0, 1], [99.5, 2], [98.0, 50]], "asks": [[100.2, 3], [100.9, 1], [102.0, 50]]}
    bid, ask = depth_within(book, 0.01, 1.0)
    assert abs(bid - (100 * 1 + 99.5 * 2)) < 1e-9, bid
    assert abs(ask - (100.2 * 3 + 100.9 * 1)) < 1e-9, ask
    assert depth_within({"bids": [], "asks": []}, 0.01) is None
    assert abs(depth_within(book, 0.01, 10.0)[0] - 10 * bid) < 1e-6

def test_imbalance_metrics():
    ci = CoinImbalance("X", 500.0, 100.0, 3)
    assert ci.side == "LONG" and abs(ci.ratio - 5) < 1e-9 and abs(ci.strength - 500 / 600) < 1e-9
    assert ci.side_ratio(1) == 5 and abs(ci.side_ratio(-1) - 0.2) < 1e-9
    assert CoinImbalance("Y", 0.0, 100.0, 1).side == "SHORT"

def test_grid_is_100():
    g = generate_grid()
    assert len(g) == 100 and len(set(g)) == 100

def _candles(n=600, seed=1):
    random.seed(seed)
    px, out = 100.0, []
    for i in range(n):
        drift = 0.002 if (i // 40) % 2 == 0 else -0.002
        o = px
        c = o * (1 + drift + random.gauss(0, 0.001))
        h, l = max(o, c) * 1.0005, min(o, c) * 0.9995
        out.append([i * 60000, o, h, l, c, 1000 + random.random() * 500])
        px = c
    return out

def test_backtester():
    cfg = Config()
    c = _candles()
    trades = simulate(c, Params(3, 0.75, 1.5), cfg)
    assert trades
    for t in trades:
        gross = t.side * (t.exit / t.entry - 1)
        assert abs(t.net - (gross - cfg.fee_round_trip)) < 1e-12
    winner, ranked = optimize(c, cfg)
    assert len(ranked) == 100
    assert all(r.n_trades <= cfg.backtest_trades for r in ranked)
    assert ranked[0].win_rate >= ranked[-1].win_rate
    if winner:
        assert winner.net_pnl > 0 and winner.n_trades >= cfg.min_backtest_trades

def test_stop_loss_in_backtest():
    cfg = Config()
    cs = [[i, 100, 101, 99, 100.9, 1000] for i in range(10)]
    cs += [[10, 100.9, 101, 90, 91, 1000]] + [[11 + i, 91, 91.5, 90.5, 91, 1000] for i in range(10)]
    t = simulate(cs, Params(3, 0.7, 1.5), cfg)
    assert t and t[0].reason == "stop" and t[0].net < -cfg.stop_loss

def test_gate():
    cfg = Config(gate_path=os.path.join(tempfile.mkdtemp(), "g.json"))
    g = Gate(cfg)
    for _ in range(7):
        g.record_paper(0.005)
    assert not g.unlocked and g.streak == 7
    g.record_paper(0.0041)
    assert g.streak == 0
    for _ in range(8):
        g.record_paper(0.0042)
    assert g.unlocked and not g.live_allowed
    assert Gate(cfg).unlocked

def test_ratelimiter():
    async def run():
        b = TokenBucket(rate=20, burst=1)
        t0 = time.monotonic()
        for _ in range(11):
            await b.acquire()
        assert time.monotonic() - t0 >= 0.45
        lim = ExchangeLimiter(10)
        lim.on_rate_limited()
        assert not lim.available and lim.cooldown_left > 4
    asyncio.run(run())

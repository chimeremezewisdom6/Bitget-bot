from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass

from config import Config

log = logging.getLogger("backtest")
CAP = 999.0

@dataclass(frozen=True)
class Params:
    ratio_trigger: float
    strength_trigger: float
    fade_trigger: float

    def __str__(self) -> str:
        return (f"ratio>={self.ratio_trigger:g}x strength>={self.strength_trigger:.0%} fade<{self.fade_trigger:g}x")

@dataclass
class Trade:
    entry_idx: int
    side: int
    entry: float
    exit: float
    net: float
    reason: str

@dataclass
class SequenceResult:
    params: Params
    n_trades: int
    wins: int
    win_rate: float
    net_pnl: float

    def __str__(self) -> str:
        return (f"[{self.params}] trades={self.n_trades} win_rate={self.win_rate:.0%} net={self.net_pnl * 100:+.2f}%")

def generate_grid() -> list[Params]:
    return [Params(r, s, f) for r, s, f in itertools.product((3, 4, 5, 6, 7), (0.70, 0.75, 0.80, 0.85, 0.90), (1.5, 2.0, 2.5, 3.0))]

def _safe(a: float, b: float) -> float:
    return min(CAP, a / b) if b > 1e-12 else CAP

def simulate(candles: list, p: Params, cfg: Config) -> list[Trade]:
    w = cfg.proxy_window
    n = len(candles)
    if n < w + 3:
        return []
    pb = [0.0] * (n + 1)
    ps = [0.0] * (n + 1)
    for i, (_, o, h, l, c, v) in enumerate(candles):
        rng = h - l
        clv = (c - l) / rng if rng > 0 else 0.5
        b = (v or 0.0) * clv
        pb[i + 1] = pb[i] + b
        ps[i + 1] = ps[i] + ((v or 0.0) - b)

    def flow(j: int):
        return pb[j + 1] - pb[j + 1 - w], ps[j + 1] - ps[j + 1 - w]

    max_hold = max(1, cfg.max_trade_seconds // 60)
    trades: list[Trade] = []
    i = w - 1
    while i < n - 1:
        B, S = flow(i)
        tot = B + S
        if tot <= 0:
            i += 1
            continue
        strength = max(B, S) / tot
        if _safe(max(B, S), min(B, S)) >= p.ratio_trigger and strength >= p.strength_trigger:
            side = 1 if B >= S else -1
            e_idx = i + 1
            entry = candles[e_idx][1]
            stop = entry * (1 - side * cfg.stop_loss)
            last = min(n - 1, e_idx + max_hold - 1)
            exit_px, reason, j = None, "time", e_idx
            for j in range(e_idx, last + 1):
                _, o, h, l, c, v = candles[j]
                if (side == 1 and l <= stop) or (side == -1 and h >= stop):
                    exit_px, reason = stop, "stop"
                    break
                b2, s2 = flow(j)
                sr = _safe(b2, s2) if side == 1 else _safe(s2, b2)
                if sr < p.fade_trigger:
                    exit_px, reason = c, "fade"
                    break
                if j == last:
                    exit_px, reason = c, "time"
            truncated = reason == "time" and (e_idx + max_hold - 1) > (n - 1)
            if exit_px is not None and not truncated:
                net = side * (exit_px / entry - 1) - cfg.fee_round_trip
                trades.append(Trade(e_idx, side, entry, exit_px, net, reason))
            i = j + 1
        else:
            i += 1
    return trades

def evaluate(candles: list, p: Params, cfg: Config) -> SequenceResult:
    t = simulate(candles, p, cfg)[-cfg.backtest_trades:]
    wins = sum(1 for x in t if x.net > 0)
    return SequenceResult(p, len(t), wins, wins / len(t) if t else 0.0, sum(x.net for x in t))

def optimize(candles: list, cfg: Config):
    results = [evaluate(candles, p, cfg) for p in generate_grid()]
    ranked = sorted(results, key=lambda r: (r.win_rate, r.net_pnl), reverse=True)
    eligible = [r for r in ranked if r.n_trades >= cfg.min_backtest_trades and (r.net_pnl > 0 or not cfg.require_positive_backtest)]
    return (eligible[0] if eligible else None), ranked

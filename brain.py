# brain.py
# Pure computation. No I/O. Called by Body and Learner.

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

Side = Literal["buy", "sell"]

@dataclass
class EntrySignal:
    symbol: str
    side: Side
    score: int
    reason: str
    ofi_1m_orders: float
    ofi_1m_volume: float
    ofi_3m_orders: float
    ofi_3m_volume: float
    ofi_10m_volume: float
    exit_mode: Literal["time_stop", "trailing"] = "time_stop"

class OfiWindow:
    def __init__(self, horizon_s: float):
        self.horizon_s = horizon_s
        self.trades: deque = deque()

    def add(self, ts: float, side: str, price: float, qty: float):
        self.trades.append((ts, side, price, qty))
        cutoff = ts - self.horizon_s
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()

    def stats(self, now: float | None = None) -> dict:
        now = now or time.time()
        cutoff = now - self.horizon_s
        while self.trades and self.trades[0][0] < cutoff:
            self.trades.popleft()
        bo = bv = so = sv = 0.0
        for _, side, price, qty in self.trades:
            if side == "buy":
                bo += 1
                bv += price * qty
            else:
                so += 1
                sv += price * qty
        return {"buy_orders": bo, "sell_orders": so, "buy_volume": bv, "sell_volume": sv}

def _ratio(a: float, b: float) -> float:
    if b <= 0:
        return float("inf") if a > 0 else 0.0
    return a / b

def _dominant(stats: dict) -> tuple[str, str]:
    side = "buy" if stats["buy_volume"] >= stats["sell_volume"] else "sell"
    opp = "sell" if side == "buy" else "buy"
    return side, opp

def _window_ratios(stats: dict, side: str, opp: str) -> tuple[float, float]:
    return (
        _ratio(stats[f"{side}_orders"], stats[f"{opp}_orders"]),
        _ratio(stats[f"{side}_volume"], stats[f"{opp}_volume"]),
    )

def continuation_score(win_1m: OfiWindow, win_3m: OfiWindow, win_10m: OfiWindow,
                      minute_volumes: list[float] | None = None,
                      price_series: list[float] | None = None) -> tuple[int, str]:
    score = 0
    reasons = []
    now = time.time()

    if minute_volumes and len(minute_volumes) >= 3:
        m1, m2, m3 = minute_volumes[-3:]
        if m2 >= 0.8 * m1 and m3 >= 0.8 * m2 and max(m1, m2, m3) > 0:
            score += 1
            reasons.append("vol_accel")

    s1 = win_1m.stats(now)
    s3 = win_3m.stats(now)
    s10 = win_10m.stats(now)
    d1, _ = _dominant(s1)
    d3, _ = _dominant(s3)
    d10, _ = _dominant(s10)

    if d1 == d3 == d10:
        side, opp = d1, ("sell" if d1 == "buy" else "buy")
        r1o, r1v = _window_ratios(s1, side, opp)
        r3o, r3v = _window_ratios(s3, side, opp)
        r10v = _ratio(s10[f"{side}_volume"], s10[f"{opp}_volume"])
        if r1o >= 1.5 and r1v >= 2.0 and r3o >= 2.0 and r3v >= 3.0 and r10v >= 1.5:
            score += 1
            reasons.append("ofi_persist")

    if price_series and len(price_series) >= 20:
        recent = list(price_series)[-30:]
        peak = max(recent)
        trough = min(recent)
        span = (peak - trough) / trough if trough > 0 else 0
        if span >= 0.003:
            cur = recent[-1]
            if cur > trough * 1.003 and cur < peak:
                score += 1
                reasons.append("absorption")

    if s10["buy_volume"] + s10["sell_volume"] > 0:
        side10, opp10 = _dominant(s10)
        r10v = _ratio(s10[f"{side10}_volume"], s10[f"{opp10}_volume"])
        if r10v >= 1.5:
            score += 1
            reasons.append("10m_skew")

    return score, ",".join(reasons) if reasons else "none"

def decide_entry(symbol: str, share_result: dict,
                 win_1m: OfiWindow, win_3m: OfiWindow, win_10m: OfiWindow,
                 minute_volumes: list[float] | None = None,
                 price_series: list[float] | None = None,
                 required_score: int = 4,
                 params: dict | None = None) -> EntrySignal | None:
    params = params or {}
    r1o_min = params.get("ofi_1m_orders_min", 1.5)
    r1v_min = params.get("ofi_1m_volume_min", 2.0)
    r3o_min = params.get("ofi_3m_orders_min", 2.0)
    r3v_min = params.get("ofi_3m_volume_min", 3.0)
    r10v_min = params.get("ofi_10m_volume_min", 1.5)

    if not share_result.get("passed", share_result.get("passed_share_filter", False)):
        return None

    now = time.time()
    s1, s3, s10 = win_1m.stats(now), win_3m.stats(now), win_10m.stats(now)
    d1, o1 = _dominant(s1)
    d3, _ = _dominant(s3)
    d10, _ = _dominant(s10)
    if not (d1 == d3 == d10):
        return None

    side, opp = d1, o1
    r1o, r1v = _window_ratios(s1, side, opp)
    r3o, r3v = _window_ratios(s3, side, opp)
    r10v = _ratio(s10[f"{side}_volume"], s10[f"{opp}_volume"])

    if not (r1o >= r1o_min and r1v >= r1v_min
            and r3o >= r3o_min and r3v >= r3v_min
            and r10v >= r10v_min):
        return None

    score, _ = continuation_score(win_1m, win_3m, win_10m, minute_volumes, price_series)
    if score < required_score:
        return None

    return EntrySignal(
        symbol=symbol, side="buy" if side == "buy" else "sell",
        score=score,
        reason=f"{side} 1m {r1o:.2f}x/{r1v:.2f}x, 3m {r3o:.2f}x/{r3v:.2f}x, 10m {r10v:.2f}x",
        ofi_1m_orders=r1o, ofi_1m_volume=r1v,
        ofi_3m_orders=r3o, ofi_3m_volume=r3v,
        ofi_10m_volume=r10v,
    )

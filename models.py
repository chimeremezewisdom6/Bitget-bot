from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

CAP = 999.0

def _div(a: float, b: float) -> float:
    return min(CAP, a / b) if b > 0 else CAP

@dataclass(frozen=True)
class Venue:
    symbol: str
    contract_size: float = 1.0

@dataclass
class Coin:
    base: str
    volume_usd: float
    venues: dict

@dataclass
class CoinImbalance:
    base: str
    bid_usd: float
    ask_usd: float
    n_venues: int

    @property
    def total(self) -> float:
        return self.bid_usd + self.ask_usd

    @property
    def ratio(self) -> float:
        return _div(self.bid_usd, self.ask_usd)

    @property
    def side(self) -> str:
        return "LONG" if self.bid_usd >= self.ask_usd else "SHORT"

    @property
    def strength(self) -> float:
        return max(self.bid_usd, self.ask_usd) / self.total if self.total > 0 else 0.0

    @property
    def dominance(self) -> float:
        return _div(max(self.bid_usd, self.ask_usd), min(self.bid_usd, self.ask_usd))

    def side_ratio(self, side: int) -> float:
        return _div(self.bid_usd, self.ask_usd) if side == 1 else _div(self.ask_usd, self.bid_usd)

@dataclass
class ScanResult:
    seq: int
    ts: float
    universe_size: int
    measured: int
    top: list
    fluct: dict
    selected: CoinImbalance
    coin: Coin

@dataclass
class ActiveTrade:
    base: str
    side: int
    mode: str
    entry: float
    opened: float
    last_px: float
    gross: float = 0.0
    side_ratio: float = 0.0
    fade_trigger: float = 0.0

class SharedState:
    def __init__(self) -> None:
        self.latest: Optional[ScanResult] = None
        self.active: Optional[ActiveTrade] = None
        self.winning = None
        self.halted = False
        self.trades = 0
        self.wins = 0
        self.session_net = 0.0

    def publish(self, scan: ScanResult) -> None:
        self.latest = scan

    async def next_scan(self, after_seq: int, max_age: float) -> Optional[ScanResult]:
        while not self.halted:
            s = self.latest
            if s and s.seq > after_seq and time.time() - s.ts <= max_age:
                return s
            await asyncio.sleep(0.5)
        return None

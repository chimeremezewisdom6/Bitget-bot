"""Perpetual universe selection with explicit exclusions and sample sizes."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from research.features import depth_within_pct, spread_bps

TOP_N = 200
MIN_TURNOVER_USDT = 50_000.0
MAX_SPREAD_BPS = 10.0
MIN_DEPTH_USDT = 20_000.0

TURNOVER_BANDS = [
    {"name": "under_1m_turnover", "min_usd": 0.0, "max_usd": 1_000_000.0},
    {"name": "1m_10m_turnover", "min_usd": 1_000_000.0, "max_usd": 10_000_000.0},
    {"name": "10m_100m_turnover", "min_usd": 10_000_000.0, "max_usd": 100_000_000.0},
    {"name": "over_100m_turnover", "min_usd": 100_000_000.0, "max_usd": None},
]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def classify_turnover(turnover: Any) -> str:
    value = _num(turnover, -1.0)
    if value < 0:
        return "UNVERIFIED"
    for band in TURNOVER_BANDS:
        if value >= band["min_usd"] and (band["max_usd"] is None or value < band["max_usd"]):
            return band["name"]
    return "UNVERIFIED"


@dataclass(frozen=True)
class Perp:
    symbol: str
    base: str
    quote: str
    turnover24h: float
    last: float
    bid: float
    ask: float
    spread_bps: float | None
    bid_depth_usdt: float
    ask_depth_usdt: float
    taker_fee: float | None = None
    launch_ms: int | None = None

    @property
    def mid(self) -> float | None:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base": self.base,
            "quote": self.quote,
            "turnover24h": self.turnover24h,
            "last": self.last,
            "bid": self.bid,
            "ask": self.ask,
            "spread_bps": self.spread_bps,
            "bid_depth_usdt": self.bid_depth_usdt,
            "ask_depth_usdt": self.ask_depth_usdt,
            "taker_fee": self.taker_fee,
            "launch_ms": self.launch_ms,
        }


@dataclass
class Selection:
    selected: list[Perp]
    excluded: list[dict[str, Any]]
    sample_sizes: dict[str, Any]
    band_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.as_dict() for item in self.selected],
            "excluded": self.excluded,
            "sample_sizes": self.sample_sizes,
            "band_counts": self.band_counts,
        }


@dataclass
class Candidates:
    rows: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    sample_sizes: dict[str, Any]


def is_crypto_perp(instrument: dict[str, Any]) -> bool:
    status = str(instrument.get("status", "")).lower()
    is_perpetual = (
        str(instrument.get("type", "")).lower() == "perpetual"
        or str(instrument.get("instrumentType", "")).lower() == "perpetual"
    )
    symbol_type = str(instrument.get("symbolType", "crypto")).lower()
    quote = str(instrument.get("quoteCoin", "")).upper()
    return status == "online" and is_perpetual and symbol_type == "crypto" and quote == "USDT"


def rank_candidates(
    tickers: Iterable[dict[str, Any]],
    instruments: Iterable[dict[str, Any]],
    *,
    top_n: int = TOP_N,
    min_turnover: float = MIN_TURNOVER_USDT,
) -> Candidates:
    instrument_map = {
        row.get("symbol"): row
        for row in instruments or []
        if isinstance(row, dict) and row.get("symbol")
    }
    excluded: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for ticker in tickers or []:
        symbol = ticker.get("symbol")
        if not symbol:
            continue
        instrument = instrument_map.get(symbol)
        if instrument is None:
            excluded.append({"symbol": symbol, "stage": "instrument", "reason": "not_listed"})
            continue
        if not is_crypto_perp(instrument):
            excluded.append({"symbol": symbol, "stage": "instrument", "reason": "not_crypto_perpetual_usdt"})
            continue
        turnover = _num(ticker.get("turnover24h"))
        if turnover < min_turnover:
            excluded.append({
                "symbol": symbol, "stage": "turnover", "reason": "below_min_turnover",
                "turnover24h": turnover,
            })
            continue
        bid = _num(ticker.get("bid1Price"))
        ask = _num(ticker.get("ask1Price"))
        candidates.append({
            "symbol": symbol,
            "base": instrument.get("baseCoin"),
            "quote": instrument.get("quoteCoin"),
            "turnover24h": turnover,
            "last": _num(ticker.get("lastPrice")),
            "bid": bid,
            "ask": ask,
            "spread_bps": spread_bps(bid, ask),
            "taker_fee": _num(instrument.get("takerFeeRate"), 0.0) or None,
            "launch_ms": int(_num(instrument.get("launchTime"), 0.0)) or None,
        })
    candidates.sort(key=lambda row: row["turnover24h"], reverse=True)
    top = candidates[:top_n]
    for row in candidates[top_n:]:
        excluded.append({
            "symbol": row["symbol"], "stage": "top_n",
            "reason": f"rank_beyond_{top_n}", "turnover24h": row["turnover24h"],
        })
    return Candidates(
        rows=top,
        excluded=excluded,
        sample_sizes={
            "candidates": len(candidates),
            "top_n": len(top),
            "top_n_limit": top_n,
        },
    )


def select(
    candidates: Candidates,
    books: dict[str, dict[str, Any]],
    *,
    max_spread_bps: float = MAX_SPREAD_BPS,
    min_depth_usdt: float = MIN_DEPTH_USDT,
) -> Selection:
    selected: list[Perp] = []
    excluded = list(candidates.excluded)
    after_spread = 0
    after_depth = 0
    for row in candidates.rows:
        symbol = row["symbol"]
        spread = row.get("spread_bps")
        if spread is None or spread >= max_spread_bps:
            excluded.append({
                "symbol": symbol, "stage": "spread",
                "reason": f"spread_bps={spread} >= {max_spread_bps}",
                "spread_bps": spread,
            })
            continue
        after_spread += 1
        book = books.get(symbol) or {}
        mid = (row["bid"] + row["ask"]) / 2.0 if row["bid"] > 0 and row["ask"] > 0 else None
        bid_depth = depth_within_pct(book.get("b", []), mid)
        ask_depth = depth_within_pct(book.get("a", []), mid)
        if min(bid_depth, ask_depth) <= min_depth_usdt:
            excluded.append({
                "symbol": symbol, "stage": "depth",
                "reason": f"min_depth_usdt={min(bid_depth, ask_depth)} <= {min_depth_usdt}",
                "bid_depth_usdt": bid_depth, "ask_depth_usdt": ask_depth,
            })
            continue
        after_depth += 1
        selected.append(Perp(
            symbol=symbol,
            base=row.get("base") or "",
            quote=row.get("quote") or "USDT",
            turnover24h=row["turnover24h"],
            last=row["last"],
            bid=row["bid"],
            ask=row["ask"],
            spread_bps=spread,
            bid_depth_usdt=bid_depth,
            ask_depth_usdt=ask_depth,
            taker_fee=row.get("taker_fee"),
            launch_ms=row.get("launch_ms"),
        ))
    band_counts = {band["name"]: 0 for band in TURNOVER_BANDS}
    for item in selected:
        band = classify_turnover(item.turnover24h)
        band_counts[band] = band_counts.get(band, 0) + 1
    return Selection(
        selected=selected,
        excluded=excluded,
        sample_sizes={
            **candidates.sample_sizes,
            "after_spread": after_spread,
            "after_depth": after_depth,
            "final": len(selected),
            "low_sample": len(selected) < 50,
        },
        band_counts=band_counts,
    )

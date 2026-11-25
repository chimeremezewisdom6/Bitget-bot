"""Spot market snapshots and spot-perp basis for the spot-demand hypothesis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from research.features import (
    basis_bps,
    closed_candles,
    return_pct,
    spread_bps,
    turnover_z,
)

SPOT_CATEGORY = "SPOT"
SPOT_MAX_SYMBOLS = 50


@dataclass
class SpotSnapshot:
    symbol: str
    base: str
    turnover24h: float
    last: float
    bid: float
    ask: float
    spread_bps: float | None
    ret_5m_pct: float | None
    ret_15m_pct: float | None
    ret_60m_pct: float | None
    turnover_z: float | None
    basis_bps: float | None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base": self.base,
            "turnover24h": self.turnover24h,
            "last": self.last,
            "bid": self.bid,
            "ask": self.ask,
            "spread_bps": self.spread_bps,
            "ret_5m_pct": self.ret_5m_pct,
            "ret_15m_pct": self.ret_15m_pct,
            "ret_60m_pct": self.ret_60m_pct,
            "turnover_z": self.turnover_z,
            "basis_bps": self.basis_bps,
            "error": self.error,
        }


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def spot_instruments_map(instruments: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row.get("symbol"): row
        for row in instruments or []
        if isinstance(row, dict)
        and row.get("symbol")
        and str(row.get("status", "")).lower() == "online"
        and str(row.get("symbolType", "crypto")).lower() == "crypto"
        and str(row.get("quoteCoin", "")).upper() == "USDT"
    }


def map_spot(base: str, instruments: dict[str, dict[str, Any]]) -> str | None:
    if not base:
        return None
    symbol = f"{base.upper()}USDT"
    return symbol if symbol in instruments else None


async def spot_snapshot(
    client: Any,
    perps: Iterable[Any],
    *,
    max_symbols: int = SPOT_MAX_SYMBOLS,
    now_ms: int | None = None,
) -> list[SpotSnapshot]:
    instruments_payload = await client.get("/api/v3/market/instruments", {"category": SPOT_CATEGORY})
    tickers_payload = await client.get("/api/v3/market/tickers", {"category": SPOT_CATEGORY})
    instruments = spot_instruments_map(instruments_payload.get("data", []))
    tickers = {
        row.get("symbol"): row
        for row in tickers_payload.get("data", [])
        if isinstance(row, dict) and row.get("symbol")
    }
    perp_list = list(perps)[:max_symbols]
    results: list[SpotSnapshot] = []
    calls = []
    mapped = []
    for perp in perp_list:
        symbol = map_spot(perp.base, instruments)
        if symbol is None:
            results.append(SpotSnapshot(
                symbol=perp.symbol, base=perp.base, turnover24h=0.0, last=0.0,
                bid=0.0, ask=0.0, spread_bps=None, ret_5m_pct=None,
                ret_15m_pct=None, ret_60m_pct=None, turnover_z=None,
                basis_bps=None, error="SPOT_UNMAPPED",
            ))
            continue
        mapped.append((perp, symbol))
        calls.append(("/api/v3/market/candles", {
            "category": SPOT_CATEGORY, "symbol": symbol, "interval": "1m", "limit": "100",
        }))
    responses = await client.gather(calls, concurrency=6) if calls else []
    for (perp, symbol), response in zip(mapped, responses):
        ticker = tickers.get(symbol) or {}
        bid = _num(ticker.get("bid1Price"))
        ask = _num(ticker.get("ask1Price"))
        spot_mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else None
        if isinstance(response, Exception):
            results.append(SpotSnapshot(
                symbol=perp.symbol, base=perp.base, turnover24h=_num(ticker.get("turnover24h")),
                last=_num(ticker.get("lastPrice")), bid=bid, ask=ask,
                spread_bps=spread_bps(bid, ask), ret_5m_pct=None, ret_15m_pct=None,
                ret_60m_pct=None, turnover_z=None,
                basis_bps=basis_bps(perp.mid, spot_mid), error="SPOT_CANDLES_FAILED",
            ))
            continue
        candles = closed_candles(response.get("data", []), now_ms)
        z = turnover_z(response.get("data", []), now_ms)
        results.append(SpotSnapshot(
            symbol=perp.symbol,
            base=perp.base,
            turnover24h=_num(ticker.get("turnover24h")),
            last=_num(ticker.get("lastPrice")),
            bid=bid,
            ask=ask,
            spread_bps=spread_bps(bid, ask),
            ret_5m_pct=return_pct(candles, 5),
            ret_15m_pct=return_pct(candles, 15),
            ret_60m_pct=return_pct(candles, 60),
            turnover_z=z.get("turnover_z"),
            basis_bps=basis_bps(perp.mid, spot_mid),
        ))
    return results

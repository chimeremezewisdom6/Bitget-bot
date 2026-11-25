"""Versioned event definitions for market-behaviour experiments.

Events are deterministic functions of a feature record. They never fetch data,
never read credentials and never execute trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

DEFINITION_VERSION = "1.0.0"


@dataclass(frozen=True)
class Event:
    event_id: str
    type: str
    version: str
    symbol: str
    ts_ms: int
    direction: str
    features: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "definition_version": self.version,
            "symbol": self.symbol,
            "ts_ms": self.ts_ms,
            "direction": self.direction,
            "features": self.features,
            "quality": self.quality,
        }

    def compact(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "definition_version": self.version,
            "symbol": self.symbol,
            "ts_ms": self.ts_ms,
            "direction": self.direction,
        }


def _value(feature: dict[str, Any], key: str) -> float | None:
    value = feature.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _make(feature: dict[str, Any], event_type: str, direction: str, extra: dict[str, Any] | None = None) -> Event:
    symbol = str(feature.get("symbol", "UNKNOWN"))
    ts_ms = int(feature.get("ts_ms", 0))
    payload = {key: feature.get(key) for key in (
        "turnover_z_60m", "return_1m_pct", "return_5m_pct", "return_15m_pct",
        "oi_delta_15m_pct", "taker_imbalance", "taker_coverage_pct",
        "taker_quality", "spread_bps", "vol60_bps", "flag_0_7",
        "spot_basis_bps", "spot_return_5m_pct", "spot_turnover_z", "spot_status",
        "spot_move_5m_ts_ms", "perp_move_5m_ts_ms", "spot_lead_ms",
        "book_imbalance_0p5", "funding_rate", "taker_fee_bps", "fee_status",
        "turnover24h_usdt", "turnover_band",
        "liquidation_long_usdt", "liquidation_short_usdt",
        "liquidation_total_usdt", "liquidation_records",
        "liquidation_side", "liquidation_status",
    )}
    if extra:
        payload.update(extra)
    return Event(
        event_id=f"{event_type}:{symbol}:{ts_ms}:{direction}",
        type=event_type,
        version=DEFINITION_VERSION,
        symbol=symbol,
        ts_ms=ts_ms,
        direction=direction,
        features=payload,
        quality={
            "taker_quality": feature.get("taker_quality"),
            "volatility_status": feature.get("volatility_status"),
            "flag_0_7": feature.get("flag_0_7"),
        },
    )


def detect_turnover_expansion(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    z = _value(feature, "turnover_z_60m")
    ret = _value(feature, "return_1m_pct")
    if z is None or ret is None:
        return None
    if z < float(params.get("turnover_z", 2.0)):
        return None
    if abs(ret) < float(params.get("min_abs_return_pct", 0.2)):
        return None
    return _make(feature, "turnover_expansion", "LONG" if ret > 0 else "SHORT")


def detect_oi_build(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    delta = _value(feature, "oi_delta_15m_pct")
    ret = _value(feature, "return_15m_pct")
    if delta is None or ret is None:
        return None
    if abs(delta) < float(params.get("oi_delta_pct", 0.5)):
        return None
    if delta * ret <= 0:
        return None
    return _make(feature, "oi_build", "LONG" if ret > 0 else "SHORT")


def detect_oi_change(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    """OI change with a price move; OI and price directions are recorded separately.

    When ``require_positive_oi`` is set, only positive OI growth qualifies. Negative
    OI changes are left for descriptive diagnostics, not an event.
    """
    params = params or {}
    delta = _value(feature, "oi_delta_15m_pct")
    ret = _value(feature, "return_15m_pct")
    if delta is None or ret is None:
        return None
    min_delta = float(params.get("min_abs_oi_delta_pct", 2.0))
    if params.get("require_positive_oi"):
        if delta < min_delta:
            return None
    elif abs(delta) < min_delta:
        return None
    if abs(ret) < float(params.get("min_abs_return_pct", 0.2)):
        return None
    direction = "LONG" if ret > 0 else "SHORT"
    oi_direction = "UP" if delta > 0 else "DOWN"
    alignment = "ALIGNED" if delta * ret > 0 else "OPPOSED"
    return _make(feature, "oi_change", direction, {
        "oi_direction": oi_direction,
        "price_direction": direction,
        "oi_price_alignment": alignment,
    })


def detect_liquidation_spike(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    """Directional liquidation spike; the mode chooses fade or follow."""
    params = params or {}
    total = _value(feature, "liquidation_total_usdt")
    records = _value(feature, "liquidation_records")
    long_usdt = _value(feature, "liquidation_long_usdt") or 0.0
    short_usdt = _value(feature, "liquidation_short_usdt") or 0.0
    if total is None or total < float(params.get("min_notional_usdt", 5_000.0)):
        return None
    if records is None or records < float(params.get("min_records", 1)):
        return None
    if long_usdt > short_usdt:
        side = "LONG"
    elif short_usdt > long_usdt:
        side = "SHORT"
    else:
        return None
    mode = str(params.get("mode", "fade")).lower()
    if mode == "fade":
        direction = "LONG" if side == "LONG" else "SHORT"
    elif mode == "follow":
        direction = "SHORT" if side == "LONG" else "LONG"
    else:
        return None
    return _make(feature, "liquidation_spike", direction, {
        "liquidation_side": side,
        "liquidation_mode": mode,
    })


def detect_taker_aggression(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    imbalance = _value(feature, "taker_imbalance")
    if imbalance is None:
        return None
    min_quality = params.get("min_quality")
    if min_quality and feature.get("taker_quality") != min_quality:
        return None
    if abs(imbalance) < float(params.get("min_imbalance", 0.5)):
        return None
    return _make(feature, "taker_aggression", "LONG" if imbalance > 0 else "SHORT")


def detect_absorption(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    proxy = feature.get("absorption") or {}
    if not proxy.get("absorbed"):
        return None
    if params.get("require_depth_known") and not proxy.get("depth_known"):
        return None
    direction = proxy.get("direction")
    if direction not in ("LONG", "SHORT"):
        return None
    if params.get("require_book_imbalance"):
        book_imbalance = proxy.get("book_imbalance")
        min_abs = float(params.get("min_abs_book_imbalance", 0.2))
        if book_imbalance is None:
            return None
        if direction == "SHORT" and book_imbalance > -min_abs:
            return None
        if direction == "LONG" and book_imbalance < min_abs:
            return None
    return _make(feature, "absorption", direction, {"absorption": proxy})


def detect_breakout(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    if not feature.get("breakout_60m"):
        return None
    direction = feature.get("breakout_direction")
    if direction not in ("LONG", "SHORT"):
        return None
    z = _value(feature, "turnover_z_60m")
    if z is None or z < float(params.get("turnover_z", 2.0)):
        return None
    if feature.get("failed_breakout"):
        return None
    return _make(feature, "breakout", direction)


def detect_failed_breakout(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    if not feature.get("failed_breakout"):
        return None
    direction = feature.get("breakout_direction")
    if direction not in ("LONG", "SHORT"):
        return None
    z = _value(feature, "turnover_z_60m")
    if z is None or z < float(params.get("turnover_z", 2.0)):
        return None
    fade = "SHORT" if direction == "LONG" else "LONG"
    return _make(feature, "failed_breakout", fade, {"breakout_direction": direction})


def detect_spot_lead(feature: dict[str, Any], params: dict[str, Any] | None = None) -> Event | None:
    params = params or {}
    spot_z = _value(feature, "spot_turnover_z")
    spot_return = _value(feature, "spot_return_5m_pct")
    if spot_z is None or spot_return is None:
        return None
    if spot_z < float(params.get("spot_turnover_z", 2.0)):
        return None
    if params.get("require_timestamp_lead"):
        spot_move_ts = _value(feature, "spot_move_5m_ts_ms")
        perp_move_ts = _value(feature, "perp_move_5m_ts_ms")
        if spot_move_ts is None:
            return None
        if perp_move_ts is not None and spot_move_ts >= perp_move_ts:
            return None
    elif abs(spot_return) < float(params.get("min_abs_spot_return_pct", 0.2)):
        return None
    return _make(feature, "spot_lead", "LONG" if spot_return > 0 else "SHORT")


DETECTORS: dict[str, Callable[[dict[str, Any], dict[str, Any] | None], Event | None]] = {
    "turnover_expansion": detect_turnover_expansion,
    "oi_build": detect_oi_build,
    "oi_change": detect_oi_change,
    "liquidation_spike": detect_liquidation_spike,
    "taker_aggression": detect_taker_aggression,
    "absorption": detect_absorption,
    "breakout": detect_breakout,
    "failed_breakout": detect_failed_breakout,
    "spot_lead": detect_spot_lead,
}


def detect(feature: dict[str, Any], event_type: str, params: dict[str, Any] | None = None) -> Event | None:
    detector = DETECTORS.get(event_type)
    if detector is None:
        raise ValueError(f"Unknown event type: {event_type}")
    return detector(feature, params)


def detect_all(features: Iterable[dict[str, Any]], event_type: str, params: dict[str, Any] | None = None) -> list[Event]:
    events = []
    for feature in features:
        event = detect(feature, event_type, params)
        if event is not None:
            events.append(event)
    return events


def dedupe(events: Iterable[Event], min_gap_ms: int = 3_600_000) -> list[Event]:
    """Keep the earliest event per symbol/type/direction within ``min_gap_ms``."""
    kept: list[Event] = []
    last_seen: dict[tuple[str, str, str], int] = {}
    for event in sorted(events, key=lambda item: (item.symbol, item.ts_ms)):
        key = (event.symbol, event.type, event.direction)
        previous = last_seen.get(key)
        if previous is not None and event.ts_ms - previous < min_gap_ms:
            continue
        kept.append(event)
        last_seen[key] = event.ts_ms
    return kept

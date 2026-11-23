"""Pure shadow execution math; this module never connects to an exchange."""
from __future__ import annotations
from typing import Any

def _number(value: Any) -> float:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else 0.0
    except (TypeError, ValueError):
        return 0.0

def walk_book(levels: list, side: str, *, quote_target: float | None = None, base_target: float | None = None) -> dict:
    """Walk asks for buy or bids for sell; target exactly one of quote or base."""
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError("side must be buy or sell")
    if (quote_target is None) == (base_target is None):
        raise ValueError("provide exactly one target")
    target = _number(quote_target if quote_target is not None else base_target)
    if target <= 0:
        raise ValueError("fill target must be positive")
    remaining = target
    base_filled = quote_filled = 0.0
    for level in levels or []:
        if len(level) < 2:
            continue
        price, available = _number(level[0]), _number(level[1])
        if price <= 0 or available <= 0:
            continue
        take_base = min(available, remaining / price) if quote_target is not None else min(available, remaining)
        take_quote = take_base * price
        base_filled += take_base
        quote_filled += take_quote
        remaining -= take_quote if quote_target is not None else take_base
        if remaining <= 1e-10:
            break
    complete = remaining <= max(1e-8, target * 1e-9)
    return {
        "side": side,
        "requested_quote_usdt": target if quote_target is not None else None,
        "requested_base": target if base_target is not None else None,
        "filled_quote_usdt": quote_filled,
        "filled_base": base_filled,
        "remaining_target": max(remaining, 0.0),
        "vwap": quote_filled / base_filled if base_filled else None,
        "complete": complete,
        "filled_target": target - max(remaining, 0.0),
    }

def simulate_round_trip(*, entry_levels: list, exit_levels: list, direction: str, notional_usdt: float, taker_fee_bps: float, funding_bps: float = 0.0) -> dict:
    """Estimate market entry/exit from two archived books; never submits an order.

    funding_bps is the signed rate paid by a LONG; SHORT pays the opposite.
    Supply zero if no funding event applies to the hypothetical holding period.
    """
    direction = direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise ValueError("direction must be LONG or SHORT")
    if notional_usdt <= 0 or taker_fee_bps < 0:
        raise ValueError("notional must be positive and fee bps non-negative")
    entry_side, exit_side = ("buy", "sell") if direction == "LONG" else ("sell", "buy")
    entry = walk_book(entry_levels, entry_side, quote_target=notional_usdt)
    if not entry["complete"]:
        return {"status": "PARTIAL_ENTRY_NO_FULL_POSITION", "direction": direction, "entry": entry, "exit": None, "net_pnl_usdt": None}
    exit_fill = walk_book(exit_levels, exit_side, base_target=entry["filled_base"])
    if not exit_fill["complete"]:
        return {"status": "PARTIAL_EXIT_UNCLOSED_REMAINDER", "direction": direction, "entry": entry, "exit": exit_fill, "net_pnl_usdt": None}
    entry_quote, exit_quote = entry["filled_quote_usdt"], exit_fill["filled_quote_usdt"]
    gross = exit_quote - entry_quote if direction == "LONG" else entry_quote - exit_quote
    entry_fee = entry_quote * taker_fee_bps / 10000
    exit_fee = exit_quote * taker_fee_bps / 10000
    funding_cost = entry_quote * funding_bps / 10000 * (1 if direction == "LONG" else -1)
    fees = entry_fee + exit_fee
    net = gross - fees - funding_cost
    return {
        "status": "FULLY_SIMULATED", "direction": direction, "entry": entry, "exit": exit_fill,
        "gross_pnl_usdt": gross, "entry_fee_usdt": entry_fee, "exit_fee_usdt": exit_fee,
        "total_fees_usdt": fees, "funding_cost_usdt": funding_cost, "net_pnl_usdt": net,
        "net_return_on_entry_notional_pct": net / entry_quote * 100,
        "assumptions": ["Visible depth snapshots only; no queue priority or hidden liquidity.",
                        "No guarantee of execution; market impact may change after snapshot.",
                        "Funding applies only when an actual funding event occurs during the hold.",
                        "No exchange order was submitted."]
    }

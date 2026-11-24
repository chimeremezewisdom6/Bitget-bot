"""14-day Bitget 60-minute breakout impact and duration study.

Uses public market candles only. No account, order, position, or trading endpoints.
Breakouts are the first 1m close outside the preceding 60 completed 1m candle
range. One event per symbol per 240 minutes avoids counting one move repeatedly.
"""
import asyncio
import json
import math
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

BASE = "https://api.bitget.com"
CATEGORY = "USDT-FUTURES"
MINUTE = 60_000
DAYS = 14
HORIZON = 240
WINDOWS = (5, 10, 15, 30, 60, 120, 240)
CHUNK = 950
OUT = Path(__file__).resolve().parent / "reports/daily_research"


def num(value, default=0.0):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


class RateGate:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.last = 0.0

    async def wait(self):
        async with self.lock:
            delay = 1 / 12 - (time.monotonic() - self.last)
            if delay > 0:
                await asyncio.sleep(delay)
            self.last = time.monotonic()


async def get_json(session, gate, path, params=None):
    error = None
    for attempt in range(6):
        try:
            await gate.wait()
            async with session.get(BASE + path, params=params) as response:
                if response.status == 429 or response.status >= 500:
                    raise RuntimeError("temporary HTTP " + str(response.status))
                response.raise_for_status()
                payload = await response.json()
                if payload.get("code") != "00000":
                    raise RuntimeError(str(payload.get("code")) + " " + str(payload.get("msg")))
                return payload.get("data", [])
        except Exception as exc:
            error = exc
            if attempt < 5:
                await asyncio.sleep(min(20, 1.5 * (2 ** attempt)))
    raise RuntimeError(str(error))


def parse_candles(raw):
    by_ts = {}
    for row in raw or []:
        try:
            if len(row) < 7:
                continue
            ts = int(row[0])
            by_ts[ts] = {
                "ts": ts, "o": num(row[1]), "h": num(row[2]),
                "l": num(row[3]), "c": num(row[4]), "q": num(row[6]),
            }
        except (TypeError, ValueError, IndexError):
            continue
    return [by_ts[k] for k in sorted(by_ts)]


async def fetch_symbol(session, gate, semaphore, symbol, start, end):
    async with semaphore:
        raw = []
        errors = []
        cursor = start
        while cursor < end:
            stop = min(end, cursor + CHUNK * MINUTE)
            params = {
                "category": CATEGORY, "symbol": symbol, "interval": "1m",
                "startTime": str(cursor), "endTime": str(stop - 1),
                "limit": "1000", "type": "market",
            }
            try:
                raw.extend(await get_json(session, gate, "/api/v3/market/candles", params) or [])
            except Exception as exc:
                errors.append(str(exc)[:180])
            cursor = stop
        rows = [x for x in parse_candles(raw) if start <= x["ts"] < end]
        return symbol, rows, errors


def directional_return(start_price, end_price, direction):
    if start_price <= 0 or end_price <= 0:
        return None
    raw = (end_price / start_price - 1) * 100
    return raw if direction == "LONG" else -raw


def measure_forward(rows, index, direction, boundary, is_breakout):
    start = rows[index]["c"]
    future = rows[index + 1:index + HORIZON + 1]
    result = {
        "direction": direction,
        "start_timestamp_ms": rows[index]["ts"],
        "start_price": start,
        "boundary": boundary,
        "horizons": {},
        "duration_minutes": None,
        "duration_censored_at_240m": False,
        "retest_count": 0,
        "max_favorable_excursion_pct": None,
        "max_adverse_excursion_pct": None,
    }
    if len(future) < HORIZON:
        return None

    for minutes in WINDOWS:
        close = future[minutes - 1]["c"]
        result["horizons"][str(minutes)] = {
            "directional_return_pct": round(directional_return(start, close, direction), 6),
            "positive": directional_return(start, close, direction) > 0,
            "close_beyond_breakout_level": (
                close > boundary if direction == "LONG" else close < boundary
            ) if is_breakout else None,
        }

    if direction == "LONG":
        favorable = [(x["h"] / start - 1) * 100 for x in future if start > 0]
        adverse = [(x["l"] / start - 1) * 100 for x in future if start > 0]
        outside = [x["c"] > boundary for x in future]
    else:
        favorable = [(start / x["l"] - 1) * 100 for x in future if x["l"] > 0]
        adverse = [(start / x["h"] - 1) * 100 for x in future if x["h"] > 0]
        outside = [x["c"] < boundary for x in future]

    result["max_favorable_excursion_pct"] = round(max(favorable), 6) if favorable else None
    result["max_adverse_excursion_pct"] = round(min(adverse), 6) if adverse else None
    if is_breakout:
        first_inside = next((i + 1 for i, value in enumerate(outside) if not value), None)
        result["duration_minutes"] = first_inside if first_inside is not None else HORIZON
        result["duration_censored_at_240m"] = first_inside is None
        result["retest_count"] = sum(
            1 for i in range(1, len(outside)) if outside[i - 1] and not outside[i]
        )
        for minutes in WINDOWS:
            if minutes <= HORIZON:
                result["horizons"][str(minutes)]["held_beyond_level"] = all(outside[:minutes])
    return result


def scan_symbol(symbol, rows):
    by_ts = {x["ts"]: i for i, x in enumerate(rows)}
    events = []
    controls = []
    last_event = -HORIZON
    last_control_ts = -1
    # All windows are based on closed candles; future 240m must be complete.
    for i in range(60, len(rows) - HORIZON - 1):
        if any(rows[j]["ts"] - rows[j - 1]["ts"] != MINUTE for j in range(i - 60, i + HORIZON + 1)):
            continue
        prior = rows[i - 60:i]
        candle = rows[i]
        high = max(x["h"] for x in prior)
        low = min(x["l"] for x in prior)
        if candle["c"] > high:
            direction, boundary = "LONG", high
        elif candle["c"] < low:
            direction, boundary = "SHORT", low
        else:
            direction, boundary = None, None

        if direction and i - last_event >= HORIZON:
            measured = measure_forward(rows, i, direction, boundary, True)
            if measured:
                measured.update({
                    "type": "breakout", "symbol": symbol,
                    "breakout_timestamp_utc": datetime.fromtimestamp(candle["ts"] / 1000, timezone.utc).isoformat(),
                    "breakout_close": candle["c"],
                    "prior_60m_high": high, "prior_60m_low": low,
                })
                events.append(measured)
                last_event = i

        # Matched non-breakout comparison: fixed 4h sampling, direction set by
        # the preceding 60m return, and the sampled close must remain in range.
        if candle["ts"] - last_control_ts >= HORIZON * MINUTE and not direction:
            prior_move = directional_return(prior[0]["o"], prior[-1]["c"], "LONG")
            control_direction = "LONG" if (prior_move or 0) >= 0 else "SHORT"
            measured = measure_forward(rows, i, control_direction, 0, False)
            if measured:
                measured.update({
                    "type": "control", "symbol": symbol,
                    "control_timestamp_utc": datetime.fromtimestamp(candle["ts"] / 1000, timezone.utc).isoformat(),
                    "prior_60m_return_pct": round(prior_move or 0, 6),
                })
                controls.append(measured)
                last_control_ts = candle["ts"]
    return events, controls


def median(values):
    values = [x for x in values if x is not None and math.isfinite(x)]
    return round(statistics.median(values), 6) if values else None


def summarize_group(rows, is_breakout):
    output = {"n": len(rows), "horizons": {}}
    for minutes in WINDOWS:
        values = [x["horizons"][str(minutes)]["directional_return_pct"] for x in rows]
        output["horizons"][str(minutes)] = {
            "median_directional_return_pct": median(values),
            "positive_rate_pct": round(100 * sum(x > 0 for x in values) / len(values), 3) if values else None,
            "median_absolute_return_pct": median([abs(x) for x in values]),
        }
        if is_breakout:
            held = [x["horizons"][str(minutes)].get("held_beyond_level") for x in rows]
            output["horizons"][str(minutes)]["still_beyond_breakout_level_pct"] = (
                round(100 * sum(bool(x) for x in held) / len(held), 3) if held else None
            )
    if is_breakout:
        output["duration"] = {
            "median_minutes_capped_at_240": median([x["duration_minutes"] for x in rows]),
            "mean_minutes_capped_at_240": round(statistics.mean([x["duration_minutes"] for x in rows]), 3) if rows else None,
            "still_beyond_after_240m_pct": round(100 * sum(x["duration_censored_at_240m"] for x in rows) / len(rows), 3) if rows else None,
            "median_max_favorable_excursion_pct": median([x["max_favorable_excursion_pct"] for x in rows]),
            "median_max_adverse_excursion_pct": median([x["max_adverse_excursion_pct"] for x in rows]),
        }
    return output


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    end = int(time.time() * 1000) // MINUTE * MINUTE
    start = end - DAYS * 1440 * MINUTE
    gate = RateGate()
    timeout = aiohttp.ClientTimeout(total=55, connect=15)
    async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(limit=24)) as session:
        instruments, tickers = await asyncio.gather(
            get_json(session, gate, "/api/v3/market/instruments", {"category": CATEGORY}),
            get_json(session, gate, "/api/v3/market/tickers", {"category": CATEGORY}),
        )
        live = {
            x.get("symbol") for x in instruments
            if x.get("status") == "online" and x.get("symbol")
            and (x.get("type") == "perpetual" or x.get("instrumentType") == "perpetual")
            and x.get("symbolType", "crypto") == "crypto"
        }
        universe = sorted(
            [x for x in tickers if x.get("symbol") in live],
            key=lambda x: num(x.get("turnover24h")), reverse=True
        )
        max_markets = int(__import__("os").getenv("BITGET_MAX_MARKETS", "0"))
        if max_markets > 0:
            universe = universe[:max_markets]
        semaphore = asyncio.Semaphore(10)
        fetched = await asyncio.gather(*(
            fetch_symbol(session, gate, semaphore, item["symbol"], start, end)
            for item in universe
        ))

    events, controls, coverage = [], [], []
    for symbol, rows, errors in fetched:
        ev, ctl = scan_symbol(symbol, rows)
        events.extend(ev)
        controls.extend(ctl)
        coverage.append({
            "symbol": symbol, "candles": len(rows),
            "coverage_pct": round(100 * len(rows) / (DAYS * 1440), 3),
            "breakouts": len(ev), "controls": len(ctl), "errors": errors,
        })

    grouped = {}
    for direction in ("LONG", "SHORT"):
        ev = [x for x in events if x["direction"] == direction]
        ctl = [x for x in controls if x["direction"] == direction]
        grouped[direction] = {
            "breakouts": summarize_group(ev, True),
            "controls": summarize_group(ctl, False),
            "breakout_minus_control_median_return_pct": {
                str(m): round(
                    (summarize_group(ev, True)["horizons"][str(m)]["median_directional_return_pct"] or 0)
                    - (summarize_group(ctl, False)["horizons"][str(m)]["median_directional_return_pct"] or 0), 6
                ) if ev and ctl else None for m in WINDOWS
            },
        }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_start_utc": datetime.fromtimestamp(start / 1000, timezone.utc).isoformat(),
        "window_end_utc": datetime.fromtimestamp(end / 1000, timezone.utc).isoformat(),
        "duration_days": DAYS, "horizon_minutes": HORIZON,
        "universe": "All currently online eligible USDT perpetuals ordered by current 24h turnover; point-in-time historical universe is not reconstructed.",
        "symbols_requested": len(universe),
        "symbols_with_95pct_candle_coverage": sum(x["coverage_pct"] >= 95 for x in coverage),
        "candles_collected": sum(x["candles"] for x in coverage),
        "breakout_events": len(events), "control_windows": len(controls),
        "by_direction": grouped, "coverage": coverage,
        "definitions": {
            "breakout": "First 1m candle close above the previous 60 completed 1m candles' high (LONG) or below their low (SHORT).",
            "event_deduplication": "At most one breakout event per symbol in each 240-minute period.",
            "duration": "Minutes until the first subsequent 1m close returns inside the breakout boundary; events still outside at 240m are right-censored at 240m.",
            "control": "Non-breakout timestamp sampled at most every 240m; direction follows the prior 60m return sign.",
        },
        "limitations": [
            "This is observational association, not proof that the breakout caused the move.",
            "The control group is a transparent non-breakout baseline, not a randomized experiment.",
            "Current live universe creates survivorship bias; historical listings/delisted contracts are not reconstructed.",
            "Events without a complete 240-minute future window are excluded.",
            "Duration is capped/right-censored at 240 minutes; longer duration requires a longer study horizon.",
            "A 1m close back inside the boundary counts as a failed hold even if price later re-breaks.",
            "No taker flow, OI, funding, liquidation, spread, or slippage is included in this price-impact study.",
        ],
    }

    json_path = OUT / "bitget_60m_breakout_impact_summary.json"
    events_path = OUT / "bitget_60m_breakout_impact_events.jsonl"
    controls_path = OUT / "bitget_60m_breakout_control_windows.jsonl"
    report_path = OUT / "bitget_60m_breakout_impact_report.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    events_path.write_text("".join(json.dumps(x) + "\n" for x in events), encoding="utf-8")
    controls_path.write_text("".join(json.dumps(x) + "\n" for x in controls), encoding="utf-8")

    lines = [
        "# Bitget 60-minute breakout impact and duration study",
        "",
        f"Generated UTC: {summary['generated_at_utc']}",
        f"Window: {summary['window_start_utc']} to {summary['window_end_utc']}",
        f"Markets: {len(universe)}; breakouts: {len(events)}; controls: {len(controls)}",
        f"Markets with >=95% candle coverage: {summary['symbols_with_95pct_candle_coverage']}",
        "",
        "## LONG",
        "| Horizon | Breakout median return | Breakout positive rate | Still above boundary | Control median return | Breakout minus control |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for direction in ("LONG", "SHORT"):
        if direction == "SHORT":
            lines += ["", "## SHORT",
                "| Horizon | Breakout median return | Breakout positive rate | Still below boundary | Control median return | Breakout minus control |",
                "|---:|---:|---:|---:|---:|---:|"]
        data = grouped[direction]
        for m in WINDOWS:
            b = data["breakouts"]["horizons"][str(m)]
            c = data["controls"]["horizons"][str(m)]
            lines.append(
                f"| {m}m | {b['median_directional_return_pct']}% | {b['positive_rate_pct']}% | "
                f"{b.get('still_beyond_breakout_level_pct', 'n/a')}% | "
                f"{c['median_directional_return_pct']}% | "
                f"{data['breakout_minus_control_median_return_pct'][str(m)]}% |"
            )
        d = data["breakouts"].get("duration", {})
        lines += [
            "",
            f"Duration median (capped at 240m): {d.get('median_minutes_capped_at_240')} minutes",
            f"Mean duration (capped at 240m): {d.get('mean_minutes_capped_at_240')} minutes",
            f"Still beyond boundary at 240m: {d.get('still_beyond_after_240m_pct')}%",
            f"Median MFE: {d.get('median_max_favorable_excursion_pct')}%; median MAE: {d.get('median_max_adverse_excursion_pct')}%",
        ]
    lines += ["", "## Method and limitations", *[f"- {x}" for x in summary["limitations"]],
              "", "Raw events: bitget_60m_breakout_impact_events.jsonl",
              "Control windows: bitget_60m_breakout_control_windows.jsonl"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "completed", "symbols": len(universe),
        "coverage_95pct": summary["symbols_with_95pct_candle_coverage"],
        "breakouts": len(events), "controls": len(controls),
        "report": str(report_path), "summary": str(json_path),
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

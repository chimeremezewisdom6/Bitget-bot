"""Build a transparent performance and evidence summary from research JSONL records."""
import json
import csv
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("reports/daily_research")


def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
            except json.JSONDecodeError:
                rows.append({"_parse_error": number})
    return rows


def build_report(root=ROOT):
    try:
        session = json.loads((root / "session.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        session = {}

    observations = read_jsonl(root / "market_observations.jsonl")
    experiments = read_jsonl(root / "shadow_experiments.jsonl")
    all_errors = read_jsonl(root / "collection_errors.jsonl")
    # Keep legacy Reddit/RSS failures in the raw archive, but exclude them from
    # current health because the Bitget-only collector no longer requests feeds.
    external_hosts = ("reddit.com", "coindesk.com", "cointelegraph.com", "rss")
    errors = [
        item for item in all_errors
        if not any(host in json.dumps(item, ensure_ascii=False).lower() for host in external_hosts)
    ]
    candle_streak_checks = read_jsonl(root / "candle_streak_checks.jsonl")
    candle_streak_qualified = [x for x in candle_streak_checks if x.get("qualifies") is True]
    trend_backtests = read_jsonl(root / "trend_first_hour_backtest.jsonl")
    early_window_backtests = read_jsonl(root / "trend_early_window_backtest.jsonl")
    ignition_records = read_jsonl(root / "trend_ignition.jsonl")
    ignition_latest = {}
    for item in ignition_records:
        if item.get("symbol") and item.get("status") == "ANALYZED":
            ignition_latest[item["symbol"]] = item
    ignition_ranked = sorted(
        ignition_latest.values(),
        key=lambda item: max(
            (direction.get("score", 0) for direction in item.get("directions", {}).values()),
            default=0
        ), reverse=True
    )
    ignition_candidates = [
        item for item in ignition_ranked
        if any(direction.get("stage") == "IGNITION_CANDIDATE"
               for direction in item.get("directions", {}).values())
    ]
    early_window_events = [
        event for row in early_window_backtests for event in row.get("events", [])
        if isinstance(event.get("early_window_analysis"), list)
    ]
    early_window_summary = {}
    for minutes in (5, 10, 15, 20, 30, 60):
        samples = [
            window for event in early_window_events
            for window in event.get("early_window_analysis", [])
            if window.get("minutes") == minutes
        ]
        continuation_values = [
            float(item["direction_adjusted_continuation_to_hour_end_pct"])
            for item in samples
            if isinstance(item.get("direction_adjusted_continuation_to_hour_end_pct"), (int, float))
        ]
        matching_values = [
            float(item.get("direction_matching_pct", 0)) for item in samples
        ]
        early_window_summary[minutes] = {
            "samples": len(samples),
            "scored": len(continuation_values),
            "positive": sum(value > 0 for value in continuation_values),
            "mean_continuation": (
                sum(continuation_values) / len(continuation_values) if continuation_values else None
            ),
            "mean_matching": (
                sum(matching_values) / len(matching_values) if matching_values else None
            ),
        }
    trend_events = [
        {**event, "symbol": row.get("symbol")}
        for row in trend_backtests for event in row.get("events", [])
    ]
    trend_long = [x for x in trend_events if x.get("direction") == "LONG"]
    trend_short = [x for x in trend_events if x.get("direction") == "SHORT"]
    trend_matching = [x.get("direction_matching_pct", 0) for x in trend_events]

    # Export every detected event and a per-coin rollup on every report build.
    early_event_lookup = {
        (row.get("symbol"), str(event.get("trend_start_timestamp_ms"))): event
        for row in early_window_backtests for event in row.get("events", [])
    }
    coin_rollups = {}
    for event in trend_events:
        symbol = event.get("symbol")
        if not symbol:
            continue
        item = coin_rollups.setdefault(symbol, {
            "events": 0, "long": 0, "short": 0, "positive": 0,
            "matching_sum": 0.0, "follow_sum": 0.0,
            "best": None, "worst": None,
        })
        item["events"] += 1
        item[event.get("direction", "").lower()] += 1
        follow = float(event.get("first_hour_follow_through_pct", 0) or 0)
        item["positive"] += int(follow > 0)
        item["matching_sum"] += float(event.get("direction_matching_pct", 0) or 0)
        item["follow_sum"] += follow
        detail = {
            "direction": event.get("direction"),
            "start": event.get("trend_start_timestamp_ms"),
            "follow": follow,
        }
        if item["best"] is None or follow > item["best"]["follow"]:
            item["best"] = detail
        if item["worst"] is None or follow < item["worst"]["follow"]:
            item["worst"] = detail

    def utc_text(timestamp_ms):
        return datetime.fromtimestamp(
            int(timestamp_ms) / 1000, timezone.utc
        ).isoformat().replace("+00:00", "Z") if timestamp_ms else ""

    coin_csv = root / "trend_coin_summary.csv"
    with coin_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "symbol", "trend_events", "long_events", "short_events",
            "positive_first_hour_events", "positive_first_hour_pct",
            "avg_direction_matching_candles_pct", "avg_first_hour_follow_through_pct",
            "best_event_direction", "best_event_start_utc", "best_event_follow_through_pct",
            "worst_event_direction", "worst_event_start_utc", "worst_event_follow_through_pct",
        ])
        for symbol, item in sorted(coin_rollups.items(), key=lambda pair: (-pair[1]["events"], pair[0])):
            count = item["events"]
            best, worst = item["best"], item["worst"]
            writer.writerow([
                symbol, count, item["long"], item["short"], item["positive"],
                round(item["positive"] / count * 100, 2),
                round(item["matching_sum"] / count, 2),
                round(item["follow_sum"] / count, 4),
                best["direction"], utc_text(best["start"]), best["follow"],
                worst["direction"], utc_text(worst["start"]), worst["follow"],
            ])

    event_csv = root / "trend_event_details.csv"
    windows = (5, 10, 15, 20, 30, 60)
    with event_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        header = [
            "symbol", "trend_start_utc", "direction", "trend_start_close",
            "first_hour_end_utc", "first_hour_end_close", "first_hour_follow_through_pct",
            "green_candles_60m", "red_candles_60m", "doji_candles_60m",
            "direction_matching_candles_60m", "direction_matching_pct_60m",
        ]
        for minutes in windows:
            header.extend([
                f"green_{minutes}m", f"red_{minutes}m", f"doji_{minutes}m",
                f"direction_match_pct_{minutes}m", f"continuation_after_{minutes}m_pct",
                f"max_favorable_after_{minutes}m_pct", f"max_adverse_after_{minutes}m_pct",
            ])
        writer.writerow(header)
        for event in trend_events:
            detail = early_event_lookup.get((
                event.get("symbol"), str(event.get("trend_start_timestamp_ms"))
            ), {})
            by_window = {
                window.get("minutes"): window
                for window in detail.get("early_window_analysis", [])
            }
            row = [
                event.get("symbol"), utc_text(event.get("trend_start_timestamp_ms")),
                event.get("direction"), event.get("trend_start_close"),
                utc_text(event.get("first_hour_end_timestamp_ms")),
                event.get("first_hour_end_close"), event.get("first_hour_follow_through_pct"),
                event.get("green_candles"), event.get("red_candles"), event.get("doji_candles"),
                event.get("direction_matching_candles"), event.get("direction_matching_pct"),
            ]
            for minutes in windows:
                window = by_window.get(minutes, {})
                row.extend([
                    window.get("green_candles"), window.get("red_candles"),
                    window.get("doji_candles"), window.get("direction_matching_pct"),
                    window.get("direction_adjusted_continuation_to_hour_end_pct"),
                    window.get("max_favorable_excursion_after_window_pct"),
                    window.get("max_adverse_excursion_after_window_pct"),
                ])
            writer.writerow(row)

    signals = [x for x in experiments if x.get("type") == "signal"]
    watch_conditions = [x for x in experiments if x.get("type") == "watch_condition"]
    outcomes = [x for x in experiments if x.get("type") == "orderbook_shadow_outcome"]
    reference_outcomes = [x for x in experiments if x.get("type") == "forward_reference_outcome"]
    unavailable = [x for x in experiments if x.get("type") == "evaluation_unavailable"]

    scored = [
        x for x in outcomes
        if isinstance(x.get("net_after_trading_fees_usdt"), (int, float))
        and isinstance(x.get("notional_usdt"), (int, float))
        and x["notional_usdt"] > 0
    ]
    net_usdt = [float(x["net_after_trading_fees_usdt"]) for x in scored]
    net_bps = [
        float(x["net_after_trading_fees_usdt"]) / float(x["notional_usdt"]) * 10000
        for x in scored
    ]
    wins = sum(value > 0 for value in net_usdt)
    losses = sum(value < 0 for value in net_usdt)
    flat = sum(value == 0 for value in net_usdt)
    gross_profit = sum(value for value in net_usdt if value > 0)
    gross_loss = abs(sum(value for value in net_usdt if value < 0))
    total_net = sum(net_usdt)
    win_rate = wins / len(scored) * 100 if scored else None
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    mean_bps = sum(net_bps) / len(net_bps) if net_bps else None
    mean_win = gross_profit / wins if wins else None
    mean_loss = -gross_loss / losses if losses else None

    by_strategy = defaultdict(list)
    for row in scored:
        bps = float(row["net_after_trading_fees_usdt"]) / float(row["notional_usdt"]) * 10000
        by_strategy[row.get("strategy", "unknown")].append(bps)

    symbols = sorted({x.get("symbol") for x in observations if x.get("symbol")})
    cap_observations = Counter(x.get("activity_band", "UNVERIFIED") for x in observations)

    try:
        watchlist = json.loads(
            (root.parent / "market_cap_watchlist" / "current_watchlist.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        watchlist = {}

    streak_rows = []
    for symbol in sorted({x.get("symbol") for x in candle_streak_checks if x.get("symbol")}):
        symbol_checks = [x for x in candle_streak_checks if x.get("symbol") == symbol]
        latest = symbol_checks[-1]
        qualified = any(x.get("qualifies") for x in symbol_checks)
        streak_rows.append(
            f"| {symbol} | {len(symbol_checks)} | {latest.get('dominant_colour', '—')} | "
            f"{latest.get('dominant_count', '—')} | {'Yes' if qualified else 'No'} |"
        )
    lines = [
        "# 24-Hour Bitget USDT Perpetual Research Report", "",
        f"- Session started UTC: {session.get('started_at_utc', 'unknown')}",
        f"- Session ended UTC: {session.get('ended_at_utc', 'not recorded')}",
        f"- Collector cycles: {session.get('cycles', 0)}",
        f"- Distinct symbols observed: {len(symbols)}",
        f"- Current Bitget turnover-watchlist contracts: {len(watchlist.get('watchlist_symbols', []))}",
        f"- Market observation rows: {len(observations)}",
        f"- Candidate signals eligible for entry evaluation: {len(signals)}",
        f"- Watch-only RSI conditions (no entry): {len(watch_conditions)}",
        f"- Two-snapshot order-book shadow outcomes: {len(scored)}",
        f"- Legacy ticker-reference outcomes: {len(reference_outcomes)}",
        f"- Outcomes unavailable: {len(unavailable)}",
        f"- Collection error records: {len(errors)}",
        f"- 60-minute same-colour candle checks: {len(candle_streak_checks)}",
        f"- Checks meeting 40+ same-colour candles: {len(candle_streak_qualified)}",
        "",
        "## Previous 24-hour trend-start candle-colour backtest",
        "",
        f"- Symbols with completed historical backtests: {len(trend_backtests)}",
        f"- Breakout-based trend starts found: {len(trend_events)} (LONG: {len(trend_long)}; SHORT: {len(trend_short)})",
        f"- Average direction-matching candle share in first hour: {sum(trend_matching) / len(trend_matching):.1f}%" if trend_matching else "- Average direction-matching candle share in first hour: unavailable",
        "- Complete exports: [all 216 coin summaries](trend_coin_summary.csv) and [all trend events with 5/10/15/20/30/60-minute candle/continuation detail](trend_event_details.csv). These files are regenerated whenever this report runs.",
        "",
        "A trend start is defined as a fully closed 1m candle closing above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT). The first hour is the breakout candle plus the next 59 fully closed 1m candles. Green, red and doji candles are counted separately. This is a consistent breakout proxy, not a universal definition of every trend.",
        "",
        "## Early-trend candle windows (separate experiment)",
        "",
        f"- Symbols with early-window backtests: {len(early_window_backtests)}",
        f"- Complete trend events with early-window measurements: {len(early_window_events)}",
        "",
        "For each detected trend, this compares the first 5, 10, 15, 20, 30 and 60 candles. The continuation column is the direction-adjusted price change from that window's closing price to the end of the first hour. Positive means price continued in the trend direction; negative means it reversed. The 60-minute row has no candles remaining after its close, so its continuation-to-hour-end is not scored and is excluded from that metric. These are descriptive historical samples, not proof that early candle colour predicts future returns.",
        "",
        "| First minutes | Events with window data | Avg direction-matching candles % | Positive continuation (scored events) | Avg continuation after window % |",
        "|---:|---:|---:|---:|---:|",
        *[
            (
                f"| {minutes} | {early_window_summary[minutes]['samples']} | "
                f"{early_window_summary[minutes]['mean_matching']:.1f}% | "
                f"{early_window_summary[minutes]['positive']}/{early_window_summary[minutes]['scored']} "
                f"({early_window_summary[minutes]['positive'] / early_window_summary[minutes]['scored'] * 100:.1f}%) | "
                f"{early_window_summary[minutes]['mean_continuation']:.4f}% |"
                if early_window_summary[minutes]['scored'] and early_window_summary[minutes]['mean_continuation'] is not None
                else f"| {minutes} | {early_window_summary[minutes]['samples']} | "
                     f"{early_window_summary[minutes]['mean_matching']:.1f}% | — | — |"
                if early_window_summary[minutes]['samples'] and early_window_summary[minutes]['mean_matching'] is not None
                else f"| {minutes} | 0 | — | — | — |"
            )
            for minutes in (5, 10, 15, 20, 30, 60)
        ],
        "",
        "## Current trend-ignition radar (latest Bitget scan per coin)", "",
        f"- Coins with usable candle/OI analysis: {len(ignition_latest)}",
        f"- LONG/SHORT ignition candidates (score at least 4/7): {len(ignition_candidates)}",
        "- This radar ranks developing movement using 1m price/candle structure and volume, plus Bitget 5m historical aggregate open interest. OI is not long/short-specific.",
        "",
        "| Coin | Side | Score / 7 | Stage | Price 5m | Price 15m | OI 15m | Volume x | 5m candle colour | Positioning context |",
        "|---|---|---:|---|---:|---:|---:|---:|---|---|",
        *[
            (
                f"| {item.get('symbol')} | {side} | {data.get('score')} / 7 | {data.get('stage')} | "
                f"{data.get('price_change_pct', {}).get('5m')}% | {data.get('price_change_pct', {}).get('15m')}% | "
                f"{(str(data.get('open_interest_change_pct', {}).get('15')) + '%') if data.get('open_interest_change_pct', {}).get('15') is not None else 'unavailable'} | "
                f"{item.get('volume_multiple_5m_vs_prior20m')}x | "
                f"{item.get('candle_windows', {}).get('5', {}).get('green')}/{item.get('candle_windows', {}).get('5', {}).get('red')} | "
                f"{data.get('positioning_context')} |"
            )
            for item in ignition_ranked[:40]
            for side, data in sorted(item.get("directions", {}).items(),
                                     key=lambda pair: pair[1].get("score", 0), reverse=True)[:1]
        ],
        *([] if ignition_ranked else ["| No completed ignition analyses yet | — | — | — | — | — | — | — | — | — |"]),
        "",
        "Scoring checks: aligned 5m/15m price acceleration, rising 15m OI, 5m turnover surge versus the prior 20m, directional candle pressure with real candle bodies, 20m breakout, 60m breakout, and higher-high/lower-low structure. Scores are evidence counts, not probabilities. A high score is a research watch candidate, not a buy/sell instruction. Rising aggregate OI means total outstanding positions increased; it does not reveal whether longs or shorts initiated them.",
        "",
        "| Symbol | Direction | Trend start (UTC) | Green | Red | Doji | Matching candles | Matching % | First-hour follow-through % |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {x.get('symbol')} | {x.get('direction')} | "
            f"{__import__('datetime').datetime.fromtimestamp(x.get('trend_start_timestamp_ms', 0) / 1000, __import__('datetime').timezone.utc).strftime('%Y-%m-%d %H:%M')} | "
            f"{x.get('green_candles')} | {x.get('red_candles')} | {x.get('doji_candles')} | "
            f"{x.get('direction_matching_candles')} / 60 | {x.get('direction_matching_pct')}% | "
            f"{x.get('first_hour_follow_through_pct')}%"
            for x in sorted(trend_events, key=lambda item: item.get("direction_matching_pct", 0), reverse=True)[:100]
        ],
        *([] if trend_events else ["| No complete breakout trends found | — | — | — | — | — | — | — | — |"]),
        "",
        "## Mandatory 60-minute same-colour candle experiment", "",
        "Each eligible symbol is checked up to five separate times. Every check uses the latest 60 fully closed one-minute candles; green and red candles are counted separately, doji candles count toward neither colour, and a result qualifies when either colour reaches at least 40. This is a research filter, not a trade instruction.",
        "",
        "| Symbol | Checks recorded | Latest colour | Same-colour count | Qualified |",
        "|---|---:|---|---:|---|",
        *streak_rows,
        *([] if candle_streak_checks else ["| No complete 60-candle checks yet | 0 | — | — | — |"]),
        "",
        "## Bitget futures-turnover activity-group coverage", "",
        "| Group | Watchlist candidates | Observation rows |",
        "|---|---:|---:|",
        *[
            f"| {band.get('label', band['name'])} | "
            f"{len(watchlist.get('selected_groups', watchlist.get('groups', {})).get(band['name'], []))} | "
            f"{cap_observations.get(band['name'], 0)} |"
            for band in watchlist.get("activity_band_definitions", [])
        ],
        *([] if watchlist.get("activity_band_definitions") else ["| No current activity watchlist | 0 | 0 |"]),
        "",
        "## Profit-versus-loss summary (hypothetical book-walk outcomes)", "",
        f"- Positive outcomes: {wins}; negative outcomes: {losses}; flat: {flat}",
        f"- Win rate among scored outcomes: {win_rate:.1f}%" if win_rate is not None else "- Win rate: unavailable",
        f"- Gross positive outcomes: {gross_profit:.6f} USDT",
        f"- Gross negative outcomes: {gross_loss:.6f} USDT",
        f"- Total estimated net after trading fees: {total_net:.6f} USDT",
        f"- Profit factor (gross gains / gross losses): {profit_factor:.3f}" if profit_factor is not None else "- Profit factor: unavailable (no scored losses or no scored outcomes)",
        f"- Average winning outcome: {mean_win:.6f} USDT" if mean_win is not None else "- Average winning outcome: unavailable",
        f"- Average losing outcome: {mean_loss:.6f} USDT" if mean_loss is not None else "- Average losing outcome: unavailable",
        f"- Mean estimated net result: {mean_bps:.2f} bps" if mean_bps is not None else "- Mean estimated net result: unavailable",
        "",
        "These estimates walk the visible entry book and a later visible exit book, deducting the authenticated account-specific Bitget taker fee when available, otherwise instrument metadata; missing fees are not assumed to be zero. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. The same signal is evaluated at multiple sizes and horizons, so these rows are correlated and must not be treated as independent trades. A completed simulation is not proof of profitability.",
        "",
        f"- Ticker-only reference outcomes (separate, not executable): {len(reference_outcomes)}",
        "",
        "## Strategy breakdown", "",
        "| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |",
        "|---|---:|---:|---:|---:|"
    ]

    for name, values in sorted(by_strategy.items()):
        lines.append(
            f"| {name} | {len(values)} | {sum(v > 0 for v in values)} | "
            f"{sum(v < 0 for v in values)} | {sum(values) / len(values):.2f} |"
        )
    if not by_strategy:
        lines.append("| No scored outcomes | 0 | 0 | 0 | — |")

    lines += [
        "", "## Legacy Trader discussion records", "",
        "Older trader discussion records, if present in the repository, are historical and unverified. The Bitget-only collector does not fetch, update or use them in research conclusions.",
        "", "## Limitations", "",
        "- The collector uses Bitget USDT perpetual market endpoints only. It samples the highest-turnover eligible contracts plus selected contracts from the current provisional four-band watchlist; market capitalisation is not inferred from ticker symbols.",
        "- Bitget futures endpoints do not provide circulating market cap; this report groups coins by Bitget 24h futures turnover instead.",
        "- GitHub scheduled runs may be delayed or skipped; cycles and timestamps show actual collection, not guaranteed continuous monitoring.",
        "- Funding is not included in the automatic short-horizon net P&L. Fees are estimated from instrument metadata and may differ from the account's actual fee tier.",
        "- Any ticker-only legacy outcomes are reference-price calculations and are kept separate from two-snapshot order-book shadow outcomes.",
        "- Small samples, repeated signals, correlated coins and changing regimes can distort apparent performance.",
        "- No Demo or Live orders were placed.", "",
        "## Research files", "",
        "- market_observations.jsonl — timestamped ticker/order-book summaries.",
        "- candles_1m.jsonl — de-duplicated one-minute candles.",
        "- trend_first_hour_backtest.jsonl — rolling 24-hour breakout trend starts and first-hour candle-colour counts.",
        "- trend_early_window_backtest.jsonl — separate 5/10/15/20/30/60-minute candle-window measurements and continuation outcomes.",
        "- trend_ignition.jsonl — per-cycle LONG/SHORT trend-development scores combining Bitget 1m candle structure, turnover acceleration and historical 5m open interest.",
        "- shadow_experiments.jsonl — signals, partial entry/exit records, book-walk outcomes and unavailable evaluations.",
        "- collection_errors.jsonl — Bitget API and processing failures.", ""
    ]
    status = {
        "schema_version": 1,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "BITGET_ONLY_READ_ONLY",
        "data_source": "Bitget USDT-FUTURES",
        "trading_enabled": False,
        "session": {
            "active": bool(session.get("active", False)),
            "started_at_utc": session.get("started_at_utc"),
            "ends_at_utc": session.get("ends_at_utc"),
            "last_collection_utc": session.get("last_at"),
            "cycles": session.get("cycles", 0),
            "symbols_last_cycle": session.get("symbols_last_cycle", 0),
            "bitget_auth_status": session.get("bitget_auth_status", "NOT_CHECKED"),
        },
        "coverage": {
            "distinct_symbols_observed": len(symbols),
            "market_observation_rows": len(observations),
            "one_minute_candle_records": len(read_jsonl(root / "candles_1m.jsonl")),
            "long_trend_starts": len(trend_long),
            "short_trend_starts": len(trend_short),
            "early_window_trend_events": len(early_window_events),
            "trend_ignition_latest_symbols": len(ignition_latest),
            "trend_ignition_candidates": len(ignition_candidates),
            "trend_ignition_records": len(ignition_records),
        },
        "candle_streak_experiment": {
            "checks": len(candle_streak_checks),
            "qualified_40_plus": len(candle_streak_qualified),
        },
        "shadow_execution": {
            "scored_orderbook_outcomes": len(scored),
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "estimated_net_usdt": round(total_net, 8),
            "mean_net_bps": round(mean_bps, 4) if mean_bps is not None else None,
        },
        "health": {
            "collection_error_records": len(errors),
            "latest_error": errors[-1] if errors else None,
            "status": "CHECK_ERRORS" if errors else "NO_RECORDED_ERRORS",
        },
        "report_file": "daily_research_summary.md",
    }
    (root / "research_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    output = ROOT / "daily_research_summary.md"
    output.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {output}")

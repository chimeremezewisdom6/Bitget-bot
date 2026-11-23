"""Build a transparent performance and evidence summary from research JSONL records."""
import json
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
    posts = read_jsonl(root / "public_trader_posts.jsonl")
    experiments = read_jsonl(root / "shadow_experiments.jsonl")
    errors = read_jsonl(root / "collection_errors.jsonl")
    candle_streak_checks = read_jsonl(root / "candle_streak_checks.jsonl")
    candle_streak_qualified = [x for x in candle_streak_checks if x.get("qualifies") is True]

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

    sources = Counter(x.get("source", "unknown") for x in posts)
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
        f"- Public commentary items: {len(posts)}",
        f"- Candidate signals eligible for entry evaluation: {len(signals)}",
        f"- Watch-only RSI conditions (no entry): {len(watch_conditions)}",
        f"- Two-snapshot order-book shadow outcomes: {len(scored)}",
        f"- Legacy ticker-reference outcomes: {len(reference_outcomes)}",
        f"- Outcomes unavailable: {len(unavailable)}",
        f"- Collection error records: {len(errors)}",
        f"- 60-minute same-colour candle checks: {len(candle_streak_checks)}",
        f"- Checks meeting 40+ same-colour candles: {len(candle_streak_qualified)}",
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

    lines += ["", "## Public trader and community commentary (unverified)", ""]
    lines += [f"- {source}: {count} items" for source, count in sources.most_common()] or ["- None collected."]
    recent_posts = sorted(posts, key=lambda x: x.get("collected_at_utc", ""), reverse=True)[:30]
    if recent_posts:
        lines += ["", "### Recent collected posts", ""]
        for post in recent_posts:
            title = str(post.get("title", "Untitled")).replace("\n", " ").replace("|", "/")[:220]
            url = post.get("url")
            link = f"[source]({url})" if isinstance(url, str) and url.startswith("http") else str(post.get("source", "source"))
            published = post.get("published") or post.get("collected_at_utc") or "date unavailable"
            lines.append(f"- {title} — {link} — {published}")

    lines += [
        "", "## Limitations", "",
        "- The collector samples the highest-turnover eligible Bitget USDT perpetual contracts plus selected contracts from the current provisional four-band watchlist. Bitget-reported contract names are used; market capitalisation is not inferred from ticker symbols.",
        "- Bitget futures endpoints do not provide circulating market cap; this report groups coins by Bitget 24h futures turnover instead.",
        "- Public trader posts are unverified statements, not authenticated fills or audited track records.",
        "- GitHub scheduled runs may be delayed or skipped; cycles and timestamps show actual collection, not guaranteed continuous monitoring.",
        "- Funding is not included in the automatic short-horizon net P&L. Fees are estimated from instrument metadata and may differ from the account's actual fee tier.",
        "- Any ticker-only legacy outcomes are reference-price calculations and are kept separate from two-snapshot order-book shadow outcomes.",
        "- Small samples, repeated signals, correlated coins and changing regimes can distort apparent performance.",
        "- No Demo or Live orders were placed.", "",
        "## Research files", "",
        "- market_observations.jsonl — timestamped ticker/order-book summaries.",
        "- candles_1m.jsonl — de-duplicated one-minute candles.",
        "- public_trader_posts.jsonl — public RSS commentary and verification caveats.",
        "- shadow_experiments.jsonl — signals, partial entry/exit records, book-walk outcomes and unavailable evaluations.",
        "- collection_errors.jsonl — API/feed failures.", ""
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    output = ROOT / "daily_research_summary.md"
    output.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {output}")

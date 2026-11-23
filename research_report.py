"""Build a transparent summary from the 24-hour shadow research JSONL records."""
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
    signals = [x for x in experiments if x.get("type") == "signal"]
    watch_conditions = [x for x in experiments if x.get("type") == "watch_condition"]
    outcomes = [x for x in experiments if x.get("type") == "orderbook_shadow_outcome"]
    reference_outcomes = [x for x in experiments if x.get("type") == "forward_reference_outcome"]
    unavailable = [x for x in experiments if x.get("type") == "evaluation_unavailable"]
    net = [float(x["net_after_trading_fees_usdt"]) / float(x["notional_usdt"]) * 10000
           for x in outcomes if isinstance(x.get("net_after_trading_fees_usdt"), (int, float))
           and isinstance(x.get("notional_usdt"), (int, float)) and x["notional_usdt"] > 0]
    wins, losses, flat = sum(x > 0 for x in net), sum(x < 0 for x in net), sum(x == 0 for x in net)
    by_strategy = defaultdict(list)
    for row in outcomes:
        if isinstance(row.get("net_after_trading_fees_usdt"), (int, float)) and row.get("notional_usdt", 0) > 0:
            by_strategy[row.get("strategy", "unknown")].append(float(row["net_after_trading_fees_usdt"]) / float(row["notional_usdt"]) * 10000)
    symbols = sorted({x.get("symbol") for x in observations if x.get("symbol")})
    sources = Counter(x.get("source", "unknown") for x in posts)
    avg = sum(net) / len(net) if net else None
    lines = [
        "# 24-Hour Bitget USDT Perpetual Research Report", "",
        f"- Session started UTC: {session.get('started_at_utc', 'unknown')}",
        f"- Session ended UTC: {session.get('ended_at_utc', 'not recorded')}",
        f"- Collector cycles: {session.get('cycles', 0)}",
        f"- Distinct symbols observed: {len(symbols)}",
        f"- Market observation rows: {len(observations)}",
        f"- Public commentary items: {len(posts)}",
        f"- Candidate signals eligible for entry evaluation: {len(signals)}",
        f"- Watch-only RSI conditions (no entry): {len(watch_conditions)}",
        f"- Two-snapshot order-book shadow outcomes: {len(net)}",
        f"- Legacy ticker-reference outcomes: {len(reference_outcomes)}",
        f"- Outcomes unavailable: {len(unavailable)}",
        f"- Collection error records: {len(errors)}", "",
        "## Two-snapshot order-book shadow outcomes (not exchange fills)", "",
        f"- Positive: {wins}; negative: {losses}; flat: {flat}",
        f"- Mean estimated net result: {avg:.2f} bps" if avg is not None else "- Mean estimated net result: unavailable", "",
        "These estimates walk the visible entry book and a later visible exit book, and deduct the instrument taker fee metadata when available. They are not executable fills and may omit queue position, latency, hidden liquidity, book changes between snapshots and funding. A completed simulation is not proof of profitability. Ticker-only reference outcomes, if any, are listed separately and must not be combined with this sample.", "",
        f"- Ticker-only reference outcomes (separate, not executable): {len(reference_outcomes)}", "",
        "## Strategy breakdown", "",
        "| Strategy | Outcomes | Positive | Negative | Mean estimated net (bps) |",
        "|---|---:|---:|---:|---:|"
    ]
    for name, values in sorted(by_strategy.items()):
        lines.append(f"| {name} | {len(values)} | {sum(v > 0 for v in values)} | {sum(v < 0 for v in values)} | {sum(values)/len(values):.2f} |")
    if not by_strategy:
        lines.append("| No scored outcomes | 0 | 0 | 0 | — |")
    lines += ["", "## Public commentary sources", ""]
    lines += [f"- {source}: {count}" for source, count in sources.most_common()] or ["- None collected."]
    lines += [
        "", "## Limitations", "",
        "- The collector samples highest-turnover eligible Bitget USDT perpetual contracts, not a verified four-band market-cap watchlist.",
        "- Market cap is not supplied by Bitget futures endpoints; require a separately timestamped, identity-matched source.",
        "- Public trader posts are unverified statements, not authenticated fills or audited track records.",
        "- GitHub scheduled runs may be delayed or skipped; cycles and timestamps show actual collection, not guaranteed continuous monitoring.",
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

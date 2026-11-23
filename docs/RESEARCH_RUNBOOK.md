# Read-Only Futures Research Runbook

## Safety boundary

This workflow reads public Bitget USDT perpetual market data only. It does not use Bitget API credentials and must not be connected to Demo or Live order placement. The existing scanner workflow is deliberately paused. Do not enable it as part of research.

## Start the 24-hour session

1. Open the repository Actions tab.
2. Select **24-Hour Futures Research (Read Only)**.
3. Select **Run workflow** on the main branch.
4. Choose action **start** and dispatch once.
5. Confirm the run succeeds and commits the session state under reports/daily_research/session.json.

Do not dispatch start again while the session is active. The program rejects a second start rather than resetting the existing data.

## What the recorder does

- Attempts one collection cycle every five minutes while the session is active.
- Samples the highest-turnover online Bitget USDT perpetual contracts above the $500,000 24-hour quote-turnover floor (up to 15 symbols per cycle).
- Saves one-minute candles, tickers, funding/open interest context, spread and visible order-book depth.
- Collects deduplicated public RSS posts from selected crypto/trading sources. These posts are unverified commentary, not verified trader fills.
- Records rule-based signal hypotheses, not recommendations.
- For each signal, attempts $100, $500 and $1,000 hypothetical market entries by walking the current visible order book. If the visible entry book is insufficient or the taker fee is missing, it does not invent a completed entry.
- Attempts fresh exit-book walks after 5, 15 and 30 minutes for the exact hypothetical base quantity. It deducts the instrument taker fee at entry and exit. Funding is recorded as context but is not included in this automatic P&L.
- After 24 hours it stops creating new signals, then allows up to 30 minutes to settle pending 30-minute exit observations.

## Inspect the session

Use Actions → 24-Hour Futures Research (Read Only) → Run workflow → action **status**. This prints the current session state without resetting it.

## Output files

All durable records are committed under reports/daily_research:

- session.json — start/end, cycle counts and session state.
- market_observations.jsonl — ticker and visible depth summaries.
- candles_1m.jsonl — de-duplicated one-minute candles.
- public_trader_posts.jsonl — public commentary, source URL and verification caveat.
- shadow_experiments.jsonl — hypotheses, partial entries, book-walk outcomes and unavailable evaluations.
- pending.json — open hypothetical observations awaiting their exit horizon.
- collection_errors.jsonl — API/RSS failures.
- daily_research_summary.md — automatically rebuilt summary and limitations.

## How to interpret results

- A two-snapshot order-book simulation is not a real fill. It cannot know queue position, hidden liquidity, latency, or what the book did between snapshots.
- Funding is not included in the automatic P&L; do not treat net-after-fees as fully net of all perpetual-futures costs.
- Public trader commentary is not independently verified. Do not assume a post author traded the position.
- Market cap is not supplied by the Bitget futures endpoints. Do not infer cap bands from symbols or spot turnover.
- The top-turnover sample is not the requested verified 12-coin / four-market-cap-group watchlist. Keep this limitation visible until a timestamped identity-matched cap dataset and explicit band definitions are approved.
- GitHub scheduled runs can be delayed or skipped. Inspect timestamps and cycle counts; never describe the recorder as guaranteed continuous monitoring.
- A positive day or a small number of positive shadow outcomes is not evidence of a durable trading edge. Require larger samples, out-of-sample tests, regime coverage and full costs.

## Before any future change to trading permissions

No trading is authorized by this research workflow. Any future Demo or Live test requires a separate explicit user decision and a separate safety review. Research completion does not enable the scanner.

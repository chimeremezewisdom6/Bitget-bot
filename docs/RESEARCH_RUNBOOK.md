# Read-Only Futures Research Runbook

## Safety boundary

This repository now contains one scheduled public-data collector, `daily_research.py`. The former trading scanner, Demo smoke-test workflow, scanner workflow and stale trade-state files have been removed. The retained research code has no account, order, leverage or position-management functions and does not require Bitget API credentials.

## Start the single observation workflow

1. Open [24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Select **Run workflow** on branch `main`.
3. Choose action **start** and dispatch once.
4. The workflow checks that no prior session is active, builds the four-band CoinGecko/Bitget watchlist, starts the 24-hour session and commits the initial state.
5. Confirm the initial Actions run succeeds. Scheduled runs then attempt one collection cycle every five minutes.

No separate watchlist workflow or snapshot workflow is required.

## What the collector records

- Highest-turnover eligible online Bitget USDT perpetual contracts above the $500,000 24-hour quote-turnover floor (up to 15 per cycle), plus selected contracts from the current four-band watchlist.
- One-minute candles, prices, funding/open-interest context, spread and visible order-book depth.
- Up to three candidates per configured market-cap band if identity, turnover and liquidity checks allow.
- Deduplicated public RSS commentary approximately every 15 minutes. These are unverified posts, not verified trader fills or audited track records.
- Rule-based signal hypotheses and hypothetical $100, $500 and $1,000 market entries by walking the visible order book.
- Fresh exit-book walks at 5, 15 and 30 minutes for the exact hypothetical base quantity, including VWAP, slippage, gross P&L and estimated taker-fee-adjusted P&L.
- Collection errors and missing data.

Funding is recorded as context but excluded from automatic short-horizon net P&L. A visible-book walk is not a guaranteed fill.

## Inspect or stop

Choose action **status** to inspect the current session. Choose **stop** to stop early, preserve collected records, rebuild the report and upload the package.

The session stops creating new signals after 24 hours and allows up to 30 minutes for pending 30-minute hypothetical exits. GitHub schedule execution is best-effort, not guaranteed.

## Download results

Open the completed GitHub Actions run and download the `bitget-24-hour-futures-research-...` artifact from **Artifacts**. The same records are committed under `reports/daily_research/`; the market-cap watchlist is under `reports/market_cap_watchlist/`.

Key files include `session.json`, `market_observations.jsonl`, `candles_1m.jsonl`, `public_trader_posts.jsonl`, `shadow_experiments.jsonl`, `collection_errors.jsonl` and `daily_research_summary.md`.

## Interpretation rules

- Two-snapshot order-book simulations cannot know queue position, hidden liquidity, latency or intervening book changes.
- Funding is not included in automatic P&L.
- Public trader commentary is unverified; do not assume authors actually traded.
- Market cap comes from a separate CoinGecko snapshot; ticker matches require identity review.
- GitHub scheduled runs can be delayed or skipped. Use actual timestamps and cycle counts.
- Repeated sizes and horizons from the same signal are correlated, not independent trades.
- A positive day or small sample does not prove a durable edge. Require larger samples, out-of-sample tests, multiple regimes and full costs.

## After the experiment

Upload the downloaded ZIP in this chat. Analyse outcomes, fees, slippage, adverse movement, unavailable fills, market conditions and trader commentary. Separate measured observations from assumptions and public claims. Only after this review should a future trading scanner be considered.

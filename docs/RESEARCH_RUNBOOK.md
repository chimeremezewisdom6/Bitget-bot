# Read-Only Futures Research Runbook

## Safety boundary

The 24-hour research collector reads public Bitget USDT perpetual market data only. It does not need API credentials and has no account, order, leverage, or position-management functions. The existing Demo-capable `scanner.py` and its automated workflow remain separate and paused. Do not enable trading as part of this experiment.

## Start the single observation workflow

1. Open [24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Select **Run workflow** on branch `main`.
3. Choose action **start** and dispatch once.
4. The workflow checks that no session is already active, builds the four-band CoinGecko/Bitget watchlist, starts the 24-hour session, and commits the initial state.
5. Confirm the GitHub Actions run completes successfully. The scheduled workflow then attempts one collection cycle every five minutes.

No separate market-cap workflow or shadow snapshot workflow is required. Do not start another session while one is active.

## What the collector records

- The highest-turnover eligible online Bitget USDT perpetual contracts above the $500,000 24-hour quote-turnover floor (up to 15 symbols per cycle), plus selected contracts from the current four-band watchlist.
- One-minute candles, prices, funding/open-interest context, spread and visible order-book depth.
- Up to three candidates in each configured market-cap band if identity, turnover and liquidity checks allow. It does not force three selections when fewer qualify.
- Deduplicated public RSS commentary approximately every 15 minutes. These are unverified posts, not verified trader fills or audited track records.
- Rule-based signal hypotheses. RSI extremes are watch-only and do not create hypothetical positions without a separate reversal-confirmation rule.
- Hypothetical $100, $500 and $1,000 market entries by walking the visible order book. Insufficient visible depth or missing fee metadata is recorded as partial/unavailable rather than treated as a completed entry.
- Fresh exit-book walks at 5, 15 and 30 minutes for the exact hypothetical base quantity. It records VWAP, slippage, gross P&L and taker-fee-adjusted P&L. Funding is retained as context but excluded from this automatic short-horizon result.
- Collection errors and missing data, so the final analysis can account for gaps rather than only successful outcomes.

## Inspect or stop

Open the same workflow and choose action **status** to print the current session state. Choose **stop** to stop collection early, rebuild the report and upload the collected data. Stopping preserves existing records.

The session automatically stops generating new signals after 24 hours and allows a 30-minute grace period for pending 30-minute hypothetical exits. The next scheduled run marks the session complete and uploads the final research package.

## Download results

Open the completed GitHub Actions run and download the artifact named `bitget-24-hour-futures-research-...` from **Artifacts**. The same records are committed under `reports/daily_research/`, with the market-cap watchlist under `reports/market_cap_watchlist/`.

Key files:

- `session.json` — start/end timestamps, cycle counts and status.
- `market_observations.jsonl` — timestamped market and visible-depth observations.
- `candles_1m.jsonl` — de-duplicated one-minute candles.
- `public_trader_posts.jsonl` — public commentary, source and verification caveat.
- `shadow_experiments.jsonl` — signal hypotheses, partial entries, book-walk outcomes and unavailable evaluations.
- `collection_errors.jsonl` — API and RSS failures.
- `daily_research_summary.md` — generated summary and limitations.
- `../market_cap_watchlist/current_watchlist.json` — provisional four-band watchlist.

## Interpretation rules

- A two-snapshot order-book simulation is not a real fill. It cannot know queue position, hidden liquidity, latency, or what the book did between snapshots.
- Funding is not included in automatic P&L. Do not treat net-after-fees as fully net of all perpetual-futures costs.
- Public trader commentary is unverified. Do not assume a post author actually traded the position.
- Market cap is not supplied by Bitget futures endpoints. The watchlist joins a separate CoinGecko snapshot; exact ticker matches still require manual identity review. Ambiguous or uncertain assets remain unclassified.
- The cap groups in `config/market_cap_bands.json` are provisional and may contain fewer than three candidates in a group.
- GitHub scheduled runs can be delayed or skipped. Use timestamps and cycle counts; never describe this as guaranteed uninterrupted monitoring.
- A positive day or a small number of positive shadow outcomes is not proof of a durable edge. Require larger samples, out-of-sample tests, multiple market regimes and full costs.

## After the experiment

Upload the downloaded artifact ZIP in this chat. Analyse profitable and losing hypothetical outcomes, strategy and coin-group performance, fees, slippage, adverse movement, unavailable fills, market conditions and trader commentary. Keep verified measurements separate from assumptions and public claims. Only after this review should we decide whether and how to rebuild the trading scanner. No Demo or Live trading is authorised by completing the research run.

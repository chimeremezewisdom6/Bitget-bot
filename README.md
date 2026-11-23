# Bitget Futures Market Research (Read Only)

This repository is now a **research-only market observer**. It has one scheduled collector: `daily_research.py`. The old trade-execution scanner, its workflows and inactive trade-state files have been removed. There are no Demo or Live order functions in the retained research modules.

## Start the 24-hour experiment

1. Open [Actions → 24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Choose **Run workflow**, select branch `main`, and choose action **start**.
3. The workflow automatically builds the four-band market-cap/liquidity watchlist, then starts the observation session. No separate workflow is needed.
4. GitHub Actions attempts a collection cycle every five minutes for 24 hours, with up to 30 minutes to evaluate pending 30-minute hypothetical exits.
5. Use action **status** to inspect progress. Use **stop** to end early and preserve the data.

Only start one session at a time. The workflow rejects a second start while the current session or its settlement grace period is active.

## What gets recorded

- Online Bitget USDT perpetual contracts, turnover and price observations.
- One-minute candles, funding/open-interest context, bid/ask spread and visible order-book depth.
- Up to three eligible coins in each provisional market-cap band, when identity and liquidity checks allow.
- Public RSS trader/community commentary, deduplicated and labelled unverified.
- Rule-based signal hypotheses and hypothetical $100/$500/$1,000 order-book entries.
- Fresh hypothetical exit-book walks at 5, 15 and 30 minutes, with VWAP, partial-fill status, slippage and estimated taker fees.
- Collection failures and missing/unavailable observations.

Default provisional cap groups: lower below $10m, smaller $10m–$100m, mid $100m–$1bn, and mega $1bn or above. See `config/market_cap_bands.json`. A unique ticker match is not proof of asset identity. Unverified or ambiguous symbols must not be treated as confirmed assets; do not force three coins into a group if fewer qualify.

## Download the results

When the session completes, the workflow uploads an artifact named similar to `bitget-24-hour-futures-research-...`. Open the completed Actions run and download it from **Artifacts**. Durable records are also committed under:

- `reports/daily_research/market_observations.jsonl`
- `reports/daily_research/candles_1m.jsonl`
- `reports/daily_research/public_trader_posts.jsonl`
- `reports/daily_research/shadow_experiments.jsonl`
- `reports/daily_research/collection_errors.jsonl`
- `reports/daily_research/session.json`
- `reports/daily_research/daily_research_summary.md`
- `reports/market_cap_watchlist/current_watchlist.json` and `current_watchlist.md`

Upload the ZIP here after the run. The report separates estimated hypothetical outcomes from unverified trader commentary. We can then analyse wins/losses by strategy, coin group, market regime, size and holding period before designing any future trading system.

## Important limitations

GitHub's five-minute schedule is best-effort; runs may be delayed or skipped. Check actual timestamps and cycle counts. Public posts are not authenticated trader histories or proof of fills. Visible-book simulations are estimates, not guaranteed executions. Funding is recorded as context but is not included in automatic short-horizon net P&L. A 24-hour sample cannot prove a durable profitable edge.

## Project files

- `daily_research.py` — single scheduled, public-data collector.
- `cap_watchlist.py` — automatically builds the provisional four-band watchlist.
- `shadow_execution.py` — pure order-book fill, slippage and fee calculations.
- `research_report.py` — produces profit/loss and evidence summaries.
- `config/` — market-cap boundaries and optional manual identity overrides.
- `tests/` — research calculations and read-only safety tests.
- `archive/legacy_trade_history.json` — retained historical records for later review; not used by the collector.
- `docs/PROJECT_KNOWLEDGE_BASE.md` — dated project decisions and lessons.
- `docs/RESEARCH_RUNBOOK.md` — operating instructions.

## Validation

Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt
python -m py_compile daily_research.py shadow_execution.py research_report.py cap_watchlist.py
python -m unittest discover -s tests -v
```

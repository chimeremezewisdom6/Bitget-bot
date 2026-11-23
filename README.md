# Bitget Futures Scanner and Research

This repository retains one trading scanner, `scanner.py`, and one separate **read-only research collector**, `daily_research.py`. The collector is the only scheduled market-observation process. It does not need API keys and cannot place Demo or Live orders.

## Current operating mode: observation only

- Do not place Live or Demo orders.
- The automated trading workflow `.github/workflows/scanner.yml` remains deliberately disabled.
- Keep `scanner.py` intact for future, separately authorised work; it is not used by the 24-hour research experiment.
- Do not run the scanner with `BOT_DRY_RUN=false`.
- The five-minute research workflow uses public Bitget market endpoints only. It does not read account balances, positions, or submit orders.

## Start the 24-hour experiment

1. Open [Actions → 24-Hour Futures Research (Read Only)](https://github.com/chimeremezewisdom6/Bitget-bot/actions/workflows/daily-futures-research.yml).
2. Choose **Run workflow**, select branch `main`, and choose action **start**.
3. The workflow automatically builds the current four-band watchlist, then starts the observation session. You do not need to run a separate watchlist workflow.
4. Leave the workflow enabled. GitHub Actions attempts a collection cycle every five minutes for 24 hours, followed by up to 30 minutes to evaluate pending 30-minute hypothetical exits.
5. Use action **status** to inspect progress. Use **stop** to end early and preserve the collected data.

Only start one session. The workflow rejects a second start while the current session or its settlement grace period is active.

## What gets recorded

- Online Bitget USDT perpetual contracts, turnover and price observations.
- One-minute candles, funding/open-interest context, bid/ask spread and visible order-book depth.
- Up to three eligible coins in each provisional market-cap band, when enough correctly identified and liquid candidates exist.
- Public RSS trader/community commentary, deduplicated and explicitly labelled unverified.
- Rule-based signal hypotheses and hypothetical $100/$500/$1,000 order-book entries.
- Fresh hypothetical exit-book walks at 5, 15 and 30 minutes, with VWAP, partial-fill status, slippage and taker-fee estimates.
- Collection failures and missing/unavailable observations, not just favorable outcomes.

The default cap groups are provisional: lower below $10m, smaller $10m–$100m, mid $100m–$1bn, and mega $1bn or above. See `config/market_cap_bands.json`. Exact ticker matches are not proof of asset identity; ambiguous or unverified assets must remain unclassified. Do not force three coins into a band when fewer qualify.

## Download the results

The completed run uploads a downloadable GitHub Actions artifact named similar to `bitget-24-hour-futures-research-...`. Open the workflow run and download it from **Artifacts**. The same durable records are committed under:

- `reports/daily_research/market_observations.jsonl`
- `reports/daily_research/candles_1m.jsonl`
- `reports/daily_research/public_trader_posts.jsonl`
- `reports/daily_research/shadow_experiments.jsonl`
- `reports/daily_research/collection_errors.jsonl`
- `reports/daily_research/session.json`
- `reports/daily_research/daily_research_summary.md`
- `reports/market_cap_watchlist/current_watchlist.json` and `current_watchlist.md`

Upload the artifact ZIP here after the run. I can then compare hypothetical wins and losses by strategy, coin group, market regime, notional size and holding horizon, while separating measured exchange data from unverified trader claims.

## Important limitations

A five-minute GitHub schedule is best-effort: runs may be delayed or skipped. Inspect actual timestamps and cycle counts. Public posts are not authenticated trader histories or proof of fills. A visible-book entry and later exit are estimates, not guaranteed executions; funding is recorded as context but is not included in the automatic short-horizon net P&L. A 24-hour sample is exploratory and cannot prove a durable profitable edge.

## Project files

- `scanner.py` — existing Demo-capable scanner; do not activate during this experiment.
- `daily_research.py` — single scheduled, public-data observation collector.
- `cap_watchlist.py` — called automatically at session start to create the provisional cap-group watchlist.
- `shadow_execution.py` — pure order-book fill and fee calculations; no network or trading access.
- `research_report.py` — transparent summary of observed records.
- `config/` — cap bands and manually verified asset-identity overrides.
- `tests/` — unit and safety-boundary tests.
- `docs/PROJECT_KNOWLEDGE_BASE.md` — dated history, decisions and lessons.
- `docs/RESEARCH_RUNBOOK.md` — concise operating instructions.

## Validation

Python 3.11 or newer:

```bash
python -m pip install -r requirements.txt
python -m py_compile scanner.py daily_research.py shadow_execution.py research_report.py cap_watchlist.py
python -m unittest discover -s tests -v
```

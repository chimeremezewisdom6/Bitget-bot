# ChatGPT research handoff

This document is the short operating map for a future assistant session. The user wants a hands-off Bitget research application: when they return, inspect the repository's latest evidence and explain what it has learned without asking them to repeat the setup.

## Repository and operating model

- Repository: `chimeremezewisdom6/Bitget-bot`
- Default branch: `main`
- Runtime market-data provider: Bitget USDT-FUTURES only.
- GitHub Actions is the code host and scheduler, not a market-data provider.
- The research collector is read-only. It must not place, amend or cancel orders, change leverage, change margin mode, or enable live trading.
- The research workflow attempts a collection every five minutes. GitHub scheduling is best-effort; verify actual schedule-event runs and heartbeat timestamps rather than trusting the cron expression alone.
- The workflow now automatically ensures a 24-hour session exists on schedule/push events. It should not require the user to manually ping or start a session.
- A code/workflow push to `main` bootstraps one collection cycle. Report-data commits do not trigger another push cycle because they are excluded by the workflow path filter.

## Read these files first when resuming

1. `reports/daily_research/research_status.json` — machine-readable current status, data coverage, shadow results and error health.
2. `reports/daily_research/heartbeat.json` — last workflow event, collection outcome, run ID, last collection time and cycle count.
3. `reports/daily_research/session.json` — session start/end, active flag, cycles and Bitget authentication status.
4. `reports/daily_research/daily_research_summary.md` — human-readable research report and analysis.
5. `reports/daily_research/collection_errors.jsonl` — inspect the latest actual Bitget/API or processing errors. Archived Reddit/RSS errors are legacy records and are excluded from current health summaries.
6. `reports/daily_research/shadow_experiments.jsonl`, `candles_1m.jsonl`, `trend_first_hour_backtest.jsonl`, `trend_early_window_backtest.jsonl`, and `candle_streak_checks.jsonl` — supporting raw evidence.

## Required research coverage

- Scan eligible Bitget USDT perpetual contracts ranked by 24-hour futures turnover (do not call this market capitalisation; Bitget endpoints do not provide circulating market cap).
- Study LONG and SHORT breakout trend starts and first-hour candle colour.
- Compare the first 5, 10, 15, 20, 30 and 60 minutes of each trend and direction-adjusted continuation.
- Run up to five separate checks per symbol for 60 fully closed one-minute candles; record whether either candle colour reaches 40 or more.
- Observe order books, spread, depth and recent Bitget public fills.
- Simulate entries/exits by walking visible books and estimate fees, slippage, partial fills and net outcomes.
- Keep hypotheses, watch-only conditions, simulated fills and actual account fills clearly separate. These are not live trades.

## Interpretation and safety

- A 40+ candle count is a research observation, not an automatic trade instruction.
- A positive simulated net result is not proof of a profitable strategy. Repeated sizes/horizons and signals can be correlated; account for fees, spread, slippage, latency, funding and sample size.
- Bitget account credentials are used only for signed read-only permission/fee metadata requests. Never print or expose secret values.
- Do not switch to Demo or Live order placement without the user's explicit new instruction and separate safety review.
- Do not claim five-minute monitoring is reliable until the latest `heartbeat.json` and GitHub Actions history show repeated successful main `schedule` runs and watchdog recovery runs where needed. A successful `push` bootstrap proves the workflow and collector can run, but does not prove the cron trigger is firing. The watchdog is a recovery path, not a guarantee against GitHub-wide scheduler outages.
- The assistant cannot watch continuously between chats or send a message on its own. When the user returns, fetch the latest repository state and continue from the files above; do not ask for ZIP uploads unless repository access is unavailable.

## User experience

The user wants minimal manual work. Do not ask them to run Python commands or upload logs when the GitHub repository is accessible. Report plainly: whether the collector ran, the last successful timestamp, what Bitget data it captured, the strongest findings, what remains uncertain, and any action actually needed from the user.

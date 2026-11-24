# Experiment 1 — Bitget gradual-trend fuel study

**Run time (UTC):** 2026-11-24 08:23  
**Data window:** 2026-11-23 08:22 to 2026-11-24 08:22  
**Status:** Completed; authenticated Bitget read-only access confirmed.

## Question

Which observable market conditions are associated with a gradual move of at least 4% over two hours, where the two-hour directional move is at least four times the absolute first-ten-minute move?

## Experiment design

- Universe: top 200 online crypto USDT perpetuals by 24-hour turnover.
- Data: 1-minute closed candles; 288,000 candles collected; 200/200 symbols usable; zero candle-fetch errors.
- Candidate: a 1-minute close beyond the preceding 60-minute high or low.
- Forward outcome: next 120 minutes.
- Gradual trend: at least 4% direction-adjusted return, all 120 closes remain beyond the breakout boundary, and the two-hour return / absolute first-10-minute return is at least 4.
- Fast spike: at least 4% over two hours but fails the 4x gradualness ratio.
- Other candidates: failed or weak.
- Early features: direction-adjusted return, same-direction candle share, turnover relative to the preceding 20-minute baseline, and path efficiency, measured at 1/3/5/10/15/30 minutes.

## Observed results

| Outcome | Count |
|---|---:|
| Gradual trends | 10 |
| Fast 4% spikes | 30 |
| Failed or weak | 1,761 |
| Total candidates | 1,801 |

At the 10-minute horizon:

| Feature | Gradual median | Failed/weak median | Fast-spike median |
|---|---:|---:|---:|
| Turnover / prior 20m | 2.335x | 1.685x | 6.831x |
| Directional candle share | 50% | 40% | 60% |
| Path efficiency | 0.394 | 0.360 | 0.656 |

At 30 minutes, gradual trends had median path efficiency 0.331, versus 0.199 for failed/weak candidates and 0.254 for fast spikes. Gradual trends' median turnover ratio was 2.424x at 30 minutes, versus 1.622x for failed/weak and 5.055x for fast spikes.

## What this suggests — not what it proves

1. **Turnover expansion is associated with breakouts, but it is not a direction signal.** Fast spikes showed much larger turnover surges than gradual trends. A simple volume/turnover spike may therefore select explosive moves rather than the slower trend type being sought.
2. **Persistence and path quality may be more useful than maximum early activity.** At 30 minutes, gradual trends had better median path efficiency than both comparison groups. This is a preliminary clue that sustained directional progress with less reversal may distinguish gradual trends.
3. **A few same-colour candles are not enough evidence.** At 10 minutes the gradual group median directional candle share was only 50%; the fast-spike group was 60%. Counting candle colour alone does not distinguish the target trend reliably in this sample.
4. **The evidence does not establish the fuel or cause.** These are associations measured after a breakout candidate has already occurred. The study does not establish that turnover, candle colour, or efficiency caused continuation.
5. **The sample is too small for a stable ranking.** Only 10 gradual events were observed in this one-day window. Do not turn these medians into trading rules.

## Data limitations and quality flags

- Historical open-interest alignment was available for only 21 of 1,801 candidate events. Many per-symbol OI calls returned HTTP 429. OI conclusions are therefore not reliable in this run.
- Aggregate open interest cannot reveal whether new longs or shorts initiated positions.
- Historical taker buy/sell flow, historical funding, and historical order-book depth were not retrieved. No claims about these variables are made.
- The 10-minute features are measured after the breakout candidate. They are early continuation descriptors, not pre-breakout predictors.
- The first one-minute directional candle share and path efficiency are mechanically 1.0 for many/all groups because the candidate is selected on a breakout close. Those one-minute metrics are not useful discriminators.
- The strict requirement that every one of 120 closes stay beyond the breakout boundary may exclude valid trends that retest the level. A parallel tolerant-retest label should be tested.
- The study is a single 24-hour observational sample. It does not prove causality or net profitability after fees, spread, slippage, and funding.

## Next experiments

1. Extend the identical event definitions across at least 14–30 days, store each daily run, and use chronological train/validation/test periods.
2. Add a tolerant-hold outcome (for example, permit a small, explicitly defined number of closes back through the breakout level) alongside the strict label.
3. Build pre-breakout features using only information available before the breakout: preceding turnover acceleration, range compression, volatility, candle-body/wick structure, and trend context.
4. Compare gradual trends separately against fast spikes and failed breakouts, with matched symbol/time/volatility controls.
5. Repair historical OI collection using rate limiting, backoff, endpoint parameter validation, and timestamp coverage checks before interpreting OI.
6. Add only genuine timestamped historical taker flow/funding/order-book data if Bitget provides it at the needed historical resolution.
7. Evaluate out-of-sample precision, recall, calibration, and net returns after realistic trading costs. No live trading.

## Source artifacts

- Full report: `reports/daily_research/bitget_fuel_attribution_report.md`
- Event-level data: `reports/daily_research/bitget_fuel_attribution_events.jsonl`
- Machine-readable summary: `reports/daily_research/bitget_fuel_attribution_summary.json`

**Bottom line:** This first experiment points toward sustained path efficiency and moderate, persistent participation as more promising clues than the biggest turnover burst or simply counting candle colours. It is a research lead, not a proven cause or validated signal.

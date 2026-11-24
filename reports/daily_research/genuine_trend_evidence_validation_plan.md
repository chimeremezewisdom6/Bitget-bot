# Genuine Trend Evidence Validation — Research Protocol

Generated: 2026-11-24

## Purpose

Test whether early Bitget market evidence actually distinguishes a gradual, sustained 2-hour move from a short-lived spike. This is a research-only experiment. No orders, balances, or withdrawals are accessed.

## What the existing 24-hour study established

The authenticated run completed for 200 online USDT perpetual contracts and processed 288,000 closed 1-minute candles. It found 686 2-hour breakout-and-hold candidates, 86 with at least 4% directional return, 53 rejected by the first-10-minute 4x speed rule, and 33 qualifying gradual trends (18 LONG, 15 SHORT).

The 33-event sample is descriptive, not proof of prediction. It is selected using the final 120-minute outcome, so it cannot establish that the early evidence would have identified those trends before they happened.

## Audit findings and limitations

1. The current detector requires every one of the 120 closes to remain beyond the original 60-minute breakout boundary. This is a strict breakout-hold definition; it may reject valid trends that retest the level and recover.
2. The 4x rule is currently evaluated using the first 10 minutes only: absolute first-10-minute directional move must be no more than one quarter of the final 2-hour directional return. The largest later rolling 10-minute move is reported but does not disqualify the event. This is consistent with the current written implementation; it does not test whether a trend later turns into a spike.
3. The report's turnover acceleration is an association observed after selecting completed trends. It has not been compared against failed breakouts or ordinary market periods.
4. Historical open interest was alignable at both event boundaries for only 1 of 33 events. Funding and order-book values were current snapshots, not historical event-time evidence. Historical aggressive buyer/seller dominance was not measured.
5. The 2-hour workflow is push/manual-dispatch triggered, not a five-minute scheduled workflow. The separate unified scanner is scheduled every five minutes. The two workflows therefore have different responsibilities.
6. The unified scanner's latest committed heartbeat inspected during this audit was 2026-11-24 06:27 UTC (18 collection cycles). That file alone does not prove the schedule remained healthy through the current time; inspect recent scheduled Actions runs and heartbeat freshness before claiming continuous operation.

## Next experiment: walk-forward early-evidence validation

### A. Build an unbiased event universe

- Scan the same top 200 online crypto USDT perpetuals by 24-hour turnover.
- Use closed 1-minute candles only and preserve exact UTC timestamps.
- Identify candidate 60-minute high/low breakouts, but do not select events based on the eventual 2-hour return when building the feature dataset.
- Include positive outcomes, failed breakouts, reversals, low-volatility periods, and abrupt spikes.
- De-duplicate overlapping candidates per symbol and direction with a documented cooldown.
- Save every candidate and its eventual outcome, including rejected events.

### B. Freeze the user's trend definition as an outcome label

For each candidate, measure the directional net return from breakout close to the close 120 minutes later. A qualifying completed trend must:
- last the full 120 minutes;
- achieve at least 4.0% directional net movement;
- have final 120-minute directional movement at least 4 times the absolute directional move during the first 10 minutes;
- be labelled LONG or SHORT independently.

Also record every rolling 10-minute move during the 120 minutes. Keep this as a separate diagnostic initially; compare a second stricter label that also rejects any later 10-minute burst exceeding one quarter of the final 2-hour movement. Do not silently change the user's primary first-10-minute rule.

### C. Test what is knowable in real time

Create snapshots at +1, +3, +5, +10, +15, +20 and +30 minutes after breakout. At each snapshot, calculate only information available up to that timestamp:
- net directional return and path efficiency;
- candle body/range, directional candle share and wick/rejection behaviour;
- quote turnover versus the preceding 20/60-minute baseline;
- turnover acceleration and trade count, if available;
- taker buy/sell volume imbalance, if the Bitget historical endpoint supplies it;
- open-interest change from timestamp-aligned historical observations;
- funding rate only when historical timestamped values are available;
- spread and order-book imbalance only when timestamped historical snapshots are available;
- BTC/ETH market return over the same interval as context.

Do not fill missing historical fields with current snapshots. Store null plus a reason.

### D. Compare against controls

Compare qualifying trends with:
- breakout candidates that fail to reach +4%;
- breakouts that reverse or lose the breakout level;
- moves that reach +4% but violate the 4x gradual-speed rule;
- randomly sampled non-breakout 2-hour windows matched by coin and volatility.

Report feature distributions and differences for each group. Calculate precision, recall, false-positive rate, and lift for simple rules and a transparent baseline model. Avoid fitting many parameters to one day of data.

### E. Out-of-sample design

- Use earlier dates to discover candidate features and thresholds.
- Freeze the rules.
- Evaluate on later, unseen dates (at least 14 days initially, preferably 30+ days).
- Split by time, not random rows, to avoid future leakage.
- Bootstrap confidence intervals by day and symbol.
- Report results before fees and after conservative fee + spread + slippage assumptions.
- Compare against simple baselines: breakout-only, turnover-only, and price-only.

### F. Evidence quality gates

Do not claim that a feature works unless:
- its values are genuinely timestamp-aligned and known at the prediction time;
- it improves out-of-sample precision/lift over the price-only baseline;
- it retains performance across multiple days and many symbols;
- confidence intervals and sample counts are reported;
- missing-data coverage is disclosed;
- results remain useful after estimated transaction costs.

## Files to publish

- `trend_evidence_candidates.jsonl`: all candidates and labels.
- `trend_evidence_features.jsonl`: timestamped feature snapshots at each decision horizon.
- `trend_evidence_validation.md`: controls, coverage, results, uncertainty, and conclusions.
- `trend_evidence_validation_summary.json`: machine-readable metrics.
- `trend_evidence_validation.py`: reproducible analysis code and tests.

## Automation recommendation

Keep the existing five-minute unified scanner as the live data collector and heartbeat. Do not run a full 200-symbol 24-hour historical backtest every five minutes. Add a separate scheduled daily walk-forward validation job, and let the unified scanner expose its latest validation status/report. Keep all activity read-only.

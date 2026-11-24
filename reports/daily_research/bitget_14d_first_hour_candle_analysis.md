# 14-day first-hour candle analysis

Generated from the existing `bitget_14d_gradual_event_details.jsonl` event rows on 2026-11-24.

## Sample and scope

- 289 tolerant gradual-trend events (the report's strict label is a subset; this file includes events passing the tolerant hold rule).
- 121 LONG and 168 SHORT events.
- Each event contains the 60 one-minute candles after its breakout timestamp.
- A direction-matching candle is GREEN for LONG and RED for SHORT. Doji candles are not counted as directional.
- These are event-level descriptive statistics, not a live signal or proof of prediction.

## First-hour candle-colour results

| First-hour window | Mean share of candles matching trend direction | Median share |
|---|---:|---:|
| First 5 minutes | 56.68% | 60.00% |
| First 10 minutes | 47.99% | 50.00% |
| First 15 minutes | 46.41% | 46.67% |
| First 20 minutes | 45.50% | 50.00% |
| First 30 minutes | 44.90% | 46.67% |
| First 60 minutes | 44.08% | 46.67% |

Across all 289 events, the mean first-hour counts were 22.22 green candles, 23.28 red candles, and 14.50 doji candles. The mean number of direction-matching candles was 26.45 of 60 (44.08%); the median was 28.

## LONG vs SHORT

| Direction | Events | Mean matching candles in first hour | Mean matching share |
|---|---:|---:|---:|
| LONG | 121 | 26.40 / 60 | 44.01% |
| SHORT | 168 | 26.48 / 60 | 44.14% |

Median two-hour direction-adjusted return was 5.995% for LONG and 4.990% for SHORT. Median first-10-minute direction-adjusted move was 0.927% for LONG and 0.718% for SHORT.

## What this says

1. Candle colour by itself is not a strong confirmation filter: even among the 289 events that met the tolerant gradual-trend definition, fewer than half of the first-hour candles matched the eventual trend direction on average.
2. The first five minutes were more directionally aligned (56.68% mean), but the share declined toward 44.08% over the full hour. An early burst of matching candles should not be mistaken for sustained directional control.
3. LONG and SHORT events had nearly identical first-hour directional-candle shares. The result does not support using a different candle-colour threshold for longs versus shorts.
4. A better research test is to combine candle direction with turnover expansion, path efficiency, open-interest change, taker buy/sell imbalance, and funding/crowding measures, all measured strictly as-of the breakout. The derivatives enrichment is still pending and has not produced results yet.

## Limitations

- The 289-event cohort is selected by a two-hour outcome label, so these figures describe the eventual winners and cannot be applied directly to all breakouts without a separate out-of-sample test.
- Events may overlap or repeat within the same market and day; they are not necessarily independent.
- The underlying market universe is the current top 200 USDT perpetuals by turnover, not a point-in-time historical universe.
- This is descriptive analysis over 14 days, not a validated trading strategy. Fees, spread, slippage, funding, and liquidation risk still matter.

Source data: `reports/daily_research/bitget_14d_gradual_event_details.jsonl`.

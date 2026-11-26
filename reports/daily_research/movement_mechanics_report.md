# Bitget movement mechanics: live microstructure event study

Generated UTC: 2026-11-26T02:25:55.024000+00:00
This is a forward-collected observational study. Historical order-book depth and recent public fills are not backfilled by these endpoints.
Universe: top 50 eligible online USDT perpetuals by current 24h turnover; existing candle scanner covers its wider universe.
Latest cycle: {"liquidation_records_in_collection_interval": 100, "liquidation_records_seen_in_recent_global_page": 100, "symbols_requested": 50, "symbols_with_book": 50, "symbols_with_fills": 50, "symbols_with_oi": 50, "timestamp_ms": 1795659955024, "timestamp_utc": "2026-11-26T02:25:55.024000+00:00", "trading_enabled": false}

## What is being measured
- Aggressive-flow proxy: Bitget-reported buy/sell side of the latest public fills, weighted by price × size. The side is a proxy; do not label it proven aggressor flow without exchange-side semantic validation.
- Liquidity withdrawal: change in opposing-side order-book notional within 0.5% of mid versus the prior collection snapshot. A snapshot is not proof of spoofing or cancellation intent.
- Position expansion: change in aggregate open interest since the prior snapshot. OI does not identify which side opened.
- Liquidation pressure: public platform liquidation records; Bitget documents buy as long liquidation and sell as short liquidation. The global endpoint returns only its latest page (up to 100), so coverage is incomplete.
- Outcome: direction-adjusted price return from the movement snapshot to the next available snapshot at least 8 minutes later (accepted up to 18 minutes).

## Event versus control cohorts
Event = absolute 5m candle return >= 0.50%; control = absolute 5m candle return <= 0.15%.
Events: {
  "observations": 67,
  "with_forward_outcome": 7,
  "median_forward_10m_directional_return_pct": -0.927453,
  "positive_forward_rate_pct": 28.57,
  "taker_aligned": {
    "count": 5,
    "median_forward_return_pct": -1.17771,
    "positive_forward_rate_pct": 20.0
  },
  "opposing_book_depth_withdrawal_15pct": {
    "count": 1,
    "median_forward_return_pct": -0.927453,
    "positive_forward_rate_pct": 0.0
  },
  "open_interest_increased": {
    "count": 4,
    "median_forward_return_pct": 0.611293,
    "positive_forward_rate_pct": 50.0
  },
  "aligned_liquidations_present": {
    "count": 2,
    "median_forward_return_pct": -1.686112,
    "positive_forward_rate_pct": 0.0
  },
  "two_or_more_fuels": {
    "count": 5,
    "median_forward_return_pct": -0.927453,
    "positive_forward_rate_pct": 20.0
  }
}
Controls: {
  "observations": 196,
  "with_forward_outcome": 28,
  "median_forward_10m_directional_return_pct": -0.212121,
  "positive_forward_rate_pct": 35.71,
  "taker_aligned": {
    "count": 12,
    "median_forward_return_pct": -0.253073,
    "positive_forward_rate_pct": 25.0
  },
  "opposing_book_depth_withdrawal_15pct": {
    "count": 11,
    "median_forward_return_pct": -0.218531,
    "positive_forward_rate_pct": 27.27
  },
  "open_interest_increased": {
    "count": 16,
    "median_forward_return_pct": -0.161014,
    "positive_forward_rate_pct": 43.75
  },
  "aligned_liquidations_present": {
    "count": 5,
    "median_forward_return_pct": -0.20571,
    "positive_forward_rate_pct": 20.0
  },
  "two_or_more_fuels": {
    "count": 12,
    "median_forward_return_pct": -0.246638,
    "positive_forward_rate_pct": 16.67
  }
}

## Interpretation limits
- First collection has no prior book/OI snapshot; liquidity withdrawal and OI change become measurable only after repeat samples.
- The 100-fill public endpoint is a recent rolling sample, not a complete fixed five-minute tape. Fill age and sample span are stored so stale samples can be excluded.
- The 100-record global liquidation page is not guaranteed to include every symbol or liquidation in the interval.
- Order-book depth is a displayed snapshot and may change or cancel; it is not executed volume.
- These are associations and forward observations, not causal proof or a profitable strategy. No orders are placed.
- Minimum useful sample: several days with repeated snapshots and adequate fill/book/OI coverage.

Raw snapshots: movement_mechanics_snapshots.jsonl
Latest structured result: movement_mechanics_latest.json

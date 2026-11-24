# Bitget movement mechanics: live microstructure event study

Generated UTC: 2026-11-24T12:54:36.073000+00:00
This is a forward-collected observational study. Historical order-book depth and recent public fills are not backfilled by these endpoints.
Universe: top 50 eligible online USDT perpetuals by current 24h turnover; existing candle scanner covers its wider universe.
Latest cycle: {"liquidation_records_in_collection_interval": 0, "liquidation_records_seen_in_recent_global_page": 100, "symbols_requested": 50, "symbols_with_book": 50, "symbols_with_fills": 50, "symbols_with_oi": 50, "timestamp_ms": 1795524876073, "timestamp_utc": "2026-11-24T12:54:36.073000+00:00", "trading_enabled": false}

## What is being measured
- Aggressive-flow proxy: Bitget-reported buy/sell side of the latest public fills, weighted by price × size. The side is a proxy; do not label it proven aggressor flow without exchange-side semantic validation.
- Liquidity withdrawal: change in opposing-side order-book notional within 0.5% of mid versus the prior collection snapshot. A snapshot is not proof of spoofing or cancellation intent.
- Position expansion: change in aggregate open interest since the prior snapshot. OI does not identify which side opened.
- Liquidation pressure: public platform liquidation records; Bitget documents buy as long liquidation and sell as short liquidation. The global endpoint returns only its latest page (up to 100), so coverage is incomplete.
- Outcome: direction-adjusted price return from the movement snapshot to the next available snapshot at least 8 minutes later (accepted up to 18 minutes).

## Event versus control cohorts
Event = absolute 5m candle return >= 0.50%; control = absolute 5m candle return <= 0.15%.
Events: {
  "observations": 17,
  "with_forward_outcome": 0,
  "median_forward_10m_directional_return_pct": null,
  "positive_forward_rate_pct": null,
  "taker_aligned": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "opposing_book_depth_withdrawal_15pct": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "open_interest_increased": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "aligned_liquidations_present": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "two_or_more_fuels": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  }
}
Controls: {
  "observations": 60,
  "with_forward_outcome": 0,
  "median_forward_10m_directional_return_pct": null,
  "positive_forward_rate_pct": null,
  "taker_aligned": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "opposing_book_depth_withdrawal_15pct": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "open_interest_increased": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "aligned_liquidations_present": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
  },
  "two_or_more_fuels": {
    "count": 0,
    "median_forward_return_pct": null,
    "positive_forward_rate_pct": null
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

# Bitget 14-day derivatives fuel enrichment

Generated UTC: 2026-11-24T10:01:52.557733+00:00
Events: 27254; symbols: 200

Only observations timestamped at or before the breakout are joined. OI/taker/long-short are accepted only when recent enough (30m/15m/30m); funding may be up to 10 days old because settlement intervals vary.
A missing match is reported as missing, never filled with a later observation.

## Coverage by source
{
  "successful_symbols": {
    "/api/v3/market/open-interest-history": 200,
    "/api/v3/market/futures-active-buy-sell": 200,
    "/api/v3/market/futures-long-short": 200,
    "/api/v3/market/history-fund-rate": 200
  },
  "symbol_errors": {
    "/api/v3/market/open-interest-history": 0,
    "/api/v3/market/futures-active-buy-sell": 0,
    "/api/v3/market/futures-long-short": 0,
    "/api/v3/market/history-fund-rate": 0
  }
}

## Event groups
{
  "GRADUAL_TREND": {
    "events": 191,
    "OI change %": {
      "n": 3,
      "median": -0.589019,
      "mean": -0.737101
    },
    "taker imbalance": {
      "n": 3,
      "median": -1.0,
      "mean": -0.520338
    },
    "long/short ratio": {
      "n": 3,
      "median": 1.2552,
      "mean": 1.1937
    },
    "funding rate": {
      "n": 183,
      "median": 5e-05,
      "mean": -0.000182
    },
    "OI matched": 3,
    "taker matched": 3,
    "long/short matched": 3,
    "funding matched": 183
  },
  "FAST_SPIKE": {
    "events": 324,
    "OI change %": {
      "n": 0,
      "median": null,
      "mean": null
    },
    "taker imbalance": {
      "n": 0,
      "median": null,
      "mean": null
    },
    "long/short ratio": {
      "n": 0,
      "median": null,
      "mean": null
    },
    "funding rate": {
      "n": 308,
      "median": 5e-05,
      "mean": -0.000431
    },
    "OI matched": 0,
    "taker matched": 0,
    "long/short matched": 0,
    "funding matched": 308
  },
  "FAILED_OR_WEAK": {
    "events": 26739,
    "OI change %": {
      "n": 23,
      "median": -0.144755,
      "mean": -0.244313
    },
    "taker imbalance": {
      "n": 29,
      "median": -0.413096,
      "mean": -0.229308
    },
    "long/short ratio": {
      "n": 37,
      "median": 1.4503,
      "mean": 1.667878
    },
    "funding rate": {
      "n": 26349,
      "median": 5e-05,
      "mean": -6.4e-05
    },
    "OI matched": 33,
    "taker matched": 29,
    "long/short matched": 37,
    "funding matched": 26349
  }
}

## Interpretation guardrails
- Open-interest increase means aggregate positions expanded; it does not identify whether longs or shorts initiated them.
- Taker imbalance is based on the API's buyVolume/sellVolume buckets; validate the endpoint's classification before treating it as aggressor-side flow.
- Long/short ratio is crowd positioning, not proof of new buying or selling.
- Funding is a positioning/carry context variable, not a directional signal by itself.
- Endpoint history depth may be shorter than the full 14-day candle window. Coverage counts expose this.
- This is observational research, not a causal test or trading recommendation.

Raw event-level joins: bitget_14d_derivatives_fuel_events.jsonl

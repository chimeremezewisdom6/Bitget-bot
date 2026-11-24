# Bitget 14-day derivatives fuel enrichment

Generated UTC: 2026-11-24T11:38:42.533118+00:00
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
    "events": 193,
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
      "n": 185,
      "median": 5e-05,
      "mean": -0.00018
    },
    "OI matched": 0,
    "taker matched": 0,
    "long/short matched": 0,
    "funding matched": 185
  },
  "FAST_SPIKE": {
    "events": 327,
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
      "n": 312,
      "median": 5e-05,
      "mean": -0.000428
    },
    "OI matched": 0,
    "taker matched": 0,
    "long/short matched": 0,
    "funding matched": 312
  },
  "FAILED_OR_WEAK": {
    "events": 26734,
    "OI change %": {
      "n": 11,
      "median": 0.112582,
      "mean": -0.226252
    },
    "taker imbalance": {
      "n": 11,
      "median": -0.285447,
      "mean": -0.186149
    },
    "long/short ratio": {
      "n": 22,
      "median": 1.4141,
      "mean": 1.684559
    },
    "funding rate": {
      "n": 26344,
      "median": 5e-05,
      "mean": -6.5e-05
    },
    "OI matched": 22,
    "taker matched": 11,
    "long/short matched": 22,
    "funding matched": 26344
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

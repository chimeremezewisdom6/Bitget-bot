# Bitget fuel attribution — event/control research\n\nGenerated UTC: 2026-11-24T08:23:18.911699+00:00\nWindow UTC: 2026-11-23T08:22:00+00:00 to 2026-11-24T08:22:00+00:00\nAuthenticated Bitget read: SUCCESS; permission: readonly; fee schedule: True\nUniverse: 200 top online crypto USDT perpetuals; symbols with >=1300 candles: 200/200; candles: 288000; fetch errors: 0\nBreakout candidates: 1801; gradual trends: 10; fast 4% spikes: 30\n\n## Labels and controls\nCandidate: closed 1m close beyond prior 60m high/low; measure next 120m without pre-selecting successful holds.\nGradual: holds breakout level for 120m, returns >=4%, and 2h move >=4x absolute first-10m move.\nFast spike: reaches >=4% but fails 4x rule. Failed/weak: all other breakout candidates.\nEarly features at 1/3/5/10/15/30m use only candles available by that horizon. Turnover vs previous 20m baseline.\n## 10-minute feature comparison\n| Feature | Gradual median | Controls median | Ratio |\n|---|---:|---:|---:|\n| turnover_vs_pre20 | 2.33532 | 1.71256 | 1.3636 |\n| directional_candle_share | 0.5 | 0.4 | 1.25 |\n| path_efficiency | 0.39444 | 0.36888 | 1.0693 |\n\n## Group counts\n{
  "GRADUAL_TREND": 10,
  "FAST_SPIKE": 30,
  "FAILED_OR_WEAK": 1761
}\n\n## Feature medians at all horizons\n{
  "1": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 1.0,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 1.0,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 1.0,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.25105,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.99984,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.24278,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 1.0,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 1.0,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 1.0,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.80803,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 7.2795,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 1.97197,
        "n": 10
      }
    }
  },
  "10": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 0.4,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.6,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.5,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.25365,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 3.14838,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.81229,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 0.35982,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.6559,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.39444,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.68523,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 6.83113,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 2.33532,
        "n": 10
      }
    }
  },
  "15": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 0.4,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.6,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.53333,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.25556,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 4.00388,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 1.26909,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 0.28133,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.50768,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.47108,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.63109,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 7.72558,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 2.20093,
        "n": 10
      }
    }
  },
  "3": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 0.66667,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.83333,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.66667,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.24969,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 2.43373,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.61251,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 0.81253,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.98431,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.68419,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.85691,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 11.11735,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 3.76668,
        "n": 10
      }
    }
  },
  "30": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 0.36667,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.53333,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.5,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.32908,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 4.91645,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 2.15481,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 0.19867,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.25351,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.33093,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.62182,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 5.05533,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 2.42356,
        "n": 10
      }
    }
  },
  "5": {
    "directional_candle_share": {
      "FAILED_OR_WEAK": {
        "median": 0.4,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.7,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.6,
        "n": 10
      }
    },
    "directional_return_pct": {
      "FAILED_OR_WEAK": {
        "median": 0.26059,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 2.90839,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.67883,
        "n": 10
      }
    },
    "path_efficiency": {
      "FAILED_OR_WEAK": {
        "median": 0.56965,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 0.75138,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 0.69743,
        "n": 10
      }
    },
    "turnover_vs_pre20": {
      "FAILED_OR_WEAK": {
        "median": 1.72265,
        "n": 1761
      },
      "FAST_SPIKE": {
        "median": 8.76878,
        "n": 30
      },
      "GRADUAL_TREND": {
        "median": 2.76144,
        "n": 10
      }
    }
  }
}\n\n## Historical open interest\nTimestamp-aligned OI events: 21/1801 across 200 symbols.\nAggregate OI does not identify whether longs or shorts opened. Missing timestamp-aligned history is null.\n## Causality assessment\nThis is an observational event/control comparison, not a randomized intervention. It cannot prove a feature caused a trend.\nA feature is more credible when it appears before later expansion and separates gradual trends from both failed-breakout and fast-spike controls.\nNo historical taker-side flow, funding or order-book values are invented. Current snapshots are not used as historical evidence.\nOne 24h sample is exploratory; confirm rankings with a multi-week time-separated test and transaction-cost assumptions.\nFull event rows: bitget_fuel_attribution_events.jsonl.
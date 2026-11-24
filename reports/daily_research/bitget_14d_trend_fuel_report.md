# Bitget 14-day trend fuel backtest

Window: 2026-11-10T11:20:00+00:00 to 2026-11-24T11:20:00+00:00
Authenticated read: SUCCESS; permission: readonly; fee schedule: True
Markets: 200; candles: 3991371; symbols with >=95% coverage: 197
Candidates: 27254; groups: {"GRADUAL_TREND": 193, "FAST_SPIKE": 327, "FAILED_OR_WEAK": 26734}
Strict gradual: 193; tolerant gradual: 299

Candidate: closed 1m close beyond previous 60m high/low. Outcomes measured over following 120m.
Gradual: >=4% direction-adjusted return, full 2h move at least 4x absolute first-10m move, and all 120 closes beyond breakout boundary.
Tolerant label permits three closes back through boundary. Pre-breakout features use candles before the breakout candle.
## Pre-breakout feature medians
JSON follows:
{
  "1": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.099157
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.0
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.0
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.0
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.030507
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.545239
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.030485
      }
    }
  },
  "3": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.060569
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.295858
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.053545
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.333333
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.666667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.938017
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.812541
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.999152
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.274154
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.71538
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.252338
      }
    }
  },
  "5": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.120919
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.492424
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.114972
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.4
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.4
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.610976
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.549945
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.698714
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.435415
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.778511
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.384075
      }
    }
  },
  "10": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.278508
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.65138
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.206655
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.3
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.5
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.474699
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.392926
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.460823
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.631676
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.828762
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.579758
      }
    }
  },
  "15": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.373878
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.736196
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.259067
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.333333
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.337759
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.28322
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.349444
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.766671
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.864491
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.688848
      }
    }
  },
  "30": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.532044
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.036546
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.362573
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.3
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.227605
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.178769
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.217925
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.916015
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.947249
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.89483
      }
    }
  },
  "60": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.691489
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.163529
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.384818
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.266667
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.283333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.139045
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.097969
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.113147
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.0
      }
    }
  }
}
## Post-breakout features (not advance predictors)
{
  "1": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.4158
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.990099
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.252506
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.0
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.0
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.198227
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 3.835683
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.536196
      }
    }
  },
  "3": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.571141
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.370826
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.241362
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.666667
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.666667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.998674
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.899895
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.83394
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.915111
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 3.464964
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.419542
      }
    }
  },
  "5": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.706964
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 1.637666
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.238305
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.6
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.4
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.842411
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.725321
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.555812
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.715323
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 3.170646
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.349524
      }
    }
  },
  "10": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.807985
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 2.489019
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.225394
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.5
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.541716
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.596053
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.350754
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.657946
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 3.082307
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.277213
      }
    }
  },
  "15": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.056466
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 2.748815
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.214143
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.466667
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.495814
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.447128
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.277627
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.421188
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 2.829586
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.264285
      }
    }
  },
  "30": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 1.849359
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 3.388682
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.208417
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.433333
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.533333
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.410958
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.306106
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.193199
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 2.636728
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 2.422193
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.26774
      }
    }
  },
  "60": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 3.589606
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 4.344328
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.204827
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.45
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.516667
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 0.333566
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 0.212388
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 0.135136
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 193,
        "median": 3.593527
      },
      "FAST_SPIKE": {
        "n": 327,
        "median": 2.214349
      },
      "FAILED_OR_WEAK": {
        "n": 26734,
        "median": 1.315543
      }
    }
  }
}
## Chronological splits
{
  "train_days_1_9": {
    "events": 17553,
    "gradual": 96,
    "spikes": 177,
    "failed": 17280
  },
  "validation_days_10_11": {
    "events": 3948,
    "gradual": 50,
    "spikes": 62,
    "failed": 3836
  },
  "test_days_12_14": {
    "events": 5753,
    "gradual": 47,
    "spikes": 88,
    "failed": 5618
  }
}
## Daily event counts
{
  "2026-11-10": {
    "FAILED_OR_WEAK": 987,
    "GRADUAL_TREND": 3,
    "FAST_SPIKE": 10
  },
  "2026-11-11": {
    "FAILED_OR_WEAK": 1929,
    "GRADUAL_TREND": 2,
    "FAST_SPIKE": 18
  },
  "2026-11-12": {
    "FAILED_OR_WEAK": 1919,
    "FAST_SPIKE": 17,
    "GRADUAL_TREND": 8
  },
  "2026-11-13": {
    "FAILED_OR_WEAK": 1910,
    "FAST_SPIKE": 20,
    "GRADUAL_TREND": 20
  },
  "2026-11-14": {
    "FAILED_OR_WEAK": 1886,
    "GRADUAL_TREND": 30,
    "FAST_SPIKE": 22
  },
  "2026-11-15": {
    "FAILED_OR_WEAK": 1878,
    "FAST_SPIKE": 20,
    "GRADUAL_TREND": 3
  },
  "2026-11-16": {
    "FAILED_OR_WEAK": 1981,
    "FAST_SPIKE": 18,
    "GRADUAL_TREND": 6
  },
  "2026-11-17": {
    "FAILED_OR_WEAK": 1907,
    "FAST_SPIKE": 20,
    "GRADUAL_TREND": 13
  },
  "2026-11-18": {
    "FAILED_OR_WEAK": 1974,
    "GRADUAL_TREND": 7,
    "FAST_SPIKE": 17
  },
  "2026-11-19": {
    "FAILED_OR_WEAK": 1906,
    "GRADUAL_TREND": 11,
    "FAST_SPIKE": 23
  },
  "2026-11-20": {
    "FAILED_OR_WEAK": 1939,
    "GRADUAL_TREND": 19,
    "FAST_SPIKE": 39
  },
  "2026-11-21": {
    "FAILED_OR_WEAK": 1893,
    "FAST_SPIKE": 28,
    "GRADUAL_TREND": 35
  },
  "2026-11-22": {
    "FAILED_OR_WEAK": 1942,
    "FAST_SPIKE": 18,
    "GRADUAL_TREND": 11
  },
  "2026-11-23": {
    "FAILED_OR_WEAK": 1921,
    "FAST_SPIKE": 46,
    "GRADUAL_TREND": 15
  },
  "2026-11-24": {
    "FAILED_OR_WEAK": 762,
    "FAST_SPIKE": 11,
    "GRADUAL_TREND": 10
  }
}
## Coverage
[
  {
    "symbol": "BTCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
    "errors": []
  },
  {
    "symbol": "ETHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "SOLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "XRPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "ZECUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "HYPEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "NEARUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "ENAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "PEPEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "MMTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 128,
    "errors": []
  },
  {
    "symbol": "EVAAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 130,
    "errors": []
  },
  {
    "symbol": "DOGEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "SUIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "BLESSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "WLDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "ADAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 127,
    "errors": []
  },
  {
    "symbol": "PIEVERSEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "PROMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "ELSAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "ARIAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
    "errors": []
  },
  {
    "symbol": "LISTAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "CYSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "UNIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "PUMPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "BNBUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "AKEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 129,
    "errors": []
  },
  {
    "symbol": "ARBUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "LINKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "AVAXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "TAOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "ACEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "INJUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 145,
    "errors": []
  },
  {
    "symbol": "ONDOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "APTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "TRUMPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "LTCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "AAVEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "BCHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "QNTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "XLMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "SKYUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "RENDERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "FILUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "XMRUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "ZROUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "FARTCOINUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "VVVUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "SHIBUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "JUPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ALGOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "INXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "DOSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "PENGUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "SAHARAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "ICNTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "MUBARAKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "DOTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 130,
    "errors": []
  },
  {
    "symbol": "FETUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "ATOMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "SEIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "TIAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "CRVUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "HBARUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "FLOCKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ASTERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "LSKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "IRYSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "ICPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "LUNCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "USDBRLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "PONSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "PIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "\u725b\u6765USDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "APRUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "DGAIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
    "errors": []
  },
  {
    "symbol": "MONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "ENSOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "WLFIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "LDOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "JCTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 128,
    "errors": []
  },
  {
    "symbol": "WIFUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "VIRTUALUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "CLSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 129,
    "errors": []
  },
  {
    "symbol": "BTWUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "USELESSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "NIGHTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "ETCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "TRXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "ELICEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 130,
    "errors": []
  },
  {
    "symbol": "XPLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "SKYAIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "VELVETUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "SANDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "CTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 145,
    "errors": []
  },
  {
    "symbol": "CYBERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "PYTHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "SAPIENUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "ONEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "RPLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 116,
    "errors": []
  },
  {
    "symbol": "ETHFIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "KASUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "CHIPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "BGBUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "INITUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "HUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "GRAMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "LITUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "CROSSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "UNITASUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "BABYUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "IDOLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "OPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "HUMAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "REUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "BREVUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "ORDIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "PROSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "BEATUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "GALAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "ERAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "AMDLUSDT",
    "candles": 5719,
    "coverage_pct": 28.368,
    "events": 39,
    "errors": []
  },
  {
    "symbol": "AEROUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "MARSCOINUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "STRKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "MEGAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "PLUMEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "CAPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "CFGUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "PIPPINUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "MORPHOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "BANKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "DEXEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "STXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "SQDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
    "errors": []
  },
  {
    "symbol": "RAYUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "1000BONKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "MAGMAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "ARUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "JTOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "GWEIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "QUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ENSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "USUALUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 130,
    "errors": []
  },
  {
    "symbol": "MYXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "NAORISUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "KAITOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "SOONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "PENDLEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "GRASSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "BOMEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "ONGUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "FLOKIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "BARDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "0GUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "IOSTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "UAIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
    "errors": []
  },
  {
    "symbol": "\u9f99\u867eUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "LABUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ORCAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "NEMUSDT",
    "candles": 8410,
    "coverage_pct": 41.716,
    "events": 51,
    "errors": []
  },
  {
    "symbol": "ALLOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "RAREUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
    "errors": []
  },
  {
    "symbol": "KERNELUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "ARXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "AXISUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "FCXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 119,
    "errors": []
  },
  {
    "symbol": "MSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "GRVTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "KGENUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "SPACEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
    "errors": []
  },
  {
    "symbol": "KITEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "POWERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "BLURUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "GPSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
    "errors": []
  },
  {
    "symbol": "ACUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
    "errors": []
  },
  {
    "symbol": "KUAISHOUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 126,
    "errors": []
  },
  {
    "symbol": "PHAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ARKMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 130,
    "errors": []
  },
  {
    "symbol": "BEAMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "PBRUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "NILUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "EGLDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "CPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
    "errors": []
  },
  {
    "symbol": "SPKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "ATUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "MEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "USDJPYUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
    "errors": []
  },
  {
    "symbol": "POLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "RIVERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "COOKIEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "DASHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
    "errors": []
  },
  {
    "symbol": "METUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "JNJUSDT",
    "candles": 5722,
    "coverage_pct": 28.383,
    "events": 37,
    "errors": []
  },
  {
    "symbol": "LAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "FFUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "EIGENUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "BERAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "AEONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "RAVEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "ZENUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  }
]
## Limitations
- Current top-200 universe creates survivorship bias; historical listings are not reconstructed.
- Observational associations do not prove causality.
- Pre-breakout features are separate from post-breakout features.
- No historical taker-side flow, funding history or historical order-book depth is claimed.
- Aggregate OI is not used to infer which side opened positions.
- Fee schedule alone is not a complete execution-cost model; spread, slippage and funding need historical data.
- Strict label requires all 120 closes beyond boundary; tolerant label permits three retests.
- 14 days is exploratory; extend out-of-sample before treating any pattern as predictive.
Raw event rows: bitget_14d_trend_fuel_events.jsonl
Gradual event details with first-hour candle colours: bitget_14d_gradual_event_details.jsonl

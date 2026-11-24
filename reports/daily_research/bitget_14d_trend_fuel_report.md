# Bitget 14-day trend fuel backtest

Window: 2026-11-10T08:45:00+00:00 to 2026-11-24T08:45:00+00:00
Authenticated read: SUCCESS; permission: readonly; fee schedule: True
Markets: 200; candles: 4005499; symbols with >=95% coverage: 198
Candidates: 27331; groups: {"GRADUAL_TREND": 189, "FAST_SPIKE": 326, "FAILED_OR_WEAK": 26816}
Strict gradual: 189; tolerant gradual: 290

Candidate: closed 1m close beyond previous 60m high/low. Outcomes measured over following 120m.
Gradual: >=4% direction-adjusted return, full 2h move at least 4x absolute first-10m move, and all 120 closes beyond breakout boundary.
Tolerant label permits three closes back through boundary. Pre-breakout features use candles before the breakout candle.
## Pre-breakout feature medians
JSON follows:
{
  "1": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.103083
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.0
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.0
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.0
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.028054
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.558493
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.02893
      }
    }
  },
  "3": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.054982
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.296698
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.052602
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.333333
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.666667
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.902484
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.81872
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.999164
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.25945
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.720461
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.251945
      }
    }
  },
  "5": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.120919
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.489459
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.113786
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.4
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.4
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.600914
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.544765
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.704556
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.401624
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.776282
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.384965
      }
    }
  },
  "10": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.277367
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.649839
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.204325
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.3
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.5
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.473214
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.388386
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.462194
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.62844
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.828099
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.581755
      }
    }
  },
  "15": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.375626
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.734028
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.255977
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.333333
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.343349
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.280254
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.351065
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.757766
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.86465
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.690953
      }
    }
  },
  "30": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.529501
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.987327
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.359523
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.3
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.229499
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.178006
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.219065
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.893959
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.941077
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.896103
      }
    }
  },
  "60": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.665716
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.183884
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.377033
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.266667
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.466667
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.283333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.137669
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.097969
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.11264
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
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
        "n": 189,
        "median": 0.413223
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.991232
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.24989
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.0
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.0
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.0
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.0
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.169759
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 3.875007
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.554505
      }
    }
  },
  "3": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.570776
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.344165
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.239234
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.666667
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.666667
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.99875
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.893682
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.839601
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.915111
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 3.500662
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.425374
      }
    }
  },
  "5": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.701872
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 1.630956
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.235869
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.6
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.4
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.877365
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.723764
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.559885
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.735603
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 3.172494
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.354781
      }
    }
  },
  "10": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.807985
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 2.485291
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.222541
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.5
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.54619
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.592994
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.35281
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.712365
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 3.104482
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.276476
      }
    }
  },
  "15": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.067821
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 2.724303
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.210084
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.466667
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.6
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.333333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.499274
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.445837
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.278052
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.438363
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 2.805977
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.264178
      }
    }
  },
  "30": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 1.858887
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 3.392806
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.200162
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.433333
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.533333
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.3
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.410958
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.308231
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.193508
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 2.649127
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 2.415234
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.266709
      }
    }
  },
  "60": {
    "directional_return_pct": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 3.628231
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 4.341067
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.193467
      }
    },
    "directional_candle_share": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.45
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.5
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.283333
      }
    },
    "path_efficiency": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 0.333566
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 0.212041
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 0.135167
      }
    },
    "turnover_vs_pre60": {
      "GRADUAL_TREND": {
        "n": 189,
        "median": 3.690366
      },
      "FAST_SPIKE": {
        "n": 326,
        "median": 2.118301
      },
      "FAILED_OR_WEAK": {
        "n": 26816,
        "median": 1.308615
      }
    }
  }
}
## Chronological splits
{
  "train_days_1_9": {
    "events": 17637,
    "gradual": 96,
    "spikes": 173,
    "failed": 17368
  },
  "validation_days_10_11": {
    "events": 3968,
    "gradual": 50,
    "spikes": 63,
    "failed": 3855
  },
  "test_days_12_14": {
    "events": 5726,
    "gradual": 43,
    "spikes": 90,
    "failed": 5593
  }
}
## Daily event counts
{
  "2026-11-10": {
    "FAILED_OR_WEAK": 1202,
    "FAST_SPIKE": 13,
    "GRADUAL_TREND": 2
  },
  "2026-11-11": {
    "FAILED_OR_WEAK": 1937,
    "GRADUAL_TREND": 3,
    "FAST_SPIKE": 18
  },
  "2026-11-12": {
    "FAILED_OR_WEAK": 1927,
    "FAST_SPIKE": 17,
    "GRADUAL_TREND": 8
  },
  "2026-11-13": {
    "FAILED_OR_WEAK": 1923,
    "FAST_SPIKE": 19,
    "GRADUAL_TREND": 20
  },
  "2026-11-14": {
    "FAILED_OR_WEAK": 1895,
    "GRADUAL_TREND": 30,
    "FAST_SPIKE": 22
  },
  "2026-11-15": {
    "FAILED_OR_WEAK": 1884,
    "FAST_SPIKE": 20,
    "GRADUAL_TREND": 3
  },
  "2026-11-16": {
    "FAILED_OR_WEAK": 1990,
    "FAST_SPIKE": 18,
    "GRADUAL_TREND": 6
  },
  "2026-11-17": {
    "FAILED_OR_WEAK": 1918,
    "FAST_SPIKE": 19,
    "GRADUAL_TREND": 13
  },
  "2026-11-18": {
    "FAILED_OR_WEAK": 1987,
    "GRADUAL_TREND": 8,
    "FAST_SPIKE": 16
  },
  "2026-11-19": {
    "FAILED_OR_WEAK": 1914,
    "GRADUAL_TREND": 10,
    "FAST_SPIKE": 23
  },
  "2026-11-20": {
    "FAILED_OR_WEAK": 1944,
    "GRADUAL_TREND": 19,
    "FAST_SPIKE": 39
  },
  "2026-11-21": {
    "FAILED_OR_WEAK": 1893,
    "FAST_SPIKE": 28,
    "GRADUAL_TREND": 35
  },
  "2026-11-22": {
    "FAILED_OR_WEAK": 1938,
    "FAST_SPIKE": 18,
    "GRADUAL_TREND": 11
  },
  "2026-11-23": {
    "FAILED_OR_WEAK": 1922,
    "FAST_SPIKE": 46,
    "GRADUAL_TREND": 15
  },
  "2026-11-24": {
    "FAILED_OR_WEAK": 542,
    "FAST_SPIKE": 10,
    "GRADUAL_TREND": 6
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
    "events": 141,
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
    "events": 135,
    "errors": []
  },
  {
    "symbol": "EVAAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
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
    "symbol": "PROMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
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
    "symbol": "ELSAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
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
    "symbol": "WLDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "CYSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "LISTAUSDT",
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
    "symbol": "TAOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "SKYUSDT",
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
    "symbol": "QNTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "XLMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
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
    "symbol": "RENDERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "JUPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "DOSUSDT",
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
    "symbol": "INXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
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
    "symbol": "ICNTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "TIAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "SAHARAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
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
    "symbol": "SEIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "CRVUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "ASTERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
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
    "symbol": "DGAIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
    "errors": []
  },
  {
    "symbol": "HUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "IRYSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
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
    "symbol": "\u725b\u6765USDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
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
    "symbol": "APRUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "LUNCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "PIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "MONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
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
    "symbol": "TRXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "BTWUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
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
    "symbol": "NIGHTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "VELVETUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "VIRTUALUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "CTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 145,
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
    "symbol": "ETCUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "events": 140,
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
    "symbol": "SANDUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
    "errors": []
  },
  {
    "symbol": "SAPIENUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
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
    "symbol": "ETHFIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 144,
    "errors": []
  },
  {
    "symbol": "PYTHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "RPLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 115,
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
    "symbol": "XPLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "LITUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "UNITASUSDT",
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
    "symbol": "OPUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "GALAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "HUMAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "ERAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "BEATUSDT",
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
    "symbol": "REUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
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
    "symbol": "CFGUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
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
    "symbol": "PLUMEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
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
    "symbol": "AMDLUSDT",
    "candles": 5564,
    "coverage_pct": 27.599,
    "events": 38,
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
    "symbol": "MARSCOINUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
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
    "symbol": "DEXEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "MORPHOUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
    "errors": []
  },
  {
    "symbol": "QUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
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
    "symbol": "BANKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
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
    "symbol": "STXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "GWEIUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
    "errors": []
  },
  {
    "symbol": "USUALUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 129,
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
    "symbol": "USDJPYUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 132,
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
    "symbol": "ENSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "RAREUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
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
    "symbol": "MYXUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "NAORISUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 135,
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
    "symbol": "SOONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
    "errors": []
  },
  {
    "symbol": "ONGUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 145,
    "errors": []
  },
  {
    "symbol": "MSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 133,
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
    "symbol": "POWERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "GRASSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "LABUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "NEMUSDT",
    "candles": 8255,
    "coverage_pct": 40.947,
    "events": 50,
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
    "symbol": "BOMEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "ALLOUSDT",
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
    "symbol": "IOSTUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "FLOKIUSDT",
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
    "symbol": "AXISUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 137,
    "errors": []
  },
  {
    "symbol": "KERNELUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
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
    "symbol": "NILUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 142,
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
    "symbol": "ACUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 131,
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
    "symbol": "GPSUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 134,
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
    "symbol": "KUAISHOUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 125,
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
    "symbol": "PHAUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
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
    "symbol": "KITEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "BEAMUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "POLUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
    "errors": []
  },
  {
    "symbol": "EDGEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "DASHUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 143,
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
    "symbol": "AEONUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 138,
    "errors": []
  },
  {
    "symbol": "CSTOCKUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 128,
    "errors": []
  },
  {
    "symbol": "NUUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 129,
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
    "symbol": "RIVERUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "MAGICUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 141,
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
    "symbol": "MEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 140,
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
    "symbol": "ATUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 136,
    "errors": []
  },
  {
    "symbol": "PEOPLEUSDT",
    "candles": 20160,
    "coverage_pct": 100.0,
    "events": 139,
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

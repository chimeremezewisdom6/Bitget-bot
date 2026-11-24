# Bitget 60-minute breakout impact and duration study

Generated UTC: 2026-11-24T11:35:04.359511+00:00
Window: 2026-11-10T11:26:00+00:00 to 2026-11-24T11:26:00+00:00
Markets: 200; breakouts: 14884; controls: 16431
Markets with >=95% candle coverage: 197

## LONG
| Horizon | Breakout median return | Breakout positive rate | Still above boundary | Control median return | Breakout minus control |
|---:|---:|---:|---:|---:|---:|
| 5m | 0.0% | 40.072% | 55.731% | 0.0% | 0% |
| 10m | 0.0% | 42.665% | 43.954% | -0.03204% | 0.03204% |
| 15m | -0.027155% | 42.622% | 36.834% | -0.048108% | 0.020953% |
| 30m | -0.049152% | 44.011% | 26.519% | -0.073388% | 0.024236% |
| 60m | -0.076395% | 44.04% | 18.926% | -0.103974% | 0.027579% |
| 120m | -0.175277% | 42.45% | 12.751% | -0.131711% | -0.043566% |
| 240m | -0.275141% | 41.791% | 8.467% | -0.186887% | -0.088254% |

Duration median (capped at 240m): 8.0 minutes
Mean duration (capped at 240m): 41.315 minutes
Still beyond boundary at 240m: 8.467%
Median MFE: 1.113212%; median MAE: -1.450963%

## SHORT
| Horizon | Breakout median return | Breakout positive rate | Still below boundary | Control median return | Breakout minus control |
|---:|---:|---:|---:|---:|---:|
| 5m | -0.0% | 38.778% | 53.897% | -0.0% | 0% |
| 10m | -0.0% | 41.903% | 42.055% | -0.0% | 0% |
| 15m | -0.018908% | 43.332% | 35.109% | -0.0% | -0.018908% |
| 30m | -0.015634% | 46.318% | 25.645% | 0.024105% | -0.039739% |
| 60m | -0.0% | 48.861% | 18.94% | -0.0% | 0% |
| 120m | -0.020925% | 48.33% | 13.79% | -0.038239% | 0.017314% |
| 240m | 0.082631% | 51.569% | 10.4% | 0.086237% | -0.003606% |

Duration median (capped at 240m): 7.0 minutes
Mean duration (capped at 240m): 42.864 minutes
Still beyond boundary at 240m: 10.4%
Median MFE: 1.314191%; median MAE: -1.192146%

## Method and limitations
- This is observational association, not proof that the breakout caused the move.
- The control group is a transparent non-breakout baseline, not a randomized experiment.
- Current top-200 universe creates survivorship bias; historical listings are not reconstructed.
- Events without a complete 240-minute future window are excluded.
- Duration is capped/right-censored at 240 minutes; longer duration requires a longer study horizon.
- A 1m close back inside the boundary counts as a failed hold even if price later re-breaks.
- No taker flow, OI, funding, liquidation, spread, or slippage is included in this price-impact study.

Raw events: bitget_60m_breakout_impact_events.jsonl
Control windows: bitget_60m_breakout_control_windows.jsonl

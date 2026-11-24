# Bitget authenticated 24-hour genuine-trend backtest

- Generated UTC: 2026-11-24T06:45:43.990131+00:00
- Window UTC: 2026-11-23T06:45:00+00:00 to 2026-11-24T06:45:00+00:00
- Bitget API key authentication: SUCCESS
- Key permission type: readonly
- Account fee schedule: AVAILABLE
- Access scope: Signed account-info and fee-rate reads only; no balances, positions, orders, or withdrawals.
- Universe: top 200 online crypto USDT perpetuals by 24h turnover.
- Coverage: 200/200 symbols; 288,000 closed 1m candles; 0 fetch errors.
- Qualifying gradual trends: 0 (LONG 0, SHORT 0).

## Exact trend rules
1. A closed 1m candle closes above the previous 60 candles' highest high (LONG) or below their lowest low (SHORT).
2. Every subsequent closed 1m candle remains outside that breakout level for 120 complete minutes.
3. Direction-adjusted net movement from breakout close to the 120th-minute close is at least 4%.
4. The 120m directional move is at least 4 times the largest same-direction move in ANY rolling 10m window during the 120 minutes. Each 10m window uses its first candle open and tenth candle close.
5. LONG and SHORT are evaluated separately; gaps and incomplete candles invalidate a sample.

## Aggregate findings
- No events passed all rules.



## What the data says fuels the move
- Persistence: 120m breakout-level hold, direction-matching candle counts, and maximum adverse/favorable excursion.
- Participation: first-10m and first-30m quote-turnover acceleration versus the 20m before the breakout.
- Historical open interest: reported only when Bitget's returned 5m observations cover both event boundaries; otherwise left blank.
- Funding and order book: current snapshots for qualifying symbols only. They are not falsely described as historical causes.
- Aggressive buyer/seller dominance: not inferred from OHLCV candles; no unsupported taker-side conclusion.

## Qualifying events
| Symbol | Side | Start UTC | 2h move % | First 10m % | Fastest 10m % | Ratio | 15m aligned | 120m aligned | First 10m turnover x | Historical OI % |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|

## Per-coin coverage
| Symbol | Candles | Trends | LONG | SHORT | Status |
|---|---:|---:|---:|---:|---|
| BTCUSDT | 1440 | 0 | 0 | 0 | OK |
| ETHUSDT | 1440 | 0 | 0 | 0 | OK |
| SOLUSDT | 1440 | 0 | 0 | 0 | OK |
| XRPUSDT | 1440 | 0 | 0 | 0 | OK |
| ZECUSDT | 1440 | 0 | 0 | 0 | OK |
| HYPEUSDT | 1440 | 0 | 0 | 0 | OK |
| NEARUSDT | 1440 | 0 | 0 | 0 | OK |
| ENAUSDT | 1440 | 0 | 0 | 0 | OK |
| EVAAUSDT | 1440 | 0 | 0 | 0 | OK |
| PEPEUSDT | 1440 | 0 | 0 | 0 | OK |
| DOGEUSDT | 1440 | 0 | 0 | 0 | OK |
| SUIUSDT | 1440 | 0 | 0 | 0 | OK |
| MMTUSDT | 1440 | 0 | 0 | 0 | OK |
| PIEVERSEUSDT | 1440 | 0 | 0 | 0 | OK |
| ELSAUSDT | 1440 | 0 | 0 | 0 | OK |
| BLESSUSDT | 1440 | 0 | 0 | 0 | OK |
| PROMUSDT | 1440 | 0 | 0 | 0 | OK |
| ADAUSDT | 1440 | 0 | 0 | 0 | OK |
| ARIAUSDT | 1440 | 0 | 0 | 0 | OK |
| WLDUSDT | 1440 | 0 | 0 | 0 | OK |
| CYSUSDT | 1440 | 0 | 0 | 0 | OK |
| PUMPUSDT | 1440 | 0 | 0 | 0 | OK |
| UNIUSDT | 1440 | 0 | 0 | 0 | OK |
| BNBUSDT | 1440 | 0 | 0 | 0 | OK |
| AKEUSDT | 1440 | 0 | 0 | 0 | OK |
| ARBUSDT | 1440 | 0 | 0 | 0 | OK |
| LINKUSDT | 1440 | 0 | 0 | 0 | OK |
| ACEUSDT | 1440 | 0 | 0 | 0 | OK |
| INJUSDT | 1440 | 0 | 0 | 0 | OK |
| LISTAUSDT | 1440 | 0 | 0 | 0 | OK |
| TAOUSDT | 1440 | 0 | 0 | 0 | OK |
| AVAXUSDT | 1440 | 0 | 0 | 0 | OK |
| APTUSDT | 1440 | 0 | 0 | 0 | OK |
| ONDOUSDT | 1440 | 0 | 0 | 0 | OK |
| TRUMPUSDT | 1440 | 0 | 0 | 0 | OK |
| AAVEUSDT | 1440 | 0 | 0 | 0 | OK |
| SKYUSDT | 1440 | 0 | 0 | 0 | OK |
| LTCUSDT | 1440 | 0 | 0 | 0 | OK |
| QNTUSDT | 1440 | 0 | 0 | 0 | OK |
| BCHUSDT | 1440 | 0 | 0 | 0 | OK |
| XLMUSDT | 1440 | 0 | 0 | 0 | OK |
| JUPUSDT | 1440 | 0 | 0 | 0 | OK |
| XMRUSDT | 1440 | 0 | 0 | 0 | OK |
| FILUSDT | 1440 | 0 | 0 | 0 | OK |
| FARTCOINUSDT | 1440 | 0 | 0 | 0 | OK |
| ALGOUSDT | 1440 | 0 | 0 | 0 | OK |
| VVVUSDT | 1440 | 0 | 0 | 0 | OK |
| SHIBUSDT | 1440 | 0 | 0 | 0 | OK |
| ZROUSDT | 1440 | 0 | 0 | 0 | OK |
| RENDERUSDT | 1440 | 0 | 0 | 0 | OK |
| DOSUSDT | 1440 | 0 | 0 | 0 | OK |
| MUBARAKUSDT | 1440 | 0 | 0 | 0 | OK |
| FETUSDT | 1440 | 0 | 0 | 0 | OK |
| DOTUSDT | 1440 | 0 | 0 | 0 | OK |
| ATOMUSDT | 1440 | 0 | 0 | 0 | OK |
| ICNTUSDT | 1440 | 0 | 0 | 0 | OK |
| PENGUUSDT | 1440 | 0 | 0 | 0 | OK |
| INXUSDT | 1440 | 0 | 0 | 0 | OK |
| ASTERUSDT | 1440 | 0 | 0 | 0 | OK |
| HUSDT | 1440 | 0 | 0 | 0 | OK |
| LSKUSDT | 1440 | 0 | 0 | 0 | OK |
| SEIUSDT | 1440 | 0 | 0 | 0 | OK |
| TIAUSDT | 1440 | 0 | 0 | 0 | OK |
| DGAIUSDT | 1440 | 0 | 0 | 0 | OK |
| FLOCKUSDT | 1440 | 0 | 0 | 0 | OK |
| HBARUSDT | 1440 | 0 | 0 | 0 | OK |
| ICPUSDT | 1440 | 0 | 0 | 0 | OK |
| USDBRLUSDT | 1440 | 0 | 0 | 0 | OK |
| SAHARAUSDT | 1440 | 0 | 0 | 0 | OK |
| CRVUSDT | 1440 | 0 | 0 | 0 | OK |
| IRYSUSDT | 1440 | 0 | 0 | 0 | OK |
| GRAMUSDT | 1440 | 0 | 0 | 0 | OK |
| 牛来USDT | 1440 | 0 | 0 | 0 | OK |
| PONSUSDT | 1440 | 0 | 0 | 0 | OK |
| ENSOUSDT | 1440 | 0 | 0 | 0 | OK |
| JCTUSDT | 1440 | 0 | 0 | 0 | OK |
| IDOLUSDT | 1440 | 0 | 0 | 0 | OK |
| PIUSDT | 1440 | 0 | 0 | 0 | OK |
| WLFIUSDT | 1440 | 0 | 0 | 0 | OK |
| CYBERUSDT | 1440 | 0 | 0 | 0 | OK |
| APRUSDT | 1440 | 0 | 0 | 0 | OK |
| NIGHTUSDT | 1440 | 0 | 0 | 0 | OK |
| BTWUSDT | 1440 | 0 | 0 | 0 | OK |
| LDOUSDT | 1440 | 0 | 0 | 0 | OK |
| MONUSDT | 1440 | 0 | 0 | 0 | OK |
| TRXUSDT | 1440 | 0 | 0 | 0 | OK |
| USDJPYUSDT | 1440 | 0 | 0 | 0 | OK |
| VELVETUSDT | 1440 | 0 | 0 | 0 | OK |
| KASUSDT | 1440 | 0 | 0 | 0 | OK |
| WIFUSDT | 1440 | 0 | 0 | 0 | OK |
| CTUSDT | 1440 | 0 | 0 | 0 | OK |
| USELESSUSDT | 1440 | 0 | 0 | 0 | OK |
| ELICEUSDT | 1440 | 0 | 0 | 0 | OK |
| CLSUSDT | 1440 | 0 | 0 | 0 | OK |
| UNITASUSDT | 1440 | 0 | 0 | 0 | OK |
| VIRTUALUSDT | 1440 | 0 | 0 | 0 | OK |
| LUNCUSDT | 1440 | 0 | 0 | 0 | OK |
| ETCUSDT | 1440 | 0 | 0 | 0 | OK |
| SANDUSDT | 1440 | 0 | 0 | 0 | OK |
| SAPIENUSDT | 1440 | 0 | 0 | 0 | OK |
| ETHFIUSDT | 1440 | 0 | 0 | 0 | OK |
| ONEUSDT | 1440 | 0 | 0 | 0 | OK |
| CHIPUSDT | 1440 | 0 | 0 | 0 | OK |
| PYTHUSDT | 1440 | 0 | 0 | 0 | OK |
| XPLUSDT | 1440 | 0 | 0 | 0 | OK |
| BGBUSDT | 1440 | 0 | 0 | 0 | OK |
| LITUSDT | 1440 | 0 | 0 | 0 | OK |
| RPLUSDT | 1440 | 0 | 0 | 0 | OK |
| INITUSDT | 1440 | 0 | 0 | 0 | OK |
| CROSSUSDT | 1440 | 0 | 0 | 0 | OK |
| SKYAIUSDT | 1440 | 0 | 0 | 0 | OK |
| OPUSDT | 1440 | 0 | 0 | 0 | OK |
| ERAUSDT | 1440 | 0 | 0 | 0 | OK |
| GALAUSDT | 1440 | 0 | 0 | 0 | OK |
| ORDIUSDT | 1440 | 0 | 0 | 0 | OK |
| BEATUSDT | 1440 | 0 | 0 | 0 | OK |
| PIPPINUSDT | 1440 | 0 | 0 | 0 | OK |
| BREVUSDT | 1440 | 0 | 0 | 0 | OK |
| AEROUSDT | 1440 | 0 | 0 | 0 | OK |
| AMDLUSDT | 1440 | 0 | 0 | 0 | OK |
| HUMAUSDT | 1440 | 0 | 0 | 0 | OK |
| CFGUSDT | 1440 | 0 | 0 | 0 | OK |
| STRKUSDT | 1440 | 0 | 0 | 0 | OK |
| QUSDT | 1440 | 0 | 0 | 0 | OK |
| REUSDT | 1440 | 0 | 0 | 0 | OK |
| MEGAUSDT | 1440 | 0 | 0 | 0 | OK |
| DEXEUSDT | 1440 | 0 | 0 | 0 | OK |
| 1000BONKUSDT | 1440 | 0 | 0 | 0 | OK |
| MAGMAUSDT | 1440 | 0 | 0 | 0 | OK |
| PLUMEUSDT | 1440 | 0 | 0 | 0 | OK |
| MORPHOUSDT | 1440 | 0 | 0 | 0 | OK |
| USUALUSDT | 1440 | 0 | 0 | 0 | OK |
| CAPUSDT | 1440 | 0 | 0 | 0 | OK |
| RAREUSDT | 1440 | 0 | 0 | 0 | OK |
| BANKUSDT | 1440 | 0 | 0 | 0 | OK |
| MARSCOINUSDT | 1440 | 0 | 0 | 0 | OK |
| RAYUSDT | 1440 | 0 | 0 | 0 | OK |
| STXUSDT | 1440 | 0 | 0 | 0 | OK |
| SQDUSDT | 1440 | 0 | 0 | 0 | OK |
| ARUSDT | 1440 | 0 | 0 | 0 | OK |
| MYXUSDT | 1440 | 0 | 0 | 0 | OK |
| GWEIUSDT | 1440 | 0 | 0 | 0 | OK |
| ENSUSDT | 1440 | 0 | 0 | 0 | OK |
| JTOUSDT | 1440 | 0 | 0 | 0 | OK |
| PENDLEUSDT | 1440 | 0 | 0 | 0 | OK |
| NILUSDT | 1440 | 0 | 0 | 0 | OK |
| KAITOUSDT | 1440 | 0 | 0 | 0 | OK |
| NAORISUSDT | 1440 | 0 | 0 | 0 | OK |
| SOONUSDT | 1440 | 0 | 0 | 0 | OK |
| POWERUSDT | 1440 | 0 | 0 | 0 | OK |
| BLURUSDT | 1440 | 0 | 0 | 0 | OK |
| FCXUSDT | 1440 | 0 | 0 | 0 | OK |
| KGENUSDT | 1440 | 0 | 0 | 0 | OK |
| GRASSUSDT | 1440 | 0 | 0 | 0 | OK |
| MSUSDT | 1440 | 0 | 0 | 0 | OK |
| BARDUSDT | 1440 | 0 | 0 | 0 | OK |
| GRVTUSDT | 1440 | 0 | 0 | 0 | OK |
| BOMEUSDT | 1440 | 0 | 0 | 0 | OK |
| BABYUSDT | 1440 | 0 | 0 | 0 | OK |
| LABUSDT | 1440 | 0 | 0 | 0 | OK |
| AXISUSDT | 1440 | 0 | 0 | 0 | OK |
| IOSTUSDT | 1440 | 0 | 0 | 0 | OK |
| NEMUSDT | 1440 | 0 | 0 | 0 | OK |
| UAIUSDT | 1440 | 0 | 0 | 0 | OK |
| CPUSDT | 1440 | 0 | 0 | 0 | OK |
| ACUUSDT | 1440 | 0 | 0 | 0 | OK |
| ALLOUSDT | 1440 | 0 | 0 | 0 | OK |
| FLOKIUSDT | 1440 | 0 | 0 | 0 | OK |
| BEAMUSDT | 1440 | 0 | 0 | 0 | OK |
| 0GUSDT | 1440 | 0 | 0 | 0 | OK |
| ARXUSDT | 1440 | 0 | 0 | 0 | OK |
| BERAUSDT | 1440 | 0 | 0 | 0 | OK |
| GPSUSDT | 1440 | 0 | 0 | 0 | OK |
| KUAISHOUUSDT | 1440 | 0 | 0 | 0 | OK |
| ONGUSDT | 1440 | 0 | 0 | 0 | OK |
| ORCAUSDT | 1440 | 0 | 0 | 0 | OK |
| PBRUSDT | 1440 | 0 | 0 | 0 | OK |
| METUSDT | 1440 | 0 | 0 | 0 | OK |
| SPKUSDT | 1440 | 0 | 0 | 0 | OK |
| KITEUSDT | 1440 | 0 | 0 | 0 | OK |
| ARKMUSDT | 1440 | 0 | 0 | 0 | OK |
| KERNELUSDT | 1440 | 0 | 0 | 0 | OK |
| NUUSDT | 1440 | 0 | 0 | 0 | OK |
| DASHUSDT | 1440 | 0 | 0 | 0 | OK |
| PHAUSDT | 1440 | 0 | 0 | 0 | OK |
| POLUSDT | 1440 | 0 | 0 | 0 | OK |
| CSTOCKUSDT | 1440 | 0 | 0 | 0 | OK |
| EDGEUSDT | 1440 | 0 | 0 | 0 | OK |
| MAGICUSDT | 1440 | 0 | 0 | 0 | OK |
| COOKIEUSDT | 1440 | 0 | 0 | 0 | OK |
| LAUSDT | 1440 | 0 | 0 | 0 | OK |
| RIVERUSDT | 1440 | 0 | 0 | 0 | OK |
| GRTUSDT | 1440 | 0 | 0 | 0 | OK |
| EIGENUSDT | 1440 | 0 | 0 | 0 | OK |
| RAVEUSDT | 1440 | 0 | 0 | 0 | OK |
| ATUSDT | 1440 | 0 | 0 | 0 | OK |
| ZESTUSDT | 1440 | 0 | 0 | 0 | OK |
| PEOPLEUSDT | 1440 | 0 | 0 | 0 | OK |
| OPGUSDT | 1440 | 0 | 0 | 0 | OK |
| UBUSDT | 1440 | 0 | 0 | 0 | OK |

## Limitations
- Historical research only; not current entry signals or a profitability claim.
- Breakout/hold is a defined proxy and can miss trends without a 60m range break or with a brief retest.
- The four-times filter is deliberately strict and checks all rolling 10m windows.
- Historical OI, funding, order-book depth and taker-side history may not cover past events. Missing evidence is not fabricated.
- Returns exclude fees, spread, slippage, funding payments and execution latency. No orders were placed.
- Top 200 means the highest 24h-turnover online crypto USDT perpetuals at test time.

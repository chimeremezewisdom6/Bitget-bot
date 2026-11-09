# Paper exhaustion bot — growing vs dying side

Paper-trades the "one side is dying, the other is growing, take the
biggest gap" signal across 4 windows: 10m, 20m, 30m, 1h.

## Install

    pip install -r requirements.txt

## Run

    python paper_exhaustion.py

Or in the background:

    ./run.sh

## What the bot does

For each symbol (>= $1M 24h volume) and each window:

1. Splits the window into 4 quarters
2. Measures buy and sell USD in each quarter
3. Computes `buy_growth = (Q3+Q4 buy) / (Q1+Q2 buy)`
   and `sell_growth` the same way
4. **Growing side** = whichever has the larger growth
   **Dying side** = whichever has the smaller growth
   **Gap** = grow_growth / die_growth
5. Fires only when:
   - gap >= 2.0
   - grow_growth >= 1.5
   - die_growth <= 0.7
   - growing side dominates Q4 (>= 1.3x)
   - Q4 growing volume >= $5k (scaled to window)
6. Opens a **paper** trade on the growing side

Trade: TP 2% / SL 0.8% / timeout 2x window.
Every trade tracked at 7 horizons (1m,3m,5m,10m,30m,1h,2h) for analysis.

## Output

Live on console when each signal fires and closes.
Summary every 5 minutes.
Full CSV at `/tmp/paper_exhaustion/trades.csv`.

## Analyze after 24h

    python analyze.py

Shows per-window win rate, gap buckets (do bigger gaps win more?),
best horizon per window, per-symbol ranking.

## Do not run on Render free tier

`/tmp` gets wiped on restart. Run locally or on a small VPS.

## Tuning

All parameters at the top of `paper_exhaustion.py`:

- `GAP_MIN` (default 2.0) — raise to be pickier about "biggest gaps"
- `ACCEL_MIN` (1.5), `DECAY_MAX` (0.7) — tighter to require cleaner divergence
- `TP_PCT` (2.0), `SL_PCT` (0.8) — trade exit
- `SYMBOLS_COUNT` (15) — coin universe size

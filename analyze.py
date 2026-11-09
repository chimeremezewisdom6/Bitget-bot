"""analyze.py — read /tmp/paper_exhaustion/trades.csv and report.

Answers:
  - Which window has the best win rate / expectancy?
  - Do BIGGER gaps win more? (this is the "biggest gap" hypothesis)
  - Which horizon would exit have been best?
  - Per-symbol ranking

Run: python analyze.py
"""

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

CSV_PATH = Path("/tmp/paper_exhaustion/trades.csv")
MIN_REALISTIC_PNL = -100.0


def _f(x, default=0.0):
    if x is None or x == "":
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _load():
    if not CSV_PATH.exists():
        print(f"no file at {CSV_PATH}")
        return []
    with CSV_PATH.open() as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows
            if _f(r.get("realistic_pnl"), MIN_REALISTIC_PNL) > MIN_REALISTIC_PNL]


def _stats(xs):
    n = len(xs)
    if n == 0:
        return None
    wins = [x for x in xs if x > 0]
    losses = [x for x in xs if x <= 0]
    wr = len(wins) / n
    aw = mean(wins) if wins else 0.0
    al = mean(losses) if losses else 0.0
    exp = wr * aw + (1 - wr) * al
    return {"n": n, "wr": wr, "aw": aw, "al": al, "exp": exp}


def _print_header(title):
    print()
    print("=" * 88)
    print(title)
    print("=" * 88)


def main():
    rows = _load()
    if not rows:
        print("no closed trades yet — wait longer")
        return

    print(f"loaded {len(rows)} closed trades from {CSV_PATH}")

    # ---------- Per window ----------
    _print_header("PER WINDOW (realistic exit: TP 2% / SL 0.8% / timeout)")
    by_window = defaultdict(list)
    for r in rows:
        by_window[r["window"]].append(_f(r["realistic_pnl"]))
    for wname in ["10min", "20min", "30min", "1h"]:
        xs = by_window.get(wname, [])
        s = _stats(xs)
        if not s:
            print(f"  {wname:>6}: no closed trades")
            continue
        print(f"  {wname:>6}: n={s['n']:>3} WR={s['wr']:>5.1%} "
              f"avg_win={s['aw']:>+5.2f}% avg_loss={s['al']:>+5.2f}% "
              f"exp={s['exp']:>+5.2f}%")

    # ---------- Per gap bucket ----------
    _print_header("DO BIGGER GAPS WIN MORE? (gap = growing / dying growth)")
    buckets = [(2.0, 3.0), (3.0, 5.0), (5.0, 10.0), (10.0, 1e9)]
    labels = ["2-3x", "3-5x", "5-10x", "10x+"]
    for (lo, hi), label in zip(buckets, labels):
        xs = [_f(r["realistic_pnl"]) for r in rows
              if lo <= _f(r["gap"]) < hi]
        s = _stats(xs)
        if not s:
            print(f"  gap {label:>8}: no trades")
            continue
        print(f"  gap {label:>8}: n={s['n']:>3} WR={s['wr']:>5.1%} "
              f"exp={s['exp']:>+5.2f}%")

    # ---------- Best horizon per window ----------
    _print_header("BEST HORIZON PER WINDOW (which exit point would have won?)")
    horizons = [60, 180, 300, 600, 1800, 3600, 7200]
    for wname in ["10min", "20min", "30min", "1h"]:
        wrows = [r for r in rows if r["window"] == wname]
        if not wrows:
            continue
        print(f"\n  [{wname}]")
        best = []
        for h in horizons:
            xs = [_f(r.get(f"h_{h}s_pnl")) for r in wrows
                  if r.get(f"h_{h}s_pnl") not in (None, "")]
            s = _stats(xs)
            if not s or s["n"] < 3:
                continue
            best.append((h, s))
        best.sort(key=lambda x: -x[1]["exp"])
        for h, s in best[:4]:
            print(f"    {h:>5}s: n={s['n']:>3} WR={s['wr']:>5.1%} "
                  f"exp={s['exp']:>+5.2f}%")

    # ---------- Per symbol ----------
    _print_header("PER SYMBOL (realistic exit)")
    by_sym = defaultdict(list)
    for r in rows:
        by_sym[r["symbol"]].append(_f(r["realistic_pnl"]))
    ranked = [(sym, _stats(xs)) for sym, xs in by_sym.items()]
    ranked = [x for x in ranked if x[1] and x[1]["n"] >= 2]
    ranked.sort(key=lambda x: -x[1]["exp"])
    for sym, s in ranked[:15]:
        print(f"  {sym:>14}: n={s['n']:>3} WR={s['wr']:>5.1%} "
              f"exp={s['exp']:>+5.2f}%")

    # ---------- Overall best config ----------
    _print_header("OVERALL VERDICT")
    all_xs = [_f(r["realistic_pnl"]) for r in rows]
    s = _stats(all_xs)
    if s:
        print(f"  All trades: n={s['n']} WR={s['wr']:.1%} "
              f"expectancy={s['exp']:+.3f}% per trade")
    if s and s["exp"] > 0.3:
        print("  VERDICT: positive expectancy. Worth further testing.")
    elif s and s["exp"] > 0:
        print("  VERDICT: marginally positive. Collect more data.")
    else:
        print("  VERDICT: negative expectancy. Do not deploy live.")


if __name__ == "__main__":
    main()

"""Small-sample statistics without external dependencies."""
from __future__ import annotations

import math
import random
import statistics
from typing import Any, Iterable, Sequence


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _percentile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(p * (len(ordered) - 1))))]


def bootstrap_ci(
    values: Sequence[float],
    *,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
    blocks: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Percentile bootstrap of the mean, optionally resampling whole blocks."""
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "n_boot": n_boot}
    rng = random.Random(seed)
    means = []
    if blocks is not None and len(blocks) == len(clean):
        grouped: dict[Any, list[float]] = {}
        for label, value in zip(blocks, clean):
            grouped.setdefault(label, []).append(value)
        labels = list(grouped)
        for _ in range(n_boot):
            sample = []
            for _ in labels:
                sample.extend(grouped[labels[rng.randrange(len(labels))]])
            means.append(statistics.fmean(sample))
    else:
        for _ in range(n_boot):
            sample = [clean[rng.randrange(len(clean))] for _ in clean]
            means.append(statistics.fmean(sample))
    means.sort()
    lo = means[int((alpha / 2) * (n_boot - 1))]
    hi = means[int((1 - alpha / 2) * (n_boot - 1))]
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 6),
        "lo": round(lo, 6),
        "hi": round(hi, 6),
        "n_boot": n_boot,
    }


def wilson_interval(successes: int, n: int, z: float = 1.96) -> dict[str, Any]:
    if n <= 0:
        return {"n": 0, "rate": None, "lo": None, "hi": None}
    rate = successes / n
    denominator = 1 + z * z / n
    centre = (rate + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((rate * (1 - rate) + z * z / (4 * n)) / n) / denominator
    return {
        "n": n,
        "successes": successes,
        "rate": round(rate, 6),
        "lo": round(max(0.0, centre - margin), 6),
        "hi": round(min(1.0, centre + margin), 6),
    }


def profit_factor(values: Iterable[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    if losses == 0:
        return None
    return round(gains / losses, 6)


def bh_fdr(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg q-values aligned with the input order."""
    n = len(pvalues)
    if n == 0:
        return []
    indexed = sorted(enumerate(pvalues), key=lambda item: item[1])
    qvalues = [1.0] * n
    running = 1.0
    for rank in range(n, 0, -1):
        index, pvalue = indexed[rank - 1]
        running = min(running, pvalue * n / rank)
        qvalues[index] = round(min(1.0, running), 6)
    return qvalues


def verdict(
    *,
    n: int,
    days: int,
    ci: dict[str, Any],
    lift_bps: float | None,
    q_value: float | None,
    min_events: int = 200,
    min_days: int = 10,
    fdr_q: float = 0.10,
) -> str:
    if n < min_events or days < min_days:
        return "INCONCLUSIVE"
    if ci.get("lo") is None or ci.get("hi") is None:
        return "INCONCLUSIVE"
    if q_value is not None and q_value > fdr_q:
        return "INCONCLUSIVE"
    if lift_bps is not None and lift_bps <= 0:
        return "INCONCLUSIVE"
    if ci["lo"] > 0:
        return "VALIDATED"
    if ci["hi"] < 0:
        return "REJECTED"
    return "INCONCLUSIVE"


def summarise(values: Sequence[float], *, blocks: Sequence[Any] | None = None, seed: int = 0) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "ci": None,
                "positive_rate": None, "profit_factor": None, "p10": None, "p90": None}
    ci = bootstrap_ci(clean, blocks=blocks, seed=seed)
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 6),
        "median": round(statistics.median(clean), 6),
        "stdev": round(statistics.stdev(clean), 6) if len(clean) > 1 else None,
        "ci": ci,
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 6),
        "profit_factor": profit_factor(clean),
        "p10": round(_percentile(clean, 0.10), 6),
        "p90": round(_percentile(clean, 0.90), 6),
    }


def bootstrap_pvalue(
    values: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 0,
    blocks: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """One-sided bootstrap p-value for H0: mean <= 0."""
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not clean:
        return {"n": 0, "mean": None, "p_value": None, "n_boot": n_boot}
    observed = statistics.fmean(clean)
    centered = [value - observed for value in clean]
    rng = random.Random(seed)
    means = []
    if blocks is not None and len(blocks) == len(centered):
        grouped: dict[Any, list[float]] = {}
        for label, value in zip(blocks, centered):
            grouped.setdefault(label, []).append(value)
        labels = list(grouped)
        for _ in range(n_boot):
            sample = []
            for _ in labels:
                sample.extend(grouped[labels[rng.randrange(len(labels))]])
            means.append(statistics.fmean(sample))
    else:
        for _ in range(n_boot):
            means.append(statistics.fmean([centered[rng.randrange(len(centered))] for _ in centered]))
    exceed = sum(1 for value in means if value >= observed)
    return {
        "n": len(clean),
        "mean": round(observed, 6),
        "p_value": round((1 + exceed) / (n_boot + 1), 6),
        "n_boot": n_boot,
    }

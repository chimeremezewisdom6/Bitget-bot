"""Load collected bundles and create leakage-safe chronological splits."""
from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any, Iterable

DAY_MS = 86_400_000


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bundle(path: str | Path, sections: set[str] | None = None) -> dict[str, Any]:
    """Read a cycle bundle produced by ``collector.bundle``.

    ``sections`` limits reading to the named JSONL sections, which keeps
    evaluation memory bounded when only ``features`` is needed.
    """
    path = Path(path)
    result: dict[str, Any] = {"meta": {}, "rows": {}}
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = Path(member.name).stem
            if name != "meta" and sections is not None and name not in sections:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            text = handle.read().decode("utf-8")
            if name == "meta":
                result["meta"] = json.loads(text)
                continue
            rows = []
            for line in text.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            result["rows"][name] = rows
    return result


def load_bundles(root: str | Path, sections: set[str] | None = None) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {}
    metas = []
    for path in sorted(Path(root).glob("*.tar.gz")):
        bundle = load_bundle(path, sections=sections)
        metas.append({"path": str(path), "sha256": sha256_file(path), **bundle["meta"]})
        for name, values in bundle["rows"].items():
            rows.setdefault(name, []).extend(values)
    return {"metas": metas, "rows": rows}


def day_index(ts_ms: int, start_ms: int) -> int:
    return int((int(ts_ms) - int(start_ms)) // DAY_MS)


def split_30d(
    rows: Iterable[dict[str, Any]],
    start_ms: int,
    *,
    train_days: int = 15,
    validation_days: int = 7,
    test_days: int = 8,
    embargo_minutes: int = 60,
    max_horizon_min: int = 60,
    feature_lookback_min: int = 64,
) -> dict[str, list[dict[str, Any]]]:
    """Chronological split with an embargo at both internal boundaries.

    Events whose forward horizon crosses a split boundary are excluded, so no
    label uses data from the next split.
    """
    total = train_days + validation_days + test_days
    validation_start = train_days
    test_start = train_days + validation_days
    embargo_ms = embargo_minutes * 60_000
    horizon_ms = max_horizon_min * 60_000
    boundaries = [
        start_ms + validation_start * DAY_MS,
        start_ms + test_start * DAY_MS,
        start_ms + total * DAY_MS,
    ]
    out = {"train": [], "validation": [], "test": []}
    for row in rows:
        ts = row.get("ts_ms")
        if ts is None:
            continue
        index = day_index(ts, start_ms)
        if index < 0 or index >= total:
            continue
        if index < validation_start:
            split = "train"
        elif index < test_start:
            split = "validation"
        else:
            split = "test"
        # Exclude events too close to either internal boundary or crossing the end.
        near_boundary = any(abs(int(ts) + horizon_ms - boundary) < embargo_ms for boundary in boundaries[:2])
        crosses_end = int(ts) + horizon_ms > boundaries[2]
        # Also exclude the first feature_lookback_min of a later split, because
        # its trailing features would otherwise use candles from the prior split.
        lookback_ms = int(feature_lookback_min) * 60_000
        split_start = (
            start_ms + validation_start * DAY_MS
            if split == "validation"
            else start_ms + test_start * DAY_MS
            if split == "test"
            else None
        )
        backward_leak = split_start is not None and int(ts) - lookback_ms < split_start
        if near_boundary or crosses_end or backward_leak:
            continue
        out[split].append(row)
    return out

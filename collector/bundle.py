"""Deterministic compressed cycle bundles and their manifests."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any, Iterable

BUNDLE_VERSION = 1
DEFAULT_MAX_BYTES = 1_500_000
DROP_ORDER = ("micro", "book", "flow", "spot", "oi", "liquidations", "events", "candles")


def serialise(row: Any) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: serialise(row))


def section_bytes(sections: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        name: sum(len(serialise(row)) + 1 for row in rows)
        for name, rows in sections.items()
    }


def trim_sections(
    sections: dict[str, list[dict[str, Any]]],
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Drop optional sections in a fixed order until the bundle fits.

    Returns the trimmed sections and the names that were dropped. Nothing is
    removed silently: the caller must put the names in the manifest.
    """
    working = {name: list(rows) for name, rows in sections.items()}
    dropped: list[str] = []
    for name in DROP_ORDER:
        if sum(section_bytes(working).values()) <= max_bytes:
            break
        if working.get(name):
            working[name] = []
            dropped.append(name)
    return working, dropped


def _write_tar_gz(files: dict[str, bytes], out: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(data))
    with out.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(buffer.getvalue())


def build_bundle(
    sections: dict[str, list[dict[str, Any]]],
    meta: dict[str, Any],
    out_dir: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[Path, dict[str, Any]]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trimmed, dropped = trim_sections(sections, max_bytes=max_bytes)
    payload = {
        "meta": meta,
        **{name: _sort_rows(rows) for name, rows in trimmed.items()},
    }
    files: dict[str, bytes] = {}
    for name, rows in payload.items():
        if name == "meta":
            text = json.dumps(rows, indent=2, sort_keys=True) + "\n"
        else:
            text = "".join(serialise(row) + "\n" for row in rows)
        files[f"{name}.jsonl" if name != "meta" else "meta.json"] = text.encode("utf-8")
    bundle_path = out / "bundle.tar.gz"
    _write_tar_gz(files, bundle_path)
    size = bundle_path.stat().st_size
    manifest = manifest_for(bundle_path, meta, trimmed, dropped, size)
    return bundle_path, manifest


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_for(
    bundle_path: str | Path,
    meta: dict[str, Any],
    sections: dict[str, list[dict[str, Any]]],
    dropped: list[str],
    size_bytes: int,
) -> dict[str, Any]:
    counts = {name: len(rows) for name, rows in sections.items()}
    return {
        "schema_version": BUNDLE_VERSION,
        "slot": meta.get("slot"),
        "git_sha": meta.get("git_sha"),
        "artifact": Path(bundle_path).parent.name,
        "sha256": sha256_file(bundle_path),
        "size_bytes": int(size_bytes),
        "size_target_bytes": 300_000,
        "size_target_exceeded": int(size_bytes) > 300_000,
        "counts": counts,
        "quality": {
            "symbols_ok": meta.get("symbols_ok"),
            "symbols_failed": meta.get("symbols_failed"),
            "duplicates": meta.get("duplicates", 0),
            "truncated_sections": dropped,
        },
    }

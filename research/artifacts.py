"""List, download and validate GitHub Actions artifacts without hiding failures."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, Sequence

API_URL = "https://api.github.com"


class ArtifactError(RuntimeError):
    pass


class Transport(Protocol):
    def get_json(self, url: str) -> dict[str, Any]: ...
    def get_bytes(self, url: str) -> bytes: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class UrllibTransport:
    def __init__(self, token: str, *, timeout: float = 60.0):
        if not token:
            raise ArtifactError("GITHUB_TOKEN is required to list or download artifacts")
        self.token = token
        self.timeout = timeout

    def _headers(self, authenticated: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "bitget-phase-b-research",
        }
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers=self._headers())
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise
            location = exc.headers.get("Location")
            if not location:
                raise ArtifactError("Artifact redirect had no Location header") from exc
            # The signed storage URL must not receive the GitHub token.
            with urllib.request.urlopen(
                urllib.request.Request(location, headers=self._headers(authenticated=False)),
                timeout=self.timeout,
            ) as response:
                return response.read()


@dataclass(frozen=True)
class Artifact:
    id: int
    name: str
    created_at: str
    expired: bool
    size_in_bytes: int
    archive_download_url: str
    workflow_run_id: int | None = None

    @property
    def created_ms(self) -> int:
        return _iso_to_ms(self.created_at)


def _iso_to_ms(value: str) -> int:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(stamp.timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _artifact_from_row(row: dict[str, Any]) -> Artifact | None:
    try:
        return Artifact(
            id=int(row["id"]),
            name=str(row["name"]),
            created_at=str(row["created_at"]),
            expired=bool(row.get("expired", False)),
            size_in_bytes=int(row.get("size_in_bytes", 0)),
            archive_download_url=str(row["archive_download_url"]),
            workflow_run_id=(
                int(row["workflow_run"]["id"])
                if isinstance(row.get("workflow_run"), dict) and row["workflow_run"].get("id")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def list_artifacts(
    repo: str,
    *,
    transport: Transport,
    prefix: str = "bitget-5m-",
    days: int = 3,
    now_ms: int | None = None,
    max_pages: int = 20,
) -> dict[str, Any]:
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    cutoff = now - int(days) * 86_400_000
    found: list[Artifact] = []
    errors: list[dict[str, Any]] = []
    pages = 0
    for page in range(1, max_pages + 1):
        url = f"{API_URL}/repos/{repo}/actions/artifacts?per_page=100&page={page}"
        try:
            payload = transport.get_json(url)
        except Exception as exc:
            errors.append({"stage": "list", "page": page, "error": type(exc).__name__, "message": str(exc)[:300]})
            break
        pages = page
        rows = payload.get("artifacts") or []
        for row in rows:
            artifact = _artifact_from_row(row)
            if artifact is None or not artifact.name.startswith(prefix):
                continue
            if artifact.created_ms and artifact.created_ms < cutoff:
                continue
            found.append(artifact)
        if len(rows) < 100:
            break
    return {
        "artifacts": found,
        "errors": errors,
        "pages": pages,
        "cutoff_ms": cutoff,
        "now_ms": now,
    }


def _safe_extract(archive: zipfile.ZipFile, destination: Path, *, summary_only: bool) -> None:
    for info in archive.infolist():
        name = info.filename
        if name.startswith("/") or ".." in Path(name).parts:
            raise ArtifactError(f"Unsafe artifact path: {name}")
        if summary_only and not name.endswith("summary.json"):
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as handle:
            handle.write(source.read())


def download_artifact(
    artifact: Artifact,
    out_dir: str | Path,
    *,
    transport: Transport,
    summary_only: bool = False,
) -> dict[str, Any]:
    if artifact.expired:
        return {"id": artifact.id, "name": artifact.name, "status": "EXPIRED", "bytes": 0}
    try:
        data = transport.get_bytes(artifact.archive_download_url)
    except Exception as exc:
        return {
            "id": artifact.id, "name": artifact.name, "status": "DOWNLOAD_ERROR",
            "error": type(exc).__name__, "message": str(exc)[:300], "bytes": 0,
        }
    destination = Path(out_dir) / str(artifact.id)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            _safe_extract(archive, destination, summary_only=summary_only)
    except Exception as exc:
        return {
            "id": artifact.id, "name": artifact.name, "status": "BAD_ZIP",
            "error": type(exc).__name__, "message": str(exc)[:300], "bytes": len(data),
        }
    return {
        "id": artifact.id, "name": artifact.name, "status": "OK",
        "bytes": len(data), "path": str(destination),
    }


def download_bundles(
    repo: str,
    *,
    transport: Transport,
    prefix: str = "bitget-5m-",
    days: int = 3,
    out_dir: str | Path,
    max_artifacts: int = 900,
    max_bytes: int = 400_000_000,
    now_ms: int | None = None,
    summary_only: bool = False,
) -> dict[str, Any]:
    listing = list_artifacts(
        repo, transport=transport, prefix=prefix, days=days, now_ms=now_ms
    )
    artifacts = sorted(listing["artifacts"], key=lambda item: item.created_ms)
    truncated = len(artifacts) > max_artifacts
    if truncated:
        artifacts = artifacts[-max_artifacts:]
    downloaded: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = list(listing["errors"])
    total_bytes = 0
    for artifact in artifacts:
        if total_bytes >= max_bytes:
            errors.append({
                "stage": "download", "status": "SIZE_LIMIT",
                "message": f"Stopped after {total_bytes} bytes",
            })
            break
        result = download_artifact(
            artifact, out_dir, transport=transport, summary_only=summary_only
        )
        result["created_at"] = artifact.created_at
        downloaded.append(result)
        total_bytes += int(result.get("bytes") or 0)
        if result.get("status") != "OK":
            errors.append({
                "stage": "download", "artifact": artifact.name,
                "status": result.get("status"), "message": result.get("message"),
            })
    return {
        "repo": repo,
        "prefix": prefix,
        "days": int(days),
        "artifacts_listed": len(listing["artifacts"]),
        "artifacts_downloaded": sum(1 for item in downloaded if item.get("status") == "OK"),
        "total_bytes": total_bytes,
        "truncated": truncated,
        "downloaded": downloaded,
        "errors": errors,
        "cutoff_ms": listing["cutoff_ms"],
        "now_ms": listing["now_ms"],
    }


def _find_one(root: Path, name: str) -> Path | None:
    matches = sorted(root.rglob(name))
    return matches[0] if matches else None


def validate_artifact_dir(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    summary_path = _find_one(root, "summary.json")
    bundle_path = _find_one(root, "bundle.tar.gz")
    if summary_path is None:
        return {"status": "INCOMPLETE", "reason": "summary.json missing", "path": str(root)}
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "INCOMPLETE", "reason": f"summary unreadable: {exc}", "path": str(root)}
    outcome = summary.get("outcome")
    if bundle_path is None:
        status = "FAILED_NO_BUNDLE" if outcome == "failed" else "INCOMPLETE"
        return {"status": status, "summary": summary, "path": str(root)}
    expected = (summary.get("manifest") or {}).get("sha256")
    actual = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    if expected and expected != actual:
        return {
            "status": "BAD_SHA", "summary": summary, "bundle": str(bundle_path),
            "expected_sha256": expected, "actual_sha256": actual, "path": str(root),
        }
    return {
        "status": "OK", "summary": summary, "bundle": str(bundle_path),
        "sha256": actual, "path": str(root),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download read-only Phase B artifacts")
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("download")
    download.add_argument("--repo", required=True)
    download.add_argument("--prefix", default="bitget-5m-")
    download.add_argument("--days", type=int, default=3)
    download.add_argument("--out", required=True)
    download.add_argument("--max-artifacts", type=int, default=900)
    download.add_argument("--max-bytes", type=int, default=400_000_000)
    download.add_argument("--summary-only", action="store_true")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is not set", flush=True)
        return 2
    transport = UrllibTransport(token)
    if args.command == "download":
        result = download_bundles(
            args.repo,
            transport=transport,
            prefix=args.prefix,
            days=args.days,
            out_dir=args.out,
            max_artifacts=args.max_artifacts,
            max_bytes=args.max_bytes,
            summary_only=args.summary_only,
        )
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "artifacts_manifest.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "listed": result["artifacts_listed"],
            "downloaded": result["artifacts_downloaded"],
            "errors": len(result["errors"]),
            "truncated": result["truncated"],
        }, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

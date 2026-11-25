"""Truthful session state and heartbeat. No unbounded lists."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

SESSION_SECONDS = 86_400
SETTLE_SECONDS = 1_800


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(target.parent), delete=False, suffix=".tmp"
    )
    try:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, target)
    finally:
        if not handle.closed:
            handle.close()
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def load_session(path: str | Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def start_session(now_ms: int) -> dict[str, Any]:
    end_epoch = now_ms / 1000.0 + SESSION_SECONDS
    settle_epoch = end_epoch + SETTLE_SECONDS
    from datetime import datetime, timezone
    return {
        "active": True,
        "started_at_utc": datetime.fromtimestamp(now_ms / 1000.0, timezone.utc).isoformat(),
        "end_epoch": end_epoch,
        "ends_at_utc": datetime.fromtimestamp(end_epoch, timezone.utc).isoformat(),
        "settle_epoch": settle_epoch,
        "settle_until_utc": datetime.fromtimestamp(settle_epoch, timezone.utc).isoformat(),
        "cycles": 0,
        "successful_cycles": 0,
        "last_slot": None,
        "last_at": None,
        "data_source": "Bitget USDT-FUTURES",
        "trading_enabled": False,
    }


def is_active(state: dict[str, Any], now_ms: int) -> bool:
    end = state.get("settle_epoch", state.get("end_epoch", 0)) or 0
    return bool(state.get("active")) and now_ms / 1000.0 < float(end)


def finish_session(state: dict[str, Any], now_ms: int) -> dict[str, Any]:
    from datetime import datetime, timezone
    updated = dict(state)
    updated["active"] = False
    updated["stopped_at_utc"] = datetime.fromtimestamp(now_ms / 1000.0, timezone.utc).isoformat()
    return updated


def heartbeat(
    result: dict[str, Any],
    session: dict[str, Any],
    *,
    event: str = "manual",
    action: str = "collect",
    run_id: str = "",
    now_ms: int | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone
    stamp = datetime.fromtimestamp((now_ms or 0) / 1000.0, timezone.utc).isoformat() if now_ms else None
    return {
        "schema_version": 2,
        "heartbeat_utc": stamp,
        "slot": result.get("slot"),
        "event": event,
        "action": action,
        "outcome": result.get("outcome", "failed"),
        "run_id": run_id,
        "symbols_requested": result.get("symbols_requested", 0),
        "symbols_ok": result.get("symbols_ok", 0),
        "symbols_failed": result.get("symbols_failed", 0),
        "candles_new": result.get("candles_new", 0),
        "events": result.get("events", 0),
        "duplicates": result.get("duplicates", 0),
        "duration_ms": result.get("duration_ms"),
        "artifact": result.get("artifact"),
        "session_active": bool(session.get("active")),
        "cycles": int(session.get("cycles", 0)),
        "successful_cycles": int(session.get("successful_cycles", 0)),
        "last_collection_utc": session.get("last_at"),
        "expected_interval_minutes": 5,
        "trading_enabled": False,
        "errors": list(result.get("errors", []))[:20],
    }

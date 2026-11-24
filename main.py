"""Single public entry point for every Bitget read-only research action.

The scheduler and manual ping both call this file. Specialist modules remain
internal implementation modules so their tested logic stays reusable.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SESSION = ROOT / "reports" / "daily_research" / "session.json"


def run(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def session_state():
    try:
        return json.loads(SESSION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def is_active(state):
    end = state.get("settle_epoch", state.get("end_epoch", 0))
    return bool(state.get("active")) and time.time() < float(end or 0)


def start():
    state = session_state()
    if is_active(state):
        print("Existing 24-hour research session is active; keeping it.")
        return
    print("Preparing Bitget USDT futures activity watchlist.")
    run("cap_watchlist.py")
    run("daily_research.py", "start")


def collect():
    state = session_state()
    if not is_active(state):
        start()
    print("Running one Bitget read-only research collection cycle.")
    run("daily_research.py", "collect")
    run("research_report.py")


def ping():
    """Cron and manual heartbeat entry point: ensure session, collect, report."""
    collect()
    state = session_state()
    print(json.dumps({
        "scanner": "Bitget read-only research",
        "ping": "ok",
        "session_active": is_active(state),
        "cycles": state.get("cycles", 0),
        "last_collection_utc": state.get("last_at"),
        "trading_enabled": False,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Bitget unified read-only research scanner")
    parser.add_argument("action", choices=["start", "collect", "ping", "status", "stop"])
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "collect":
        collect()
    elif action == "ping":
        ping()
    elif action == "status":
        print(json.dumps(session_state(), indent=2))
    elif action == "stop":
        state = session_state()
        state["active"] = False
        from datetime import datetime, timezone
        state["stopped_at_utc"] = datetime.now(timezone.utc).isoformat()
        SESSION.parent.mkdir(parents=True, exist_ok=True)
        SESSION.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print("Research stopped; existing evidence preserved.")


if __name__ == "__main__":
    main()

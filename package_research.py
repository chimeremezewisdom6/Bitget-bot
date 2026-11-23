"""Create one portable ZIP with raw evidence, CSV exports, report and manifest."""
import csv
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
DATA = REPORTS / "daily_research"
PACKAGE = REPORTS / "bitget_24h_research_package.zip"
JSONL_FILES = [
    "market_observations.jsonl",
    "candles_1m.jsonl",
    "trend_early_window_backtest.jsonl",
    "public_trader_posts.jsonl",
    "shadow_experiments.jsonl",
    "collection_errors.jsonl",
]


def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                rows.append({"_parse_error_line": line_number, "_raw": line.rstrip()})
    return rows


def csv_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def export_csv(source):
    rows = load_jsonl(source)
    destination = source.with_suffix(".csv")
    columns = sorted({key for row in rows for key in row})
    if not columns:
        columns = ["_no_records"]
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})
    return len(rows), destination


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in JSONL_FILES:
        count, csv_path = export_csv(DATA / name)
        counts[name] = count
        print(f"{name}: {count} rows -> {csv_path.name}")

    included = []
    for path in sorted(DATA.rglob("*")):
        if path.is_file() and path != PACKAGE:
            included.append(path)
    watchlist = REPORTS / "market_cap_watchlist"
    if watchlist.exists():
        included.extend(path for path in sorted(watchlist.rglob("*")) if path.is_file())

    manifest = {
        "package_created_utc": datetime.now(timezone.utc).isoformat(),
        "description": "Read-only Bitget USDT futures research. No orders were submitted.",
        "record_counts": counts,
        "files": [
            {"path": str(path.relative_to(REPORTS)), "bytes": path.stat().st_size}
            for path in included
        ],
        "interpretation_warnings": [
            "Turnover activity bands are not market-cap classifications.",
            "Shadow order-book fills are estimates, not guaranteed executable fills.",
            "Repeated sizes and horizons from one signal are correlated observations.",
            "A short research sample does not establish a durable profitable edge."
        ],
    }
    manifest_path = DATA / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme_path = DATA / "DOWNLOAD_README.txt"
    readme_path.write_text(
        "BITGET 24-HOUR READ-ONLY RESEARCH PACKAGE\n"
        "==========================================\n"
        "Start with daily_research_summary.md and package_manifest.json.\n"
        "CSV files can be opened in Excel or Google Sheets. JSONL files preserve raw records.\n"
        "shadow_experiments.csv contains signals and hypothetical outcomes.\n"
        "market_observations.csv contains timestamped Bitget market observations.\n"
        "candles_1m.csv contains de-duplicated one-minute candles.\n"
        "No live or demo orders were submitted. Estimated results are not a promise of profit.\n",
        encoding="utf-8",
    )
    included.extend([manifest_path, readme_path])
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PACKAGE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(included)):
            archive.write(path, path.relative_to(REPORTS))
    print(f"Created {PACKAGE} ({PACKAGE.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

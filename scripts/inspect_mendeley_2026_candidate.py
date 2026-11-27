from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp_dataset_assessment"
REPORT = ROOT / "reports" / "mendeley_2026_candidate_assessment.json"
SOURCES = {
    "sales": "https://raw.githubusercontent.com/shreyayp/RetailPulse/main/data/raw/retail_sales_ml_apl.csv",
    "inventory": "https://raw.githubusercontent.com/shreyayp/RetailPulse/main/data/raw/retail_inventory_ml_apl.csv",
}
DATE_WORDS = {"date", "business_date", "transaction_date", "sales_date", "day", "start_date", "end_date", "snapshot_date", "inventory_date"}


def normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def download(url: str, target: Path) -> str:
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "VenkatRetailDataQualityAudit/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
            digest.update(block)
    return digest.hexdigest()


def inspect_file(kind: str, url: str) -> dict:
    filename = url.rsplit("/", 1)[-1]
    path = TMP / filename
    sha256 = download(url, path)
    field_counts = {}
    date_stats = {}
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if not headers:
            raise RuntimeError(f"{filename}: CSV has no header")
        normalized = {name: normalise(name) for name in headers}
        date_fields = [
            name for name, norm in normalized.items()
            if norm in DATE_WORDS or "date" in norm or "timestamp" in norm
        ]
        date_stats = {field: {"min": None, "max": None, "valid": 0, "invalid": 0} for field in date_fields}
        for row in reader:
            rows += 1
            for field, stats in date_stats.items():
                value = row.get(field, "")
                parsed = parse_date(value)
                if parsed is None:
                    stats["invalid"] += 1
                    continue
                iso = parsed.isoformat(sep=" ")
                stats["valid"] += 1
                if stats["min"] is None or iso < stats["min"]:
                    stats["min"] = iso
                if stats["max"] is None or iso > stats["max"]:
                    stats["max"] = iso
    return {
        "filename": filename,
        "source_url": url,
        "bytes": path.stat().st_size,
        "sha256": sha256,
        "rows": rows,
        "columns": headers,
        "date_fields": date_stats,
    }


def main():
    results = {kind: inspect_file(kind, url) for kind, url in SOURCES.items()}
    report = {
        "assessment_run_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "Retail Transactions and Stocks Data",
        "dataset_doi": "10.17632/27x8mjm8k4.1",
        "publisher_page": "https://data.mendeley.com/datasets/27x8mjm8k4/1",
        "dataset_license": "CC BY 4.0",
        "candidate_distribution": "Public GitHub mirror used only for inspection; cite and attribute the original Mendeley Data record.",
        "files": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

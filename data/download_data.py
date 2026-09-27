"""Download the real IBM Telco Customer Churn dataset (7,043 rows, 21 columns).

Source: IBM sample data published in the Apache-2.0 licensed repository
https://github.com/IBM/telco-customer-churn-on-icp4d

Usage:
    python data/download_data.py            # -> data/raw/Telco-Customer-Churn.csv
"""
from __future__ import annotations

import csv
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from telco_churn import config  # noqa: E402


def main() -> int:
    target = config.DEFAULT_RAW_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {config.TELCO_SOURCE_URL}")
    req = urllib.request.Request(config.TELCO_SOURCE_URL, headers={"User-Agent": "telco-churn-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = resp.read()
    target.write_bytes(payload)

    with target.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        n_rows = sum(1 for _ in reader)
    if header != config.RAW_COLUMNS:
        print("ERROR: header does not match the expected schema:\n", header)
        return 1
    status = "OK" if n_rows == config.EXPECTED_REAL_ROWS else "WARNING: unexpected row count"
    print(f"Saved {target} | rows={n_rows} ({status}) | sha256={hashlib.sha256(payload).hexdigest()[:16]}…")
    print("Next: python data/generate_network_kpis.py && python -m telco_churn run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

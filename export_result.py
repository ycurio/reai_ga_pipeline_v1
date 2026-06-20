"""Convert raw pipeline JSON output into CRM/dialer-ready CSV and JSON files."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

from reai.scoring import WEIGHTS

WEIGHTS_BY_VALUE = {record_type.value: weight for record_type, weight in WEIGHTS.items()}

LEAD_FIELDS = [
    "owner_name", "parcel_id", "property_address", "county", "state",
    "phone", "email",
    "bedrooms", "baths", "sqft", "lot_size", "year_built", "assessed_value",
    "equity_percent", "unpaid_balance", "original_loan_amount", "mortgage_recording_date",
]
DETAIL_FIELDS = [
    "source", "record_type", "case_number", "status", "filing_date",
    "amount", "instrument_number", "book", "page", "confidence",
    "raw_reference", "raw_url",
]


def load_results(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def write_summary_csv(results: list[dict], path: Path) -> None:
    fieldnames = LEAD_FIELDS + ["score"] + list(WEIGHTS_BY_VALUE)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            seen_types = {r["record_type"] for r in item["records"]}
            row = {field: item["lead"].get(field) for field in LEAD_FIELDS}
            row["score"] = item["score"]
            for record_type, weight in WEIGHTS_BY_VALUE.items():
                row[record_type] = weight if record_type in seen_types else 0
            writer.writerow(row)


def write_detailed_csv(results: list[dict], path: Path) -> None:
    fieldnames = LEAD_FIELDS + DETAIL_FIELDS
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            lead_row = {field: item["lead"].get(field) for field in LEAD_FIELDS}
            for record in item["records"]:
                writer.writerow(lead_row | {field: record.get(field) for field in DETAIL_FIELDS})


def write_sorted_json(results: list[dict], path: Path) -> None:
    path.write_text(json.dumps(sorted(results, key=lambda item: item["score"], reverse=True), indent=2))


def main():
    p = argparse.ArgumentParser(description="Export pipeline results to CRM/dialer-ready files")
    p.add_argument("--input", default="data/output/results.json")
    p.add_argument("--outdir", default="data/output")
    args = p.parse_args()

    results = load_results(Path(args.input))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    summary_path = outdir / "results_summary.csv"
    detailed_path = outdir / "results_detailed.csv"
    sorted_path = outdir / "results_sorted.json"

    write_summary_csv(results, summary_path)
    write_detailed_csv(results, detailed_path)
    write_sorted_json(results, sorted_path)

    print(f"wrote {summary_path}")
    print(f"wrote {detailed_path}")
    print(f"wrote {sorted_path}")


if __name__ == "__main__":
    main()

"""Convert a lead export (foreclosure/NOD/lis-pendens or successor/probate) into a
pipeline-compatible leads CSV, seeded with the distress type already known from the source file.
"""
from __future__ import annotations
import argparse
import csv
import re
from pathlib import Path

import pandas as pd

LEAD_FIELDS = ["owner_name", "parcel_id", "property_address", "county", "state", "seed_record_type"]
SEED_TYPE_DELIM = "|"

DOC_TYPE_TO_RECORD_TYPE = [
    ("LIS PENDENS", "lis_pendens"),
    ("DEFAULT", "notice_of_default"),
    ("FORECLOSURE", "foreclosure"),
]
DEFAULT_RECORD_TYPE = "foreclosure"


def classify_doc_type(description: str | None) -> str:
    d = (description or "").upper()
    for needle, record_type in DOC_TYPE_TO_RECORD_TYPE:
        if needle in d:
            return record_type
    return DEFAULT_RECORD_TYPE


def convert_foreclosure_export(df: pd.DataFrame) -> pd.DataFrame:
    """Handles the foreclosure/NOD/lis-pendens provider export schema (Document Type Code Description,
    Property Full Street Address, Assessor Parcel Number, etc.) - seed type is classified per row."""
    leads = pd.DataFrame()
    leads["owner_name"] = df["Current Owner Name"].str.strip()
    leads["parcel_id"] = df["Assessor Parcel Number"].fillna(df["NOD Apn"]).fillna("").str.strip()
    leads["property_address"] = (
        df["Property Full Street Address"].fillna("").str.strip() + ", " +
        df["Property City Name"].fillna("").str.strip() + ", " +
        df["Property State"].fillna("").str.strip() + " " +
        df["Property Zipcode"].fillna("").astype(str).str.strip()
    )
    leads["county"] = df["County"].fillna("").str.strip()
    leads["state"] = df["Property State"].fillna("GA").str.strip()
    leads["seed_record_type"] = df["Document Type Code Description"].apply(classify_doc_type)
    return leads


def convert_successor(df: pd.DataFrame) -> pd.DataFrame:
    """Handles the successor/pre-probate provider export schema (Owner Name, Age, Group Tag, etc.)
    - every row seeds as successor-level distress."""
    leads = pd.DataFrame()
    leads["owner_name"] = df["Owner Name"].str.strip()
    leads["parcel_id"] = df["Parcel No"].fillna("").astype(str).str.strip()
    leads["property_address"] = (
        df["Property Address"].fillna("").str.strip() + ", " +
        df["Property City"].fillna("").str.strip() + ", " +
        df["Property State"].fillna("").str.strip() + " " +
        df["Property Zip"].fillna("").astype(str).str.strip()
    )
    leads["county"] = df["Property County"].fillna("").str.strip()
    leads["state"] = df["Property State"].fillna("GA").str.strip()
    leads["seed_record_type"] = "successor"
    return leads


CONVERTERS = {
    "foreclosure": convert_foreclosure_export,
    "successor": convert_successor,
}


def normalize_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().upper())


def lead_identity(row: dict) -> tuple[str, str]:
    return (normalize_key(row.get("owner_name")), normalize_key(row.get("property_address")))


def merge_seed_types(existing: str, new: str) -> str:
    types = [t for t in (existing or "").split(SEED_TYPE_DELIM) if t]
    if new and new not in types:
        types.append(new)
    return SEED_TYPE_DELIM.join(types)


def merge_leads(rows: list[dict], new_rows: list[dict]) -> tuple[list[dict], int, int]:
    """Merge new_rows into rows by (owner_name, property_address) identity.
    A lead seen under a new seed type gets that type added (summed at scoring time),
    not replaced - returns (merged_rows, added_count, merged_count)."""
    index = {lead_identity(r): r for r in rows}
    added = merged = 0
    for new in new_rows:
        key = lead_identity(new)
        existing = index.get(key)
        if existing is None:
            rows.append(new)
            index[key] = new
            added += 1
        else:
            existing["seed_record_type"] = merge_seed_types(existing["seed_record_type"], new["seed_record_type"])
            for field in ("parcel_id", "county"):
                if not existing.get(field) and new.get(field):
                    existing[field] = new[field]
            merged += 1
    return rows, added, merged


def load_existing_leads(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    p = argparse.ArgumentParser(description="Convert a lead export to a pipeline-compatible leads CSV")
    p.add_argument("input", help="Path to the lead export .xlsx file")
    p.add_argument("--type", choices=sorted(CONVERTERS), required=True, help="Source export schema")
    p.add_argument("-o", "--output", default="leads.csv", help="Output CSV path (default: leads.csv)")
    p.add_argument("-a", "--append", action="store_true",
                    help="Merge into an existing leads CSV instead of overwriting it")
    args = p.parse_args()

    df = pd.read_excel(args.input)
    leads = CONVERTERS[args.type](df)
    leads = leads[leads["owner_name"].notna() & (leads["owner_name"] != "")]
    new_rows = leads.to_dict("records")

    output_path = Path(args.output)
    existing_rows = load_existing_leads(output_path) if args.append else []
    merged_rows, added, merged_count = merge_leads(existing_rows, new_rows)

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_FIELDS)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"Converted {len(new_rows)} leads from {args.input} ({args.type}): "
          f"{added} new, {merged_count} merged into existing leads -> {output_path} "
          f"({len(merged_rows)} total)")


if __name__ == "__main__":
    main()

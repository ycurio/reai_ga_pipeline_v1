"""Convert a lead export (foreclosure/NOD/lis-pendens or successor/probate) into a
pipeline-compatible leads CSV, seeded with the distress type already known from the source file.
"""
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

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


def main():
    p = argparse.ArgumentParser(description="Convert a lead export to a pipeline-compatible leads CSV")
    p.add_argument("input", help="Path to the lead export .xlsx file")
    p.add_argument("--type", choices=sorted(CONVERTERS), required=True, help="Source export schema")
    p.add_argument("-o", "--output", default="leads.csv", help="Output CSV path (default: leads.csv)")
    p.add_argument("-a", "--append", action="store_true",
                    help="Append to an existing leads CSV instead of overwriting it")
    args = p.parse_args()

    df = pd.read_excel(args.input)
    leads = CONVERTERS[args.type](df)

    leads = leads[leads["owner_name"].notna() & (leads["owner_name"] != "")]
    leads = leads.reset_index(drop=True)

    append = args.append and Path(args.output).exists()
    leads.to_csv(args.output, mode="a" if append else "w", header=not append, index=False)
    print(f"Converted {len(leads)} leads from {args.input} ({args.type}) -> {args.output}"
          f"{' (appended)' if append else ''}")
    print(leads.head(10).to_string())


if __name__ == "__main__":
    main()

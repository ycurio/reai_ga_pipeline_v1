"""Convert a lead export (foreclosure/NOD/lis-pendens or successor/probate) into a
pipeline-compatible leads CSV, seeded with the distress type already known from the source file.
"""
from __future__ import annotations
import argparse
import csv
import re
from pathlib import Path

import pandas as pd

LEAD_FIELDS = [
    "owner_name", "parcel_id", "property_address", "county", "state",
    "phone", "email", "all_phones", "all_emails",
    "bedrooms", "baths", "sqft", "lot_size", "year_built", "assessed_value",
    "equity_percent", "unpaid_balance", "original_loan_amount", "mortgage_recording_date",
    "seed_record_type",
]
SEED_TYPE_DELIM = "|"

PHONE_COLUMN_CANDIDATES = ["Phone", "Phone Number", "Owner Phone", "Cell Phone", "Mobile Phone"]
EMAIL_COLUMN_CANDIDATES = ["Email", "Email Address", "Owner Email"]

# Skip-traced exports return up to 5 ranked phones and 3 ranked emails per lead.
MULTI_PHONE_COLUMNS = ["Phone", "Phone2", "Phone3", "Phone4", "Phone5"]
MULTI_EMAIL_COLUMNS = ["Email", "Email 2", "Email 3"]

# Skip-traced exports echo the original owner name back as "Full Name" - if that collides
# with the skip-trace's own "Full Name" column (the matched contact, which can be a totally
# different name/entity than the title owner), pandas renames the echoed one to "Full Name.1".
OWNER_NAME_COLUMN_CANDIDATES = ["Current Owner Name", "Full Name.1", "Full Name"]

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


def _stringify(value) -> str:
    """Excel often stores numeric-looking columns (phone, parcel #) as floats - format
    whole-number floats without the trailing '.0' instead of naively str()-ing them."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def col(df: pd.DataFrame, name: str) -> pd.Series:
    """Pull a column as a stripped string, or blank if the source file doesn't have it."""
    if name not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[name].apply(_stringify)


def first_matching_col(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name].apply(_stringify)
    return pd.Series([""] * len(df), index=df.index)


def format_phone(value: str) -> str:
    """Normalize a bare-digits US phone number to E.164 (+1XXXXXXXXXX)."""
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return value


def first_nonblank(*series: pd.Series) -> pd.Series:
    result = series[0]
    for s in series[1:]:
        result = result.where(result != "", s)
    return result


def collect_multi(df: pd.DataFrame, columns: list[str], formatter=None) -> pd.Series:
    """Collect non-blank values across multiple ranked columns (e.g. Phone, Phone2, ...)
    per row into one deduped, delimited list, dropping columns the file doesn't have."""
    existing = [c for c in columns if c in df.columns]
    if not existing:
        return pd.Series([""] * len(df), index=df.index)

    def combine(row):
        values = [v for v in row if v]
        if formatter:
            values = [formatter(v) for v in values]
        deduped = list(dict.fromkeys(values))
        return SEED_TYPE_DELIM.join(deduped)

    cols = pd.concat([df[c].apply(_stringify) for c in existing], axis=1)
    return cols.apply(combine, axis=1)


def convert_foreclosure_export(df: pd.DataFrame) -> pd.DataFrame:
    """Handles the foreclosure/NOD/lis-pendens provider export schema (Document Type Code Description,
    Property Full Street Address, Assessor Parcel Number, etc.) - seed type is classified per row."""
    leads = pd.DataFrame()
    leads["owner_name"] = first_matching_col(df, OWNER_NAME_COLUMN_CANDIDATES)
    leads["parcel_id"] = first_nonblank(col(df, "Assessor Parcel Number"), col(df, "NOD Apn"))
    leads["property_address"] = (
        col(df, "Property Full Street Address") + ", " +
        col(df, "Property City Name") + ", " +
        col(df, "Property State") + " " +
        col(df, "Property Zipcode")
    )
    leads["county"] = col(df, "County")
    leads["state"] = first_nonblank(col(df, "Property State"), pd.Series(["GA"] * len(df), index=df.index))
    leads["seed_record_type"] = col(df, "Document Type Code Description").apply(classify_doc_type)
    leads["phone"] = first_matching_col(df, PHONE_COLUMN_CANDIDATES).apply(format_phone)
    leads["email"] = first_matching_col(df, EMAIL_COLUMN_CANDIDATES)
    leads["all_phones"] = collect_multi(df, MULTI_PHONE_COLUMNS, formatter=format_phone)
    leads["all_emails"] = collect_multi(df, MULTI_EMAIL_COLUMNS)
    leads["bedrooms"] = col(df, "Bedrooms")
    leads["baths"] = col(df, "Baths")
    leads["sqft"] = col(df, "Sq Ft")
    leads["lot_size"] = col(df, "Lotsize")
    leads["year_built"] = col(df, "Year Built")
    leads["assessed_value"] = col(df, "Assessed Value")
    leads["equity_percent"] = col(df, "Equity")
    leads["unpaid_balance"] = col(df, "Unpaid Balance")
    leads["original_loan_amount"] = col(df, "Original Loan Amount")
    leads["mortgage_recording_date"] = col(df, "Loan Recording Date")
    return leads


def convert_successor(df: pd.DataFrame) -> pd.DataFrame:
    """Handles the successor/pre-probate provider export schema (Owner Name, Age, Group Tag, etc.)
    - every row seeds as successor-level distress."""
    leads = pd.DataFrame()
    leads["owner_name"] = col(df, "Owner Name")
    leads["parcel_id"] = col(df, "Parcel No")
    leads["property_address"] = (
        col(df, "Property Address") + ", " +
        col(df, "Property City") + ", " +
        col(df, "Property State") + " " +
        col(df, "Property Zip")
    )
    leads["county"] = col(df, "Property County")
    leads["state"] = first_nonblank(col(df, "Property State"), pd.Series(["GA"] * len(df), index=df.index))
    leads["seed_record_type"] = "successor"
    leads["phone"] = first_matching_col(df, PHONE_COLUMN_CANDIDATES).apply(format_phone)
    leads["email"] = first_matching_col(df, EMAIL_COLUMN_CANDIDATES)
    leads["all_phones"] = collect_multi(df, MULTI_PHONE_COLUMNS, formatter=format_phone)
    leads["all_emails"] = collect_multi(df, MULTI_EMAIL_COLUMNS)
    leads["bedrooms"] = ""
    leads["baths"] = ""
    leads["sqft"] = col(df, "Gross Area")
    leads["lot_size"] = col(df, "Lot Area")
    leads["year_built"] = col(df, "Year Built")
    leads["assessed_value"] = col(df, "Assessed Value")
    leads["equity_percent"] = ""
    leads["unpaid_balance"] = ""
    leads["original_loan_amount"] = ""
    leads["mortgage_recording_date"] = ""
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
            fillable = [f for f in LEAD_FIELDS if f not in ("owner_name", "property_address", "seed_record_type")]
            for field in fillable:
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

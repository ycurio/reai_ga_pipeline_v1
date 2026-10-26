"""Enrich an existing leads CSV with phone/email via DataZapp's skip-trace append API,
for leads that don't already have contact info from an upstream skip-traced export.

DataZapp gates their API docs behind a sales contact (api@datazapp.com per their
knowledge base) - the endpoint path and response field names below are inferred from
their public examples and must be confirmed against the real spec once credentials
are issued.
"""
from __future__ import annotations
import argparse
import csv
import os
from pathlib import Path

from reai.convert_leads import format_phone, SEED_TYPE_DELIM
from reai.http import session_with_retries
from reai.name_utils import parse_owner_name


def needs_append(row: dict) -> bool:
    return not (row.get("phone") or "").strip() and not (row.get("email") or "").strip()


def split_address(property_address: str | None) -> dict:
    """property_address is stored as 'street, city, state zip' by convert_leads.py."""
    parts = [p.strip() for p in (property_address or "").split(",")]
    street = parts[0] if len(parts) > 0 else ""
    city = parts[1] if len(parts) > 1 else ""
    state_zip = parts[2].split() if len(parts) > 2 else []
    state = state_zip[0] if state_zip else ""
    zip_code = state_zip[1] if len(state_zip) > 1 else ""
    return {"Address": street, "City": city, "State": state, "Zip": zip_code}


def to_request_row(row: dict) -> dict:
    name_fields = parse_owner_name(row.get("owner_name") or "")
    request = {
        "FirstName": name_fields.get("firstName", ""),
        "LastName": name_fields.get("lastName", ""),
    }
    request.update(split_address(row.get("property_address")))
    return request


class DataZappClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("DATAZAPP_API_KEY")
        self.base_url = base_url or os.getenv("DATAZAPP_BASE_URL", "https://api.datazapp.com/v1")
        self.http = session_with_retries()

    def append_batch(self, rows: list[dict]) -> list[dict]:
        if not self.api_key:
            raise RuntimeError("Missing DATAZAPP_API_KEY")
        if not rows:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"records": [to_request_row(r) for r in rows]}
        r = self.http.post(f"{self.base_url}/append/phone", json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json().get("records", [])


def merge_match(row: dict, match: dict) -> None:
    phone = format_phone(match.get("Phone") or "")
    email = match.get("Email") or ""
    if phone:
        row["phone"] = row.get("phone") or phone
        existing = [p for p in (row.get("all_phones") or "").split(SEED_TYPE_DELIM) if p]
        if phone not in existing:
            row["all_phones"] = SEED_TYPE_DELIM.join(existing + [phone])
    if email:
        row["email"] = row.get("email") or email
        existing = [e for e in (row.get("all_emails") or "").split(SEED_TYPE_DELIM) if e]
        if email not in existing:
            row["all_emails"] = SEED_TYPE_DELIM.join(existing + [email])


def enrich_leads(rows: list[dict], client: DataZappClient) -> int:
    """Mutate rows in place, filling phone/email for leads that had neither. Returns matched count."""
    targets = [r for r in rows if needs_append(r)]
    matches = client.append_batch(targets)
    matched_count = 0
    for row, match in zip(targets, matches):
        if match.get("Phone") or match.get("Email"):
            merge_match(row, match)
            matched_count += 1
    return matched_count


def main():
    p = argparse.ArgumentParser(description="Enrich a leads CSV with phone/email via DataZapp")
    p.add_argument("leads_csv", nargs="?", default="leads.csv", help="Path to leads CSV (default: leads.csv)")
    p.add_argument("-o", "--output", help="Output path (default: overwrite input in place)")
    args = p.parse_args()

    path = Path(args.leads_csv)
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    total_needing = sum(1 for r in rows if needs_append(r))
    matched_count = enrich_leads(rows, DataZappClient())

    out_path = Path(args.output) if args.output else path
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Matched {matched_count} of {total_needing} leads needing contact info -> {out_path}")


if __name__ == "__main__":
    main()

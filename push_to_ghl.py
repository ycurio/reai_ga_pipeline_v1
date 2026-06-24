"""Push scored leads into GoHighLevel as Contacts, tagged by distress signal.

NOTE: live-tested successfully on 2026-06-21 - the upsert endpoint, Bearer token auth,
and core body fields (name, phone, email, address, tags) are confirmed working against
a real account. customFields remains UNVERIFIED (no field IDs configured yet, so none
were sent in that test) - confirm the {"id": ..., "value": ...} shape once you fill in
CUSTOM_FIELD_IDS below.

Custom fields must exist in your GHL location first (Settings -> Custom Fields) -
GHL's API keys customFields by field ID, not name, so fill in CUSTOM_FIELD_IDS below
with the real IDs from your location before they'll actually populate.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from reai.http import session_with_retries
from reai.name_utils import parse_owner_name

GHL_BASE_URL = "https://services.leadconnectorhq.com"
GHL_API_VERSION = "2021-07-28"

# Fill in with real custom field IDs from your GHL location. Leave blank to skip.
CUSTOM_FIELD_IDS = {
    "distress_score": "",
    "record_types": "",
    "county": "",
    "assessed_value": "",
    "equity_percent": "",
}


def score_tier(score: int) -> str:
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def split_property_address(property_address: str | None) -> dict:
    """property_address is built as 'street, city, state zip' by convert_leads.py."""
    if not property_address:
        return {"address1": "", "city": "", "state": "", "postalCode": ""}
    parts = [p.strip() for p in property_address.split(",")]
    address1 = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""
    state, _, postal_code = (parts[2] if len(parts) > 2 else "").strip().partition(" ")
    return {"address1": address1, "city": city, "state": state, "postalCode": postal_code}


def build_contact_payload(item: dict, location_id: str) -> dict:
    lead = item["lead"]
    parsed_name = parse_owner_name(lead.get("owner_name") or "")
    record_types = sorted({r["record_type"] for r in item["records"]})

    tags = [f"distress:{score_tier(item['score'])}"] + [f"type:{t}" for t in record_types]

    values = {
        "distress_score": str(item["score"]),
        "record_types": ", ".join(record_types),
        "county": lead.get("county") or "",
        "assessed_value": lead.get("assessed_value") or "",
        "equity_percent": lead.get("equity_percent") or "",
    }
    custom_fields = [
        {"id": field_id, "value": values[key]}
        for key, field_id in CUSTOM_FIELD_IDS.items() if field_id
    ]

    payload = {
        "locationId": location_id,
        "firstName": parsed_name.get("firstName", ""),
        "lastName": parsed_name.get("lastName", ""),
        "phone": lead.get("phone") or None,
        "email": lead.get("email") or None,
        "tags": tags,
        "customFields": custom_fields,
        "source": "REAI Pipeline",
    }
    payload.update(split_property_address(lead.get("property_address")))
    return payload


def push_contact(session, payload: dict, api_key: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Version": GHL_API_VERSION,
        "Content-Type": "application/json",
    }
    r = session.post(f"{GHL_BASE_URL}/contacts/upsert", json=payload, headers=headers, timeout=30)
    if not r.ok:
        print(f"GHL error {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="Push scored leads into GoHighLevel as Contacts")
    p.add_argument("--input", default="data/output/results.json")
    p.add_argument("--min-score", type=int, default=0, help="Only push leads scoring at or above this")
    p.add_argument("--limit", type=int, default=None, help="Only push the first N matching leads")
    p.add_argument("--live", action="store_true", help="Actually call the GHL API (default is dry-run print)")
    p.add_argument("--api-key", default=os.getenv("GHL_TOKEN"),
                    help="GHL Location API key / Private Integration token (default: GHL_TOKEN env var)")
    p.add_argument("--location-id", default=os.getenv("GHL_LOCATION_ID"),
                    help="GHL location ID (default: GHL_LOCATION_ID env var)")
    args = p.parse_args()

    if args.live and (not args.api_key or not args.location_id):
        p.error("--live requires --api-key/GHL_TOKEN and --location-id/GHL_LOCATION_ID")

    results = json.loads(Path(args.input).read_text())
    candidates = [item for item in results if item["score"] >= args.min_score]
    candidates.sort(key=lambda item: item["score"], reverse=True)
    if args.limit is not None:
        candidates = candidates[:args.limit]

    session = session_with_retries() if args.live else None

    for item in candidates:
        payload = build_contact_payload(item, args.location_id or "DRY-RUN-LOCATION-ID")
        if args.live:
            result = push_contact(session, payload, args.api_key)
            contact_id = result.get("contact", {}).get("id", "ok")
            print(f"pushed {payload['firstName']} {payload['lastName']} (score {item['score']}) -> {contact_id}")
        else:
            print(json.dumps(payload, indent=2))

    mode = "live" if args.live else "dry-run"
    print(f"\n{len(candidates)} leads processed in {mode} mode (min_score={args.min_score})")


if __name__ == "__main__":
    main()

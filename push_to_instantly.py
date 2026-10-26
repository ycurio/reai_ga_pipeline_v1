"""Push scored leads into Instantly.ai as campaign/list leads, with every lead and
record field carried over as a custom_variable.

Instantly requires `email` on a lead to add it to a campaign, so leads without one
are skipped (count reported at the end) - this mirrors the all_phones/all_emails
fields convert_leads.py already produces, just enforced by Instantly's API itself.

NOTE: untested against a real Instantly account - confirm the /leads/add request/response
shape and your workspace's custom_variables field names once you have an API key.
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv

from reai.http import session_with_retries
from reai.name_utils import parse_owner_name

INSTANTLY_BASE_URL = "https://api.instantly.ai"

LEAD_FIELDS = [
    "owner_name", "parcel_id", "property_address", "mailing_address", "county", "state",
    "all_phones", "all_emails", "bedrooms", "baths", "sqft", "lot_size",
    "year_built", "assessed_value", "equity_percent", "unpaid_balance",
    "original_loan_amount", "mortgage_recording_date",
    "auction_date", "auction_time", "auction_city", "past_due_amount",
    "trustee_name", "trustee_phone", "contact_phone",
]

RECORD_FIELDS = [
    "source", "record_type", "filing_date", "amount", "status", "case_number",
    "instrument_number", "book", "page", "raw_reference", "raw_url", "confidence",
]


def join_record_field(records: list[dict], field: str) -> str:
    values = [str(r[field]) for r in records if r.get(field) not in (None, "")]
    return "|".join(values)


def build_custom_variables(item: dict) -> dict:
    lead = item["lead"]
    records = item["records"]

    custom_variables: dict = {field: lead.get(field) or "" for field in LEAD_FIELDS}
    custom_variables["seed_record_types"] = ", ".join(lead.get("seed_record_types") or [])
    custom_variables["distress_score"] = item["score"]

    for field in RECORD_FIELDS:
        custom_variables[f"record_{field}"] = join_record_field(records, field)

    return custom_variables


def build_lead_payload(item: dict) -> dict:
    lead = item["lead"]
    parsed_name = parse_owner_name(lead.get("owner_name") or "")

    return {
        "first_name": parsed_name.get("firstName", ""),
        "last_name": parsed_name.get("lastName", ""),
        "email": lead.get("email"),
        "phone": lead.get("phone") or None,
        "custom_variables": build_custom_variables(item),
    }


def persist_payloads(payloads: list[dict], outdir: Path, mode: str) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    payload_path = outdir / "instantly_payloads.json"
    payload_path.write_text(json.dumps(payloads, indent=2))
    return payload_path


def append_push_log(log_path: Path, entry: dict) -> None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def persist_to_postgres(payloads: list[dict], batch_no: int, mode: str, campaign_id: str | None,
                        list_id: str | None, min_score: int, input_path: str, response: dict | None) -> bool:
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        return False

    try:
        from psycopg import connect
    except ImportError:
        print("Postgres persistence skipped: psycopg is not installed")
        return False

    try:
        with connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS instantly_pushes (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    mode TEXT NOT NULL,
                    batch_no INT NOT NULL,
                    campaign_id TEXT,
                    list_id TEXT,
                    lead_email TEXT,
                    payload JSONB NOT NULL,
                    response JSONB,
                    input_file TEXT,
                    min_score INT,
                    status TEXT NOT NULL
                )
            """)
            for payload in payloads:
                cur.execute(
                    """
                    INSERT INTO instantly_pushes (
                        mode, batch_no, campaign_id, list_id, lead_email, payload, response,
                        input_file, min_score, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        mode,
                        batch_no,
                        campaign_id,
                        list_id,
                        payload.get("email"),
                        json.dumps(payload),
                        json.dumps(response) if response is not None else None,
                        input_path,
                        min_score,
                        "sent" if mode == "live" else "dry-run",
                    ),
                )
            conn.commit()
        return True
    except Exception as exc:
        print(f"Postgres persistence failed: {exc}")
        return False


def push_leads(session, payloads: list[dict], api_key: str, campaign_id: str | None, list_id: str | None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {"leads": payloads, "skip_if_in_campaign": True}
    if campaign_id:
        body["campaign_id"] = campaign_id
    if list_id:
        body["list_id"] = list_id

    r = session.post(f"{INSTANTLY_BASE_URL}/api/v2/leads/add", json=body, headers=headers, timeout=60)
    if not r.ok:
        print(f"Instantly error {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def main():
    load_dotenv(override=True)
    p = argparse.ArgumentParser(description="Push scored leads into Instantly.ai as leads")
    p.add_argument("--input", default="data/output/results.json")
    p.add_argument("--min-score", type=int, default=0, help="Only push leads scoring at or above this")
    p.add_argument("--limit", type=int, default=None, help="Only push the first N matching leads")
    p.add_argument("--batch-size", type=int, default=1000, help="Instantly allows up to 1000 leads per request")
    p.add_argument("--live", action="store_true", help="Actually call the Instantly API (default is dry-run print)")
    p.add_argument("--api-key", default=None,
                    help="Instantly API key (default: INSTANTLY_API_KEY env var)")
    p.add_argument("--campaign-id", default=None,
                    help="Target campaign ID (default: INSTANTLY_CAMPAIGN_ID env var)")
    p.add_argument("--list-id", default=None,
                    help="Target list ID, use instead of --campaign-id (default: INSTANTLY_LIST_ID env var)")
    args = p.parse_args()

    args.api_key = args.api_key or os.getenv("INSTANTLY_API_KEY")
    args.campaign_id = args.campaign_id or os.getenv("INSTANTLY_CAMPAIGN_ID")
    args.list_id = args.list_id or os.getenv("INSTANTLY_LIST_ID")

    if not args.campaign_id and not args.list_id:
        p.error("Must provide --campaign-id/INSTANTLY_CAMPAIGN_ID or --list-id/INSTANTLY_LIST_ID")
    if args.campaign_id and args.list_id:
        p.error("Provide only one of --campaign-id or --list-id, not both")
    if args.campaign_id and not is_uuid(args.campaign_id):
        p.error("--campaign-id/INSTANTLY_CAMPAIGN_ID must be a valid UUID from Instantly")
    if args.list_id and not is_uuid(args.list_id):
        p.error("--list-id/INSTANTLY_LIST_ID must be a valid UUID from Instantly")
    if args.live and not args.api_key:
        p.error("--live requires --api-key/INSTANTLY_API_KEY")

    results = json.loads(Path(args.input).read_text())
    candidates = [item for item in results if item["score"] >= args.min_score]
    candidates.sort(key=lambda item: item["score"], reverse=True)
    if args.limit is not None:
        candidates = candidates[:args.limit]

    skipped_no_email = [item for item in candidates if not item["lead"].get("email")]
    candidates = [item for item in candidates if item["lead"].get("email")]

    payloads = [build_lead_payload(item) for item in candidates]

    input_path = Path(args.input)
    outdir = input_path.parent if input_path.parent.exists() else Path("data/output")
    payload_path = persist_payloads(payloads, outdir, "live" if args.live else "dry-run")
    log_path = outdir / "instantly_push_log.jsonl"

    if args.live:
        session = session_with_retries()
        for i in range(0, len(payloads), args.batch_size):
            batch = payloads[i:i + args.batch_size]
            result = push_leads(session, batch, args.api_key, args.campaign_id, args.list_id)
            batch_no = i // args.batch_size + 1
            append_push_log(log_path, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "live",
                "batch": batch_no,
                "count": len(batch),
                "campaign_id": args.campaign_id,
                "list_id": args.list_id,
                "payloads": batch,
                "response": result,
            })
            persisted_to_db = persist_to_postgres(batch, batch_no, "live", args.campaign_id, args.list_id,
                                                  args.min_score, args.input, result)
            if persisted_to_db:
                print(f"persisted batch {batch_no} to Postgres")
            print(f"batch {batch_no}: uploaded={result.get('leads_uploaded')} "
                  f"duplicates={result.get('duplicated_leads')} invalid={result.get('invalid_email_count')} "
                  f"in_blocklist={result.get('in_blocklist')}")
    else:
        for payload in payloads:
            print(json.dumps(payload, indent=2))
        append_push_log(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "dry-run",
            "batch": 1,
            "count": len(payloads),
            "campaign_id": args.campaign_id,
            "list_id": args.list_id,
            "payloads": payloads,
            "response": None,
        })
        persisted_to_db = persist_to_postgres(payloads, 1, "dry-run", args.campaign_id, args.list_id,
                                              args.min_score, args.input, None)
        if persisted_to_db:
            print("persisted dry-run payloads to Postgres")

    mode = "live" if args.live else "dry-run"
    print(f"\n{len(payloads)} leads processed in {mode} mode (min_score={args.min_score}), "
          f"{len(skipped_no_email)} skipped for missing email")
    print(f"persisted payload snapshot -> {payload_path}")
    print(f"persisted push log -> {log_path}")


if __name__ == "__main__":
    main() 

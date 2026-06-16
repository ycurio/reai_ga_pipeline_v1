from __future__ import annotations
import os
from reai.http import session_with_retries
from reai.models import LeadKey, RecordType, SourceHealth, SourceRecord
from reai.sources.base import SourceAdapter


class PacerBankruptcyAdapter(SourceAdapter):
    name = "PACER_BANKRUPTCY"

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("PACER_BASE_URL", "https://pcl.uscourts.gov/pcl-public-api/rest")
        self.username = os.getenv("PACER_USERNAME")
        self.password = os.getenv("PACER_PASSWORD")
        self.client_code = os.getenv("PACER_CLIENT_CODE", "REAI-GA-PIPELINE")
        self.http = session_with_retries()

    def healthcheck(self) -> SourceHealth:
        if not self.username or not self.password:
            return SourceHealth(source=self.name, ok=False, message="Missing PACER credentials")
        return SourceHealth(source=self.name, ok=True, message="credentials present; live search not run")

    def search(self, lead: LeadKey) -> list[SourceRecord]:
        if not lead.owner_name:
            return []
        if not self.username or not self.password:
            raise RuntimeError("Missing PACER_USERNAME/PACER_PASSWORD")

        # PACER PCL API payloads should be confirmed against your account's current PCL API guide.
        # Keep endpoint configurable so you can adjust without changing code.
        url = f"{self.base_url}/parties/find"
        payload = {
            "lastNameOrBusinessName": lead.owner_name,
            "courtType": "bankruptcy",
            "state": "GA",
            "clientCode": self.client_code,
        }
        r = self.http.post(url, json=payload, auth=(self.username, self.password), timeout=60)
        r.raise_for_status()
        data = r.json()
        records = []
        for item in data.get("content", data.get("parties", [])):
            records.append(SourceRecord(
                source=self.name, record_type=RecordType.bankruptcy, county=lead.county,
                owner_name=lead.owner_name, parcel_id=lead.parcel_id, property_address=lead.property_address,
                filing_date=item.get("dateFiled") or item.get("filedDate"),
                status=item.get("caseStatus"), case_number=item.get("caseNumber"),
                raw_reference=item.get("courtId"), raw=item, confidence=0.75
            ))
        return records

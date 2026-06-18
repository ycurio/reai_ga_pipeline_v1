from __future__ import annotations
import os
from reai.http import session_with_retries
from reai.models import LeadKey, RecordType, SourceHealth, SourceRecord
from reai.sources.base import SourceAdapter


class PacerBankruptcyAdapter(SourceAdapter):
    name = "PACER_BANKRUPTCY"

    # Georgia bankruptcy court IDs
    GA_COURTS = ["ganbk", "gasbk", "gambk"]

    def __init__(self, base_url: str | None = None):
        self.pcl_base = base_url or os.getenv(
            "PACER_BASE_URL", "https://pcl.uscourts.gov/pcl-public-api/rest"
        )
        self.auth_url = os.getenv(
            "PACER_AUTH_URL", "https://pacer.login.uscourts.gov/services/cso-auth"
        )
        self.username = os.getenv("PACER_USERNAME")
        self.password = os.getenv("PACER_PASSWORD")
        self.client_code = os.getenv("PACER_CLIENT_CODE", "REAI-GA-PIPELINE")
        self.http = session_with_retries()
        self._token: str | None = None

    def _authenticate(self) -> str:
        """Get X-NEXT-GEN-CSO token from PACER authentication service."""
        payload = {
            "loginId": self.username,
            "password": self.password,
            "clientCode": self.client_code,
        }
        r = self.http.post(
            self.auth_url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        login_result = data.get("loginResult", "")
        if str(login_result) != "0":
            error_desc = data.get("errorDescription", "Unknown error")
            raise RuntimeError(
                f"PACER auth failed (loginResult={login_result}): {error_desc}"
            )
        token = data.get("nextGenCSO")
        if not token:
            raise RuntimeError("PACER auth returned no nextGenCSO token")
        self._token = token
        return token

    def _get_token(self) -> str:
        """Return cached token or authenticate."""
        if self._token:
            return self._token
        return self._authenticate()

    def healthcheck(self) -> SourceHealth:
        if not self.username or not self.password:
            return SourceHealth(
                source=self.name, ok=False, message="Missing PACER credentials"
            )
        try:
            self._authenticate()
            return SourceHealth(
                source=self.name, ok=True, message="Authenticated successfully"
            )
        except Exception as e:
            return SourceHealth(source=self.name, ok=False, message=f"Auth failed: {e}")

    def search(self, lead: LeadKey) -> list[SourceRecord]:
        if not lead.owner_name:
            return []
        if not self.username or not self.password:
            raise RuntimeError("Missing PACER_USERNAME/PACER_PASSWORD")

        token = self._get_token()

        # Use the full name as lastName — works for both persons and entities
        search_body: dict = {
            "lastName": lead.owner_name.strip(),
            "jurisdictionType": "bk",
            "courtCase": {
                "courtId": self.GA_COURTS,
            },
        }

        url = f"{self.pcl_base}/parties/find"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NEXT-GEN-CSO": token,
        }

        r = self.http.post(url, json=search_body, headers=headers, timeout=60)

        # If 401, token expired — re-authenticate and retry once
        if r.status_code == 401:
            token = self._authenticate()
            headers["X-NEXT-GEN-CSO"] = token
            r = self.http.post(url, json=search_body, headers=headers, timeout=60)

        r.raise_for_status()

        # Check for new token in response headers
        new_token = r.headers.get("X-NEXT-GEN-CSO")
        if new_token:
            self._token = new_token

        data = r.json()
        records = []
        for item in data.get("content", []):
            court_case = item.get("courtCase", {})
            records.append(
                SourceRecord(
                    source=self.name,
                    record_type=RecordType.bankruptcy,
                    county=lead.county,
                    owner_name=lead.owner_name,
                    parcel_id=lead.parcel_id,
                    property_address=lead.property_address,
                    filing_date=court_case.get("dateFiled") or item.get("dateFiled"),
                    status=item.get("caseStatus"),
                    case_number=court_case.get("caseNumberFull")
                    or item.get("caseNumberFull"),
                    raw_reference=court_case.get("courtId") or item.get("courtId"),
                    raw_url=court_case.get("caseLink"),
                    raw=item,
                    confidence=0.75,
                )
            )
        return records

from __future__ import annotations
import os
import re
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

    def _normalize(self, name: str) -> str:
        """Normalize a name for comparison: lowercase, strip suffixes and punctuation."""
        name = name.lower().strip()
        # Remove common suffixes
        for suffix in ['jr', 'sr', 'ii', 'iii', 'iv', 'v']:
            name = re.sub(rf'\b{suffix}\b', '', name)
        # Remove punctuation and extra spaces
        name = re.sub(r'[^a-z\s]', '', name)
        return ' '.join(name.split())

    def _name_matches(self, lead_name: str, pacer_result: dict) -> bool:
        """Check if a PACER result matches the lead's name closely enough.

        Matching strategy:
          - lastName must match exactly
          - firstName must match exactly (not just starts-with)
          - If middle initial is available, use it to further filter
        """
        parsed = self._parse_name(lead_name)
        search_last = self._normalize(parsed.get("lastName", ""))
        search_first = self._normalize(parsed.get("firstName", ""))
        search_middle = self._normalize(parsed.get("middleName", ""))

        result_last = self._normalize(pacer_result.get("lastName", ""))
        result_first = self._normalize(pacer_result.get("firstName", ""))
        result_middle = self._normalize(pacer_result.get("middleName", ""))

        # Last name must match exactly
        if search_last != result_last:
            return False

        # If we have a firstName, it must match exactly
        if search_first:
            if search_first != result_first:
                return False

        # If we have a middle initial/name, check it matches
        if search_middle and result_middle:
            # Compare first character (initial) at minimum
            if search_middle[0] != result_middle[0]:
                return False

        return True

    def _parse_name(self, owner_name: str) -> dict:
        """Parse owner_name into lastName, firstName, middleName for PACER search.

        Handles formats like:
          - 'Bynum Cynthia F' -> lastName=Bynum, firstName=Cynthia, middleName=F
          - 'Setzer Stephen A & Daughtry Martha T' -> lastName=Setzer, firstName=Stephen, middleName=A
          - 'ABC HOMES LLC' -> lastName=ABC HOMES LLC (entity, no firstName)
        """
        name = owner_name.strip()

        # Handle semicolons (multiple people listed)
        if ';' in name:
            name = name.split(';')[0].strip()

        # If contains '&', take only the first person
        if '&' in name:
            name = name.split('&')[0].strip()

        # Split into parts
        parts = name.split()

        if len(parts) == 1:
            # Single word — treat as entity or last name only
            return {"lastName": parts[0]}
        elif len(parts) >= 2:
            # Check if it looks like an entity (LLC, INC, CORP, TRUST, etc.)
            entity_indicators = ['LLC', 'INC', 'CORP', 'LTD', 'TRUST', 'ESTATE',
                                 'PROPERTIES', 'INVESTMENTS', 'HOLDINGS', 'GROUP',
                                 'PARTNERS', 'ASSOCIATION', 'BANK', 'COMPANY']
            upper_name = name.upper()
            if any(ind in upper_name for ind in entity_indicators):
                return {"lastName": name}
            else:
                # Assume format: LastName FirstName [MiddleInitial/MiddleName]
                result = {"lastName": parts[0], "firstName": parts[1]}
                if len(parts) >= 3:
                    result["middleName"] = parts[2]
                return result

        return {"lastName": name}

    def search(self, lead: LeadKey) -> list[SourceRecord]:
        if not lead.owner_name:
            return []
        if not self.username or not self.password:
            raise RuntimeError("Missing PACER_USERNAME/PACER_PASSWORD")

        token = self._get_token()

        # Parse name into lastName/firstName for PACER
        name_fields = self._parse_name(lead.owner_name)
        search_body: dict = {
            "lastName": name_fields["lastName"],
            "jurisdictionType": "bk",
            "exactNameMatch": True,
            "caseYearFrom": "2021",
            "courtCase": {
                "courtId": self.GA_COURTS,
            },
        }
        if "firstName" in name_fields:
            search_body["firstName"] = name_fields["firstName"]

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
        seen_cases = set()  # Deduplicate by case number

        for item in data.get("content", []):
            # Filter: only keep results that match the lead's name
            if not self._name_matches(lead.owner_name, item):
                continue

            court_case = item.get("courtCase", {})
            case_number = (
                court_case.get("caseNumberFull") or item.get("caseNumberFull") or ""
            )

            # Deduplicate: skip if we've already seen this case
            if case_number and case_number in seen_cases:
                continue
            seen_cases.add(case_number)

            # Assign confidence based on match quality
            result_first = (item.get("firstName") or "").lower()
            parsed = self._parse_name(lead.owner_name)
            search_first = (parsed.get("firstName") or "").lower()
            if search_first and result_first == search_first:
                confidence = 0.90
            elif search_first and result_first.startswith(search_first[:3]):
                confidence = 0.75
            else:
                confidence = 0.60

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
                    case_number=case_number,
                    raw_reference=court_case.get("courtId") or item.get("courtId"),
                    raw_url=court_case.get("caseLink"),
                    raw=item,
                    confidence=confidence,
                )
            )
        return records

"""Debug: test PACER search with actual lead name formats."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Authenticate
auth_url = "https://pacer.login.uscourts.gov/services/cso-auth"
payload = {
    "loginId": os.getenv("PACER_USERNAME"),
    "password": os.getenv("PACER_PASSWORD"),
    "clientCode": os.getenv("PACER_CLIENT_CODE", "REAI-GA-PIPELINE"),
}
r = requests.post(auth_url, json=payload,
                  headers={"Content-Type": "application/json", "Accept": "application/json"},
                  timeout=30)
token = r.json()["nextGenCSO"]
print(f"Authenticated OK\n")

# Test different name formats
test_names = [
    # Full name as-is from leads
    {"lastName": "Bynum Cynthia F", "jurisdictionType": "bk", "courtCase": {"courtId": ["ganbk", "gasbk", "gambk"]}},
    # Last name only
    {"lastName": "Bynum", "jurisdictionType": "bk", "courtCase": {"courtId": ["ganbk", "gasbk", "gambk"]}},
    # Last + first name split
    {"lastName": "Bynum", "firstName": "Cynthia", "jurisdictionType": "bk", "courtCase": {"courtId": ["ganbk", "gasbk", "gambk"]}},
    # Another lead
    {"lastName": "Setzer", "firstName": "Stephen", "jurisdictionType": "bk", "courtCase": {"courtId": ["ganbk", "gasbk", "gambk"]}},
]

pcl_url = "https://pcl.uscourts.gov/pcl-public-api/rest/parties/find"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-NEXT-GEN-CSO": token,
}

for body in test_names:
    r2 = requests.post(pcl_url, json=body, headers=headers, timeout=60)
    data = r2.json()
    total = data.get("pageInfo", {}).get("totalElements", 0)
    print(f"Search: {body.get('lastName','')}, {body.get('firstName','')} -> Status: {r2.status_code}, Results: {total}")
    if total > 0:
        first = data["content"][0]
        court_case = first.get("courtCase", {})
        print(f"  First match: {first.get('firstName','')} {first.get('lastName','')} | Case: {court_case.get('caseTitle','')} | Filed: {court_case.get('dateFiled','')}")
    print()

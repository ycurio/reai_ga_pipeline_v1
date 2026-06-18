"""Test PACER party search with a single lead."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Step 1: Authenticate
auth_url = "https://pacer.login.uscourts.gov/services/cso-auth"
payload = {
    "loginId": os.getenv("PACER_USERNAME"),
    "password": os.getenv("PACER_PASSWORD"),
    "clientCode": os.getenv("PACER_CLIENT_CODE", "REAI-GA-PIPELINE"),
}
r = requests.post(auth_url, json=payload,
                  headers={"Content-Type": "application/json", "Accept": "application/json"},
                  timeout=30)
data = r.json()
token = data["nextGenCSO"]
print(f"Got token: {token[:20]}...")
print()

# Step 2: Party search
pcl_url = "https://pcl.uscourts.gov/pcl-public-api/rest/parties/find"
search_body = {
    "lastName": "Bynum",
    "firstName": "Cynthia",
    "jurisdictionType": "bk",
    "courtCase": {
        "courtId": ["ganbk", "gasbk", "gambk"],
    },
}
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-NEXT-GEN-CSO": token,
}

print(f"Searching for: {search_body}")
print(f"URL: {pcl_url}")
print()

r2 = requests.post(pcl_url, json=search_body, headers=headers, timeout=60)
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text[:1000]}")

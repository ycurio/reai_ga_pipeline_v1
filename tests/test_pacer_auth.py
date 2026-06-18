"""Quick test to debug PACER authentication."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

auth_url = "https://pacer.login.uscourts.gov/services/cso-auth"
username = os.getenv("PACER_USERNAME")
password = os.getenv("PACER_PASSWORD")
client_code = os.getenv("PACER_CLIENT_CODE", "REAI-GA-PIPELINE")

print(f"Username: {username}")
print(f"Password: {'*' * len(password) if password else 'MISSING'}")
print(f"Client code: {client_code}")
print(f"Auth URL: {auth_url}")
print()

payload = {
    "loginId": username,
    "password": password,
    "clientCode": client_code,
}

print("Attempting authentication...")
try:
    r = requests.post(
        auth_url,
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30,
    )
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

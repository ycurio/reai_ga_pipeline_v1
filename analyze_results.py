"""Analyze pipeline results."""
import json

data = json.load(open("data/output/results.json"))
print(f"Total leads processed: {len(data)}")
print()

# Count leads with records found
with_records = [d for d in data if d.get("records")]
with_score = [d for d in data if d.get("score", 0) > 0]
errors = [d for d in data if any("error" in str(r.get("raw", "")) for r in d.get("records", []))]

print(f"Leads with bankruptcy matches: {len(with_records)}")
print(f"Leads with score > 0: {len(with_score)}")
print(f"Leads with errors: {len(errors)}")
print(f"Leads with no matches: {len(data) - len(with_records)}")
print()

# Show top scored leads
scored = sorted(data, key=lambda x: x.get("score", 0), reverse=True)
print("=== TOP SCORED LEADS ===")
count = 0
for item in scored:
    if item.get("score", 0) > 0:
        count += 1
        print(f"  Score: {item['score']} | {item['lead']['owner_name']} | {item['lead'].get('property_address','')}")
        for rec in item.get("records", []):
            if "error" not in str(rec.get("raw", "")):
                print(f"    -> {rec['record_type']} | Case: {rec.get('case_number','')} | Filed: {rec.get('filing_date','')}")
if count == 0:
    print("  (none)")
print()

# Show any errors
if errors:
    print("=== ERRORS ===")
    for item in errors[:5]:
        print(f"  {item['lead']['owner_name']}")
        for rec in item.get("records", []):
            raw = rec.get("raw", {})
            if "error" in str(raw):
                print(f"    Error: {raw}")

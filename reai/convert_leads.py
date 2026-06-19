"""Convert a GA SFR foreclosure/NOD Excel export to a pipeline-compatible leads CSV."""
import argparse
import pandas as pd

p = argparse.ArgumentParser(description="Convert GA SFR Excel export to a leads CSV")
p.add_argument("input", help="Path to the GA SFR .xlsx file")
p.add_argument("-o", "--output", default="leads.csv", help="Output CSV path (default: leads.csv)")
args = p.parse_args()

df = pd.read_excel(args.input)

# Build the leads CSV with required columns
leads = pd.DataFrame()
leads["owner_name"] = df["Current Owner Name"].str.strip()
leads["parcel_id"] = df["Assessor Parcel Number"].fillna(df["NOD Apn"]).fillna("").str.strip()
leads["property_address"] = (
    df["Property Full Street Address"].fillna("").str.strip() + ", " +
    df["Property City Name"].fillna("").str.strip() + ", " +
    df["Property State"].fillna("").str.strip() + " " +
    df["Property Zipcode"].fillna("").astype(str).str.strip()
)
leads["county"] = df["County"].fillna("").str.strip()
leads["state"] = df["Property State"].fillna("GA").str.strip()

# Drop rows with no owner name
leads = leads[leads["owner_name"].notna() & (leads["owner_name"] != "")]
leads = leads.reset_index(drop=True)

leads.to_csv(args.output, index=False)
print(f"Converted {len(leads)} leads to {args.output}")
print(leads.head(10).to_string())

"""Convert the uploaded dialer contacts Excel file to pipeline-compatible leads CSV."""
import pandas as pd

df = pd.read_excel("/home/ubuntu/upload/DialerContacts[June17,2026].xlsx")

# Build the leads CSV with required columns
leads = pd.DataFrame()
leads["owner_name"] = df["Full Name"].fillna(df["Last Name"]).str.strip()
leads["parcel_id"] = ""  # Not available in this dataset
leads["property_address"] = (
    df["Property Address"].fillna("").str.strip() + ", " +
    df["Property City"].fillna("").str.strip() + ", " +
    df["Property State"].fillna("").str.strip() + " " +
    df["Property Zip"].fillna("").astype(str).str.strip()
)
leads["county"] = ""  # Not available; PACER searches by state + name anyway
leads["state"] = df["Property State"].fillna("GA").str.strip()

# Drop rows with no owner name
leads = leads[leads["owner_name"].notna() & (leads["owner_name"] != "")]
leads = leads.reset_index(drop=True)

output_path = "/home/ubuntu/reai_ga_pipeline_v1/leads.csv"
leads.to_csv(output_path, index=False)
print(f"Converted {len(leads)} leads to {output_path}")
print(leads.head(10).to_string())

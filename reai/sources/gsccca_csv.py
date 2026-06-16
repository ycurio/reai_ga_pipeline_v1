from __future__ import annotations
import glob
from pathlib import Path
import pandas as pd
from reai.models import LeadKey, RecordType, SourceHealth, SourceRecord
from reai.sources.base import SourceAdapter


def classify_instrument(text: str | None) -> RecordType:
    t = (text or "").upper()
    if "LIS PENDENS" in t:
        return RecordType.lis_pendens
    if "DEED UNDER POWER" in t or "FORECLOSURE" in t:
        return RecordType.deed_under_power
    if "HOMEOWNER" in t or "HOA" in t or "CONDOMINIUM" in t or "PROPERTY OWNER" in t:
        return RecordType.hoa_lien
    if "MECHANIC" in t or "MATERIALMAN" in t:
        return RecordType.mechanics_lien
    if "TAX LIEN" in t or "STATE REVENUE" in t or "FEDERAL TAX" in t:
        return RecordType.tax_lien
    if "JUDG" in t:
        return RecordType.judgment
    return RecordType.unknown


class GSCCCAExportAdapter(SourceAdapter):
    name = "GSCCCA_EXPORT"

    def __init__(self, input_dir: str = "data/gsccca_exports"):
        self.input_dir = Path(input_dir)

    def healthcheck(self) -> SourceHealth:
        count = len(glob.glob(str(self.input_dir / "*.csv")))
        return SourceHealth(source=self.name, ok=self.input_dir.exists(), message=f"{count} CSV files found")

    def search(self, lead: LeadKey) -> list[SourceRecord]:
        files = glob.glob(str(self.input_dir / "*.csv"))
        if not files or not lead.owner_name:
            return []
        needles = [lead.owner_name.upper()]
        records: list[SourceRecord] = []
        for f in files:
            df = pd.read_csv(f, dtype=str).fillna("")
            cols = {c.lower().strip(): c for c in df.columns}
            searchable = df.astype(str).agg(" ".join, axis=1).str.upper()
            matched = df[searchable.apply(lambda row: any(n in row for n in needles))]
            for _, row in matched.iterrows():
                instrument = row.get(cols.get("instrument type", ""), "") if cols.get("instrument type") else row.to_string()
                records.append(SourceRecord(
                    source=self.name,
                    record_type=classify_instrument(instrument),
                    county=row.get(cols.get("county", ""), lead.county) if cols.get("county") else lead.county,
                    owner_name=lead.owner_name,
                    parcel_id=lead.parcel_id,
                    property_address=lead.property_address,
                    filing_date=row.get(cols.get("filing date", ""), None) or None,
                    amount=float(row.get(cols.get("amount", ""), "0").replace(",", "") or 0) if cols.get("amount") else None,
                    instrument_number=row.get(cols.get("instrument number", ""), None) if cols.get("instrument number") else None,
                    book=row.get(cols.get("book", ""), None) if cols.get("book") else None,
                    page=row.get(cols.get("page", ""), None) if cols.get("page") else None,
                    raw_reference=str(f), raw=row.to_dict(), confidence=0.7
                ))
        return records

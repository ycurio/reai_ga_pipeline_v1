from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterable
from pydantic import TypeAdapter
from reai.models import LeadKey, SourceRecord, RecordType
from reai.scoring import distress_score
from reai.sources.fema_nfhl import FemaNFHLAdapter
from reai.sources.pacer_bankruptcy import PacerBankruptcyAdapter
from reai.sources.gsccca_csv import GSCCCAExportAdapter


def default_sources(gsccca_dir: str = "data/gsccca_exports", include_pacer: bool = False, include_fema: bool = False):
    sources = []
    if include_fema:
        sources.append(FemaNFHLAdapter())
    sources.append(GSCCCAExportAdapter(gsccca_dir))
    if include_pacer:
        sources.append(PacerBankruptcyAdapter())
    return sources


def run_for_leads(leads: Iterable[LeadKey], sources=None) -> list[dict]:
    sources = sources or default_sources()
    output = []
    for lead in leads:
        records: list[SourceRecord] = []
        if lead.seed_record_type:
            records.append(SourceRecord(
                source="INTAKE_SEED", record_type=lead.seed_record_type,
                county=lead.county, state=lead.state, owner_name=lead.owner_name,
                parcel_id=lead.parcel_id, property_address=lead.property_address,
                confidence=1.0,
            ))
        for source in sources:
            try:
                records.extend(source.search(lead))
            except Exception as e:
                records.append(SourceRecord(source=source.name, owner_name=lead.owner_name,
                                            parcel_id=lead.parcel_id, property_address=lead.property_address,
                                            raw={"error": str(e)}))
        output.append({"lead": lead.model_dump(), "score": distress_score(records),
                       "records": [r.model_dump(mode="json") for r in records]})
    return output


def load_leads_csv(path: str) -> list[LeadKey]:
    rows = list(csv.DictReader(open(path, newline="")))
    for r in rows:
        if not r.get("seed_record_type"):
            r.pop("seed_record_type", None)
    return [LeadKey(**r) for r in rows]

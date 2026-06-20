from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class RecordType(str, Enum):
    parcel = "parcel"
    bankruptcy = "bankruptcy"
    hoa_lien = "hoa_lien"
    tax_lien = "tax_lien"
    mechanics_lien = "mechanics_lien"
    judgment = "judgment"
    lis_pendens = "lis_pendens"
    notice_of_default = "notice_of_default"
    deed_under_power = "deed_under_power"
    foreclosure = "foreclosure"
    probate = "probate"
    successor = "successor"
    flood = "flood"
    business_entity = "business_entity"
    unknown = "unknown"


class LeadKey(BaseModel):
    owner_name: Optional[str] = None
    parcel_id: Optional[str] = None
    property_address: Optional[str] = None
    county: Optional[str] = None
    state: str = "GA"
    seed_record_types: list[RecordType] = Field(default_factory=list)


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    record_type: RecordType = RecordType.unknown
    county: Optional[str] = None
    state: str = "GA"
    owner_name: Optional[str] = None
    parcel_id: Optional[str] = None
    property_address: Optional[str] = None
    mailing_address: Optional[str] = None
    filing_date: Optional[date] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    case_number: Optional[str] = None
    instrument_number: Optional[str] = None
    book: Optional[str] = None
    page: Optional[str] = None
    raw_reference: Optional[str] = None
    raw_url: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceHealth(BaseModel):
    source: str
    ok: bool
    message: str

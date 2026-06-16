from __future__ import annotations
from typing import Optional
from reai.http import session_with_retries
from reai.models import LeadKey, RecordType, SourceHealth, SourceRecord
from reai.sources.base import SourceAdapter


class FemaNFHLAdapter(SourceAdapter):
    name = "FEMA_NFHL"
    # Effective NFHL ArcGIS service. Layers can change; configure if needed.
    base_url = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"

    def __init__(self):
        self.http = session_with_retries()

    def healthcheck(self) -> SourceHealth:
        r = self.http.get(f"{self.base_url}?f=json", timeout=20)
        return SourceHealth(source=self.name, ok=r.ok, message=f"HTTP {r.status_code}")

    def search(self, lead: LeadKey) -> list[SourceRecord]:
        # Production note: FEMA query requires geometry. Ingest parcel centroid lat/lon from GIS/QPublic first.
        lat = getattr(lead, "lat", None)
        lon = getattr(lead, "lon", None)
        if lat is None or lon is None:
            return []
        layer = 28  # common NFHL flood hazard layer index; verify by service metadata.
        url = f"{self.base_url}/{layer}/query"
        params = {
            "f": "json",
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
        }
        data = self.http.get(url, params=params, timeout=30).json()
        out = []
        for feat in data.get("features", []):
            a = feat.get("attributes", {})
            out.append(SourceRecord(
                source=self.name, record_type=RecordType.flood,
                county=lead.county, parcel_id=lead.parcel_id, property_address=lead.property_address,
                status=a.get("FLD_ZONE") or a.get("ZONE_SUBTY"), raw=a, confidence=0.8
            ))
        return out

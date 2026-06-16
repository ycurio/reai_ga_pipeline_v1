from pathlib import Path
from reai.models import LeadKey, RecordType
from reai.sources.gsccca_csv import GSCCCAExportAdapter


def test_gsccca_export_matches_owner(tmp_path: Path):
    d = tmp_path / "exports"
    d.mkdir()
    (d / "lien.csv").write_text("County,Instrument Type,Name,Amount\nFulton,HOA LIEN,ABC HOMES LLC,1250\n")
    adapter = GSCCCAExportAdapter(str(d))
    results = adapter.search(LeadKey(owner_name="ABC HOMES LLC", county="Fulton"))
    assert len(results) == 1
    assert results[0].record_type == RecordType.hoa_lien
    assert results[0].amount == 1250

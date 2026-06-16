from reai.models import SourceRecord, RecordType
from reai.scoring import distress_score


def test_score_caps_at_100():
    records = [SourceRecord(source="x", record_type=t) for t in [
        RecordType.bankruptcy, RecordType.hoa_lien, RecordType.tax_lien,
        RecordType.lis_pendens, RecordType.deed_under_power, RecordType.probate
    ]]
    assert distress_score(records) == 100

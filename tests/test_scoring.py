from datetime import date
from reai.models import SourceRecord, RecordType
from reai.scoring import distress_score

AS_OF = date(2026, 6, 19)


def test_score_caps_at_100():
    records = [SourceRecord(source="x", record_type=t) for t in [
        RecordType.bankruptcy, RecordType.hoa_lien, RecordType.tax_lien,
        RecordType.lis_pendens, RecordType.deed_under_power, RecordType.probate
    ]]
    assert distress_score(records) == 100


def test_bankruptcy_base_weight_is_18():
    records = [SourceRecord(source="x", record_type=RecordType.bankruptcy)]
    assert distress_score(records, as_of=AS_OF) == 18


def test_bankruptcy_recency_bonus_tiers():
    recent = [SourceRecord(source="x", record_type=RecordType.bankruptcy, filing_date=date(2026, 5, 1))]   # 49 days
    mid = [SourceRecord(source="x", record_type=RecordType.bankruptcy, filing_date=date(2026, 1, 1))]       # 169 days
    old = [SourceRecord(source="x", record_type=RecordType.bankruptcy, filing_date=date(2025, 9, 1))]       # 291 days
    ancient = [SourceRecord(source="x", record_type=RecordType.bankruptcy, filing_date=date(2024, 1, 1))]   # >365 days

    assert distress_score(recent, as_of=AS_OF) == 18 + 15
    assert distress_score(mid, as_of=AS_OF) == 18 + 12
    assert distress_score(old, as_of=AS_OF) == 18 + 8
    assert distress_score(ancient, as_of=AS_OF) == 18


def test_repeat_filer_bonus():
    one = [SourceRecord(source="x", record_type=RecordType.bankruptcy, case_number="1")]
    two = [SourceRecord(source="x", record_type=RecordType.bankruptcy, case_number="1"),
           SourceRecord(source="x", record_type=RecordType.bankruptcy, case_number="2")]
    three = two + [SourceRecord(source="x", record_type=RecordType.bankruptcy, case_number="3")]

    assert distress_score(one, as_of=AS_OF) == 18
    assert distress_score(two, as_of=AS_OF) == 18 + 2
    assert distress_score(three, as_of=AS_OF) == 18 + 5


def test_stacking_bonus_for_distinct_distress_types():
    single = [SourceRecord(source="x", record_type=RecordType.foreclosure)]
    two_types = [SourceRecord(source="x", record_type=RecordType.foreclosure),
                 SourceRecord(source="x", record_type=RecordType.bankruptcy)]
    three_types = two_types + [SourceRecord(source="x", record_type=RecordType.lis_pendens)]

    assert distress_score(single, as_of=AS_OF) == 30
    assert distress_score(two_types, as_of=AS_OF) == 30 + 18 + 5
    assert distress_score(three_types, as_of=AS_OF) == 30 + 18 + 25 + 10

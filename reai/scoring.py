from __future__ import annotations
from collections import defaultdict
from reai.models import RecordType, SourceRecord

WEIGHTS = {
    RecordType.bankruptcy: 20,
    RecordType.hoa_lien: 18,
    RecordType.tax_lien: 18,
    RecordType.mechanics_lien: 12,
    RecordType.judgment: 12,
    RecordType.lis_pendens: 25,
    RecordType.notice_of_default: 15,
    RecordType.deed_under_power: 30,
    RecordType.foreclosure: 30,
    RecordType.probate: 20,
    RecordType.successor: 20,
    RecordType.flood: -8,
}


def distress_score(records: list[SourceRecord]) -> int:
    seen = set()
    score = 0
    for r in records:
        if r.record_type in seen:
            continue
        seen.add(r.record_type)
        score += WEIGHTS.get(r.record_type, 0)
    return max(0, min(100, score))

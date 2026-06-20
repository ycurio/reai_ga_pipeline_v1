from __future__ import annotations
from datetime import date
from reai.models import RecordType, SourceRecord

WEIGHTS = {
    RecordType.bankruptcy: 18,
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

# (max days since filing, bonus) - first matching tier wins
BANKRUPTCY_RECENCY_BONUS = [
    (90, 15),
    (180, 12),
    (365, 8),
]

# (min distinct bankruptcy filings, bonus) - highest matching tier wins
REPEAT_FILER_BONUS = [
    (3, 5),
    (2, 2),
]

# (min distinct distress record types found, bonus) - highest matching tier wins
STACKING_BONUS = [
    (3, 10),
    (2, 5),
]


def _highest_tier_bonus(tiers: list[tuple[int, int]], value: int) -> int:
    for threshold, bonus in tiers:
        if value >= threshold:
            return bonus
    return 0


def _bankruptcy_recency_bonus(bankruptcy_records: list[SourceRecord], as_of: date) -> int:
    filing_dates = [r.filing_date for r in bankruptcy_records if r.filing_date]
    if not filing_dates:
        return 0
    days_since_latest = (as_of - max(filing_dates)).days
    for max_days, bonus in BANKRUPTCY_RECENCY_BONUS:
        if days_since_latest <= max_days:
            return bonus
    return 0


def distress_score(records: list[SourceRecord], as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    seen = set()
    score = 0
    for r in records:
        if r.record_type in seen:
            continue
        seen.add(r.record_type)
        score += WEIGHTS.get(r.record_type, 0)

    bankruptcy_records = [r for r in records if r.record_type == RecordType.bankruptcy]
    score += _bankruptcy_recency_bonus(bankruptcy_records, as_of)
    score += _highest_tier_bonus(REPEAT_FILER_BONUS, len(bankruptcy_records))
    score += _highest_tier_bonus(STACKING_BONUS, len(seen))

    return max(0, min(100, score))

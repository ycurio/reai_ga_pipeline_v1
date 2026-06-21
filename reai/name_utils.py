"""Shared owner_name parsing for the "LastName FirstName [MiddleInitial]" format
used across the lead source exports (e.g. 'Reid Michelle S', 'ABC HOMES LLC')."""
from __future__ import annotations

ENTITY_INDICATORS = ['LLC', 'INC', 'CORP', 'LTD', 'TRUST', 'ESTATE',
                      'PROPERTIES', 'INVESTMENTS', 'HOLDINGS', 'GROUP',
                      'PARTNERS', 'ASSOCIATION', 'BANK', 'COMPANY']


def parse_owner_name(owner_name: str) -> dict:
    """Parse owner_name into lastName, firstName, middleName.

    Handles formats like:
      - 'Bynum Cynthia F' -> lastName=Bynum, firstName=Cynthia, middleName=F
      - 'Setzer Stephen A & Daughtry Martha T' -> lastName=Setzer, firstName=Stephen, middleName=A
      - 'ABC HOMES LLC' -> lastName=ABC HOMES LLC (entity, no firstName)
    """
    name = owner_name.strip()

    if ';' in name:
        name = name.split(';')[0].strip()
    if '&' in name:
        name = name.split('&')[0].strip()

    parts = name.split()

    if len(parts) == 1:
        return {"lastName": parts[0]}
    elif len(parts) >= 2:
        upper_name = name.upper()
        if any(ind in upper_name for ind in ENTITY_INDICATORS):
            return {"lastName": name}
        result = {"lastName": parts[0], "firstName": parts[1]}
        if len(parts) >= 3:
            result["middleName"] = parts[2]
        return result

    return {"lastName": name}

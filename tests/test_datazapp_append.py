from reai.datazapp_append import DataZappClient, enrich_leads, needs_append, split_address


def test_needs_append():
    assert needs_append({"phone": "", "email": ""})
    assert not needs_append({"phone": "+15551234567", "email": ""})
    assert not needs_append({"phone": "", "email": "a@b.com"})


def test_split_address():
    parsed = split_address("123 Main St, Atlanta, GA 30301")
    assert parsed == {"Address": "123 Main St", "City": "Atlanta", "State": "GA", "Zip": "30301"}


def test_enrich_leads_fills_matched_rows_only():
    rows = [
        {"owner_name": "Smith John", "property_address": "1 A St, Atlanta, GA 30301",
         "phone": "", "email": "", "all_phones": "", "all_emails": ""},
        {"owner_name": "Doe Jane", "property_address": "2 B St, Atlanta, GA 30301",
         "phone": "+15559998888", "email": "", "all_phones": "+15559998888", "all_emails": ""},
    ]

    class FakeClient(DataZappClient):
        def __init__(self):
            pass

        def append_batch(self, targets):
            assert len(targets) == 1
            return [{"Phone": "5551234567", "Email": "john@example.com"}]

    matched = enrich_leads(rows, FakeClient())

    assert matched == 1
    assert rows[0]["phone"] == "+15551234567"
    assert rows[0]["email"] == "john@example.com"
    assert rows[0]["all_phones"] == "+15551234567"
    assert rows[1]["phone"] == "+15559998888"

import responses
from reai.models import LeadKey
from reai.sources.pacer_bankruptcy import PacerBankruptcyAdapter

AUTH_URL = "https://pacer.login.uscourts.gov/services/cso-auth"
SEARCH_URL = "https://pcl.uscourts.gov/pcl-public-api/rest/parties/find"


def make_adapter(monkeypatch):
    monkeypatch.setenv("PACER_USERNAME", "user")
    monkeypatch.setenv("PACER_PASSWORD", "pass")
    return PacerBankruptcyAdapter()


def test_parse_name_person():
    adapter = PacerBankruptcyAdapter()
    assert adapter._parse_name("Bynum Cynthia F") == {
        "lastName": "Bynum", "firstName": "Cynthia", "middleName": "F"
    }


def test_parse_name_entity():
    adapter = PacerBankruptcyAdapter()
    assert adapter._parse_name("ABC HOMES LLC") == {"lastName": "ABC HOMES LLC"}


def test_name_matches_requires_exact_first_and_last():
    adapter = PacerBankruptcyAdapter()
    assert adapter._name_matches("Bynum Cynthia F", {
        "lastName": "Bynum", "firstName": "Cynthia", "middleName": "Faye"
    })
    assert not adapter._name_matches("Bynum Cynthia F", {
        "lastName": "Bynum", "firstName": "Cindy"
    })
    assert not adapter._name_matches("Bynum Cynthia F", {
        "lastName": "Smith", "firstName": "Cynthia"
    })


@responses.activate
def test_authenticate_raises_on_login_failure(monkeypatch):
    adapter = make_adapter(monkeypatch)
    responses.add(responses.POST, AUTH_URL, json={
        "loginResult": "1", "errorDescription": "Invalid credentials"
    }, status=200)
    try:
        adapter._authenticate()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "Invalid credentials" in str(e)


@responses.activate
def test_search_dedupes_and_filters_by_name(monkeypatch):
    adapter = make_adapter(monkeypatch)
    responses.add(responses.POST, AUTH_URL, json={
        "loginResult": "0", "nextGenCSO": "token-123"
    }, status=200)
    responses.add(responses.POST, SEARCH_URL, json={"content": [
        {"firstName": "Cynthia", "lastName": "Bynum",
         "courtCase": {"caseNumberFull": "1:24-bk-001", "dateFiled": "2024-01-01",
                       "courtId": "ganbk", "caseLink": "http://example.com/1"}},
        {"firstName": "Cynthia", "lastName": "Bynum",
         "courtCase": {"caseNumberFull": "1:24-bk-001", "dateFiled": "2024-01-01",
                       "courtId": "ganbk", "caseLink": "http://example.com/1"}},
        {"firstName": "Someone", "lastName": "Else",
         "courtCase": {"caseNumberFull": "1:24-bk-999", "dateFiled": "2024-01-01",
                       "courtId": "ganbk"}},
    ]}, status=200)

    results = adapter.search(LeadKey(owner_name="Bynum Cynthia F", county="Fulton"))

    assert len(results) == 1
    assert results[0].case_number == "1:24-bk-001"
    assert results[0].confidence == 0.90


@responses.activate
def test_search_reauthenticates_on_401(monkeypatch):
    adapter = make_adapter(monkeypatch)
    responses.add(responses.POST, AUTH_URL, json={
        "loginResult": "0", "nextGenCSO": "stale-token"
    }, status=200)
    responses.add(responses.POST, SEARCH_URL, json={}, status=401)
    responses.add(responses.POST, AUTH_URL, json={
        "loginResult": "0", "nextGenCSO": "fresh-token"
    }, status=200)
    responses.add(responses.POST, SEARCH_URL, json={"content": []}, status=200)

    results = adapter.search(LeadKey(owner_name="Bynum Cynthia F"))

    assert results == []
    assert len(responses.calls) == 4
    assert responses.calls[3].request.headers["X-NEXT-GEN-CSO"] == "fresh-token"

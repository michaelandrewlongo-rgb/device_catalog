"""Tests for source health reporting, AccessGUDID fix, and ClinicalTrials hardening."""

from unittest.mock import MagicMock, patch

import pytest

from pipeline.evidence.accessgudid import AccessGUDIDClient
from pipeline.evidence.clinical_trials import ClinicalTrialsClient, build_trials_query
from pipeline.evidence.models import SourceHealth, SourceType
from pipeline.evidence.registry import detect_potential_duplicates, identity_from_knowledge


# ---------------------------------------------------------------------------
# build_trials_query
# ---------------------------------------------------------------------------

def test_build_trials_query_quotes_terms():
    q = build_trials_query(["Pipeline Flex", "PED"])
    assert q == '"Pipeline Flex" OR "PED"'


def test_build_trials_query_single_term():
    assert build_trials_query(["Surpass Streamline"]) == '"Surpass Streamline"'


# ---------------------------------------------------------------------------
# AccessGUDIDClient - pageSize parameter
# ---------------------------------------------------------------------------

def _gudid_payload(brand_name="TestDevice", device_id="00123", company="Acme Inc"):
    return {
        "search_results": {
            "number_results": "1",
            "result": [
                {
                    "deviceIdentifier": "test-uuid-1234",
                    "brandName": brand_name,
                    "companyName": company,
                    "modelNumber": "M-001",
                    "ID": [{"deviceId": device_id, "type": "Primary"}],
                    "gmdnTerms": [{"termName": "Test device", "gmdnCode": "99999"}],
                }
            ],
        }
    }


def test_accessgudid_uses_correct_params():
    """Verify the client sends pageSize/pageNumber to the correct endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _gudid_payload()

    captured_params = {}
    captured_url = {}

    def fake_get(url, params=None, headers=None):
        captured_params.update(params or {})
        captured_url["url"] = url
        return mock_resp

    with patch("pipeline.evidence.accessgudid.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        client = AccessGUDIDClient()
        records = client.search("Pipeline", limit=5)

    assert "pageSize" in captured_params, "Client must use pageSize, not size"
    assert "size" not in captured_params
    assert captured_params["pageSize"] == 5
    assert "pageNumber" in captured_params
    assert "/api/" not in captured_url["url"], "Endpoint must not include /api/v2/ prefix"
    assert len(records) == 1
    assert records[0].source_type == SourceType.ACCESSGUDID
    # Title should include brand and company
    assert "TestDevice" in records[0].title
    assert "Acme Inc" in records[0].title
    # Source URL should point to the device UUID
    assert "test-uuid-1234" in records[0].source_url


def test_accessgudid_health_ok(tmp_path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _gudid_payload()

    with patch("pipeline.evidence.accessgudid.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = lambda *a, **kw: mock_resp
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        client = AccessGUDIDClient()
        records = client.search("Pipeline", device_family="flow-diverter--x", health_log=health_log)

    assert len(records) == 1
    assert len(health_log) == 1
    assert health_log[0].status == "ok"
    assert health_log[0].record_count == 1
    assert health_log[0].source_type == "accessgudid"


def test_accessgudid_health_empty():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"gudid": {"device": []}}

    with patch("pipeline.evidence.accessgudid.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = lambda *a, **kw: mock_resp
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = AccessGUDIDClient().search("Unknown Device", health_log=health_log)

    assert records == []
    assert health_log[0].status == "empty"
    assert health_log[0].record_count == 0


def test_accessgudid_health_http_error():
    import httpx

    with patch("pipeline.evidence.accessgudid.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(side_effect=httpx.RequestError("timeout"))
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = AccessGUDIDClient().search("Something", health_log=health_log)

    assert records == []
    assert health_log[0].status == "connection_error"
    assert health_log[0].http_status is None  # no HTTP response received


def test_accessgudid_unexpected_response_shape():
    """Guard fires when search_results.result exists but is not a list."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # result key present but not a list
    mock_resp.json.return_value = {"search_results": {"result": "unexpected_string"}}

    with patch("pipeline.evidence.accessgudid.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = lambda *a, **kw: mock_resp
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = AccessGUDIDClient().search("Device", health_log=health_log)

    assert records == []
    assert health_log[0].status == "unexpected_response"


# ---------------------------------------------------------------------------
# ClinicalTrialsClient - query.intr field + health
# ---------------------------------------------------------------------------

def _trials_payload(nct_id="NCT00000001", title="A Study of Device X"):
    return {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": nct_id,
                        "briefTitle": title,
                    },
                    "statusModule": {"overallStatus": "COMPLETED"},
                }
            }
        ]
    }


def test_clinicaltrials_uses_query_intr_first():
    """Client should hit query.intr before falling back to query.term."""
    captured_params_list = []

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _trials_payload()

    def fake_get(url, params=None, headers=None):
        captured_params_list.append(dict(params or {}))
        return mock_resp

    with patch("pipeline.evidence.clinical_trials.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        client = ClinicalTrialsClient()
        records = client.search('"Pipeline Flex"')

    # First call should use query.intr
    assert "query.intr" in captured_params_list[0]
    assert len(records) == 1
    assert records[0].source_type == SourceType.CLINICALTRIALS


def test_clinicaltrials_falls_back_to_term_when_intr_empty():
    """If query.intr returns no studies, fall back to query.term."""
    call_count = 0

    def fake_get(url, params=None, headers=None):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "query.intr" in (params or {}):
            mock_resp.json.return_value = {"studies": []}
        else:
            mock_resp.json.return_value = _trials_payload()
        return mock_resp

    with patch("pipeline.evidence.clinical_trials.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        records = ClinicalTrialsClient().search('"Pipeline Flex"')

    assert call_count == 2  # intr then term
    assert len(records) == 1


def test_clinicaltrials_403_shows_as_http_error_not_empty():
    """A 403 from the ClinicalTrials API should produce http_error in health, not empty."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("pipeline.evidence.clinical_trials.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = lambda *a, **kw: mock_resp
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = ClinicalTrialsClient().search('"Device"', health_log=health_log)

    assert records == []
    assert health_log[0].status == "http_error"
    assert health_log[0].http_status == 403


def test_clinicaltrials_health_logged():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _trials_payload()

    with patch("pipeline.evidence.clinical_trials.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = lambda *a, **kw: mock_resp
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = ClinicalTrialsClient().search(
            '"Pipeline"', device_family="flow-diverter--x", health_log=health_log
        )

    assert len(health_log) == 1
    assert health_log[0].status == "ok"
    assert health_log[0].record_count == 1
    assert not health_log[0].fallback_used


def test_clinicaltrials_fallback_recorded_in_health():
    """When query.intr returns empty and query.term succeeds, fallback_used=True."""
    def fake_get(url, params=None, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "query.intr" in (params or {}):
            mock_resp.json.return_value = {"studies": []}
        else:
            mock_resp.json.return_value = _trials_payload()
        return mock_resp

    with patch("pipeline.evidence.clinical_trials.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = fake_get
        mock_client_cls.return_value = mock_client

        health_log: list[SourceHealth] = []
        records = ClinicalTrialsClient().search('"Device"', health_log=health_log)

    assert len(health_log) == 1
    assert health_log[0].fallback_used is True
    assert health_log[0].status == "ok"


def test_pubmed_error_is_caught_and_logged():
    """Network errors in PubMedClient.search are caught and produce a health entry."""
    import httpx

    with patch("pipeline.evidence.pubmed.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = MagicMock(side_effect=httpx.RequestError("connection refused"))
        mock_client_cls.return_value = mock_client

        from pipeline.evidence.pubmed import PubMedClient
        health_log: list[SourceHealth] = []
        articles = PubMedClient().search("test query", health_log=health_log)

    assert articles == []
    assert len(health_log) == 1
    assert health_log[0].status == "connection_error"
    assert health_log[0].http_status is None


# ---------------------------------------------------------------------------
# detect_potential_duplicates
# ---------------------------------------------------------------------------

def _make_identity(category, manufacturer, product_slug, display_name):
    return identity_from_knowledge(category, manufacturer, product_slug, f"# {display_name}")


def test_detect_duplicates_slug_prefix():
    identities = [
        _make_identity("flow-diverter", "medtronic", "pipeline-embolization-device", "Pipeline"),
        _make_identity("flow-diverter", "medtronic", "pipeline-embolization-device-plus", "Pipeline Plus"),
    ]
    dupes = detect_potential_duplicates(identities)
    assert len(dupes) == 1
    assert dupes[0]["reason"] == "slug_prefix"


def test_detect_duplicates_no_cross_category():
    identities = [
        _make_identity("flow-diverter", "medtronic", "pipeline", "Pipeline Embolization Device"),
        _make_identity("aspiration", "medtronic", "pipeline-aspiration", "Pipeline Aspiration"),
    ]
    dupes = detect_potential_duplicates(identities)
    assert dupes == []


def test_detect_duplicates_name_overlap():
    identities = [
        _make_identity("flow-diverter", "stryker", "surpass-streamline", "Surpass Streamline Flow Diverter System"),
        _make_identity("flow-diverter", "stryker", "surpass-streamline-new", "Surpass Streamline Flow Diverter New"),
    ]
    dupes = detect_potential_duplicates(identities)
    # Both share "surpass", "streamline", "flow", "diverter" = 4 words → flagged
    assert len(dupes) >= 1


def test_detect_duplicates_distinct_devices():
    identities = [
        _make_identity("flow-diverter", "medtronic", "pipeline-flex", "Pipeline Flex"),
        _make_identity("flow-diverter", "stryker", "surpass-streamline", "Surpass Streamline"),
    ]
    dupes = detect_potential_duplicates(identities)
    assert dupes == []

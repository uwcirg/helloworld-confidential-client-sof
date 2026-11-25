"""Tests for response filters."""
import pytest
from unittest.mock import patch, MagicMock

from confidential_backend.response_filters.extracted_observation import ExtractedObservationFilter

APP_FHIR_URL = "http://app-fhir:8080"
IDENTIFIER_SYSTEM = "http://launch-fhir.example.org/fhir"


@pytest.fixture
def observation_filter():
    return ExtractedObservationFilter(
        app_fhir_url=APP_FHIR_URL,
        identifier_system=IDENTIFIER_SYSTEM,
    )


def _make_observation(obs_id):
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {"text": "test"},
    }


def _make_bundle(observations, next_url=None):
    bundle = {
        "resourceType": "Bundle",
        "total": len(observations),
        "entry": [{"resource": obs} for obs in observations],
    }
    if next_url:
        bundle["link"] = [{"relation": "next", "url": next_url}]
    return bundle


def _make_app_fhir_bundle(extracted_obs_ids):
    """Simulate the app FHIR server returning Observations stamped with upstream IDs."""
    entries = []
    for obs_id in extracted_obs_ids:
        entries.append({
            "resource": {
                "resourceType": "Observation",
                "id": f"app-{obs_id}",
                "identifier": [
                    {"system": IDENTIFIER_SYSTEM, "value": obs_id}
                ],
            }
        })
    return {
        "resourceType": "Bundle",
        "total": len(entries),
        "entry": entries,
    }


# --- applies_to ---

def test_applies_to_observation(observation_filter):
    assert observation_filter.applies_to("Observation") is True


def test_does_not_apply_to_other_resources(observation_filter):
    for resource_type in ("Patient", "Condition", "MedicationRequest", "Bundle"):
        assert observation_filter.applies_to(resource_type) is False


# --- single resource ---

@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_single_observation_not_extracted_passes_through(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle([])
    mock_get.return_value.raise_for_status = MagicMock()

    obs = _make_observation("obs-1")
    with app.app_context():
        result = observation_filter.filter(obs)

    assert result["resourceType"] == "Observation"
    assert result["id"] == "obs-1"


@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_single_observation_already_extracted_returns_empty_bundle(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle(["obs-1"])
    mock_get.return_value.raise_for_status = MagicMock()

    obs = _make_observation("obs-1")
    with app.app_context():
        result = observation_filter.filter(obs)

    assert result["resourceType"] == "Bundle"
    assert result["total"] == 0
    assert result["entry"] == []


# --- bundle filtering ---

@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_bundle_filters_extracted_observations(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle(["obs-1", "obs-3"])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([
        _make_observation("obs-1"),
        _make_observation("obs-2"),
        _make_observation("obs-3"),
    ])
    with app.app_context():
        result = observation_filter.filter(bundle)

    assert result["total"] == 1
    assert len(result["entry"]) == 1
    assert result["entry"][0]["resource"]["id"] == "obs-2"


@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_bundle_all_extracted_returns_empty(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle(["obs-1", "obs-2"])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([
        _make_observation("obs-1"),
        _make_observation("obs-2"),
    ])
    with app.app_context():
        result = observation_filter.filter(bundle)

    assert result["total"] == 0
    assert result["entry"] == []


@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_bundle_none_extracted_passes_through_unchanged(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle([])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([
        _make_observation("obs-1"),
        _make_observation("obs-2"),
    ])
    with app.app_context():
        result = observation_filter.filter(bundle)

    assert result["total"] == 2
    assert len(result["entry"]) == 2


@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_empty_bundle_passes_through(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle([])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([])
    with app.app_context():
        result = observation_filter.filter(bundle)

    # no app FHIR call needed for empty bundle
    mock_get.assert_not_called()
    assert result["total"] == 0


# --- app FHIR query correctness ---

@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_batch_query_uses_correct_identifier_params(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle([])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([
        _make_observation("obs-A"),
        _make_observation("obs-B"),
    ])
    with app.app_context():
        observation_filter.filter(bundle)

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert call_kwargs[0][0] == f"{APP_FHIR_URL}/Observation"
    identifier_param = call_kwargs[1]["params"]["identifier"]
    assert f"{IDENTIFIER_SYSTEM}|obs-A" in identifier_param
    assert f"{IDENTIFIER_SYSTEM}|obs-B" in identifier_param


# --- fail-open behavior ---

@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_app_fhir_failure_fails_open(mock_get, app, observation_filter):
    """If app FHIR is unreachable, return unfiltered results rather than raising."""
    import requests as req
    mock_get.side_effect = req.RequestException("connection refused")

    bundle = _make_bundle([
        _make_observation("obs-1"),
        _make_observation("obs-2"),
    ])
    with app.app_context():
        result = observation_filter.filter(bundle)

    # unfiltered results come through
    assert result["total"] == 2


# --- non-Observation entries in bundle are preserved ---

@patch("confidential_backend.response_filters.extracted_observation.requests.get")
def test_non_observation_entries_in_bundle_preserved(mock_get, app, observation_filter):
    mock_get.return_value.json.return_value = _make_app_fhir_bundle(["obs-1"])
    mock_get.return_value.raise_for_status = MagicMock()

    bundle = _make_bundle([_make_observation("obs-1")])
    bundle["entry"].append({"resource": {"resourceType": "Patient", "id": "pat-1"}})
    bundle["total"] = 2

    with app.app_context():
        result = observation_filter.filter(bundle)

    # obs-1 filtered, Patient preserved
    assert result["total"] == 1
    assert result["entry"][0]["resource"]["resourceType"] == "Patient"

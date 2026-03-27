"""Tests for multiple FHIR endpoints."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from confidential_backend.source_strategies.secondary_fhir_strategy import SecondaryFhirStrategy

launch_system = "http://launch/system/mrn"
app_system = "http://app/system/mrn"
app_fhir_url = "http://fhir:8080"
mrn = "be-12-fe"


@pytest.fixture
def launch_patient():
    return {
        "resourceType": "Patient",
        "id": "abc123",
        "identifier": [ {"system": launch_system, "value": mrn} ]
    }

@pytest.fixture
def app_patient():
    return {
        "resourceType": "Patient",
        "id": "different-from-launch-id",
        "identifier": [{"system": app_system, "value": mrn}]
    }


@patch("confidential_backend.source_strategies.secondary_fhir_strategy.requests.get")
def test_secondary_patient_lookup(mock_get, app, launch_patient, app_patient):
    search_result = {
        "resourceType": "Bundle",
        "total": 1,
        "entry": [
            {
                "resource": app_patient
            }
        ]
    }

    mock_response = mock_get.return_value
    mock_response.json.return_value = search_result
    mock_response.status_code = 200

    secondary_fhir_strategy = SecondaryFhirStrategy(
        name="TestStrategy",
        server_url=app_fhir_url,
        mrn_system=app_system,
        launch_mrn_systems=f"uri:bogus,{launch_system},http://silly.org",
    )
    with app.app_context():
        result = secondary_fhir_strategy.lookup_identified_patient(launch_patient)

    expected_url = '/'.join((app_fhir_url, "Patient"))
    expected_params = {"identifier": f"{app_system}|{mrn}"}
    mock_get.assert_called_once_with(expected_url, params=expected_params)
    assert result == app_patient


def test_secondary_patient_put(mocker, launch_patient, app_patient):
    mocker.patch(
        "confidential_backend.source_strategies.secondary_fhir_strategy.SecondaryFhirStrategy.translated_patient_id",
        return_value="different-from-launch-id",
    )

    secondary_fhir_strategy = SecondaryFhirStrategy(
        name="TestStrategy",
        server_url=app_fhir_url,
        mrn_system=app_system,
        launch_mrn_systems=f"{launch_system}",
    )
    resource = {
        "resourceType": "DocumentReference",
        "id": "docref1",
        "subject": {"reference": f"Patient/{launch_patient['id']}"},
        "author": [{"reference": f"Patient/{launch_patient['id']}"},]
    }

    result = secondary_fhir_strategy.adjust_patient_in_request_json(
        original_request_json=resource, launch_pid=launch_patient['id'])
    assert result['id'] == resource['id']
    assert result['subject']['reference'] == f"Patient/{app_patient['id']}"

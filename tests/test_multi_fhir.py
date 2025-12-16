"""Tests for multiple FHIR endpoints."""
from copy import deepcopy
from unittest.mock import patch
from confidential_backend.secondary_fhir_strategy import SecondaryFhirStrategy


@patch("confidential_backend.secondary_fhir_strategy.requests.get")
def test_secondary_patient_lookup(mock_get, app):
    launch_system = "http://launch/system/mrn"
    app_system = "http://app/system/mrn"
    app_fhir_url = "http://fhir:8080"
    mrn = "be-12-fe"
    launch_patient = {
        "resourceType": "Patient",
        "id": "abc123",
        "identifier": [ {"system": launch_system, "value": mrn} ]
    }
    app_patient = deepcopy(launch_patient)
    app_patient["identifier"] = [ {"system": app_system, "value": mrn} ]
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

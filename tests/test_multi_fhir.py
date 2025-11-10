"""Tests for multiple FHIR endpoints."""
from copy import deepcopy
from unittest.mock import patch
from confidential_backend.muli_fhir import lookup_identified_patient


@patch("confidential_backend.muli_fhir.requests.get")
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

    mock_response = mock_get.return_value
    mock_response.json.return_value = app_patient
    mock_response.status_code = 200

    app.config["LAUNCH_MRN_SYSTEM"] = launch_system
    app.config["APP_FHIR_MRN_SYSTEM"] = app_system
    app.config["APP_FHIR_URL"] = app_fhir_url

    with app.app_context():
        result = lookup_identified_patient(launch_patient)

    expected_url = '/'.join((app_fhir_url, "Patient"))
    expected_params = {"identifier": f"{app_system}|{mrn}"}
    mock_get.assert_called_once_with(expected_url, params=expected_params)
    assert result == app_patient

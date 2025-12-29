from pytest import fixture
from confidential_backend.source_strategies.secondary_fhir_strategy import SecondaryFhirStrategy

patient_A = "1234abcd"
patient_B = "abc"
server_url = "http://localhost/fhir"

@fixture
def second_strat(mocker) -> SecondaryFhirStrategy:
    strat = SecondaryFhirStrategy(name="testy", server_url=server_url)
    mocker.patch.object(strat, "translated_patient_id", return_value=patient_B)
    return strat


def test_no_patient_id(second_strat):
    path = f"/QuestionnaireResponse/17?subject=abc"
    improved = second_strat.adjust_patient_query(path, patient_A)
    assert improved == '/'.join((server_url, path))


def test_patient_id_inside_another_id(second_strat):
    """Query shouldn't get modified, even if patient id is part of a larger id"""
    id_with_embedded = (f"6f3-{patient_A}", f"{patient_A}abc", f"1{patient_A}2")
    for id in id_with_embedded:
        query = f"/Observation?code={id}"
        improved = second_strat.adjust_patient_query(query, patient_A)
        assert improved == '/'.join((server_url, query))


def test_patient_id_in_path(second_strat):
    query = f"random/Patient/{patient_A}"
    improved = second_strat.adjust_patient_query(query, patient_A)
    assert improved == '/'.join((server_url, query.replace(patient_A, patient_B)))


def test_matching_param_value(second_strat):
    query = f"random/Observation?patient={patient_A}"
    improved = second_strat.adjust_patient_query(query, patient_A)
    assert improved == '/'.join((server_url, query.replace(patient_A, patient_B)))


def test_embedded_patient_in_param_value(second_strat):
    # should replace only patient identifier, not the embedded match in the middle of a code value
    query = f"random/Observation?patient={patient_A}&code=tcfu{patient_A}Xqxw0"
    improved = second_strat.adjust_patient_query(query, patient_A)
    assert improved == '/'.join((server_url, query.replace(patient_A, patient_B, 1)))

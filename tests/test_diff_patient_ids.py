from confidential_backend.multi_fhir import adjust_patient_query

patient_A = "1234abcd"
patient_B = "abc"

def test_no_patient_id():
    path = f"/QuestionnaireResponse/17?subject=abc"
    improved = adjust_patient_query(path, patient_A, patient_B)
    assert improved == path


def test_patient_id_inside_another_id():
    """Query shouldn't get modified, even if patient id is part of a larger id"""
    id_with_embedded = (f"6f3-{patient_A}", f"{patient_A}abc", f"1{patient_A}2")
    for id in id_with_embedded:
        query = f"/Observation?code={id}"
        improved = adjust_patient_query(query, patient_A, patient_B)
        assert improved == query


def test_patient_id_in_path():
    query = f"random/Patient/{patient_A}"
    improved = adjust_patient_query(query, patient_A, patient_B)
    assert improved == query.replace(patient_A, patient_B)


def test_matching_param_value():
    query = f"random/Observation?patient={patient_A}"
    improved = adjust_patient_query(query, patient_A, patient_B)
    assert improved == query.replace(patient_A, patient_B)


def test_embedded_patient_in_param_value():
    # should replace only patient identifier, not the embedded match in the middle of a code value
    query = f"random/Observation?patient={patient_A}&code=tcfu{patient_A}Xqxw0"
    improved = adjust_patient_query(query, patient_A, patient_B)
    assert improved == query.replace(patient_A, patient_B, 1)

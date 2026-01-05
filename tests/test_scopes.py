from fhir.smart.scopes import scopes
from confidential_backend.scope import request_scope, request_allowed


def test_messy_relative_path():
    req_scope = request_scope(context="patient", request_path="Medication?subject=123", http_method='GET')
    assert req_scope
    _, scope_tuple = req_scope
    assert scope_tuple[1] == 'Medication'


def test_resource_by_id_scope():
    request_path = "Patient/5ee05359-57bf-4cee-8e89-91382c07e162"
    req_scope = request_scope(context="patient", request_path=request_path, http_method='GET')
    assert req_scope


def test_second_page():
    request_path = "?_getpages=311f6eb3-d13e-4abc-863f-1882032da6e5&_getpagesoffset=40&_count=20&_pretty=true&_bundletype=searchset"
    req_scope = request_scope(context="patient", request_path=request_path, http_method='GET')
    assert req_scope
    _, scope_tuple = req_scope
    assert scope_tuple[1] == 'Patient'


def test_wildcard_resource_allowed():
    auth_scopes = scopes("patient/*.r")
    req_scope = request_scope(context="patient", request_path="Medication", http_method='GET')
    assert request_allowed(req_scope, auth_scopes) is True


def test_disallowed_resource():
    auth_scopes = scopes("patient/Observation.r")
    req_scope = request_scope(context="patient", request_path="Medication", http_method='GET')
    assert request_allowed(req_scope, auth_scopes) is False


def test_disallowed_method():
    auth_scopes = scopes("patient/Observation.r")
    req_scope = request_scope(context="patient", request_path="Observation", http_method='POST')
    assert request_allowed(req_scope, auth_scopes) is False

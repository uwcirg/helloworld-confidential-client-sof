import re
import requests
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from flask import current_app

from confidential_backend.wrapped_session import get_session_value


def adjust_patient_query(full_path, a_pid, b_pid):
    """Given request path and parameters for server A, adjust for server B

    :param full_path: request path and query string as requested for server A
        (i.e. full URL beyond the scheme and netloc)
    :param a_pid: patient id for the patient of interest, i.e. server A's Patient.id
    :param b_pid: patient id for the patient of interest, i.e. server B's Patient.id

    Server A and server B often have different patient ids for the same
    patient (typically linked by a secondary identifier, such as MRN).
    Given a request path for server A, adjust by replacing Patient references
    to server A's patient id, with server B's patient id
    """
    if not full_path:
        return full_path

    query = urlparse(full_path)

    # replace in path if present, i.e. /Patient/<a_pid>
    escaped = re.escape(a_pid)
    path_pattern = re.compile(rf'(?<=/){escaped}(?=/|$)')
    if path_pattern.search(query.path):
        updated_path = path_pattern.sub(b_pid, query.path)
        query = query._replace(path=updated_path)

    # replace any values found in query strings
    qs = parse_qsl(query.query, keep_blank_values=True)
    updated_query = []
    update_needed = False
    for key, value in qs:
        if value == a_pid:
            update_needed = True
            updated_query.append((key, b_pid))
        else:
            updated_query.append((key, value))
    if update_needed:
        query = query._replace(query=urlencode(updated_query))
    return urlunparse(query)


def lookup_identified_patient(launch_patient):
    """Using config identifiers, look for a patient match on other FHIR server

    :param launch_patient: FHIR patient resource from launch FHIR server.
    :returns: secondary patient if an identifier match is found, otherwise None

    Using respective configured `MRN_SYSTEM`s, attempt to locate patient on other
    FHIR server.  If found, store in session and return matching patient resource

    :returns: secondary patient if an identifier match is found, otherwise None
    """
    launch_system = current_app.config.get("LAUNCH_FHIR_MRN_SYSTEM")
    app_system = current_app.config.get("APP_FHIR_MRN_SYSTEM")
    app_fhir = current_app.config.get("APP_FHIR_URL")

    if not launch_system and app_system and app_fhir:
        return  # TODO: should we raise or silently allow single FHIR?

    mrn = None
    for ident in launch_patient.get("identifier", []):
        if ident.get("system") == launch_system:
            mrn = ident["value"]
            break

    if not mrn:
        current_app.logger.info(f"Launch patient {launch_patient['id']} does not have MRN matching system {launch_system}")
        return

    request_url = f"{app_fhir}/Patient"
    params = {"identifier": f"{app_system}|{mrn}"}
    response = requests.get(request_url, params=params)
    response.raise_for_status()
    # search returns a bundle - contents of exactly 1 indicates a match
    bundle = response.json()
    assert bundle['resourceType'] == 'Bundle'
    if bundle['total'] == 0:
        current_app.logger.debug(f"not able to locate match for launch_patient,mrn {launch_patient['id']},{mrn}")
        return None
    if bundle['total'] > 1:
        current_app.logger.error(f"multiple patient matches for MRN {mrn} ; can't match multiple!")
    match = bundle['entry'][0]['resource']
    assert match['resourceType'] == 'Patient'
    current_app.logger.debug(
        f"mapped launch patient {launch_patient['id']} to {match['id']}")
    return match


def secondary_fhir_server_request(request_path, launch_patient_id, headers, original_request):
    """Modify and fire request to secondary FHIR server

    :param request_path: the FHIR request path, i.e. `Observation?patient=123`
    :param launch_patient_id: the FHIR patient id as known by the LAUNCH FHIR server
    :param headers: the request headers to include
    :param original_request: the original request sent to the calling view function

    :returns: executed request - caller responsible for handling errors and extracting results
    """

    # Correct Patient.id for secondary server
    # The original request prior to request_path names unwanted details
    full_path = original_request.url[original_request.url.find(request_path):]
    app_patient_id = get_session_value('app_fhir_patient_id')
    improved_path = adjust_patient_query(full_path, launch_patient_id, app_patient_id)
    secondary_fhir_url = '/'.join((current_app.config.get("APP_FHIR_URL"), improved_path))
    current_app.logger.debug(f"attempt secondary FHIR request {secondary_fhir_url}")
    secondary_response = requests.request(
        url=secondary_fhir_url,
        method=original_request.method,
        headers=headers,
        json=original_request.json if original_request.method in ('POST', 'PUT') else None
    )
    return secondary_response

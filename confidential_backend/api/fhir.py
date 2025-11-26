import requests

from flask import Blueprint, current_app, g, request
from flask_cors import cross_origin

from confidential_backend import PROXY_HEADERS
from confidential_backend.fhirresourcelogger import getLogger
from confidential_backend.jsonify_abort import jsonify_abort
from confidential_backend.multi_fhir import lookup_identified_patient, secondary_fhir_server_request
from confidential_backend.wrapped_session import get_session_value, set_session_value

blueprint = Blueprint('fhir', __name__)
r4prefix = '/v/r4/fhir'

# including OPTIONS conflicts with flask-cors
SUPPORTED_METHODS = ('GET', 'POST', 'PUT', 'DELETE')

def collate_results(*result_sets):
    """Compile given result sets into a single bundle"""
    results = {'resourceType': 'Bundle', 'entry': []}

    for rs in result_sets:
        if 'entry' in rs:
            results['entry'].extend(rs['entry'])

    results['total'] = len(results['entry'])
    return results


def empty_response(response):
    """Check for valid / empty response from FHIR server

    :param response: response from FHIR server
    :returns: True if the response is empty or 404, False otherwise
    """
    if response.status_code == 400:
        # Requests for Questionnaire raises BadRequest.  Swallow
        # to give secondary FHIR servers a chance to respond
        return True
    if response.status_code == 404:
        return True
    if response.status_code == 410:
        # when paging through the secondary servers response,
        # the launch FHIR returns a 410 as it doesn't recognize
        # the next page reference
        return True
    results = response.json()
    if results.get('resourceType') == 'Bundle':
        return results.get('total', -1) == 0
    # handle servers that don't set total
    if results.get('resourceType') == 'Bundle' and not results.get('entry'):
        return True
    return False


@blueprint.route('/fhir-router/', defaults={'relative_path': '', 'session_id': None}, methods=SUPPORTED_METHODS)
@blueprint.route('/fhir-router/<string:session_id>/<path:relative_path>', methods=SUPPORTED_METHODS)
@blueprint.route('/fhir-router/<string:session_id>/', defaults={'relative_path': ''}, methods=SUPPORTED_METHODS)
@cross_origin(allow_headers=PROXY_HEADERS)
def route_fhir(relative_path, session_id):
    from confidential_backend.cachelaunchresponse import persist_response
    g.session_id = session_id
    current_app.logger.debug('received session_id as path parameter: %s', session_id)

    if relative_path == '':
        # when the relative path beyond the flask route and session_id is only
        # query string parameters, the route parsing fails to pick them up.  rebuild
        relative_path = '?' + request.query_string.decode() if request.query_string else ''

    # prefer patient ID baked into access token JWT by EHR; fallback to initial transparent launch token for fEMR
    patient_id = get_session_value('token_response', {}).get('patient') or get_session_value('launch_token_patient')
    if not patient_id:
        return jsonify_abort(status_code=400, message="no patient ID found in session; can't continue")

    iss = get_session_value('iss')
    if not iss:
        return jsonify_abort(status_code=400, message="no iss found in session; can't continue")

    # use EHR FHIR server from launch
    # use session lookup across sessions if necessary
    upstream_fhir_base_url = iss
    upstream_fhir_url = '/'.join((upstream_fhir_base_url, relative_path))
    upstream_headers = {}
    for header_name in PROXY_HEADERS:
        if header_name in request.headers:
            upstream_headers[header_name] = request.headers[header_name]

    if current_app.config['DEBUG_FHIR_REQUESTS']:
        current_app.logger.debug(
            f'request headers (incoming to /fhir-router): {request.headers}')
        current_app.logger.debug(
            f'upstream headers (outgoing to {upstream_fhir_url}): '
            f'{upstream_headers} ;;; params: {request.args} ;;; json: {request.json}')

    fhir_logger = getLogger()
    upstream_response = requests.request(
        url=upstream_fhir_url,
        method=request.method,
        headers=upstream_headers,
        params=request.args,
        json=request.json if request.method in ('POST', 'PUT') else None
    )
    if (
            empty_response(upstream_response) and
            current_app.config.get('APP_FHIR_URL') and
            get_session_value('app_fhir_patient_id')):
        # If no results found from upstream (aka LAUNCH) FHIR server, try secondary
        secondary_response = secondary_fhir_server_request(
            request_path=relative_path,
            launch_patient_id=patient_id,
            headers=upstream_headers,  # TODO: need these adjust for other FHIR server?
            original_request=request
        )
        secondary_response.raise_for_status()
        fhir_logger.info({
            "message": "response",
            "fhir_server": "APP FHIR",
            "fhir": secondary_response.json()})
        return secondary_response.json()

    upstream_response.raise_for_status()
    if relative_path.startswith('Patient'):
        # Patient lookup after launch - obtain secondary FHIR server Patient.id
        if True:  # TODO: this isn't getting reset between /launch sessions: not get_session_value('app_fhir_patient_id'):
            app_fhir_patient = lookup_identified_patient(upstream_response.json())
            if app_fhir_patient:
                set_session_value('app_fhir_patient_id', app_fhir_patient['id'])

    persist_response.delay(upstream_response.json())
    fhir_logger.info({
        "message": "response",
        "fhir_server": "LAUNCH FHIR",
        "fhir": upstream_response.json()})

    return upstream_response.json()

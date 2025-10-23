import requests

from flask import Blueprint, current_app, g, request
from flask_cors import cross_origin

from confidential_backend import PROXY_HEADERS
from confidential_backend.audit import audit_entry
from confidential_backend.fhirresourcelogger import getLogger
from confidential_backend.jsonify_abort import jsonify_abort
from confidential_backend.wrapped_session import get_session_value

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


@blueprint.route(f'{r4prefix}/Patient/<string:id>')
def patient_by_id(id):
    from confidential_backend.cachelaunchresponse import persist_response
    base_url = get_session_value('iss')
    key = f'patient_{id}'
    value = get_session_value(key)
    if value:
        return value

    patient_url = f'{base_url}/Patient/{id}'

    upstream_headers = {}

    for header_name in PROXY_HEADERS:
        if header_name in request.headers:
            upstream_headers[header_name] = request.headers[header_name]

    response = requests.get(
        url=patient_url,
        headers=upstream_headers,
    )
    response.raise_for_status()
    persist_response.delay(response.json())
    fhir_logger = getLogger()
    fhir_logger.info(
        {"message": "response", "fhir": upstream_response.json()})
    patient_fhir = response.json()
    # TODO when possible w/o session cookie: set_session_value(key, patient_fhir)

    return patient_fhir


@blueprint.route('/fhir-router/', defaults={'relative_path': '', 'session_id': None}, methods=SUPPORTED_METHODS)
@blueprint.route('/fhir-router/<string:session_id>/<path:relative_path>', methods=SUPPORTED_METHODS)
@blueprint.route('/fhir-router/<string:session_id>/', defaults={'relative_path': ''}, methods=SUPPORTED_METHODS)
@cross_origin(allow_headers=PROXY_HEADERS)
def route_fhir(relative_path, session_id):
    from confidential_backend.cachelaunchresponse import persist_response
    g.session_id = session_id
    current_app.logger.debug('received session_id as path parameter: %s', session_id)

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

    upstream_response = requests.request(
        url=upstream_fhir_url,
        method=request.method,
        headers=upstream_headers,
        params=request.args,
        json=request.json if request.method in ('POST', 'PUT') else None
    )
    upstream_response.raise_for_status()
    persist_response.delay(upstream_response.json())
    fhir_logger = getLogger()
    fhir_logger.info(
        {"message": "response", "fhir": upstream_response.json()})
    return upstream_response.json()

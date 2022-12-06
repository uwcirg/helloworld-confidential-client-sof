import requests

from flask import Blueprint, current_app, g, request

from confidential_backend.audit import audit_entry
from confidential_backend.jsonify_abort import jsonify_abort
from confidential_backend.wrapped_session import get_session_value

blueprint = Blueprint('fhir', __name__)
r4prefix = '/v/r4/fhir'

PROXY_HEADERS = ('Authorization', 'Cache-Control', 'Content-Type')

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
    patient_fhir = response.json()
    # TODO when possible w/o session cookie: set_session_value(key, patient_fhir)

    return patient_fhir


@blueprint.route('/fhir-router/', defaults={'relative_path': '', 'session_id': None})
@blueprint.route('/fhir-router/<string:session_id>/<path:relative_path>')
def route_fhir(relative_path, session_id):
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

    upstream_response = requests.get(
        url=upstream_fhir_url,
        headers=upstream_headers,
        params=request.args,
    )
    upstream_response.raise_for_status()
    return upstream_response.json()


@blueprint.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers.setdefault('Access-Control-Allow-Headers', ", ".join(PROXY_HEADERS))

    return response

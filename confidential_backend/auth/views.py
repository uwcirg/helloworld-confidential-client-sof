from flask import Blueprint, current_app, redirect, request, url_for, session
from flask_cors import cross_origin
import requests

from confidential_backend import PROXY_HEADERS
from confidential_backend.audit import audit_entry
from confidential_backend.auth.helpers import extract_payload, format_as_jwt
from confidential_backend.extensions import oauth


# SMIT launch token encoding scheme
# https://github.com/smart-on-fhir/smart-launcher/blob/master/static/codec.js#L4-L17
# launch tokens are typically opaque to the SoF client app
LAUNCH_VALUE_TO_CODE = {
    "launch_ehr": "a",
    "patient": "b",
    "encounter": "c",
    "auth_error": "d",
    "provider": "e",
    "sim_ehr": "f",
    "select_encounter": "g",
    "launch_prov": "h",
    "skip_login": "i",
    "skip_auth": "j",
    "launch_pt": "k",
    "launch_cds": "l",
}


blueprint = Blueprint('auth', __name__, url_prefix='/auth')


def get_extension_value(url, extensions):
    """Get the value of an extension, given the extension URL and list of extensions"""
    for extension in extensions:
        if extension.get('url') == url:
            for key, value in extension.items():
                if key.startswith('value'):
                    return value
            return extension[url]
    raise ValueError('extension url not present in any extension', url)


def debugging_compliance_fix(session):
    def _fix(response):
        current_app.logger.debug('access_token request url: %s', response.request.url)
        current_app.logger.debug('access_token request headers: %s', response.request.headers)
        current_app.logger.debug('access_token request body: %s', response.request.body)

        current_app.logger.debug('access_token response: %s', response)
        current_app.logger.debug('access_token response.status_code: %s', response.status_code)
        current_app.logger.debug('access_token response.content: %s', response.content)

        response.raise_for_status()

        return response
    session.register_compliance_hook('access_token_response', _fix)


@blueprint.route('/launch')
def launch():
    """
    SMART-on-FHIR launch endpoint
    set /auth/launch as SoF App Launch URL
    """
    iss = request.args['iss']
    current_app.logger.debug('iss from EHR: %s', iss)
    session['iss'] = iss

    launch = request.args.get('launch')
    if launch:
        # launch value received from EHR
        current_app.logger.debug('launch: %s', launch)

        # Extract user and subject from encoded launch parameter if found
        # NB this is documented to be ``an opaque handle to the EHR context
        # is passed along to the app as part of the launch URL``
        # the SMIT Sandbox (and fEMR) use a base64 encoded JSON object
        payload = extract_payload(format_as_jwt(launch))

        launch_token_patient = payload.get(LAUNCH_VALUE_TO_CODE['patient'])
        if launch_token_patient:
            session['subject'] = f"Patient/{launch_token_patient}"

        launch_token_provider = payload.get(LAUNCH_VALUE_TO_CODE['provider'])
        if launch_token_provider:
            session['user'] = f"Provider/{launch_token_provider}"
        audit_entry("launch", extra={'tags':['launch']})
        session['launch_token_patient'] = launch_token_patient

    # fetch conformance statement from /metadata
    ehr_metadata_url = '%s/metadata' % iss
    metadata = requests.get(
        ehr_metadata_url,
        headers={'Accept': 'application/json'},
    )
    metadata.raise_for_status()
    metadata_security = metadata.json()['rest'][0].get('security')

    # default to config values (in case SoF dynamic configuration fails)
    authorize_url = current_app.config.get('SOF_AUTHORIZE_URL')
    token_url = current_app.config.get('SOF_ACCESS_TOKEN_URL')

    # dynamic configuration
    if metadata_security:
        authorize_url = get_extension_value(url='authorize', extensions=metadata_security['extension'][0]['extension'])
        token_url = get_extension_value(url='token', extensions=metadata_security['extension'][0]['extension'])

    # set client id and secret from flask config
    oauth.register(
        name='sof',
        access_token_url=token_url,
        authorize_url=authorize_url,
        compliance_fix=debugging_compliance_fix,
        # todo: try using iss
        # api_base_url=iss+'/',
        client_kwargs={'scope': current_app.config['SOF_CLIENT_SCOPES']},
    )
    # work around back-end caching of dynamic config values
    oauth.sof.authorize_url = authorize_url
    oauth.sof.access_token_url = token_url

    # redirect URL to pass (as QS param) to EHR Authz server
    # EHR Authz server will redirect to this URL after authorization
    redirect_url = url_for('auth.authorize', _external=True)

    current_app.logger.debug('redirecting to EHR Authz. will return to: %s', redirect_url)

    current_app.logger.debug('passing iss as aud: %s', iss)
    return oauth.sof.authorize_redirect(
        redirect_uri=redirect_url,
        # SoF requires iss to be passed as aud querystring param
        aud=iss,
        # must pass launch param back when using EHR launch
        launch=launch,
    )


@blueprint.route('/authorize')
def authorize():
    """
    Direct identity provider to redirect here after auth
    """
    # raise 400 if error passed (as querystring params)
    if 'error' in request.args:
        error_details = {
            'error': request.args['error'],
            'error_description': request.args['error_description'],
        }
        return error_details, 400
    # authlib persists OAuth client details via secure cookie
    # if not '_sof_authlib_state_' in session:
        # return 'authlib state cookie missing; restart auth flow', 400

    # todo: define fetch_token function that requests JSON (Accept: application/json header)
    # https://github.com/lepture/authlib/blob/master/authlib/oauth2/client.py#L154
    token_response = oauth.sof.authorize_access_token(_format='json')
    extracted_id_token = extract_payload(token_response.get('id_token'))
    audit_entry(
        "JWT payload",
        extra={'tags':['JWT', "authorize"], 'payload': extracted_id_token})
    username = extracted_id_token.get('preferred_username')

    # standalone uses profile
    if 'profile' in extracted_id_token:
        session['user'] = session.get('user', extracted_id_token['profile'])
    else:
        session['user'] = session.get('user', {'username': username})

    if 'patient' in token_response:
        session['subject'] = session.get('subject', 'Patient/{}'.format(token_response['patient']))

    iss = session['iss']
    current_app.logger.debug('iss from session: %s', iss)

    session['token_response'] = token_response

    frontend_url = current_app.config['LAUNCH_DEST']

    current_app.logger.debug('redirecting to frontend app: %s', frontend_url)
    return redirect(frontend_url)


@blueprint.route('/auth-info')
@cross_origin(allow_headers=PROXY_HEADERS)
def auth_info():
    token_response = session['token_response']
    iss = session['iss']
    launch_token_patient = session['launch_token_patient']
    session_id = request.cookies.get(current_app.session_cookie_name)
    return {
        # debugging
        'token_data': token_response,

        "fakeTokenResponse": {
            "access_token": token_response['access_token'],
            "token_type": "Bearer",
        },
        "realFhirServiceUrl": iss,
        "fhirServiceUrl": url_for(
            'fhir.route_fhir',
            session_id=session_id,
            relative_path='',
            _external=True
        ),
        # fallback to patient obtained from non-opaque (non-standard) launch token
        "patientId":token_response.get('patient', launch_token_patient),
    }


@blueprint.route('/users/<int:user_id>')
def users(user_id):
    return {'ok': True}


@blueprint.before_request
def before_request_func():
    current_app.logger.debug('before_request session: %s', session)
    current_app.logger.debug('before_request authlib state present: %s','_sof_authlib_state_' in session)


@blueprint.after_request
def after_request_func(response):
    current_app.logger.debug('after_request session: %s', session)
    current_app.logger.debug('after_request authlib state present: %s','_sof_authlib_state_' in session)
    # allow requests with cookies to auth-info endpoint
    if request.path == "/auth/auth-info":
        response.headers['Access-Control-Allow-Credentials'] = 'true'

    return response

import msgpack
from flask import g, current_app, request, session


def get_session_value(key, default=None):
    """Return session value for given key

    Typically flask-session allows for direct access via `session.get`
    but that only works when a browser cookie is available, which is
    not the case when launched from an EMR or fEMR.

    Until resolved, this function tries local and configured session
    and returns a value if found.
    """
    if key in session:
        return session.get(key, default)

    # session_id stored on entry point in `fhir_router`
    if 'session_id' in g:
        return get_redis_session_data(g.session_id).get(key, default)


def set_session_value(key, value):
    if request.cookies.get("session"):
        session[key] = value
        return

    raise NotImplementedError("Can't set session variables w/o session cookie")


def get_redis_session_data(session_id):
    """Load session data associated with given session_id"""
    if session_id is None:
        return {}

    # TODO: further investigate using SessionHandler
    redis_handle = current_app.config['SESSION_REDIS']
    session_prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')

    encoded_session_data = redis_handle.get(f'{session_prefix}{session_id}')

    # why doesn't this use the flask default JSON serializer?
    # (probably because the session is designed to hold non JSON serializable objects, like datetime)
    try:
        session_data = msgpack.loads(encoded_session_data)
    except msgpack.exceptions.FormatError:
        current_app.logger.error(f'Unable to load session data for {session_id}')
        current_app.logger.error(f'failed to decode {encoded_session_data}')
        session_data = {}
    return session_data



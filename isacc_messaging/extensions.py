from authlib.integrations.flask_client import OAuth
from flask import current_app
from flask_session import Session
import redis
from requests_cache import CachedSession

oauth = OAuth()
sess = Session()


class CS_Singleton(object):
    """Work around lack of CachedSession delayed bootstrap w/ singleton"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CS_Singleton, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self._cached_session = None

    @property
    def cached_session(self):
        if self._cached_session is None:
            if current_app.config['TESTING']:
                backend = 'memory'
                connection = None
            else:
                backend = 'redis'
                connection = redis.StrictRedis.from_url(
                    current_app.config.get("REQUEST_CACHE_URL"))

            self._cached_session = CachedSession(
                cache_name=current_app.name,
                backend=backend,
                expire_after=current_app.config['REQUEST_CACHE_EXPIRE'],
                include_get_headers=True,
                old_data_on_error=True,
                connection=connection
            )

        return self._cached_session

"""Default configuration

Use env var to override
"""
import os
import redis

SERVER_NAME = os.getenv("SERVER_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")
# URL scheme to use outside of request context
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", 'http')
FHIR_URL = os.getenv("FHIR_URL")
SESSION_TYPE = os.getenv("SESSION_TYPE", 'redis')
SESSION_REDIS = redis.from_url(os.getenv("SESSION_REDIS", "redis://127.0.0.1:6379"))

REQUEST_CACHE_URL = os.environ.get('REQUEST_CACHE_URL', 'redis://localhost:6379/0')
REQUEST_CACHE_EXPIRE = 24 * 60 * 60  # 24 hours

LOGSERVER_TOKEN = os.getenv('LOGSERVER_TOKEN')
LOGSERVER_URL = os.getenv('LOGSERVER_URL')

# NB log level hardcoded at INFO for logserver
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG').upper()

VERSION_STRING = os.getenv("VERSION_STRING")

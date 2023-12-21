"""Default configuration

Use env var to override
"""
import os
import redis

AUTH_TOKEN_LOG_FILTER = os.getenv("AUTH_TOKEN_LOG_FILTER").split(",") if "AUTH_TOKEN_LOG_FILTER" in os.environ else None
DEBUG_OUTPUT_DIR = os.getenv("DEBUG_OUTPUT_DIR", '/tmp')
SERVER_NAME = os.getenv("SERVER_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")
# URL scheme to use outside of request context
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", 'http')

SESSION_TYPE = os.getenv("SESSION_TYPE", 'redis')
SESSION_REDIS = redis.from_url(os.getenv("SESSION_REDIS", "redis://127.0.0.1:6379"))
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN")
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", 'Lax')
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", 'false').lower() == 'true'

REQUEST_CACHE_URL = os.environ.get('REQUEST_CACHE_URL', 'redis://localhost:6379/0')
REQUEST_CACHE_EXPIRE = 24 * 60 * 60  # 24 hours

SOF_CLIENT_ID = os.getenv("SOF_CLIENT_ID")
SOF_CLIENT_SECRET = os.getenv("SOF_CLIENT_SECRET")
SOF_CLIENT_SCOPES = os.getenv("SOF_CLIENT_SCOPES", "patient/*.read launch/patient")

SOF_ACCESS_TOKEN_URL = os.getenv("SOF_ACCESS_TOKEN_URL")
SOF_AUTHORIZE_URL = os.getenv("SOF_AUTHORIZE_URL")

LOGSERVER_TOKEN = os.getenv('LOGSERVER_TOKEN')
LOGSERVER_URL = os.getenv('LOGSERVER_URL')

# NB log level hardcoded at INFO for logserver
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG').upper()

LAUNCH_DEST = os.getenv("LAUNCH_DEST")

VERSION_STRING = os.getenv("VERSION_STRING")

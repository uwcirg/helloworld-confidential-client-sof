from flask import Flask
import logging
from logging import config as logging_config
import os
from werkzeug.middleware.proxy_fix import ProxyFix

from isacc_messaging import api
from isacc_messaging.audit import audit_entry, audit_log_init
from isacc_messaging.extensions import oauth, sess


def create_app(testing=False, cli=False):
    """Application factory, used to create application
    """
    app = Flask('isacc_messaging')
    app.config.from_object('isacc_messaging.config')
    app.config['TESTING'] = testing

    configure_logging(app)
    configure_extensions(app, cli)
    register_blueprints(app)
    configure_proxy(app)

    return app


def configure_logging(app):
    app.logger  # must call to initialize prior to config or it'll replace

    config = 'logging.ini'
    if not os.path.exists(config):
        # look above the testing dir when testing or debugging locally
        config = os.path.join('..', config)

    logging_config.fileConfig(config, disable_existing_loggers=False)
    app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL'].upper()))
    app.logger.debug(
        "isacc messaging service logging initialized",
        extra={'tags': ['testing', 'logging', 'app']})

    if not app.config['LOGSERVER_URL']:
        return

    audit_log_init(app)
    audit_entry(
        "isacc messaging service logging initialized",
        extra={'tags': ['testing', 'logging', 'events'],
            'version': app.config['VERSION_STRING']})


def configure_extensions(app, cli):
    """configure flask extensions
    """
    oauth.init_app(app)
    sess.init_app(app)


def register_blueprints(app):
    """register all blueprints for application
    """
    app.register_blueprint(api.views.base_blueprint)


def configure_proxy(app):
    """Add werkzeug fixer to detect headers applied by upstream reverse proxy"""
    if app.config.get('PREFERRED_URL_SCHEME', '').lower() == 'https':
        app.wsgi_app = ProxyFix(
            app=app.wsgi_app,

            # trust X-Forwarded-Host
            x_host=1,

            # trust X-Forwarded-Port
            x_port=1,
        )

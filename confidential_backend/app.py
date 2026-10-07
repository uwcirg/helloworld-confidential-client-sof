from flask import Flask
from flask_cors import CORS
import logging
from logging import config as logging_config
import os
import sys
from werkzeug.middleware.proxy_fix import ProxyFix

from confidential_backend import auth, api
from confidential_backend.audit import audit_entry, audit_log_init
from confidential_backend.dynamic_factory import load_strategies
from confidential_backend.extensions import oauth, secondary_sources, sess


def create_app(testing=False, cli=False):
    """Application factory, used to create application
    """
    app = Flask('confidential_backend')
    app.config.from_object('confidential_backend.config')
    app.config['TESTING'] = testing
    CORS(app)

    configure_logging(app)
    configure_extensions(app, cli)
    register_blueprints(app)
    configure_proxy(app)
    configure_secondary_sources(app)

    return app


def configure_logging(app):
    # Clear preexisting handlers attached by the framework to avoid double logging
    # 1. Access the logger manager registry
    logger_dict = logging.root.manager.loggerDict

    # 2. Loop through every single initialized child logger
    for logger_name, logger_obj in logger_dict.items():
        if isinstance(logger_obj, logging.Logger):
            # Clear all framework-attached handlers on this child
            if logger_obj.handlers:
                for handler in list(logger_obj.handlers):
                    logger_obj.removeHandler(handler)

            # Force the child to pass its logs up to the root configuration
            logger_obj.propagate = True

    # 3. Completely clear the root logger just in case
    logging.getLogger().handlers = []

    # 4. Now load logging.ini cleanly
    config = 'logging.ini'
    if not os.path.exists(config):
        # look above the testing dir when testing or debugging locally
        config = os.path.join('..', config)

    logging_config.fileConfig(config, disable_existing_loggers=False)
    app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL'].upper()))
    app.logger.debug(
        "confidential backend logging initialized",
        extra={'tags': ['testing', 'logging', 'app']})

    if not app.config['LOGSERVER_URL']:
        return

    audit_log_init(app)
    debugging_audit_log = False
    if debugging_audit_log:
        args = ",".join(sys.argv)
        audit_entry(
            f"confidential backend logging initialized w/ {args}",
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
    app.register_blueprint(auth.views.blueprint)
    app.register_blueprint(api.views.base_blueprint)
    app.register_blueprint(api.fhir.blueprint)


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


def configure_secondary_sources(app):
    """Add any configured additional sources, beyond the required launch FHIR server"""
    strats = load_strategies(app)
    for strat in strats:
        # avoid pushing duplicates as factory calls for app and celery stack
        if not any(s.name == strat.name for s in secondary_sources):
            secondary_sources.append(strat)

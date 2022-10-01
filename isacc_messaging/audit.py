"""Audit

functions to simplify adding context and extra data to log messages destined for audit logs
"""
from copy import deepcopy
from flask import current_app, has_app_context
import logging

from isacc_messaging.logserverhandler import LogServerHandler

EVENT_LOG_NAME = "isacc_messaging_event_logger"


def audit_log_init(app):
    log_server_handler = LogServerHandler(
        jwt=app.config['LOGSERVER_TOKEN'],
        url=app.config['LOGSERVER_URL'])
    event_logger = logging.getLogger(EVENT_LOG_NAME)
    event_logger.setLevel(logging.INFO)
    event_logger.addHandler(log_server_handler)


def audit_entry(message, level='info', extra=None):
    """Log entry, adding in session info such as active user"""
    try:
        logger = logging.getLogger(EVENT_LOG_NAME)
        log_at_level = getattr(logger, level.lower())
    except AttributeError:
        raise ValueError(f"audit_entry given bogus level: {level}")

    if extra is None:
        extra = {}

    if has_app_context():
        if 'version' not in extra:
            extra['version'] = current_app.config['VERSION_STRING']

        # echo ERRORs to current_app.logger for alerts
        if level.lower() == 'error':
            # remove obvious PHI
            scrubbed_extra = deepcopy(extra)
            for x in ('user', 'subject', 'patient'):
                if x in scrubbed_extra:
                    scrubbed_extra[x] = 'REDACTED - see audit logs'
            current_app.logger.error(message, extra=scrubbed_extra)

    log_at_level(message, extra=extra)

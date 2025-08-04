"""Specialized logger for capturing all FHIR resources from upstream servers"""
from flask import current_app
import logging
from pythonjsonlogger.jsonlogger import JsonFormatter


def configure_resource_logger(logger):
    """Only if configured, write to named file.  Otherwise use app logger"""
    filename = current_app.config["FHIR_RESOURCES_LOGFILE"]
    if not filename:
        return current_app.logger

    handler = logging.FileHandler(filename)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger


def getLogger():
    logger = logging.getLogger("FHIR_RESOURCES")

    # Avoid duplicates from multiple calls
    if not logger.handlers:
        logger = configure_resource_logger(logger)

    return logger

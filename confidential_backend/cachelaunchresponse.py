"""Persist all resources received from the launch URL FHIR server"""
from celery.utils.log import get_task_logger

from confidential_backend.celery_utils import celery

logger = get_task_logger(__name__)

@celery.task
def persist_response(response):
    logger.info("Response received of type %s", response.get("resourceType"))


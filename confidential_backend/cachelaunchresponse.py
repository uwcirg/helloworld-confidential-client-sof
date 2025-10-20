"""Persist all resources received from the launch URL FHIR server"""
import requests
from celery.utils.log import get_task_logger

from confidential_backend.celery_utils import create_celery

logger = get_task_logger(__name__)
celery = create_celery()

@celery.task
def persist_response(response):
    if not "resourceType" in response:
        logger.error(f"non-FHIR response; can't persist: {response}")
        return
    logger.info("Response received of type %s", response.get("resourceType"))
    persist_bundle(response)


def persist_resource(resource):
    """Given any single resource, persist to the cache URL"""
    resource_type = resource["resourceType"]
    if resource_type == "Bundle":
        raise ValueError("persisting whole bundles not supported")

    # Always PUT with given ID, in order to prevent duplicates
    base = "http://fhir-internal:8080/fhir/"
    id = resource["id"]
    put_url = f"{base}{resource_type}/{id}"
    response = requests.put(put_url, json=resource)
    response.raise_on_status()


def persist_bundle(bundle):
    """Break into single resources for persistence - don't retain bundles"""
    if bundle["resourceType"] != "Bundle":
        persist_resource(bundle)
        return

    for e in bundle["entry"]:
        persist_resource(e["resource"])

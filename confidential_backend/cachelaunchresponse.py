"""Persist all resources received from the launch URL FHIR server"""
import requests
from celery.utils.log import get_task_logger
from flask import current_app

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

    # Always PUT with given ID, in order to prevent duplicates
    base = current_app.config["LAUNCH_CACHE_URL"]
    id = resource["id"]
    put_url = f"{base}/{resource_type}/{id}"
    logger.debug(f"Persisting {put_url}")
    try:
        response = requests.put(put_url, json=resource)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.warn(
            f"HTTP error on persist: {response.status_code} {response.reason}")
        logger.warn(f"{response.text[:500]}")
    except request.exceptions.RequestException as err:
        logger.error(f"Request failed: {err}")


def persist_bundle(bundle):
    """Unpack and persist containted resources, then the bundle itself"""

    if bundle["resourceType"] != "Bundle":
        persist_resource(bundle)
        return

    # break apart the bundle, persisting every contained entry
    for e in bundle.get("entry", []):
        persist_resource(e["resource"])

    # persist the bundle itself
    base = current_app.config["LAUNCH_CACHE_URL"]
    bundle['type'] = 'collection'  # can't persist a searchset
    try:
        response = requests.post(f"{base}/Bundle", json=bundle)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.warn(
            f"HTTP error on persist: {response.status_code} {response.reason}")
        logger.warn(f"{response.text[:500]}")
    except request.exceptions.RequestException as err:
        logger.error(f"Request failed: {err}")

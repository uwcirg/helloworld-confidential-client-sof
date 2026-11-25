"""Filter launch FHIR Observations that already exist in the app FHIR server.

Some portion of the Observations in the launch FHIR server may have come from
app FHIR QuestionnaireResponses via $extract.  In such a case, the matching
Observations are tagged with an identifier during the extract and post process.

This filter removes any Observations from the launch FHIR response, where an
app FHIR Observation whose identifier matches the system/value pair used to
record the upstream (launch) FHIR server's Observation ID is found.

This mirrors the identifier convention established in fishmouth, where
update_identifier() stamps each app-side Observation with:
  system = UPSTREAM_FHIR_URL
  value  = <Epic Observation.id>
"""
import requests
from flask import current_app


class ExtractedObservationFilter:

    def __init__(self, app_fhir_url: str, identifier_system: str):
        """
        :param app_fhir_url: base URL of the app FHIR server to query for existing observations
        :param identifier_system: the identifier system used to stamp upstream IDs on app observations
            (matches UPSTREAM_FHIR_URL in fishmouth config, e.g. 'https://epic.example.org/fhir')
        """
        self._app_fhir_url = app_fhir_url
        self._identifier_system = identifier_system

    def applies_to(self, resource_type: str) -> bool:
        return resource_type == "Observation"

    def filter(self, response_json: dict) -> dict:
        """Remove Observations from response that are already present in app FHIR server."""
        if response_json.get("resourceType") == "Bundle":
            return self._filter_bundle(response_json)

        # single resource
        if response_json.get("resourceType") == "Observation":
            obs_id = response_json.get("id")
            if obs_id and self._already_extracted(obs_id):
                # return an empty bundle rather than a bare null
                return {"resourceType": "Bundle", "total": 0, "entry": []}
            return response_json

        return response_json

    def _filter_bundle(self, bundle: dict) -> dict:
        entries = bundle.get("entry", [])
        if not entries:
            return bundle

        # collect all launch Observation IDs in one pass, then batch-query app FHIR
        obs_ids = [
            e["resource"]["id"]
            for e in entries
            if e.get("resource", {}).get("resourceType") == "Observation"
            and e.get("resource", {}).get("id")
        ]

        extracted_ids = self._fetch_extracted_ids(obs_ids)

        filtered_entries = [
            e for e in entries
            if not (
                e.get("resource", {}).get("resourceType") == "Observation"
                and e.get("resource", {}).get("id") in extracted_ids
            )
        ]

        result = dict(bundle)
        result["entry"] = filtered_entries
        result["total"] = len(filtered_entries)
        return result

    def _already_extracted(self, obs_id: str) -> bool:
        return obs_id in self._fetch_extracted_ids([obs_id])

    def _fetch_extracted_ids(self, obs_ids: list) -> set:
        """Query app FHIR for Observations whose identifier.value matches any of obs_ids.

        Uses the identifier search parameter with the configured system, e.g.:
          GET /Observation?identifier=https://epic.../fhir|obs-id-1,obs-id-2,...
        """
        if not obs_ids:
            return set()

        # FHIR allows comma-separated OR on identifier values; batch the lookup
        identifier_param = ",".join(
            f"{self._identifier_system}|{oid}" for oid in obs_ids
        )
        try:
            resp = requests.get(
                f"{self._app_fhir_url}/Observation",
                params={"identifier": identifier_param},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            current_app.logger.warning(
                f"AppFhirDedupFilter: app FHIR query failed, skipping filter: {e}"
            )
            return set()

        bundle = resp.json()
        extracted = set()
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            for ident in resource.get("identifier", []):
                if ident.get("system") == self._identifier_system:
                    extracted.add(ident["value"])  # value = launch server Observation.id
        return extracted

"""Source Strategy implementation for a FHIR server in a secondary (non launch) role."""
from fhir.smart.scopes import scopes
import re
import requests
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from flask import current_app, has_request_context

from confidential_backend.wrapped_session import get_session_value, set_session_value
from confidential_backend.scope import request_allowed
from confidential_backend.source_strategy import SourceStrategy

class SecondaryFhirStrategy(SourceStrategy):
    def __init__(self, name, **kwargs):
        """Initialize this strategy - NB instance state is not reliable across requests"""
        self.name = name
        self._session_patient_key = kwargs.get('session_patient_key', f'{self.name}_patient_id')
        self._server_url = kwargs.get('server_url')
        self._mrn_system = kwargs.get('mrn_system')
        self._launch_mrn_systems = kwargs.get('launch_mrn_systems')
        try:
            self._scopes = scopes(
                kwargs.get('scopes', 'patient/*.cruds system/*.cruds user/*.cruds'))
        except ValueError as ve:
            current_app.logger.error(
                f"Invalid scope {kwargs['scopes']} on Secondary FHIR strategy: {name}")
            raise ve

    def adjust_patient_query(self, full_path, launch_pid):
        """Given request path and launch patient id, return query for implementation source

        :param full_path: request path and query string as requested for launch server
            (i.e. full URL beyond the scheme and netloc)
        :param launch_pid: patient id for the patient of interest from launch server's perspective

        Launch server and strategy implementation server often have different patient ids for the
        same patient (typically linked by a secondary identifier, such as MRN).
        Given a request path and patient id for the launch server, adjust the request to fit
        the implementation server's patient id and in some cases, the request format.

        :returns: url for equivalent request against implementation server.
        """
        if not full_path:
            return full_path

        query = urlparse(full_path)

        # replace in path if present, i.e. /Patient/<launch_pid>
        escaped = re.escape(launch_pid)
        path_pattern = re.compile(rf'(?<=/){escaped}(?=/|$)')
        if path_pattern.search(query.path):
            updated_path = path_pattern.sub(self.translated_patient_id(), query.path)
            query = query._replace(path=updated_path)

        # replace any values found in query strings
        qs = parse_qsl(query.query, keep_blank_values=True)
        updated_query = []
        update_needed = False
        for key, value in qs:
            if value == launch_pid:
                update_needed = True
                updated_query.append((key, self.translated_patient_id()))
            else:
                updated_query.append((key, value))
        if update_needed:
            query = query._replace(query=urlencode(updated_query))

        return '/'.join((self._server_url, urlunparse(query)))

    def allowed_request(self, request_scope):
        return request_allowed(request_scope, self._scopes)

    def empty_response(self, response):
        """Returns true if the response is empty, false otherwise.

        :returns: True if the response is empty or 404, False otherwise
        """
        if response is None:
            return True
        if response.status_code == 404:
            return True
        if response.status_code == 410:
            # when paging through the secondary servers response,
            # other FHIR servers return a 410 as they don't recognize
            # the next page reference
            return True
        results = response.json()
        if results.get('resourceType') == 'Bundle':
            return results.get('total', -1) == 0
        # handle servers that don't set total
        if results.get('resourceType') == 'Bundle' and not results.get('entry'):
            return True
        return False

    def lookup_identified_patient(self, launch_patient):
        """Using config identifiers, look for a patient match on other FHIR server

        :param launch_patient: FHIR patient resource from launch FHIR server.
        :returns: secondary patient if an identifier match is found, otherwise None

        Using respective configured `MRN_SYSTEM`s, attempt to locate patient on other
        FHIR server.  If found, store in session and return matching patient resource

        NB, if a match is found, the patient ID is persisted in the session.

        :returns: secondary patient if an identifier match is found, otherwise None
        """
        if not (self._launch_mrn_systems and self._mrn_system and self._server_url):
            snippet = (
                f"launch mrn systems: {self._launch_mrn_systems}, "
                f"mrn system: {self._mrn_system}, "
                f"server url: {self._server_url}")
            raise RuntimeError(
                f"Misconfigured {self.name} server: {snippet}")

        mrn = None
        for ident in launch_patient.get("identifier", []):
            if ident.get("system") in self._launch_mrn_systems:
                mrn = ident["value"]
                break

        if not mrn:
            current_app.logger.info(
                f"Launch patient {launch_patient['id']} does not have identifier "
                f"for MRN systems {self._launch_mrn_systems}")
            return

        request_url = f"{self._server_url}/Patient"
        params = {"identifier": f"{self._mrn_system}|{mrn}"}
        response = requests.get(request_url, params=params)
        response.raise_for_status()
        # search returns a bundle - contents of exactly 1 indicates a match
        bundle = response.json()
        assert bundle['resourceType'] == 'Bundle'
        if bundle['total'] == 0:
            current_app.logger.debug(
                f"{self.name} not able to locate match for "
                f"launch_patient,mrn {launch_patient['id']},{mrn}")
            return None
        if bundle['total'] > 1:
            # NB: writing to error log but simply returning first in case of multiple matches
            current_app.logger.error(
                f"{self.name} multiple patient matches for MRN {mrn} ; can't match multiple!")
        match = bundle['entry'][0]['resource']
        assert match['resourceType'] == 'Patient'
        current_app.logger.debug(
            f"mapped launch patient {launch_patient['id']} to {match['id']} on {self.name}")
        if has_request_context():
            set_session_value(self._session_patient_key, match['id'])
        return match

    def server_url(self):
        """Returns the configured server url for the respective source strategy."""
        return self._server_url

    def translated_patient_id(self):
        """Returns the launch patient id translated or mapped to the implementation
        strategy's patient id.
        """
        # The session value was either set when the launch /Patient was requested
        # or it is unknown
        return get_session_value(self._session_patient_key)

    def server_request(self, request_path, launch_patient_id, headers, original_request):
        """Modify and fire request to this secondary FHIR server

        :param request_path: the FHIR request path, i.e. `Observation?patient=123`
        :param launch_patient_id: the FHIR patient id as known by the LAUNCH FHIR server
        :param headers: the request headers to include
        :param original_request: the original request sent to the calling view function

        :returns: executed request - caller responsible for handling errors and extracting results
        """
        # Correct Patient.id for this server
        # The original request prior to request_path names unwanted details
        full_path = original_request.url[original_request.url.find(request_path):]
        secondary_fhir_url = self.adjust_patient_query(full_path, launch_patient_id)
        current_app.logger.debug(f"attempt secondary FHIR request {secondary_fhir_url}")
        secondary_response = requests.request(
            url=secondary_fhir_url,
            method=original_request.method,
            headers=headers,
            json=original_request.json if original_request.method in ('POST', 'PUT') else None
        )
        return secondary_response

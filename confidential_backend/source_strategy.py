"""Source Strategy Module

Source abstraction typically represents FHIR Resource servers, but is not limited to such,
as additional source endpoints such as PDMP also use this abstraction.

Some sources are read only, others have a limited set of resources that can be written.

Clients maintain an ordered list of sources, attempting to read / write from each source,
returning after the first success.

NB instance state is not reliable across requests given multiple worker threads.  Use
session when state is required.
"""
from abc import ABC


class SourceStrategy(ABC):
    """Abstract interface, this API to be implemented by each source strategy class."""

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
        pass

    def empty_response(self, response):
        """Returns true if the response is empty, false otherwise."""
        pass

    def lookup_identified_patient(self, launch_patient):
        """Using config identifiers, look for a patient match on other FHIR server

        :param launch_patient: FHIR patient resource from launch FHIR server.
        :returns: secondary patient if an identifier match is found, otherwise None

        Using respective configured `MRN_SYSTEM`s, attempt to locate patient on other
        FHIR server.  If found, store in session and return matching patient resource

        :returns: secondary patient if an identifier match is found, otherwise None
        """
        pass

    def server_url(self):
        """Returns the configured server url for the respective source strategy."""
        pass

    def translated_patient_id(self):
        """Returns the launch patient id translated or mapped to the implementation
        strategy's patient id.
        """
        pass

    def server_request(self, request_path, launch_patient_id, upstream_headers, original_request):
        """Requests data from strategy source."""
        pass

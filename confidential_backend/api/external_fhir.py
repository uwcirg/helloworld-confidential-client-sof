"""Module for external FHIR implementation.

External FHIR refers to an additional FHIR endpoint, not to be confused
with the upstream endpoint, named on launch as the `iss` parameter, as part
of the standard SoF protocol.

External FHIR is outside the SoF protocol, used only when business logic
demands a secondary store must be used or considered.

The two FHIR stores are unique silos, and therefore, mappings between the two
often require an additional mapping to determine, for example, the respective
ID for a Patient in each respective system.

In order for the front-end apps to remain SoF compliant, expecting a single
FHIR endpoint for all requests, when configured to include an EXTERNAL_FHIR
endpoint - requests to the upstream FHIR are supplimented with resources from
the external source, but only when it makes sense.

Rules for when to include a resource from the External source:
- when a single resource is requested by ID, only if the upstream source
  yielded no results, will the search also be attempted from the external source
- when a resource type is requested naming a `subject` as a parameter, it
  is assumed the subject parameter refers to the upstream Patient.id,
  requiring a Patient.id map lookup and substitution.
- given the complexity of paging through result sets, and masquerading as
  part of the upstream request, downstream results will NOT be included if
  the upstream has more than a single page.

"""

def downstream_request(upstream_response, relative_path, **upstream_request_args):
    """Combine downstream response with upstream as per rules

    See rules at top of module; determine if downstream request should
    be modified or executed, then combine with upstream response

    :param upstream_response: JSON from upstream server, or None, in case of 404
    :param relative_path: the request path, minus server API portion
    :param upstream_request_args: all args included in upstream request
    :returns: JSON of response, inserted into upstream response if applicable

    """

    def next_link_in_bundle(response_json):
        """Check response - if a bundle with a next link, return True"""
        if response_json and response_json['resourceType'] == 'Bundle':
            # check for `relation: next` url in bundle links
            for item in response_json.get("link", []):
                if item.get("relation", "") == "next":
                    return True

    # multiple pages of results?  don't insert more in paginated as
    # we don't yet have the complex logic to keep pages in sync between the
    # two servers.  if the upstream results include a `next` page link,
    # simply return upstream results
    if next_link_in_bundle(upstream_response):
        return upstream_response

    downstream_server = current_app.config['EXTERNAL_FHIR_API']
    request_args = upstream_request_args.copy()
    request_args['url'] = '/'.join((downstream_server, relative_path))

    # if request appears in ResourceType/ID format, return upstream
    # result unless empty, as the request is assumed to be for a single
    parts = relative_path.split('/')
    if len(parts) == 2:
        if upstream_response:
            return upstream_response
        if parts[0] == 'Patient':
            # requires a map lookup for downstream version of patient.id
            downstream_patient_id = patient_id_map(parts[1])
            request_args['url'] = '/'.join((downstream_server, parts[0], downsream_patient_id))
        response = requests.request(**request_args)
        response.raise_for_status()
        return response.json()

    if 'subject' in request_args['params']:
        # must translate Subject.id to downstream version
        upstream_patient_id = request_args['params']['subject']
        downstream_patient_id = patient_id_map(upstream_patient_id)
        request_args['params']['subject'] = downstream_patient_id

    response = requests.request(**request_args)
    try:
        response.raise_for_status()
        if next_link_in_bundle(response.json()):
            current_app.logger.error(
                "Paginated results un-reachable in downstream server "
                f" {request_args['url']}/{request_args['params']}")
        # insert response JSON into upstream results
        collated = collate_results(upstream_response, response.json())
        return collated
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            # no results downstream, just return upstream
            return upstream_response
        current_app.logger.error(
            f"Failed request on downstream server {request_args['url']}"
            f"/{request_args['params']} ;;; {e}")
        raise e

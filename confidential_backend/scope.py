"""Module to manage scope definitions and checks"""
from fhir.smart.scopes import scopes


def http_method_to_access(method: str) -> str:
    method = method.upper()
    if method == "DELETE":
        return "d"
    if method in {"GET", "HEAD"}:
        return "rs"
    if method in {"POST", "PUT", "PATCH"}:
        return "cu"
    raise ValueError(f"Unsupported HTTP method: {method}")


def request_scope(context: str, request_path: str, http_method: str) -> scopes:
    """Generates a scopes object given request parameters

    :context: request context, one of {patient, user, system}
    :request_path: request_path string, typically names the desired resource, such as Patient or QuestionnaireResponse
        but may include query string parameters
    :http_method: HTTP request method, one of {DELETE, GET, HEAD, POST, PUT, PATCH}
    """
    resource, _ = request_path.split("?") if '?' in request_path else (request_path, "")
    if not resource:
        # Only known to happen when the second page in a bundle is requested.
        # difficult to manage at this level, return a very basic scope guaranteed
        # to work in most cases.  TODO find a better way
        resource = "Patient"

    cruds = http_method_to_access(http_method)
    return scopes(f"{context}/{resource}.{cruds}")

def request_allowed(request_scope, server_scope: scopes) -> bool:
    """Check if request is allowed on server

    :request_scope: build from request parameters, see `request_scope`
    :server_scope: the configured scope for server being probed

    :return: True if request is allowed, False otherwise
    """
    permitted_set = request_scope.intersection(server_scope)
    return len(permitted_set) > 0

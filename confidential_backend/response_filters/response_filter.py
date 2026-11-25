"""Abstract base for post-fetch response filters."""
from abc import ABC, abstractmethod


class ResponseFilter(ABC):
    """Optionally transform/filter a launch FHIR response using secondary source data.

    Filters run after a successful launch FHIR response, before returning to the client.
    They are resource-type aware and silently no-op on resource types they don't handle.
    """

    @abstractmethod
    def applies_to(self, resource_type: str) -> bool:
        """Return True if this filter should run for the given FHIR resource type."""
        pass

    @abstractmethod
    def filter(self, response_json: dict) -> dict:
        """Given a FHIR response (resource or Bundle), return filtered version."""
        pass

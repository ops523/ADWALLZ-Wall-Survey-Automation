from __future__ import annotations

from abc import ABC, abstractmethod

from src.streetview.models import ImageryQuery, ImageryResult


class StreetImageryProvider(ABC):
    """
    Provider-neutral interface for street-level imagery discovery.

    Contract:
    - The query heading is a requested viewing direction.
    - Providers are NOT required to return imagery captured at that heading.
    - If imagery is available, the provider should return its actual image
      heading when the provider exposes one.
    - Provider-specific API details must remain inside the provider.
    - Discovery orchestration is responsible for fallback between providers.
    """

    name: str

    @abstractmethod
    def find_nearby(
        self,
        query: ImageryQuery,
    ) -> ImageryResult:
        """
        Find the best available street-level image near a coordinate.

        Implementations must return:
        - AVAILABLE when usable imagery was found.
        - NOT_AVAILABLE when the provider has no suitable imagery.
        - ERROR when the provider could not complete the request.

        Implementations should not raise expected provider/API/network
        failures when they can reasonably represent them as ERROR.
        """
        raise NotImplementedError

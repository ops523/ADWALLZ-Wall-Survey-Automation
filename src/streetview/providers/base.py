from __future__ import annotations

from abc import ABC, abstractmethod

from src.streetview.models import ImageryQuery, ImageryResult


class StreetImageryProvider(ABC):
    """
    Common interface for all street-level imagery providers.
    """

    name: str

    @abstractmethod
    def find_nearby(
        self,
        query: ImageryQuery,
    ) -> ImageryResult:
        """
        Find the best available street-level image near a coordinate.
        """
        raise NotImplementedError

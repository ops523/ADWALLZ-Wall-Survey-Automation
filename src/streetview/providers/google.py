from __future__ import annotations

from src.streetview.client import StreetViewClient
from src.streetview.models import ImageryQuery, ImageryResult
from src.streetview.providers.base import StreetImageryProvider


class GoogleStreetViewProvider(StreetImageryProvider):
    name = "google"

    def __init__(
        self,
        client: StreetViewClient,
    ) -> None:
        self.client = client

    def find_nearby(
        self,
        query: ImageryQuery,
    ) -> ImageryResult:
        metadata = self.client.metadata(
            latitude=query.latitude,
            longitude=query.longitude,
            radius_m=query.radius_m,
        )

        if metadata.status == "OK":
            return ImageryResult(
                provider=self.name,
                status="AVAILABLE",
                image_id=metadata.pano_id,
                latitude=metadata.latitude,
                longitude=metadata.longitude,
                capture_date=metadata.date,
                heading=None,
                image_url=None,
                metadata=metadata.raw,
            )

        if metadata.status in {
            "ZERO_RESULTS",
            "NOT_FOUND",
        }:
            return ImageryResult(
                provider=self.name,
                status="NOT_AVAILABLE",
                image_id=None,
                latitude=None,
                longitude=None,
                capture_date=None,
                heading=None,
                image_url=None,
                metadata=metadata.raw,
            )

        return ImageryResult(
            provider=self.name,
            status="ERROR",
            image_id=None,
            latitude=None,
            longitude=None,
            capture_date=None,
            heading=None,
            image_url=None,
            metadata=metadata.raw,
        )

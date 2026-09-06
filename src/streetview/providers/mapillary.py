from __future__ import annotations

from typing import Any

import requests

from src.streetview.models import ImageryQuery, ImageryResult
from src.streetview.providers.base import StreetImageryProvider


MAPILLARY_IMAGES_URL = "https://graph.mapillary.com/images"


class MapillaryProvider(StreetImageryProvider):
    name = "mapillary"

    def __init__(
        self,
        access_token: str,
        timeout_seconds: float = 30.0,
        retry_count: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("Mapillary access token is required.")

        if timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than zero.")

        if retry_count < 0:
            raise ValueError("Retry count cannot be negative.")

        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.session = session or requests.Session()

    def _get(self, params: dict[str, Any]) -> requests.Response:
        last_error: Exception | None = None

        headers = {
            "Authorization": f"OAuth {self.access_token}",
        }

        for attempt in range(self.retry_count + 1):
            try:
                response = self.session.get(
                    MAPILLARY_IMAGES_URL,
                    params=params,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )

                if response.status_code >= 500:
                    raise requests.HTTPError(
                        f"Mapillary server error: {response.status_code}",
                        response=response,
                    )

                return response

            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.HTTPError,
            ) as exc:
                last_error = exc

                if attempt >= self.retry_count:
                    break

        assert last_error is not None
        raise last_error

    def find_nearby(self, query: ImageryQuery) -> ImageryResult:
        radius_m = min(max(query.radius_m, 0), 50)

        response = self._get(
            {
                "access_token": self.access_token,
                "lat": query.latitude,
                "lng": query.longitude,
                "radius": radius_m,
                "limit": 1,
                "fields": (
                    "id,"
                    "computed_geometry,"
                    "captured_at,"
                    "compass_angle,"
                    "computed_compass_angle,"
                    "thumb_1024_url"
                ),
            }
        )

        response.raise_for_status()

        payload = response.json()

        if "error" in payload:
            return ImageryResult(
                provider=self.name,
                status="ERROR",
                image_id=None,
                latitude=None,
                longitude=None,
                capture_date=None,
                heading=None,
                image_url=None,
                metadata=payload,
            )

        images = payload.get("data") or []

        if not images:
            return ImageryResult(
                provider=self.name,
                status="NOT_AVAILABLE",
                image_id=None,
                latitude=None,
                longitude=None,
                capture_date=None,
                heading=None,
                image_url=None,
                metadata=payload,
            )

        image = images[0]

        geometry = image.get("computed_geometry") or {}
        coordinates = geometry.get("coordinates") or []

        longitude = None
        latitude = None

        if len(coordinates) >= 2:
            longitude = coordinates[0]
            latitude = coordinates[1]

        capture_timestamp = image.get("captured_at")

        heading = image.get("computed_compass_angle")

        if heading is None:
            heading = image.get("compass_angle")

        return ImageryResult(
            provider=self.name,
            status="AVAILABLE",
            image_id=image.get("id"),
            latitude=latitude,
            longitude=longitude,
            capture_date=(
                str(capture_timestamp)
                if capture_timestamp is not None
                else None
            ),
            heading=heading,
            image_url=image.get("thumb_1024_url"),
            metadata=image,
        )

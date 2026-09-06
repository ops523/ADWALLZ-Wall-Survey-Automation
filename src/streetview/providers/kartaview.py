from __future__ import annotations

from typing import Any

import requests

from src.streetview.models import ImageryQuery, ImageryResult
from src.streetview.providers.base import StreetImageryProvider


KARTAVIEW_PHOTO_URL = (
    "https://api.openstreetcam.org/2.0/photo/"
)


class KartaViewProvider(StreetImageryProvider):
    name = "kartaview"

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero."
            )

        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def find_nearby(
        self,
        query: ImageryQuery,
    ) -> ImageryResult:
        response = self.session.get(
            KARTAVIEW_PHOTO_URL,
            params={
                "lat": query.latitude,
                "lng": query.longitude,
                "radius": query.radius_m,
                "zoomLevel": 18,
                "join": "sequence",
                "orderBy": "id",
                "orderDirection": "desc",
            },
            timeout=self.timeout_seconds,
        )

        response.raise_for_status()

        payload: dict[str, Any] = response.json()

        result = payload.get("result") or {}
        data = result.get("data") or []

        if not data:
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

        photo = data[0]

        return ImageryResult(
            provider=self.name,
            status="AVAILABLE",
            image_id=str(
                photo.get("id")
                or photo.get("photoId")
            ),
            latitude=_float_or_none(
                photo.get("lat")
                or photo.get("latitude")
            ),
            longitude=_float_or_none(
                photo.get("lng")
                or photo.get("longitude")
            ),
            capture_date=(
                photo.get("shotDate")
                or photo.get("dateAdded")
                or photo.get("date_added")
            ),
            heading=_float_or_none(
                photo.get("heading")
                or photo.get("bearing")
            ),
            image_url=(
                photo.get("fileUrl")
                or photo.get("file_url")
                or photo.get("url")
            ),
            metadata=photo,
        )


def _float_or_none(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

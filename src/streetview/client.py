from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


METADATA_URL = (
    "https://maps.googleapis.com/maps/api/streetview/metadata"
)

IMAGE_URL = (
    "https://maps.googleapis.com/maps/api/streetview"
)


@dataclass(frozen=True)
class StreetViewMetadata:
    status: str
    pano_id: str | None
    latitude: float | None
    longitude: float | None
    date: str | None
    copyright: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class StreetViewImageRequest:
    latitude: float
    longitude: float
    heading: float
    fov: float
    pitch: float
    width: int
    height: int
    radius_m: int
    source: str = "outdoor"


class StreetViewClient:
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 30.0,
        retry_count: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(
                "Google Street View API key is required."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero."
            )

        if retry_count < 0:
            raise ValueError(
                "Retry count cannot be negative."
            )

        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.session = session or requests.Session()

    def _get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> requests.Response:
        last_error: Exception | None = None

        for attempt in range(
            self.retry_count + 1
        ):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )

                if response.status_code >= 500:
                    raise requests.HTTPError(
                        f"Server error: {response.status_code}",
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

                time.sleep(
                    min(
                        2 ** attempt,
                        8,
                    )
                )

        assert last_error is not None
        raise last_error

    def metadata(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 50,
    ) -> StreetViewMetadata:
        if radius_m < 0:
            raise ValueError(
                "Street View radius cannot be negative."
            )

        response = self._get(
            METADATA_URL,
            params={
                "location": (
                    f"{latitude:.7f},"
                    f"{longitude:.7f}"
                ),
                "radius": radius_m,
                "source": "outdoor",
                "key": self.api_key,
            },
        )

        response.raise_for_status()

        payload = response.json()

        location = payload.get(
            "location"
        ) or {}

        return StreetViewMetadata(
            status=str(
                payload.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            pano_id=payload.get(
                "pano_id"
            ),
            latitude=location.get(
                "lat"
            ),
            longitude=location.get(
                "lng"
            ),
            date=payload.get(
                "date"
            ),
            copyright=payload.get(
                "copyright"
            ),
            raw=payload,
        )

    def image_url(
        self,
        request: StreetViewImageRequest,
    ) -> str:
        params = {
            "size": (
                f"{request.width}x"
                f"{request.height}"
            ),
            "location": (
                f"{request.latitude:.7f},"
                f"{request.longitude:.7f}"
            ),
            "heading": request.heading % 360.0,
            "fov": request.fov,
            "pitch": request.pitch,
            "radius": request.radius_m,
            "source": request.source,
            "return_error_code": "true",
            "key": self.api_key,
        }

        prepared = requests.Request(
            "GET",
            IMAGE_URL,
            params=params,
        ).prepare()

        return prepared.url

    def download_image(
        self,
        request: StreetViewImageRequest,
        output_path: str | Path,
    ) -> Path:
        url = self.image_url(request)

        response = self._get(
            url,
            params={},
        )

        response.raise_for_status()

        output = Path(output_path)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_bytes(
            response.content
        )

        return output

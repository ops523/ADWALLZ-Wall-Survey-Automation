from __future__ import annotations

from typing import Any

from src.streetview.models import ImageryQuery
from src.streetview.providers.mapillary import MapillaryProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "kwargs": kwargs,
            }
        )
        return self.response


def test_mapillary_returns_available_image() -> None:
    response = FakeResponse(
        {
            "data": [
                {
                    "id": "mapillary-123",
                    "computed_geometry": {
                        "type": "Point",
                        "coordinates": [78.7081, 15.9149],
                    },
                    "captured_at": 1750000000000,
                    "compass_angle": 91.0,
                    "computed_compass_angle": 92.0,
                    "thumb_1024_url": "https://example.com/image.jpg",
                }
            ]
        }
    )

    session = FakeSession(response)

    provider = MapillaryProvider(
        access_token="test-token",
        session=session,
    )

    result = provider.find_nearby(
        ImageryQuery(
            latitude=15.9149208,
            longitude=78.7079658,
            radius_m=50,
        )
    )

    assert result.provider == "mapillary"
    assert result.status == "AVAILABLE"
    assert result.image_id == "mapillary-123"
    assert result.latitude == 15.9149
    assert result.longitude == 78.7081
    assert result.heading == 92.0


def test_mapillary_returns_not_available() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "data": []
            }
        )
    )

    provider = MapillaryProvider(
        access_token="test-token",
        session=session,
    )

    result = provider.find_nearby(
        ImageryQuery(
            latitude=15.9149208,
            longitude=78.7079658,
            radius_m=50,
        )
    )

    assert result.provider == "mapillary"
    assert result.status == "NOT_AVAILABLE"


def test_mapillary_radius_is_capped_at_50m() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "data": []
            }
        )
    )

    provider = MapillaryProvider(
        access_token="test-token",
        session=session,
    )

    provider.find_nearby(
        ImageryQuery(
            latitude=15.9149208,
            longitude=78.7079658,
            radius_m=100,
        )
    )

    params = session.calls[0]["kwargs"]["params"]

    assert params["radius"] == 50
    assert params["limit"] == 1

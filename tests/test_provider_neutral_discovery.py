from __future__ import annotations

from dataclasses import dataclass

from src.streetview.discovery import ImageryDiscovery
from src.streetview.models import ImageryQuery, ImageryResult
from src.streetview.providers.base import StreetImageryProvider


@dataclass
class FakeProvider(StreetImageryProvider):
    name: str
    result: ImageryResult | None = None
    exception: Exception | None = None
    calls: int = 0
    received_queries: list[ImageryQuery] | None = None

    def __post_init__(self) -> None:
        self.received_queries = []

    def find_nearby(
        self,
        query: ImageryQuery,
    ) -> ImageryResult:
        self.calls += 1
        assert self.received_queries is not None
        self.received_queries.append(query)

        if self.exception is not None:
            raise self.exception

        assert self.result is not None
        return self.result


def available_result(
    provider: str,
    image_id: str,
    heading: float | None = None,
) -> ImageryResult:
    return ImageryResult(
        provider=provider,
        status="AVAILABLE",
        image_id=image_id,
        latitude=14.67,
        longitude=79.57,
        capture_date="2026-01-01",
        heading=heading,
        image_url=f"https://example.com/{image_id}.jpg",
        metadata={
            "source": provider,
        },
    )


def unavailable_result(
    provider: str,
) -> ImageryResult:
    return ImageryResult(
        provider=provider,
        status="NOT_AVAILABLE",
        image_id=None,
        latitude=None,
        longitude=None,
        capture_date=None,
        heading=None,
        image_url=None,
        metadata={
            "source": provider,
        },
    )


def error_result(
    provider: str,
) -> ImageryResult:
    return ImageryResult(
        provider=provider,
        status="ERROR",
        image_id=None,
        latitude=None,
        longitude=None,
        capture_date=None,
        heading=None,
        image_url=None,
        metadata={
            "source": provider,
        },
    )


def test_fallback_from_unavailable_to_next_provider() -> None:
    google = FakeProvider(
        name="google",
        result=unavailable_result("google"),
    )

    mapillary = FakeProvider(
        name="mapillary",
        result=available_result(
            provider="mapillary",
            image_id="map-1",
            heading=92.0,
        ),
    )

    discovery = ImageryDiscovery(
        providers=[google, mapillary],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=90.0,
    )

    assert result.status == "AVAILABLE"
    assert result.provider == "mapillary"
    assert result.image_id == "map-1"

    assert google.calls == 1
    assert mapillary.calls == 1

    assert result.metadata["requested_heading"] == 90.0

    assert result.metadata["attempts"] == [
        {
            "provider": "google",
            "status": "NOT_AVAILABLE",
        },
        {
            "provider": "mapillary",
            "status": "AVAILABLE",
        },
    ]


def test_fallback_from_error_to_next_provider() -> None:
    google = FakeProvider(
        name="google",
        result=error_result("google"),
    )

    kartaview = FakeProvider(
        name="kartaview",
        result=available_result(
            provider="kartaview",
            image_id="karta-1",
            heading=181.0,
        ),
    )

    discovery = ImageryDiscovery(
        providers=[google, kartaview],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=270.0,
    )

    assert result.status == "AVAILABLE"
    assert result.provider == "kartaview"
    assert result.image_id == "karta-1"

    assert result.metadata["requested_heading"] == 270.0

    assert result.metadata["attempts"] == [
        {
            "provider": "google",
            "status": "ERROR",
        },
        {
            "provider": "kartaview",
            "status": "AVAILABLE",
        },
    ]


def test_provider_exception_does_not_break_discovery() -> None:
    failing = FakeProvider(
        name="mapillary",
        exception=TimeoutError(
            "provider timed out"
        ),
    )

    working = FakeProvider(
        name="kartaview",
        result=available_result(
            provider="kartaview",
            image_id="karta-2",
            heading=45.0,
        ),
    )

    discovery = ImageryDiscovery(
        providers=[failing, working],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=45.0,
    )

    assert result.status == "AVAILABLE"
    assert result.provider == "kartaview"

    assert result.metadata["attempts"] == [
        {
            "provider": "mapillary",
            "status": "ERROR",
            "error_type": "TimeoutError",
            "error_message": "provider timed out",
        },
        {
            "provider": "kartaview",
            "status": "AVAILABLE",
        },
    ]


def test_all_providers_unavailable() -> None:
    google = FakeProvider(
        name="google",
        result=unavailable_result("google"),
    )

    mapillary = FakeProvider(
        name="mapillary",
        result=unavailable_result("mapillary"),
    )

    kartaview = FakeProvider(
        name="kartaview",
        result=unavailable_result("kartaview"),
    )

    discovery = ImageryDiscovery(
        providers=[
            google,
            mapillary,
            kartaview,
        ],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=180.0,
    )

    assert result.status == "NOT_AVAILABLE"
    assert result.provider == "none"
    assert result.image_id is None

    assert result.metadata["requested_heading"] == 180.0

    assert result.metadata["attempts"] == [
        {
            "provider": "google",
            "status": "NOT_AVAILABLE",
        },
        {
            "provider": "mapillary",
            "status": "NOT_AVAILABLE",
        },
        {
            "provider": "kartaview",
            "status": "NOT_AVAILABLE",
        },
    ]


def test_first_available_provider_wins() -> None:
    first = FakeProvider(
        name="google",
        result=available_result(
            provider="google",
            image_id="google-1",
        ),
    )

    second = FakeProvider(
        name="mapillary",
        result=available_result(
            provider="mapillary",
            image_id="map-2",
        ),
    )

    discovery = ImageryDiscovery(
        providers=[first, second],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
    )

    assert result.provider == "google"
    assert result.image_id == "google-1"

    assert first.calls == 1
    assert second.calls == 0


def test_requested_and_actual_heading_remain_distinct() -> None:
    provider = FakeProvider(
        name="mapillary",
        result=available_result(
            provider="mapillary",
            image_id="map-heading",
            heading=271.0,
        ),
    )

    discovery = ImageryDiscovery(
        providers=[provider],
    )

    result = discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=90.0,
    )

    assert result.metadata["requested_heading"] == 90.0
    assert result.heading == 271.0


def test_provider_receives_normalized_requested_heading() -> None:
    provider = FakeProvider(
        name="google",
        result=available_result(
            provider="google",
            image_id="google-heading",
        ),
    )

    discovery = ImageryDiscovery(
        providers=[provider],
    )

    discovery.discover(
        latitude=14.67,
        longitude=79.57,
        heading=450.0,
    )

    assert provider.received_queries is not None
    assert len(provider.received_queries) == 1
    assert provider.received_queries[0].heading == 90.0


def test_side_fallback_preserves_side_identity() -> None:
    google = FakeProvider(
        name="google",
        result=unavailable_result("google"),
    )

    mapillary = FakeProvider(
        name="mapillary",
        result=available_result(
            provider="mapillary",
            image_id="map-side",
            heading=271.0,
        ),
    )

    discovery = ImageryDiscovery(
        providers=[google, mapillary],
    )

    side = discovery.discover_side(
        point_id="P001",
        latitude=14.67,
        longitude=79.57,
        side="RIGHT",
        heading=270.0,
    )

    assert side.point_id == "P001"
    assert side.side == "right"
    assert side.requested_heading == 270.0
    assert side.provider == "mapillary"
    assert side.image_id == "map-side"
    assert side.image_heading == 271.0

from __future__ import annotations

from pathlib import Path

from src.streetview.cache import ImageryCache
from src.streetview.discovery import ImageryDiscovery
from src.streetview.models import (
    ImageryResult,
    SideImageryResult,
)
from src.streetview.providers.base import StreetImageryProvider


class FakeProvider(StreetImageryProvider):
    name = "fake"

    def __init__(self) -> None:
        self.queries = []

    def find_nearby(self, query):
        self.queries.append(query)

        return ImageryResult(
            provider=self.name,
            status="AVAILABLE",
            image_id=f"image-{query.heading}",
            latitude=query.latitude,
            longitude=query.longitude,
            capture_date="2026-01",
            heading=query.heading,
            image_url=None,
            metadata={
                "query_heading": query.heading,
            },
        )


def test_discover_normalizes_heading():
    provider = FakeProvider()

    discovery = ImageryDiscovery(
        providers=[provider],
    )

    result = discovery.discover(
        latitude=14.669176,
        longitude=79.5743613,
        heading=450,
    )

    assert result.status == "AVAILABLE"
    assert result.metadata["requested_heading"] == 90.0
    assert provider.queries[0].heading == 90.0


def test_discover_side_preserves_side_identity():
    provider = FakeProvider()

    discovery = ImageryDiscovery(
        providers=[provider],
    )

    result = discovery.discover_side(
        point_id="P001",
        latitude=14.669176,
        longitude=79.5743613,
        side="LEFT",
        heading=450,
    )

    assert isinstance(result, SideImageryResult)
    assert result.point_id == "P001"
    assert result.side == "left"
    assert result.requested_heading == 90.0
    assert result.image_id == "image-90.0"


def test_discover_side_rejects_invalid_side():
    discovery = ImageryDiscovery(
        providers=[FakeProvider()],
    )

    try:
        discovery.discover_side(
            point_id="P001",
            latitude=14.669176,
            longitude=79.5743613,
            side="front",
            heading=90,
        )
    except ValueError as exc:
        assert "left" in str(exc)
        assert "right" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for invalid side"
        )


def test_discover_both_sides_keeps_headings_separate():
    provider = FakeProvider()

    discovery = ImageryDiscovery(
        providers=[provider],
    )

    left, right = discovery.discover_both_sides(
        point_id="P001",
        latitude=14.669176,
        longitude=79.5743613,
        heading_left=90,
        heading_right=270,
    )

    assert left.side == "left"
    assert right.side == "right"

    assert left.requested_heading == 90.0
    assert right.requested_heading == 270.0

    assert left.image_id == "image-90.0"
    assert right.image_id == "image-270.0"


def test_heading_aware_discovery_cache_does_not_cross_sides(
    tmp_path: Path,
):
    cache = ImageryCache(
        tmp_path / "imagery.json"
    )

    provider = FakeProvider()

    discovery = ImageryDiscovery(
        providers=[provider],
        cache=cache,
    )

    first = discovery.discover(
        latitude=14.669176,
        longitude=79.5743613,
        heading=90,
    )

    second = discovery.discover(
        latitude=14.669176,
        longitude=79.5743613,
        heading=270,
    )

    assert first.image_id == "image-90.0"
    assert second.image_id == "image-270.0"

    assert len(provider.queries) == 2

    # Same heading should now be served from cache.
    cached = discovery.discover(
        latitude=14.669176,
        longitude=79.5743613,
        heading=90,
    )

    assert cached.image_id == "image-90.0"
    assert cached.metadata["cache_hit"] is True

    assert len(provider.queries) == 2

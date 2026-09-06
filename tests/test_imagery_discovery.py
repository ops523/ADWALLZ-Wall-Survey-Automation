from __future__ import annotations

from typing import Any

from src.streetview.cache import ImageryCache
from src.streetview.discovery import ImageryDiscovery
from src.streetview.models import ImageryQuery, ImageryResult


class FakeProvider:
    def __init__(self, name: str, status: str) -> None:
        self.name = name
        self.status = status
        self.calls = 0

    def find_nearby(self, query: ImageryQuery) -> ImageryResult:
        self.calls += 1

        return ImageryResult(
            provider=self.name,
            status=self.status,
            image_id=f"{self.name}-image",
            latitude=query.latitude,
            longitude=query.longitude,
            capture_date="2026-01-01",
            heading=90.0,
            image_url=f"https://example.com/{self.name}.jpg",
            metadata={},
        )


def test_first_available_provider_is_used() -> None:
    first = FakeProvider("google", "AVAILABLE")
    second = FakeProvider("mapillary", "AVAILABLE")

    discovery = ImageryDiscovery([first, second])

    result = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    assert result.provider == "google"
    assert result.status == "AVAILABLE"
    assert first.calls == 1
    assert second.calls == 0


def test_fallback_to_second_provider() -> None:
    first = FakeProvider("google", "NOT_AVAILABLE")
    second = FakeProvider("mapillary", "AVAILABLE")

    discovery = ImageryDiscovery([first, second])

    result = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    assert result.provider == "mapillary"
    assert result.status == "AVAILABLE"
    assert first.calls == 1
    assert second.calls == 1


def test_no_provider_available() -> None:
    first = FakeProvider("google", "NOT_AVAILABLE")
    second = FakeProvider("mapillary", "NOT_AVAILABLE")

    discovery = ImageryDiscovery([first, second])

    result = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    assert result.provider == "none"
    assert result.status == "NOT_AVAILABLE"
    assert first.calls == 1
    assert second.calls == 1


def test_cache_prevents_second_provider_call(tmp_path) -> None:
    cache = ImageryCache(tmp_path / "imagery_cache.json")

    provider = FakeProvider("google", "AVAILABLE")

    discovery = ImageryDiscovery(
        providers=[provider],
        cache=cache,
    )

    first = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    second = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    assert first.provider == "google"
    assert second.provider == "google"
    assert second.status == "AVAILABLE"

    assert provider.calls == 1
    assert second.metadata["cache_hit"] is True


def test_negative_result_is_cached(tmp_path) -> None:
    cache = ImageryCache(tmp_path / "imagery_cache.json")

    provider = FakeProvider("google", "NOT_AVAILABLE")

    discovery = ImageryDiscovery(
        providers=[provider],
        cache=cache,
    )

    first = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    second = discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
    )

    assert first.provider == "none"
    assert first.status == "NOT_AVAILABLE"

    assert second.provider == "none"
    assert second.status == "NOT_AVAILABLE"

    assert provider.calls == 1
    assert second.metadata["cache_hit"] is True


def test_cache_is_radius_specific(tmp_path) -> None:
    cache = ImageryCache(tmp_path / "imagery_cache.json")

    provider = FakeProvider("google", "AVAILABLE")

    discovery = ImageryDiscovery(
        providers=[provider],
        cache=cache,
    )

    discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
        radius_m=50,
    )

    discovery.discover(
        latitude=15.9149,
        longitude=78.7080,
        radius_m=25,
    )

    assert provider.calls == 2
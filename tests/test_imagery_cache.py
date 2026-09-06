from __future__ import annotations

from src.streetview.cache import ImageryCache


def test_cache_round_trip(tmp_path):
    cache = ImageryCache(
        tmp_path / "imagery.json"
    )

    value = {
        "status": "AVAILABLE",
        "image_id": "test-image",
    }

    cache.set(
        provider="google",
        latitude=15.9149208,
        longitude=78.7079658,
        radius_m=50,
        value=value,
    )

    result = cache.get(
        provider="google",
        latitude=15.9149208,
        longitude=78.7079658,
        radius_m=50,
    )

    assert result == value


def test_cache_key_is_provider_specific():
    google_key = ImageryCache.make_key(
        "google",
        15.9149208,
        78.7079658,
        50,
    )

    kartaview_key = ImageryCache.make_key(
        "kartaview",
        15.9149208,
        78.7079658,
        50,
    )

    assert google_key != kartaview_key
